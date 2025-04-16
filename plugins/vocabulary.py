import os
import logging
import random
import asyncio
import json
import hashlib
import tempfile
from datetime import datetime, timedelta
from typing import Tuple

import requests
from pytz import timezone
from groq import Groq
from gtts import gTTS
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import FloodWait

import aiofiles
from config import *

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Groq Client Configuration
groq_client = Groq(api_key="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")

# Vocabulary Plugin Configuration
SENT_WORDS_FILE = "sent_words.json"
MAX_STORED_WORDS = 200
TEMP_AUDIO_DIR = "temp_pronunciation"

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

async def generate_pronunciation(word: str) -> str:
    """Generate audio pronunciation using gTTS"""
    try:
        os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)
        clean_word = re.sub(r'[^a-zA-Z-]', '', word).lower()
        file_path = os.path.join(TEMP_AUDIO_DIR, f"{clean_word}.mp3")
        
        # Generate only if not exists
        if not os.path.exists(file_path):
            tts = gTTS(text=word, lang='en', tld='com', slow=False)
            tts.save(file_path)
        
        return file_path
    except Exception as e:
        logger.error(f"Pronunciation generation failed: {str(e)}")
        return None

async def fetch_daily_word() -> Tuple[str, str, str]:
    """
    Fetches random vocabulary word with audio
    Returns (formatted_word, word_id, audio_path)
    """
    try:
        response = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": """You are a creative English language expert. Generate vocabulary content with this EXACT format:

✨<b><i> Word Of The Day ! </i></b> ✨

<b><i>📚 [Word] (part-of-speech)</i></b>
━━━━━━━━━━━━━━━
<b><i>Meaning :</i></b>[Concise definition] 

<b><i>💡 Think: </i></b>
[Relatable analogy/example]

<b><i>🎯 Synonyms :</i></b>
<b>[Syn1]:</b> [Brief context]
<b>[Syn2]:</b> [Different nuance]
<b>[Syn3]:</b> [Specialized usage]

<b><i>📝 Antonyms: </i></b>
<b>[Ant1]:</b> [Direct opposite]
<b>[Ant2]:</b> [Contextual contrast]
<b>[Ant3]:</b> [Conceptual inverse]

<b><i>See It In Action!🎬</i></b>
"[Real-world example sentence]"

<b><i>🧭 Want more wonders? Explore:</i></b> ➡️ @Excellerators"""
                },
                {
                    "role": "user",
                    "content": "Generate a fresh vocabulary entry with part-of-speech. Focus on contemporary usage and clear distinctions between similar terms."
                }
            ],
            model="llama3-70b-8192",
            temperature=1.2,
            max_tokens=400,
            stream=False
        )
        
        word_content = response.choices[0].message.content
        word_hash = hashlib.md5(word_content.encode()).hexdigest()
        
        # Extract base word from content
        word_line = next(line for line in word_content.split('\n') if '📚' in line)
        word = re.search(r'📚\s*(.*?)\s*\(', word_line).group(1).strip()
        
        # Generate pronunciation
        audio_path = await generate_pronunciation(word)
        
        return (word_content, word_hash, audio_path)
        
    except Exception as e:
        logger.error(f"Groq API error: {str(e)}")
        fallback_word = "Serendipity"
        return (
            f"""✨<b><i> Word Of The Day ! </i></b> ✨

<b><i>📚 {fallback_word} (noun)</i></b>
━━━━━━━━━━━━━━━
<b><i>Meaning :</i></b>The occurrence of fortunate discoveries by accident 🍀

<b><i>💡 Think: </i></b>
Finding money in old jeans while doing laundry 👖

<b><i>🎯 Synonyms :</i></b>
<b>Fortuity:</b> Chance occurrence 
<b>Kismet:</b> Destiny's role 
<b>Happenstance:</b> Random coincidence 

<b><i>📝 Antonyms: </i></b>
<b>Planning:</b> Intentional design 
<b>Calculation:</b> Precise intention 
<b>Predictability:</b> Expected outcome 

<b><i>See It In Action!🎬</i></b>
"Through pure serendipity, I discovered my favorite café while lost in a new city." ☕️

<b><i>🧭 Want more wonders? Explore:</i></b> ➡️ @Excellerators""",
            f"fallback_{time.time()}",
            await generate_pronunciation(fallback_word)
        )

async def send_scheduled_vocabulary(bot: Client):
    """Send scheduled vocabulary with pronunciation"""
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
        logger.info(f"Next vocabulary post at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_words()
            word_content, word_id, audio_path = await fetch_daily_word()
            
            # Retry for unique word
            retry = 0
            while word_id in sent_ids and retry < 3:
                word_content, word_id, audio_path = await fetch_daily_word()
                retry += 1
            
            # Send text content
            text_message = await bot.send_message(
                chat_id=VOCAB_CHANNEL,
                text=word_content,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            
            # Send pronunciation audio
            if audio_path and os.path.exists(audio_path):
                await bot.send_voice(
                    chat_id=VOCAB_CHANNEL,
                    voice=audio_path,
                    caption=f"🔊 Pronunciation of today's word",
                    reply_to_message_id=text_message.id
                )
            
            # Cleanup and logging
            sent_ids.append(word_id)
            await save_sent_words(sent_ids)
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📖 Vocabulary posted at {datetime.now(tz).strftime('%H:%M IST')}\nID: {word_id}"
            )
            
        except Exception as e:
            logger.exception("Vocabulary broadcast failed:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"⚠️ Vocabulary post failed: {str(e)[:500]}"
            )

@Client.on_message(filters.command('vocab') & filters.user(ADMINS))
async def instant_vocab_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Crafting unique vocabulary post...")
        sent_ids = await load_sent_words()
        word_content, word_id, audio_path = await fetch_daily_word()
        
        # Retry for unique word
        retry = 0
        while word_id in sent_ids and retry < 5:
            word_content, word_id, audio_path = await fetch_daily_word()
            retry += 1
        
        # Send content
        text_message = await client.send_message(
            chat_id=VOCAB_CHANNEL,
            text=word_content,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        # Send pronunciation
        if audio_path and os.path.exists(audio_path):
            await client.send_voice(
                chat_id=VOCAB_CHANNEL,
                voice=audio_path,
                caption=f"🔊 Pronunciation of today's word",
                reply_to_message_id=text_message.id
            )
        
        # Update records
        sent_ids.append(word_id)
        await save_sent_words(sent_ids)
        await processing_msg.edit("✅ Vocabulary published with pronunciation!")
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
    """Initialize vocabulary scheduler"""
    asyncio.create_task(send_scheduled_vocabulary(client))