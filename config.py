# config.py — Central configuration. Keep this file out of version control.
# Copy to config.py and fill in your values (do not commit to git).

# ── Telegram ──────────────────────────────────────────────────────────────────
# 1. Message @BotFather on Telegram → /newbot → copy the token below
# 2. Start a chat with your bot, then visit:
#    https://api.telegram.org/bot<TOKEN>/getUpdates
#    to find your chat_id
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID_HERE"

# ── Signal settings ───────────────────────────────────────────────────────────
# Periods refer to 30m candles, not days.
# e.g. EMA_FAST=20 = 20 × 30m bars = 10 hours of trading time
EMA_FAST = 20
EMA_SLOW = 50