"""
LifeSpark - Telegram Daily Quotes & Advice Bot
-----------------------------------------------
Features:
- /start          -> registers the user for the daily broadcast
- /stop           -> unsubscribes the user
- /today          -> Today's Quote
- /advice         -> Life Advice
- /motivation     -> Motivation
- /relationships  -> Relationships
- /mindset        -> Mindset
- /night          -> Night Reflection
- Daily job       -> automatically sends "Today's Quote" to every subscribed user

SETUP:
1. pip install -r requirements.txt
2. Set your bot token as an environment variable (do NOT hardcode it):
   export BOT_TOKEN="your-telegram-bot-token"
3. Run: python bot.py

Users are stored in users.json (chat IDs of everyone who has /start'd the bot).
Content is a curated local library per category, so it works instantly with
no external API dependency (fast and always available).
"""

import json
import logging
import os
import random
from pathlib import Path

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from quotes_data import QUOTE_LIBRARY

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable not set. "
        "Run: export BOT_TOKEN='your-token-here' before starting the bot."
    )

USERS_FILE = Path(__file__).parent / "users.json"

# Daily broadcast time, in UTC. 7:00 UTC = 8:00 AM in Nigeria (WAT, UTC+1).
DAILY_HOUR_UTC = 7
DAILY_MINUTE_UTC = 0

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Content library
# ---------------------------------------------------------------------------

CATEGORIES = {
    "today": {
        "label": "Today's Quote",
        "emoji": "💬",
        "items": [
            "The best time to plant a tree was 20 years ago. The second best time is now.",
            "You don't have to be great to start, but you have to start to be great.",
            "Difficult roads often lead to beautiful destinations.",
            "Small steps every day add up to big results.",
            "Your future is created by what you do today, not tomorrow.",
            "What lies behind you and what lies ahead matter less than what lies within you.",
            "Do what you can, with what you have, where you are.",
            "It always seems impossible until it's done.",
            "The only way to do great work is to love what you do.",
            "Turn your wounds into wisdom.",
        ],
    },
    "advice": {
        "label": "Life Advice",
        "emoji": "🌱",
        "items": [
            "Focus on progress, not perfection.",
            "Say no to things that don't align with your goals.",
            "Rest is productive too. Don't skip it.",
            "Write down your goals. It makes them real.",
            "Ask for help before you're overwhelmed, not after.",
            "Don't compare your chapter one to someone else's chapter twenty.",
            "Protect your peace like it's your job, because it is.",
            "You can't pour from an empty cup. Take care of yourself first.",
            "Slow progress is still progress. Keep going.",
            "Choose your battles. Not everything deserves your energy.",
        ],
    },
    "motivation": {
        "label": "Motivation",
        "emoji": "💪",
        "items": [
            "Push yourself, because no one else is going to do it for you.",
            "Great things never came from comfort zones.",
            "Dream it. Believe it. Build it.",
            "The pain of discipline weighs ounces, the pain of regret weighs tons.",
            "Success is the sum of small efforts repeated daily.",
            "You are capable of more than you know.",
            "Don't stop when you're tired. Stop when you're done.",
            "Every accomplishment starts with the decision to try.",
            "Discipline is choosing between what you want now and what you want most.",
            "Wake up with determination, go to bed with satisfaction.",
        ],
    },
    "relationships": {
        "label": "Relationships",
        "emoji": "❤️",
        "items": [
            "The best relationships are built on honesty, even when it's uncomfortable.",
            "Listen to understand, not just to reply.",
            "Show up for people consistently, not just when it's convenient.",
            "A good relationship gives you freedom, not control.",
            "Say what you mean, and mean what you say, kindly.",
            "The people who matter will always make time for you.",
            "Love grows where forgiveness lives.",
            "Healthy relationships take work from both sides, not just one.",
            "Be someone's safe place, not another source of stress.",
            "Real connection is built in the small, everyday moments.",
        ],
    },
    "mindset": {
        "label": "Mindset",
        "emoji": "🧠",
        "items": [
            "Your mindset shapes your reality more than your circumstances do.",
            "Whether you think you can or think you can't, you're right.",
            "A fixed mindset says 'I can't'. A growth mindset says 'not yet'.",
            "Change the way you look at things, and the things you look at change.",
            "Your thoughts become your words, your words become your actions.",
            "Replace 'I have to' with 'I get to'. It changes everything.",
            "The mind is everything. What you think, you become.",
            "Train your mind to see the good in every situation.",
            "You are not your thoughts. You are the one who notices them.",
            "Progress starts with believing change is possible.",
        ],
    },
    "night": {
        "label": "Night Reflection",
        "emoji": "🌙",
        "items": [
            "Today is done. Let it go, and rest well.",
            "You showed up today. That's enough.",
            "Not every day will be perfect, and that's okay.",
            "Reflect on one good thing that happened today before you sleep.",
            "Tomorrow is a fresh page. Tonight, just rest.",
            "Forgive yourself for today's mistakes. Growth isn't linear.",
            "Close the day with gratitude, not regret.",
            "You did your best with what you had today.",
            "Let go of what you can't control, and rest in what you can.",
            "Sleep well. You've earned it.",
        ],
    },
}

# Merge the large auto-sourced quote library on top of the hand-picked lines above,
# so each category has hundreds of options instead of repeating quickly.
for _key, _extra in QUOTE_LIBRARY.items():
    if _key in CATEGORIES:
        CATEGORIES[_key]["items"].extend(_extra)

FALLBACK_TEXT = "Take a breath. You're doing better than you think."

# Tracks the last quote index shown per category, globally, so consecutive
# sends (across all users) don't repeat the same line back-to-back.
_last_shown_index = {}

# ---------------------------------------------------------------------------
# User storage (very simple JSON file; swap for a real DB if you scale up)
# ---------------------------------------------------------------------------

def load_users() -> set[int]:
    if USERS_FILE.exists():
        return set(json.loads(USERS_FILE.read_text()))
    return set()


def save_users(users: set[int]) -> None:
    USERS_FILE.write_text(json.dumps(list(users)))


# ---------------------------------------------------------------------------
# Content picker
# ---------------------------------------------------------------------------

def get_content(category_key: str) -> str:
    category = CATEGORIES.get(category_key)
    if not category:
        return FALLBACK_TEXT
    items = category["items"]
    if len(items) > 1:
        # Avoid repeating the exact same line that was just shown.
        last_index = _last_shown_index.get(category_key)
        index = random.randrange(len(items))
        while index == last_index:
            index = random.randrange(len(items))
        _last_shown_index[category_key] = index
        text = items[index]
    else:
        text = items[0] if items else FALLBACK_TEXT
    return f"{category['emoji']} {category['label']}\n\n{text}"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

COMMAND_LIST_TEXT = (
    "Commands:\n"
    "💬 /today - Today's Quote\n"
    "🌱 /advice - Life Advice\n"
    "💪 /motivation - Motivation\n"
    "❤️ /relationships - Relationships\n"
    "🧠 /mindset - Mindset\n"
    "🌙 /night - Night Reflection\n"
    "/stop - unsubscribe from daily messages\n\n"
    "Tip: you can also just tap a button below instead of typing a command."
)

# Maps the exact text shown on each menu button back to its category key,
# so tapping a button works exactly like typing the matching command.
BUTTON_LABELS = {
    "💬 Today's Quote": "today",
    "🌱 Life Advice": "advice",
    "💪 Motivation": "motivation",
    "❤️ Relationships": "relationships",
    "🧠 Mindset": "mindset",
    "🌙 Night Reflection": "night",
}

MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["💬 Today's Quote", "🌱 Life Advice"],
        ["💪 Motivation", "❤️ Relationships"],
        ["🧠 Mindset", "🌙 Night Reflection"],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    users.add(update.effective_chat.id)
    save_users(users)
    await update.message.reply_text(
        f"Welcome! You're now subscribed to daily quotes and advice.\n\n{COMMAND_LIST_TEXT}",
        reply_markup=MENU_KEYBOARD,
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    users.discard(update.effective_chat.id)
    save_users(users)
    await update.message.reply_text("You've been unsubscribed from daily messages. Send /start anytime to rejoin.")


async def category_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # context.chat_data / job stores which category via the command itself
    command = update.message.text.split()[0].lstrip("/").split("@")[0]
    await update.message.reply_text(get_content(command))


async def menu_button_pressed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    category_key = BUTTON_LABELS.get(update.message.text)
    if category_key:
        await update.message.reply_text(get_content(category_key))


# ---------------------------------------------------------------------------
# Daily broadcast job
# ---------------------------------------------------------------------------

async def send_daily_broadcast(context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    if not users:
        logger.info("No subscribed users, skipping daily broadcast.")
        return

    message = get_content("today")
    logger.info("Sending daily broadcast to %d users", len(users))

    for chat_id in list(users):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            # If a user blocked the bot, remove them so we stop retrying
            logger.warning("Failed to message %s: %s", chat_id, e)
            users.discard(chat_id)

    save_users(users)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    for key in CATEGORIES:
        app.add_handler(CommandHandler(key, category_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_button_pressed))

    # Schedule the daily job
    from datetime import time as dtime

    app.job_queue.run_daily(
        send_daily_broadcast, time=dtime(hour=DAILY_HOUR_UTC, minute=DAILY_MINUTE_UTC)
    )

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
       
