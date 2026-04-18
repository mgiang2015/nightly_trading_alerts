# Nightly Trading Signal System

Nightly signal analysis for SGX/US tickers, delivered via Telegram.
Fetches 30-minute candles from Yahoo Finance, computes configurable signals,
and sends a formatted summary each evening.

---

## Strategies

| Strategy | Signal logic |
|---|---|
| `EMACrossStrategy` | BUY/SELL when fast EMA crosses above/below slow EMA |
| `VolumeBreakoutStrategy` | BUY/SELL when price breaks a recent high/low with above-average volume |
| `RSIDivergenceStrategy` | BUY/SELL on RSI divergence confirmed by slow EMA trend direction |

The active strategy is set in `main.py`. All strategies share a common
`BaseStrategy` interface — adding a new one requires only a new file in
`signals/` and a one-line addition to `signals/__init__.py`.

---

## Project structure

```
nightly-trading-alerts/
├── main.py                    # Pipeline entry point — run this
├── config.py                  # Non-secret settings (EMA periods, etc.)
├── tickers.py                 # Loads WATCHLIST from environment
├── requirements.txt
├── pytest.ini
├── .env.example               # Copy to .env and fill in credentials
├── .gitignore
│
├── data/
│   ├── fetcher.py             # yfinance 30m download + SQLite storage
│   └── prices.db              # auto-created on first run
│
├── signals/
│   ├── __init__.py            # Re-exports all strategies and compute_signals
│   ├── base.py                # BaseStrategy abstract class
│   ├── engine.py              # compute_signals() runner
│   ├── ema_cross.py           # EMACrossStrategy
│   ├── volume_breakout.py     # VolumeBreakoutStrategy
│   └── rsi_divergence.py      # RSIDivergenceStrategy
│
├── alerts/
│   └── telegram_bot.py        # Formats and sends Telegram message
│
├── tests/
│   ├── conftest.py            # Shared fixtures (make_ohlcv, mem_db)
│   ├── test_engine.py         # EMACrossStrategy + compute_signals tests
│   ├── test_fetcher.py        # SQLite storage layer tests
│   ├── test_telegram.py       # Message formatter + escape tests
│   ├── test_volume_breakout.py
│   └── test_rsi_divergence.py
│
├── backtest/                  # Phase 2 — vectorbt scripts go here
└── logs/
    └── pipeline.log           # auto-created
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

All credentials and the ticker watchlist are stored in a `.env` file that is
never committed to version control.

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```
TELEGRAM_TOKEN=6767676767:AaaBBbCCCc
TELEGRAM_CHAT_ID=6767676767
WATCHLIST=ES3.SI,D05.SI,O39.SI,U11.SI
```

**Getting your Telegram credentials:**
1. Open Telegram → search `@BotFather` → `/newbot` → follow prompts → copy token
2. Start a chat with your new bot (send it any message)
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
4. Find `"chat": {"id": ...}` — that is your `TELEGRAM_CHAT_ID`

**Ticker format:** SGX tickers use the `.SI` suffix (e.g. `D05.SI`, `ES3.SI`).
US tickers use plain symbols (e.g. `AAPL`, `SPY`).

### 3. Choose a strategy

Open `main.py` and set the strategy you want to run:

```python
from signals import compute_signals, EMACrossStrategy
from signals import VolumeBreakoutStrategy, RSIDivergenceStrategy

# Pick one:
signals, strategy_name = compute_signals(data)                          # default: EMA crossover
signals, strategy_name = compute_signals(data, VolumeBreakoutStrategy())
signals, strategy_name = compute_signals(data, RSIDivergenceStrategy())
```

Strategy parameters are tuned in `config.py`.

### 4. Run

Always run from the project root so Python can resolve package imports:

```bash
cd /path/to/nightly-trading-alerts
export $(cat .env | xargs) && python main.py
```

If Telegram is not configured the report prints to stdout instead, which is
useful for testing the pipeline without a bot set up.

### 5. Schedule nightly runs

SGX closes at 17:30 SGT. The pipeline is best run at ~18:00 SGT (10:00 UTC)
to ensure the final candles have settled.

**Linux/macOS (cron):**

```bash
crontab -e
```

```
0 10 * * 1-5 cd /path/to/nightly-trading-alerts && export $(cat .env | xargs) && python3 main.py >> logs/cron.log 2>&1
```

---

## Running tests

```bash
cd /path/to/nightly-trading-alerts
export $(cat .env | xargs) && pytest
```

To run a specific test file:

```bash
pytest tests/test_engine.py
pytest tests/test_volume_breakout.py -v
```

Tests use in-memory SQLite and synthetic price data — no network calls, no real credentials required. The `WATCHLIST` env var is still needed because `tickers.py` is imported at module level; set a dummy value if running tests without a `.env`:

```bash
WATCHLIST=TEST.SI pytest
```

---

## Configuration reference

All non-secret settings live in `config.py`:

```python
# EMA crossover
EMA_FAST = 20          # fast EMA period (in 30m bars)
EMA_SLOW = 50          # slow EMA period (in 30m bars)

# Volume breakout
BREAKOUT_WINDOW   = 20   # bars to look back for recent high/low
VOLUME_MULTIPLIER = 1.5  # minimum volume ratio vs rolling average

# RSI divergence
RSI_PERIOD       = 14   # RSI calculation period
RSI_SWING_WINDOW = 3    # half-width for swing point detection
RSI_LOOKBACK     = 40   # bars to scan back for a prior swing
```

All periods are in **30-minute bars**. `EMA_FAST=20` = 20 × 30m = 10 hours
of market time.

---

## Adding a new strategy

1. Create `signals/my_strategy.py` with a class that extends `BaseStrategy`:

```python
from signals.base import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "My strategy"

    def compute(self, df: pd.DataFrame) -> dict:
        # df has columns: open, high, low, close, volume
        return {
            "signal": "BUY",   # "BUY" | "SELL" | "HOLD"
            "close":  df["close"].iloc[-1],
            "detail": "explanation string",
        }
```

2. Add it to `signals/__init__.py`:

```python
from signals.my_strategy import MyStrategy
```

3. Use it in `main.py`:

```python
from signals import MyStrategy
signals, strategy_name = compute_signals(data, strategy=MyStrategy())
```

No other changes needed.