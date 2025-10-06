#!/usr/bin/env python3
import os
import logging
import time
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    CallbackContext, CallbackQueryHandler
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Get configuration from environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWNER_CHAT_ID = os.environ.get('OWNER_CHAT_ID')

if not BOT_TOKEN or not OWNER_CHAT_ID:
    print("❌ ERROR: Missing environment variables!")
    exit(1)

# Channel links
CHANNELS = [
    {"name": "🔥 CHANNEL 1", "url": "https://t.me/IOS_ANDROID_NPVT"},
    {"name": "🔥 CHANNEL 2", "url": "https://t.me/ACHANNELWITHHELLAPLUGS00"},
    {"name": "🔥 CHANNEL 3", "url": "https://t.me/unlimtedwxrld"},
    {"name": "🔥 CHANNEL 4", "url": "https://t.me/The_Easy_Plugs"},
    {"name": "🔥 PRIVATE CHANNEL", "url": "https://t.me/+yUFDl0Qu6VE2OGRk"},
]

# Store data
user_conversations = {}
pending_messages = {}
MESSAGE_EXPIRY_TIME = 3 * 24 * 60 * 60

# Flask app for health checks
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Bot is Running!", 200

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}, 200

class MessageExpiryManager:
    def __init__(self):
        self.running = True
    
    def start_cleanup(self, application):
        def cleanup_loop():
            while self.running:
                try:
                    current_time = time.time()
                    for msg_id, msg_data in list(pending_messages.items()):
                        if current_time - msg_data["timestamp"] > MESSAGE_EXPIRY_TIME:
                            try:
                                user_info = user_conversations.get(msg_data["user_id"], {})
                                user_display = user_info.get('first_name', 'Unknown User')
                                expiry_notice = f"⏰ Message from {user_display} expired (3 days old)."
                                application.bot.edit_message_text(
                                    chat_id=OWNER_CHAT_ID,
                                    message_id=msg_data["owner_message_id"],
                                    text=expiry_notice
                                )
                                del pending_messages[msg_id]
                            except:
                                if msg_id in pending_messages:
                                    del pending_messages[msg_id]
                    time.sleep(3600)  # Check every hour
                except Exception as e:
                    logging.error(f"Cleanup error: {e}")
                    time.sleep(60)
        
        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logging.info("✅ Cleanup thread started")

expiry_manager = MessageExpiryManager()

# Bot handlers
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("📢 Our Channels", callback_data="channels")],
        [InlineKeyboardButton("🆘 Help", callback_data="help")],
        [InlineKeyboardButton("💬 Contact Owner", callback_data="contact")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\nI'm your messaging assistant.",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "🤖 **Bot Help**\n\n"
        "**Features:**\n"
        "• Message forwarding to owner\n"
        "• 3-day message expiry\n"
        "• Secure and private\n\n"
        "**Commands:**\n"
        "/start - Start bot\n"
        "/help - This help\n"
        "/channels - Show channels"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def show_channels(update: Update, context: CallbackContext):
    channels_text = "📢 **Our Channels:**\n\n"
    keyboard = []
    for channel in CHANNELS:
        channels_text += f"• {channel['name']}\n"
        keyboard.append([InlineKeyboardButton(channel["name"], url=channel["url"])])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(channels_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if query.data == "channels":
        await show_channels(update, context)
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "contact":
        await update.callback_query.message.reply_text("💬 You can now send any message to contact the owner!")

async def forward_to_owner(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        if update.effective_chat.type != "private":
            return
        
        user_identifier = f"User_{hash(user.id) % 10000:04d}"
        user_info = f"👤 From: {user.first_name or 'Unknown'}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\n🔒 ID: {user_identifier}\n⏰ Expires in 3 days"
        
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("📨 Reply", callback_data=f"reply_{user.id}_{update.message.message_id}")
        ]])
        
        user_conversations[user.id] = {
            'first_name': user.first_name,
            'username': user.username
        }
        
        if update.message.text:
            message_text = f"💬 New Message\n{user_info}\n\n{update.message.text}"
            sent_message = await context.bot.send_message(
                chat_id=OWNER_CHAT_ID,
                text=message_text,
                reply_markup=reply_markup
            )
            
            pending_messages[update.message.message_id] = {
                "user_id": user.id,
                "timestamp": time.time(),
                "owner_message_id": sent_message.message_id
            }
            
            await update.message.reply_text("✅ Message sent to owner!")
            
    except Exception as e:
        logging.error(f"Forward error: {e}")
        await update.message.reply_text("❌ Error sending message.")

async def handle_owner_reply(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('reply_'):
        parts = query.data.split('_')
        user_id = int(parts[1])
        original_message_id = int(parts[2])
        
        if original_message_id not in pending_messages:
            await query.answer("❌ Message expired (3 days old)", show_alert=True)
            return
            
        context.user_data['replying_to'] = user_id
        await query.edit_message_text("🔄 Reply to this message to respond to the user...")

async def forward_reply_to_user(update: Update, context: CallbackContext):
    if 'replying_to' in context.user_data:
        try:
            user_id = context.user_data['replying_to']
            if update.message.text:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📩 Reply from owner:\n\n{update.message.text}"
                )
                await update.message.reply_text("✅ Reply sent!")
            del context.user_data['replying_to']
        except Exception as e:
            await update.message.reply_text("❌ Failed to send reply.")

def run_bot():
    """Run Telegram bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("channels", show_channels))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(MessageHandler(
        filters.Chat(OWNER_CHAT_ID) & filters.TEXT & ~filters.COMMAND,
        forward_reply_to_user
    ))
    
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        forward_to_owner
    ))

    # Start cleanup thread
    expiry_manager.start_cleanup(application)
    
    print("🤖 Bot starting on Render...")
    application.run_polling()

def start_server():
    """Start Flask server for Render health checks"""
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting web server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Start web server in main thread (for Render health checks)
    start_server()