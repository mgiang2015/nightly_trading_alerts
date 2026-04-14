# config.py — Non-secret configuration only.
# Telegram credentials are read from environment variables, not stored here.
# See README.md for setup instructions.

# ── Signal settings ───────────────────────────────────────────────────────────
# Periods refer to 30m candles, not days.
# e.g. EMA_FAST=20 = 20 × 30m bars = 10 hours of trading time
EMA_FAST = 20
EMA_SLOW = 50