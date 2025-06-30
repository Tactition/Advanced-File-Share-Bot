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

# --------------------- RELIABLE MESSAGE LOGGING (WITH MEDIA SUPPORT) ---------------------
@Client.on_message(filters.private & filters.create(not_command_filter) & ~filters.service)
async def log_all_private_messages(client, message: Message):
    try:
        user = message.from_user
        
        # Build metadata with both UID and BOT markers
        user_info = (
            "📩 <b>New Message from User of Audiobook Bot</b>\n"
            f"👤 <b>Name:</b> {user.first_name or 'N/A'} {user.last_name or ''}\n"
            f"🆔 <b>User ID:</b> `{user.id}` #UID{user.id}#\n"
            f"🤖 <b>Bot Name:</b> {client.me.username}\n"
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
            # Handle media messages
            header = await client.send_message(LOG_CHANNEL, user_info)
            forwarded = await message.forward(LOG_CHANNEL)
            
            # Add metadata as a reply to the forwarded media
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

# --------------------- SECURE REPLY HANDLER (WITH MEDIA SUPPORT) ---------------------
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
            # Handle media replies
            if message.media:
                # Add prefix to caption if exists
                if message.caption:
                    new_caption = f"<b>Admin Reply:</b>\n\n{message.caption}"
                    await message.copy(
                        user_id,
                        caption=new_caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                # For media without caption
                else:
                    await message.copy(user_id)
                    await client.send_message(
                        user_id,
                        "<b>Admin Reply</b>",
                        parse_mode=enums.ParseMode.HTML
                    )
                msg_type = "Media"
            
            # Handle text replies
            else:
                await client.send_message(
                    user_id,
                    f"<b>Admin Reply:</b>\n\n{message.text}",
                    parse_mode=enums.ParseMode.HTML
                )
                msg_type = "Message"
            
            await message.reply_text(f"✅ {msg_type} sent to user {user_id}", quote=True)

        except Exception as e:
            error_msg = f"❌ Delivery failed: {str(e)}"
            await message.reply_text(error_msg, quote=True)
            logger.error(f"Reply Error: {e}")

    except Exception as e:
        logger.critical(f"Reply handler crashed: {e}")
        await message.reply_text("🚨 System error in reply handler", quote=True)

# --------------------- ADMIN SEND MESSAGE (WITH MEDIA SUPPORT) ---------------------
@Client.on_message(filters.command('message') & filters.user(ADMINS))
async def admin_send_message(client: Client, message: Message):
    """
    Admin command with media support:
      /message <user_id|@username> <text> [with media attachment]
    """
    # Handle media messages
    if message.media and message.caption:
        parts = message.caption.split(maxsplit=1)
        if len(parts) < 1:
            return await message.reply(
                "⚠️ <b>Media Usage:</b> Add caption: <code>/message &lt;user_id|@username&gt; [text]</code>\n\n"
                "<b>Example:</b> <code>/message 123456789 Check this image</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        target = parts[0]
        text = parts[1] if len(parts) > 1 else None
    # Handle text messages
    elif not message.media:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply(
                "⚠️ <b>Usage:</b> <code>/message &lt;user_id|@username&gt; &lt;text&gt;</code>\n\n"
                "<b>Example:</b> <code>/message 123456789 Hello there!</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        target, text = parts[1], parts[2]
    else:
        return await message.reply(
            "⚠️ <b>Send media with caption:</b> <code>/message &lt;user_id|@username&gt; [text]</code>",
            quote=True,
            parse_mode=enums.ParseMode.HTML
        )

    # Resolve ID or username
    try:
        user_id = int(target)
    except ValueError:
        username = target.lstrip('@')
        try:
            user = await client.get_users(username)
            user_id = user.id
        except PeerIdInvalid:
            return await message.reply(f"❌ User <code>@{username}</code> not found.", quote=True, parse_mode=enums.ParseMode.HTML)
        except RPCError as e:
            logger.error(f"Error resolving @{username}: {e}")
            return await message.reply(f"❌ Error: <code>{e}</code>", quote=True, parse_mode=enums.ParseMode.HTML)

    try:
        # Send media with caption
        if message.media:
            await message.copy(
                chat_id=user_id,
                caption=text
            )
            msg_type = "Media"
        # Send text message
        else:
            await client.send_message(chat_id=user_id, text=text)
            msg_type = "Message"
        
        # Create response
        response = (
            f"✅ {msg_type} sent to user:\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"<i>Reply to this message to continue the conversation</i>"
        )
        
        await message.reply(response, quote=True, parse_mode=enums.ParseMode.HTML)
    except RPCError as e:
        logger.error(f"Failed to send to {user_id}: {e}")
        await message.reply(f"❌ Delivery failed: <code>{e}</code>", quote=True, parse_mode=enums.ParseMode.HTML)

# --------------------- USER SEND MESSAGE (WITH MEDIA SUPPORT) ---------------------
@Client.on_message(filters.command('message') & filters.private & ~filters.user(ADMINS))
async def user_send_message(client: Client, message: Message):
    """
    User command with media support:
      /message <text> [with media attachment]
    """
    # Extract message text/caption
    if message.media and message.caption:
        text = message.caption.split(maxsplit=1)[1] if len(message.caption.split()) > 1 else ""
    elif not message.media:
        if len(message.command) < 2:
            return await message.reply(
                "⚠️ <b>Usage:</b> <code>/message your_text_here</code>\n\n"
                "<b>Example:</b> <code>/message I need help with my account</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        text = message.text.split(maxsplit=1)[1]
    else:
        text = ""

    user = message.from_user
    
    # Build metadata header
    header = (
        f"📩 #message <b>From User</b>\n"
        f"👤 Name: {user.first_name or ''} {user.last_name or ''}\n"
        f"🆔 User ID: <code>{user.id}</code> #UID{user.id}#\n"
        f"🤖 Bot ID: #BOT{client.me.id}#\n"
        f"📱 Username: @{user.username or 'N/A'}\n"
        f"⏰ Time: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "➖➖➖➖➖➖➖\n"
    )
    
    try:
        # Forward media with caption
        if message.media:
            await message.copy(
                LOG_CHANNEL,
                caption=header + (message.caption or ""),
                parse_mode=enums.ParseMode.HTML
            )
        # Forward text message
        else:
            await client.send_message(
                LOG_CHANNEL, 
                header + text,
                parse_mode=enums.ParseMode.HTML
            )
        
        await message.reply(
            "✅ Your message has been sent to the admins.\n"
            "They'll reply to you here when available.",
            quote=True
        )
    except Exception as e:
        logger.error(f"Failed to forward user message: {e}")
        await message.reply(
            "❌ Could not send your message. Please try again later.",
            quote=True
        )
