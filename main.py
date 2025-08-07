import asyncio
import threading
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ParseMode # Import ParseMode enum
from urllib.parse import unquote, urlparse, parse_qs, quote
# Ensure 'config' module is correctly set up with API_ID, API_HASH, BOT_TOKEN
from config import API_ID, API_HASH, BOT_TOKEN

from flask import Flask

# Initialize Flask app
app_flask = Flask(__name__)

# ---- Flask Route for Health Check ----
@app_flask.route('/')
def index():
    """
    Simple Flask route to indicate the bot is running.
    Useful for deployment platforms like Render for health checks.
    """
    return "✅ Bot is running!"

# ---- Pyrogram Bot Setup ----
# Initialize the Pyrogram Client
pyro = Client("studysmarter_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Dictionary to store user-specific data during the input collection process
# Each user's data will include flags to track input collection state.
user_data = {}

@pyro.on_message(filters.command("start"))
async def start(client, message):
    """
    Handles the /start command. Greets the user and provides instructions.
    """
    await message.reply("🎓 Welcome to the Study Smarter Bot!\n\nJust send a lesson link like:\n<code>https://theeduverse.xyz/play?lessonurl=...</code>", parse_mode=ParseMode.HTML)

@pyro.on_message(filters.regex(r"theeduverse\.xyz/play\?lessonurl="))
async def handle_link(client, message):
    """
    Handles messages containing the specific lesson URL pattern.
    Extracts the lesson URL, validates it, and initiates the data collection process.
    """
    user_id = message.from_user.id
    try:
        url = message.text
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        lesson_url = unquote(query.get("lessonurl", [""])[0]) # Extract and unquote the lessonurl

        # Validate if the lesson URL is an M3U8 link
        if not lesson_url.endswith(".m3u8"):
            return await message.reply("❌ Invalid M3U8 link. Please ensure the lesson URL ends with .m3u8.")

        # Construct the final player link
        final_link = f"https://studysmarterx.netlify.app/player?url={quote(lesson_url)}"

        # Store initial data for the user, including state flags
        user_data[user_id] = {
            "link": final_link,
            "title": "",
            "date": "",
            "notes": "",
            "title_collected": False, # Flag to track if title input has been processed
            "date_collected": False,  # Flag to track if date input has been processed
            "notes_collected": False  # Flag to track if notes input has been processed
        }
        await message.reply("✅ Link processed successfully!\nNow, please send the <b>Title</b> for this lecture, or type /empty to skip.", parse_mode=ParseMode.HTML)
    except Exception as e:
        # Catch any errors during URL parsing or processing
        await message.reply(f"❌ Error parsing link: {e}. Please ensure the link is correct and try again.")

@pyro.on_message(filters.text & filters.private)
async def collect_inputs(client, message: Message):
    """
    Collects additional information (Title, Date, Notes) from the user
    in a conversational flow using state flags.
    """
    user_id = message.from_user.id
    # Check if the user is in the data collection state
    if user_id not in user_data:
        return # Ignore messages if no active data collection session

    state = user_data[user_id]
    user_input = message.text.strip() # Get user input and strip whitespace

    # State 1: Collecting Title
    if not state["title_collected"]:
        if user_input == "/empty":
            state["title"] = "" # Explicitly set to empty string if skipped
        else:
            state["title"] = user_input
        state["title_collected"] = True # Mark title as processed for this session
        await message.reply("📅 Great! Now, please send the <b>Date</b> of the lecture (e.g., '2023-10-26'), or type /empty to skip.", parse_mode=ParseMode.HTML)
        return # Important: return after processing one state to wait for next input

    # State 2: Collecting Date
    if not state["date_collected"]:
        if user_input == "/empty":
            state["date"] = "" # Explicitly set to empty string if skipped
        else:
            state["date"] = user_input
        state["date_collected"] = True # Mark date as processed for this session
        await message.reply("📝 Almost there! Now, please send the <b>Notes link</b> (if any), or type /empty to skip.", parse_mode=ParseMode.HTML)
        return # Important: return after processing one state

    # State 3: Collecting Notes
    if not state["notes_collected"]:
        if user_input == "/empty":
            state["notes"] = "" # Explicitly set to empty string if skipped
        else:
            state["notes"] = user_input
        state["notes_collected"] = True # Mark notes as processed for this session

        # All inputs collected, send the final formatted message
        await send_final_message(client, message, state)
        del user_data[user_id] # Clear user data after completion
        return # Important: return after final processing

async def send_final_message(client, message, data):
    """
    Constructs and sends the final message with lecture link and notes,
    including inline keyboard buttons.
    """
    # Prepare message components, only include if data is present
    title = f"<b>📌 {data['title']}</b>\n" if data['title'] else ""
    date = f"🗓️ {data['date']}\n" if data['date'] else ""
    body = "🔗 Lecture and notes available below.\n\n"
    footer = "Provided by @studysmarterhub — share us for more!"

    full_text = f"{title}{date}{body}{footer}"

    # Define inline keyboard buttons
    buttons = [
        [InlineKeyboardButton("▶️ Watch Lecture", url=data["link"])] # Button to watch the lecture
    ]
    # Add 'View Notes' button only if notes is a non-empty string and starts with "http"
    if data["notes"] and data["notes"].startswith("http"):
        buttons.append([InlineKeyboardButton("📝 View Notes", url=data["notes"])])

    # Add 'Share' button to trigger an inline query for the promotional text
    buttons.append([
        InlineKeyboardButton("🔗 Share", switch_inline_query="share_aarambh")
    ])

    markup = InlineKeyboardMarkup(buttons)

    # Send the final message
    await message.reply(
        full_text,
        parse_mode=ParseMode.HTML, # Use ParseMode.HTML for HTML formatting
        disable_web_page_preview=True, # Prevent Telegram from generating a web page preview
        reply_markup=markup
    )

@pyro.on_inline_query()
async def inline_query_handler(client, inline_query):
    """
    Handles inline queries, specifically for sharing bot information.
    This is now used to share the specific promotional text for Aarambh batch.
    """
    if inline_query.query == "share_aarambh":
        await inline_query.answer(
            results=[
                client.types.InlineQueryResultArticle(
                    title="Share Aarambh Batch",
                    input_message_content=client.types.InputTextMessageContent(
                        "Access the aarambh batch free at @aarambh_batch_10th Join our backup at @studysmarterhub"
                    ),
                    description="Click to share this promotional message.",
                    thumb_url="https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg" # Telegram logo for the thumbnail
                )
            ],
            cache_time=1 # Cache the result for 1 second
        )

# ---- Thread to run Flask alongside bot ----
def run_flask():
    """
    Function to run the Flask app in a separate thread.
    """
    app_flask.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask, name="FlaskThread")
    flask_thread.start()

    # Run the Pyrogram bot in the main thread.
    # This ensures signal handling works correctly.
    print("Starting Pyrogram bot in the main thread...")
    pyro.run()
