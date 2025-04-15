import os
import logging
import random
import asyncio
import json
import hashlib
import html
import base64
import time
import socket
import ssl
import re
import urllib.parse
from datetime import date, datetime, timedelta
from typing import List, Tuple

import requests
from pytz import timezone
from bs4 import BeautifulSoup, Comment
from validators import domain

from pyrogram import Client, filters, enums
from pyrogram.types import Message, PollOption
from pyrogram.errors import FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid

import aiofiles

from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info, get_short_link
from Zahid.utils.file_properties import get_name, get_hash, get_media_file_size
from config import *

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File to store sent fact IDs
SENT_FACTS_FILE = "sent_facts.json"
MAX_STORED_FACTS = 200  # Keep last 200 fact IDs

async def load_sent_facts() -> list:
    """Load sent fact IDs from file"""
    try:
        async with aiofiles.open(SENT_FACTS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_facts(fact_ids: list):
    """Save sent fact IDs to file"""
    async with aiofiles.open(SENT_FACTS_FILE, "w") as f:
        await f.write(json.dumps(fact_ids[-MAX_STORED_FACTS:]))

def fetch_daily_fact() -> tuple:
    """
    Fetches 1 random fact with duplicate prevention
    Returns (formatted_fact, fact_id)
    """
    try:
        response = requests.get(
            "https://uselessfacts.jsph.pl/api/v2/facts/random",
            headers={'Accept': 'application/json'},
            timeout=10
        )
        response.raise_for_status()
        fact_data = response.json()
        
        fact_text = f"✦ {fact_data['text'].strip()}"
        fact_id = fact_data.get('id', str(time.time()))  # Use timestamp as fallback ID
        
        return (
            "🧠 **Daily Knowledge Boost**\n\n"
            f"{fact_text}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Stay Curious! @Excellerators",
            fact_id
        )
        
    except Exception as e:
        logger.error(f"Fact API error: {e}")
        return (
            "💡 **Did You Know?**\n\n"
            "✦ Honey never spoils and can last for thousands of years!\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Learn more @Excellerators",
            f"fallback_{time.time()}"
        )

async def send_scheduled_facts(bot: Client):
    """Send scheduled facts with duplicate prevention"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        target_times = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=12, minute=0, second=0, microsecond=0),
            now.replace(hour=16, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0)
        ]
        
        valid_times = [t for t in target_times if t > now]
        next_time = min(valid_times) if valid_times else target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next fact at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_facts()
            fact_message, fact_id = fetch_daily_fact()
            
            # Retry until unique fact found (max 5 attempts)
            retry = 0
            while fact_id in sent_ids and retry < 5:
                fact_message, fact_id = fetch_daily_fact()
                retry += 1
            
            await bot.send_message(
                chat_id=FACTS_CHANNEL,
                text=fact_message,
                disable_web_page_preview=True
            )
            sent_ids.append(fact_id)
            await save_sent_facts(sent_ids)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📖 Fact sent at {datetime.now(tz).strftime('%H:%M IST')}\nID: {fact_id}"
            )
            
        except Exception as e:
            logger.exception("Fact broadcast failed:")

@Client.on_message(filters.command('facts') & filters.user(ADMINS))
async def instant_facts_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Fetching unique fact...")
        sent_ids = await load_sent_facts()
        fact_message, fact_id = fetch_daily_fact()
        
        # Retry for unique fact
        retry = 0
        while fact_id in sent_ids and retry < 5:
            fact_message, fact_id = fetch_daily_fact()
            retry += 1
        
        await client.send_message(
            chat_id=FACTS_CHANNEL,
            text=fact_message,
            disable_web_page_preview=True
        )
        sent_ids.append(fact_id)
        await save_sent_facts(sent_ids)
        
        await processing_msg.edit("✅ Unique fact published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"📚 Manual fact sent\nID: {fact_id}"
        )
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Fact command failed: {str(e)[:500]}"
        )


def schedule_facts(client: Client):
    """Starts the facts scheduler"""
    asyncio.create_task(send_scheduled_facts(client))


# --------------------- new function ------------------------ #