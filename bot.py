"""
Telegram Daily Quotes & Advice Bot
-----------------------------------
Features:
- /start   -> registers the user for daily broadcasts
- /stop    -> unsubscribes the user
- /quote   -> sends a random quote on demand
- /advice  -> sends a random piece of advice on demand
- Daily job -> automatically sends a quote to every subscribed user

SETUP:
1. pip install -r requirements.txt
2. Set your bot token as an environment variable (do NOT hardcode it):
   export BOT_TOKEN="your-telegram-bot-token"
3. Run: python bot.py

Users are stored in users.json (chat IDs of everyone who has /start'd the bot).
Quotes come from the free ZenQuotes API (https://zenquotes.io), with a small
local fallback list in case the API is unreachable.
"""

import json
import logging
import os
import random
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

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
DAILY_HOUR_UTC = 8  # what time (UTC) the daily broadcast goes out; change as you like

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

FALLBACK_QUOTES = [
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "You don't have to be great to start, but you have to start to be great.",
    "Difficult roads often lead to beautiful destinations.",
    "Small steps every day add up to big results.",
    "Your future is created by what you do today, not tomorrow.",
]

FALLBACK_ADVICE = [
    "Focus on progress, not perfection.",
    "Say no to things that don't align with your goals.",
    "Rest is productive too. Don't skip it.",
    "Write down your goals. It makes them real.",
    "Ask for help before you're overwhelmed, not after.",
]

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
# Content fetchers
# ---------------------------------------------------------------------------

def get_quote() -> str:
    try:
        resp = requests.get("https://zenquotes.io/api/random", timeout=5)
        resp.raise_for_status()
        data = resp.json()[0]
        return f'"{data["q"]}" — {data["a"]}'
    except Exception as e:
        logger.warning("Quote API failed, using fallback: %s", e)
        return random.choice(FALLBACK_QUOTES)


def get_advice() -> str:
    try:
        resp = requests.get("https://api.adviceslip.com/advice", timeout=5)
        resp.raise_for_status()
        return resp.json()["slip"]["advice"]
    except Exception as e:
        logger.warning("Advice API failed, using fallback: %s", e)
        return random.choice(FALLBACK_ADVICE)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    users.add(update.effective_chat.id)
    save_users(users)
    await update.message.reply_text(
        "Welcome! You're now subscribed to daily quotes and advice.\n\n"
        "Commands:\n"
        "/quote - get a random quote\n"
        "/advice - get a random piece of advice\n"
        "/stop - unsubscribe from daily messages"
    )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    users.discard(update.effective_chat.id)
    save_users(users)
    await update.message.reply_text("You've been unsubscribed from daily messages. Send /start anytime to rejoin.")


async def quote_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(get_quote())


async def advice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(get_advice())


# ---------------------------------------------------------------------------
# Daily broadcast job
# ---------------------------------------------------------------------------

async def send_daily_broadcast(context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    if not users:
        logger.info("No subscribed users, skipping daily broadcast.")
        return

    message = get_quote()
    logger.info("Sending daily broadcast to %d users", len(users))

    for chat_id in list(users):
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"Your daily quote:\n\n{message}")
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
    app.add_handler(CommandHandler("quote", quote_cmd))
    app.add_handler(CommandHandler("advice", advice_cmd))

    # Schedule the daily job
    from datetime import time as dtime

    app.job_queue.run_daily(send_daily_broadcast, time=dtime(hour=DAILY_HOUR_UTC, minute=0))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
