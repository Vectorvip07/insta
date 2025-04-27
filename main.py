#!/usr/bin/env python3
"""
Enhanced Telegram bot to download Instagram reels with:
- Join channel requirement
- User-friendly UI with clear instructions
- Top quality reel downloads with captions
- Progress indicators
- High load handling messages
- Background web server to keep alive on Render
"""

import os
import re
import logging
import time
import requests
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Updater, CommandHandler, MessageHandler,
                          CallbackQueryHandler, Filters, CallbackContext)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = "7828233355:AAEgdjNtWLrTe41f0Mi5w_lmzXdLZWtamTo"
BOT_USERNAME = "@Zhfjsbot"
CHANNEL_USERNAME = "@instadownloadbkt"
CHANNEL_LINK = "https://t.me/instadownloadbkt"
DONATION = "Bhavesh_dev"

# Regex to extract Instagram reel shortcode from URL
REEL_REGEX = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)/?"
)

# Track active downloads
active_downloads = 0
MAX_CONCURRENT_DOWNLOADS = 3

# Flask web server to fake alive for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running fine!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ------------------ Bot Functions ------------------

def check_channel_membership(update: Update, context: CallbackContext) -> bool:
    user_id = update.effective_user.id
    try:
        member = context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        return False

def start(update: Update, context: CallbackContext) -> None:
    if not check_channel_membership(update, context):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("I've Joined ✅", callback_data="check_membership")]
        ])
        update.message.reply_text(
            "📢 Please join our channel to use this bot!\n\n"
            "After joining, click 'I've Joined' to continue.",
            reply_markup=keyboard
        )
        return

    welcome_text = """
🌟 *Welcome to Instagram Reel Downloader Bot* 🌟

🔹 *How to use:*
1. Send me any Instagram Reel link
2. I'll download it in highest quality
3. You'll receive the video with original caption

⚡ *Features:*
- Top quality downloads (up to 1080p)
- Fast and reliable service
- Preserves original captions
- Clean and simple interface

⚠ *Note:*
- Only works with public Instagram accounts
- May take longer during high traffic periods

Send me a Reel link now to get started!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Share Bot", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}")],
        [InlineKeyboardButton("Support Channel", url=CHANNEL_LINK)]
    ])
    
    update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

def send_typing_action(chat_id, context):
    context.bot.send_chat_action(chat_id=chat_id, action='typing')

def send_uploading_video_action(chat_id, context):
    context.bot.send_chat_action(chat_id=chat_id, action='upload_video')

def download_reel(update: Update, context: CallbackContext) -> None:
    global active_downloads
    
    if not check_channel_membership(update, context):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("I've Joined ✅", callback_data="check_membership")]
        ])
        update.message.reply_text(
            "❌ You must join our channel to use this bot.\n\n"
            "Please join and try again.",
            reply_markup=keyboard
        )
        return
    
    message = update.message
    text = message.text.strip()
    chat_id = update.effective_chat.id

    if active_downloads >= MAX_CONCURRENT_DOWNLOADS:
        message.reply_text(
            "⚠️ *High Load Notice*\n\n"
            "Our bot is currently processing many requests.\n"
            "Please wait a moment...",
            parse_mode='Markdown'
        )
        while active_downloads >= MAX_CONCURRENT_DOWNLOADS:
            time.sleep(2)

    match = REEL_REGEX.search(text)
    if not match:
        message.reply_text(
            "❌ *Invalid Link*\n\n"
            "Please send a valid Instagram Reel URL like:\n"
            "`https://www.instagram.com/reel/ABC123/`\n\n"
            "Or try another link.",
            parse_mode='Markdown'
        )
        return

    shortcode = match.group(1)
    logger.info(f"Processing reel: {shortcode}")
    active_downloads += 1
    
    try:
        progress_msg = message.reply_text(
            "⏳ *Download in Progress...*\n\n"
            "Fetching highest quality...",
            parse_mode='Markdown'
        )
        send_typing_action(chat_id, context)

        import instaloader
        L = instaloader.Instaloader(
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        if not post.is_video:
            progress_msg.edit_text(
                "❌ This post doesn't contain a video.\n"
                "Please send a Reel or video link."
            )
            return
        
        video_url = post.video_url
        caption = f"🎥 *Original Caption:*\n{post.caption}\n\n" if post.caption else ""
        caption += f"🔗 [View on Instagram](https://instagram.com/p/{shortcode})"

        progress_msg.edit_text(
            "⏳ *Downloading...*\n\n"
            "This may take a few seconds...",
            parse_mode='Markdown'
        )

        filename = f"{shortcode}.mp4"
        with requests.get(video_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        progress_msg.edit_text(
            "✅ *Download Complete!*\n\n"
            "📤 Uploading...",
            parse_mode='Markdown'
        )
        send_uploading_video_action(chat_id, context)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Another", callback_data='download_another')],
            [InlineKeyboardButton("🌟 Donate", url=f"https://t.me/{DONATION}?start=rate")],
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]
        ])
        
        with open(filename, 'rb') as video_file:
            message.reply_video(
                video=video_file,
                caption=caption,
                parse_mode='Markdown',
                reply_markup=keyboard,
                supports_streaming=True
            )

        progress_msg.delete()
        
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"Instaloader error: {e}")
        progress_msg.edit_text(
            "❌ *Download Failed*\n\n"
            "Maybe it's a private account or unavailable post.",
            parse_mode='Markdown'
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        progress_msg.edit_text(
            "❌ *Connection Error*\n\n"
            "Failed to download. Try later.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        progress_msg.edit_text(
            "❌ *An Error Occurred*\n\n"
            "Please try again.",
            parse_mode='Markdown'
        )
    finally:
        active_downloads -= 1
        try:
            os.remove(filename)
        except:
            pass

def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id
    
    if data == 'download_another':
        query.answer()
        context.bot.send_message(
            chat_id=chat_id,
            text="🔄 Send me another Instagram Reel link to download:",
            parse_mode='Markdown'
        )
    elif data == 'check_membership':
        if check_channel_membership(update, context):
            query.answer("Thanks for joining! Now you can use the bot.")
            start(update, context)
        else:
            query.answer("You haven't joined the channel yet!", show_alert=True)
    else:
        query.answer()

def run_bot():
    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, download_reel))
    dispatcher.add_handler(CallbackQueryHandler(button_callback))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    Thread(target=run_flask).start()
    run_bot()