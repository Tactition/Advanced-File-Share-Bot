import os
import logging
import random
import asyncio
import re
import json
import html
import base64
import time
import socket
import ssl
import urllib.parse
import requests
from datetime import date, datetime, timedelta
from pytz import timezone
from bs4 import BeautifulSoup, Comment
from pyrogram import Client, filters, enums
from pyrogram.types import *
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

# For asynchronous file operations
import aiofiles

from validators import domain
from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info, get_short_link
from Zahid.utils.file_properties import get_name, get_hash, get_media_file_size
from config import *

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# =============================
# DAILY FACTS FUNCTIONALITY
# =============================
def fetch_daily_fact() -> str:
    """
    Fetches 1 random fact from the API (single fact version)
    """
    try:
        response = requests.get(
            "https://uselessfacts.jsph.pl/api/v2/facts/random",
            headers={'Accept': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        fact_data = response.json()
        
        # Directly use the text from API response
        fact = f"✦ {fact_data['text'].strip()}"
            
        return (
            "🧠 **Daily Knowledge Boost**\n\n"
            f"{fact}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Stay Curious! @Excellerators"
        )
        
    except Exception as e:
        logger.error(f"Fact API error: {e}")
        return (
            "💡 **Did You Know?**\n\n"
            "✦ Honey never spoils and can last for thousands of years!\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Learn more @Excellerators"
        )

# Modified sender function for single fact
async def send_scheduled_facts(bot: Client):
    """
    Sends 1 fact daily at 8 AM, 1 PM, and 8 PM IST
    """
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        target_times = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=13, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0)
        ]
        
        valid_times = [t for t in target_times if t > now]
        if not valid_times:
            next_time = target_times[0] + timedelta(days=1)
        else:
            next_time = min(valid_times)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next fact at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)
        
        try:
            fact_message = fetch_daily_fact()
            await bot.send_message(
                chat_id=FACTS_CHANNEL,
                text=fact_message,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.exception("Fact broadcast failed:")

@Client.on_message(filters.command('facts') & filters.user(ADMINS))
async def instant_facts_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Fetching today's fact...")
        fact_message = fetch_daily_fact()
        
        await client.send_message(
            chat_id=FACTS_CHANNEL,
            text=fact_message,
            disable_web_page_preview=True
        )
        await processing_msg.edit("✅ Fact published!")
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")