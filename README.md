# Telegram Daily Quotes & Advice Bot

## What it does
- `/start` — subscribes the user to a daily quote
- `/stop` — unsubscribes
- `/quote` — sends a random quote right now
- `/advice` — sends a random piece of advice right now
- Once a day (default 8:00 UTC), automatically messages every subscribed user with a quote

## 1. Get a fresh bot token
If you ever pasted your token somewhere public (chat, email, GitHub), revoke it first:
BotFather → `/mybots` → your bot → API Token → Revoke current token → copy the new one.

## 2. Run it locally (to test)
```bash
cd telegram_quote_bot
pip install -r requirements.txt
export BOT_TOKEN="your-new-token-here"
python bot.py
```
Open Telegram, message your bot `/start`, then try `/quote` and `/advice`.

Leave it running (in a terminal, or `screen`/`tmux`) to test the daily broadcast —
or temporarily change `DAILY_HOUR_UTC` in `bot.py` to a couple minutes from now to see it fire.

## 3. Deploy so it runs 24/7
Free options that work well for this kind of bot:

**Railway.app** (recommended, easiest)
1. Push this folder to a GitHub repo (don't commit `users.json` or any token)
2. New Project → Deploy from GitHub repo
3. Add environment variable `BOT_TOKEN` in the Railway dashboard
4. Set the start command: `python bot.py`

**Render.com**
1. New → Background Worker → connect your repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `python bot.py`
4. Add `BOT_TOKEN` under Environment

## Notes
- User chat IDs are stored in `users.json` (created automatically). On platforms with ephemeral file systems (like Render's free tier), this resets on redeploy — for a permanent bot, swap this for a small database (SQLite file with a persistent disk, or Postgres) later.
- Quotes come from the free ZenQuotes and Advice Slip APIs, with a local fallback if they're down.
- Never commit your bot token to GitHub. Always use an environment variable.
