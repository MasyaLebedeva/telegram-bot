import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor

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
WEBHOOK_URL = f"https://gigtest-bot-new.onrender.com{WEBHOOK_PATH}"

# Инициализация
logger.info("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

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

# Обработчик для health check
async def on_startup(dp):
    logger.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown(dp):
    logger.info("Бот остановлен")
    await bot.delete_webhook()
    await dp.storage.close()
    await dp.storage.wait_closed()
    await bot.session.close()

if __name__ == "__main__":
    executor.start_webhook(
        dispatcher=dp,
        webhook_path=WEBHOOK_PATH,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000))
    )
