import os
import logging
import random
import asyncio
import re
import json
import base64
from validators import domain
from Script import script
from plugins.dbusers import db
from pyrogram import Client, filters, enums
from plugins.users_api import get_user, update_user_info, get_short_link
from pyrogram.errors import *
from pyrogram.types import *
from utils import verify_user, check_token, check_verification, get_token
from config import *
from Zahid.utils.file_properties import get_name, get_hash, get_media_file_size
from pytz import timezone
from datetime import date, datetime, timedelta
import time
import subprocess
import socket
import ssl
import urllib.parse
import requests
logger = logging.getLogger(__name__)

# --------------------- IMPROVED UTILITY FUNCTIONS ---------------------
def extract_user_id_from_text(text: str) -> int:
    """Extract User ID with multiple fallback methods"""
    patterns = [
        r'#UID(\d+)#',                     # Primary embedded pattern
        r'User ID:\s*`(\d+)`',             # Backtick format
        r'This message is from User ID:\s*(\d+)'  # Plain text
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None

def not_command_filter(_, __, message: Message) -> bool:
    """Better command detection with argument handling"""
    return not (message.text and message.text.split()[0].startswith('/'))

# --------------------- RELIABLE MESSAGE LOGGING ---------------------
@Client.on_message(filters.private & filters.create(not_command_filter) & ~filters.service)
async def log_all_private_messages(client, message: Message):
    try:
        user = message.from_user
        
        # Build metadata with both UID and BOT markers
        user_info = (
            "📩 <b>New Message from User of Audiobook Bot</b>\n"
            f"👤 <b>Name:</b> {user.first_name or 'N/A'} {user.last_name or ''}\n"
            f"🆔 <b>User ID:</b> `{user.id}` #UID{user.id}#\n"
            f"🤖 <b>Bot Name:</b> {client.me.username}\n"  # Add this line
            f"🤖 <b>Bot ID:</b> #BOT{client.me.id}#\n"
            f"📱 <b>Username:</b> @{user.username or 'N/A'}\n"
            f"⏰ <b>Time:</b> {datetime.now(timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S')}\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
            "<b>Original Message:</b>"
        )

        if message.text:
            await client.send_message(
                LOG_CHANNEL,
                f"{user_info}\n\n{message.text}"
            )
        else:
            # Forward media first then add metadata
            header = await client.send_message(LOG_CHANNEL, user_info)
            forwarded = await message.forward(LOG_CHANNEL)
            try:
                await forwarded.reply_text(
                    f"👤 This message is from User ID: {user.id}\n"
                    f"🤖 Via Bot: #BOT{client.me.id}#",
                    quote=True
                )
            except Exception as e:
                logger.error(f"Metadata reply failed: {e}")

    except Exception as e:
        logger.error(f"Logging Error: {e}")
        try:
            await client.send_message(LOG_CHANNEL, f"⚠️ Logging Error: {str(e)}")
        except Exception as inner_e:
            logger.error(f"Error reporting failed: {inner_e}")

# --------------------- SECURE REPLY HANDLER ---------------------
@Client.on_message(filters.chat(LOG_CHANNEL) & filters.reply)
async def reply_to_user(client, message: Message):
    try:
        current_msg = message.reply_to_message
        user_id = None
        target_bot_id = None

        # Traverse reply chain with security checks
        while current_msg:
            text_source = current_msg.text or current_msg.caption or ""
            
            # Extract both IDs from text
            bot_match = re.search(r'#BOT(\d+)#', text_source)
            target_bot_id = int(bot_match.group(1)) if bot_match else None
            user_id = extract_user_id_from_text(text_source)

            if user_id and target_bot_id:
                break
                
            current_msg = current_msg.reply_to_message

        # Security verification
        if target_bot_id != client.me.id:
            logger.warning(f"Ignored reply for bot {target_bot_id}")
            return

        if not user_id:
            if message.reply_to_message.forward_from:
                user_id = message.reply_to_message.forward_from.id
            else:
                logger.error("No user ID found")
                await message.reply_text("❌ No user ID detected", quote=True)
                return

        try:
            # Send reply with confirmation
            if message.text:
                await client.send_message(
                    user_id,
                    f"<b>Admin Reply:</b>\n\n{message.text}"
                )
            else:
                await message.copy(user_id)
            
            await message.reply_text(f"✅ Reply sent to user {user_id}", quote=True)

        except Exception as e:
            error_msg = f"❌ Delivery failed: {str(e)}"
            await message.reply_text(error_msg, quote=True)
            logger.error(f"Reply Error: {e}")

    except Exception as e:
        logger.critical(f"Reply handler crashed: {e}")
        await message.reply_text("🚨 System error in reply handler", quote=True)