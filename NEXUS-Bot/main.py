import os
import json
import logging
import time
import asyncio
from datetime import date, datetime
from functools import wraps
from telegram import (
    Update, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton 
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, 
    ConversationHandler,
    JobQueue
)
from threading import Thread

# Telethon imports
from telethon import TelegramClient
from telethon.sessions import StringSession 
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PeerFloodError

# Flask app import
from app import run_flask_app

# --- Configuration and Global State (Keep this the same) ---

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_IDS = [int(x.strip()) for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip().isdigit()] 
USER_DATA_FILE = 'user_data.json'
MAX_DAILY_MESSAGES = 150       
PREMIUM_DAILY_MESSAGES = 1500  
USER_DATA = {}                 

GET_PHONE, GET_OTP, GET_PASSWORD = range(3) 
clients = {} 
JOB_KEY = 'campaign_job'
SPAMMING_ACTIVE = False 

AD_DATA = {
    'ad_message': "Welcome to our new service! Click here to learn more.",
    'interval_seconds': 20,         
    'cycle_interval_seconds': 3600, 
    'sessions': [] 
}

# --- Inline Keyboard Generation (Keep this the same) ---

def get_main_keyboard():
    """Generates the main Inline Keyboard layout."""
    keyboard = [
        [InlineKeyboardButton("🔗 Integrate API Session", callback_data='add_session')],
        [
            InlineKeyboardButton("📝 Set Ad Content", callback_data='set_ad_btn'),
            InlineKeyboardButton("⏱ Set Group Delay", callback_data='set_interval_btn')
        ],
        [
            InlineKeyboardButton("🔄 Set Cycle Delay", callback_data='set_ctimer_btn'),
            InlineKeyboardButton("🗑 Clear All Sessions", callback_data='clear_sessions')
        ],
        [
            InlineKeyboardButton("▶️ Start Campaign", callback_data='start_campaign'),
            InlineKeyboardButton("⏹ Stop Campaign", callback_data='stop_campaign')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Utility Functions (Keep this the same) ---

def load_user_data():
    """Loads user data from a JSON file."""
    global USER_DATA
    try:
        with open(USER_DATA_FILE, 'r') as f:
            USER_DATA = json.load(f)
        logging.info(f"Loaded user data for {len(USER_DATA)} users.")
    except FileNotFoundError:
        USER_DATA = {}
    except Exception as e:
        logging.error(f"Failed to load user data: {e}")
        USER_DATA = {}

def save_user_data():
    """Saves user data to a JSON file."""
    try:
        with open(USER_DATA_FILE, 'w') as f:
            json.dump(USER_DATA, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save user data: {e}")

def get_user_status(user_id):
    """Retrieves user data and resets daily counters if a new day."""
    user_id_str = str(user_id)
    today = date.today().isoformat()
    
    status = USER_DATA.setdefault(user_id_str, {
        'is_banned': False,
        'is_premium': False,
        'messages_today': 0,
        'last_reset_day': today
    })
    
    if status['last_reset_day'] != today:
        status['messages_today'] = 0
        status['last_reset_day'] = today
        save_user_data()

    return status

def update_sessions_file():
    """Rewrites the entire sessions.json file with the current AD_DATA['sessions'] list."""
    try:
        with open('sessions.json', 'w') as f:
            for session_string in AD_DATA['sessions']:
                f.write(session_string + '\n')
        logging.info("Sessions file updated successfully.")
    except Exception as e:
        logging.error(f"Failed to write sessions file: {e}")

def save_session_string(session_string: str):
    """Adds a new session string and updates the file."""
    if session_string not in AD_DATA['sessions']:
        AD_DATA['sessions'].append(session_string)
        update_sessions_file()
        logging.info("New session string integrated successfully.")

# --- Admin Decorator (Keep this the same) ---

def is_admin_check(func):
    """Decorator to check if the user executing the command is an admin."""
    @wraps(func)
    async def wrapper(update: Update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Access Denied. This command is for administrators only.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# --- Handler Utilities for Inline Buttons (Keep this the same) ---

async def add_session_callback(update: Update, context) -> int:
    """Entry point for session integration via inline button."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "➡️ Please enter the phone number (e.g., +1234567890) of the account you wish to integrate for API access.",
        reply_markup=None
    )

    return GET_PHONE 

async def handle_button_press(update: Update, context):
    """Routes inline button presses to the appropriate function and ensures the menu is shown once."""
    query = update.callback_query
    await query.answer() 

    chat_id = query.message.chat_id
    data = query.data

    await query.edit_message_text(f"Action '{data}' selected. Please wait or proceed with the required input...", reply_markup=None)

    if data == 'set_ad_btn':
        await set_ad(update, context)
    elif data == 'set_interval_btn':
        await set_interval(update, context)
    elif data == 'set_ctimer_btn':
        await set_cycle_interval(update, context)
    elif data == 'start_campaign':
        await start_spam(update, context)
    elif data == 'stop_campaign':
        await stop_spam(update, context)
    elif data == 'clear_sessions':
        await clear_my_sessions(update, context)

    await context.bot.send_message(chat_id, "Please select the next action:", reply_markup=get_main_keyboard())

# --- Conversation Handlers (Keep this the same) ---

async def start_command(update: Update, context) -> int:
    """Greets the user and shows the main menu with Inline Buttons."""
    await update.message.reply_text(
        "👋 Welcome to the Nexus API Client. Select an action below to manage your campaign:",
        parse_mode=None,
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def stop_command(update: Update, context) -> None:
    """Handles the /stop command by calling stop_spam."""
    await stop_spam(update, context, called_by_command=True)

async def help_command(update: Update, context) -> None:
    """Provides a list of commands and user status."""
    user_id = update.effective_user.id
    status = get_user_status(user_id)
    
    help_text = (
        "🤖 Nexus Client Help\n\n"
        "General Commands:\n"
        "/start - Show the main menu.\n"
        "/stop - Immediately halt the bulk messaging campaign.\n"
        "/setad <message> - Set the advertisement content.\n"
        "/setinterval <seconds> - Set the Group Delay (between different chats, min 5s).\n"
        "/setctimer <seconds> - Set the Cycle Delay (between full campaign blasts, min 60s).\n"
    )

    if user_id in ADMIN_IDS:
        help_text += (
            "\n🛡️ Admin Commands:\n"
            "/broadcast <message> - Send a message through all integrated sessions (experimental).\n"
            "/ban <user_id> - Ban a user from using the campaign feature.\n"
            "/unban <user_id> - Unban a user.\n"
            "/setpremium <user_id> true|false - Set a user's premium status.\n"
        )
    
    user_status_line = "\nCurrent Status:\n"
    user_status_line += f"• Account Status: {'✨ Premium' if status['is_premium'] else 'Standard'}\n"
    user_status_line += f"• Messages Today: {status['messages_today']}\n"
    
    if status['is_premium'] or user_id in ADMIN_IDS:
        limit = PREMIUM_DAILY_MESSAGES if status['is_premium'] else MAX_DAILY_MESSAGES
        user_status_line += f"• Daily Limit: {limit} messages per day\n"
        
    user_status_line += f"• Banned: {'🚫 Yes' if status['is_banned'] else '🟢 No'}"

    help_text += user_status_line

    await update.message.reply_text(help_text, parse_mode=None)


async def phone_received(update: Update, context) -> int:
    """Initializes the Telethon client and sends the login code."""
    chat_id = update.effective_chat.id
    phone_number = update.message.text.strip()

    try:
        API_ID = int(os.environ.get('API_ID'))
        API_HASH = os.environ.get('API_HASH')
    except (TypeError, ValueError):
        await update.message.reply_text("❌ ERROR: API credentials are missing or invalid in environment variables. Please contact support.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    client = None
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone_number)

        context.user_data['phone_number'] = phone_number
        clients[chat_id] = client 

        await update.message.reply_text("✅ Success! A login code has been sent to that account. Please enter the code here now.")

        return GET_OTP

    except Exception:
        await update.message.reply_text(f"❌ Integration Failed: Error sending code. Please check the number and try again.", reply_markup=get_main_keyboard())
        if client:
            try:
                await client.disconnect()
            except:
                pass
        return ConversationHandler.END

async def otp_received(update: Update, context) -> int:
    """Uses the OTP to sign in, extracts the session string, and handles 2FA."""
    chat_id = update.effective_chat.id
    otp_code = update.message.text.strip()
    
    client = clients.get(chat_id) 
    phone_number = context.user_data.get('phone_number')

    if not client or not phone_number:
        await update.message.reply_text("❌ Error: Integration data lost. Please start over.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    try:
        await client.sign_in(phone_number, otp_code)
        
        session_string = client.session.save()
        save_session_string(session_string)
        
        await client.disconnect()
        del clients[chat_id]
        
        await update.message.reply_text(
            "🎉 Session Integrated Successfully! The account is ready for use in your campaigns.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )
        return ConversationHandler.END 
        
    except SessionPasswordNeededError:
        await update.message.reply_text("🔑 Two-Factor Authentication required. Please enter your account password now.")
        return GET_PASSWORD
        
    except Exception:
        await update.message.reply_text(f"❌ Authentication FAILED. Code was incorrect or an error occurred. Please start again.", reply_markup=get_main_keyboard())
        await client.disconnect()
        if chat_id in clients:
            del clients[chat_id]
        return ConversationHandler.END

async def password_received(update: Update, context) -> int:
    """Completes sign-in using the 2FA password."""
    chat_id = update.effective_chat.id
    password = update.message.text.strip()
    
    client = clients.get(chat_id) 

    if not client:
        await update.message.reply_text("❌ Error: Integration data lost during password phase. Please start over.", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    try:
        await client.sign_in(password=password)
        
        session_string = client.session.save()
        save_session_string(session_string)
        
        await client.disconnect()
        del clients[chat_id]
        
        await update.message.reply_text(
            "🎉 2FA Authentication Successful! The session is fully integrated.",
            reply_markup=get_main_keyboard(),
            parse_mode=None
        )
        return ConversationHandler.END
        
    except FloodWaitError as e:
        await update.message.reply_text(f"🛑 Authentication Failed: You are rate-limited by Telegram for {e.seconds} seconds. Please wait and try again.", reply_markup=get_main_keyboard())
        await client.disconnect()
        if chat_id in clients:
            del clients[chat_id]
        return ConversationHandler.END

    except Exception:
        await update.message.reply_text(f"❌ Password FAILED. The 2FA password was incorrect or an error occurred. Please try the code and password process again.", reply_markup=get_main_keyboard())
        await client.disconnect()
        if chat_id in clients:
            del clients[chat_id]
        return ConversationHandler.END

# --- Ad and Interval Setters (Keep this the same) ---

async def set_ad(update: Update, context) -> None:
    """Sets the ad message."""
    message_source = update.effective_message 

    if context.args and len(context.args) > 0:
        new_ad = " ".join(context.args)
        AD_DATA['ad_message'] = new_ad
        await message_source.reply_text(f"✅ Ad Content updated successfully. New message: {new_ad}", parse_mode=None)

    else: 
        await message_source.reply_text(
            f"📝 Current Ad Content: {AD_DATA['ad_message']}\n"
            f"To change, please use the command: /setad <your new ad message>", parse_mode=None
        )


async def set_interval(update: Update, context) -> None:
    """Sets the delay interval between messages to DIFFERENT groups (Group Timer)."""
    message_source = update.effective_message

    if context.args and len(context.args) > 0:
        try:
            new_interval = int(context.args[0])
            if new_interval < 5:
                 new_interval = 5
                 await message_source.reply_text("⚠️ Minimum delay enforced. Setting Group Delay to 5 seconds.")
            AD_DATA['interval_seconds'] = new_interval
            await message_source.reply_text(f"✅ Group Delay (Inter-Group Delay) set to {new_interval} seconds.", parse_mode=None)
        except ValueError:
            await message_source.reply_text("❌ Invalid input. Please enter a whole number in seconds.")

    else: 
        await message_source.reply_text(
            f"⏱ Current Group Delay: {AD_DATA['interval_seconds']} seconds.\n"
            f"To change, please use the command: /setinterval <seconds>", parse_mode=None
        )

async def set_cycle_interval(update: Update, context) -> None:
    """Sets the delay interval between full campaign cycles (Cycle Timer)."""
    message_source = update.effective_message

    if context.args and len(context.args) > 0:
        try:
            new_interval = int(context.args[0])
            if new_interval < 60:
                 new_interval = 60
                 await message_source.reply_text("⚠️ Minimum cycle timer enforced. Setting Cycle Delay to 60 seconds.")
            AD_DATA['cycle_interval_seconds'] = new_interval

            if SPAMMING_ACTIVE:
                current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)
                for job in current_jobs:
                    job.schedule_removal()
                context.application.job_queue.run_repeating(
                    run_spam_job, 
                    interval=new_interval, 
                    first=1,
                    name=JOB_KEY,
                    data={'chat_id': message_source.chat_id, 'user_id': message_source.from_user.id}
                )
                await message_source.reply_text(f"✅ Cycle Delay set to {new_interval} seconds. Campaign job rescheduled immediately with new interval.", parse_mode=None)
            else:
                await message_source.reply_text(f"✅ Cycle Delay (Delay between cycles) set to {new_interval} seconds.", parse_mode=None)

        except ValueError:
            await message_source.reply_text("❌ Invalid input. Please enter a whole number in seconds.")

    else: 
        await message_source.reply_text(
            f"🔄 Current Cycle Delay: {AD_DATA['cycle_interval_seconds']} seconds.\n"
            f"To change, please use the command: /setctimer <seconds>", parse_mode=None
        )


async def clear_my_sessions(update: Update, context) -> None:
    """Clears all sessions associated with this bot for data security."""
    global AD_DATA
    message_source = update.effective_message

    if not AD_DATA['sessions']:
        await message_source.reply_text("⚠️ No sessions are currently integrated to clear.")
        return

    count = len(AD_DATA['sessions'])
    AD_DATA['sessions'] = [] 
    update_sessions_file() 

    await message_source.reply_text(f"🗑️ Success! All {count} integrated API sessions have been permanently cleared from storage.", parse_mode=None)


# --- Admin Commands (Keep this the same) ---

@is_admin_check
async def admin_broadcast(update: Update, context) -> None:
    """Admin command to send a message through all integrated sessions to all chats."""
    try:
        API_ID = int(os.environ.get('API_ID'))
        API_HASH = os.environ.get('API_HASH')
    except (TypeError, ValueError):
        await update.message.reply_text("❌ ERROR: API credentials are missing for broadcast.", parse_mode=None)
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message_to_send = " ".join(context.args)
    chat_id = update.effective_chat.id
    
    if not AD_DATA['sessions']:
        await update.message.reply_text("⚠️ No integrated sessions found to broadcast from.")
        return
        
    await update.message.reply_text(f"➡️ Initiating broadcast across {len(AD_DATA['sessions'])} sessions. Message: {message_to_send[:30]}...", parse_mode=None)

    total_sessions = 0
    total_messages = 0

    for session_string in AD_DATA['sessions']:
        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.start()
            
            result = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=1000, hash=0))
            chats = result.chats
            
            for chat in chats:
                if hasattr(chat, 'broadcast') or hasattr(chat, 'megagroup'):
                    try:
                        await client.send_message(chat, message_to_send)
                        total_messages += 1
                        await asyncio.sleep(1) 
                    except Exception:
                        pass 
                        
            await client.disconnect()
            total_sessions += 1

        except Exception as e:
            logging.error(f"Broadcast failed for session {session_string[:10]}...: {e}")
            
    await context.bot.send_message(chat_id, 
        f"✅ Broadcast Complete!\n\n"
        f"Sessions Used: {total_sessions} / {len(AD_DATA['sessions'])}\n"
        f"Total Messages Sent: {total_messages}", parse_mode=None
    )


@is_admin_check
async def ban_user(update: Update, context) -> None:
    """Admin command to ban a user ID."""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /ban <user_id> (User ID must be a number).")
        return
    
    user_id_str = context.args[0]
    status = get_user_status(user_id_str)
    status['is_banned'] = True
    save_user_data()
    
    await update.message.reply_text(f"🚫 User ID {user_id_str} has been BANNED.", parse_mode=None)

@is_admin_check
async def unban_user(update: Update, context) -> None:
    """Admin command to unban a user ID."""
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /unban <user_id> (User ID must be a number).")
        return
    
    user_id_str = context.args[0]
    status = get_user_status(user_id_str)
    status['is_banned'] = False
    save_user_data()
    
    await update.message.reply_text(f"🟢 User ID {user_id_str} has been UNBANNED.", parse_mode=None)


@is_admin_check
async def set_premium(update: Update, context) -> None:
    """Admin command to set a user's premium status."""
    if len(context.args) < 2 or not context.args[0].isdigit() or context.args[1].lower() not in ['true', 'false']:
        await update.message.reply_text("Usage: /setpremium <user_id> true|false.")
        return
    
    user_id_str = context.args[0]
    status_bool = context.args[1].lower() == 'true'
    
    status = get_user_status(user_id_str)
    status['is_premium'] = status_bool
    save_user_data()
    
    status_emoji = '✨' if status_bool else '⭐'
    await update.message.reply_text(f"{status_emoji} User ID {user_id_str} premium status set to {status_bool}.", parse_mode=None)


# --- Campaign Handlers (Keep this the same) ---

async def start_spam(update: Update, context) -> None:
    """Initiates the bulk messaging campaign as a repeating job."""
    global SPAMMING_ACTIVE
    message_source = update.effective_message
    control_user_id = update.effective_user.id

    if SPAMMING_ACTIVE:
        await message_source.reply_text("⚠️ The campaign is already running. Use 'Stop Campaign' if you wish to halt it.")
        return
        
    if not AD_DATA['sessions']:
        await message_source.reply_text("❌ No integrated sessions found. Please use 'Integrate API Session' first.")
        return

    status = get_user_status(control_user_id)
    limit = PREMIUM_DAILY_MESSAGES if status['is_premium'] else MAX_DAILY_MESSAGES
    if status['is_banned']:
        await message_source.reply_text("❌ You are currently banned from starting campaigns.")
        return
    
    if status['messages_today'] >= limit:
        await message_source.reply_text(f"🛑 Daily Limit Reached! You have sent the maximum allowed messages ({limit}) today. Please wait until tomorrow to start a new campaign.", parse_mode=None)
        return

    current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)
    if current_jobs:
        await message_source.reply_text("❌ Error: A repeating job is already registered. Please use 'Stop Campaign' first.")
        return

    SPAMMING_ACTIVE = True
    
    cycle_interval = AD_DATA['cycle_interval_seconds']
    
    context.application.job_queue.run_repeating(
        run_spam_job, 
        interval=cycle_interval, 
        first=1,
        name=JOB_KEY,
        data={'chat_id': message_source.chat_id, 'user_id': control_user_id} 
    )

    await message_source.reply_text(
        f"🚀 Campaign Initiated!\n\n"
        f"Sessions in Use: {len(AD_DATA['sessions'])}\n"
        f"Group Delay: {AD_DATA['interval_seconds']}s\n"
        f"Cycle Timer: {cycle_interval}s", 
        parse_mode=None
    )

async def stop_spam(update: Update, context, called_by_command=False) -> None:
    """Stops the repeating bulk messaging campaign."""
    global SPAMMING_ACTIVE
    message_source = update.message if called_by_command else update.effective_message 

    current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)

    if not current_jobs:
        await message_source.reply_text("⚠️ The campaign is currently inactive or was not started.")
        if called_by_command:
            await message_source.reply_text("Select next action:", reply_markup=get_main_keyboard())
        return

    for job in current_jobs:
        job.schedule_removal()

    SPAMMING_ACTIVE = False

    response_text = "🛑 Campaign Successfully Halted. The repeating task has been removed from the queue."

    if called_by_command:
        await message_source.reply_text(response_text, reply_markup=get_main_keyboard(), parse_mode=None)
    else:
        await message_source.reply_text(response_text, parse_mode=None)


async def run_spam_job(context):
    """The function that performs one full cycle of messaging through all integrated sessions."""
    global SPAMMING_ACTIVE
    
    chat_id = context.job.data['chat_id']
    control_user_id = context.job.data['user_id']
    
    if not SPAMMING_ACTIVE:
        return 

    status = get_user_status(control_user_id)
    limit = PREMIUM_DAILY_MESSAGES if status['is_premium'] else MAX_DAILY_MESSAGES
    
    if status['is_banned'] or status['messages_today'] >= limit:
        SPAMMING_ACTIVE = False
        current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)
        for job in current_jobs:
            job.schedule_removal()
            
        reason = "banned" if status['is_banned'] else f"hit daily limit of {limit} messages"
        await context.application.bot.send_message(chat_id, f"🛑 Campaign Halted!\n\nReason: Control user {reason}.", parse_mode=None)
        return

    try:
        API_ID = int(os.environ.get('API_ID'))
        API_HASH = os.environ.get('API_HASH')
        bot = context.application.bot
    except:
        SPAMMING_ACTIVE = False
        current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)
        for job in current_jobs:
            job.schedule_removal()
        await bot.send_message(chat_id, "❌ CRITICAL FAILURE: API keys missing. Campaign stopped.", parse_mode=None)
        return

    sessions_completed = 0
    total_messages_sent = 0
    cycle_start_time = time.time()
    group_delay = AD_DATA['interval_seconds']
    cycle_delay = AD_DATA['cycle_interval_seconds']

    await bot.send_message(chat_id, f"🔄 Starting Campaign Cycle (Next cycle in {cycle_delay}s)", parse_mode=None)

    for session_string in AD_DATA['sessions']:
        if not SPAMMING_ACTIVE:
            await bot.send_message(chat_id, "Campaign cycle stopped by user request.")
            return

        try:
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.start()

            session_entity = await client.get_me()
            session_name = f"@{session_entity.username}" if session_entity.username else f"ID: {session_entity.id}"

            await bot.send_message(chat_id, f"\n➡️ Initiating blast via session: {session_name}", parse_mode=None)

            result = await client(GetDialogsRequest(
                 offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=1000, hash=0
             ))

            chats = result.chats
            session_messages_sent = 0

            for chat in chats:
                if not SPAMMING_ACTIVE: break

                if status['messages_today'] >= limit:
                    await bot.send_message(chat_id, f"🛑 Daily Limit Reached! The campaign is halting. You have sent the maximum allowed messages today.", parse_mode=None)
                    SPAMMING_ACTIVE = False
                    await client.disconnect()
                    break

                try:
                    if hasattr(chat, 'broadcast') or hasattr(chat, 'megagroup'):
                        chat_title = getattr(chat, 'title', f"Chat ID: {chat.id}")

                        await client.send_message(chat, AD_DATA['ad_message'])

                        await bot.send_message(chat_id, f"   - ✅ Sent to: {chat_title}", parse_mode=None)
                        session_messages_sent += 1
                        total_messages_sent += 1

                        status['messages_today'] += 1
                        save_user_data()

                        await asyncio.sleep(group_delay) 

                except (FloodWaitError, PeerFloodError) as e:
                    wait_time = getattr(e, 'seconds', 'unknown')
                    error_message = f"   - ⚠️ Rate Limit Hit for session {session_name}. Waiting {wait_time}s or disconnecting this session."
                    logging.warning(error_message)
                    await bot.send_message(chat_id, error_message, parse_mode=None)
                    await client.disconnect() 
                    sessions_completed += 1
                    break 

                except Exception as e:
                    error_message = f"   - ❌ FAILED to send to: {chat_title}. Reason: {type(e).__name__}."
                    logging.warning(error_message)
                    await bot.send_message(chat_id, error_message, parse_mode=None)
            
            if not SPAMMING_ACTIVE:
                break

            await client.disconnect()
            sessions_completed += 1
            await bot.send_message(chat_id, 
                f"✅ Session {session_name} completed. Messages sent in this session: {session_messages_sent}.", parse_mode=None
            )

        except Exception as e:
            logging.error(f"Critical error during session processing for {session_string[:10]}...: {e}")
            await bot.send_message(chat_id, 
                f"⚠️ Error occurred while processing session {session_string[:10]}... Skipping to the next session.", parse_mode=None
            )
            try:
                if 'client' in locals() and client:
                    await client.disconnect()
            except:
                pass

    if not SPAMMING_ACTIVE:
        current_jobs = context.application.job_queue.get_jobs_by_name(JOB_KEY)
        for job in current_jobs:
            job.schedule_removal()
        return

    cycle_duration = time.time() - cycle_start_time
    if not status['is_banned']:
        remaining_line = f"• Remaining Today: {limit - status['messages_today']}"
    else:
        remaining_line = ""

    await bot.send_message(chat_id, 
        f"🏁 Campaign Cycle Complete\n\n"
        f"• Sessions Processed: {sessions_completed} out of {len(AD_DATA['sessions'])}\n"
        f"• Total Messages Sent in Cycle: {total_messages_sent}\n"
        f"• Cycle Duration: {cycle_duration:.2f} seconds\n"
        f"• Next Cycle Starts In: {cycle_delay}s\n"
        f"{remaining_line}"
        , parse_mode=None
    )


# --- Main Application Setup (Modified) ---

def main() -> None:
    """Starts the bot application."""
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    if not BOT_TOKEN:
        logging.critical("CRITICAL: BOT_TOKEN not found. Cannot start bot.")
        return

    application = Application.builder().token(BOT_TOKEN).job_queue(JobQueue()).build()

    add_session_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_session_callback, pattern='^add_session$')
        ],
        states={
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received)],
            GET_OTP: [MessageHandler(filters.TEXT & ~filters.COMMAND, otp_received)], 
            GET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, password_received)],
        },
        fallbacks=[CommandHandler('start', start_command)], 
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command)) 
    application.add_handler(add_session_handler) 
    application.add_handler(CallbackQueryHandler(handle_button_press))

    application.add_handler(CommandHandler("setad", set_ad))
    application.add_handler(CommandHandler("setinterval", set_interval))
    application.add_handler(CommandHandler("setctimer", set_cycle_interval))
    
    application.add_handler(CommandHandler("broadcast", admin_broadcast))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("setpremium", set_premium))
    
    logging.info("Nexus API Client started...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    # 1. Start Flask in a separate thread
    logging.info("Starting Flask web server in background thread...")
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()
    
    # 2. Load data
    load_user_data()
    try:
        with open('sessions.json', 'r') as f:
            AD_DATA['sessions'] = [line.strip() for line in f if line.strip()]
        logging.info(f"Loaded {len(AD_DATA['sessions'])} integrated sessions.")
    except FileNotFoundError:
        logging.warning("No previous sessions found. Starting fresh.")
    except Exception as e:
        logging.error(f"Error loading sessions: {e}")

    # 3. Start the main bot polling loop
    logging.info("Starting Telegram Bot Polling Loop...")
    main()
