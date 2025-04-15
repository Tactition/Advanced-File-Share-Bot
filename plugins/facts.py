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


def fetch_daily_facts() -> str:
    """
    Fetches 3 random facts from the Random Useless Facts API
    """
    try:
        facts = set()
        attempt = 0
        
        # Try to get 3 unique facts with fallback
        while len(facts) < 3 and attempt < 5:
            response = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random", 
                                  headers={'Accept': 'application/json'}, 
                                  timeout=10)
            response.raise_for_status()
            fact_data = response.json()
            
            # Clean HTML tags and special characters
            clean_fact = re.sub('<[^<]+?>', '', fact_data['text'])  # Remove HTML tags
            clean_fact = html.unescape(clean_fact)  # Convert HTML entities
            facts.add(clean_fact)
            attempt += 1
        
        # Format the facts list
        formatted_facts = [f"✦ {fact.strip()}" for fact in list(facts)[:3]]
        
        # If we couldn't get 3 unique facts, fill with fallbacks
        while len(formatted_facts) < 3:
            formatted_facts.append("✦ The average cloud weighs about 1.1 million pounds")
            
        fact_message = (
            "🧠 **Daily Knowledge Boost Facts**\n\n"
            "\n\n".join(formatted_facts) + 
            "\n\n━━━━━━━━━━━━━━━━━━━\n"
            "Stay Curious! @Excellerators"
        )
        return fact_message
        
    except Exception as e:
        logger.error(f"Fact API error: {e}")
        return (
            "💡 **Did You Know?**\n\n"
            "✦ The human brain generates about 20 watts of electricity\n"
            "✦ Honey never spoils - edible after 3000 years!\n"
            "✦ Octopuses have three hearts\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Learn more @Excellerators"
        )

# Modified sender function for 3x daily facts
async def send_scheduled_facts(bot: Client):
    """
    Sends facts daily at 8 AM, 1 PM, and 8 PM IST
    """
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        
        # Today's target times (8:00, 13:00, 20:00)
        target_times = [
            now.replace(hour=8, minute=0, second=0, microsecond=0),
            now.replace(hour=13, minute=0, second=0, microsecond=0),
            now.replace(hour=20, minute=0, second=0, microsecond=0)
        ]
        
        # Find next valid time
        next_time = min(t for t in target_times if t > now)
        if not any(t > now for t in target_times):
            # All today's times passed, use first tomorrow
            next_time = target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        human_time = next_time.strftime("%d %b %Y at %I:%M %p")
        
        logger.info(
            f"⏰ Next fact broadcast: {human_time} IST\n"
            f"💤 Sleeping for {sleep_seconds//3600:.0f}h {(sleep_seconds%3600)//60:.0f}m"
        )
        
        await asyncio.sleep(sleep_seconds)
        
        try:
            fact_message = fetch_daily_facts()
            # Send only to channels
            await bot.send_message(
                chat_id=FACTS_CHANNEL,
                text=fact_message,
                disable_web_page_preview=True
            )
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📚 Daily facts sent at {datetime.now(tz).strftime('%H:%M IST')}\n\n{fact_message}",
                disable_web_page_preview=True
            )
            logger.info(f"Successfully sent facts to channel at {next_time.strftime('%H:%M IST')}")
            
        except Exception as e:
            logger.exception("Fact broadcast failed:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"❌ Fact broadcast failed at {datetime.now(tz).strftime('%H:%M')}:\n{str(e)}"
            )


@Client.on_message(filters.command('facts') & filters.user(ADMINS))
async def instant_facts_handler(client, message: Message):
    """
    Handles /facts command to immediately fetch and send 3 facts to the channel
    """
    try:
        # Send processing status
        processing_msg = await message.reply("🔍 Fetching fresh knowledge nuggets...")
        
        # Fetch new facts
        fact_message = fetch_daily_facts()
        
        # Send to quote channel
        await client.send_message(
            chat_id=QUOTE_CHANNEL,
            text=fact_message,
            disable_web_page_preview=True
        )
        
        # Update status and log
        await processing_msg.edit("✅ Facts successfully published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"📚 Facts sent manually by {message.from_user.mention}\n\n{fact_message}",
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.exception("Facts Command Error:")
        error_msg = f"❌ Failed to fetch facts: {str(e)[:200]}"
        await processing_msg.edit(error_msg)
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Facts Command Failed by {message.from_user.mention}:\n{error_msg}"
        )

# Update the scheduler initialization
def schedule_all_content(client: Client):
    """
    Starts  and fact schedulers
    """
    # New fact scheduler
    asyncio.create_task(send_scheduled_facts(client))
