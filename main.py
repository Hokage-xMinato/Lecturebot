import asyncio
import threading
import re
import uuid # Import for generating unique IDs
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from pyrogram.errors import RPCError
from urllib.parse import unquote, urlparse, parse_qs, quote
from config import API_ID, API_HASH, BOT_TOKEN
from flask import Flask

# Initialize Flask app
app_flask = Flask(__name__)

@app_flask.route('/')
def index():
    return "✅ Bot is running!"

# Initialize Pyrogram Client
pyro = Client("studysmarter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- Configuration ---
ADMINS = [5199423758] # Replace with your actual admin user IDs

# DESTINATIONS now include (chat_id, topic_id, reply_to_message_id)
# Set reply_to_message_id to None if not needed for a destination.
DESTINATIONS = {
    "SSC": (-1002584962735, 8, None),
    "Maths Channel": (-1002637860051, None, None),
    "Test Topic": (-1002143525251, 10, None),
    "Aarambh Batch Reply": (-1002584962735, 8, 6768), # Example: replies to specific message
}
# --- End Configuration ---

user_data = {} # Stores temporary data for the current user's block creation
saved_blocks = {} # Stores saved blocks with their assigned IDs

# --- Decorators for Authorization ---
def is_admin(func):
    async def wrapper(client, message, *args, **kwargs):
        if message.from_user and message.from_user.id in ADMINS:
            return await func(client, message, *args, **kwargs)
        await message.reply("❌ You are not authorized to use this bot.")
    return wrapper

def is_admin_callback(func):
    async def wrapper(client, callback_query, *args, **kwargs):
        if callback_query.from_user and callback_query.from_user.id in ADMINS:
            return await func(client, callback_query, *args, **kwargs)
        await callback_query.answer("❌ Not authorized", show_alert=True)
    return wrapper

# --- Bot Handlers ---
@pyro.on_message(filters.command("start"))
@is_admin
async def start(client, message):
    await message.reply(
        "🎓 **Study Smarter Bot**\n\n"
        "Send a lesson link to begin:\n"
        "➡️ `https://theeduverse.xyz/play?lessonurl=...m3u8`",
        parse_mode=ParseMode.MARKDOWN
    )

@pyro.on_message(filters.regex(r"theeduverse\.xyz/play\?lessonurl=", flags=re.IGNORECASE))
@is_admin
async def handle_link(client, message):
    try:
        url = message.text
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        lesson_url = unquote(query.get("lessonurl", [""])[0])

        if not lesson_url.endswith(".m3u8"):
            return await message.reply("❌ Invalid M3U8 link in URL.")

        final_link = f"https://studysmarterx.netlify.app/player?url={quote(lesson_url)}"

        user_data[message.from_user.id] = {
            "link": final_link, "title": "", "date": "", "notes": "",
            "title_collected": False, "date_collected": False, "notes_collected": False,
            "final_text": "", "final_markup": None
        }
        await message.reply("✅ Link processed! Now send the **Title**.\n(Send /empty to skip)", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ An error occurred while processing the link: {e}")

@pyro.on_message(filters.text & filters.private & ~filters.command(["done", "start", "chatinfo", "save", "post"]))
@is_admin
async def collect_inputs(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    state = user_data[user_id]
    user_input = message.text.strip()

    if not state["title_collected"]:
        state["title"] = user_input if user_input != "/empty" else ""
        state["title_collected"] = True
        await message.reply("📅 Now send the **Date**.\n(Send /empty to skip)", parse_mode=ParseMode.HTML)
        return

    if not state["date_collected"]:
        state["date"] = user_input if user_input != "/empty" else ""
        state["date_collected"] = True
        await message.reply("📝 Finally, send the **Notes link**.\n(Send /empty to skip)", parse_mode=ParseMode.HTML)
        return

    if not state["notes_collected"]:
        state["notes"] = user_input if user_input != "/empty" else ""
        state["notes_collected"] = True

        title = f"<b>📌 {state['title']}</b>\n" if state['title'] else ""
        date = f"🗓️ {state['date']}\n" if state['date'] else ""
        text = f"{title}{date}\n🔗 Lecture and notes are linked below.\n\n<b>Provided by @studysmarterhub</b>"
        
        buttons = [[InlineKeyboardButton("▶️ Watch Lecture", url=state["link"])]]
        if state["notes"] and state["notes"].startswith("http"):
            buttons.append([InlineKeyboardButton("📝 View Notes", url=state["notes"])])
        
        promo_text = quote("Access @aarambh_batch_10th | Backup @studysmarterhub")
        buttons.append([InlineKeyboardButton("🔗 Share this Post", url=f"https://t.me/share/url?url={promo_text}")])
        
        markup = InlineKeyboardMarkup(buttons)

        state["final_text"] = text
        state["final_markup"] = markup
        
        await message.reply("✅ **Preview of your post:**")
        await message.reply(
            text=state["final_text"],
            reply_markup=state["final_markup"],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await message.reply("Looks good? Send /done to choose where to post it, or /save to store it.")

@pyro.on_message(filters.command("done"))
@is_admin
async def done_command(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id].get("notes_collected"):
        return await message.reply("❌ No lecture block has been created yet. Please send a link first.")

    buttons = [[InlineKeyboardButton(name, callback_data=f"send_to:{name}")] for name in DESTINATIONS]
    await message.reply("📍 **Select a destination to post to:**", reply_markup=InlineKeyboardMarkup(buttons))

@pyro.on_callback_query(filters.regex(r"^send_to:"))
@is_admin_callback
async def send_to_destination(client, callback_query: CallbackQuery):
    """Sends the final message to the selected destination channel/topic."""
    user_id = callback_query.from_user.id
    try:
        destination_name = callback_query.data.split(":", 1)[1]
        
        # Unpack the tuple with three elements
        chat_id, topic_id, reply_to_message_id = DESTINATIONS[destination_name]
        data = user_data[user_id]

        # Prepare common kwargs for sending the message
        send_kwargs = {
            "chat_id": chat_id,
            "text": data["final_text"],
            "reply_markup": data["final_markup"],
            "parse_mode": ParseMode.HTML,
            "disable_web_page_preview": True
        }

        # Add message_thread_id if a topic is specified and supported
        if topic_id and "message_thread_id" in Client.send_message.__code__.co_varnames:
            send_kwargs["message_thread_id"] = topic_id

        # Add reply_to_message_id if a specific message to reply to is specified
        if reply_to_message_id:
            send_kwargs["reply_to_message_id"] = reply_to_message_id

        await client.send_message(**send_kwargs)
        
        await callback_query.answer(f"✅ Successfully posted to {destination_name}!", show_alert=True)
        await callback_query.message.edit_text(f"✅ Message sent to **{destination_name}**.")

    except RPCError as e:
        await callback_query.answer(f"❌ Telegram API Error: {e}", show_alert=True)
        await callback_query.message.edit_text(
            f"❗️**Failed to send to {destination_name}**\n\n"
            f"**Error:** `{e}`\n\n"
            "**Please Check:**\n"
            "1. Is the bot an **admin** in the destination chat?\n"
            "2. Does it have permission to **send messages** (and manage topics)?\n"
            "3. Are the **Chat ID**, **Topic ID**, and **Reply-to Message ID** correct?"
        )
    except Exception as e:
        await callback_query.answer(f"❌ A bot error occurred: {e}", show_alert=True)
        await callback_query.message.edit_text(f"❗️**An unexpected error occurred:**\n\n`{e}`")
    finally:
        # Clear user data after posting
        if user_id in user_data:
            del user_data[user_id]

@pyro.on_message(filters.command("save") & filters.private)
@is_admin
async def save_block(client, message: Message):
    """
    Saves the current lecture block to local memory with a random ID.
    Only accessible by admins.
    """
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id].get("notes_collected"):
        return await message.reply("❌ No complete lecture block to save. Please create one first.")

    # Generate a unique, short ID
    block_id = str(uuid.uuid4().hex[:8]) # Using first 8 chars of a UUID

    # Store the entire user_data block under this ID
    saved_blocks[block_id] = user_data[user_id]
    
    # Clear the current user's ephemeral data
    del user_data[user_id]

    await message.reply(
        f"✅ Lecture block saved! Use `/post {block_id}` to post it.\n"
        f"**Saved ID:** `{block_id}`",
        parse_mode=ParseMode.MARKDOWN
    )

@pyro.on_message(filters.command("post") & filters.group) # Ensure /post only works in groups
async def post_block(client, message: Message):
    """
    Posts a saved lecture block to the current group/topic.
    Accessible by anyone in the group.
    Usage: /post <assigned_id>
    """
    args = message.command
    if len(args) < 2:
        return await message.reply("Usage: `/post <assigned_id>`", reply_to_message_id=message.id)

    block_id = args[1]
    
    if block_id not in saved_blocks:
        return await message.reply(f"❌ Block with ID `{block_id}` not found.", reply_to_message_id=message.id)

    block_data = saved_blocks[block_id]

    chat_id = message.chat.id
    # Get the current topic ID if the command is used within a topic
    topic_id = message.message_thread_id 

    # Prepare common kwargs for sending the message
    send_kwargs = {
        "chat_id": chat_id,
        "text": block_data["final_text"],
        "reply_markup": block_data["final_markup"],
        "parse_mode": ParseMode.HTML,
        "disable_web_page_preview": True
    }

    # Add message_thread_id if a topic is specified and supported
    # This ensures it posts in the current topic or general chat as appropriate
    if topic_id and "message_thread_id" in Client.send_message.__code__.co_varnames:
        send_kwargs["message_thread_id"] = topic_id
    
    try:
        # Attempt to send the message with the determined chat/topic ID
        await client.send_message(**send_kwargs)
        # Reply to the user's command confirming success
        await message.reply(f"✅ Block `{block_id}` posted successfully!", reply_to_message_id=message.id)
    except RPCError as e:
        # Reply to the user's command with the error, ensuring it stays in context
        await message.reply(
            f"❌ Failed to post block `{block_id}`:\n\n"
            f"**Error:** `{e}`\n\n"
            "**Please Check:**\n"
            "1. Is the bot an **admin** in this chat?\n"
            "2. Does it have permission to **send messages** (and manage topics)?",
            reply_to_message_id=message.id # This is the reply to the user's command
        )
    except Exception as e:
        # Catch other unexpected errors and reply to the user's command
        await message.reply(f"❗️An unexpected error occurred: `{e}`", reply_to_message_id=message.id)


@pyro.on_message(filters.command("chatinfo") & filters.group)
@is_admin
async def chat_info(client, message: Message):
    """
    Provides the chat ID and, if applicable, the message thread ID (topic ID)
    for the group where the command is used.
    """
    chat_id = message.chat.id
    topic_id = message.message_thread_id if message.message_thread_id else "N/A (No topic)"

    response_text = (
        f"**Chat Information:**\n"
        f"🔗 **Chat ID:** `{chat_id}`\n"
        f"💬 **Topic ID:** `{topic_id}`\n\n"
        f"Use these IDs in your `DESTINATIONS` configuration or for the /post command's topic context."
    )

    # Reply in the same topic if available, otherwise just in the chat
    await message.reply_text(
        response_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_to_message_id=message.id # Ensures reply is in the same topic if it exists
    )


# --- Flask and Bot Execution ---
def run_flask():
    app_flask.run(host="0.0.0.0", port=10000, debug=False, use_reloader=False)

if __name__ == "__main__":
    print("Starting Flask web server in a background thread...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Starting Pyrogram bot...")
    pyro.run()
