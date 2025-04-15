import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiohttp import web

# Конфигурация
API_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Токен из Render
CHANNEL_ID = "-1001324681912"
CHANNEL_LINK = "https://t.me/lebedevamariiatgm"

# Инициализация
print("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot=bot)
app = web.Application()  # WSGI приложение для gunicorn

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    print(f"START: Команда /start от {message.from_user.id}")
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Проверить подписку ✅", callback_data="check_subscription")]
    ])
    await message.answer("👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал", reply_markup=markup)

# Обработчик для check_subscription
@dp.callback_query(lambda c: c.data == "check_subscription")
async def process_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    print(f"CHECK_SUB: Callback от {user_id}: {callback.data}")
    try:
        print(f"CHECK_SUB: Проверка статуса для user_id={user_id} в канале {CHANNEL_ID}")
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        print(f"CHECK_SUB: Статус: {member.status}")
        if member.status in ["member", "administrator", "creator"]:
            await bot.send_message(user_id, "🎉 Спасибо за подписку. Держи файл с ответами на тесты: https://docs.google.com/document/d/1wRpzasug5kSagNZgtG2QlSRMyK-7PP3ZYvNcejoDkoo/edit?usp=sharing")
        else:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)]
            ])
            await bot.send_message(user_id, "😔 Упс. Кажется ты не подписался на канал. Подпишись!", reply_markup=markup)
        await callback.answer()
    except Exception as e:
        print(f"CHECK_SUB: Ошибка: {type(e).__name__}: {e}")
        await bot.send_message(user_id, "😓 Ошибка проверки подписки. Попробуй позже.")
        await callback.answer("Ошибка")

# Webhook и health check
async def webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.process_update(update)
        return web.json_response({"status": "ok"})
    except Exception as e:
        print(f"Webhook ошибка: {e}")
        return web.json_response({"status": "error"}, status=500)

async def health(request):
    return web.json_response({"status": "healthy"})

app.router.add_post(f"/webhook/{API_TOKEN}", webhook)
app.router.add_get("/health", health)

# Установка webhook при старте
async def on_startup(_):
    WEBHOOK_URL = f"https://gigtest-bot.onrender.com/webhook/{API_TOKEN}"
    await bot.delete_webhook()
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен для @gigtestibot")

# Запуск приложения
async def start_app():
    try:
        await on_startup(None)  # Устанавливаем webhook
        port = int(os.getenv("PORT", 10000))
        print(f"Запуск сервера на порту {port}...")
        return app  # Возвращаем приложение для gunicorn
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        raise

# Gunicorn будет вызывать эту функцию
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_app())