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
                    "content": """You are a creative English language expert who specializes in vocabulary and talk like a professional influential Figures. Generate vocabulary content with this EXACT format:

✨<b><i> Word Of The Day ! </i></b> ✨

<b><i>📚 [Word]</i></b>
━━━━━━━━━━━━━━━
<b><i>Meaning :</i></b>[Short definition] 

<b><i>💡Think: </i></b>
[Short relatable example/analogy]

<b><i>Synonyms :</i></b>
<b>[Word1]:</b> [Brief explanation]
<b>[Word2]:</b> [Different angle]
<b>[Word3]:</b> [Unique take]

<b><i>Antonyms: </i></b>
<b>[Word1] :</b> [Contrasting concept]
<b>[Word2] :</b> [Opposite perspective]
<b>[Word3] :</b> [Counterpart idea]

<b><i>See It In Action!🎬</i></b>
"[Practical example sentence]"

<b><i>Want more wonders? Explore:</i></b> ➡️ @Excellerators"""
                },
                {
                    "role": "user",
                    "content": "Generate a fresh vocabulary entry in the specified format. Make it contemporary and conversational."
                }
            ],
            model="llama3-70b-8192",
            temperature=1.3,
            max_tokens=400,
            stream=False
        )
        
        word_content = response.choices[0].message.content
        word_hash = hashlib.md5(word_content.encode()).hexdigest()
        
        return (word_content, word_hash)
        
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return (
            """✨ Level Up Your Lexicon! ✨
Enthusiast 
(Meaning): Someone who's absolutely fired up and deeply passionate about a specific hobby, interest, or subject! 🔥

Think: That friend who lives and breathes video games? The person who can talk about their favorite band for hours? Yep, they're enthusiasts!

Synonyms :
Fanatic: Going beyond just liking something! Think super dedicated.
Devotee: Heart and soul invested! Shows a deep commitment.
Aficionado: Not just a fan, but a knowledgeable one! Knows the ins and outs.

Word Opposites (Flip the Script! 🔄):
Skeptic: Hmm, I'm not so sure... Questions everything! 🤔
Critic: Always finding something to pick apart. 🤨
Indifferent: Meh. Doesn't care either way. 😴

See It In Action! 🎬
"The release of the new sci-fi series drew in a massive crowd of enthusiasts, eager to explore its intricate world and compelling characters." 🚀🌌

Ready to become a vocabulary enthusiast yourself? 😉
Want more word wonders? ➡️ @Excellerators""",
            f"fallback_{time.time()}"
        )

async def send_scheduled_vocabulary(bot: Client):
    """Send scheduled vocabulary words with duplicate prevention"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        target_times = [
            now.replace(hour=11, minute=30, second=0, microsecond=0),  # 11:30 AM IST
            now.replace(hour=19, minute=30, second=0, microsecond=0)  # 7:30 PM IST
        ]
        
        valid_times = [t for t in target_times if t > now]
        next_time = min(valid_times) if valid_times else target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next vocab at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_words()
            word_message, word_id = fetch_daily_word()
            
            # Retry for unique word (max 3 attempts)
            retry = 0
            while word_id in sent_ids and retry < 3:
                word_message, word_id = fetch_daily_word()
                retry += 1
            
            await bot.send_message(
                chat_id=VOCAB_CHANNEL,
                text=word_message,
                disable_web_page_preview=True
            )
            sent_ids.append(word_id)
            await save_sent_words(sent_ids)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📖 Vocab sent at {datetime.now(tz).strftime('%H:%M IST')}\nID: {word_id}"
            )
            
        except Exception as e:
            logger.exception("Vocabulary broadcast failed:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"⚠️ Vocab send failed: {str(e)[:500]}"
            )
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