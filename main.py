import asyncio
import threading
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
# For better practice, move these to your config.py file
ADMINS = [5199423758]  # Your admin user IDs
DESTINATIONS = {
    # Make sure these IDs are correct!
    "SSC": (-1002584962735, 8),  # (group_chat_id, topic_id)
    "Maths Channel": (-1002637860051, None), # (channel_chat_id, None)
    "Test Topic": (-1002143525251, 10), # (group_chat_id, topic_id)
}
# --- End Configuration ---


user_data = {}

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

@pyro.on_message(filters.regex(r"theeduverse\.xyz/play\?lessonurl="))
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
            "link": final_link,
            "title": "", "date": "", "notes": "",
            "title_collected": False, "date_collected": False, "notes_collected": False,
            "final_text": "", "final_markup": None # For storing the final message
        }
        await message.reply("✅ Link processed! Now send the **Title**.\n(Send /empty to skip)", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ An error occurred while processing the link: {e}")

@pyro.on_message(filters.text & filters.private & ~filters.command("done") & ~filters.command("start"))
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

        # --- BUILD THE MESSAGE ONCE ---
        title = f"<b>📌 {state['title']}</b>\n" if state['title'] else ""
        date = f"🗓️ {state['date']}\n" if state['date'] else ""
        text = f"{title}{date}\n🔗 Lecture and notes are linked below.\n\n<b>Provided by @studysmarterhub</b>"
        
        buttons = [[InlineKeyboardButton("▶️ Watch Lecture", url=state["link"])]]
        
        if state["notes"] and state["notes"].startswith("http"):
            buttons.append([InlineKeyboardButton("📝 View Notes", url=state["notes"])])
        
        promo_text = quote("Access @aarambh_batch_10th | Backup @studysmarterhub")
        buttons.append([InlineKeyboardButton("🔗 Share this Post", url=f"https://t.me/share/url?url={promo_text}")])
        
        markup = InlineKeyboardMarkup(buttons)

        # Store the final text and markup
        state["final_text"] = text
        state["final_markup"] = markup
        
        # Show the preview to the admin
        await message.reply(
            "✅ **Preview of your post:**"
        )
        await message.reply(
            text=state["final_text"],
            reply_markup=state["final_markup"],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await message.reply("Looks good? Send /done to choose where to post it.")

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
    user_id = callback_query.from_user.id
    try:
        destination_name = callback_query.data.split(":", 1)[1]
        chat_id, topic_id = DESTINATIONS[destination_name]
        data = user_data[user_id]
        
        # --- SEND THE PRE-BUILT MESSAGE ---
        # The `message_thread_id` parameter is ignored if it's None, so this works for both cases.
        await client.send_message(
            chat_id=chat_id,
            message_thread_id=topic_id,
            text=data["final_text"],
            reply_markup=data["final_markup"],
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        
        await callback_query.answer(f"✅ Successfully posted to {destination_name}!", show_alert=True)
        await callback_query.message.edit_text(f"✅ Message sent to **{destination_name}**.")

    except RPCError as e:
        # This will catch errors from Telegram (e.g., bot not in chat, wrong topic id)
        await callback_query.answer(f"❌ Telegram API Error: {e}", show_alert=True)
        await callback_query.message.edit_text(
            f"❗️**Failed to send to {destination_name}**\n\n"
            f"**Error:** `{e}`\n\n"
            "**Please Check:**\n"
            "1. Is the bot an **admin** in the destination chat?\n"
            "2. Does the bot have permission to **send messages** (and post in topics)?\n"
            "3. Is the **Topic ID** (`{topic_id}`) correct and does the topic still exist?"
        )
    except Exception as e:
        # This will catch any other error (e.g., KeyError if data is missing)
        await callback_query.answer(f"❌ A bot error occurred: {e}", show_alert=True)
        await callback_query.message.edit_text(f"❗️**An unexpected error occurred:**\n\n`{e}`")
        
    finally:
        # Clean up user data to allow for a new post
        if user_id in user_data:
            del user_data[user_id]

# --- Flask and Bot Execution ---
def run_flask():
    # Runs the Flask app in a separate thread
    app_flask.run(host="0.0.0.0", port=10000, debug=False, use_reloader=False)

if __name__ == "__main__":
    print("Starting Flask web server...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Starting Pyrogram bot...")
    pyro.run()
