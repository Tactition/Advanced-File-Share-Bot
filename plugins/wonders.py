import os
import logging
import random
import asyncio
import json
import hashlib
import html
import time
from datetime import datetime, timedelta

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

# File to store sent wonder IDs
SENT_WONDERS_FILE = "sent_wonders.json"
MAX_STORED_WONDERS = 200  # Keep last 200 IDs

async def load_sent_wonders() -> list:
    """Load sent wonder IDs from file"""
    try:
        async with aiofiles.open(SENT_WONDERS_FILE, "r") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_wonders(wonder_ids: list):
    """Save sent wonder IDs to file"""
    async with aiofiles.open(SENT_WONDERS_FILE, "w") as f:
        await f.write(json.dumps(wonder_ids[-MAX_STORED_WONDERS:]))

def fetch_wonder() -> dict:
    """
    Fetches a random wonder from API
    Returns dict with wonder data
    """
    try:
        response = requests.get(
            "https://www.world-wonders-api.org/v0/wonders/random",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Truncate long descriptions
        description = data.get("description", "")
        if len(description) > 1000:
            description = description[:997] + "..."

        return {
            "id": str(data.get("id", time.time())),
            "name": data.get("name", "Unknown Wonder"),
            "location": data.get("location", "Unknown Location"),
            "description": description,
            "image_url": data.get("imageUrl", "")
        }
    except Exception as e:
        logger.error(f"Wonder API error: {e}")
        # Fallback data
        return {
            "id": f"fallback_{time.time()}",
            "name": "Great Pyramid of Giza",
            "location": "Giza, Egypt",
            "description": "The oldest and largest of the three pyramids in the Giza pyramid complex bordering El Giza, Egypt.",
            "image_url": "https://example.com/pyramid.jpg"
        }

async def send_wonder_post(bot: Client, wonder: dict):
    """Send wonder to channel with proper formatting"""
    caption = (
        f"🏛️ <b>{html.escape(wonder['name'])}</b>\n\n"
        f"📍 <b>Location:</b> {html.escape(wonder['location'])}\n\n"
        f"{html.escape(wonder['description'])}\n\n"
        "🌍 Explore more wonders @Excellerators"
    )

    try:
        if wonder['image_url'] and url(wonder['image_url']):
            await bot.send_photo(
                chat_id=WONDERS_CHANNEL,
                photo=wonder['image_url'],
                caption=caption,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await bot.send_message(
                chat_id=WONDERS_CHANNEL,
                text=caption,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Failed to send wonder: {e}")
        await bot.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Failed to send wonder {wonder['id']}: {str(e)[:500]}"
        )

async def send_scheduled_wonders(bot: Client):
    """Send scheduled wonders with duplicate prevention"""
    tz = timezone('Asia/Kolkata')
    
    while True:
        now = datetime.now(tz)
        # Send at 9 AM and 9 PM IST
        target_times = [
            now.replace(hour=9, minute=0, second=0, microsecond=0),
            now.replace(hour=21, minute=0, second=0, microsecond=0)
        ]
        
        valid_times = [t for t in target_times if t > now]
        next_time = min(valid_times) if valid_times else target_times[0] + timedelta(days=1)
        
        sleep_seconds = (next_time - now).total_seconds()
        logger.info(f"Next wonder at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_wonders()
            wonder = fetch_wonder()
            
            # Retry for unique wonder
            retry = 0
            while wonder['id'] in sent_ids and retry < 5:
                wonder = fetch_wonder()
                retry += 1
            
            await send_wonder_post(bot, wonder)
            sent_ids.append(wonder['id'])
            await save_sent_wonders(sent_ids)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"🏛️ Wonder sent at {datetime.now(tz).strftime('%H:%M IST')}\nID: {wonder['id']}"
            )
            
        except Exception as e:
            logger.exception("Wonder broadcast failed:")

@Client.on_message(filters.command('wonders') & filters.user(ADMINS))
async def manual_wonder_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Fetching wonder...")
        sent_ids = await load_sent_wonders()
        wonder = fetch_wonder()
        
        # Retry for unique wonder
        retry = 0
        while wonder['id'] in sent_ids and retry < 5:
            wonder = fetch_wonder()
            retry += 1
        
        await send_wonder_post(client, wonder)
        sent_ids.append(wonder['id'])
        await save_sent_wonders(sent_ids)
        
        await processing_msg.edit("✅ Wonder published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"🏛️ Manual wonder sent\nID: {wonder['id']}"
        )
        
    except Exception as e:
        await processing_msg.edit(f"❌ Error: {str(e)[:200]}")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Wonder command failed: {str(e)[:500]}"
        )

def schedule_wonders(client: Client):
    """Starts the wonders scheduler"""
    asyncio.create_task(send_scheduled_wonders(client))