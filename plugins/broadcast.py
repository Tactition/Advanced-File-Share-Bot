   

from pyrogram.errors import InputUserDeactivated, UserNotParticipant, FloodWait, UserIsBlocked, PeerIdInvalid
from plugins.dbusers import db
from pyrogram import Client, filters
from config import ADMINS
import asyncio
import datetime
import time

   

async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        return False, "Error"
    except Exception as e:
        return False, "Error"


# Broadcast command handler
@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def verupikkals(bot, message):
    # ❗ Check if the command was not used as a reply
    if not message.reply_to_message:
        await message.reply_text(
            "❗To use the broadcast feature, please **reply to the message** you want to send.\n\n"
            "👉 Example:\n1. Forward or type the message you want to broadcast\n2. Reply to it with `/broadcast`"
        )
        return

    b_msg = message.reply_to_message
    users = await db.get_all_users()
    sts = await message.reply_text(text='📢 **Broadcasting your message...**')
    start_time = time.time()
    total_users = await db.total_users_count()

    done = 0
    blocked = 0
    deleted = 0
    failed = 0
    success = 0

   

    async for user in users:
        if 'id' in user:
            pti, sh = await broadcast_messages(int(user['id']), b_msg)
            if pti:
                success += 1
            else:
                if sh == "Blocked":
                    blocked += 1
                elif sh == "Deleted":
                    deleted += 1
                elif sh == "Error":
                    failed += 1
        else:
            failed += 1  # No user ID, can't send

        done += 1

        if done % 20 == 0:
            try:
                await sts.edit(
                    f"🚀 Broadcast in progress...\n\n"
                    f"👥 Total Users: {total_users}\n"
                    f"✅ Success: {success}\n"
                    f"⛔ Blocked: {blocked}\n"
                    f"🗑️ Deleted: {deleted}\n"
                    f"❌ Failed: {failed}\n"
                    f"📦 Completed: {done}/{total_users}"
                )
            except:
                pass

    time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
    await sts.edit(
        f"✅ **Broadcast Completed!**\n\n"
        f"🕒 Time Taken: {time_taken}\n"
        f"👥 Total Users: {total_users}\n"
        f"✅ Success: {success}\n"
        f"⛔ Blocked: {blocked}\n"
        f"🗑️ Deleted: {deleted}\n"
        f"❌ Failed: {failed}"
    )
