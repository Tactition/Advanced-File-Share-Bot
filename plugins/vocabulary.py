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

# Add to your existing plugin file (e.g., vocabulary_plugin.py)
from groq import Groq

# Configuration
client = Groq(api_key="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")
SENT_WORDS_FILE = "sent_words.json"
MAX_STORED_WORDS = 200

async def load_sent_words() -> list:
    """Load sent word IDs from file"""
    try:
        async with aiofiles.open(SENT_WORDS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_words(word_ids: list):
    """Save sent word IDs to file"""
    async with aiofiles.open(SENT_WORDS_FILE, "w") as f:
        await f.write(json.dumps(word_ids[-MAX_STORED_WORDS:]))

def fetch_daily_word() -> tuple:
    """
    Fetches random vocabulary word using Groq API
    Returns (formatted_word, word_id)
    """
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Generate useful English vocabulary for daily conversations with meaning, synonyms, antonyms, and example."
                },
                {
                    "role": "user",
                    "content": "Generate a random vocabulary word with: 1. Word, 2. Meaning, 3. 2-3 synonyms, 4. 2-3 antonyms, 5. Example usage. Use bold headings."
                }
            ],
            model="llama3-70b-8192",
            temperature=1.2,
            max_tokens=300
        )
        
        word_content = response.choices[0].message.content
        word_hash = hashlib.md5(word_content.encode()).hexdigest()
        
        return (
            f"📚 **Daily Vocabulary Boost**\n\n{word_content}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Learn More @Excellerators",
            word_hash
        )
        
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return (
            "📖 **Word of the Day**\n\n"
            "**Word:** Resilient\n"
            "**Meaning:** Able to recover quickly from difficulties\n"
            "**Synonyms:** Tough, durable, robust\n"
            "**Antonyms:** Fragile, vulnerable, weak\n"
            "**Example:** Despite setbacks, she remained resilient.\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Learn More @Excellerators",
            f"fallback_{time.time()}"
        )

async def send_scheduled_vocabulary(bot: Client):
    """Send scheduled vocabulary words with duplicate prevention"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        # Set your desired schedule (8 AM and 8 PM IST)
        target_times = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0)
        ]
        
        valid_times = [t for t in target_times if t > now]
        next_time = min(valid_times) if valid_times else target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next vocabulary at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_words()
            word_message, word_id = fetch_daily_word()
            
            # Retry for unique word
            retry = 0
            while word_id in sent_ids and retry < 5:
                word_message, word_id = fetch_daily_word()
                retry += 1
            
            await bot.send_message(
                chat_id=VOCAB_CHANNEL,  # Add to config.py
                text=word_message,
                disable_web_page_preview=True
            )
            sent_ids.append(word_id)
            await save_sent_words(sent_ids)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📚 Vocabulary sent at {datetime.now(tz).strftime('%H:%M IST')}\nID: {word_id}"
            )
            
        except Exception as e:
            logger.exception("Vocabulary broadcast failed:")

@Client.on_message(filters.command('vocab') & filters.user(ADMINS))
async def instant_vocab_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Generating unique vocabulary...")
        sent_ids = await load_sent_words()
        word_message, word_id = fetch_daily_word()
        
        # Retry for unique word
        retry = 0
        while word_id in sent_ids and retry < 5:
            word_message, word_id = fetch_daily_word()
            retry += 1
        
        await client.send_message(
            chat_id=VOCAB_CHANNEL,
            text=word_message,
            disable_web_page_preview=True
        )
        sent_ids.append(word_id)
        await save_sent_words(sent_ids)
        
        await processing_msg.edit("✅ Vocabulary published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"📖 Manual vocabulary sent\nID: {word_id}"
        )
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Vocab command failed: {str(e)[:500]}"
        )

def schedule_vocabulary(client: Client):
    """Starts the vocabulary scheduler"""
    asyncio.create_task(send_scheduled_vocabulary(client))