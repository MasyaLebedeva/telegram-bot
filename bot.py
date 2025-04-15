from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import asyncio

# Конфигурация
API_TOKEN = '7814963909:AAGoxBu9pkVmyAwyw41x7Nyy0n9ww9QTvoU'
CHANNEL_ID = '-1001324681912'  # Проверено, работает
CHANNEL_LINK = 'https://t.me/lebedevamariiatgm'  # Ссылка на твой канал

# Инициализация
print("Инициализация бота...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

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

# Запуск бота
if __name__ == "__main__":
    print("Запуск бота...")
    asyncio.run(dp.start_polling(bot))