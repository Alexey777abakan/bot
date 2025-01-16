import logging
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    MenuButtonCommands, BotCommand
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из .env
load_dotenv()

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "bot.log")),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль
    ]
)
logger = logging.getLogger(__name__)

# Данные бота из переменных окружения
API_TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@sozvezdie_skidok")  # Публичное имя канала
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Созвездие скидок")  # Название канала
ADMIN_ID = int(os.getenv("ADMIN_ID"))
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # URL вашего бота на Render
PORT = int(os.getenv("PORT", 5000))  # Порт для веб-сервера

# Проверяем, что токен загружен
if not API_TOKEN:
    raise ValueError("Токен не найден. Убедитесь, что переменная окружения API_TOKEN установлена.")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class Form(StatesGroup):
    welcome = State()
    menu = State()
    phone = State()
    broadcast = State()  # Состояние для рассылки

# Клавиатуры
def create_welcome_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Начать")],
            [KeyboardButton(text="ℹ️ Помощь")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def create_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💳 Кредитные карты"), KeyboardButton(text="💰 Займ-Мастер")],
            [KeyboardButton(text="🛡️ Страхование"), KeyboardButton(text="💼 Карьерный навигатор")],
            [KeyboardButton(text="🎁 Сокровищница выгод"), KeyboardButton(text="🔄 Начать заново")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def subscribe_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📢 Подписаться на канал {CHANNEL_NAME}", url=f"https://t.me/{CHANNEL_ID[1:]}")],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
    ])

def create_credit_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Кредитные карты", callback_data="credit_cards")],
        [InlineKeyboardButton(text="Кредитный навигатор", url="https://ppdu.ru/956606fa-02c7-4389-9069-943c0ab8c02b")],
        [InlineKeyboardButton(text="СберБанк - Кредитная СберКарта", url="https://trk.ppdu.ru/click/3RujX0b6?erid=2SDnjcVm7Md")],
        [InlineKeyboardButton(text="Т-Банк - Кредитная карта Платинум", url="https://trk.ppdu.ru/click/1McwYwsf?erid=2SDnjcyz7NY")],
        [InlineKeyboardButton(text="Уралсиб - Кредитная карта с кешбэком", url="https://trk.ppdu.ru/click/bhA4OaNe?erid=2SDnje5iw3n")],
        [InlineKeyboardButton(text="Т-Банк — Кредитная карта Платинум// Кешбэк 2 000 рублей", url="https://trk.ppdu.ru/click/QYJQHNtB?erid=2SDnjdSG9a1")],
        [InlineKeyboardButton(text="Совкомбанк - Карта рассрочки Халва МИР", url="https://trk.ppdu.ru/click/8lDSWnJn?erid=Kra23XHz1")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_loans_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Займ-Мастер", url="https://ppdu.ru/8bfd124d-1628-4eb2-a238-531a4c629329")],
        [InlineKeyboardButton(text="MoneyMan", url="https://trk.ppdu.ru/click/iaxTaZ7u?erid=2SDnjd4NP9c")],
        [InlineKeyboardButton(text="Joymoney", url="https://trk.ppdu.ru/click/1Uf12FL6?erid=Kra23wZmP")],
        [InlineKeyboardButton(text="Целевые финансы", url="https://trk.ppdu.ru/click/uqh4iG8P?erid=2SDnjeePynH")],
        [InlineKeyboardButton(text="ДоброЗайм", url="https://trk.ppdu.ru/click/VGWQ7lRU?erid=2SDnjdGSjHa")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_jobs_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Карьерный навигатор", url="https://ppdu.ru/c8f23f85-45da-4804-a190-e6a358a9061b")],
        [InlineKeyboardButton(text="Курьер в Яндекс.Еда/Яндекс.Лавка", url="https://trk.ppdu.ru/click/80UG6A1L?erid=Kra23uVC3")],
        [InlineKeyboardButton(text="Магнит // Водитель категории Е", url="https://trk.ppdu.ru/click/kUTRwEqg?erid=2SDnjcR2t2N")],
        [InlineKeyboardButton(text="Курьер/Повар-кассир в Burger King", url="https://trk.ppdu.ru/click/UpMcqi2J?erid=2SDnjdu6ZqS")],
        [InlineKeyboardButton(text="Альфа банк // Специалист по доставке пластиковых карт", url="https://trk.ppdu.ru/click/Sg02KcAS?erid=2SDnjbsvvT3")],
        [InlineKeyboardButton(text="Т-Банк — Работа в Т-Банке", url="https://trk.ppdu.ru/click/JdRx49qY?erid=2SDnjcbs16H")],
        [InlineKeyboardButton(text="Специалист по продажам услуг МТС", url="https://trk.ppdu.ru/click/8Vv8AUVS?erid=2SDnjdhc8em")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_insurance_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Осаго", url="https://b2c.pampadu.ru/index.html#2341f23d-fced-49e1-8ecc-2184e809bf77")],
        [InlineKeyboardButton(text="Страхование ипотеки", url="https://ipoteka.pampadu.ru/index.html#c46f5bfd-5d57-41d8-889c-61b8b6860cad")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def create_treasure_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Сокровищница выгод: ваш подарок уже ждет!", url="https://ppdu.ru/gifts/c94552a5-a5b6-4e65-b191-9b6bc36cd85b")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Словарь для хранения соответствий между командами и клавиатурами
MENU_OPTIONS = {
    "💳 Кредитные карты": create_credit_keyboard,
    "💰 Займ-Мастер": create_loans_keyboard,
    "💼 Карьерный навигатор": create_jobs_keyboard,
    "🛡️ Страхование": create_insurance_keyboard,
    "🎁 Сокровищница выгод": create_treasure_keyboard
}

# Функции для работы с базой данных
async def init_db():
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                phone TEXT,
                first_interaction BOOLEAN DEFAULT FALSE
            )
        ''')
        await db.commit()

async def add_user(user_id, phone):
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id, phone, first_interaction) VALUES (?, ?, ?)', (user_id, phone, True))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        async with db.execute('SELECT * FROM users') as cursor:
            rows = await cursor.fetchall()
            return rows

async def user_has_phone(user_id):
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        async with db.execute('SELECT phone FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None and row[0] is not None

async def user_first_interaction(user_id):
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        async with db.execute('SELECT first_interaction FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None and row[0]

async def set_first_interaction(user_id):
    async with aiosqlite.connect(os.getenv("DATABASE_URL", "users.db")) as db:
        await db.execute('UPDATE users SET first_interaction = TRUE WHERE user_id = ?', (user_id,))
        await db.commit()

# Аналитика
async def log_user_action(user_id: int, action: str):
    logger.info(f"Пользователь {user_id} выполнил действие: {action}")

# Настройка меню
async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Запустить бота"),
        BotCommand(command="/help", description="Помощь"),
        BotCommand(command="/menu", description="Главное меню"),
    ]

    try:
        await bot.set_my_commands(commands)
        logger.info("Команды успешно установлены.")
    except Exception as e:
        logger.error(f"Ошибка при установке команд: {e}")

    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Меню успешно установлено в левом нижнем углу.")
    except Exception as e:
        logger.error(f"Ошибка при установке меню: {e}")

async def on_startup(bot: Bot):
    await set_main_menu(bot)
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")

# Обработчики
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await log_user_action(user_id, "запустил бота")
    first_interaction = await user_first_interaction(user_id)

    if first_interaction:
        if await user_has_phone(user_id):
            await state.set_state(Form.menu)
            await message.answer(
                "👋 Добро пожаловать обратно! 🎉\n\n"
                "Выберите раздел, чтобы продолжить:",
                reply_markup=create_menu_keyboard()
            )
        else:
            await state.set_state(Form.welcome)
            await message.answer(
                "👋 Привет! Добро пожаловать в наш бот! 🎉\n\n"
                "Здесь вы можете:\n"
                "💳 Оформить кредит\n"
                "💰 Получить займ\n"
                "🛡️ Оформить страховку\n"
                "💼 Найти работу\n\n"
                "Выберите действие ниже:",
                reply_markup=create_welcome_keyboard()
            )
    else:
        await state.set_state(Form.welcome)
        await message.answer(
            "👋 Привет! Добро пожаловать в наш бот! 🎉\n\n"
            "Здесь вы можете:\n"
            "💳 Оформить кредит\n"
            "💰 Получить займ\n"
            "🛡️ Оформить страховку\n"
            "💼 Найти работу\n\n"
            "Выберите действие ниже:",
            reply_markup=create_welcome_keyboard()
        )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await log_user_action(message.from_user.id, "запросил помощь")
    help_text = """
    📚 **Помощь**

    - **/start**: Запустить бота.
    - **/menu**: Вернуться в главное меню.
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message, state: FSMContext):
    await log_user_action(message.from_user.id, "открыл меню")
    await state.set_state(Form.menu)
    await message.answer("Выберите раздел:", reply_markup=create_menu_keyboard())

@dp.message(StateFilter(Form.welcome), lambda message: message.text == "🚀 Начать")
async def process_welcome_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await log_user_action(user_id, "нажал 'Начать'")
    await set_first_interaction(user_id)
    
    if await user_has_phone(user_id):
        await state.set_state(Form.menu)
        await message.answer("Выберите раздел:", reply_markup=create_menu_keyboard())
    else:
        await state.set_state(Form.phone)
        await message.answer("Пожалуйста, поделитесь своим номером телефона, чтобы продолжить.", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Поделиться номером", request_contact=True)]],
            resize_keyboard=True
        ))

@dp.message(StateFilter(Form.welcome), lambda message: message.text == "ℹ️ Помощь")
async def process_welcome_help(message: types.Message):
    await log_user_action(message.from_user.id, "запросил помощь")
    help_text = """
    📚 **Помощь**

    - **/start**: Запустить бота.
    - **/menu**: Вернуться в главное меню.
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(StateFilter(Form.menu))
async def process_menu_selection(message: types.Message, state: FSMContext):
    option = message.text
    if option in MENU_OPTIONS:
        await log_user_action(message.from_user.id, f"выбрал раздел: {option}")
        
        # Проверяем подписку на канал
        try:
            chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=message.from_user.id)
            if chat_member.status in ["member", "administrator", "creator"]:
                # Пользователь подписан, показываем офферы
                keyboard = MENU_OPTIONS[option]()
                await message.answer("Выберите опцию:", reply_markup=keyboard)
            else:
                # Пользователь не подписан, просим подписаться
                await message.answer(
                    f"❌ Для доступаOops! DeepSeek is experiencing high traffic at the moment. Please check back in a little while.Oops! DeepSeek is experiencing high traffic at the moment. Please check back in a little while.