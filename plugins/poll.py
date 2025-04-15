import os
import logging
import json
import time
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, PollOption
from config import ADMINS

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

POLL_OPTIONS_FILE = "poll_templates.json"
DEFAULT_POLLS = {
    "mood": {
        "question": "How are you feeling today?",
        "options": ["Great", "Good", "Okay", "Not so good", "Terrible"]
    },
    "food": {
        "question": "What's your favorite food type?",
        "options": ["Italian", "Chinese", "Indian", "Mexican", "Fast food"]
    },
    "weather": {
        "question": "What's your favorite weather?",
        "options": ["Sunny", "Rainy", "Snowy", "Cloudy", "Windy"]
    }
}

async def load_poll_templates():
    """Load poll templates from file"""
    try:
        if os.path.exists(POLL_OPTIONS_FILE):
            with open(POLL_OPTIONS_FILE, "r") as f:
                return json.load(f)
        # If file doesn't exist, create it with default polls
        with open(POLL_OPTIONS_FILE, "w") as f:
            json.dump(DEFAULT_POLLS, f, indent=4)
        return DEFAULT_POLLS
    except Exception as e:
        logger.error(f"Error loading poll templates: {e}")
        return DEFAULT_POLLS

async def save_poll_templates(templates):
    """Save poll templates to file"""
    try:
        with open(POLL_OPTIONS_FILE, "w") as f:
            json.dump(templates, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving poll templates: {e}")

@Client.on_message(filters.command('poll'))
async def send_poll_handler(client, message: Message):
    """Send a poll when a user uses the /poll command"""
    try:
        # Extract command arguments
        args = message.text.split(' ', 2)
        poll_templates = await load_poll_templates()
        
        # If no arguments are provided, send the default mood poll
        if len(args) == 1:
            poll_data = poll_templates.get("mood", DEFAULT_POLLS["mood"])
            await message.reply_poll(
                question=poll_data["question"],
                options=poll_data["options"],
                is_anonymous=False,
                allows_multiple_answers=False
            )
            return
            
        # If a template name is provided
        if len(args) >= 2 and args[1] in poll_templates:
            poll_data = poll_templates[args[1]]
            await message.reply_poll(
                question=poll_data["question"],
                options=poll_data["options"],
                is_anonymous=False,
                allows_multiple_answers=False
            )
            return
            
        # Custom poll with format: /poll "Question" "Option1, Option2, Option3"
        if len(args) == 3:
            try:
                question = args[1].strip('"\'')
                options_text = args[2].strip('"\'')
                options = [opt.strip() for opt in options_text.split(',')]
                
                # Validate options
                if len(options) < 2:
                    await message.reply("❌ A poll needs at least 2 options!")
                    return
                    
                if len(options) > 10:
                    await message.reply("❌ Maximum 10 options are allowed in a poll!")
                    return
                
                await message.reply_poll(
                    question=question,
                    options=options,
                    is_anonymous=False,
                    allows_multiple_answers=False
                )
                return
            except Exception as e:
                logger.error(f"Error creating custom poll: {e}")
                
        # If we reach here, show usage instructions
        await message.reply(
            "📊 **Poll Command Usage**:\n\n"
            "• `/poll` - Send a mood poll\n"
            "• `/poll food` - Send food preference poll\n"
            "• `/poll weather` - Send weather preference poll\n"
            "• `/poll \"Your question?\" \"Option1, Option2, Option3\"`\n\n"
            f"Available templates: {', '.join(poll_templates.keys())}"
        )
        
    except Exception as e:
        logger.exception(f"Poll command error: {e}")
        await message.reply("❌ Error creating poll. Please try again later.")

@Client.on_message(filters.command('addpoll') & filters.user(ADMINS))
async def add_poll_template(client, message: Message):
    """Allows admins to add new poll templates"""
    try:
        args = message.text.split(' ', 3)
        if len(args) != 4:
            await message.reply(
                "❌ **Format error!**\n\n"
                "Usage: `/addpoll template_name \"Question\" \"Option1, Option2, ...\"`\n\n"
                "Example: `/addpoll movies \"What's your favorite movie genre?\" \"Action, Comedy, Horror, Sci-Fi, Drama\"`"
            )
            return
            
        template_name = args[1].lower()
        question = args[2].strip('"\'')
        options_text = args[3].strip('"\'')
        options = [opt.strip() for opt in options_text.split(',')]
        
        if len(options) < 2 or len(options) > 10:
            await message.reply("❌ Poll must have between 2 and 10 options!")
            return
            
        poll_templates = await load_poll_templates()
        poll_templates[template_name] = {
            "question": question,
            "options": options
        }
        await save_poll_templates(poll_templates)
        
        await message.reply(f"✅ Poll template `{template_name}` added successfully!")
        
    except Exception as e:
        logger.exception(f"Add poll template error: {e}")
        await message.reply("❌ Error adding poll template.")

@Client.on_message(filters.command('listpolls'))
async def list_poll_templates(client, message: Message):
    """List all available poll templates"""
    try:
        poll_templates = await load_poll_templates()
        if not poll_templates:
            await message.reply("No poll templates available.")
            return
            
        reply_text = "📊 **Available Poll Templates**:\n\n"
        for name, data in poll_templates.items():
            options_text = "`, `".join(data["options"])
            reply_text += f"• **{name}**: \"{data['question']}\"\n  Options: `{options_text}`\n\n"
            
        await message.reply(reply_text)
        
    except Exception as e:
        logger.exception(f"List polls error: {e}")
        await message.reply("❌ Error retrieving poll templates.")

@Client.on_message(filters.command('delpoll') & filters.user(ADMINS))
async def delete_poll_template(client, message: Message):
    """Allows admins to delete poll templates"""
    try:
        args = message.text.split(' ', 1)
        if len(args) != 2:
            await message.reply("❌ Usage: `/delpoll template_name`")
            return
            
        template_name = args[1].lower()
        poll_templates = await load_poll_templates()
        
        if template_name not in poll_templates:
            await message.reply(f"❌ Template `{template_name}` not found!")
            return
            
        del poll_templates[template_name]
        await save_poll_templates(poll_templates)
        
        await message.reply(f"✅ Poll template `{template_name}` deleted successfully!")
        
    except Exception as e:
        logger.exception(f"Delete poll template error: {e}")
        await message.reply("❌ Error deleting poll template.")