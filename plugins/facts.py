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
import json
from validators import domain
from Script import script
from plugins.dbusers import db
from plugins.users_api import get_user, update_user_info, get_short_link
from Zahid.utils.file_properties import get_name, get_hash, get_media_file_size
from config import *
import hashlib

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


 # --------------------------------------------------

# File to store sent question IDs

import os
import logging
import random
import asyncio
import json
import hashlib
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Tuple

import requests
from pytz import timezone
from pyrogram import Client, filters, enums
from pyrogram.types import Message, PollOption
from pyrogram.errors import FloodWait


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
SENT_TRIVIA_FILE = "sent_trivia.json"
MAX_STORED_QUESTIONS = 300
IST = timezone('Asia/Kolkata')

async def load_sent_trivia() -> List[str]:
    """Load sent question IDs from file"""
    try:
        async with aiofiles.open(SENT_TRIVIA_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_trivia(question_ids: List[str]):
    """Save sent question IDs to file"""
    async with aiofiles.open(SENT_TRIVIA_FILE, "w") as f:
        await f.write(json.dumps(question_ids[-MAX_STORED_QUESTIONS:]))

def generate_question_id(question_text: str) -> str:
    """Generate SHA-256 hash of question text"""
    return hashlib.sha256(question_text.encode()).hexdigest()

def fetch_trivia_question() -> Tuple[str, List[PollOption], int, str, str, str]:
    """
    Fetches and formats trivia question for Telegram poll
    Returns: (question, options, correct_idx, category, difficulty, qid)
    """
    try:
        response = requests.get(
            "https://opentdb.com/api.php",
            params={
                "amount": 1,
                "category": 9,
                "type": "multiple",
                "encode": "url3986"
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        if data['response_code'] != 0 or not data['results']:
            raise ValueError("No results from API")

        question_data = data['results'][0]
        decoded = {
            'question': urllib.parse.unquote(question_data['question']),
            'correct': urllib.parse.unquote(question_data['correct_answer']),
            'incorrect': [urllib.parse.unquote(a) for a in question_data['incorrect_answers']],
            'category': urllib.parse.unquote(question_data['category']),
            'difficulty': urllib.parse.unquote(question_data['difficulty'])
        }

        # Prepare options
        options = decoded['incorrect'] + [decoded['correct']]
        random.shuffle(options)
        correct_idx = options.index(decoded['correct'])

        # Create PollOption objects with length validation
        poll_options = [
            PollOption(text=o[:100])
            for o in options
        ]

        return (
            decoded['question'][:255],  # Truncate to 255 chars
            poll_options,
            correct_idx,
            decoded['category'],
            decoded['difficulty'],
            generate_question_id(decoded['question'])
        )

    except Exception as e:
        logger.error(f"Trivia API error: {e}")
        # Fallback question
        return (
            "Which country is known as the Land of Rising Sun?",
            [
                PollOption(text="China"),
                PollOption(text="Japan"),
                PollOption(text="India"),
                PollOption(text="Thailand")
            ],
            1,
            "General Knowledge",
            "Easy",
            f"fallback_{time.time()}"
        )

async def send_scheduled_trivia(bot: Client):
    """Main scheduling loop for trivia polls"""
    while True:
        now = datetime.now(IST)
        target_times = [
            now.replace(hour=h, minute=0, second=0, microsecond=0)
            for h in [9, 13, 17, 21]  # 9AM, 1PM, 5PM, 9PM IST
        ]
        
        # Find next valid target time
        next_time = min(t for t in target_times if t > now) if any(t > now for t in target_times) \
            else target_times[0] + timedelta(days=1)

        sleep_duration = (next_time - now).total_seconds()
        logger.info(f"Next trivia scheduled for {next_time.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
        await asyncio.sleep(sleep_duration)

        try:
            sent_ids = await load_sent_trivia()
            question, options, correct_idx, category, difficulty, qid = fetch_trivia_question()

            # Retry mechanism for unique questions
            retry = 0
            while qid in sent_ids and retry < 5:
                question, options, correct_idx, category, difficulty, qid = fetch_trivia_question()
                retry += 1

            # Send the poll
            poll = await bot.send_poll(
                chat_id=TRIVIA_CHANNEL,
                question=question,
                options=options,
                is_anonymous=False,
                type=enums.PollType.QUIZ,
                correct_option_id=correct_idx,
                explanation=f"Category: {category}\nDifficulty: {difficulty.title()}"[:200],
                explanation_parse_mode=enums.ParseMode.MARKDOWN,
                close_date=datetime.now(IST) + timedelta(hours=24)
            )

            # Update sent questions
            sent_ids.append(qid)
            await save_sent_trivia(sent_ids)

            # Log success
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=(
                    f"✅ Trivia Poll Sent\n"
                    f"🕒 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n"
                    f"📝 {question[:75]}...\n"
                    f"🆔 {qid}\n"
                    f"📊 Poll ID: {poll.id}"
                )
            )

        except Exception as e:
            logger.exception("Failed to send scheduled trivia:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"❌ Scheduled Trivia Failed\nError: {str(e)[:500]}"
            )

@Client.on_message(filters.command('trivia') & filters.user(ADMINS))
async def manual_trivia(client: Client, message: Message):
    """Handle manual trivia command from admins"""
    processing_msg = None
    try:
        processing_msg = await message.reply("⏳ Generating trivia poll...")
        sent_ids = await load_sent_trivia()
        question, options, correct_idx, category, difficulty, qid = fetch_trivia_question()

        # Retry for unique question
        retry = 0
        while qid in sent_ids and retry < 5:
            question, options, correct_idx, category, difficulty, qid = fetch_trivia_question()
            retry += 1

        # Send poll
        poll = await client.send_poll(
            chat_id=TRIVIA_CHANNEL,
            question=question,
            options=options,
            is_anonymous=True,
            type=enums.PollType.QUIZ,
            correct_option_id=correct_idx,
            explanation=f"Category: {category}\nDifficulty: {difficulty.title()}"[:200],
            explanation_parse_mode=enums.ParseMode.MARKDOWN,
            close_date=datetime.now(IST) + timedelta(hours=24)
        )
        
        # Update sent questions
        sent_ids.append(qid)
        await save_sent_trivia(sent_ids)

        # Update processing message
        await processing_msg.edit("✅ Trivia poll published!")

        # Log success
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=(
                f"🎛 Manual Trivia Sent\n"
                f"👤 {message.from_user.mention}\n"
                f"📝 {question[:75]}...\n"
                f"🆔 {qid}\n"
                f"📊 Poll ID: {poll.id}"
            )
        )

    except Exception as e:
        error_msg = f"❌ Error: {type(e).__name__} - {str(e)[:200]}"
        if processing_msg:
            await processing_msg.edit(error_msg)
        else:
            await message.reply(error_msg)
        
        logger.exception("Manual trivia error:")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Manual Trivia Failed\nError: {repr(e)[:500]}"
        )

def start_scheduler(client: Client):
    """Initialize the trivia scheduler"""
    client.loop.create_task(send_scheduled_trivia(client))
