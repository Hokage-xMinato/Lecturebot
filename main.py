import asyncio
import threading
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ParseMode
from urllib.parse import unquote, urlparse, parse_qs, quote
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
user_data = {}

# List of allowed user IDs (admins)
# Add your user IDs here, separated by commas.
ADMINS = [
    5199423758,  # Replace with the user ID of the admin
    # Add more admin user IDs here
]

# A dictionary to store channel/group and topic information.
# The keys are the display names, and the values are a tuple:
# (chat_id, topic_id_or_none)
# For the main channel without topics, the topic_id can be None.
# For a group with topics, the topic_id is the unique ID for that topic.
DESTINATIONS = {
    "SSC": (-1002584962735, 8),
    "Maths Channel": (-1002637860051, None),
    "Physics Group": (-1009876543210, None),
    "Test Topic": (-1002143525251, 10),
}

def is_admin(func):
    """
    Decorator to check if the user is an admin.
    """
    async def wrapper(client, message, *args, **kwargs):
        if message.from_user and message.from_user.id in ADMINS:
            return await func(client, message, *args, **kwargs)
        else:
            await message.reply("❌ You are not authorized to use this bot.")
    return wrapper

def is_admin_callback(func):
    """
    Decorator for callback queries to check if the user is an admin.
    """
    async def wrapper(client, callback_query, *args, **kwargs):
        if callback_query.from_user and callback_query.from_user.id in ADMINS:
            return await func(client, callback_query, *args, **kwargs)
        else:
            await callback_query.answer("❌ You are not authorized to use this bot.", show_alert=True)
    return wrapper

@pyro.on_message(filters.command("start"))
@is_admin
async def start(client, message):
    """
    Handles the /start command. Greets the user and provides instructions.
    """
    await message.reply("🎓 Welcome to the Study Smarter Bot!\n\nJust send a lesson link like:\n<code>https://theeduverse.xyz/play?lessonurl=...m3u8</code>", parse_mode=ParseMode.HTML)

@pyro.on_message(filters.regex(r"theeduverse\.xyz/play\?lessonurl="))
@is_admin
async def handle_link(client, message):
    """
    Handles messages containing the specific lesson URL pattern.
    """
    user_id = message.from_user.id
    try:
        url = message.text
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        lesson_url = unquote(query.get("lessonurl", [""])[0])

        if not lesson_url.endswith(".m3u8"):
            return await message.reply("❌ Invalid M3U8 link. Please ensure the lesson URL ends with .m3u8.")

        final_link = f"https://studysmarterx.netlify.app/player?url={quote(lesson_url)}"

        user_data[user_id] = {
            "link": final_link,
            "title": "",
            "date": "",
            "notes": "",
            "title_collected": False,
            "date_collected": False,
            "notes_collected": False
        }
        await message.reply("✅ Link processed successfully!\nNow, please send the <b>Title</b> for this lecture, or type /empty to skip.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"❌ Error parsing link: {e}. Please ensure the link is correct and try again.")

@pyro.on_message(filters.text & filters.private & ~filters.command("done"))
@is_admin
async def collect_inputs(client, message: Message):
    """
    Collects additional information (Title, Date, Notes) from the user
    in a conversational flow using state flags.
    """
    user_id = message.from_user.id
    if user_id not in user_data:
        return

    state = user_data[user_id]
    user_input = message.text.strip()

    if not state["title_collected"]:
        state["title"] = user_input if user_input != "/empty" else ""
        state["title_collected"] = True
        await message.reply("📅 Great! Now, please send the <b>Date</b> of the lecture (e.g., '2023-10-26'), or type /empty to skip.", parse_mode=ParseMode.HTML)
        return

    if not state["date_collected"]:
        state["date"] = user_input if user_input != "/empty" else ""
        state["date_collected"] = True
        await message.reply("📝 Almost there! Now, please send the <b>Notes link</b> (if any), or type /empty to skip.", parse_mode=ParseMode.HTML)
        return

    if not state["notes_collected"]:
        state["notes"] = user_input if user_input != "/empty" else ""
        state["notes_collected"] = True

        await send_final_message_to_user(client, message, state)
        await message.reply("Lecture block created successfully. Reply /done to share this block in a group or channel.")
        return

async def send_final_message_to_user(client, message, data):
    """
    Constructs and sends the final message with lecture link and notes
    to the user who created the block.
    """
    title = f"<b>📌 {data['title']}</b>\n" if data['title'] else ""
    date = f"🗓️ {data['date']}\n" if data['date'] else ""
    body = "🔗 Lecture and notes available below.\n\n"
    footer = "Provided by @studysmarterhub — share us for more!"
    full_text = f"{title}{date}{body}{footer}"

    buttons = [
        [InlineKeyboardButton("▶️ Watch Lecture", url=data["link"])]
    ]
    if data["notes"] and data["notes"].startswith("http"):
        buttons.append([InlineKeyboardButton("📝 View Notes", url=data["notes"])])

    promotional_text = "Access the aarambh batch free at @aarambh_batch_10th Join our backup at @studysmarterhub"
    encoded_promotional_text = quote(promotional_text)
    buttons.append([InlineKeyboardButton("🔗 Share", url=f"tg://msg?text={encoded_promotional_text}")])

    markup = InlineKeyboardMarkup(buttons)

    await message.reply(
        full_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=markup
    )

@pyro.on_message(filters.command("done"))
@is_admin
async def done_command_handler(client, message):
    """
    Handles the /done command to initiate the channel/topic selection process.
    """
    user_id = message.from_user.id
    if user_id not in user_data or not user_data[user_id].get("notes_collected"):
        return await message.reply("You need to create a lecture block first. Send a lesson link to begin.")

    buttons = [[InlineKeyboardButton(name, callback_data=f"send_to:{name}")] for name in DESTINATIONS]
    markup = InlineKeyboardMarkup(buttons)
    await message.reply("Please select where you want to send this lecture block:", reply_markup=markup)

@pyro.on_callback_query()
@is_admin_callback
async def send_to_channel_handler(client, callback_query: CallbackQuery):
    """
    Handles button clicks for selecting the destination channel/topic.
    """
    data = callback_query.data
    if not data.startswith("send_to:"):
        await callback_query.answer("Invalid action.")
        return

    user_id = callback_query.from_user.id
    if user_id not in user_data or not user_data[user_id].get("notes_collected"):
        await callback_query.answer("Session expired. Please start over.", show_alert=True)
        return

    destination_name = data.split(":")[1]
    destination = DESTINATIONS.get(destination_name)

    if not destination:
        await callback_query.answer("Destination not found.", show_alert=True)
        return

    chat_id, topic_id = destination
    lecture_data = user_data[user_id]

    # --- Start of Unchanged Message Formatting ---
    title = f"<b>📌 {lecture_data['title']}</b>\n" if lecture_data['title'] else ""
    date = f"🗓️ {lecture_data['date']}\n" if lecture_data['date'] else ""
    body = "🔗 Lecture and notes available below.\n\n"
    footer = "Provided by @studysmarterhub — share us for more!"
    full_text = f"{title}{date}{body}{footer}"

    buttons = [
        [InlineKeyboardButton("▶️ Watch Lecture", url=lecture_data["link"])]
    ]
    if lecture_data["notes"] and lecture_data["notes"].startswith("http"):
        buttons.append([InlineKeyboardButton("📝 View Notes", url=lecture_data["notes"])])

    promotional_text = "Access the aarambh batch free at @aarambh_batch_10th Join our backup at @studysmarterhub"
    encoded_promotional_text = quote(promotional_text)
    buttons.append([InlineKeyboardButton("🔗 Share", url=f"tg://msg?text={encoded_promotional_text}")])

    markup = InlineKeyboardMarkup(buttons)
    # --- End of Unchanged Message Formatting ---

    #
    # >>>>> THIS IS THE CORRECTED CODE BLOCK <<<<<
    #
    try:
        # Prepare the common arguments for sending the message
        send_args = {
            "chat_id": chat_id,
            "text": full_text,
            "parse_mode": ParseMode.HTML,
            "disable_web_page_preview": True,
            "reply_markup": markup
        }

        # Only add the message_thread_id if we are sending to a topic
        if topic_id:
            send_args["message_thread_id"] = topic_id
        
        # Send the message using the prepared arguments
        await client.send_message(**send_args)

        await callback_query.answer(f"Sent to {destination_name} successfully!", show_alert=True)
        await callback_query.message.edit_text(f"✅ The lecture has been sent to **{destination_name}**.")

    except Exception as e:
        # This will now show the REAL error, like the 'unexpected keyword' one
        error_message = str(e)
        await callback_query.answer(f"Failed to send: {error_message}", show_alert=True)
        await callback_query.message.edit_text(
            f"❌ An error occurred while sending the message to **{destination_name}**.\n\n"
            f"**Error:** `{error_message}`\n\n"
            "Please ensure the bot is an admin in the destination and that your Pyrogram version is up-to-date."
        )
    # >>>>> END OF CORRECTED CODE BLOCK <<<<<

    # Finally, clear the user's data after the message has been sent.
    if user_id in user_data:
        del user_data[user_id]

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
    print("Starting Pyrogram bot in the main thread...")
    pyro.run()
