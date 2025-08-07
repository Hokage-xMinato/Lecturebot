from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from urllib.parse import unquote, urlparse, parse_qs, quote
from config import API_ID, API_HASH, BOT_TOKEN

from flask import Flask
import threading

app_flask = Flask(__name__)

# ---- Flask Route ----
@app_flask.route('/')
def index():
    return "✅ Bot is running!"

# ---- Pyrogram Bot Setup ----
pyro = Client("studysmarter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

@pyro.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("🎓 Welcome to the Study Smarter Bot!\n\nJust send a lesson link like:\n<code>https://theeduverse.xyz/play?lessonurl=...</code>")

@pyro.on_message(filters.regex(r"theeduverse\.xyz/play\?lessonurl="))
async def handle_link(client, message):
    user_id = message.from_user.id
    try:
        url = message.text
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        lesson_url = unquote(query.get("lessonurl", [""])[0])
        if not lesson_url.endswith(".m3u8"):
            return await message.reply("❌ Invalid M3U8 link.")
        
        final_link = f"https://studysmarterx.netlify.app/player?url={quote(lesson_url)}"
        user_data[user_id] = {
            "link": final_link,
            "title": "",
            "date": "",
            "notes": ""
        }
        await message.reply("✅ Link processed.\nNow send the <b>Title</b> or type /empty to skip.", parse_mode="html")
    except Exception:
        await message.reply("❌ Error parsing link.")

@pyro.on_message(filters.text & filters.private)
async def collect_inputs(client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    state = user_data[user_id]
    
    if not state["title"]:
        if message.text != "/empty":
            state["title"] = message.text
        await message.reply("📅 Now send the <b>Date</b> or type /empty to skip.", parse_mode="html")
        return
    
    if not state["date"]:
        if message.text != "/empty":
            state["date"] = message.text
        await message.reply("📝 Now send the <b>Notes (link)</b> or type /empty to skip.", parse_mode="html")
        return
    
    if not state["notes"]:
        if message.text != "/empty":
            state["notes"] = message.text
        
        await send_final_message(client, message, state)
        del user_data[user_id]

async def send_final_message(client, message, data):
    title = f"<b>📌 {data['title']}</b>\n" if data['title'] else ""
    date = f"🗓️ {data['date']}\n" if data['date'] else ""
    body = "🔗 Lecture and notes available below.\n\n"
    footer = "Provided by @studysmarterhub — share us for more!"

    full_text = f"{title}{date}{body}{footer}"

    buttons = [
        [InlineKeyboardButton("▶️ Watch Lecture", url=data["link"])]
    ]
    if data["notes"].startswith("http"):
        buttons.append([InlineKeyboardButton("📝 View Notes", url=data["notes"])])

    buttons.append([
        InlineKeyboardButton("🔗 Share", switch_inline_query="share_aarambh")
    ])

    markup = InlineKeyboardMarkup(buttons)

    await message.reply(
        full_text,
        parse_mode="html",
        disable_web_page_preview=True,
        reply_markup=markup
    )

@pyro.on_inline_query()
async def inline_query_handler(client, inline_query):
    if inline_query.query == "share_aarambh":
        await inline_query.answer(
            results=[
                client.types.InlineQueryResultArticle(
                    title="Share Aarambh Batch",
                    input_message_content=client.types.InputTextMessageContent(
                        "📢 Join us for Aarambh batch at @aarambh_batch_10th\nand our backup at @studysmarterhub."
                    ),
                    description="Click to share this",
                    thumb_url="https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg"
                )
            ],
            cache_time=1
        )

# ---- Thread to run bot alongside Flask ----
def run_bot():
    pyro.run()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    app_flask.run(host="0.0.0.0", port=10000)  # Render exposes port 10000
