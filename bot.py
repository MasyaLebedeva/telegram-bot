import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not API_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения")
CHANNEL_ID = "-1001324681912"
CHANNEL_LINK = "https://t.me/lebedevamariiatgm"
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"https://gigtest-bot.onrender.com{WEBHOOK_PATH}"

# Инициализация
logger.info("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot=bot)
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
        logger.error(f"Webhook ошибка: {e}")
        return web.json_response({"status": "error"}, status=500)

async def health(request):
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
        logger.error(f"Ошибка установки webhook: {e}")
        raise

# Запуск сервера
async def start_app():
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.getenv("PORT"))  # Используем только $PORT
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Бот @gigtestibot запущен на порту {port}")
        await on_startup(None)
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(start_app())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
