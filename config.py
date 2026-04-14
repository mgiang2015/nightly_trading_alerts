# config.py — Non-secret configuration only.
# Telegram credentials are read from environment variables, not stored here.
# See README.md for setup instructions.

# ── EMA crossover settings ────────────────────────────────────────────────────
# Periods refer to 30m candles, not days.
# e.g. EMA_FAST=20 = 20 × 30m bars = 10 hours of trading time
EMA_FAST = 20
EMA_SLOW = 50

# ── Volume-confirmed breakout settings ───────────────────────────────────────
# BREAKOUT_WINDOW   : number of bars to look back for the recent high/low
# VOLUME_MULTIPLIER : minimum ratio of current bar volume to rolling average
#                     e.g. 1.5 means volume must be 50% above the recent average
BREAKOUT_WINDOW    = 20
VOLUME_MULTIPLIER  = 1.5