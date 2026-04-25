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

# ── Cross-sectional strategy settings ────────────────────────────────────────
# CROSS_TOPN : number of top/bottom ranked tickers to flag as BUY/SELL.
#              e.g. 3 means the 3 most oversold → BUY, 3 most overbought → SELL
CROSS_TOPN = 3

# ── RSI divergence settings ───────────────────────────────────────────────────
# RSI_PERIOD        : RSI calculation period
# RSI_SWING_WINDOW  : bars to scan left/right when identifying swing points
# RSI_LOOKBACK      : how far back (in bars) to search for a prior swing point
RSI_PERIOD       = 14
RSI_SWING_WINDOW = 3
RSI_LOOKBACK     = 40