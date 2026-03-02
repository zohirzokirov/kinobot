import os
import logging
import time
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import mysql.connector
from mysql.connector import Error
import telebot
from telebot import types
from dotenv import load_dotenv

# Environment variables
load_dotenv()

# Logging konfiguratsiyasi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Konfiguratsiya
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
ADMIN_CHANNEL_ID = int(os.getenv('ADMIN_CHANNEL_ID', 0))

# MySQL konfiguratsiyasi
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'telegram_bot'),
    'buffered': True
}



TOKEN = BOT_TOKEN

bot = telebot.TeleBot(TOKEN)

bot_info = bot.get_me()
print(bot_info.username)

# Botni yaratish
bot = telebot.TeleBot(BOT_TOKEN)

# User session ma'lumotlari
user_sessions: Dict[int, Dict[str, Any]] = {}
user_last_request: Dict[int, float] = {}

# Anti-spam dekoratori
def anti_spam(func):
    def wrapper(message):
        user_id = message.from_user.id
        current_time = time.time()
        
        if user_id in user_last_request:
            time_diff = current_time - user_last_request[user_id]
            if time_diff < 0.6:
                bot.send_message(user_id, "❌ Iltimos, biroz sekinroq so'rov yuboring!")
                return
        
        user_last_request[user_id] = current_time
        return func(message)
    
    return wrapper

# User tekshirish dekoratori
def check_user_registered(func):
    def wrapper(message):
        user_id = message.from_user.id
        username = message.from_user.username
        
        # User bazada borligini tekshirish
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                
                if not user:
                    # User bazada yo'q, qo'shamiz
                    save_user(user_id, username)
                    logger.info(f"Yangi foydalanuvchi qo'shildi: {user_id}")
                
            except Error as e:
                logger.error(f"User check error: {e}")
            finally:
                cursor.close()
                connection.close()
        
        return func(message)
    return wrapper

# Majburiy obuna dekoratori
# Majburiy obuna dekoratori
def check_subscription(func):
    def wrapper(message):
        user_id = message.from_user.id
        
        # Adminlar uchun tekshirmaymiz
        if user_id in ADMIN_IDS:
            return func(message)
        
        # Majburiy kanallarni tekshirish
        mandatory_channels = get_mandatory_channels()
        
        if not mandatory_channels:
            return func(message)
        
        # Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshirish
        not_subscribed = []
        for channel in mandatory_channels:
            channel_id = channel[2]  # channel_id (3-element)
            if channel_id:
                try:
                    chat_member = bot.get_chat_member(channel_id, user_id)
                    if chat_member.status not in ['member', 'administrator', 'creator']:
                        not_subscribed.append(channel)
                except Exception as e:
                    logger.error(f"Channel check error: {e}")
                    not_subscribed.append(channel)
        
        if not_subscribed:
            # Agar obuna bo'lmagan kanallar bo'lsa
            show_subscription_required(message, not_subscribed)
            return
        
        return func(message)
    
    return wrapper

# Callback query uchun majburiy obuna dekoratori
def check_subscription_callback(func):
    def wrapper(call):
        user_id = call.from_user.id
        
        # Adminlar uchun tekshirmaymiz
        if user_id in ADMIN_IDS:
            return func(call)
        
        # Majburiy kanallarni tekshirish
        mandatory_channels = get_mandatory_channels()
        
        if not mandatory_channels:
            return func(call)
        
        # Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshirish
        not_subscribed = []
        for channel in mandatory_channels:
            channel_id = channel[2]  # channel_id (3-element)
            if channel_id:
                try:
                    chat_member = bot.get_chat_member(channel_id, user_id)
                    if chat_member.status not in ['member', 'administrator', 'creator']:
                        not_subscribed.append(channel)
                except Exception as e:
                    logger.error(f"Channel check error: {e}")
                    not_subscribed.append(channel)
        
        if not_subscribed:
            # Agar obuna bo'lmagan kanallar bo'lsa
            show_subscription_required_callback(call, not_subscribed)
            return
        
        return func(call)
    
    return wrapper
# Inline query uchun majburiy obuna dekoratori
def check_subscription_inline(func):
    def wrapper(query):
        user_id = query.from_user.id
        
        # Adminlar uchun tekshirmaymiz
        if user_id in ADMIN_IDS:
            return func(query)
        
        # Majburiy kanallarni tekshirish
        mandatory_channels = get_mandatory_channels()
        
        if not mandatory_channels:
            return func(query)
        
        # Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshirish
        not_subscribed = []
        for channel in mandatory_channels:
            channel_id = channel[2]  # channel_id (3-element)
            if channel_id:
                try:
                    chat_member = bot.get_chat_member(channel_id, user_id)
                    if chat_member.status not in ['member', 'administrator', 'creator']:
                        not_subscribed.append(channel)
                except Exception as e:
                    logger.error(f"Channel check error: {e}")
                    not_subscribed.append(channel)
        
        if not_subscribed:
            # Agar obuna bo'lmagan kanallar bo'lsa
            show_subscription_required_inline(query, not_subscribed)
            return
        
        return func(query)
    
    return wrapper

def show_subscription_required(message, channels):
    user_id = message.from_user.id
    
    # Majburiy va ixtiyoriy kanallarni ajratib olish
    mandatory_channels = [ch for ch in channels]  # channels faqat majburiy kanallar
    optional_channels = get_optional_channels()   # ixtiyoriy kanallarni alohida olamiz
    
    text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Barcha majburiy kanallar
    all_channels = mandatory_channels + optional_channels
    
    for channel in all_channels:
        channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
        
        # Kanal linkini olish
        if channel_db_id:  # Agar channel_id bo'lsa (Telegram kanali)
            channel_url = get_channel_url(channel_db_id)
            if not channel_url:
                channel_url = channel_link
        else:
            channel_url = channel_link
        
        # Tugma matni faqat "A'zo bo'lish"
        keyboard.add(types.InlineKeyboardButton(
            "A'zo bo'lish", 
            url=channel_url
        ))
    
    keyboard.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_subscription"))
    
    bot.send_message(user_id, text, reply_markup=keyboard)

def show_subscription_required_callback(call, channels):
    user_id = call.from_user.id
    
    # Majburiy va ixtiyoriy kanallarni ajratib olish
    mandatory_channels = [ch for ch in channels]  # channels faqat majburiy kanallar
    optional_channels = get_optional_channels()   # ixtiyoriy kanallarni alohida olamiz
    
    text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Barcha majburiy kanallar
    all_channels = mandatory_channels + optional_channels
    
    for channel in all_channels:
        channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
        
        # Kanal linkini olish
        if channel_db_id:  # Agar channel_id bo'lsa (Telegram kanali)
            channel_url = get_channel_url(channel_db_id)
            if not channel_url:
                channel_url = channel_link
        else:
            channel_url = channel_link
        
        # Tugma matni faqat "A'zo bo'lish"
        keyboard.add(types.InlineKeyboardButton(
            "A'zo bo'lish", 
            url=channel_url
        ))
    
    keyboard.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_subscription"))
    
    bot.edit_message_text(
        text, user_id, call.message.message_id,
        reply_markup=keyboard
    )

def show_subscription_required_inline(query, channels):
    user_id = query.from_user.id
    
    # Majburiy va ixtiyoriy kanallarni ajratib olish
    mandatory_channels = [ch for ch in channels]  # channels faqat majburiy kanallar
    optional_channels = get_optional_channels()   # ixtiyoriy kanallarni alohida olamiz
    
    text = "📢 Botdan foydalanish uchun kanallarga obuna bo'ling va botni qayta ishga tushiring."
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Barcha majburiy kanallar
    all_channels = mandatory_channels + optional_channels
    
    for channel in all_channels:
        channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
        
        # Kanal linkini olish
        if channel_db_id:  # Agar channel_id bo'lsa (Telegram kanali)
            channel_url = get_channel_url(channel_db_id)
            if not channel_url:
                channel_url = channel_link
        else:
            channel_url = channel_link
        
        # Tugma matni faqat "A'zo bo'lish"
        keyboard.add(types.InlineKeyboardButton(
            "A'zo bo'lish", 
            url=channel_url
        ))
    
    result = types.InlineQueryResultArticle(
        id='subscription_required',
        title="❌ Obuna talabi",
        description="Botdan foydalish uchun kanallarga obuna bo'ling",
        input_message_content=types.InputTextMessageContent(
            message_text=text
        ),
        reply_markup=keyboard
    )
    
    bot.answer_inline_query(query.id, [result], cache_time=1)

def get_mandatory_channels():
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, channel_link, channel_id, channel_username, is_mandatory FROM channels WHERE is_mandatory = TRUE")
        channels = cursor.fetchall()
        return channels
    except Error as e:
        logger.error(f"Error getting channels: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def get_optional_channels():
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, channel_link, channel_id, channel_username, is_mandatory FROM channels WHERE is_mandatory = FALSE")
        channels = cursor.fetchall()
        return channels
    except Error as e:
        logger.error(f"Error getting optional channels: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

def get_all_channels():
    """Barcha kanallarni olish"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, channel_link, channel_id, channel_username, is_mandatory FROM channels")
        channels = cursor.fetchall()
        return channels
    except Error as e:
        logger.error(f"Error getting all channels: {e}")
        return []
    finally:
        cursor.close()
        connection.close()
def add_channel(channel_link: str, channel_username: str, channel_id: int, is_mandatory: bool, added_by: int):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO channels (channel_link, channel_username, channel_id, is_mandatory, added_by) VALUES (%s, %s, %s, %s, %s)",
            (channel_link, channel_username, channel_id, is_mandatory, added_by)
        )
        connection.commit()
        return True
    except Error as e:
        logger.error(f"Error adding channel: {e}")
        return False
    finally:
        cursor.close()
        connection.close()

def delete_channel(channel_id: int):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM channels WHERE id = %s", (channel_id,))
        connection.commit()
        return True
    except Error as e:
        logger.error(f"Error deleting channel: {e}")
        return False
    finally:
        cursor.close()
        connection.close()


# MySQL connection funksiyasi
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"MySQL connection error: {e}")
        return None

# User ma'lumotlarini saqlash
def save_user(user_id: int, username: str):
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT IGNORE INTO users (id, username) VALUES (%s, %s)",
            (user_id, username)
        )
        connection.commit()
    except Error as e:
        logger.error(f"Error saving user: {e}")
    finally:
        cursor.close()
        connection.close()

# Asosiy menyu
def main_menu(user_id: int):
    keyboard = types.InlineKeyboardMarkup()
    
    buttons = [
        types.InlineKeyboardButton("🔍 Nom orqali qidirish", switch_inline_query_current_chat=""),
    ]
    
    if user_id in ADMIN_IDS:
        buttons.append(types.InlineKeyboardButton("👨‍💻 Admin Panel", callback_data="admin_panel"))
    
    for button in buttons:
        keyboard.add(button)
    
    return keyboard

# Admin paneli
def admin_panel():
    keyboard = types.InlineKeyboardMarkup()
    
    buttons = [
        types.InlineKeyboardButton("🎬 Kino qo'shish", callback_data="add_movie"),
        types.InlineKeyboardButton("🗑️ Kino o'chirish", callback_data="delete_movie"),
        types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Xabar yuborish", callback_data="broadcast"),
        types.InlineKeyboardButton("👥 Majburiy obuna", callback_data="force_subscribe"),
        types.InlineKeyboardButton("🔙 Orqaga", callback_data="main_menu")
    ]
    
    for button in buttons:
        keyboard.add(button)
    
    return keyboard

def channels_management_panel():
    keyboard = types.InlineKeyboardMarkup()
    
    buttons = [
        types.InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel"),
        types.InlineKeyboardButton("➖ Kanal o'chirish", callback_data="delete_channel"),
        types.InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="channels_list"),
        types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_panel")
    ]
    
    for button in buttons:
        keyboard.add(button)
    
    return keyboard

def get_channel_url(channel_db_id):
    """Kanal ID bo'yicha taklif havolasini olish"""
    try:
        chat = bot.get_chat(channel_db_id)
        
        # Private kanal uchun taklif havolasini yaratish
        if str(chat.id).startswith('-100'):
            # Private kanal - taklif havolasini yaratish
            try:
                invite_link = chat.invite_link
                if not invite_link:
                    # Agar taklif havolasi bo'lmasa, yangi yaratish
                    invite_link = bot.create_chat_invite_link(
                        chat.id, 
                        member_limit=1,
                        creates_join_request=False
                    ).invite_link
                return invite_link
            except Exception as e:
                logger.error(f"Create invite link error: {e}")
                # Agar taklif havolasi yarata olmasa, public kanal uchun format qaytaramiz
                return f"https://t.me/c/{str(chat.id)[4:]}"
        else:
            # Public kanal
            if chat.username:
                return f"https://t.me/{chat.username}"
            else:
                # Agar username bo'lmasa, taklif havolasini yaratish
                try:
                    invite_link = chat.invite_link
                    if not invite_link:
                        invite_link = bot.create_chat_invite_link(
                            chat.id, 
                            member_limit=1,
                            creates_join_request=False
                        ).invite_link
                    return invite_link
                except Exception as e:
                    logger.error(f"Create invite link error: {e}")
                    # Inline query uchun default URL qaytaramiz
                    return "https://t.me"
                    
    except Exception as e:
        logger.error(f"Get channel URL error: {e}")
        # Inline query uchun default URL qaytaramiz
        return "https://t.me"

def is_valid_url(url):
    """URL ning to'g'ri ekanligini tekshirish"""
    try:
        # Oddiy URL formatini tekshirish
        if url.startswith(('https://', 'http://', 'tg://')):
            return True
        return False
    except:
        return False

def get_safe_channel_url(channel_db_id):
    """Xavfsiz kanal URL ni olish (agar noto'g'ri bo'lsa, default URL qaytaradi)"""
    url = get_channel_url(channel_db_id)
    if is_valid_url(url):
        return url
    else:
        logger.warning(f"Invalid URL generated: {url}, using default URL")
        return "https://t.me"

# Janrlarni olish
def get_genres():
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id, name FROM genres ORDER BY name")
        genres = cursor.fetchall()
        return genres
    except Error as e:
        logger.error(f"Error getting genres: {e}")
        return []
    finally:
        cursor.close()
        connection.close()

# Janr tanlash menyusi
def genre_selection_menu(selected_genres: List[int] = None, page: int = 0):
    if selected_genres is None:
        selected_genres = []
    
    genres = get_genres()
    
    if not genres:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation"))
        return keyboard
    
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    
    items_per_page = 9
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_genres = genres[start_idx:end_idx]
    
    for genre_id, genre_name in page_genres:
        emoji = "✅" if genre_id in selected_genres else "⚪"
        callback_data = f"genre_{genre_id}"
        keyboard.add(types.InlineKeyboardButton(
            f"{emoji} {genre_name}", 
            callback_data=callback_data
        ))
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅️ Oldingi", callback_data=f"genre_page_{page-1}"))
    
    if end_idx < len(genres):
        nav_buttons.append(types.InlineKeyboardButton("Keyingi ➡️", callback_data=f"genre_page_{page+1}"))
    
    if nav_buttons:
        if len(nav_buttons) == 2:
            keyboard.add(nav_buttons[0], nav_buttons[1])
        else:
            keyboard.add(nav_buttons[0])
    
    action_buttons = []
    if selected_genres:
        action_buttons.append(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_genres"))
    
    action_buttons.append(types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation"))
    
    if len(action_buttons) == 2:
        keyboard.add(action_buttons[0], action_buttons[1])
    else:
        keyboard.add(action_buttons[0])
    
    return keyboard

# Sifat tanlash menyusi
def quality_selection_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    qualities = [
        ("1080p", "quality_1080"),
        ("720p", "quality_720"),
        ("480p", "quality_480")
    ]
    
    for quality, callback_data in qualities:
        keyboard.add(types.InlineKeyboardButton(quality, callback_data=callback_data))
    
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_genres"))
    return keyboard

@bot.message_handler(commands=['start'])
@anti_spam
@check_user_registered
@check_subscription
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    save_user(user_id, username)
    
    # Deep link parametrlarini tekshirish (faqat kanal ID sini olish uchun)
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith('channel_'):
            channel_id = param.replace('channel_', '')
            # Kanal ma'lumotlarini ko'rsatish
            try:
                channel_id_int = int(channel_id)
                chat = bot.get_chat(channel_id_int)
                if chat.username:
                    channel_url = f"https://t.me/{chat.username}"
                else:
                    channel_url = f"https://t.me/c/{str(chat.id)[4:]}" if str(chat.id).startswith('-100') else f"tg://resolve?domain={chat.id}"
                
                bot.send_message(
                    user_id,
                    f"🔗 Kanal havolasi:\n\n"
                    f"📝 Kanal: {chat.title}\n"
                    f"🔗 Link: {channel_url}\n\n"
                    f"Kanalga obuna bo'lish uchun yuqoridagi linkni bosing yoki kanal nomini qidiring.",
                    reply_markup=types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton("🔰 Kanalga o'tish", url=channel_url)
                    )
                )
            except Exception as e:
                logger.error(f"Channel deep link error: {e}")
                bot.send_message(user_id, "❌ Kanal topilmadi!")
            return
    
    welcome_text = (
        "🎬 Kino botiga xush kelibsiz!\n\n"
        "Quyidagi tugmalardan foydalanishingiz mumkin:"
    )
    
    bot.send_message(user_id, welcome_text, reply_markup=main_menu(user_id))

@bot.message_handler(commands=['ad'])
@anti_spam
def admin_command(message):
    user_id = message.from_user.id
    
    if user_id in ADMIN_IDS:
        bot.send_message(user_id, "👨‍💻 Admin Panel", reply_markup=admin_panel())
    else:
        bot.send_message(user_id, "❌ Sizda admin huquqlari mavjud emas!")
@bot.message_handler(func=lambda message: True, content_types=['text', 'video', 'document', 'animation', 'video_note'])
@anti_spam
@check_user_registered
@check_subscription
def handle_all_messages(message):
    """Barcha xabarlarni qayta ishlash"""
    user_id = message.from_user.id
    
    # Adminlar uchun sessiya tekshiruvi
    if user_id in user_sessions:
        session = user_sessions[user_id]
        
        # Forward qilingan media uchun
        if session.get('waiting_for_movie_forward'):
            # Forward qilinganligini tekshirish
            if not message.forward_date:
                bot.send_message(
                    user_id,
                    "❌ Iltimos, videoni forward qiling! Oddiy xabar emas.\n\n"
                    "Boshqa kanaldan yoki chatdan videoli xabarni botga forward qiling."
                )
                return
            
            # Video yoki media borligini tekshirish
            if message.video or message.document or message.animation or message.video_note:
                handle_movie_forward(message, session)
            else:
                content_type = message.content_type
                bot.send_message(
                    user_id,
                    f"❌ Forward qilingan xabarda video topilmadi! ({content_type})\n\n"
                    f"Iltimos, video faylni forward qiling."
                )
            return
        
        # Matnli xabarlar uchun
        elif session.get('waiting_for_movie_title') and message.text:
            handle_movie_title(message, session)
            return
            
        elif session.get('waiting_for_broadcast') and message.text:
            handle_broadcast(message, session)
            return
            
        elif session.get('waiting_for_delete_movie') and message.text and message.text.isdigit():
            handle_delete_movie(message, session)
            return
            
        elif session.get('waiting_for_channel_link') and message.text:
            handle_channel_link(message, session)
            return
            
        elif session.get('waiting_for_channel_id') and message.text and message.text.lstrip('-').isdigit():
            handle_channel_id(message, session)
            return
    
    # Hech qanday sessiya yo'q yoki sessiya mos kelmadi
    if message.text and not message.text.startswith('/'):
        # Matnli xabar - qidiruv
        handle_search(message)
    elif message.content_type != 'text':
        # Media xabar lekin sessiya yo'q
        bot.send_message(user_id, "❌ Kino qidirish uchun matn kiriting yoki /start ni bosing.")
def handle_search(message):
    user_id = message.from_user.id
    search_text = message.text.strip()
    
    if not search_text:
        return
    
    connection = get_db_connection()
    if not connection:
        bot.send_message(user_id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        
        if search_text.isdigit():
            cursor.execute("""
                SELECT m.id, m.title, m.quality, m.channel_message_id, m.file_id,
                       GROUP_CONCAT(g.name SEPARATOR ', ') as genres
                FROM movies m
                LEFT JOIN movie_genres mg ON m.id = mg.movie_id
                LEFT JOIN genres g ON mg.genre_id = g.id
                WHERE m.id = %s
                GROUP BY m.id
            """, (int(search_text),))
        else:
            cursor.execute("""
                SELECT m.id, m.title, m.quality, m.channel_message_id, m.file_id,
                       GROUP_CONCAT(g.name SEPARATOR ', ') as genres
                FROM movies m
                LEFT JOIN movie_genres mg ON m.id = mg.movie_id
                LEFT JOIN genres g ON mg.genre_id = g.id
                WHERE m.title LIKE %s
                GROUP BY m.id
                LIMIT 10
            """, (f'%{search_text}%',))
        
        movies = cursor.fetchall()
        
        if not movies:
            bot.send_message(user_id, "❌ Hech qanday kino topilmadi!")
            return
        
        for movie in movies:
            movie_id, title, quality, channel_message_id, file_id, genres = movie
            
            movie_info = (
                f"🎬 <b>{title}</b>\n"
                f"🆔 ID: <code>{movie_id}</code>\n"
                f"📊 Sifat: {quality}\n"
                f"🎭 Janrlar: {genres if genres else 'Noma''lum'}\n"
            )
            
            # Kino faylini forward qilish
            if file_id:
                try:
                    # Video yoki document forward qilish
                    bot.send_video(user_id, file_id, caption=movie_info, parse_mode='HTML')
                except:
                    try:
                        bot.send_document(user_id, file_id, caption=movie_info, parse_mode='HTML')
                    except:
                        bot.send_message(user_id, f"{movie_info}\n❌ Kinoni yuborib bo'lmadi", parse_mode='HTML')
            elif channel_message_id:
                try:
                    # Kanaldagi xabarni forward qilish
                    bot.forward_message(user_id, ADMIN_CHANNEL_ID, channel_message_id)
                    bot.send_message(user_id, movie_info, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"Forward error: {e}")
                    bot.send_message(user_id, f"{movie_info}\n❌ Kinoni topib bo'lmadi", parse_mode='HTML')
            else:
                bot.send_message(user_id, movie_info, parse_mode='HTML')
                
    except Error as e:
        logger.error(f"Search error: {e}")
        bot.send_message(user_id, "❌ Qidirishda xatolik yuz berdi!")
    finally:
        cursor.close()
        connection.close()

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
@anti_spam
@check_subscription_callback
def handle_callback_query(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    try:
        # 🎬 Asosiy menyu
        if call.data == "main_menu":
            bot.edit_message_text(
                "🎬 Asosiy menyu",
                user_id, message_id,
                reply_markup=main_menu(user_id)
            )
        
        # 👨‍💻 Admin panel
        elif call.data == "admin_panel":
            if user_id in ADMIN_IDS:
                bot.edit_message_text(
                    "👨‍💻 Admin Panel",
                    user_id, message_id,
                    reply_markup=admin_panel()
                )
            else:
                bot.answer_callback_query(call.id, "❌ Sizda admin huquqlari mavjud emas!")
        
        # ➕ Kino qo‘shish
        elif call.data == "add_movie":
            if user_id in ADMIN_IDS:
                start_add_movie(user_id, message_id)
            else:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        

        
        elif call.data.startswith("genre_page_"):
            handle_genre_pagination(call)




        
        elif call.data == "back_to_genres":
            handle_back_to_genres(call)

        # ❌ Amalni bekor qilish
        elif call.data == "cancel_operation":
            handle_cancel_operation(call)

        # 📢 Broadcast
        elif call.data == "broadcast":
            if user_id in ADMIN_IDS:
                start_broadcast(user_id, message_id)

        # 🗑 Kino o‘chirish
        elif call.data == "delete_movie":
            if user_id in ADMIN_IDS:
                start_delete_movie(user_id, message_id)

        # 📈 Admin statistikasi
        elif call.data == "admin_stats":
            if user_id in ADMIN_IDS:
                show_admin_stats(user_id, message_id)

        # 👤 Foydalanuvchi statistikasi
        elif call.data == "stats":
            show_user_stats(user_id, message_id)

        # 🎬 Kino yuborish
        elif call.data.startswith("send_movie_"):
            handle_send_movie(call)

        # 📢 Majburiy obuna boshqaruvi
        elif call.data == "force_subscribe":
            if user_id in ADMIN_IDS:
                show_channels_management(user_id, message_id)

        elif call.data == "add_channel":
            if user_id in ADMIN_IDS:
                start_add_channel(user_id, message_id)

        elif call.data == "delete_channel":
            if user_id in ADMIN_IDS:
                start_delete_channel(user_id, message_id)

        elif call.data == "channels_list":
            if user_id in ADMIN_IDS:
                show_channels_list(user_id, message_id)

        elif call.data.startswith("channel_type_"):
            handle_channel_type_selection(call)

        elif call.data.startswith("confirm_channel_"):
            handle_confirm_channel(call)

        elif call.data.startswith("cancel_channel_"):
            handle_cancel_channel(call)

        elif call.data.startswith("delete_channel_"):
            handle_delete_channel_confirmation(call)

        elif call.data.startswith("confirm_delete_"):
            handle_confirm_delete_channel(call)

        elif call.data == "check_subscription":
            handle_check_subscription(call)
        # Callback query handler ichiga qo'shamiz:
        elif call.data.startswith("add_method_"):
            handle_add_method_selection(call)
        elif call.data.startswith("genre_"):
            handle_genre_selection_callback(call)
    
        # Janrlarni tasdiqlash
        elif call.data == "confirm_genres":
            handle_confirm_genres_callback(call)
        
        # Janr tanlashni bekor qilish
        elif call.data == "cancel_genres":
            handle_cancel_genres_callback(call)
        
        # Sifat tanlash
        elif call.data.startswith("quality_"):
            handle_quality_selection_callback(call)

    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")







def show_admin_stats(user_id: int, message_id: int):
    connection = get_db_connection()
    if not connection:
        bot.answer_callback_query(call.id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM movies")
        total_movies = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT genre_id) FROM movie_genres")
        used_genres = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM genres")
        total_genres = cursor.fetchone()[0]
        
        # Oxirgi 24 soatda qo'shilgan foydalanuvchilar
        cursor.execute("SELECT COUNT(*) FROM users WHERE registered_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)")
        new_users_24h = cursor.fetchone()[0]
        
        # Oxirgi 24 soatda qo'shilgan kinolar
        cursor.execute("SELECT COUNT(*) FROM movies WHERE added_at >= DATE_SUB(NOW(), INTERVAL 1 DAY)")
        new_movies_24h = cursor.fetchone()[0]
        
        stats_text = (
            "📊 Admin Statistika\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"🎬 Jami kinolar: {total_movies}\n"
            f"🎭 Foydalanilgan janrlar: {used_genres}/{total_genres}\n\n"
            f"📈 Oxirgi 24 soat:\n"
            f"• Yangi foydalanuvchilar: {new_users_24h}\n"
            f"• Yangi kinolar: {new_movies_24h}"
        )
        
        bot.edit_message_text(
            stats_text, user_id, message_id,
            reply_markup=admin_panel()
        )
        
    except Error as e:
        logger.error(f"Admin stats error: {e}")
        bot.answer_callback_query(call.id, "❌ Statistika olishda xatolik!")
    finally:
        cursor.close()
        connection.close()

def show_channels_management(user_id: int, message_id: int):
    text = "👥 Majburiy obuna boshqaruvi\n\nQuyidagi amallardan birini tanlang:"
    bot.edit_message_text(text, user_id, message_id, reply_markup=channels_management_panel())

def start_add_channel(user_id: int, message_id: int):
    user_sessions[user_id] = {
        'operation': 'add_channel',
        'waiting_for_channel_type': True
    }
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🔰 Majburiy kanal", callback_data="channel_type_mandatory"),
        types.InlineKeyboardButton("📱 Ixtiyoriy kanal", callback_data="channel_type_optional")
    )
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="force_subscribe"))
    
    bot.edit_message_text(
        "📋 Kanal turini tanlang:",
        user_id, message_id,
        reply_markup=keyboard
    )

def handle_channel_type_selection(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_channel':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    
    if call.data == "channel_type_mandatory":
        session['is_mandatory'] = True
        session['waiting_for_channel_type'] = False
        
        # Kanal qo'shish usulini so'rash
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("🔗 Link orqali", callback_data="add_method_link"),
            types.InlineKeyboardButton("🆔 ID orqali", callback_data="add_method_id")
        )
        keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="add_channel"))
        
        bot.edit_message_text(
            "🔰 Majburiy kanal qo'shish\n\n"
            "Kanal qo'shish usulini tanlang:",
            user_id, message_id,
            reply_markup=keyboard
        )
    
    elif call.data == "channel_type_optional":
        session['is_mandatory'] = False
        session['waiting_for_channel_type'] = False
        session['waiting_for_channel_link'] = True
        
        bot.edit_message_text(
            "📱 Ixtiyoriy kanal qo'shish\n\n"
            "Kanal yoki sahifaning to'liq linkini yuboring:\n"
            "Masalan: https://t.me/kanal_nomi yoki https://instagram.com/sahifa_nomi",
            user_id, message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Orqaga", callback_data="add_channel")
            )
        )
    
    bot.answer_callback_query(call.id)

def handle_add_method_selection(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_channel':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    
    if call.data == "add_method_link":
        session['waiting_for_channel_link'] = True
        session['add_method'] = 'link'
        
        bot.edit_message_text(
            "🔰 Majburiy kanal qo'shish (Link)\n\n"
            "Kanalning to'liq linkini yuboring:\n"
            "Masalan: https://t.me/kanal_nomi\n\n"
            "⚠️ Eslatma: Bot kanalda admin bo'lishi kerak!",
            user_id, message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
            )
        )
    
    elif call.data == "add_method_id":
        session['waiting_for_channel_id'] = True
        session['add_method'] = 'id'
        
        bot.edit_message_text(
            "🔰 Majburiy kanal qo'shish (ID)\n\n"
            "Kanal ID sini yuboring:\n"
            "Masalan: -1001234567890\n\n"
            "⚠️ Eslatma: Bot kanalda admin bo'lishi kerak!",
            user_id, message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
            )
        )
    
    bot.answer_callback_query(call.id)

def handle_channel_link(message, session):
    user_id = message.from_user.id
    channel_link = message.text.strip()
    
    # Link formatini tekshirish
    if not (channel_link.startswith('https://t.me/') or channel_link.startswith('https://instagram.com/') or 
            channel_link.startswith('https://www.instagram.com/') or channel_link.startswith('https://youtube.com/') or
            channel_link.startswith('https://www.youtube.com/')):
        bot.send_message(user_id, "❌ Noto'g'ri link formati! Iltimos, to'g'ri link yuboring.")
        return
    
    session['channel_link'] = channel_link
    session['waiting_for_channel_link'] = False
    
    if session['is_mandatory'] and session.get('add_method') == 'link':
        # Majburiy kanal uchun bot adminligini tekshirish
        try:
            # Kanal username ni olish
            if channel_link.startswith('https://t.me/'):
                channel_username = channel_link.replace('https://t.me/', '')
                
                # Kanal ma'lumotlarini olish
                chat = bot.get_chat(f"@{channel_username}")
                session['channel_username'] = f"@{channel_username}"
                session['channel_id'] = chat.id
                
                # Bot kanalda admin ekanligini tekshirish
                bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
                if bot_member.status not in ['administrator', 'creator']:
                    bot.send_message(
                        user_id,
                        f"❌ Bot kanalda admin emas!\n\n"
                        f"Kanal: {chat.title}\n"
                        f"Botni kanalga admin qiling va keyin qayta urinib ko'ring.",
                        reply_markup=types.InlineKeyboardMarkup().add(
                            types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
                        )
                    )
                    return
                
                # Tasdiqlash uchun yuborish
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_channel_{chat.id}"),
                    types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_channel_{chat.id}")
                )
                
                bot.send_message(
                    user_id,
                    f"🔰 Kanal ma'lumotlari:\n\n"
                    f"📝 Nomi: {chat.title}\n"
                    f"🔗 Username: @{channel_username}\n"
                    f"🆔 ID: {chat.id}\n"
                    f"📊 Turi: Majburiy\n\n"
                    f"Kanalni qo'shishni tasdiqlaysizmi?",
                    reply_markup=keyboard
                )
                
            else:
                # Telegram bo'lmagan kanallar uchun
                session['channel_username'] = channel_link
                session['channel_id'] = None
                
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_channel_optional"),
                    types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_channel_optional")
                )
                
                bot.send_message(
                    user_id,
                    f"📱 Kanal ma'lumotlari:\n\n"
                    f"🔗 Link: {channel_link}\n"
                    f"📊 Turi: Ixtiyoriy\n\n"
                    f"Kanalni qo'shishni tasdiqlaysizmi?",
                    reply_markup=keyboard
                )
                
        except Exception as e:
            logger.error(f"Channel check error: {e}")
            bot.send_message(
                user_id,
                f"❌ Kanalni tekshirishda xatolik: {e}\n\n"
                f"Kanal mavjudligini va bot admin ekanligini tekshiring.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
                )
            )
    else:
        # Ixtiyoriy kanal yoki ID orqali qo'shish
        session['channel_username'] = channel_link
        session['channel_id'] = None
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_channel_optional"),
            types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_channel_optional")
        )
        
        bot.send_message(
            user_id,
            f"📱 Kanal ma'lumotlari:\n\n"
            f"🔗 Link: {channel_link}\n"
            f"📊 Turi: Ixtiyoriy\n\n"
            f"Kanalni qo'shishni tasdiqlaysizmi?",
            reply_markup=keyboard
        )

def handle_channel_id(message, session):
    user_id = message.from_user.id
    channel_id_text = message.text.strip()
    
    # ID formatini tekshirish
    try:
        channel_id = int(channel_id_text)
    except ValueError:
        bot.send_message(user_id, "❌ Noto'g'ri ID formati! Iltimos, faqat raqam kiriting.")
        return
    
    session['channel_id'] = channel_id
    session['waiting_for_channel_id'] = False
    
    try:
        # Kanal ma'lumotlarini olish
        chat = bot.get_chat(channel_id)
        session['channel_username'] = f"@{chat.username}" if chat.username else chat.title
        session['channel_link'] = f"https://t.me/{chat.username}" if chat.username else f"ID: {channel_id}"
        
        # Bot kanalda admin ekanligini tekshirish
        bot_member = bot.get_chat_member(channel_id, bot.get_me().id)
        if bot_member.status not in ['administrator', 'creator']:
            bot.send_message(
                user_id,
                f"❌ Bot kanalda admin emas!\n\n"
                f"Kanal: {chat.title}\n"
                f"Botni kanalga admin qiling va keyin qayta urinib ko'ring.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
                )
            )
            return
        
        # Tasdiqlash uchun yuborish
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_channel_{channel_id}"),
            types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_channel_{channel_id}")
        )
        
        bot.send_message(
            user_id,
            f"🔰 Kanal ma'lumotlari:\n\n"
            f"📝 Nomi: {chat.title}\n"
            f"🔗 Username: {f'@{chat.username}' if chat.username else 'Yo''q'}\n"
            f"🆔 ID: {channel_id}\n"
            f"📊 Turi: Majburiy\n\n"
            f"Kanalni qo'shishni tasdiqlaysizmi?",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Channel ID check error: {e}")
        bot.send_message(
            user_id,
            f"❌ Kanalni tekshirishda xatolik: {e}\n\n"
            f"Kanal ID sini va bot admin ekanligini tekshiring.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Orqaga", callback_data="cancel_operation")
            )
        )

def handle_confirm_channel(call):
    user_id = call.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_channel':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    
    try:
        if call.data == "confirm_channel_optional":
            # Ixtiyoriy kanal
            success = add_channel(
                session['channel_link'],
                session['channel_username'],
                None,
                session['is_mandatory'],
                user_id
            )
        else:
            # Majburiy kanal
            channel_id = int(call.data.split('_')[2])
            success = add_channel(
                session['channel_link'],
                session['channel_username'],
                channel_id,
                session['is_mandatory'],
                user_id
            )
        
        if success:
            # Kanal ma'lumotlarini olish va taklif havolasini yaratish
            channel_info = ""
            if session.get('channel_id'):
                try:
                    chat = bot.get_chat(session['channel_id'])
                    channel_url = get_channel_url(session['channel_id'])
                    if channel_url:
                        channel_info = f"\n🔗 Taklif havolasi: {channel_url}"
                    else:
                        channel_info = f"\n⚠️ Taklif havolasi yaratilmadi. Kanal sozlamalarini tekshiring."
                except Exception as e:
                    logger.error(f"Channel info error: {e}")
                    channel_info = f"\n🔗 Kanal linki: {session['channel_link']}"
            
            bot.edit_message_text(
                f"✅ Kanal muvaffaqiyatli qo'shildi!{channel_info}",
                user_id, call.message.message_id
            )
            # Sessionni tozalash
            del user_sessions[user_id]
            
            # Kanallar boshqaruv paneliga qaytish
            bot.send_message(user_id, "👥 Majburiy obuna boshqaruvi", reply_markup=channels_management_panel())
        else:
            bot.edit_message_text(
                "❌ Kanal qo'shishda xatolik!",
                user_id, call.message.message_id
            )
    
    except Exception as e:
        logger.error(f"Confirm channel error: {e}")
        bot.edit_message_text(
            "❌ Kanal qo'shishda xatolik!",
            user_id, call.message.message_id
        )
    
    bot.answer_callback_query(call.id)

def handle_cancel_channel(call):
    user_id = call.from_user.id
    
    if user_id in user_sessions and user_sessions[user_id].get('operation') == 'add_channel':
        del user_sessions[user_id]
    
    bot.edit_message_text(
        "❌ Kanal qo'shish bekor qilindi!",
        user_id, call.message.message_id
    )
    bot.send_message(user_id, "👥 Majburiy obuna boshqaruvi", reply_markup=channels_management_panel())
    bot.answer_callback_query(call.id)

def start_delete_channel(user_id: int, message_id: int):
    channels = get_all_channels()  # Barcha kanallarni olish
    
    if not channels:
        bot.edit_message_text(
            "❌ Hozircha kanallar mavjud emas!",
            user_id, message_id,
            reply_markup=channels_management_panel()
        )
        return
    
    keyboard = types.InlineKeyboardMarkup()
    
    for channel in channels:
        channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
        channel_type = "🔰" if is_mandatory else "📱"
        display_name = channel_username or channel_link
        # Display name ni qisqartirish
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
        keyboard.add(types.InlineKeyboardButton(
            f"{channel_type} {display_name}",
            callback_data=f"delete_channel_{channel_id}"
        ))
    
    keyboard.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="force_subscribe"))
    
    bot.edit_message_text(
        "🗑️ O'chirmoqchi bo'lgan kanalni tanlang:",
        user_id, message_id,
        reply_markup=keyboard
    )

def handle_delete_channel_confirmation(call):
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[2])
    
    # Kanal ma'lumotlarini olish
    connection = get_db_connection()
    if not connection:
        bot.answer_callback_query(call.id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT channel_link, channel_username, is_mandatory FROM channels WHERE id = %s", (channel_id,))
        channel = cursor.fetchone()
        
        if not channel:
            bot.answer_callback_query(call.id, "❌ Kanal topilmadi!")
            return
        
        channel_link, channel_username, is_mandatory = channel
        channel_type = "Majburiy" if is_mandatory else "Ixtiyoriy"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"confirm_delete_{channel_id}"),
            types.InlineKeyboardButton("❌ Yo'q", callback_data="force_subscribe")
        )
        
        bot.edit_message_text(
            f"🗑️ Kanalni o'chirish\n\n"
            f"🔗 Link: {channel_link}\n"
            f"📝 Username: {channel_username or 'Mavjud emas'}\n"
            f"📊 Turi: {channel_type}\n\n"
            f"Rostan ham bu kanalni o'chirmoqchimisiz?",
            user_id, call.message.message_id,
            reply_markup=keyboard
        )
        
    except Error as e:
        logger.error(f"Delete channel error: {e}")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")
    finally:
        cursor.close()
        connection.close()
    
    bot.answer_callback_query(call.id)

def handle_confirm_delete_channel(call):
    user_id = call.from_user.id
    channel_id = int(call.data.split('_')[2])
    
    success = delete_channel(channel_id)
    
    if success:
        bot.edit_message_text(
            "✅ Kanal muvaffaqiyatli o'chirildi!",
            user_id, call.message.message_id
        )
    else:
        bot.edit_message_text(
            "❌ Kanal o'chirishda xatolik!",
            user_id, call.message.message_id
        )
    
    bot.send_message(user_id, "👥 Majburiy obuna boshqaruvi", reply_markup=channels_management_panel())
    bot.answer_callback_query(call.id)
def show_channels_list(user_id: int, message_id: int):
    mandatory_channels = get_mandatory_channels()
    optional_channels = get_optional_channels()
    
    text = "📋 Kanallar ro'yxati\n\n"
    
    if mandatory_channels:
        text += "🔰 Majburiy kanallar:\n"
        for i, channel in enumerate(mandatory_channels, 1):
            channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
            
            # Kanal linkini olish
            if channel_db_id:
                channel_url = get_channel_url(channel_db_id)
                if not channel_url:
                    channel_url = "❌ Taklif havolasi mavjud emas"
            else:
                channel_url = channel_link
            
            text += f"{i}. {channel_username or channel_link}\n   🔗 {channel_url}\n"
        text += "\n"
    
    if optional_channels:
        text += "📱 Ixtiyoriy kanallar:\n"
        for i, channel in enumerate(optional_channels, 1):
            channel_id, channel_link, channel_db_id, channel_username, is_mandatory = channel
            text += f"{i}. {channel_username or channel_link}\n   🔗 {channel_link}\n"
    
    if not mandatory_channels and not optional_channels:
        text += "❌ Hozircha kanallar mavjud emas!"
    
    bot.edit_message_text(
        text, user_id, message_id,
        reply_markup=channels_management_panel()
    )
def handle_check_subscription(call):
    user_id = call.from_user.id
    
    # Majburiy kanallarni tekshirish
    mandatory_channels = get_mandatory_channels()
    
    if not mandatory_channels:
        bot.answer_callback_query(call.id, "✅ Siz botdan foydalanish huquqiga egasiz!", show_alert=True)
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "🎬 Asosiy menyu", reply_markup=main_menu(user_id))
        return
    
    # Foydalanuvchi barcha kanallarga obuna bo'lganligini tekshirish
    not_subscribed = []
    for channel in mandatory_channels:
        channel_id = channel[2]  # channel_id (3-element)
        if channel_id:
            try:
                chat_member = bot.get_chat_member(channel_id, user_id)
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    not_subscribed.append(channel)
            except Exception as e:
                logger.error(f"Channel check error: {e}")
                not_subscribed.append(channel)
    
    if not_subscribed:
        bot.answer_callback_query(
            call.id, 
            "❌ Hali barcha kanallarga obuna bo'lmagansiz! Iltimos, barcha kanallarga obuna bo'ling.", 
            show_alert=True
        )
    else:
        bot.answer_callback_query(call.id, "✅ Tabriklaymiz! Siz botdan foydalanish huquqiga egasiz!", show_alert=True)
        bot.delete_message(user_id, call.message.message_id)
        bot.send_message(user_id, "🎬 Asosiy menyu", reply_markup=main_menu(user_id))

def start_broadcast(user_id: int, message_id: int):
    user_sessions[user_id] = {
        'operation': 'broadcast',
        'waiting_for_broadcast': True
    }
    
    bot.edit_message_text(
        "📢 Xabar yuborish\n\nYubormoqchi bo'lgan xabaringizni kiriting:",
        user_id, message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
        )
    )

def handle_broadcast(message, session):
    user_id = message.from_user.id
    broadcast_text = message.text
    
    connection = get_db_connection()
    if not connection:
        bot.send_message(user_id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()
        
        sent_count = 0
        failed_count = 0
        
        # Birinchi navbatda admin ga test xabar
        bot.send_message(user_id, f"📢 Xabar yuborish boshlandi...\n\n{broadcast_text}")
        
        for user in users:
            try:
                bot.send_message(user[0], f"{broadcast_text}")
                sent_count += 1
                time.sleep(0.1)  # Spamdan saqlanish uchun
            except:
                failed_count += 1
                continue
        
        result_text = (
            f"✅ Xabar yuborish yakunlandi!\n\n"
            f"✅ Muvaffaqiyatli: {sent_count}\n"
            f"❌ Muvaffaqiyatsiz: {failed_count}\n"
            f"📊 Jami: {sent_count + failed_count}"
        )
        
        bot.send_message(user_id, result_text, reply_markup=admin_panel())
        
        # Sessionni tozalash
        del user_sessions[user_id]
        
    except Error as e:
        logger.error(f"Broadcast error: {e}")
        bot.send_message(user_id, "❌ Xabar yuborishda xatolik!")
    finally:
        cursor.close()
        connection.close()

def start_delete_movie(user_id: int, message_id: int):
    user_sessions[user_id] = {
        'operation': 'delete_movie',
        'waiting_for_delete_movie': True
    }
    
    bot.edit_message_text(
        "🗑️ Kino o'chirish\n\nO'chirmoqchi bo'lgan kino ID sini kiriting:",
        user_id, message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
        )
    )

def handle_delete_movie(message, session):
    user_id = message.from_user.id
    movie_id = message.text.strip()
    
    if not movie_id.isdigit():
        bot.send_message(user_id, "❌ Iltimos, faqat raqam kiriting!")
        return
    
    connection = get_db_connection()
    if not connection:
        bot.send_message(user_id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        
        # Kino mavjudligini tekshirish
        cursor.execute("SELECT title FROM movies WHERE id = %s", (int(movie_id),))
        movie = cursor.fetchone()
        
        if not movie:
            bot.send_message(user_id, "❌ Bunday ID li kino topilmadi!")
            return
        
        # Kinoni o'chirish
        cursor.execute("DELETE FROM movies WHERE id = %s", (int(movie_id),))
        connection.commit()
        
        bot.send_message(
            user_id, 
            f"✅ '{movie[0]}' kinosi muvaffaqiyatli o'chirildi!",
            reply_markup=admin_panel()
        )
        
        # Sessionni tozalash
        del user_sessions[user_id]
        
    except Error as e:
        logger.error(f"Delete movie error: {e}")
        bot.send_message(user_id, "❌ Kino o'chirishda xatolik!")
    finally:
        cursor.close()
        connection.close()
        

# Inline query handler
# Inline query handler
@bot.inline_handler(func=lambda query: True)
@anti_spam
@check_subscription_inline
def handle_inline_query(query):
    user_id = query.from_user.id
    search_text = query.query.strip()
    
    logger.info(f"Inline query: '{search_text}' from user {user_id}")
    
    try:
        connection = get_db_connection()
        if not connection:
            return
        
        cursor = connection.cursor()
        
        if search_text:
            # Matn bo'yicha qidirish
            cursor.execute("""
                SELECT m.id, m.title, m.quality, m.file_id, m.channel_message_id,
                       GROUP_CONCAT(g.name SEPARATOR ', ') as genres
                FROM movies m
                LEFT JOIN movie_genres mg ON m.id = mg.movie_id
                LEFT JOIN genres g ON mg.genre_id = g.id
                WHERE m.title LIKE %s
                GROUP BY m.id
                ORDER BY 
                    CASE 
                        WHEN m.title LIKE %s THEN 1
                        WHEN m.title LIKE %s THEN 2
                        ELSE 3
                    END,
                    m.title
                LIMIT 20
            """, (f'%{search_text}%', f'{search_text}%', f'%{search_text}'))
        else:
            # Bo'sh qidirish - oxirgi qo'shilgan kinolar
            cursor.execute("""
                SELECT m.id, m.title, m.quality, m.file_id, m.channel_message_id,
                       GROUP_CONCAT(g.name SEPARATOR ', ') as genres
                FROM movies m
                LEFT JOIN movie_genres mg ON m.id = mg.movie_id
                LEFT JOIN genres g ON mg.genre_id = g.id
                GROUP BY m.id
                ORDER BY m.added_at DESC
                LIMIT 20
            """)
        
        movies = cursor.fetchall()
        
        results = []
        
        if not movies:
            # Agar kino topilmasa
            no_results_msg = types.InlineQueryResultArticle(
                id='0',
                title="❌ Hech qanday kino topilmadi",
                description="Boshqa kalit so'zlar bilan qidirib ko'ring",
                input_message_content=types.InputTextMessageContent(
                    message_text="❌ Hech qanday kino topilmadi. Boshqa kalit so'zlar bilan qidirib ko'ring."
                )
            )
            results.append(no_results_msg)
        else:
            for movie in movies:
                movie_id, title, quality, file_id, channel_message_id, genres = movie
                
                # Qisqacha tavsif
                description_parts = []
                if quality:
                    description_parts.append(f"Sifat: {quality}")
                if genres:
                    # Janrlarni qisqartirish
                    genre_list = genres.split(', ')
                    short_genres = ', '.join(genre_list[:2]) + ('...' if len(genre_list) > 2 else '')
                    description_parts.append(f"Janr: {short_genres}")
                
                description = ' | '.join(description_parts) if description_parts else "Ma'lumot yo'q"
                
                # Kino ma'lumotlari
                movie_info = (
                    f"🎬 <b>{title}</b>\n"
                    f"🆔 ID: <code>{movie_id}</code>\n"
                    f"📊 Sifat: {quality}\n"
                    f"🎭 Janrlar: {genres if genres else 'Noma''lum'}\n\n"
                    f"✅ Kino avtomatik ravishda yuborildi!"
                )
                
                # Thumbnail uchun
                thumbnail_url = "https://via.placeholder.com/100/0088cc/FFFFFF?text=🎬"
                
                # Kino yuborish uchun input message content
                if file_id:
                    # Agar file_id bo'lsa, videoni yuboramiz
                    try:
                        # Video fayl turini aniqlash
                        result = types.InlineQueryResultCachedVideo(
                            id=str(movie_id),
                            video_file_id=file_id,
                            title=title,
                            description=description,
                            caption=movie_info,
                            parse_mode='HTML'
                        )
                    except:
                        # Agar video bo'lmasa, document sifatida
                        result = types.InlineQueryResultCachedDocument(
                            id=str(movie_id),
                            document_file_id=file_id,
                            title=title,
                            description=description,
                            caption=movie_info,
                            parse_mode='HTML'
                        )
                else:
                    # Agar file_id bo'lmasa, oddiy xabar
                    result = types.InlineQueryResultArticle(
                        id=str(movie_id),
                        title=title,
                        description=description,
                        thumbnail_url=thumbnail_url,
                        input_message_content=types.InputTextMessageContent(
                            message_text=movie_info,
                            parse_mode='HTML'
                        )
                    )
                
                results.append(result)
        
        bot.answer_inline_query(query.id, results, cache_time=1)
        
    except Exception as e:
        logger.error(f"Inline query error: {e}")
        # Xato holatida bo'sh natija qaytarish
        error_result = types.InlineQueryResultArticle(
            id='error',
            title="❌ Xatolik yuz berdi",
            description="Qaytadan urinib ko'ring",
            input_message_content=types.InputTextMessageContent(
                message_text="❌ Qidirishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring."
            )
        )
        bot.answer_inline_query(query.id, [error_result], cache_time=1)
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()

# Kino uchun keyboard yaratish
def create_movie_keyboard(movie_id: int, file_id: str = None):
    keyboard = types.InlineKeyboardMarkup()
    
    # Kino yuborish tugmasi
    if file_id:
        keyboard.add(types.InlineKeyboardButton("🎬 Kino yuborish", callback_data=f"send_movie_{movie_id}"))
    
    # Qidirish tugmasi
    keyboard.add(types.InlineKeyboardButton("🔍 Boshqa kino qidirish", switch_inline_query_current_chat=""))
    
    return keyboard

# Kino qo'shish funksiyalari
def start_add_movie(user_id: int, message_id: int):
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    user_sessions[user_id] = {
        'operation': 'add_movie',
        'selected_genres': [],
        'current_genre_page': 0,
        'waiting_for_movie_title': True
    }
    
    bot.edit_message_text(
        "🎬 Kino qo'shish\n\nIltimos, kino nomini kiriting:",
        user_id, message_id,
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
        )
    )

def handle_movie_title(message, session):
    user_id = message.from_user.id
    session['movie_title'] = message.text
    session['waiting_for_movie_title'] = False
    
    bot.send_message(
        user_id,
        "🎭 Kino janrlarini tanlang:",
        reply_markup=genre_selection_menu(session['selected_genres'], session['current_genre_page'])
    )
def handle_movie_forward(message, session):
    """Forward qilingan kinoni qayta ishlash"""
    user_id = message.from_user.id
    
    # Log qo'shamiz
    logger.info(f"handle_movie_forward called for user {user_id}")
    logger.info(f"Message content type: {message.content_type}")
    logger.info(f"Forward date: {message.forward_date}")
    logger.info(f"From chat ID: {message.forward_from_chat.id if message.forward_from_chat else 'N/A'}")
    logger.info(f"From message ID: {message.forward_from_message_id if message.forward_from_message_id else 'N/A'}")
    
    # Forward qilingan xabarni tekshirish
    if not message.forward_date:
        logger.warning(f"Message is not a forward from user {user_id}")
        bot.send_message(
            user_id, 
            "❌ Iltimos, kino videosini forward qiling! Oddiy xabar emas.\n\n"
            "Kino videosi bo'lgan xabarni boshqa kanaldan yoki chatdan botga forward qiling.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
            )
        )
        return
    
    # Videoni tekshirish
    file_id = None
    file_type = None
    
    if message.video:
        file_id = message.video.file_id
        file_type = 'video'
        logger.info(f"Video found with file_id: {file_id}")
        logger.info(f"Video details: {message.video.__dict__}")
    elif message.document:
        # Document ichida video bo'lishi mumkin
        file_id = message.document.file_id
        file_type = 'document'
        logger.info(f"Document found with file_id: {file_id}")
        logger.info(f"Document mime_type: {message.document.mime_type}")
        logger.info(f"Document details: {message.document.__dict__}")
    elif message.animation:
        file_id = message.animation.file_id
        file_type = 'animation'
        logger.info(f"Animation found with file_id: {file_id}")
    elif message.video_note:
        file_id = message.video_note.file_id
        file_type = 'video_note'
        logger.info(f"Video note found with file_id: {file_id}")
    else:
        logger.warning(f"No video/media found in forwarded message from user {user_id}")
        
        # Xabarda nima borligini log qilamiz
        content_types = []
        if message.photo:
            content_types.append('photo')
        if message.audio:
            content_types.append('audio')
        if message.voice:
            content_types.append('voice')
        if message.sticker:
            content_types.append('sticker')
        if message.text:
            content_types.append('text')
        
        logger.warning(f"Message contains: {', '.join(content_types)}")
        
        bot.send_message(
            user_id,
            f"❌ Forward qilingan xabarda video topilmadi! (Topilgan: {', '.join(content_types)})\n\n"
            f"Iltimos, video faylni forward qiling.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
            )
        )
        return
    
    # Forward qilingan xabardan kanal ma'lumotlarini saqlash
    channel_info = ""
    if message.forward_from_chat:
        chat = message.forward_from_chat
        channel_info = f"\n📢 Kanal: {chat.title}\n📨 Xabar ID: {message.forward_from_message_id}"
    
    # Kino ma'lumotlarini bazaga saqlash
    connection = get_db_connection()
    if not connection:
        logger.error(f"Database connection failed for user {user_id}")
        bot.send_message(user_id, "❌ Bazaga ulanishda xatolik!")
        return
    
    try:
        cursor = connection.cursor()
        
        # Kino ma'lumotlarini saqlash
        cursor.execute(
            "INSERT INTO movies (title, quality, file_id, added_by) VALUES (%s, %s, %s, %s)",
            (session['movie_title'], session['quality'], file_id, user_id)
        )
        movie_id = cursor.lastrowid
        logger.info(f"Movie saved with ID: {movie_id}")
        
        # Janr ma'lumotlarini saqlash
        for genre_id in session['selected_genres']:
            cursor.execute(
                "INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)",
                (movie_id, genre_id)
            )
            logger.info(f"Genre {genre_id} linked to movie {movie_id}")
        
        connection.commit()
        logger.info(f"Transaction committed for movie {movie_id}")
        
        # Foydalanuvchiga xabar
        success_text = (
            f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
            f"📝 Nomi: {session['movie_title']}\n"
            f"🆔 ID: <code>{movie_id}</code>\n"
            f"📊 Sifat: {session['quality']}\n"
            f"📁 File turi: {file_type}\n"
            f"📁 File ID: <code>{file_id}</code>{channel_info}\n\n"
            f"Endi foydalanuvchilar bu kinoni inline query orqali topishlari mumkin."
        )
        
        # Forward qilingan xabarni o'chirish
        try:
            bot.delete_message(user_id, message.message_id)
            logger.info(f"Forwarded message deleted for user {user_id}")
        except Exception as e:
            logger.warning(f"Could not delete message: {e}")
        
        bot.send_message(user_id, success_text, parse_mode='HTML', reply_markup=admin_panel())
        
        # Sessionni tozalash
        del user_sessions[user_id]
        logger.info(f"Session cleared for user {user_id}")
        
    except Error as e:
        logger.error(f"Error saving movie: {e}")
        if connection:
            connection.rollback()
        bot.send_message(
            user_id, 
            "❌ Kino saqlashda xatolik! Iltimos, qaytadan urinib ko'ring.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Admin panel", callback_data="admin_panel")
            )
        )
    finally:
        if 'cursor' in locals():
            cursor.close()
        if connection:
            connection.close()

def handle_genre_selection(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_movie':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    genre_id = int(call.data.split('_')[1])
    current_page = session.get('current_genre_page', 0)
    
    if genre_id in session['selected_genres']:
        session['selected_genres'].remove(genre_id)
    else:
        session['selected_genres'].append(genre_id)
    
    bot.edit_message_reply_markup(
        user_id, message_id,
        reply_markup=genre_selection_menu(session['selected_genres'], current_page)
    )
    bot.answer_callback_query(call.id)

def handle_genre_pagination(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_movie':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    new_page = int(call.data.split('_')[2])
    session['current_genre_page'] = new_page
    
    bot.edit_message_reply_markup(
        user_id, message_id,
        reply_markup=genre_selection_menu(session['selected_genres'], new_page)
    )
    bot.answer_callback_query(call.id)

def handle_confirm_genres(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_movie':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    
    if not session['selected_genres']:
        bot.answer_callback_query(call.id, "❌ Kamida bitta janr tanlang!")
        return
    
    bot.edit_message_text(
        "📊 Kino sifatini tanlang:",
        user_id, message_id,
        reply_markup=quality_selection_menu()
    )
def handle_quality_selection(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_movie':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    quality = call.data.split('_')[1]
    session['quality'] = quality
    logger.info(f"User {user_id} selected quality: {quality}")
    
    # Endi forward qilishni so'rash
    session['waiting_for_movie_forward'] = True
    
    # Avvalgi xabarni o'chirish
    bot.delete_message(user_id, message_id)
    
    # Yangi xabar yuborish
    bot.send_message(
        user_id,
        "📁 <b>Kino videosini botga forward qiling:</b>\n\n"
        "1. Istagan kanaldan yoki chatdan kinoli xabarni toping\n"
        "2. Shu xabarni botga <b>FORWARD</b> qiling (oddiy xabar emas, forward)\n"
        "3. Bot video faylni qabul qilib, ma'lumotlarni saqlaydi.\n\n"
        "⚠️ <b>Muhim:</b>\n"
        "• Video fayl bo'lishi kerak (video, document, animation)\n"
        "• Xabar forward qilingan bo'lishi shart\n"
        "• Video yuborilayotganda botga tushadi va saqlanadi",
        parse_mode='HTML',
        reply_markup=types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔙 Bekor qilish", callback_data="cancel_operation")
        )
    )
    bot.answer_callback_query(call.id)

# Janr tugmalarini yaratish funksiyasi
def create_genres_keyboard(selected_genres=None):
    """Janrlarni tugmalar ko'rinishida qaytaradi"""
    if selected_genres is None:
        selected_genres = []
    
    genres = get_genres()
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    for genre_id, genre_name in genres:
        # Agar janr tanlangan bo'lsa, ✅ belgisi qo'yiladi
        prefix = "✅ " if genre_id in selected_genres else ""
        callback_data = f"genre_{genre_id}"
        buttons.append(types.InlineKeyboardButton(
            f"{prefix}{genre_name}", 
            callback_data=callback_data
        ))
    
    # Tugmalarni 3 qatordan qilib joylashtirish
    keyboard.add(*buttons)
    
    # Tasdiqlash va bekor qilish tugmalari
    keyboard.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_genres"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_genres")
    )
    
    return keyboard

# Kino qo'shish boshlanganda janr tanlashni ko'rsatish
def start_add_movie_genres(user_id: int, message_id: int):
    """Kino qo'shishda janr tanlashni boshlash"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['selected_genres'] = []
    user_sessions[user_id]['adding_movie'] = True
    
    keyboard = create_genres_keyboard([])
    
    bot.edit_message_text(
        "🎬 Kino qo'shish - Janr tanlash\n\n"
        "Kinoning janrlarini tanlang (bir nechta tanlashingiz mumkin):",
        user_id, message_id,
        reply_markup=keyboard
    )

# Janr tanlash callback handler
def handle_genre_selection_callback(call):
    """Janr tanlash tugmasi bosilganda ishlaydi"""
    user_id = call.from_user.id
    genre_id = int(call.data.split('_')[1])
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {'selected_genres': []}
    
    if 'selected_genres' not in user_sessions[user_id]:
        user_sessions[user_id]['selected_genres'] = []
    
    selected = user_sessions[user_id]['selected_genres']
    
    # Janrni tanlash yoki olib tashlash
    if genre_id in selected:
        selected.remove(genre_id)
    else:
        selected.append(genre_id)
    
    # Tugmalarni yangilash
    keyboard = create_genres_keyboard(selected)
    bot.edit_message_reply_markup(
        user_id, 
        call.message.message_id,
        reply_markup=keyboard
    )
    
    bot.answer_callback_query(call.id)

# Janrlarni tasdiqlash
def handle_confirm_genres_callback(call):
    """Tanlangan janrlarni tasdiqlash"""
    user_id = call.from_user.id
    
    if user_id not in user_sessions or 'selected_genres' not in user_sessions[user_id]:
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return
    
    selected = user_sessions[user_id]['selected_genres']
    
    if not selected:
        bot.answer_callback_query(call.id, "❌ Kamida bitta janr tanlang!")
        return
    
    # Janrlarni nomlarini olish
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            placeholders = ','.join(['%s'] * len(selected))
            cursor.execute(f"SELECT name FROM genres WHERE id IN ({placeholders})", selected)
            genre_names = [row[0] for row in cursor.fetchall()]
            
            # Tanlangan janrlarni xabarda ko'rsatish
            genres_text = ", ".join(genre_names)
            
            # Keyingi bosqichga o'tish (masalan, sifat tanlash)
            user_sessions[user_id]['step'] = 'quality'
            
            # Sifat tanlash menyusini ko'rsatish
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            qualities = [
                ("1080p", "quality_1080"),
                ("720p", "quality_720"),
                ("480p", "quality_480")
            ]
            for quality, callback in qualities:
                keyboard.add(types.InlineKeyboardButton(quality, callback_data=callback))
            
            bot.edit_message_text(
                f"✅ Tanlangan janrlar: {genres_text}\n\n"
                f"Endi kino sifatini tanlang:",
                user_id, call.message.message_id,
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"Error getting genre names: {e}")
            bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi!")
        finally:
            cursor.close()
            connection.close()

# Janr tanlashni bekor qilish
def handle_cancel_genres_callback(call):
    """Janr tanlashni bekor qilish"""
    user_id = call.from_user.id
    
    if user_id in user_sessions:
        if 'selected_genres' in user_sessions[user_id]:
            del user_sessions[user_id]['selected_genres']
        if 'adding_movie' in user_sessions[user_id]:
            del user_sessions[user_id]['adding_movie']
    
    bot.edit_message_text(
        "❌ Kino qo'shish bekor qilindi.",
        user_id, call.message.message_id,
        reply_markup=admin_panel() if user_id in ADMIN_IDS else main_menu(user_id)
    )
    
    bot.answer_callback_query(call.id)

# Sifat tanlash callback handler
def handle_quality_selection_callback(call):
    """Sifat tanlanganda ishlaydi"""
    user_id = call.from_user.id
    quality = call.data.split('_')[1]
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['quality'] = quality
    
    bot.edit_message_text(
        f"✅ Sifat tanlandi: {quality}p\n\n"
        f"Endi kino videosini yuboring yoki forward qiling:",
        user_id, call.message.message_id
    )
    
    # Bu yerda kino video qabul qilish bosqichiga o'tish
    user_sessions[user_id]['step'] = 'waiting_video'
    
    bot.answer_callback_query(call.id)
    
def handle_channel_message_id(message, session):
    user_id = message.from_user.id
    message_id_text = message.text.strip()
    
    if not message_id_text.isdigit():
        bot.send_message(user_id, "❌ Iltimos, faqat raqam kiriting!")
        return
    
    channel_message_id = int(message_id_text)
    
    # Kanaldagi xabarni o'zimizga forward qilib file_id ni olamiz
    try:
        forwarded_msg = bot.forward_message(user_id, ADMIN_CHANNEL_ID, channel_message_id)
        
        # File_id ni olish
        file_id = None
        if forwarded_msg.video:
            file_id = forwarded_msg.video.file_id
        elif forwarded_msg.document:
            file_id = forwarded_msg.document.file_id
        elif forwarded_msg.audio:
            file_id = forwarded_msg.audio.file_id
        
        # Kino ma'lumotlarini bazaga saqlash
        connection = get_db_connection()
        if not connection:
            bot.send_message(user_id, "❌ Bazaga ulanishda xatolik!")
            return
        
        try:
            cursor = connection.cursor()
            
            # Kino ma'lumotlarini saqlash
            cursor.execute(
                "INSERT INTO movies (title, quality, channel_message_id, file_id, added_by) VALUES (%s, %s, %s, %s, %s)",
                (session['movie_title'], session['quality'], channel_message_id, file_id, user_id)
            )
            movie_id = cursor.lastrowid
            
            # Janr ma'lumotlarini saqlash
            for genre_id in session['selected_genres']:
                cursor.execute(
                    "INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)",
                    (movie_id, genre_id)
                )
            
            connection.commit()
            
            # Foydalanuvchiga xabar
            success_text = (
                f"✅ Kino muvaffaqiyatli qo'shildi!\n\n"
                f"📝 Nomi: {session['movie_title']}\n"
                f"🆔 ID: <code>{movie_id}</code>\n"
                f"📊 Sifat: {session['quality']}\n"
                f"📋 Kanal ID: {channel_message_id}\n"
                f"📁 File ID: {file_id if file_id else 'Mavjud emas'}\n\n"
                f"Endi foydalanuvchilar bu kinoni inline query orqali topishlari mumkin."
            )
            
            bot.send_message(user_id, success_text, parse_mode='HTML', reply_markup=admin_panel())
            
            # Sessionni tozalash
            del user_sessions[user_id]
            
        except Error as e:
            logger.error(f"Error saving movie: {e}")
            bot.send_message(user_id, "❌ Kino saqlashda xatolik!")
        finally:
            cursor.close()
            connection.close()
            
    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        bot.send_message(user_id, "❌ Kanaldagi xabarni topib bo'lmadi! ID ni tekshiring.")

# Orqaga qaytish funksiyalari
def handle_back_to_genres(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id not in user_sessions or user_sessions[user_id].get('operation') != 'add_movie':
        bot.answer_callback_query(call.id, "❌ Sessiya muddati tugagan!")
        return
    
    session = user_sessions[user_id]
    
    bot.edit_message_text(
        "🎭 Kino janrlarini tanlang:",
        user_id, message_id,
        reply_markup=genre_selection_menu(session['selected_genres'], session['current_genre_page'])
    )
    bot.answer_callback_query(call.id)

def handle_cancel_operation(call):
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if user_id in ADMIN_IDS:
        bot.edit_message_text(
            "👨‍💻 Admin Panel",
            user_id, message_id,
            reply_markup=admin_panel()
        )
    else:
        bot.edit_message_text(
            "🎬 Asosiy menyu",
            user_id, message_id,
            reply_markup=main_menu(user_id)
        )
    
    bot.answer_callback_query(call.id)



# Botni ishga tushirish
if __name__ == "__main__":
    logger.info("Bot ishga tushdi...")
    
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot error: {e}")