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

# Configuration
ADMINS = [5199423758]  # Your admin user IDs
DESTINATIONS = {
    "SSC": (-1002584962735, 8),  # (chat_id, topic_id)
    "Maths Channel": (-1002637860051, None),
    "Test Topic": (-1002143525251, 10),
}
ANONYMOUS_POSTING = False  # Disabled for stability

user_data = {}

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

@pyro.on_message(filters.command("start"))
@is_admin
async def start(client, message):
    await message.reply(
        "🎓 Study Smarter Bot\n\n"
        "Send a lesson link:\n"
        "<code>https://theeduverse.xyz/play?lessonurl=...m3u8</code>",
        parse_mode=ParseMode.HTML
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
            return await message.reply("❌ Invalid M3U8 link")

        final_link = f"https://studysmarterx.netlify.app/player?url={quote(lesson_url)}"

        user_data[message.from_user.id] = {
            "link": final_link,
            "title": "",
            "date": "",
            "notes": "",
            "title_collected": False,
            "date_collected": False,
            "notes_collected": False
        }
        await message.reply("✅ Link processed! Send the <b>Title</b> or /empty", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

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
        await message.reply("📅 Send <b>Date</b> or /empty", parse_mode=ParseMode.HTML)
        return

    if not state["date_collected"]:
        state["date"] = user_input if user_input != "/empty" else ""
        state["date_collected"] = True
        await message.reply("📝 Send <b>Notes link</b> or /empty", parse_mode=ParseMode.HTML)
        return

    if not state["notes_collected"]:
        state["notes"] = user_input if user_input != "/empty" else ""
        state["notes_collected"] = True

        # Format the final message
        title = f"<b>📌 {state['title']}</b>\n" if state['title'] else ""
        date = f"🗓️ {state['date']}\n" if state['date'] else ""
        buttons = [[InlineKeyboardButton("▶️ Watch Lecture", url=state["link"])]]
        
        if state["notes"] and state["notes"].startswith("http"):
            buttons.append([InlineKeyboardButton("📝 View Notes", url=state["notes"])])
        
        promo_text = quote("Access @aarambh_batch_10th | Backup @studysmarterhub")
        buttons.append([InlineKeyboardButton("🔗 Share", url=f"tg://msg?text={promo_text}")])

        await message.reply(
            f"{title}{date}🔗 Lecture and notes below\n\nProvided by @studysmarterhub",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await message.reply("✅ Lecture block created! Send /done to post")

@pyro.on_message(filters.command("done"))
@is_admin
async def done_command(client, message):
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id]["notes_collected"]:
        return await message.reply("❌ No lecture block to post")

    buttons = [[InlineKeyboardButton(name, callback_data=f"send_to:{name}")] for name in DESTINATIONS]
    await message.reply("📍 Select destination:", reply_markup=InlineKeyboardMarkup(buttons))

@pyro.on_callback_query(filters.regex(r"^send_to:"))
@is_admin_callback
async def send_to_destination(client, callback_query: CallbackQuery):
    try:
        destination_name = callback_query.data.split(":")[1]
        chat_id, topic_id = DESTINATIONS[destination_name]
        data = user_data[callback_query.from_user.id]

        # Format message
        title = f"<b>📌 {data['title']}</b>\n" if data['title'] else ""
        date = f"🗓️ {data['date']}\n" if data['date'] else ""
        text = f"{title}{date}🔗 Lecture and notes below\n\nProvided by @studysmarterhub"
        
        buttons = [[InlineKeyboardButton("▶️ Watch Lecture", url=data["link"])]]
        if data["notes"] and data["notes"].startswith("http"):
            buttons.append([InlineKeyboardButton("📝 View Notes", url=data["notes"])])
        promo_text = quote("Access @aarambh_batch_10th | Backup @studysmarterhub")
        buttons.append([InlineKeyboardButton("🔗 Share", url=f"tg://msg?text={promo_text}")])

        # Send message
        try:
            if topic_id:
                await client.send_message(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            else:
                await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            
            await callback_query.answer(f"✅ Posted to {destination_name}", show_alert=True)
            await callback_query.message.edit_text(f"Message sent to {destination_name}")
            
        except RPCError as e:
            await callback_query.answer(f"❌ Failed: {e}", show_alert=True)
            await callback_query.message.edit_text(
                f"Failed to send to {destination_name}\n"
                f"Error: {e}\n\n"
                "Check:\n"
                "1. Bot permissions\n"
                "2. Topic exists\n"
                "3. Chat ID is correct"
            )
    finally:
        if callback_query.from_user.id in user_data:
            del user_data[callback_query.from_user.id]

def run_flask():
    app_flask.run(host="0.0.0.0", port=10000, debug=False, use_reloader=False)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Starting Pyrogram bot...")
    pyro.run()
