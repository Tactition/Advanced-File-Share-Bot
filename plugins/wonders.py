import os
import logging
import random
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Optional
import html
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
MAX_STORED_WONDERS = 200

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

def fetch_wonders(count: int = 2) -> Optional[list]:
    """
    Fetches random wonders from API
    Returns list of wonder dicts or None
    """

    try:
        wonders = []
        for _ in range(count):
            response = requests.get(
                "https://www.world-wonders-api.org/v0/wonders/random",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Process images
            image_urls = data.get("links", {}).get("images", [])
            main_image = next((url for url in image_urls if url and url(url)), None)

            wonders.append({
                "id": str(data.get("name", str(time.time())) + str(time.time())),
                "name": data.get("name", "Unknown Wonder"),
                "summary": data.get("summary", "No description available"),
                "location": data.get("location", "Unknown Location"),
                "build_year": data.get("build_year", "N/A"),
                "time_period": data.get("time_period", "Unknown"),
                "image_url": main_image,
                "categories": ", ".join(data.get("categories", []))
            })
        return wonders
        
    except Exception as e:
        logger.error(f"Wonder API error: {e}")
        return None


async def send_wonder_post(bot: Client, wonder: dict):
    """Send wonder to channel with proper formatting"""
    caption = (
        f"🏛️ <b>{html.escape(wonder['name'])}</b>\n\n"
        f"📍 <b>Location:</b> {html.escape(wonder['location'])}\n"
        f"🏗️ <b>Built:</b> {wonder['build_year']} ({wonder['time_period']})\n"
        f"📌 <b>Categories:</b> {wonder['categories']}\n\n"
        f"{html.escape(wonder['summary'])}\n\n"
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
        logger.info(f"Next wonder post at {next_time.strftime('%H:%M IST')}")
        await asyncio.sleep(sleep_seconds)

        try:
            sent_ids = await load_sent_wonders()
            wonders = fetch_wonders(2) or []
            
            # Ensure we get exactly 2 unique wonders
            valid_wonders = []
            for wonder in wonders:
                if wonder['id'] not in sent_ids:
                    valid_wonders.append(wonder)
                    sent_ids.append(wonder['id'])
            
            # If we didn't get enough unique wonders, fetch more
            while len(valid_wonders) < 2:
                new_wonder = fetch_wonders(1)
                if new_wonder and new_wonder[0]['id'] not in sent_ids:
                    valid_wonders.append(new_wonder[0])
                    sent_ids.append(new_wonder[0]['id'])
            
            # Send posts with 1 minute interval
            for idx, wonder in enumerate(valid_wonders[:2]):
                await send_wonder_post(bot, wonder)
                if idx == 0:  # Add delay between posts
                    await asyncio.sleep(60)
            
            await save_sent_wonders(sent_ids)
            
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"🏛️ {len(valid_wonders)} wonders sent at {datetime.now(tz).strftime('%H:%M IST')}"
            )
            
        except Exception as e:
            logger.exception("Wonder broadcast failed:")

@Client.on_message(filters.command('wonders') & filters.user(ADMINS))
async def manual_wonder_handler(client, message: Message):
    try:
        processing_msg = await message.reply("⏳ Fetching wonders...")
        sent_ids = await load_sent_wonders()
        wonders = fetch_wonders(2) or []
        
        valid_wonders = []
        for wonder in wonders:
            if wonder['id'] not in sent_ids:
                valid_wonders.append(wonder)
                sent_ids.append(wonder['id'])
        
        if not valid_wonders:
            await processing_msg.edit("❌ No new wonders found")
            return
            
        for wonder in valid_wonders:
            await send_wonder_post(client, wonder)
            await asyncio.sleep(1)
        
        await save_sent_wonders(sent_ids)
        await processing_msg.edit(f"✅ {len(valid_wonders)} wonders published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"🏛️ Manual wonders sent: {', '.join(w['id'] for w in valid_wonders)}"
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

