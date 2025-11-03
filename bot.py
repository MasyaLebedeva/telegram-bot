import os
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Update
from aiogram.dispatcher.middlewares import BaseMiddleware
import traceback
import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bot.db')
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
CHANNEL_ID = "-1001324681912"
CHANNEL_LINK = "https://t.me/lebedevamariiatgm"

# URL для webhook (замените на ваш URL)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://gigtest-bot-new.onrender.com")

# Инициализация бота
logger.info("Инициализация бота @gigtestibot...")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
Bot.set_current(bot)

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
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  language_code TEXT,
                  joined_at TIMESTAMP,
                  last_activity TIMESTAMP,
                  is_subscribed INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  action TEXT,
                  timestamp TIMESTAMP,
                  FOREIGN KEY(user_id) REFERENCES users(user_id))''')
    conn.commit()
    conn.close()

def add_user(user_id, username, first_name, last_name, language_code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users 
                 (user_id, username, first_name, last_name, language_code, joined_at, last_activity)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (user_id, username, first_name, last_name, language_code, datetime.now(), datetime.now()))
    conn.commit()
    conn.close()

def update_user_activity(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET last_activity = ? WHERE user_id = ?',
              (datetime.now(), user_id))
    conn.commit()
    conn.close()

def log_action(user_id, action):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO stats (user_id, action, timestamp) VALUES (?, ?, ?)',
              (user_id, action, datetime.now()))
    conn.commit()
    conn.close()

def get_user_stats():
    conn = sqlite3.connect(DB_PATH)
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

def get_active_users(days):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT COUNT(*) FROM users 
                 WHERE last_activity > datetime('now', ?)''', 
              (f'-{days} days',))
    count = c.fetchone()[0]
    conn.close()
    return count

# Регистрируем обработчики
def register_handlers(dp):
    logger.info("Регистрация обработчиков...")
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_message_handler(cmd_admin, commands=["admin"])
    dp.register_callback_query_handler(process_subscription, lambda c: c.data == "check_subscription")
    dp.register_callback_query_handler(process_admin_callback, lambda c: c.data.startswith("admin_"))
    dp.register_callback_query_handler(process_broadcast_callback, lambda c: c.data == "admin_broadcast")
    dp.register_callback_query_handler(process_list_users, lambda c: c.data == "admin_list_users")
    dp.register_message_handler(
        process_broadcast_message,
        lambda message: message.from_user.id in ADMIN_IDS and 
        message.reply_to_message and 
        message.reply_to_message.text.startswith("📨 Отправьте сообщение для рассылки:")
    )
    logger.info("Обработчики успешно зарегистрированы")

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
        
        await bot.send_message(
            user_id,
            "👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал",
            reply_markup=markup
        )
        logger.info(f"Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {str(e)}")
        logger.error(f"Полный стек ошибки: {traceback.format_exc()}")
        try:
            await bot.send_message(user_id, "❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        except:
            pass

@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def process_subscription(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        logger.info(f"CHECK_SUB: Начало обработки callback от {user_id}")
        
        update_user_activity(user_id)
        log_action(user_id, "check_subscription")
        
        try:
            member = await bot.get_chat_member(CHANNEL_ID, user_id)
            logger.info(f"CHECK_SUB: Статус: {member.status}")
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE users SET is_subscribed = ? WHERE user_id = ?',
                      (1 if member.status in ["member", "administrator", "creator"] else 0, user_id))
            conn.commit()
            conn.close()
            
            if member.status in ["member", "administrator", "creator"]:
                logger.info(f"CHECK_SUB: Пользователь {user_id} подписан")
                await bot.send_message(
                    user_id,
                    "🎉 Спасибо за подписку. Держи файл с ответами на тесты: "
                    "https://docs.google.com/document/d/1wRpzasug5kSagNZgtG2QlSRMyK-7PP3ZYvNcejoDkoo/edit?usp=sharing"
                )
            else:
                logger.info(f"CHECK_SUB: Пользователь {user_id} не подписан")
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
            logger.error(f"CHECK_SUB: Ошибка при проверке подписки: {str(e)}")
            await callback.answer("❌ Произошла ошибка при проверке подписки. Попробуйте позже.")
    except Exception as e:
        logger.error(f"CHECK_SUB: Критическая ошибка: {str(e)}")
        try:
            await callback.answer("❌ Произошла ошибка. Попробуйте позже.")
        except:
            pass

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: Message):
    try:
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            await message.answer("⛔️ У вас нет доступа к админ-панели")
            return
        
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

@dp.message_handler(commands=["stats_raw"])
async def cmd_stats_raw(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("⛔️ У вас нет доступа")
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = 1")
        subs = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM users WHERE last_activity > datetime('now','-1 day')")
        active = c.fetchone()[0]
        c.execute("SELECT user_id, username, first_name, last_name, last_activity FROM users ORDER BY last_activity DESC LIMIT 10")
        rows = c.fetchall()
        conn.close()

        rows_text = "\n".join([f"ID {r[0]} @{r[1] or '—'} {r[2] or ''} {r[3] or ''} | {r[4]}" for r in rows]) or "—"
        await message.answer(
            f"DB: {DB_PATH}\n"
            f"Всего: {total}\nПодписано: {subs}\nАктивны 24ч: {active}\n\nПоследние 10:\n{rows_text}"
        )
    except Exception as e:
        logger.error(f"stats_raw error: {e}")
        await message.answer("❌ Ошибка stats_raw")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_"))
async def process_admin_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ADMIN_IDS:
            await callback.answer("⛔️ У вас нет доступа")
            return
        
        action = callback.data.split("_")[1]
        
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
    except Exception as e:
        logger.error(f"Ошибка при обработке callback: {e}")
        try:
            await callback.answer("❌ Произошла ошибка")
        except:
            pass

@dp.callback_query_handler(lambda c: c.data == "admin_broadcast")
async def process_broadcast_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ADMIN_IDS:
            await callback.answer("⛔️ У вас нет доступа")
            return
        
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
    except Exception as e:
        logger.error(f"Ошибка при обработке рассылки: {e}")
        try:
            await callback.answer("❌ Произошла ошибка")
        except:
            pass

@dp.message_handler(lambda message: message.from_user.id in ADMIN_IDS and message.reply_to_message and message.reply_to_message.text.startswith("📨 Отправьте сообщение для рассылки:"))
async def process_broadcast_message(message: Message):
    try:
        conn = sqlite3.connect(DB_PATH)
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
            except Exception as e:
                failed += 1
                logger.error(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")
        
        await message.answer(
            f"✅ Рассылка завершена!\n\n"
            f"📊 Результаты:\n"
            f"• Успешно отправлено: {success}\n"
            f"• Не удалось отправить: {failed}"
        )
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        try:
            await message.answer("❌ Произошла ошибка при рассылке")
        except:
            pass

@dp.callback_query_handler(lambda c: c.data == "admin_list_users")
async def process_list_users(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id not in ADMIN_IDS:
            await callback.answer("⛔️ У вас нет доступа")
            return
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT user_id, username, first_name, last_name, is_subscribed, last_activity FROM users ORDER BY last_activity DESC LIMIT 10')
        users = c.fetchall()
        conn.close()
        
        if not users:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
            await callback.message.edit_text("👥 Список пользователей пуст", reply_markup=markup)
            return
        
        text = "👥 Список пользователей:\n\n"
        for user in users:
            user_id, username, first_name, last_name, is_subscribed, last_activity = user
            text += f"👤 {first_name} {last_name or ''} (@{username or 'нет'})\n"
            text += f"🆔 ID: {user_id}\n"
            text += f"✅ Подписка: {'Да' if is_subscribed else 'Нет'}\n"
            text += f"🕒 Последняя активность: {last_activity}\n\n"
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при обработке списка пользователей: {e}")
        try:
            await callback.answer("❌ Произошла ошибка")
        except:
            pass

# Обработчик webhook
async def handle_webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return web.Response(text="Error", status=500)

# Health check endpoint для мониторинга
async def health_check_handler(request):
    """Эндпоинт для проверки состояния бота через aiohttp"""
    try:
        # Проверяем подключение к базе данных
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                cursor.fetchone()
        except Exception as db_error:
            logger.warning(f"Проблема с БД при health check: {db_error}")
        
        # Всегда возвращаем OK, если сервер отвечает
        return web.json_response({
            "status": "ok", 
            "message": "Бот работает нормально",
            "timestamp": datetime.now().isoformat()
        }, status=200)
    except Exception as e:
        logger.error(f"Ошибка при проверке состояния: {str(e)}")
        return web.json_response({
            "status": "error", 
            "message": str(e)
        }, status=500)

# Инициализация приложения
async def init_app():
    app = web.Application()
    app.router.add_post(f'/webhook/{API_TOKEN}', handle_webhook)
    app.router.add_get('/health', health_check_handler)
    app.router.add_get('/', health_check_handler)
    return app

# Обработчики lifecycle
async def on_startup(app):
    logger.info("Настройка webhook...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        webhook_path = f"{WEBHOOK_URL}/webhook/{API_TOKEN}"
        await bot.set_webhook(url=webhook_path, allowed_updates=["message", "callback_query"])
        logger.info(f"Webhook установлен: {webhook_path}")
        
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Информация о webhook: {webhook_info}")
        
        me = await bot.get_me()
        logger.info(f"Информация о боте: {me}")
        
        register_handlers(dp)
        logger.info("Обработчики зарегистрированы")
    except Exception as e:
        logger.error(f"Ошибка при настройке webhook: {e}")
        raise

async def on_shutdown(app):
    logger.info("Shutting down...")
    try:
        await bot.delete_webhook()
        await dp.storage.close()
        await dp.storage.wait_closed()
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

if __name__ == "__main__":
    init_db()
    register_handlers(dp)
    
    async def setup_app():
        app = await init_app()
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)
        return app
    
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Запуск сервера на порту {port}")
    app = asyncio.run(setup_app())
    web.run_app(app, port=port, host='0.0.0.0')
