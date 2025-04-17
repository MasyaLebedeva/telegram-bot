import os
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils import executor
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]  # ID админов через запятую
if not API_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не задан в переменных окружения")
if not ADMIN_IDS:
    logger.warning("ADMIN_IDS не заданы в переменных окружения. Бот будет работать без админ-панели.")
CHANNEL_ID = "-1001324681912"
CHANNEL_LINK = "https://t.me/lebedevamariiatgm"
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"https://gigtest-bot-new.onrender.com{WEBHOOK_PATH}"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    
    # Таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  language_code TEXT,
                  joined_at TIMESTAMP,
                  last_activity TIMESTAMP,
                  is_subscribed INTEGER DEFAULT 0)''')
    
    # Таблица статистики
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT,
                  timestamp TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    
    conn.commit()
    conn.close()

# Инициализация
logger.info("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
Bot.set_current(bot)  # Устанавливаем текущий экземпляр бота
dp = Dispatcher(bot)
init_db()

# Middleware для логирования
class LoggingMiddleware(BaseMiddleware):
    async def on_process_message(self, message: Message, data: dict):
        logger.info(f"Получено сообщение от {message.from_user.id}: {message.text}")
        update_user_activity(message.from_user.id)
        return data

    async def on_process_callback_query(self, callback: CallbackQuery, data: dict):
        logger.info(f"Получен callback от {callback.from_user.id}: {callback.data}")
        update_user_activity(callback.from_user.id)
        return data

# Регистрируем middleware
dp.middleware.setup(LoggingMiddleware())

# Функции для работы с БД
def add_user(user_id, username, first_name, last_name, language_code):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, last_name, language_code, joined_at, last_activity)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, language_code, datetime.now(), datetime.now()))
    conn.commit()
    conn.close()

def update_user_activity(user_id):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('UPDATE users SET last_activity = ? WHERE user_id = ?',
              (datetime.now(), user_id))
    conn.commit()
    conn.close()

def log_action(user_id, action):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('INSERT INTO stats (user_id, action, timestamp) VALUES (?, ?, ?)',
              (user_id, action, datetime.now()))
    conn.commit()
    conn.close()

def get_user_stats():
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''SELECT COUNT(*) as total_users,
                        COUNT(CASE WHEN is_subscribed = 1 THEN 1 END) as subscribed_users,
                        COUNT(CASE WHEN last_activity > datetime('now', '-1 day') THEN 1 END) as active_today
                 FROM users''')
    stats = c.fetchone()
    conn.close()
    return {
        'total_users': stats[0],
        'subscribed_users': stats[1],
        'active_today': stats[2]
    }

# Регистрируем обработчики
@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    try:
        user_id = message.from_user.id
        logger.info(f"Обработка команды /start от {user_id}")
        
        add_user(user_id, message.from_user.username, message.from_user.first_name, 
                message.from_user.last_name, message.from_user.language_code)
        update_user_activity(user_id)
        log_action(user_id, "start")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="Проверить подписку ✅", callback_data="check_subscription")]
        ])
        
        await message.answer(
            "👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал",
            reply_markup=markup
        )
        logger.info(f"Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}")
        try:
            await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        except:
            pass

@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def process_subscription(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        logger.info(f"CHECK_SUB: Callback от {user_id}: {callback.data}")
        
        update_user_activity(user_id)
        log_action(user_id, "check_subscription")
        
        logger.info(f"CHECK_SUB: Проверка статуса для user_id={user_id} в канале {CHANNEL_ID}")
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        logger.info(f"CHECK_SUB: Статус: {member.status}")
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute('UPDATE users SET is_subscribed = ? WHERE user_id = ?',
                  (1 if member.status in ["member", "administrator", "creator"] else 0, user_id))
        conn.commit()
        conn.close()
        
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
        logger.info(f"CHECK_SUB: Обработка завершена для {user_id}")
    except Exception as e:
        logger.error(f"CHECK_SUB: Ошибка: {type(e).__name__}: {e}")
        try:
            await callback.answer("❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: Message):
    try:
        user_id = message.from_user.id
        logger.info(f"Обработка команды /admin от {user_id}")
        
        if user_id not in ADMIN_IDS:
            logger.warning(f"Попытка доступа к админ-панели от неавторизованного пользователя {user_id}")
            await message.answer("⛔️ У вас нет доступа к админ-панели")
            return
        
        logger.info(f"Пользователь {user_id} получил доступ к админ-панели")
        stats = get_user_stats()
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")]
        ])
        
        await message.answer(
            f"👋 Добро пожаловать в админ-панель!\n\n"
            f"📈 Общая статистика:\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"✅ Подписано: {stats['subscribed_users']}\n"
            f"🟢 Активных за сутки: {stats['active_today']}",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка в обработчике /admin: {e}")
        try:
            await message.answer("❌ Произошла ошибка при открытии админ-панели")
        except:
            pass

# Обработчик для админ-кнопок
@dp.callback_query_handler(lambda c: c.data.startswith("admin_"))
async def process_admin_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        logger.info(f"Обработка callback {callback.data} от {user_id}")
        
        if user_id not in ADMIN_IDS:
            logger.warning(f"Попытка доступа к админ-панели от неавторизованного пользователя {user_id}")
            await callback.answer("⛔️ У вас нет доступа")
            return
        
        action = callback.data.split("_")[1]
        logger.info(f"Обработка действия {action} для пользователя {user_id}")
        
        try:
            if action == "stats":
                stats = get_user_stats()
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
                ])
                await callback.message.edit_text(
                    f"📊 Статистика бота:\n\n"
                    f"👥 Всего пользователей: {stats['total_users']}\n"
                    f"✅ Подписано: {stats['subscribed_users']}\n"
                    f"🟢 Активных за сутки: {stats['active_today']}\n\n"
                    f"📈 Детальная статистика:\n"
                    f"📅 За последние 7 дней: {get_active_users(7)}\n"
                    f"📅 За последние 30 дней: {get_active_users(30)}",
                    reply_markup=markup
                )
            elif action == "broadcast":
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
                ])
                await callback.message.edit_text(
                    "📨 Отправьте сообщение для рассылки:\n\n"
                    "Поддерживаются следующие типы сообщений:\n"
                    "• Текст\n"
                    "• Фото с подписью\n"
                    "• Документ с подписью",
                    reply_markup=markup
                )
            elif action == "users":
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="admin_search_user")],
                    [InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_list_users")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
                ])
                await callback.message.edit_text(
                    "👥 Управление пользователями:\n\n"
                    "Выберите действие:",
                    reply_markup=markup
                )
            elif action == "settings":
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📢 Канал", callback_data="admin_channel_settings")],
                    [InlineKeyboardButton(text="📝 Приветственное сообщение", callback_data="admin_welcome_settings")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
                ])
                await callback.message.edit_text(
                    "⚙️ Настройки бота:\n\n"
                    "Выберите настройку:",
                    reply_markup=markup
                )
            elif action == "back":
                stats = get_user_stats()
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
                    [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
                    [InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users")],
                    [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")]
                ])
                await callback.message.edit_text(
                    f"👋 Добро пожаловать в админ-панель!\n\n"
                    f"📈 Общая статистика:\n"
                    f"👥 Всего пользователей: {stats['total_users']}\n"
                    f"✅ Подписано: {stats['subscribed_users']}\n"
                    f"🟢 Активных за сутки: {stats['active_today']}",
                    reply_markup=markup
                )
            
            await callback.answer()
            logger.info(f"Обработка действия {action} завершена успешно")
        except Exception as e:
            logger.error(f"Ошибка при обработке действия {action}: {type(e).__name__}: {e}")
            await callback.answer("❌ Произошла ошибка при обработке запроса")
    except Exception as e:
        logger.error(f"Ошибка при обработке callback {callback.data}: {type(e).__name__}: {e}")
        try:
            await callback.answer("❌ Произошла ошибка")
        except:
            pass

@dp.callback_query_handler(lambda c: c.data == "admin_broadcast")
async def process_broadcast_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        logger.info(f"Обработка callback admin_broadcast от {user_id}")
        
        if user_id not in ADMIN_IDS:
            logger.warning(f"Попытка доступа к рассылке от неавторизованного пользователя {user_id}")
            await callback.answer("⛔️ У вас нет доступа")
            return
        
        logger.info(f"Обработка действия broadcast для пользователя {user_id}")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        
        await callback.message.edit_text(
            "📨 Отправьте сообщение для рассылки:\n\n"
            "Поддерживаются следующие типы сообщений:\n"
            "• Текст\n"
            "• Фото с подписью\n"
            "• Документ с подписью",
            reply_markup=markup
        )
        
        await callback.answer()
        logger.info(f"Обработка callback admin_broadcast завершена успешно")
    except Exception as e:
        logger.error(f"Ошибка при обработке рассылки: {type(e).__name__}: {e}")
        try:
            await callback.answer("❌ Произошла ошибка при открытии раздела рассылки")
        except:
            pass

@dp.message_handler(lambda message: message.from_user.id in ADMIN_IDS and message.reply_to_message and message.reply_to_message.text.startswith("📨 Отправьте сообщение для рассылки:"))
async def process_broadcast_message(message: Message):
    try:
        user_id = message.from_user.id
        logger.info(f"Обработка сообщения для рассылки от {user_id}")
        
        conn = sqlite3.connect('bot.db')
        c = conn.cursor()
        c.execute('SELECT user_id FROM users')
        users = c.fetchall()
        conn.close()
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                await message.copy_to(user[0])
                success += 1
                logger.info(f"Сообщение успешно отправлено пользователю {user[0]}")
            except Exception as e:
                failed += 1
                logger.error(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")
        
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Результаты:\n"
            f"• Успешно отправлено: {success}\n"
            f"• Не удалось отправить: {failed}"
        )
        logger.info(f"Рассылка завершена. Успешно: {success}, Неудачно: {failed}")
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {type(e).__name__}: {e}")
        try:
            await message.answer("❌ Произошла ошибка при рассылке")
        except:
            pass

# Функция для получения количества активных пользователей
def get_active_users(days):
    conn = sqlite3.connect('bot.db')
    c = conn.cursor()
    c.execute('''SELECT COUNT(*) FROM users 
                 WHERE last_activity > datetime('now', ?)''', 
              (f'-{days} days',))
    count = c.fetchone()[0]
    conn.close()
    return count

# Обработчик для health check
async def on_startup(app):
    logger.info("Настройка вебхука...")
    try:
        # Удаляем старый вебхук
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Старый вебхук удален")
        
        # Устанавливаем новый вебхук
        await bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query"]
        )
        logger.info(f"Webhook установлен: {WEBHOOK_URL}")
        
        # Проверяем статус вебхука
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Информация о вебхуке: {webhook_info}")
        
        # Проверяем соединение с Telegram
        me = await bot.get_me()
        logger.info(f"Информация о боте: {me}")
        
        # Проверяем доступность бота
        try:
            bot_info = await bot.get_me()
            logger.info(f"Проверка доступности бота успешна: {bot_info}")
        except Exception as e:
            logger.error(f"Ошибка при проверке доступности бота: {e}")
    except Exception as e:
        logger.error(f"Ошибка при настройке вебхука: {e}")
        raise

async def on_shutdown(app):
    logger.info("Shutting down...")
    try:
        # Удаляем вебхук
        await bot.delete_webhook()
        logger.info("Webhook удален")
        
        # Закрываем хранилище
        await dp.storage.close()
        await dp.storage.wait_closed()
        logger.info("Хранилище закрыто")
        
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("Сессия бота закрыта")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

async def handle_root(request):
    return web.Response(text="Bot is running")

async def handle_webhook(request):
    try:
        data = await request.json()
        logger.info(f"Получен вебхук: {data}")
        
        update = types.Update(**data)
        logger.info(f"Создан объект Update: {update}")
        
        try:
            await dp.process_update(update)
            logger.info("Обновление успешно обработано")
            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"Ошибка при обработке обновления: {type(e).__name__}: {e}")
            return web.Response(text="Error", status=500)
    except Exception as e:
        logger.error(f"Ошибка при обработке вебхука: {type(e).__name__}: {e}")
        return web.Response(text="Error", status=500)

if __name__ == "__main__":
    # Создаем приложение
    app = web.Application()
    
    # Добавляем маршруты
    app.router.add_get('/', handle_root)
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    
    # Добавляем обработчики событий
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    
    # Запускаем приложение
    web.run_app(
        app,
        host='0.0.0.0',
        port=int(os.getenv("PORT", 10000))
    )
