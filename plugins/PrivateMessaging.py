import logging
import re
from pyrogram import Client, filters, enums
from pyrogram.errors import RPCError, PeerIdInvalid
from info import ADMINS, LOG_CHANNEL
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# --------------------- ADMIN TO USER (TEXT & MEDIA) ---------------------
@Client.on_message(filters.command('message') & filters.user(ADMINS))
async def admin_send_message(client: Client, message: Message):
    """
    Admin command:
      /message <user_id|@username> <text> [with media attachment]
    """
    # Handle media messages
    if message.media and message.caption:
        parts = message.caption.split(maxsplit=2)
        if len(parts) < 2:
            return await message.reply(
                "⚠️ <b>Media Usage:</b> Add caption: <code>/message &lt;user_id|@username&gt; [text]</code>\n\n"
                "<b>Example:</b> <code>/message 123456789 Check this image</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        target = parts[1]
        text = parts[2] if len(parts) > 2 else None
    # Handle text messages
    elif not message.media:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            return await message.reply(
                "⚠️ <b>Usage:</b> <code>/message &lt;user_id|@username&gt; &lt;text&gt;</code>\n\n"
                "<b>Example:</b> <code>/message 123456789 Hello there!</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        target, text = parts[1], parts[2]
    else:
        return await message.reply(
            "⚠️ <b>Send media with caption:</b> <code>/message &lt;user_id|@username&gt; [text]</code>",
            quote=True,
            parse_mode=enums.ParseMode.HTML
        )

    # Resolve ID or username
    try:
        user_id = int(target)
    except ValueError:
        username = target.lstrip('@')
        try:
            user = await client.get_users(username)
            user_id = user.id
        except PeerIdInvalid:
            return await message.reply(f"❌ User <code>@{username}</code> not found.", quote=True, parse_mode=enums.ParseMode.HTML)
        except RPCError as e:
            logger.error(f"Error resolving @{username}: {e}")
            return await message.reply(f"❌ Error: <code>{e}</code>", quote=True, parse_mode=enums.ParseMode.HTML)

    try:
        # Send media with caption
        if message.media:
            await message.copy(
                chat_id=user_id,
                caption=text
            )
            msg_type = "Media"
        # Send text message
        else:
            await client.send_message(chat_id=user_id, text=text)
            msg_type = "Message"
        
        # Create response
        response = (
            f"✅ {msg_type} sent to user:\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"<i>Reply to this message to continue the conversation</i>"
        )
        
        await message.reply(response, quote=True, parse_mode=enums.ParseMode.HTML)
    except RPCError as e:
        logger.error(f"Failed to send to {user_id}: {e}")
        await message.reply(f"❌ Delivery failed: <code>{e}</code>", quote=True, parse_mode=enums.ParseMode.HTML)


# --------------------- USER TO ADMIN (TEXT & MEDIA) ---------------------
@Client.on_message(filters.command('message') & filters.private & ~filters.user(ADMINS))
async def user_send_message(client: Client, message: Message):
    """
    User command:
      /message <text> [with media attachment]
    """
    # Extract message text/caption
    if message.media and message.caption:
        text = message.caption.split(maxsplit=1)[1] if len(message.caption.split()) > 1 else ""
    elif not message.media:
        if len(message.command) < 2:
            return await message.reply(
                "⚠️ <b>Usage:</b> <code>/message your_text_here</code>\n\n"
                "<b>Example:</b> <code>/message I need help with my account</code>",
                quote=True,
                parse_mode=enums.ParseMode.HTML
            )
        text = message.text.split(maxsplit=1)[1]
    else:
        text = ""

    user = message.from_user
    
    # Build metadata header
    header = (
        f"📩 #message <b>From User</b>\n"
        f"👤 Name: {user.first_name or ''} {user.last_name or ''}\n"
        f"🆔 User ID: <code>{user.id}</code> #UID{user.id}#\n"
        f"🤖 Bot ID: #BOT{client.me.id}#\n"
        f"📱 Username: @{user.username or 'N/A'}\n"
        f"⏰ Time: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "➖➖➖➖➖➖➖\n"
    )
    
    try:
        # Forward media with caption
        if message.media:
            await message.copy(
                LOG_CHANNEL,
                caption=header + (message.caption or ""),
                parse_mode=enums.ParseMode.HTML
            )
        # Forward text message
        else:
            await client.send_message(
                LOG_CHANNEL, 
                header + text,
                parse_mode=enums.ParseMode.HTML
            )
        
        await message.reply(
            "✅ Your message has been sent to the admins.\n"
            "They'll reply to you here when available.",
            quote=True
        )
    except Exception as e:
        logger.error(f"Failed to forward user message: {e}")
        await message.reply(
            "❌ Could not send your message. Please try again later.",
            quote=True
        )


# --------------------- ADMIN REPLY TO USER (TEXT & MEDIA) ---------------------
def extract_ids(text: str) -> tuple:
    """Extract both User ID and Bot ID from message text"""
    uid_match = re.search(r"#UID(\d+)#", text)
    bot_match = re.search(r"#BOT(\d+)#", text)
    return (
        int(uid_match.group(1)) if uid_match else None,
        int(bot_match.group(1)) if bot_match else None
    )

@Client.on_message(filters.chat(int(LOG_CHANNEL)) & filters.reply)
async def reply_to_user(client: Client, message: Message):
    """Routes admin replies back to the original user"""
    try:
        current_msg = message.reply_to_message
        user_id = None
        target_bot_id = None

        # Traverse reply chain to find original message with IDs
        while current_msg:
            text_source = current_msg.text or current_msg.caption or ""
            user_id, target_bot_id = extract_ids(text_source)
            
            if user_id and target_bot_id:
                break
            current_msg = current_msg.reply_to_message

        # Security check - only handle messages for this bot
        if target_bot_id != client.me.id:
            logger.warning(f"Ignoring reply meant for bot {target_bot_id}")
            return

        if not user_id:
            return await message.reply_text("❌ User ID not found in message chain", quote=True)

        try:
            # Handle media replies
            if message.media:
                # Add prefix to caption if exists
                if message.caption:
                    new_caption = f"📬 <b>Admin Reply:</b>\n{message.caption}"
                    await message.copy(
                        chat_id=user_id,
                        caption=new_caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                # For media without caption
                else:
                    await message.copy(chat_id=user_id)
                    await client.send_message(
                        user_id,
                        "📬 <b>Admin Reply</b>",
                        parse_mode=enums.ParseMode.HTML
                    )
                msg_type = "Media"
            # Handle text replies
            else:
                resp = message.text or message.caption or ""
                await client.send_message(
                    chat_id=user_id,
                    text=f"📬 <b>Admin Reply:</b>\n{resp}",
                    parse_mode=enums.ParseMode.HTML
                )
                msg_type = "Reply"
            
            await message.reply_text(f"✅ {msg_type} sent to user <code>{user_id}</code>", quote=True, parse_mode=enums.ParseMode.HTML)
            
        except RPCError as e:
            logger.error(f"Failed to reply to user {user_id}: {e}")
            await message.reply_text(f"❌ Delivery failed: <code>{e}</code>", quote=True, parse_mode=enums.ParseMode.HTML)

    except Exception as e:
        logger.critical(f"Reply handler crashed: {e}", exc_info=True)
        await message.reply_text("🚨 Error processing reply", quote=True)
