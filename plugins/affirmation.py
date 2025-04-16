import os
import logging
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Optional
import html
import hashlib
import requests
from pytz import timezone
from validators import url

from pyrogram import Client, filters, enums
from pyrogram.types import Message

import aiofiles

from config import *

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File to store sent message hashes
SENT_HASHES_FILE = "sent_hashes.json"
MAX_STORED_HASHES = 200

async def load_sent_hashes() -> list:
    """Load sent message hashes from file"""
    try:
        async with aiofiles.open(SENT_HASHES_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_hashes(hashes: list):
    """Save sent message hashes to file"""
    async with aiofiles.open(SENT_HASHES_FILE, "w") as f:
        await f.write(json.dumps(hashes[-MAX_STORED_HASHES:]))

def fetch_daily_content() -> dict:
    """Fetch combined content from both APIs"""
    content = {
        "affirmation": "You are capable of amazing things!",
        "advice": "Believe in yourself and your abilities.",
        "hash": str(time.time())
    }
    
    try:
        # Fetch affirmation
        affirmation_resp = requests.get(
            "https://www.affirmations.dev/",
            timeout=5
        )
        if affirmation_resp.status_code == 200:
            content["affirmation"] = affirmation_resp.json().get("affirmation", content["affirmation"])
    except Exception as e:
        logger.error(f"Affirmation API error: {e}")

    try:
        # Fetch advice
        advice_resp = requests.get(
            "https://api.adviceslip.com/advice",
            timeout=5
        )
        if advice_resp.status_code == 200:
            slip = advice_resp.json().get("slip", {})
            content["advice"] = slip.get("advice", content["advice"])
    except Exception as e:
        logger.error(f"Advice API error: {e}")

    # Create unique hash
    content_str = f"{content['affirmation']}{content['advice']}"
    content["hash"] = hashlib.md5(content_str.encode()).hexdigest()
    return content

async def send_daily_message(bot: Client, content: dict):
    """Send formatted message to channel"""
    message = (
        "🌅 <b>Top 1% Insights</b> 🌟\n\n"
        f"💖 <i>Affirmation:</i>\n{html.escape(content['affirmation'])}\n\n"
        f"🧠 <i>Advice of the Day:</i>\n{html.escape(content['advice'])}\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Be Positive and Explore! @Excellerators"
    )

    try:
        await bot.send_message(
            chat_id=WONDERS_CHANNEL,
            text=message,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send daily message: {e}")
        await bot.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Failed to send daily message: {str(e)[:500]}"
        )


async def send_scheduled_daily(bot: Client):
    """Send scheduled daily message"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        target_time = now.replace(hour=21, minute=0, second=0, microsecond=0)
        
        if now > target_time:
            target_time += timedelta(days=1)
        
        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"Next daily message at {target_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_hashes = await load_sent_hashes()
            content = fetch_daily_content()
            
            if content["hash"] in sent_hashes:
                logger.info("Duplicate content detected, skipping")
                continue
                
            await send_daily_message(bot, content)
            sent_hashes.append(content["hash"])
            await save_sent_hashes(sent_hashes)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📬 Daily message sent at {datetime.now(tz).strftime('%H:%M IST')}"
            )
            
        except Exception as e:
            logger.exception("Daily message failed:")

@Client.on_message(filters.command('affirm') & filters.user(ADMINS))
async def manual_daily_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Fetching daily boost...")
        sent_hashes = await load_sent_hashes()
        content = fetch_daily_content()
        
        if content["hash"] in sent_hashes:
            await processing_msg.edit("⚠️ Content already sent recently")
            return
            
        await send_daily_message(client, content)
        sent_hashes.append(content["hash"])
        await save_sent_hashes(sent_hashes)
        
        await processing_msg.edit("✅ Daily boost published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"📬 Manual daily message sent"
        )
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Daily command failed: {str(e)[:500]}"
        )

def schedule_daily(client: Client):
    """Starts the daily scheduler"""
    asyncio.create_task(send_scheduled_daily(client))