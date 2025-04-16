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

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
SENT_QUIZ_FILE = "sent_Quiz.json"
MAX_STORED_QUESTIONS = 300
IST = timezone('Asia/Kolkata')
QUESTIONS_PER_POST = 4

async def load_sent_Quiz() -> List[str]:
    """Load sent question IDs from file"""
    try:
        async with aiofiles.open(SENT_QUIZ_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_Quiz(question_ids: List[str]):
    """Save sent question IDs to file"""
    async with aiofiles.open(SENT_QUIZ_FILE, "w") as f:
        await f.write(json.dumps(question_ids[-MAX_STORED_QUESTIONS:]))

def generate_question_id(question_text: str) -> str:
    """Generate SHA-256 hash of question text"""
    return hashlib.sha256(question_text.encode()).hexdigest()

def fetch_Quiz_questions() -> List[Tuple[str, List[PollOption], int, str, str, str]]:
    """
    Fetches and formats 4 Quiz questions for Telegram polls
    Returns list of (question, options, correct_idx, category, difficulty, qid)
    """
    try:
        response = requests.get(
            "https://opentdb.com/api.php",
            params={
                "amount": QUESTIONS_PER_POST,
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

        questions = []
        for question_data in data['results']:
            decoded = {
                'question': urllib.parse.unquote(question_data['question']),
                'correct': urllib.parse.unquote(question_data['correct_answer']),
                'incorrect': [urllib.parse.unquote(a) for a in question_data['incorrect_answers']],
                'category': urllib.parse.unquote(question_data['category']),
                'difficulty': urllib.parse.unquote(question_data['difficulty'])
            }

            options = decoded['incorrect'] + [decoded['correct']]
            random.shuffle(options)
            correct_idx = options.index(decoded['correct'])

            poll_options = [PollOption(text=o[:100]) for o in options]
            
            questions.append((
                decoded['question'][:255],
                poll_options,
                correct_idx,
                decoded['category'],
                decoded['difficulty'],
                generate_question_id(decoded['question'])
            ))
        
        return questions

    except Exception as e:
        logger.error(f"Quiz API error: {e}")
        # Fallback: 4 different questions
        return [
            (
                "Which country is known as the Land of Rising Sun?",
                [PollOption(text="China"), PollOption(text="Japan"), PollOption(text="India"), PollOption(text="Thailand")],
                1,
                "General Knowledge",
                "Easy",
                f"fallback_1_{time.time()}"
            ),
            (
                "What is the capital of France?",
                [PollOption(text="London"), PollOption(text="Berlin"), PollOption(text="Paris"), PollOption(text="Madrid")],
                2,
                "Geography",
                "Medium",
                f"fallback_2_{time.time()}"
            ),
            (
                "Who painted the Mona Lisa?",
                [PollOption(text="Van Gogh"), PollOption(text="Picasso"), PollOption(text="Da Vinci"), PollOption(text="Rembrandt")],
                2,
                "Art",
                "Hard",
                f"fallback_3_{time.time()}"
            ),
            (
                "What is H2O?",
                [PollOption(text="Gold"), PollOption(text="Water"), PollOption(text="Salt"), PollOption(text="Oxygen")],
                1,
                "Science",
                "Easy",
                f"fallback_4_{time.time()}"
            )
        ]

async def send_quiz_poll(client, chat_id, question_data) -> Message:
    """Helper to send individual polls"""
    try:
        return await client.send_poll(
            chat_id=chat_id,
            question=question_data[0],
            options=question_data[1],
            is_anonymous=True,
            type=enums.PollType.QUIZ,
            correct_option_id=question_data[2],
            explanation=f"Category: {question_data[3]}\nDifficulty: {question_data[4].title()}"[:200],
            explanation_parse_mode=enums.ParseMode.MARKDOWN,
            is_closed=False
        )
    except Exception as e:
        logger.error(f"Failed to send poll: {e}")
        return None

async def process_questions(bot, questions, sent_ids):
    """Process and send multiple questions"""
    new_ids = []
    sent_polls = []
    
    for question_data in questions:
        question, _, _, _, _, qid = question_data
        retry = 0
        
        while qid in sent_ids and retry < 3:
            # Fetch replacement question
            try:
                new_questions = fetch_Quiz_questions(1)
                if new_questions:
                    question_data = new_questions[0]
                    qid = question_data[5]
                    retry += 1
            except Exception as e:
                logger.error(f"Retry failed: {e}")
                break

        if qid not in sent_ids:
            poll = await send_quiz_poll(bot, QUIZ_CHANNEL, question_data)
            if poll:
                new_ids.append(qid)
                sent_polls.append(poll)
                await asyncio.sleep(1)  # Rate limit protection

    return new_ids, sent_polls

async def send_scheduled_Quiz(bot: Client):
    """Main scheduling loop for Quiz polls"""
    while True:
        now = datetime.now(IST)
        target_times = [
            now.replace(hour=h, minute=0, second=0, microsecond=0)
            for h in [9, 13, 17, 21]  # 9AM, 1PM, 5PM, 9PM IST
        ]
        
        next_time = min(t for t in target_times if t > now) if any(t > now for t in target_times) \
            else target_times[0] + timedelta(days=1)

        sleep_duration = (next_time - now).total_seconds()
        logger.info(f"Next Quiz scheduled for {next_time.astimezone(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
        await asyncio.sleep(sleep_duration)

        try:
            sent_ids = await load_sent_Quiz()
            questions = fetch_Quiz_questions()

            new_ids, sent_polls = await process_questions(bot, questions, sent_ids)
            
            if new_ids:
                sent_ids.extend(new_ids)
                await save_sent_Quiz(sent_ids)

                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text=(
                        f"✅ {len(new_ids)} Quiz Polls Sent\n"
                        f"🕒 {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}\n"
                        f"📝 Sample: {questions[0][0][:50]}...\n"
                        f"🆔 IDs: {', '.join(qid[:6] for qid in new_ids[:3])}..."
                    )
                )
            else:
                await bot.send_message(
                    chat_id=LOG_CHANNEL,
                    text="❌ Failed to send any Quiz polls"
                )

        except Exception as e:
            logger.exception("Failed to send scheduled Quiz:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"❌ Scheduled Quiz Failed\nError: {str(e)[:500]}"
            )

@Client.on_message(filters.command('Quiz') & filters.user(ADMINS))
async def manual_Quiz(client: Client, message: Message):
    """Handle manual Quiz command from admins"""
    processing_msg = None
    try:
        processing_msg = await message.reply(f"⏳ Generating {QUESTIONS_PER_POST} Quiz polls...")
        sent_ids = await load_sent_Quiz()
        questions = fetch_Quiz_questions()

        new_ids, sent_polls = await process_questions(client, questions, sent_ids)
        
        if new_ids:
            sent_ids.extend(new_ids)
            await save_sent_Quiz(sent_ids)
            await processing_msg.edit(f"✅ {len(new_ids)} Quiz polls published!")

            await client.send_message(
                chat_id=LOG_CHANNEL,
                text=(
                    f"🎛 Manual Quiz Sent\n"
                    f"👤 {message.from_user.mention}\n"
                    f"📝 {len(new_ids)} polls\n"
                    f"🆔 IDs: {', '.join(qid[:6] for qid in new_ids[:3])}..."
                )
            )
        else:
            await processing_msg.edit("❌ Failed to send any polls")
            await client.send_message(
                chat_id=LOG_CHANNEL,
                text=f"⚠️ Manual Quiz Failed by {message.from_user.mention}"
            )

    except Exception as e:
        error_msg = f"❌ Error: {type(e).__name__} - {str(e)[:200]}"
        if processing_msg:
            await processing_msg.edit(error_msg)
        else:
            await message.reply(error_msg)
        
        logger.exception("Manual Quiz error:")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Manual Quiz Failed\nError: {repr(e)[:500]}"
        )

def quiz_scheduler(client: Client):
    """Initialize the Quiz scheduler"""
    client.loop.create_task(send_scheduled_Quiz(client))