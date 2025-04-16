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

from groq import Groq

# Configuration
client = Groq(api_key="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")

async def get_sent_words_from_channel(bot: Client) -> list:
    """Fetch sent words from channel message history"""
    sent_words = []
    try:
        async for message in bot.get_chat_history(chat_id=VOCAB_CHANNEL, limit=200):
            if not message.text:
                continue
            # Use the same extraction logic as in fetch_daily_word()
            match = re.search(r"<b><i>📚\s*(.*?)\s*</i></b>", message.text)
            if match:
                sent_words.append(match.group(1).strip())
    except Exception as e:
        logger.error(f"Error fetching channel messages: {e}")
        await bot.send_message(LOG_CHANNEL, f"⚠️ Vocab history fetch error: {str(e)[:500]}")
    return sent_words

def fetch_daily_word() -> tuple:
    """Original function remains completely unchanged"""
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a creative and charismatic English language expert with a knack for inspiring confident, effective communication who specializes in vocabulary and talks like a professional influential Figures. Every day, you generate a fresh, unique vocabulary word that will improve everyday interactions and help people speak more effectively. Generate vocabulary content with this EXACT format:

✨<b><i> Word Of The Day ! </i></b> ✨

<b><i>📚 [Word] </i></b>
━━━━━━━━━━━━━━━
<b><i>Meaning :</i></b>[Short definition] 

<b><i>💡 Think: </i></b>
[Short relatable example/analogy]

<b><i>🎯 Synonyms :</i></b>
<b>[Word1]:</b> [Brief explanation]
<b>[Word2]:</b> [Different angle]
<b>[Word3]:</b> [Unique take]

<b><i>📝 Antonyms: </i></b>
<b>[Word1] :</b> [Contrasting concept]
<b>[Word2] :</b> [Opposite perspective]
<b>[Word3] :</b> [Counterpart idea]

<b><i>See It In Action!🎬</i></b>
"[Practical example sentence]"

<b><i>🧭 Want more wonders? Explore:</i></b> ➡️ @Excellerators

"Formatting Rules:\n"
"- dont use [] in the content\n"
"""
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
        match = re.search(r"<b><i>📚\s*(.*?)\s*</i></b>", word_content)
        unique_word = match.group(1) if match else hashlib.md5(word_content.encode()).hexdigest()
        return (word_content, unique_word)
        
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        fallback_message = """✨ Level Up Your Lexicon! ✨
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
Want more word wonders? ➡️ @Excellerators"""
        return (fallback_message, f"fallback_{time.time()}")

async def send_scheduled_vocabulary(bot: Client):
    """Modified to use channel-based duplicate checking"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        target_times = [
            now.replace(hour=11, minute=30, second=0, microsecond=0),
            now.replace(hour=19, minute=30, second=0, microsecond=0)
        ]
        
        valid_times = [t for t in target_times if t > now]
        next_time = min(valid_times) if valid_times else target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next vocab at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_words = await get_sent_words_from_channel(bot)
            word_message, unique_word = fetch_daily_word()
            
            retry = 0
            while unique_word in sent_words and retry < 3:
                word_message, unique_word = fetch_daily_word()
                retry += 1
            
            await bot.send_message(
                chat_id=VOCAB_CHANNEL,
                text=word_message,
                disable_web_page_preview=True
            )
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📖 Vocab sent at {datetime.now(tz).strftime('%H:%M IST')}\nWord: {unique_word}"
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
        sent_words = await get_sent_words_from_channel(client)
        word_message, unique_word = fetch_daily_word()
        
        retry = 0
        while unique_word in sent_words and retry < 5:
            word_message, unique_word = fetch_daily_word()
            retry += 1
        
        await client.send_message(
            chat_id=VOCAB_CHANNEL,
            text=word_message,
            disable_web_page_preview=True
        )
        
        await processing_msg.edit("✅ Vocabulary published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"📖 Manual vocabulary sent\nWord: {unique_word}"
        )
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Vocab command failed: {str(e)[:500]}"
        )

def schedule_vocabulary(client: Client):
    """Unchanged scheduler function"""
    asyncio.create_task(send_scheduled_vocabulary(client))