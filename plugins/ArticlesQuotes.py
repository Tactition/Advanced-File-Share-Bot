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

# Import Groq library (make sure to set GROQ_API_KEY as an environment variable)
from groq import Groq

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# =============================
# DAILY QUOTE AUTO-SENDER FUNCTIONALITY
# =============================

def fetch_random_quote() -> str:
    """
    Fetches inspirational quotes with fallback from ZenQuotes to FavQs API.
    Maintains consistent formatting across sources.
    """
    try:
        # First try ZenQuotes API
        response = requests.get("https://zenquotes.io/api/random", timeout=10)
        response.raise_for_status()
        data = response.json()[0]
        
        quote = (
            "🔥 **Fuel for Your Morning to Conquer The Day Ahead**\n\n"
            f"\"{data['q']}\"\n"
            f"― {data['a']}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Explore our @Excellerators Empire And Build Your Mindset"
        )
        logger.info("Successfully fetched from ZenQuotes")
        return quote
        
    except Exception as zen_error:
        logger.warning(f"ZenQuotes failed: {zen_error}, trying FavQs...")
        try:
            # Fallback to FavQs API
            response = requests.get("https://favqs.com/api/qotd", timeout=10)
            response.raise_for_status()
            data = response.json()
            quote_data = data.get("quote", {})
            
            quote = (
                "🔥 **Fuel for Your Morning to Conquer The Day Ahead**\n\n"
                f"\"{quote_data.get('body', 'Stay inspired!')}\"\n"
                f"― {quote_data.get('author', 'Unknown')}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "Explore daily wisdom @Excellerators"
            )
            logger.info("Successfully fetched from FavQs")
            return quote
            
        except Exception as favq_error:
            logger.error(f"Both APIs failed: {favq_error}")
            return (
                "🌱 **Your Growth Journey**\n\n"
                "Every small step moves you forward. Keep going!\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "Join our @Excellerators Empire And Build Your Mindset"
            )

async def delete_message_after(bot: Client, chat_id: int, message_id: int, delay: int):
    """
    Waits for a specified delay and then attempts to delete a message.
    """
    await asyncio.sleep(delay)
    try:
        await bot.delete_messages(chat_id=chat_id, message_ids=message_id)
        logger.info(f"Deleted message {message_id} in chat {chat_id} after {delay} seconds")
    except Exception as e:
        logger.exception(f"Error deleting message {message_id} in chat {chat_id}:")

async def send_daily_quote(bot: Client):
    """
    Sends a daily motivational quote to all users and logs the broadcast details.
    The quote messages in the users' DMs are automatically deleted after a specified delay.
    """
    while True:
        # Calculate time until next scheduled sending time (set here to 10:47 IST, adjust as needed)
        tz = timezone('Asia/Kolkata')
        now = datetime.now(tz)
        target_time = now.replace(hour=7, minute=14, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)
            status_msg = "⏱ Next quote scheduled for tomorrow at 22:47 IST"
        else:
            status_msg = f"⏱ Next quote scheduled today at {target_time.strftime('%H:%M:%S')} IST"
        
        # Calculate sleep duration with better formatting
        sleep_duration = (target_time - now).total_seconds()
        sleep_hours = sleep_duration // 3600
        sleep_minutes = (sleep_duration % 3600) // 60
        
        logger.info(
            f"{status_msg}\n"
            f"💤 Sleeping for {sleep_hours:.0f} hours {sleep_minutes:.0f} minutes "
            f"({sleep_duration:.0f} seconds)"
        )
        
        await asyncio.sleep(sleep_duration)

        # Rest of the original function remains unchanged
        logger.info("Scheduled time reached! Sending daily quote...")
        try:
            users_cursor = await db.get_all_users()  # Async cursor for users with {'name': {'$exists': True}}
            total_users = await db.col.count_documents({'name': {'$exists': True}})
            quote_message = fetch_random_quote()

            # Send the quote to the main quote channel and log channel
            await bot.send_message(chat_id=QUOTE_CHANNEL, text=quote_message)
            await bot.send_message(chat_id=LOG_CHANNEL, text=f"📢 Sending daily quote from Audiobooks Bot:\n\n{quote_message}")

            sent = blocked = deleted = failed = 0
            done = 0
            start_time = time.time()

            async for user in users_cursor:
                if 'id' not in user or 'name' not in user:
                    continue  # Skip users with missing details
                user_id = int(user['id'])
                try:
                    # Send the quote message and then schedule its deletion after QUOTE_DELETE_DELAY seconds
                    msg = await bot.send_message(chat_id=user_id, text=quote_message)
                    asyncio.create_task(delete_message_after(bot, user_id, msg.id, QUOTE_DELETE_DELAY))
                    sent += 1
                    # Wait for a short interval between scheduling each deletion task
                    await asyncio.sleep(DELETION_INTERVAL)
                except FloodWait as e:
                    logger.info(f"Flood wait for {e.value} seconds for user {user_id}")
                    await asyncio.sleep(e.value)
                    continue
                except InputUserDeactivated:
                    await db.delete_user(user_id)
                    deleted += 1
                except UserIsBlocked:
                    await db.delete_user(user_id)
                    blocked += 1
                except PeerIdInvalid:
                    await db.delete_user(user_id)
                    failed += 1
                except Exception as e:
                    failed += 1
                    logger.exception(f"Error sending to {user_id}:")
                done += 1
                if done % 20 == 0:
                    logger.info(f"Progress: {done}/{total_users} | Sent: {sent} | Blocked: {blocked} | Deleted: {deleted} | Failed: {failed}")
            
            broadcast_time = timedelta(seconds=int(time.time() - start_time))
            summary = (
                f"✅ Daily Quote Broadcast Completed in {broadcast_time}\n\n"
                f"Total Users: {total_users}\n"
                f"Sent: {sent}\n"
                f"Blocked: {blocked}\n"
                f"Deleted: {deleted}\n"
                f"Failed: {failed}\n\n"
                f"Quote Sent:\n{quote_message}"
            )
            logger.info(summary)
            await bot.send_message(chat_id=LOG_CHANNEL, text=summary)
        except Exception as e:
            logger.exception("Error retrieving users from database:")
            await bot.send_message(chat_id=LOG_CHANNEL, text=f"Error retrieving users: {e}")
    


def schedule_daily_quotes(client: Client):
    """
    Starts the daily quote broadcast scheduler.
    """
    asyncio.create_task(send_daily_quote(client))


# =============================
# DAILY ARTICLE FUNCTIONALITY
# =============================

SENT_POSTS_FILE = "sent_posts.json"
MAX_POSTS_TO_FETCH = 100

async def load_sent_posts() -> list:
    """
    Asynchronously load sent post IDs from file.
    """
    try:
        async with aiofiles.open(SENT_POSTS_FILE, mode="r") as f:
            contents = await f.read()
            return json.loads(contents)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

async def save_sent_posts(sent_post_ids: list):
    """
    Asynchronously save sent post IDs to file.
    """
    async with aiofiles.open(SENT_POSTS_FILE, mode="w") as f:
        await f.write(json.dumps(sent_post_ids[-MAX_POSTS_TO_FETCH:]))


async def get_random_unseen_post() -> dict:
    """
    Fetch random post with varying API parameters for diversity
    """
    sent_post_ids = await load_sent_posts()
    try:
        # First try with randomized parameters
        params = {
            "per_page": MAX_POSTS_TO_FETCH,
            "orderby": random.choice(['date', 'modified', 'title', 'id']),
            "order": random.choice(['asc', 'desc']),
            "page": random.randint(1, 7),  # Assumes max 5 pages
            "_": int(time.time())  # Cache busting
        }
        
        logger.info(f"Trying randomized params: {params}")
        response = requests.get(
            "https://www.franksonnenbergonline.com/wp-json/wp/v2/posts",
            params=params,
            timeout=15
        )
        
        response.raise_for_status()
        logger.info(f"Fetching posts from Radomized param URL each param is diffrent on api call: {response.url}")
        posts = response.json()

        # Fallback to default params if no results
        if not posts:
            logger.info("No posts with random params, trying defaults")
            params = {
                "per_page": MAX_POSTS_TO_FETCH,
                "orderby": "date",
                "order": "desc",
                "page": 1,
                "_": int(time.time())
            }
            response = requests.get(
                "https://www.franksonnenbergonline.com/wp-json/wp/v2/posts",
                params=params,
                timeout=15
            )
            response.raise_for_status()
            logger.info(f"Fetching posts from default Param not random Params but all Params URL: {response.url}")
            posts = response.json()

        # Existing filtering logic
        unseen_posts = [p for p in posts if p['id'] not in sent_post_ids]
        
        if not unseen_posts:
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            if params['page'] < total_pages:
                new_params = params.copy()
                new_params['page'] += 1
                return await get_random_unseen_post()
            else:
                logger.info("Resetting seen posts")
                sent_post_ids.clear()
                unseen_posts = posts

        selected_post = random.choice(unseen_posts)
        sent_post_ids.append(selected_post['id'])
        await save_sent_posts(sent_post_ids)

        return selected_post

    except Exception as e:
        logger.error(f"Initial attempt failed: {e}")
        try:  # Final fallback to default API call
            logger.info("Attempting standard API call")
            response = requests.get(
                "https://www.franksonnenbergonline.com/wp-json/wp/v2/posts",
                params={
                    "per_page": MAX_POSTS_TO_FETCH,
                    "orderby": "date",
                    "order": "desc"
                },
                timeout=15
            )
            response.raise_for_status()
            logger.info(f"Fetching posts from default URL with default Param: {response.url}")
            posts = response.json()
            
            # Existing filtering logic
            unseen_posts = [p for p in posts if p['id'] not in sent_post_ids]
            # ... rest of filtering logic
            
            return selected_post
            
        except Exception as final_error:
            logger.exception("Complete failure in post fetching:")
            return None


def clean_content(content: str) -> str:
    """
    Clean HTML content using BeautifulSoup, removing unwanted tags and comments,
    then normalize the text. (Note: This still collapses to a single paragraph.)
    """
    try:
        soup = BeautifulSoup(content, 'html.parser')
        # Remove unwanted elements
        for tag in soup(["script", "style", "meta", "link", "nav", "footer", "aside"]):
            tag.decompose()
        # Remove comments
        for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
            comment.extract()
        text = soup.get_text()
        # Normalize whitespace (if you wish to preserve multiple paragraphs, consider removing this join)
        text = ' '.join(text.split())
        text = re.sub(r'\s+([.,!?])', r'\1', text)
        text = re.sub(r'([.,!?])\s*', r'\1 ', text)
        return text.strip()
    except Exception as e:
        logger.exception("Error cleaning content:")
        return content

def paraphrase_content(text: str, bot: Client) -> tuple:
    """
    Sends the cleaned content to Groq API for paraphrasing and title generation.
    The API response should start with "Title:" followed by the generated title,
    then an empty line, and then the paraphrased article along with key insights.
    Returns a tuple: (generated_title, generated_body).
    """
    try:
        # Log original content
        asyncio.create_task(
            bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📨 <b>Original Content Sent:</b>\n<pre>{html.escape(text[:3000])}</pre>",
                parse_mode=enums.ParseMode.HTML
            )
        )

        groq_api_key = os.getenv("groq_api_key","")
        if not groq_api_key:
            raise ValueError("Groq API key not found in environment variables")
        
        client_groq = Groq(api_key=groq_api_key)

        # Construct a clearer prompt with proper spacing and explicit requirements
        system_prompt_old = (
            "Rewrite this article in a motivational, inspirational, and persuasive manner the overall output must be between 1400 to 1700 characters "
            "Incorporate one quote or little paraphrased idea from renowned figures or Philosphers to support the article based on the context "
            "Encourage self-analysis and leveraging inherent strengths."
            "Format your response so that the first line starts with 'Title:' followed by your generated title, Also the generated title should be unique, attractive, hooky title for the article. then an empty line, and then the article text in multiple paragraphs and then some key insights or acton points from the article in bullet Points prefixed by emojies 🌟 to Sum up the article "
            "Remember the key insights or acton points heading must be bolded with Html <b> tag there should be a line break after the bolded heading of key insights or acton points and you will not give any Feedback releated to generated respose "
        )

        
        system_prompt = (
            "Rephrase the content following this EXACT structure:\n\n"
            
            "<b>[Emoji] Title Text</b> (Max 7 words)\n"
            "   Example: <b>🔥 Igniting the Spark: Unleash Greatness in Everyone</b>\n\n"
            
            "<blockquote><i>[Philosopher Quote]</i> — <b>[Philosopher Name]</b></blockquote>\n"
            "(Select quotes from Aristotle, Nietzsche, Plato, Socrates or other philosophers)\n\n"
            
            "Core Content (2-3 paragraphs, 1-2 lines each in motivational, inspirational, and persuasive manner):\n"
            "   - First paragraph: State core philosophy\n"
            "   - Second paragraph: Ask rhetorical question\n"
            "   - Third paragraph: Include real-world example\n\n"
            
            "<b>3 Pillars of [Theme]:</b>\n"
            "   🔹 <b>Principle 1</b>: Concise implementation\n"
            "   🔹 <b>Principle 2</b>: Concise implementation\n"
            "   🔹 <b>Principle 3</b>: Concise implementation\n\n"
            
            "<b><u>Actionable Insights:</u></b>\n"
            "   🌟 <b>Insight 1:</b> Specific action\n"
            "   🌟 <b>Insight 2:</b> Specific action\n"
            "   🌟 <b>Insight 3:</b> Specific action\n\n"
            
            "Closing Format:\n"
            "✨ [Motivational closing statement]\n\n"
            "[3 relevant hashtags]\n"
            
            "Formatting Rules:\n"
            "- Use ONLY these HTML tags: <b>, <i>, <u>, <blockquote>\n"
            "- Maintain 1400-1700 character limit\n"
            "-🔹 for principles / 🌟 for insights\n"
            "- No markdown, only <b>, <i>, <blockquote> tags\n"
            "- 1 emoji in title (🔥/🌟/✨/📚) \n"
            "- Conversational yet authoritative tone\n"
            "- Include 1 rhetorical question\n"
            "- Use Oxford commas and semicolons\n"
            "- Philosophical foundation in every section"
        
        )




        response = client_groq.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            model="llama-3.3-70b-versatile",
            stream=False,
        )

        if response.choices[0].message.content:
            paraphrased = response.choices[0].message.content
        else:
            raise Exception("Empty API response")

        asyncio.create_task(
            bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"📩 <b>API Response:</b>\n<pre>{html.escape(paraphrased[:3000])}</pre>",
                parse_mode=enums.ParseMode.HTML
            )
        )

        # Parse the API response: extract the title and the body
        lines = paraphrased.splitlines()
        generated_title = None
        generated_body = paraphrased  # Fallback if parsing fails

        if lines and lines[0].startswith("Title:"):
            generated_title = lines[0][len("Title:"):].strip()
            idx = 1
            while idx < len(lines) and not lines[idx].strip():
                idx += 1
            generated_body = "\n".join(lines[idx:])
        
        return (generated_title, generated_body)

    except Exception as e:
        logger.exception("Paraphrase Error:")
        asyncio.create_task(
            bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"🔥 <b>Critical Error:</b>\nUsing original text\n<code>{html.escape(str(e)[:1000])}</code>",
                parse_mode=enums.ParseMode.HTML
            )
        )
        return (None, text)

def build_structured_message(title: str, paraphrased: str) -> str:
    """
    Build and return the final structured message with the generated title (or fallback)
    and the paraphrased content.
    """
    final_title = html.escape(title) if title else "📚 Article Update"
    message = (
        f"<b>{final_title}</b>\n\n"
        f"{paraphrased}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Remember:</i> Success is built on continuous improvement, and the fact that you're reading this article shows that dedication sets you apart. \n"
        "Explore @Excellerators for more Wisdom and Divine Knowledge."
    )
    return message

async def send_daily_article(bot: Client):
    """
    Scheduled daily task to fetch, process, and send an article.
    """
    tz = timezone('Asia/Kolkata')
    while True:
        try:
            now = datetime.now(tz)
            target_time = now.replace(hour=10, minute=45, second=20, microsecond=0)
            if now >= target_time:
                target_time += timedelta(days=1)
            wait_seconds = (target_time - now).total_seconds()
            logger.info(f"Sleeping for {wait_seconds:.1f} seconds until next scheduled Article")
            await asyncio.sleep(wait_seconds)

            logger.info("Processing daily article...")
            post = await get_random_unseen_post()
            if not post:
                raise Exception("No new posts available")

            raw_content = post['content']['rendered']
            cleaned = clean_content(raw_content)
            
            generated_title, paraphrased_text = paraphrase_content(cleaned, bot)
            if not generated_title:
                generated_title = html.escape(post['title']['rendered'])
            
            message = build_structured_message(generated_title, paraphrased_text)
            await bot.send_message(
                chat_id=ARTICLE_CHANNEL,
                text=message,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text="✅ Successfully sent daily article"
            )

        except Exception as e:
            logger.exception("Error sending daily article:")
            await bot.send_message(
                chat_id=LOG_CHANNEL,
                text=f"❌ Failed to send article: {html.escape(str(e)[:1000])}"
            )
        
        await asyncio.sleep(86400)  # Wait 24 hours until next article

def schedule_daily_articles(client: Client):
    """
    Starts the daily article scheduler.
    """
    asyncio.create_task(send_daily_article(client))



# =============================
# COMMAND HANDLER FOR INSTANT QUOTE
# =============================

@Client.on_message(filters.command('quote') & filters.user(ADMINS))
async def instant_quote_handler(client, message: Message):
    """Handles /quote command to immediately send & broadcast a quote with auto-deletion after a delay."""
    try:
        processing_msg = await message.reply("✨ Preparing inspirational quote...")
        
        # Fetch quote
        quote = fetch_random_quote()
        
        # Send to quote channel
        await client.send_message(
            chat_id=QUOTE_CHANNEL,
            text=quote,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Broadcast to users (reusing daily logic)
        users_cursor = await db.get_all_users()
        total_users = await db.col.count_documents({'name': {'$exists': True}})
        
        sent = blocked = deleted = failed = 0
        start_time = time.time()

        async for user in users_cursor:
            if 'id' not in user or 'name' not in user:
                continue
            user_id = int(user['id'])
            try:
                msg = await client.send_message(chat_id=user_id, text=quote)
                # Schedule deletion after QUOTE_DELETE_DELAY seconds using msg.id (not msg.message_id)
                asyncio.create_task(delete_message_after(client, user_id, msg.id, QUOTE_DELETE_DELAY))
                 # ✅ Delay between scheduling deletions to prevent mass task pile-up
                await asyncio.sleep(DELETION_INTERVAL)
                sent += 1
            except FloodWait as e:
                logger.info(f"Flood wait for {e.value} seconds for user {user_id}")
                await asyncio.sleep(e.value)
                continue
            except (InputUserDeactivated, UserIsBlocked, PeerIdInvalid):
                await db.delete_user(user_id)
                deleted += 1
            except Exception as e:
                failed += 1
                logger.error(f"User {user_id} error: {e}")

        # Log results
        broadcast_time = timedelta(seconds=int(time.time() - start_time))
        summary = (
            f"✅ Immediate Quote Broadcast Completed\n"
            f"Total: {total_users} | Sent: {sent}\n"
            f"Cleaned: {deleted} | Failed: {failed}"
        )
        
        # Try editing the processing message; ignore if the content is the same
        try:
            await processing_msg.edit("✅ Quote broadcasted to all users!")
        except Exception as edit_err:
            if "MESSAGE_NOT_MODIFIED" in str(edit_err):
                logger.info("Processing message already has the desired content. Skipping edit.")
            else:
                logger.exception("Error editing processing message:")
        
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"🚀 Immediate quote sent by {message.from_user.mention}\n{summary}"
        )

    except Exception as e:
        logger.exception("Quote command error:")
        try:
            await processing_msg.edit("⚠️ Broadcast failed - check logs")
        except Exception:
            pass
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Quote Command Failed: {str(e)[:500]}"
        )

# =============================
# COMMAND HANDLER FOR INSTANT ARTICLE
# =============================

@Client.on_message(filters.command('article') & filters.user(ADMINS))
async def instant_article_handler(client, message: Message):
    """
    Handles the /article command from admins to immediately generate and send an article.
    """
    try:
        processing_msg = await message.reply("🛠 Crafting the article on demand...")
        
        post = await get_random_unseen_post()
        if not post:
            await processing_msg.edit("❌ No articles available!")
            return

        raw_content = post['content']['rendered']
        cleaned = clean_content(raw_content)
        generated_title, paraphrased_text = paraphrase_content(cleaned, client)
        if not generated_title:
            generated_title = html.escape(post['title']['rendered'])

        message_text = build_structured_message(generated_title, paraphrased_text)
        
        await client.send_message(
            chat_id=ARTICLE_CHANNEL,
            text=message_text,
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        await processing_msg.edit("✅ Article successfully published!")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"🚀 Immediate article sent via command from {message.from_user.mention}"
        )

    except Exception as e:
        logger.exception("Instant Article Command Error:")
        await processing_msg.edit("⚠️ Failed to generate article - check logs")
        await client.send_message(
            chat_id=LOG_CHANNEL,
            text=f"⚠️ Command Failed: {html.escape(str(e)[:1000])}"
        )


# =============================
# SCHEDULER START FUNCTIONS
# =============================

def start_schedulers(client: Client):
    """
    Starts all scheduler tasks.
    """
    schedule_daily_quotes(client)
    schedule_daily_articles(client)