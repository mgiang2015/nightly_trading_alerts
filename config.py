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

# ── Fundamental filter settings ──────────────────────────────────────────────
# Fundamentals are fetched weekly and cached in SQLite.
# Stocks that fail the thresholds below are flagged with ⚠️ in Telegram
# but signals are NOT suppressed — the flag is informational.
#
# Three sector profiles are applied (see tickers.py SECTOR_MAP):
#
#   BANK      — P/B only. D/E is meaningless for banks (their business model
#               is to hold deposits as "debt"). High P/B for a bank (>2×)
#               means the market is pricing in strong future returns.
#
#   REIT      — D/E and dividend yield. P/B less relevant since REIT value
#               is better measured by NAV discount/premium. MAS permits up
#               to 50% gearing (~1.0× D/E), so flag above that. Yield below
#               4% on an SGX REIT is unusually low and worth flagging.
#
#   INDUSTRIAL — Standard P/B and D/E. Dividend yield not thresholded here
#               as it varies widely across non-financial sectors.
#
# Set any threshold to None to disable that check.

FUND_CACHE_DAYS = 7   # days before cached fundamentals are refreshed

FUND_THRESHOLDS = {
    "bank": {
        "max_pb":        2.0,    # banks above 2× P/B are priced for perfection
        "min_div_yield": None,
        "max_de":        None,   # D/E not meaningful for banks
    },
    "reit": {
        "max_pb":        None,   # NAV discount is more relevant than P/B for REITs
        "min_div_yield": 4.0,    # SGX REITs below 4% yield are unusually low
        "max_de":        1.0,    # MAS 50% gearing limit ≈ 1.0× D/E
    },
    "industrial": {
        "max_pb":        3.0,    # high P/B signals limited margin of safety
        "min_div_yield": None,
        "max_de":        2.0,    # above 2× D/E introduces meaningful financial risk
    },
}

# ── RSI divergence settings ───────────────────────────────────────────────────
# RSI_PERIOD        : RSI calculation period
# RSI_SWING_WINDOW  : bars to scan left/right when identifying swing points
# RSI_LOOKBACK      : how far back (in bars) to search for a prior swing point
RSI_PERIOD       = 14
RSI_SWING_WINDOW = 3
RSI_LOOKBACK     = 40