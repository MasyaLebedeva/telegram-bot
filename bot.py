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

# URL для webhook
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://gigtest-bot-new.onrender.com")

# Проверка обязательных переменных
if not API_TOKEN:
    logger.error("ОШИБКА: TELEGRAM_TOKEN не установлен в переменных окружения!")
    raise ValueError("TELEGRAM_TOKEN должен быть установлен в переменных окружения")

# Инициализация бота
logger.info("Инициализация бота @gigtestibot...")
try:
    bot = Bot(token=API_TOKEN)
    dp = Dispatcher(bot)
    Bot.set_current(bot)
    logger.info("Бот успешно инициализирован")
except Exception as e:
    logger.error(f"ОШИБКА при инициализации бота: {e}")
    raise

# Функции для работы с БД (определяем ДО middleware)
def init_db():
    logger.info(f"Инициализация БД: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
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
        
        # Проверяем количество пользователей после инициализации
        c.execute('SELECT COUNT(*) FROM users')
        count = c.fetchone()[0]
        logger.info(f"БД инициализирована. Пользователей в БД: {count}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        raise

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
    try:
        logger.info(f"Получение статистики из БД: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''SELECT COUNT(*) as total_users,
                            COUNT(CASE WHEN is_subscribed = 1 THEN 1 END) as subscribed_users,
                            COUNT(CASE WHEN last_activity > datetime('now', '-1 day') THEN 1 END) as active_today
                     FROM users''')
        stats = c.fetchone()
        conn.close()
        logger.info(f"Статистика получена: total={stats[0]}, subscribed={stats[1]}, active={stats[2]}")
        return {
            'total_users': stats[0],
            'subscribed_users': stats[1],
            'active_today': stats[2]
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return {
            'total_users': 0,
            'subscribed_users': 0,
            'active_today': 0
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

# Middleware для логирования
class LoggingMiddleware(BaseMiddleware):
    async def on_process_message(self, message: Message, data: dict):
        logger.info(f"MIDDLEWARE: Получено сообщение от {message.from_user.id}: {message.text}")
        logger.info(f"MIDDLEWARE: Тип сообщения: {message.content_type}")
        if message.entities:
            commands = [message.text[e.offset:e.offset+e.length] for e in message.entities if e.type == 'bot_command']
            logger.info(f"MIDDLEWARE: Команды в сообщении: {commands}")
        try:
            update_user_activity(message.from_user.id)
        except Exception as e:
            logger.error(f"MIDDLEWARE: Ошибка обновления активности: {e}")
        return data

    async def on_process_callback_query(self, callback: CallbackQuery, data: dict):
        logger.info(f"MIDDLEWARE: Получен callback от {callback.from_user.id}: {callback.data}")
        try:
            update_user_activity(callback.from_user.id)
        except Exception as e:
            logger.error(f"MIDDLEWARE: Ошибка обновления активности: {e}")
        return data

# Регистрируем middleware
dp.middleware.setup(LoggingMiddleware())

# Регистрируем обработчики
def register_handlers(dp):
    """Регистрация всех обработчиков"""
    logger.info("Регистрация обработчиков...")
    
    # Все обработчики зарегистрированы через декораторы @dp.message_handler и @dp.callback_query_handler
    logger.info("Обработчики успешно зарегистрированы")

@dp.message_handler(commands=["start"])
async def cmd_start(message: Message):
    try:
        user_id = message.from_user.id
        logger.info(f"CMD_START: Обработка команды /start от {user_id}")
        logger.info(f"CMD_START: Текст сообщения: {message.text}")
        logger.info(f"CMD_START: Пользователь: {message.from_user.username} ({message.from_user.first_name})")
        
        add_user(user_id, message.from_user.username, message.from_user.first_name, 
                message.from_user.last_name, message.from_user.language_code)
        update_user_activity(user_id)
        log_action(user_id, "start")
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="Проверить подписку ✅", callback_data="check_subscription")]
        ])
        
        logger.info(f"CMD_START: Отправка сообщения пользователю {user_id}")
        logger.info(f"CMD_START: CHANNEL_LINK = {CHANNEL_LINK}")
        try:
            result = await bot.send_message(
                user_id,
                "👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал",
                reply_markup=markup
            )
            logger.info(f"CMD_START: Сообщение успешно отправлено пользователю {user_id}")
            logger.info(f"CMD_START: Результат отправки: message_id={result.message_id}")
        except Exception as send_error:
            logger.error(f"CMD_START: ОШИБКА при отправке сообщения: {send_error}")
            logger.error(f"CMD_START: Тип ошибки: {type(send_error).__name__}")
            logger.error(f"CMD_START: Трассировка: {traceback.format_exc()}")
            # Пробуем отправить простое сообщение без markup
            try:
                logger.info(f"CMD_START: Пробуем отправить простое сообщение без кнопок")
                await bot.send_message(user_id, "👋 Привет! Чтобы получить ответы на Гигтесты, пожалуйста, подпишись на канал")
                logger.info(f"CMD_START: Простое сообщение отправлено успешно")
            except Exception as simple_error:
                logger.error(f"CMD_START: Не удалось отправить даже простое сообщение: {simple_error}")
            raise
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
        logger.info(f"CHECK_SUB: callback.data = {callback.data}")
        logger.info(f"CHECK_SUB: CHANNEL_ID = {CHANNEL_ID}")
        
        # Отвечаем на callback сразу, чтобы пользователь видел реакцию
        await callback.answer("⏳ Проверяю подписку...")
        logger.info(f"CHECK_SUB: Ответ на callback отправлен")
        
        update_user_activity(user_id)
        log_action(user_id, "check_subscription")
        
        logger.info(f"CHECK_SUB: Проверка статуса подписки для user_id={user_id} в канале {CHANNEL_ID}")
        try:
            member = await bot.get_chat_member(CHANNEL_ID, user_id)
            logger.info(f"CHECK_SUB: Статус подписки получен: {member.status}")
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('UPDATE users SET is_subscribed = ? WHERE user_id = ?',
                      (1 if member.status in ["member", "administrator", "creator"] else 0, user_id))
            conn.commit()
            conn.close()
            
            if member.status in ["member", "administrator", "creator"]:
                logger.info(f"CHECK_SUB: Пользователь {user_id} подписан (статус: {member.status})")
                try:
                    result = await bot.send_message(
                        user_id,
                        "🎉 Спасибо за подписку. Держи файл с ответами на тесты: "
                        "https://docs.google.com/document/d/1wRpzasug5kSagNZgtG2QlSRMyK-7PP3ZYvNcejoDkoo/edit?usp=sharing"
                    )
                    logger.info(f"CHECK_SUB: Сообщение о подписке отправлено, message_id={result.message_id}")
                except Exception as send_error:
                    logger.error(f"CHECK_SUB: Ошибка при отправке сообщения о подписке: {send_error}")
            else:
                logger.info(f"CHECK_SUB: Пользователь {user_id} НЕ подписан (статус: {member.status})")
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Подписаться на канал 📢", url=CHANNEL_LINK)]
                ])
                try:
                    result = await bot.send_message(
                        user_id,
                        "😔 Упс. Кажется, ты не подписался на канал. Подпишись!",
                        reply_markup=markup
                    )
                    logger.info(f"CHECK_SUB: Сообщение о неподписке отправлено, message_id={result.message_id}")
                except Exception as send_error:
                    logger.error(f"CHECK_SUB: Ошибка при отправке сообщения о неподписке: {send_error}")
            
            logger.info(f"CHECK_SUB: Обработка завершена успешно для {user_id}")
        except Exception as e:
            logger.error(f"CHECK_SUB: Ошибка при проверке подписки: {str(e)}")
            logger.error(f"CHECK_SUB: Тип ошибки: {type(e).__name__}")
            logger.error(f"CHECK_SUB: Трассировка: {traceback.format_exc()}")
            try:
                await callback.answer("❌ Произошла ошибка при проверке подписки. Попробуйте позже.", show_alert=True)
            except Exception as answer_error:
                logger.error(f"CHECK_SUB: Не удалось отправить ответ об ошибке: {answer_error}")
    except Exception as e:
        logger.error(f"CHECK_SUB: КРИТИЧЕСКАЯ ОШИБКА: {str(e)}")
        logger.error(f"CHECK_SUB: Тип ошибки: {type(e).__name__}")
        logger.error(f"CHECK_SUB: Полная трассировка: {traceback.format_exc()}")
        try:
            await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
        except Exception as answer_error:
            logger.error(f"CHECK_SUB: Не удалось отправить ответ об ошибке: {answer_error}")
            # Пробуем отправить сообщение напрямую
            try:
                await bot.send_message(callback.from_user.id, "❌ Произошла ошибка при проверке подписки. Попробуйте позже.")
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

# Обработчик для админ-кнопок
@dp.callback_query_handler(lambda c: c.data.startswith("admin_") and c.data not in ["admin_list_users", "admin_broadcast"])
async def process_admin_callback(callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        logger.info(f"Обработка callback {callback.data} от {user_id}")
        
        if user_id not in ADMIN_IDS:
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
        except Exception as e:
            logger.error(f"Ошибка при обработке действия {action}: {type(e).__name__}: {e}")
            await callback.answer("❌ Произошла ошибка при обработке запроса")
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
        logger.info(f"LIST_USERS: Начало обработки от {user_id}, callback.data={callback.data}")
        
        if user_id not in ADMIN_IDS:
            logger.warning(f"LIST_USERS: Нет доступа для {user_id}")
            await callback.answer("⛔️ У вас нет доступа", show_alert=True)
            return
        
        # Отвечаем на callback сразу, чтобы пользователь видел реакцию
        await callback.answer("⏳ Загрузка...")
        
        logger.info(f"LIST_USERS: Подключение к БД {DB_PATH}")
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT user_id, username, first_name, last_name, is_subscribed, last_activity FROM users ORDER BY last_activity DESC LIMIT 10')
            users = c.fetchall()
            conn.close()
            logger.info(f"LIST_USERS: Найдено пользователей: {len(users)}")
        except Exception as db_error:
            logger.error(f"LIST_USERS: Ошибка БД: {db_error}")
            await callback.message.edit_text(
                f"❌ Ошибка при подключении к базе данных:\n{str(db_error)[:200]}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
                ])
            )
            return
        
        if not users:
            logger.info("LIST_USERS: Список пуст")
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
            await callback.message.edit_text(
                "👥 Список пользователей пуст",
                reply_markup=markup
            )
            return
        
        text = "👥 Список пользователей:\n\n"
        for idx, user in enumerate(users, 1):
            user_id_val, username, first_name, last_name, is_subscribed, last_activity = user
            # Форматируем имя безопасно
            name = f"{first_name or ''} {last_name or ''}".strip() or "Без имени"
            username_display = f"@{username}" if username else "нет"
            
            text += f"{idx}. {name} ({username_display})\n"
            text += f"   🆔 ID: {user_id_val}\n"
            text += f"   ✅ Подписка: {'Да' if is_subscribed else 'Нет'}\n"
            if last_activity:
                # Форматируем дату для читаемости
                try:
                    activity_time = datetime.fromisoformat(last_activity) if isinstance(last_activity, str) else last_activity
                    activity_str = activity_time.strftime("%d.%m.%Y %H:%M")
                except:
                    activity_str = str(last_activity)
                text += f"   🕒 Активность: {activity_str}\n"
            text += "\n"
        
        # Проверяем длину текста (лимит Telegram - 4096 символов)
        if len(text) > 4000:
            text = text[:4000] + "\n\n... (текст обрезан)"
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        
        logger.info(f"LIST_USERS: Отправка списка длиной {len(text)} символов")
        try:
            await callback.message.edit_text(text, reply_markup=markup)
            logger.info(f"LIST_USERS: Успешно отправлен для {user_id}")
        except Exception as edit_error:
            logger.error(f"LIST_USERS: Ошибка при редактировании сообщения: {edit_error}")
            logger.error(f"LIST_USERS: Детали ошибки редактирования: {type(edit_error).__name__}: {edit_error}")
            # Если не удалось отредактировать, отправляем новое сообщение
            try:
                await bot.send_message(
                    user_id, 
                    text, 
                    reply_markup=markup
                )
                logger.info(f"LIST_USERS: Список отправлен новым сообщением для {user_id}")
            except Exception as send_error:
                logger.error(f"LIST_USERS: Не удалось отправить новое сообщение: {send_error}")
                await callback.answer("❌ Ошибка при отправке списка", show_alert=True)
    except Exception as e:
        logger.error(f"LIST_USERS: КРИТИЧЕСКАЯ ОШИБКА - {type(e).__name__}: {e}")
        logger.error(f"LIST_USERS: Полная трассировка: {traceback.format_exc()}")
        try:
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)
        except Exception as answer_error:
            logger.error(f"LIST_USERS: Не удалось отправить ответ об ошибке: {answer_error}")
            # Попробуем отправить сообщение напрямую
            try:
                await bot.send_message(user_id, f"❌ Произошла ошибка при получении списка пользователей:\n{str(e)[:200]}")
            except:
                pass

# Обработчик webhook
async def handle_webhook(request):
    try:
        # Логируем входящий запрос
        logger.info(f"WEBHOOK: Получен HTTP запрос: {request.method} {request.path_qs}")
        logger.info(f"WEBHOOK: Headers: {dict(request.headers)}")
        
        # Проверяем, есть ли данные
        try:
            data = await request.json()
            logger.info(f"WEBHOOK: Получено обновление: {data.get('update_id', 'unknown')}")
        except Exception as json_error:
            logger.error(f"WEBHOOK: Ошибка при чтении JSON: {json_error}")
            # Пробуем прочитать как текст для диагностики
            try:
                text_data = await request.text()
                logger.error(f"WEBHOOK: Полученные данные (текст): {text_data[:500]}")
            except:
                pass
            return web.Response(text="Bad Request: Invalid JSON", status=400)
        
        # Логируем тип обновления
        if 'message' in data:
            logger.info(f"WEBHOOK: Сообщение от {data['message'].get('from', {}).get('id', 'unknown')}: {data['message'].get('text', '')}")
        elif 'callback_query' in data:
            logger.info(f"WEBHOOK: Callback от {data['callback_query'].get('from', {}).get('id', 'unknown')}: {data['callback_query'].get('data', '')}")
        
        try:
            update = types.Update(**data)
            logger.info(f"WEBHOOK: Создан объект Update, обработка...")
            await dp.process_update(update)
            logger.info(f"WEBHOOK: Обновление {data.get('update_id', 'unknown')} обработано успешно")
        except Exception as process_error:
            logger.error(f"WEBHOOK: Ошибка при process_update: {process_error}")
            logger.error(f"WEBHOOK: Тип ошибки process_update: {type(process_error).__name__}")
            logger.error(f"WEBHOOK: Трассировка process_update: {traceback.format_exc()}")
            # Продолжаем выполнение, чтобы вернуть ответ Telegram
            raise
        
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"WEBHOOK: Ошибка при обработке webhook: {str(e)}")
        logger.error(f"WEBHOOK: Тип ошибки: {type(e).__name__}")
        logger.error(f"WEBHOOK: Трассировка: {traceback.format_exc()}")
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
        
        # Возвращаем простой текст для максимальной совместимости с мониторами
        response_text = "OK"
        if request.path_qs.endswith('/health') or 'format=json' in str(request.query_string):
            # Если запрашивают /health или с параметром format=json, возвращаем JSON
            return web.json_response({
                "status": "ok", 
                "message": "Бот работает нормально",
                "timestamp": datetime.now().isoformat()
            }, status=200)
        
        # Простой текстовый ответ для большинства мониторов
        return web.Response(text=response_text, status=200, content_type='text/plain')
    except Exception as e:
        logger.error(f"Ошибка при проверке состояния: {str(e)}")
        return web.Response(text="ERROR", status=500)

# Инициализация приложения
def init_app():
    app = web.Application()
    
    # Webhook endpoint - Telegram отправляет обновления сюда
    webhook_path = f'/webhook/{API_TOKEN}'
    app.router.add_post(webhook_path, handle_webhook)
    logger.info(f"ROUTER: Зарегистрирован POST endpoint: {webhook_path}")
    
    # Health check endpoints
    app.router.add_get('/health', health_check_handler)
    app.router.add_get('/', health_check_handler)
    logger.info("ROUTER: Зарегистрированы GET endpoints: /health, /")
    
    return app

# Обработчики lifecycle
async def on_startup(app):
    """Настройка при запуске"""
    logger.info("STARTUP: Настройка webhook...")
    try:
        # Проверяем текущий webhook
        webhook_info_before = await bot.get_webhook_info()
        logger.info(f"STARTUP: Webhook до удаления: {webhook_info_before}")
        
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("STARTUP: Старый webhook удален")
        
        webhook_path = f"{WEBHOOK_URL}/webhook/{API_TOKEN}"
        logger.info(f"STARTUP: Устанавливаем webhook: {webhook_path}")
        
        result = await bot.set_webhook(
            url=webhook_path, 
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        logger.info(f"STARTUP: Результат установки webhook: {result}")
        logger.info(f"STARTUP: Webhook установлен: {webhook_path}")
        
        # Проверяем webhook после установки
        webhook_info = await bot.get_webhook_info()
        logger.info(f"STARTUP: Информация о webhook после установки: {webhook_info}")
        logger.info(f"STARTUP: URL webhook: {webhook_info.url}")
        logger.info(f"STARTUP: Pending updates: {webhook_info.pending_update_count}")
        
        me = await bot.get_me()
        logger.info(f"STARTUP: Информация о боте: {me}")
        
        # Проверяем, что обработчики зарегистрированы
        logger.info("STARTUP: Проверка обработчиков...")
        logger.info(f"STARTUP: Бот готов к работе. Ожидаем обновления на {webhook_path}")
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
    try:
        logger.info("=" * 50)
        logger.info("Запуск бота...")
        logger.info(f"TELEGRAM_TOKEN: {'Установлен' if API_TOKEN else 'НЕ УСТАНОВЛЕН!'}")
        logger.info(f"ADMIN_IDS: {ADMIN_IDS}")
        logger.info(f"WEBHOOK_URL: {WEBHOOK_URL}")
        logger.info(f"DB_PATH: {DB_PATH}")
        logger.info("=" * 50)
        
        # Инициализация базы данных
        init_db()
        logger.info("База данных инициализирована")
        
        # Обработчики уже зарегистрированы через декораторы @dp.message_handler и @dp.callback_query_handler
        logger.info("Обработчики проверены")
        
        # Создание приложения
        logger.info("Создание приложения...")
        app = init_app()
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)
        logger.info("Приложение создано")
        
        # Запуск приложения
        port = int(os.getenv("PORT", 10000))
        logger.info(f"Запуск сервера на порту {port}")
        logger.info("=" * 50)
        logger.info("Сервер запущен и готов принимать запросы")
        
        web.run_app(app, port=port, host='0.0.0.0')
    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА при запуске: {e}")
        logger.error(f"Тип ошибки: {type(e).__name__}")
        logger.error(f"Трассировка: {traceback.format_exc()}")
        logger.error("=" * 50)
        raise
