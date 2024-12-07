import asyncio
import sqlite3
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from telebot.async_telebot import AsyncTeleBot
from telebot.util import smart_split 
from moviepy import VideoFileClip
from dotenv import load_dotenv
from openai import AsyncOpenAI
import logging
import requests
import io
from moviepy.video.io.VideoFileClip import VideoFileClip
import traceback
from pathlib import Path
import base64

logging.basicConfig(
    filename="bot_logs_v2.0.log",        
    level=logging.INFO,            
    format="%(asctime)s [%(levelname)s] %(message)s",  
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"      
)


# Хранение состояний пользователей
user_data = {}

# Хранение нажатий для каждого чата и типа действия
clicked_users = {
    "analyze_messages": {},
    "summarize_messages": {},
    "load_messages": {},
    "analyze_messages_for_me": {}
}


# Загружаем переменные из .env файла
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_PATH = "chat_data_v2.db"
log_file = 'bot_logs_v2.0.log'  
ADMIN_CHAT_ID = list(map(int, os.getenv("ADMIN_CHAT_ID").split(',')))
CHAT_LOGOV_ID = os.getenv("CHAT_LOGOV_ID")
PAROL = os.getenv("PAROL")
COMPANY_NAME = os.getenv("COMPANY_NAME")
INN = os.getenv("INN")
OGRN = os.getenv("OGRN")
LOCATION = os.getenv("LOCATION")
EMAIL = os.getenv("EMAIL")
PHONE = os.getenv("PHONE")
POLICY_LINK = os.getenv("POLICY_LINK")
OFFER_LINK = os.getenv("OFFER_LINK")
AI_POLICY_LINK = os.getenv("AI_POLICY_LINK")
AGREE_PD_LINK = os.getenv("AGREE_PD_LINK")
CONF_PD_LINK = os.getenv("CONF_PD_LINK")


# Создаем клиент OpenAI
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Создаем TeleBot
bot = AsyncTeleBot(TELEGRAM_BOT_TOKEN)

# Подключение к SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()



cursor.execute("PRAGMA table_info(message_limits)")
columns = [column[1] for column in cursor.fetchall()]

if 'midia_limit' not in columns:
    cursor.execute('''
        ALTER TABLE message_limits 
        ADD COLUMN midia_limit INTEGER DEFAULT 10
    ''')
    conn.commit()




# Создание таблиц
cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER UNIQUE,
        chat_id INTEGER,
        user_id INTEGER,
        thread_id INTEGER DEFAULT NONE,
        username TEXT,
        content TEXT,
        date TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        chat_id INTEGER PRIMARY KEY,
        record BOOLEAN DEFAULT TRUE,
        [limit] INTEGER DEFAULT 100,
        style TEXT DEFAULT 'Деловой',
        reminder_enabled BOOLEAN DEFAULT TRUE,
        agreement BOOLEAN DEFAULT FALSE        
    )
""")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS message_counter (
        chat_id INTEGER NOT NULL,
        thread_id INTEGER DEFAULT 0,
        count INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, thread_id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS message_limits (
        user_id INTEGER PRIMARY KEY,
        remaining_requests INTEGER DEFAULT 5,
        midia_limit INTEGER DEFAULT 10
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS vip (
        unlimited_users TEXT DEFAULT ""
    )
''')

conn.commit()

# Функция для добавления пользователя в список vip людей (у тех у кого нету ограничений на запросы)
async def add_to_vip(username):
    cursor.execute("INSERT OR IGNORE INTO vip (unlimited_users) VALUES (?)", (username,))
    conn.commit()    


# Обрабатывает /start
@bot.message_handler(commands=['start'])
async def handle_settings(message):
    try:
        if message.chat.type != 'private':
            chat_id = message.chat.id
            chat_title = message.chat.title or "Без названия"
            logging.info(f"Пользователь нажал /start в группе {chat_title} (ID: {chat_id})")
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("🔥 Узнать про Премиум", callback_data="premium_main"))
            
            text = "👋 Привет! Это бот В команде!\n\n🛠 Основные функции:\n/start - Запуск бота\n/premium - Купить подписку\n/agree - Пользовательское соглашение\n/settings - Настройки бота\n/analyze - Оценка эффективности работы команды с детальным анализом коммуникаций и советами по улучшению\n/summarize - Краткое саммари (выжимка) из переписки чата.\n/analyze_for_me - Персональный анализ сообщений для отдельного пользователя.\n/tz - Формирование структурированного технического задания (ТЗ)\n\n🆓 Пока что у всех пользователей есть 5 бесплатных запросов к боту на анализ и саммари"

            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=keyboard, message_thread_id=message.message_thread_id)
        else:
            chat_id = message.chat.id
            logging.info(f"Пользователь нажал /start в лс (ID: {chat_id})")
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("🔥 Узнать про Премиум", callback_data="premium_main"))
            
            text = "👋 Привет! Это бот В команде!\n\n✨ Чтобы  смог вам помочь вам нужно добавить меня в ваш групповой чат, и я начну прокачивать вашу эффективность уже сегодня!\n\nКак начать работу:\nДобавьте меня в ваш групповой чат, где работает ваша команда.\nПредоставьте мне доступ к сообщениям (это нужно для выполнения функций, таких как анализ и создание саммари).\nИспользуйте мои команды и функции прямо в группе!\n🔧 Чтобы добавить меня в чат:\n\nОткройте настройки вашего группового чата.\nВыберите 'Добавить участника' и найдите меня: @.\nНе забудьте настроить доступ к сообщениям для оптимальной работы!\n💬 После добавления, я помогу с анализом, саммаризацией встреч и многими другими задачами. Просто вызовите команду /help в чате, чтобы узнать больше.\n\nГотовы к эффективной работе? Начнем! 🚀"

            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=keyboard, message_thread_id=message.message_thread_id)
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")


# Блок сообщений в лс (с админкой)
@bot.message_handler(func=lambda message: message.chat.type == 'private')
async def handle_private_messages(message):
    try:
        chat_id = message.chat.id

        is_vip = await is_vip_user(message.from_user.username)
        if is_vip:
            text = message.text
            if text.startswith(str(PAROL)):
                username = text.split(":", 1)[1].strip()
                await add_to_vip(username)
                await bot.send_message(chat_id, "<b>Админка</b>\n\nПользователь успешно добавлен", parse_mode='HTML', message_thread_id=message.message_thread_id)
            else:
                await bot.send_message(chat_id, "<b>К сожалению, бот в ЛС не работает.\nЭтот бот предназначен для групповых чатов, чтобы начать с ним работу, добавьте бота в группу</b>", parse_mode='HTML', message_thread_id=message.message_thread_id)
            return  
        else:
            await bot.send_message(chat_id, "<b>К сожалению, бот в ЛС не работает.\nЭтот бот предназначен для групповых чатов, чтобы начать с ним работу, добавьте бота в группу</b>", parse_mode='HTML', message_thread_id=message.message_thread_id)
            return
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")





# Проверяет, является ли пользователь VIP
async def is_vip_user(username):
    try:
        cursor.execute('''CREATE TABLE IF NOT EXISTS vip (
            unlimited_users TEXT DEFAULT ""
        )''')
        conn.commit()

        cursor.execute("SELECT unlimited_users FROM vip")
        result = cursor.fetchall() 

        if result:
            vip_users = []
            for row in result:
                vip_users.extend(row[0].split(","))  

            return username in vip_users
        
        return False
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")


    


# Функция для увеличения счётчика сообщений и проверки кратен ли он 100 
    
# Она нужно для того, чтобы напоминить пользователю о 100 сообщениях (типо мол не хотите ли вы проанализировать их?)
async def increment_message_count(chat_id, thread_id):
    try:
        thread_id = thread_id if thread_id is not None else 0

        cursor.execute("SELECT COUNT(*) FROM settings WHERE chat_id = ?", (chat_id,))
        exists = cursor.fetchone()[0]

        if not exists:
            cursor.execute('''
                INSERT INTO settings (chat_id, record, [limit], style, reminder_enabled)
                VALUES (?, TRUE, 100, 'Деловой', TRUE)
            ''', (chat_id,))
            conn.commit()

        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_thread ON message_counter (chat_id, thread_id)
        ''')

        cursor.execute('''
            INSERT INTO message_counter (chat_id, thread_id, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET count = message_counter.count + 1
        ''', (chat_id, thread_id))
        conn.commit()

        cursor.execute('''
            SELECT count FROM message_counter WHERE chat_id = ? AND thread_id = ?
        ''', (chat_id, thread_id))
        count = cursor.fetchone()[0]

        cursor.execute('SELECT reminder_enabled FROM settings WHERE chat_id = ?', (chat_id,))
        reminder_enabled = cursor.fetchone()[0]

        if count % 100 == 0 and reminder_enabled:
            await bot.send_message(
                chat_id,
                f"<b>Вы отправили {count} сообщений {'в этой теме' if thread_id != 0 else 'в этом чате'}.\nНе хотите проанализировать их?</b>",
                parse_mode='HTML',
                message_thread_id=thread_id if thread_id != 0 else None
            )
    except Exception:
        logging.exception("Произошла ошибка")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")


# Обработчик нажатий на кнопки "Функции", "Настройки", "Подписка"
@bot.message_handler(func=lambda message: message.text in ["Функции", "Настройки", "Подписка", "Анализ", "Саммари", "Личный анализ", "Вернуться назад"])
async def handle_main_buttons(message):
    if message.text == "Функции":
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
        markup.add(
            KeyboardButton("Анализ"),
            KeyboardButton("Саммари"),
            KeyboardButton("Личный анализ"),
            KeyboardButton("Вернуться назад")
        )
        
        await bot.send_message(
            message.chat.id,
            "Выберите одну из функций:",
            reply_markup=markup,
            message_thread_id=message.message_thread_id
        )

    elif message.text == "Настройки":
        await handle_settings(message)
    elif message.text == "Подписка":
        await handle_premium(message)
    elif message.text in ["Анализ", "Саммари", "Личный анализ"]:
        await handle_command(message)
    elif message.text == "Вернуться назад":
        markup_no_inline = ReplyKeyboardMarkup(resize_keyboard=True)
        markup_no_inline.add(
                    KeyboardButton("Функции"),
                    KeyboardButton("Настройки"),
                    KeyboardButton("Подписка")
            )
        await bot.send_message(
            message.chat.id,
                    "👋 Привет! Это бот В команде!\n\n🛠 Основные функции:\n/start - Запуск бота\n/premium - Купить подписку\n/agree - Пользовательское соглашение\n/settings - Настройки бота\n/analyze - Оценка эффективности работы команды с детальным анализом коммуникаций и советами по улучшению\n/summarize - Краткое саммари (выжимка) из переписки чата.\n/analyze_for_me - Персональный анализ сообщений для отдельного пользователя.\n/tz - Формирование структурированного технического задания (ТЗ)\n\n🆓 Пока что у всех пользователей есть 5 бесплатных запросов к боту на анализ и саммари",
                        parse_mode='HTML',
                        reply_markup=markup_no_inline, message_thread_id=message.message_thread_id)


# Обработчик новых участников чата
@bot.message_handler(content_types=['new_chat_members'])
async def handle_new_chat_members(message):
    try:
        chat_id = message.chat.id
        
        bot_info = await bot.get_me()
        bot_id = bot_info.id  
        
        for new_member in message.new_chat_members:
            if new_member.id == bot_id:
                markup = InlineKeyboardMarkup(row_width=1)
                markup.add(
                        InlineKeyboardButton("Пользовательское соглашение", url=POLICY_LINK), 
                        InlineKeyboardButton("Политика конфиденциальности и обработки персональных данных", url=CONF_PD_LINK),
                        InlineKeyboardButton("Согласие на обработку ваших персональных данных", url=AGREE_PD_LINK)
                )
                markup_no_inline = ReplyKeyboardMarkup(resize_keyboard=True)
                markup_no_inline.add(
                    KeyboardButton("Функции"),
                    KeyboardButton("Настройки"),
                    KeyboardButton("Подписка")
                )
                await bot.send_message(
                        message.chat.id,
                        "👋 Привет! Это бот В команде!\n\n🛠 Основные функции:\n/start - Запуск бота\n/premium - Купить подписку\n/agree - Пользовательское соглашение\n/settings - Настройки бота\n/analyze - Оценка эффективности работы команды с детальным анализом коммуникаций и советами по улучшению\n/summarize - Краткое саммари (выжимка) из переписки чата.\n/analyze_for_me - Персональный анализ сообщений для отдельного пользователя.\n/tz - Формирование структурированного технического задания (ТЗ)\n\n🆓 Пока что у всех пользователей есть 5 бесплатных запросов к боту на анализ и саммари",
                        parse_mode='HTML',
                        reply_markup=markup_no_inline,
                        message_thread_id=message.message_thread_id
                    )
                await bot.send_message(
                    message.chat.id,
                    "Продолжая использовать наш сервис, вы подтверждаете:\n\n"
                    "1. 📜 Ознакомление и полное согласие с условиями <b>Пользовательского соглашения</b>\n\n"
                    "2. 🔒 Принятие <b>Политики конфиденциальности и обработки персональных данных</b>\n\n"
                    "3. ✅ Дачу согласия на <b>обработку ваших персональных данных</b>\n\n"
                ,
                parse_mode='HTML',
                reply_markup=markup,
                message_thread_id=message.message_thread_id
                )
                chat_title = message.chat.title or "Без названия"
                logging.info(f"Бот добавлен в новый чат: {chat_title} (ID: {chat_id})")
                break  
            else:
                await bot.send_message(
                    chat_id,
                    f"<b>Привет, {new_member.first_name}!</b>",
                    parse_mode='HTML',
                    message_thread_id=message.message_thread_id

                )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")  





# Получает стиль ответа, который выбрал пользователь в настройках
async def get_style_for_chat(chat_id):
    try:
        cursor.execute("SELECT style FROM settings WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

        if result:
            return result[0]
        return 'Деликатный'
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")





# Функция для подсчёта слов в тексте (приближённо как токены)
def count_words(text):
    return len(text.split())



# Функция для отправки запроса в OpenAI
async def send_to_openai(prompt, messages, user_id):
    try:
        total_words = sum(count_words(msg) for msg in messages)

        while total_words > 30000 and len(messages) > 0:
            messages.pop(0)
            total_words = sum(count_words(msg) for msg in messages)
            
        if total_words > 30000:
            return "Ошибка: даже после удаления сообщений, размер данных слишком велик."
        
        completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": "\n".join(messages)
                }
            ]
        )

        if completion:
            # Уменьшаем количество оставшихся запросов
            await decrease_message_limit(user_id)
            return str(completion.choices[0].message.content).replace('#', '').replace('*', '')
        else:
            return "Ошибка в отправке сообщения в OpenAI"
    except Exception as e:
        logging.exception("Произошла ошибка при отправке запроса в OpenAI")  
        
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Произошла ошибка при обработке запроса."






# Получает количество сообщений, которое мы должны загрузить из бд
async def get_limit_for_chat(chat_id):
    try:
        cursor.execute("SELECT [limit] FROM settings WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

        if result:
            return result[0]
        else:
            return 100  

    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return 100
    






# Получает значение record из бд (таблица settings)

# record - согласился ли админ чата с пользовательским соглашением (в том числе на загрузку сообщений)
async def get_record(chat_id):
    try:
        cursor.execute("SELECT record FROM settings WHERE chat_id = ?", (chat_id,))
        result = cursor.fetchone()

        if result:
            return bool(result[0])
        else:
            cursor.execute("""
                INSERT INTO settings (chat_id)
                VALUES (?)
            """, (chat_id,))
            conn.commit()
            return True 

    except Exception as e:
        logging.exception("Произошла ошибка")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)

        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return False



# Проверяем может ли пользователь отправлять запросы (закончился ли у него лимит и vip ли он или нет)
async def can_user_execute_command(user_id, username):
    try:
        cursor.execute("SELECT remaining_requests FROM message_limits WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result:
            remaining_requests = result[0]

            cursor.execute("SELECT unlimited_users FROM vip WHERE unlimited_users = ?", (username,))
            vip_user = cursor.fetchone()
            if vip_user:
                return True  

            if remaining_requests > 0:
                return True  

        else:
            cursor.execute("INSERT INTO message_limits (user_id, remaining_requests, midia_limit) VALUES (?, ?, ?)", (user_id, 5, 10))
            conn.commit()
            return True

        return False  
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")



# Уменьшает значение лимита медиа сообщений на 1
async def decrement_midia_limit(user_id):

    cursor.execute(
        "SELECT remaining_requests, midia_limit FROM message_limits WHERE user_id = ?", 
        (user_id,)
    )
    result = cursor.fetchone()

    if result is None:
        cursor.execute(
            """
            INSERT INTO message_limits (user_id, remaining_requests, midia_limit)
            VALUES (?, ?, ?)
            """,
            (user_id, 5, 10)
        )
        conn.commit()

    remaining_requests, midia_limit = result

    if remaining_requests > 0 and midia_limit > 0:
        new_remaining_requests = remaining_requests - 1
        new_midia_limit = midia_limit - 1

        cursor.execute(
            """
            UPDATE message_limits 
            SET remaining_requests = ?, midia_limit = ?
            WHERE user_id = ?
            """,
            (new_remaining_requests, new_midia_limit, user_id)
        )
        conn.commit()







# Уменьшает значение на 1 в таблице remaining_requests (уменьшает лимит запросов на 1)
async def decrease_message_limit(user_id):
    try:
        cursor.execute("SELECT remaining_requests, midia_limit FROM message_limits WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result:
            remaining_requests = result[0]
            midia_limit = result[1]
            if remaining_requests > 0:
                new_remaining_requests = remaining_requests - 1
                cursor.execute(
                    "UPDATE message_limits SET remaining_requests = ? WHERE user_id = ?", 
                    (new_remaining_requests, user_id)
                )
                conn.commit()
        else:
            cursor.execute(
                "INSERT INTO message_limits (user_id, remaining_requests, midia_limit) VALUES (?, ?, ?)",
                (user_id, 4) 
            )
            conn.commit()
    except Exception as e:
        logging.exception("Произошла ошибка при уменьшении лимита запросов.")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")








# Обрабатывает команду вывода и изменения настроек
@bot.message_handler(commands=['settings'])
async def handle_settings(message):
    try:
        chat_title = message.chat.title or "Без названия"
        chat_id = message.chat.id
        logging.info(f"Пользователь нажал /settings в группе {chat_title} (ID: {chat_id})")
        chat_id = message.chat.id


        cursor.execute("SELECT record, [limit], style, reminder_enabled FROM settings WHERE chat_id = ? LIMIT 1", (chat_id,))
        result = cursor.fetchone()

        if not result:
            cursor.execute("""
                INSERT INTO settings (chat_id, record, [limit], style, reminder_enabled)
                VALUES (?, ?, ?, ?, ?)
            """, (chat_id, True, 100, "Деловой", True))
            conn.commit()
            record, style_value, limit_value, reminder_enabled_value = True, "Деловой", 100, True
        else:
            record, limit_value, style_value, reminder_enabled_value = result

    
        # Создаём кнопки для настроек
        keyboard = InlineKeyboardMarkup(row_width=5)


        
        record_button = InlineKeyboardButton(f"record: {'Включено' if bool(record) else 'Выключено'}", callback_data="toggle_record")





        style_button = InlineKeyboardButton(f"style: {style_value}", callback_data="toggle_style")
        reminder_button = InlineKeyboardButton(f"reminder: {'Включено' if bool(reminder_enabled_value) else 'Выключено'}", callback_data="toggle_reminder")
        limit_button = InlineKeyboardButton(f"limit: {limit_value if limit_value else 100}", callback_data="limit")
        decrement_button = InlineKeyboardButton("-10", callback_data="decrement_limit_settings")
        increment_button = InlineKeyboardButton("+10", callback_data="increment_limit_settings")
        decrement_large_button = InlineKeyboardButton("-100", callback_data="decrement_limit_large_settings")
        increment_large_button = InlineKeyboardButton("+100", callback_data="increment_limit_large_settings")

        keyboard.add(decrement_large_button, decrement_button, limit_button, increment_button, increment_large_button)
        keyboard.add(record_button)
        keyboard.add(style_button)
        keyboard.add(reminder_button)

        await bot.send_message(
                chat_id,
                "Настройки:\n\n"
                "<b>limit</b> - Сколько последних сообщений бот должен анализировать\n"
                "<b>record</b> - Нужно ли записывать сообщения.\n"
                "<b>style</b> - Стиль ответа.\n"
                "<b>reminder</b> - Включить напоминания о достижении 100 сообщений (для того, чтобы вы их проанализировали).\n",
                parse_mode='HTML',
                reply_markup=keyboard,
                message_thread_id=message.message_thread_id)
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
    













# Обработка /agree (для соглашения)
@bot.message_handler(commands=['agree'])
async def handle_agree(message):
    try:
        chat_id = message.chat.id

        with open("Пользовательское соглашение.pdf", "rb") as doc:
            await bot.send_document(
                chat_id,
                doc,
                message_thread_id=message.message_thread_id
            )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")





# Обрабатывает /premium
@bot.message_handler(commands=['premium'])
async def handle_premium(message, edit_message=False):
    try:
        chat_id = message.chat.id
        message_id = message.message_id if edit_message else None
        keyboard = InlineKeyboardMarkup(row_width=2)
        buttons = [
            InlineKeyboardButton("🛒 Купить", callback_data="premium_buy"),
            InlineKeyboardButton("🔄 Условия возврата", callback_data="premium_refund"),
            InlineKeyboardButton("📜 Юридическая информация", callback_data="premium_legal"),
            InlineKeyboardButton("📄 Оферта", callback_data="premium_offer"),
            InlineKeyboardButton("🔐 Политика обработки персональных данных", callback_data="premium_policy"),
        ]
        keyboard.add(*buttons)
        
        text = (
            "🔥 <b>Премиум-подписка — твой ключ к командной эффективности! 🔑</b>\n\n"
            "💡 <b>Что вы получаете?</b>\n"
            "1️⃣ Персональный анализ: получайте развернутые рекомендации по улучшению работы каждого члена команды.\n"
            "2️⃣ Генерация технических заданий: создавайте четкие и понятные ТЗ по вашему голосовому или текстовому запросу.\n"
            "3️⃣ Расширенные лимиты: до 100 запросов в месяц — без ограничений для вашего прогресса!\n\n"
            "🌟 <b>Почему это важно?</b>\n"
            "Искусственный интеллект помогает вашей команде быть более продуктивной, улучшать коммуникации и достигать целей быстрее. "
            "Премиум — это инструмент для профессионалов, которые ценят свое время и хотят работать умнее.\n\n"
            "🎯 Начните использовать все возможности прямо сейчас!\n\n"
            "👇 <b>Нажмите кнопку «Купить», чтобы оформить подписку за 149 ₽ в месяц и сделать вашу работу еще эффективнее.</b>"
        )

        if edit_message:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                chat_id, 
                text, 
                parse_mode="HTML", 
                reply_markup=keyboard, 
                message_thread_id=message.message_thread_id
            )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")


# Обработка /ai - соглашение об использовании ИИ
@bot.message_handler(commands=["ai"])
async def ai_agreement(message):
    text = "Соглашение об использовании нейрогенеративных инструментов"
    
    markup = InlineKeyboardMarkup()
    button = InlineKeyboardButton("Скачать соглашение", AI_POLICY_LINK)
    markup.add(button)

    await bot.send_message(message.chat.id, text, reply_markup=markup, message_thread_id=message.message_thread_id)


# Обрабатывает /tz
@bot.message_handler(commands=['tz'])
async def handle_tz_command(message):
    try:
        can_media = await get_midia_limit(message.from_user.id, message.from_user.username)
        if can_media > 0:
            chat_title = message.chat.title or "Без названия"
            chat_id = message.chat.id
            logging.info(f"Пользователь нажал /tz в группе {chat_title} (ID: {chat_id})")
            
            keyboard = InlineKeyboardMarkup()
            roles = ["Программист", "Дизайнер", "Аналитик", "PR-менеджер"]
            for role in roles:
                keyboard.add(InlineKeyboardButton(role, callback_data=f"role_{role}"))

            user_data[chat_id] = {'stage': 'selecting_role'}

            await bot.send_message(chat_id, "<b>Выберите роль, для которой нужно составить запрос:</b>", parse_mode='HTML', reply_markup=keyboard, message_thread_id=message.message_thread_id)
        else:
            await bot.send_message(chat_id, "<b>У вас закончился лимит запросов\nЕсли очень хотите продлить его - напишите @buqip</b>", parse_mode='HTML', message_thread_id=message.message_thread_id)
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")






# Обрабатывет выбор роли в /tz
@bot.callback_query_handler(func=lambda call: call.data.startswith('role_'))
async def handle_role_selection(call):
    try:
        chat_id = call.message.chat.id
        role = call.data.split('_')[1]  

        user_data[chat_id]['role'] = role

        keyboard = InlineKeyboardMarkup()
        styles = ["Деловой", "Дружелюбный", "Краткий", "Подробный"]
        for style in styles:
            keyboard.add(InlineKeyboardButton(style, callback_data=f"style_{style}"))

        user_data[chat_id]['stage'] = 'selecting_style'

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"Вы выбрали роль: <b>{role}</b>\n\nТеперь выберите стилистику запроса:",
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")






# Обрабатывает выбор стиля после /tz
@bot.callback_query_handler(func=lambda call: call.data.startswith('style_'))
async def handle_style_selection(call):
    try:
        chat_id = call.message.chat.id
        style = call.data.split('_')[1]  

        user_data[chat_id]['style'] = style

        user_data[chat_id]['stage'] = 'waiting_for_query'
        can_media = await get_midia_limit(call.from_user.id, call.from_user.username)
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"Вы выбрали стилистику: <b>{style}</b>\n\nТеперь введите сам запрос:\n{'(можно голосовым или текстом)' if can_media else '(можно только текстом)'}",
            parse_mode='HTML'
        )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}") 




# Обработка запроса в tz
@bot.message_handler(func=lambda message: 
    message.chat.id in user_data and 
    user_data[message.chat.id].get('stage') == 'waiting_for_query'
)
async def handle_user_query(message):
    try:
        query = message.text
        await decrement_midia_limit(message.from_user.id)
        chat_id = message.chat.id

        user_data[chat_id]['query'] = query

        role = user_data[chat_id]['role']
        style = user_data[chat_id]['style']

        prompt = (
            f"Составь запрос для роли - {role} (напиши на понятном для него языке) на основе текста, который сейчас пришлю\n\n"
            f"Стиль перевода: {style}."
        )
        completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": f"Текст: {query}"
                }
            ]
        )


        if completion:
            result = str(completion.choices[0].message.content).replace('#', '').replace('*', '')
        else:
            result = "Ошибка в отправке сообщения"

        cnt = 0
        for chunk in smart_split(result):
            if cnt == 0:
                await bot.send_message(chat_id, f"Готово! Вот ваше ТЗ:\n\n{chunk}", message_thread_id=message.message_thread_id)
            else:
                await bot.send_message(chat_id, chunk, message_thread_id=message.message_thread_id)
            cnt += 1

    except:
        await bot.send_message(chat_id, "Произошла ошибка при обработке запроса.", message_thread_id=message.message_thread_id)
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")

    user_data.pop(chat_id, None)





# Обработка изменения параметров настроек
@bot.callback_query_handler(func=lambda call: call.data in [
    "toggle_record", 
    "toggle_style", 
    "toggle_reminder",
    "decrement_limit_settings", 
    "increment_limit_settings", 
    "decrement_limit_large_settings", 
    "increment_limit_large_settings"
])
async def handle_settings_and_limit(call):
    try:
        chat_id = call.message.chat.id
        user_id = call.from_user.id
        action = call.data  


        if action == "toggle_record":
            admins = await bot.get_chat_administrators(chat_id)
            admin_ids = {admin.user.id for admin in admins}

            if user_id not in admin_ids:
                await bot.answer_callback_query(call.id, "Изменять этот параметр могут только администраторы.")
                return

            cursor.execute("SELECT record FROM settings WHERE chat_id = ?", (chat_id,))
            current_value = cursor.fetchone()[0]
            new_value = not bool(current_value)
            cursor.execute("UPDATE settings SET record = ? WHERE chat_id = ?", (int(new_value), chat_id))
        
        elif action == "toggle_style":
            styles = ["Деловой", "Дружелюбный", "Краткий", "Подробный"]
            cursor.execute("SELECT style FROM settings WHERE chat_id = ?", (chat_id,))
            current_style = cursor.fetchone()[0]
            current_index = styles.index(current_style)
            new_index = (current_index + 1) % len(styles)
            new_style = styles[new_index]
            cursor.execute("UPDATE settings SET style = ? WHERE chat_id = ?", (new_style, chat_id))
        
        elif action == "toggle_reminder":
            cursor.execute("SELECT reminder_enabled FROM settings WHERE chat_id = ?", (chat_id,))
            current_value = cursor.fetchone()[0]
            new_value = not bool(current_value)
            cursor.execute("UPDATE settings SET reminder_enabled = ? WHERE chat_id = ?", (int(new_value), chat_id))
        
        elif action in [
            "decrement_limit_settings", 
            "increment_limit_settings", 
            "decrement_limit_large_settings", 
            "increment_limit_large_settings"
        ]:
            cursor.execute("SELECT [limit] FROM settings WHERE chat_id = ?", (chat_id,))
            current_limit = cursor.fetchone()[0]

            if action == "decrement_limit_settings":
                new_limit = max(10, current_limit - 10)
            elif action == "increment_limit_settings":
                new_limit = current_limit + 10
            elif action == "decrement_limit_large_settings":
                new_limit = max(10, current_limit - 100)
            elif action == "increment_limit_large_settings":
                new_limit = current_limit + 100
            cursor.execute("UPDATE settings SET [limit] = ? WHERE chat_id = ?", (new_limit, chat_id))

        conn.commit()

        cursor.execute("SELECT record, style, reminder_enabled, [limit] FROM settings WHERE chat_id = ?", (chat_id,))
        record, style_value, reminder_enabled_value, limit_value = cursor.fetchone()


        keyboard = InlineKeyboardMarkup(row_width=5)

        ask_button = InlineKeyboardButton(f"record: {'Включено' if bool(record) else 'Выключено'}", callback_data="toggle_record")
        style_button = InlineKeyboardButton(f"style: {style_value}", callback_data="toggle_style")
        reminder_button = InlineKeyboardButton(f"reminder: {'Включено' if reminder_enabled_value else 'Выключено'}", callback_data="toggle_reminder")

        decrement_button = InlineKeyboardButton("-10", callback_data="decrement_limit_settings")
        increment_button = InlineKeyboardButton("+10", callback_data="increment_limit_settings")
        decrement_large_button = InlineKeyboardButton("-100", callback_data="decrement_limit_large_settings")
        increment_large_button = InlineKeyboardButton("+100", callback_data="increment_limit_large_settings")
        limit_button = InlineKeyboardButton(f"limit: {limit_value}", callback_data="noop")

        keyboard.add(decrement_large_button, decrement_button, limit_button, increment_button, increment_large_button)
        keyboard.add(ask_button)
        keyboard.add(style_button)
        keyboard.add(reminder_button)

        # Обновляем текст сообщения
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=keyboard
        )
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")






# Обработка кнопок
@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_"))
async def handle_premium_callbacks(call):
    try:
        if call.data == "premium_buy":
            if call.message.chat.type == "private":
                await bot.send_message(
                    chat_id=call.message.chat.id,
                    text="Купить премиум в ЛС нельзя. Добавьте бота в группу.",
                    parse_mode="HTML"
                )
                return
            keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Вернуться назад", callback_data="premium_back"))
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🔗 <b>Ссылка на покупку:</b> https://example.com/buy",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        elif call.data == "premium_refund":
            text = (
                "🔄 <b>Условия возврата услуги</b>\n\n"
                "📌 <b>Условия предоставления подписки:</b>\n"
                "Подписка активируется сразу после успешной оплаты и дает доступ ко всем премиум-функциям на 30 дней.\n\n"
                "📌 <b>Условия возврата:</b>\n"
                "• Возврат возможен в течение 14 дней с момента оплаты, если подписка не была использована (не было выполнено ни одного запроса).\n"
                "• Если подписка была частично использована, возврат средств не предусмотрен.\n\n"
                "📌 <b>Как запросить возврат?</b>\n"
                f"Напишите на {EMAIL}.\n"
                "Укажите:\n"
                "   • Дату оплаты.\n"
                "   • Номер транзакции (полученный при оплате).\n"
                "   • Причину запроса возврата.\n\n"
                "📌 <b>Сроки обработки заявки:</b>\n"
                "Ваш запрос будет рассмотрен в течение 5 рабочих дней. Если возврат одобрен, средства поступят на ваш счет в течение 7 рабочих дней после обработки заявки.\n\n"
                "📌 <b>Важно:</b>\n"
                "Возврат средств осуществляется в соответствии с законодательством РФ и условиями пользовательского соглашения."
            )
            keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Вернуться назад", callback_data="premium_back"))
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        elif call.data == "premium_legal":
            text = (
                "📜 <b>Юридическая информация</b>\n\n"
                "🗂️ <b>Общие данные:</b>\n"
                f"• Название компании: {COMPANY_NAME}\n"
                f"• ИНН: {INN}\n"
                f"• ОГРН/ОГРНИП: {OGRN}\n"
                f"• Местоположение: {LOCATION}\n\n"
                "📧 <b>Контактные данные:</b>\n"
                f"• Email для связи: {EMAIL}\n"
                f"• Телефон: {PHONE}"
            )
            keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Вернуться назад", callback_data="premium_back"))
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        elif call.data == "premium_offer":
            text = (
                "📄 <b>Оферта</b>\n\n"
                "📌 <b>О чём документ?</b>\n"
                "Публичная оферта — это договор, который регулирует предоставление услуг нашим ботом. Принятие оферты происходит автоматически при оформлении подписки или использовании наших услуг.\n\n"
                "📌 <b>Основные моменты:</b>\n"
                "• Условия оказания информационно-консультативных услуг.\n"
                "• Порядок оплаты и возврата средств.\n"
                "• Обязательства и права сторон.\n"
                "• Конфиденциальность и безопасность данных.\n\n"
                "📌 <b>Как действует оферта?</b>\n"
                "Оферта вступает в силу с момента оплаты подписки и действует до полного выполнения обязательств.\n\n"
                "❓ <b>Есть вопросы?</b>\n"
                f"Свяжитесь с нами: {EMAIL}\n\n"
                "📌 Полный текст доступен по ссылке ниже 👇"
            )
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🔗 Скачать оферту", url=OFFER_LINK),
                InlineKeyboardButton("🔙 Вернуться назад", callback_data="premium_back")
            )
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        elif call.data == "premium_policy":
            text = (
                "🔐 Политика конфиденциальности и обработки персональных данных\n\n"
                "🔒 Мы заботимся о вашей конфиденциальности!\n\n"

                "В этом документе вы найдете:\n"
                "• 📋 Какие данные мы обрабатываем\n"
                "• ⚙️ Как мы их используем\n"
                "• 🛡️ Как обеспечиваем их защиту\n\n"

                "Все действия выполняются в соответствии с <b>ФЗ №152 «О персональных данных»</b>.\n\n"

                "📌 Полный текст доступен по ссылке ниже 👇"
            )
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🔗 Открыть политику", url=CONF_PD_LINK),
                InlineKeyboardButton("🔙 Вернуться назад", callback_data="premium_back")
            )
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        elif call.data == "premium_back":
            await handle_premium(call.message, True)
        
        elif call.data == "premium_main":
            text = (
                "🔥 Премиум-подписка — твой ключ к командной эффективности! 🔑\n\n"
                "💡 Что вы получаете?\n"
                "1️⃣ Персональный анализ: получайте развернутые рекомендации по улучшению работы каждого члена команды.\n"
                "2️⃣ Генерация технических заданий: создавайте четкие и понятные ТЗ по вашему голосовому или текстовому запросу.\n"
                "3️⃣ Расширенные лимиты: до 100 запросов в месяц — без ограничений для вашего прогресса!\n\n"
                "🌟 Почему это важно?\n"
                "Искусственный интеллект помогает вашей команде быть более продуктивной, улучшать коммуникации и достигать целей быстрее. Премиум — это инструмент для профессионалов, которые ценят свое время и хотят работать умнее.\n\n"
                "🎯 Начните использовать все возможности прямо сейчас!\n\n"
                "👇 Нажмите кнопку «Купить», чтобы оформить подписку за 149 ₽ в месяц и сделать вашу работу еще эффективнее."
            )
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🛒 Купить", callback_data="premium_buy"),
                InlineKeyboardButton("🔄 Условия возврата", callback_data="premium_refund"),
                InlineKeyboardButton("📜 Юридическая информация", callback_data="premium_legal"),
                InlineKeyboardButton("📄 Оферта", callback_data="premium_offer"),
                InlineKeyboardButton("🔐 Политика обработки персональных данных", callback_data="premium_policy")
            )
            await bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
    
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")






# Функция для записи сообщения в базу данных
async def save_message_to_db(message_id, chat_id, user_id, thread_id, username, content, date):
    try:
        cursor.execute('''
            INSERT INTO messages (message_id, chat_id, user_id, thread_id, username, content, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, chat_id, user_id, thread_id, username, content, date))
        conn.commit()
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")




# Функция для загрузки сообщений из БД
async def load_messages(chat_id, thread_id, limit=100):
    try:
        query = '''
            SELECT username, content, date FROM messages
            WHERE chat_id = ? AND (thread_id = ? OR thread_id IS NULL)
            ORDER BY date DESC LIMIT ?
        '''
        cursor.execute(query, (chat_id, thread_id, limit))
        return cursor.fetchall()
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")




# Функция для обработки команд
@bot.message_handler(commands=['analyze', 'analyze_for_me', 'summarize'])
async def handle_command(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id

        is_can = await can_user_execute_command(user_id, message.from_user.username)

        if is_can:
            thread_id = getattr(message, "message_thread_id", None)

            cursor.execute("SELECT [limit] FROM settings WHERE chat_id = ?", (chat_id,))
            limit_result = cursor.fetchone()
            limit = limit_result[0] if limit_result else 100

            messages = await load_messages(chat_id, thread_id, limit)

            if not(messages): 
                text = 'У меня нет сообщений для вашего чата'
            else:
                text = f"Сообщений для суммаризации: {len(messages)}. Подождите немного, пожалуйста..."
            
            can_zapis = await get_record(chat_id)
            text += '\n\nЗапись сообщений выключена. \nВы можете включить её в настройках (/settings)' if not(can_zapis) else ''
            
            if not(messages): 
                await bot.send_message(chat_id, text, message_thread_id=message.message_thread_id)
                return
            else:
                await bot.send_message(chat_id, text, message_thread_id=message.message_thread_id)
            formatted_messages = [
                f"Пользователь: {username}, сообщение: {content}, дата: {date}"
                for username, content, date in messages
            ]


            style = await get_style_for_chat(chat_id)


            if message.text.startswith("/analyze_for_me") or message.text == "Личный анализ":
                user = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''} @{message.from_user.username or ''}".strip()
                prompt = (
                                f"Ты получил переписку участников команды (текст, видео, аудио, стикеры, информация про реакции - всё что есть в чате). Подготовь персональные рекомендации по улучшению навыков работы ОДНОГО ИЗ УЧАСТНИКОВ переписки - ({user}) . \n\n"
                                "Результат представь в следующем формате:\n\n"
                                "1. Рекомендации по улучшению навыков командной работы для участника. \n"
                                "2. Оценить эффективность командной работы участника по шкале от 1 до 10.\n\n"
                                f"Стиль рекомендаций: {style}."
                                "Также добавь немного смайликов, которые будут помогать структуризировать анализ."
                                "Если в переписке нету этого участника, то так и напиши"
                        )
            elif message.text.startswith("/analyze") or message.text == "Анализ":
                prompt = (
                            "Ты получил переписку участников команды (текст, видео, аудио, стикеры, информация про реакции - всё что есть в чате). Подготовь рекомендации по улучшению навыков командной работы для каждого из участников переписки. \n\n"
                            "Результат представь в следующем формате:\n\n"
                            "1. Рекомендации по улучшению навыков командной работы для каждого участника по отдельности. \n"
                            "2. Оценить эффективность командной работы каждого участника по шкале от 1 до 10.\n\n"
                            f"Стиль рекомендаций: {style}."
                            "Также добавь немного смайликов, которые будут помогать структуризировать анализ."
                        )
            
            elif message.text.startswith("/summarize") or message.text == "Саммари":
                prompt = (
                            "Сейчас я тебе отправлю переписку участников команды (текст, видео, аудио, стикеры, информация про реакции - всё что есть в чате).\n\n"
                            "Мне необходимо получить саммари всей этой переписки.\n\n"
                            "Сделай это, включив полный план того, что мы обсуждали, основные тезисы того, что мы решили делать, наши задачи на следующую встречу и какие-либо идеи, которые мы озвучивали.\n"
                            "Сам ничего не дополняй, мне нужна именно выжимка.\n"
                            "Составь саммари в формате оформленного сообщения в Телеграм.\n"
                            "Не нужно добавлять многоэтажной структуры (подпункты и тд.), так как Телеграм это нормально не отображает.\n"
                            "Также добавь немного смайликов, которые будут помогать структуризировать саммари."
                        )

            response = await send_to_openai(prompt, formatted_messages, user_id)



            for chunk in smart_split(str(response).replace('#', '').replace('*', '')):
                await bot.send_message(chat_id, chunk, reply_to_message_id=message.message_id)
        else:
            await bot.send_message(chat_id, "<b>У вас закончился лимит на запросы</b>", reply_to_message_id=message.message_id, parse_mode='HTML')
    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")




# Обрабатываем тот момент, когда прислали гс больше минуты и пользователь нажал 'да'
@bot.callback_query_handler(func=lambda call: call.data.startswith("voise_yes"))
async def voise_yes(call):
    try:
        await bot.edit_message_reply_markup(chat_id=call.message.chat.id, 
                                      message_id=call.message.message_id, 
                                      reply_markup=None)
        _, message_id, chat_id, thread_id = call.data.split(":")
        chat_id = int(chat_id)
        message_id = int(message_id)
        thread_id = None if thread_id.lower() == 'none' else int(thread_id)

        cursor.execute("SELECT content FROM messages WHERE message_id = ? AND chat_id = ? AND (thread_id = ? OR thread_id IS NULL)", 
                       (message_id, chat_id, thread_id))
        db_entry = cursor.fetchone()

        if db_entry:
            transcription = db_entry[0]
            prompt = (
                "Пожалуйста, сделай краткое и понятное резюме (саммари) следующего текста. "
                "Выдели ключевые моменты, идеи и действия. Текст:\n\n"
                f"{transcription}"
            )
                        
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты помощник, делающий саммари текста."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            summary = response.choices[0].message.content
            
            await bot.send_message(
                chat_id, 
                f"Саммари голосового сообщения:\n{str(summary).replace('#', '').replace('*', '')}",
                message_thread_id=thread_id
            )
        else:
            await bot.send_message(chat_id, "Подождите немного, я обрабатываю ваше голосовое сообщение...", message_thread_id=call.message.message_thread_id)

            while True:
                cursor.execute("SELECT content FROM messages WHERE message_id = ? AND chat_id = ? AND (thread_id = ? OR thread_id IS NULL)",
                               (message_id, chat_id, thread_id))
                db_entry = cursor.fetchone()

                if db_entry:
                    transcription = db_entry[0]
                    prompt = (
                        "Пожалуйста, сделай краткое и понятное резюме (саммари) следующего текста. "
                        "Выдели ключевые моменты, идеи и действия. Текст:\n\n"
                        f"{transcription}"
                    )
                                
                    response = await client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "Ты помощник, делающий саммари текста."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    
                    summary = response.choices[0].message.content
                    
                    await bot.send_message(
                        chat_id, 
                        f"Саммари голосового сообщения:\n\n{str(summary).replace('#', '').replace('*', '')}",
                        message_thread_id=thread_id
                    )
                    break  

                await asyncio.sleep(1)

    except:
        logging.exception("Произошла ошибка в voise_yes")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)

        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        await bot.send_message(chat_id, "Не удалось обработать голосовое сообщение")






# Обработчик всех сообщений
@bot.message_handler(content_types=['text', 'photo', 'video', 'audio', 'document', 'sticker', 'voice', 'video_note'])
async def handle_message(message):
    try:
        chat_id = message.chat.id
        try:
            if message.from_user.is_bot:
                return
            elif message.chat.id in user_data and user_data[message.chat.id]['stage'] == 'waiting_for_query':
                if message.voice:
                    can_media = await get_midia_limit(message.from_user.id, message.from_user.username)
                    if can_media > 0:
                        query = await process_voice(message)
                        user_data[chat_id]['query'] = query

                        role = user_data[chat_id]['role']
                        style = user_data[chat_id]['style']

                        prompt = (
                            f"Составь запрос для роли - {role} (напиши на понятном для него языке) на основе текста, который сейчас пришлю\n\n"
                            f"Стиль перевода: {style}."
                        )
                        completion = await client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": prompt},
                                {
                                    "role": "user",
                                    "content": f"Текст: {query}"
                                }
                            ]
                        )


                        if completion:
                            result = str(completion.choices[0].message.content).replace('#', '').replace('*', '')
                        else:
                            result = "Ошибка в отправке сообщения"

                        cnt = 0
                        for chunk in smart_split(result):
                            if cnt == 0:
                                await bot.send_message(chat_id, f"Готово! Вот ваше ТЗ:\n\n{chunk}", message_thread_id=message.message_thread_id)
                            else:
                                await bot.send_message(chat_id, chunk, message_thread_id=message.message_thread_id)
                            cnt += 1
                        await decrement_midia_limit(message.from_user.id)
                    else:
                        await bot.send_message(
                                chat_id,
                                "<b>У вас закончился лимит</b>",
                                parse_mode='HTML',
                                reply_to_message_id=message.message_id
                        )
                        return
        except:
            pass


        
        can_zapis = await get_record(chat_id)
        # Если пользователь хочет - записываем
        if can_zapis:
            content = ""
            username = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''} @{message.from_user.username or ''}".strip()
            thread_id = getattr(message, "message_thread_id", None)

            if message.text:
                content += f"Текст: {message.text.strip()}\n"

            if message.sticker:
                sticker_emoji = message.sticker.emoji or "Без эмодзи"
                content += f"Пользователь прислал стикер: {sticker_emoji}\n"

            can_media = await get_midia_limit(message.from_user.id, message.from_user.username)
            if can_media > 0:
                if message.photo:
                    content += "Изображение: \n"
                    photo = await process_photo(message)
                    content += str(photo).replace('#', '').replace('*', '')

                if message.video:
                    content += "Пользователь прислал видео (транскрибация):\n"
                    video = await process_video(message)
                    content += str(video).replace('#', '').replace('*', '')

                if message.audio:
                    content += "Пользователь прислал аудио (транскрибация):\n"
                    audio = await process_audio(message)
                    content += str(audio).replace('#', '').replace('*', '')

                if message.document:
                    file_name = message.document.file_name
                    content += f"Пользователь прислал файл: {file_name}\n"


                if message.voice:
                    can_media = await get_midia_limit(message.from_user.id, message.from_user.username)
                    duration = message.voice.duration
                    if can_media > 0 and duration > 40:
                            keyboard = InlineKeyboardMarkup(row_width=1)
                            callback_data = f"voise_yes:{message.message_id}:{chat_id}:{getattr(message, 'message_thread_id', 'none')}"
                            keyboard.add(InlineKeyboardButton("Да", callback_data=callback_data))

                            await bot.send_message(
                                        chat_id,
                                        "Вы прислали голосовое сообщение длительностью более 40 секунд. \nХотите, чтобы я его суммаризировал?",
                                        reply_to_message_id=message.message_id,
                                        reply_markup=keyboard
                                    )
                    content += "Пользователь прислал голосовое сообщение (транскрибация):\n"
                    voice = await process_voice(message)
                    content += str(voice).replace('#', '').replace('*', '')
                if message.video_note:
                    content += "Пользователь прислал видеосообщение (транскрибация):\n"
                    video_note = await process_video_note(message)
                    content += str(video_note).replace('#', '').replace('*', '')

                await save_message_to_db(
                            message_id=message.message_id,
                            chat_id=chat_id,
                            user_id=message.from_user.id,
                            thread_id=thread_id,
                            username=username,
                            content=content.strip(),
                            date=message.date
                )

                await increment_message_count(chat_id, thread_id)
    except:
        logging.exception("Произошла ошибка")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)

        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")

# получает значение лимита медиа сообщений
async def get_midia_limit(user_id, username):
    # Проверяем, есть ли запись для данного user_id
    cursor.execute("SELECT midia_limit FROM message_limits WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    

    cursor.execute("SELECT unlimited_users FROM vip WHERE unlimited_users = ?", (username,))
    vip_user = cursor.fetchone()
    if vip_user:
        return True  
    if result:
        return result[0]
    else:
        cursor.execute(
            "INSERT INTO message_limits (user_id, remaining_requests, midia_limit) VALUES (?, ?, ?)",
            (user_id, 5, 10)
        )
        return 10

# Обрабатывает фото        
async def process_photo(message):
    try:
        file_info = await bot.get_file(message.photo[-1].file_id)
        file_path = file_info.file_path

        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)

        if response.status_code != 200:
            return "Не удалось загрузить изображение"

        image_data = io.BytesIO(response.content)
        image_data.seek(0)

        base64_image = base64.b64encode(image_data.read()).decode('utf-8')

        image_url = f"data:image/jpeg;base64,{base64_image}"

        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Опишите коротко, что изображено на фотографии. (Если есть текст - напиши текст)"},
                    {"role": "user", "content": f"{{'type': 'image_url', 'image_url': {{'url': '{image_url}'}}}}"}
                ]
            )
        except:
            return "очень большой размер"

        await decrement_midia_limit(message.from_user.id)

        return response.choices[0].message.content

    except Exception as e:
        logging.exception("Произошла ошибка при обработке фото")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)

        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Не удалось обработать изображение"



# Транскрибация аудио
async def process_audio(message):
    try:
        try:
            file_info = await bot.get_file(message.audio.file_id)
        except:
            return "очень большое аудио"
        file_path = file_info.file_path

        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)

        if response.status_code != 200:
            logging.error("Ошибка при скачивании аудиофайла")
            return "Не удалось транскрибировать аудио"

        audio_file = io.BytesIO(response.content)
        audio_file.name = "audio.mp3"  

        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )

        await decrement_midia_limit(message.from_user.id)
        return transcription.text

    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Не удалось транскрибировать аудио"



# Транскрибация голосового сообщения
async def process_voice(message):
    try:
        try:
            file_info = await bot.get_file(message.voice.file_id)
        except:
            return "очень большое голосовое сообщение"
        file_path = file_info.file_path
        
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)

        if response.status_code != 200:
            logging.error("Ошибка при скачивании голосового сообщения")
            return "Не удалось загрузить голосовое сообщение"

        voice_file = io.BytesIO(response.content)
        voice_file.name = "voice.ogg"  

        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=voice_file
        )

        await decrement_midia_limit(message.from_user.id)
        return transcription.text

    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Не удалось транскрибировать голосовое сообщение"




# Видео -> Аудио -> Транскрибация
async def process_video(message):
    try:
        try:
            file_info = await bot.get_file(message.video.file_id)
        except:
            return "очень большое видео"
        file_path = file_info.file_path

        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)

        if response.status_code != 200:
            logging.error("Ошибка при скачивании видеофайла")
            return "Не удалось скачать видеофайл."

        video_file = io.BytesIO(response.content)
        video_file.seek(0) 

        audio_buffer = io.BytesIO()
        with VideoFileClip(video_file) as video:
            audio = video.audio
            if audio:
                audio.write_audiofile(audio_buffer, codec="libmp3lame")
            else:
                return "Пользователь прислал видео без звука (gif)"
        
        audio_buffer.seek(0)  

        transcription = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_buffer
        )
        await decrement_midia_limit(message.from_user.id)
        return transcription.text

    except:
        logging.exception("Произошла ошибка")  
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)
        
        error_str = error_message.getvalue()

        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Не удалось обработать видеофайл."



# Кружочек -> Аудио -> Транскрибация
async def process_video_note(message):
    try:
        base_dir = Path(__file__).parent / "downloads" / str(message.chat.id)
        if hasattr(message, "message_thread_id") and message.message_thread_id:
            base_dir /= str(message.message_thread_id)
        base_dir.mkdir(parents=True, exist_ok=True)

        temp_video_path = base_dir / "video_note.mp4"
        temp_audio_path = base_dir / f"audio_{message.message_id}.mp3"

        try:
            file_info = await bot.get_file(message.video_note.file_id)
        except:
            return "очень большое видеосообщение"
        file_path = file_info.file_path

        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        response = requests.get(file_url)

        if response.status_code != 200:
            logging.error("Ошибка при скачивании видео-кружочка")
            return "Не удалось скачать видео-кружочек."

        with open(temp_video_path, "wb") as temp_video_file:
            temp_video_file.write(response.content)

        with VideoFileClip(str(temp_video_path)) as video:
            if video.audio is None:
                logging.error("У видео нет аудиодорожки")
                return "Видео-кружочек не содержит аудио."
            
            video.audio.write_audiofile(str(temp_audio_path), codec="libmp3lame")

        with open(temp_audio_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        await decrement_midia_limit(message.from_user.id)
        return transcription.text

    except Exception as e:
        logging.exception("Ошибка при обработке видео-кружочка")
        error_message = io.StringIO()
        traceback.print_exc(file=error_message)

        error_str = error_message.getvalue()
        await bot.send_message(CHAT_LOGOV_ID, f"⚠️ ERROR ⚠️:\n\n{error_str}")
        return "Не удалось обработать видео-кружочек."

    finally:
        try:
            if temp_video_path.exists():
                temp_video_path.unlink()
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        except Exception as cleanup_error:
            logging.warning(f"Ошибка при удалении временных файлов: {cleanup_error}")



# Главная асинхронная функция
async def start():
    logging.info("Бот запущен и готов к работе.")
    await bot.polling()


# Запуск
if __name__ == "__main__":
    asyncio.run(start())