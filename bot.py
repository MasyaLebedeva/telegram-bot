import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
logger.info(f"TELEGRAM_TOKEN: {'установлен' if API_TOKEN else 'не установлен'}")
if not API_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения")
CHANNEL_ID = "-1001324681912"
CHANNEL_LINK = "https://t.me/lebedevamariiatgm"
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"https://gigtest-bot-new.onrender.com{WEBHOOK_PATH}"

# Инициализация
logger.info("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
app = web.Application()

# Обработчик команды /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    logger.info(f"START: Команда /start от {message.from_user.id}")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Проверить подписку ✅", callback_data="check_subscription")]
    ])
    await message.answer(
        "👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал",
        reply_markup=markup
    )

# Обработчик для check_subscription
@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def process_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"CHECK_SUB: Callback от {user_id}: {callback.data}")
    try:
        logger.info(f"CHECK_SUB: Проверка статуса для user_id={user_id} в канале {CHANNEL_ID}")
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        logger.info(f"CHECK_SUB: Статус: {member.status}")
        if member.status in ["member", "administrator", "creator"]:
            await bot.send_message(
                user_id,
                "🎉 Спасибо за подписку. Держи файл с ответами на тесты: "
                "https://docs.google.com/document/d/1wRpzasug5kSagNZgtG2QlSRMyK-7PP3ZYvNcejoDkoo/edit?usp=sharing"
            )
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)]
            ])
            await bot.send_message(
                user_id,
                "😔 Упс. Кажется, ты не подписался на канал. Подпишись!",
                reply_markup=markup
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"CHECK_SUB: Ошибка: {type(e).__name__}: {e}")
        await bot.send_message(user_id, "😓 Ошибка проверки подписки. Попробуй позже.")
        await callback.answer("Ошибка")

# Webhook и health check
async def webhook(request):
    logger.info("Получен запрос на вебхук")
    try:
        data = await request.json()
        logger.info(f"Данные вебхука: {data}")
        update = types.Update(**data)
        await dp.process_update(update)
        return web.json_response({"status": "ok"})
    except Exception as e:
        logger.error(f"Webhook ошибка: {type(e).__name__}: {e}")
        return web.json_response({"status": "error"}, status=500)

async def health(request):
    logger.info("Получен запрос на /health")
    return web.json_response({"status": "healthy"})

# Добавление маршрутов
app.router.add_post(WEBHOOK_PATH, webhook)
app.router.add_get("/health", health)

# Установка webhook
async def on_startup(_):
    try:
        logger.info("Удаление старого вебхука...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info(f"Установка нового вебхука: {WEBHOOK_URL}")
        await bot.set_webhook(WEBHOOK_URL)
        logger.info("Webhook успешно установлен для @gigtestibot")
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {type(e).__name__}: {e}")
        raise

# Запуск сервера
async def start_app():
    try:
        port = os.getenv("PORT")
        logger.info(f"Получен PORT из окружения: {port}")
        if not port:
            raise ValueError("Переменная окружения PORT не задана")
        try:
            port = int(port)
        except ValueError as e:
            logger.error(f"Ошибка преобразования PORT в число: {e}")
            raise
        logger.info(f"Используемый порт: {port}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Бот @gigtestibot запущен на порту {port}")
        await on_startup(None)
        return app  # Возвращаем приложение для запуска
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {type(e).__name__}: {e}")
        raise
import socket

# Запуск сервера
async def start_app():
    try:
        port = os.getenv("PORT")
        logger.info(f"Получен PORT из окружения: {port}")
        if not port:
            raise ValueError("Переменная окружения PORT не задана")
        try:
            port = int(port)
        except ValueError as e:
            logger.error(f"Ошибка преобразования PORT в число: {e}")
            raise
        # Проверка доступности порта
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                logger.info(f"Порт {port} свободен")
            except OSError as e:
                logger.error(f"Порт {port} занят: {type(e).__name__}: {e}")
                raise
        logger.info(f"Используемый порт: {port}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Бот @gigtestibot запущен на порту {port}")
        await on_startup(None)
        return app
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {type(e).__name__}: {e}")
        raise

import socket

# Запуск сервера
async def start_app():
    try:
        port = os.getenv("PORT")
        logger.info(f"Получен PORT из окружения: {port}")
        if not port:
            raise ValueError("Переменная окружения PORT не задана")
        try:
            port = int(port)
        except ValueError as e:
            logger.error(f"Ошибка преобразования PORT в число: {e}")
            raise
        # Проверка доступности порта
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                logger.info(f"Порт {port} свободен")
            except OSError as e:
                logger.error(f"Порт {port} занят: {type(e).__name__}: {e}")
                raise
        logger.info(f"Используемый порт: {port}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Бот @gigtestibot запущен на порту {port}")
        await on_startup(None)
        return app
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {type(e).__name__}: {e}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Запуск приложения...")
        port = os.getenv("PORT", "8080")
        logger.info(f"Финальный порт для запуска: {port}")
        # Проверка доступности порта
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", int(port)))
                logger.info(f"Порт {port} доступен для запуска")
            except OSError as e:
                logger.error(f"Порт {port} занят перед запуском: {type(e).__name__}: {e}")
                raise
        web.run_app(start_app(), host="0.0.0.0", port=int(port))
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {type(e).__name__}: {e}")
        raise
