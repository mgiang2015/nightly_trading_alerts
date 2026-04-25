# Nightly Trading Signal System

Nightly signal analysis for SGX/US tickers, delivered via Telegram.
Fetches OHLCV data from Yahoo Finance, computes configurable signals,
and sends a formatted summary each evening.

---

## Strategies

Two interfaces are supported depending on whether a strategy is per-ticker
or cross-sectional:

**Per-ticker (`BaseStrategy`)** — each ticker is evaluated independently.
Uses 30-minute candles.

| Strategy | Signal logic |
|---|---|
| `EMACrossStrategy` | BUY/SELL when fast EMA crosses above/below slow EMA |
| `VolumeBreakoutStrategy` | BUY/SELL when price breaks a recent high/low with above-average volume |
| `RSIDivergenceStrategy` | BUY/SELL on RSI divergence confirmed by slow EMA trend direction |

**Cross-sectional (`BaseCrossStrategy`)** — all tickers are ranked against
each other before signals are assigned. Uses daily candles. Based on
[Cen Yu, NTU FYP 2023](https://hdl.handle.net/10356/167306).

| Strategy | Signal logic |
|---|---|
| `DailyReturnStrategy` | Ranks tickers by 1-day return; flags bottom-N as BUY (mean reversion), top-N as SELL |

The active strategies are configured in `main.py` via the `STRATEGIES` list.
Each entry is `(strategy_instance, interval)` — the pipeline fetches each
interval once and routes data accordingly.

---

## Project structure

```
nightly-trading-alerts/
├── main.py                    # Pipeline entry point — run this
├── run_backtest.py            # Backtesting entry point — edit and run
├── config.py                  # Non-secret settings (periods, thresholds)
├── tickers.py                 # Loads WATCHLIST from environment
├── requirements.txt
├── pytest.ini
├── pyproject.toml             # Ruff linter config
├── .env.example               # Copy to .env and fill in credentials
├── .gitignore
│
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions — lint + test on every PR
│
├── data/
│   ├── fetcher.py             # yfinance download + SQLite storage (30m + 1d)
│   └── prices.db              # auto-created on first run
│
├── signals/
│   ├── __init__.py            # Re-exports all strategies and compute_signals
│   ├── base.py                # BaseStrategy abstract class (per-ticker)
│   ├── base_cross.py          # BaseCrossStrategy abstract class (cross-sectional)
│   ├── engine.py              # compute_signals() runner — routes both interfaces
│   ├── ema_cross.py           # EMACrossStrategy
│   ├── volume_breakout.py     # VolumeBreakoutStrategy
│   ├── rsi_divergence.py      # RSIDivergenceStrategy
│   └── daily_return.py        # DailyReturnStrategy
│
├── alerts/
│   └── telegram_bot.py        # Formats and sends Telegram message
│
├── backtest/
│   ├── backtester.py          # Generic daily backtester
│   └── results/               # CSV outputs from run_backtest.py
│
├── tests/
│   ├── conftest.py            # Shared fixtures (make_ohlcv, mem_db)
│   ├── test_engine.py         # EMACrossStrategy + compute_signals tests
│   ├── test_fetcher.py        # SQLite storage layer tests
│   ├── test_telegram.py       # Message formatter + escape tests
│   ├── test_volume_breakout.py
│   ├── test_rsi_divergence.py
│   └── test_daily_return.py
│
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

Edit `.env` and fill in your values. The default watchlist is pre-populated
with the 25 STI constituents used in the NTU FYP paper:

```
TELEGRAM_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=987654321
WATCHLIST=D05.SI,O39.SI,U11.SI,...
```

**Getting your Telegram credentials:**
1. Open Telegram → search `@BotFather` → `/newbot` → follow prompts → copy token
2. Start a chat with your new bot (send it any message)
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
4. Find `"chat": {"id": ...}` — that is your `TELEGRAM_CHAT_ID`

**Ticker format:** SGX tickers use the `.SI` suffix (e.g. `D05.SI`, `ES3.SI`).
US tickers use plain symbols (e.g. `AAPL`, `SPY`).

### 3. Configure strategies

Open `main.py` and edit the `STRATEGIES` list. Each entry is a
`(strategy_instance, data_interval)` pair:

```python
STRATEGIES = [
    (EMACrossStrategy(),    "30m"),   # intraday — 30m candles
    (DailyReturnStrategy(), "1d"),    # cross-sectional — daily candles
]
```

The pipeline fetches each unique interval once, then runs all strategies
that share that interval against the same dataset. Adding a strategy is a
single line here — no other changes needed.

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

**Windows (Task Scheduler):**
- Open Task Scheduler → Create Basic Task
- Trigger: Daily, weekdays, 18:00
- Action: Start a program → `python.exe`
- Add arguments: `main.py`
- Start in: `C:\path\to\nightly-trading-alerts`
- Set environment variables via System Properties → Advanced → Environment Variables

---

## Backtesting

The backtester runs any strategy over historical daily data and reports the
same metrics used in the NTU FYP paper: total return, CAGR, Sharpe ratio,
and max drawdown.

### Running a backtest

```bash
export $(cat .env | xargs) && python run_backtest.py
```

Edit the top of `run_backtest.py` to configure the run:

```python
STRATEGY        = DailyReturnStrategy(top_n=3)   # strategy to test
TICKERS         = WATCHLIST                       # or a custom list
PERIOD          = "5y"                            # "5y", "max", "2y", etc.
INITIAL_CAPITAL = 10_000.0                        # starting capital in SGD
WARMUP_BARS     = 60                              # bars skipped before first trade
```

### Output

Results are printed to stdout and saved to `backtest/results/`:

```
──────────────────────────────────────────────────────
  Backtest — Daily Return mean reversion (top/bottom 3)
──────────────────────────────────────────────────────
  Initial capital : SGD       10,000.00
  Final value     : SGD       18,432.11
  Total return    :              +84.32%
  CAGR            :              +12.97%
  Sharpe ratio    :               1.243
  Max drawdown    :              -22.41%
  Trades          :                 312
  Win rate        :               54.2%
  Avg trade ret   :               +0.83%
──────────────────────────────────────────────────────
```

Two CSV files are saved per run:
- `{strategy_name}_equity.csv` — daily portfolio value (plot this to see the equity curve)
- `{strategy_name}_trades.csv` — every trade with entry/exit prices and P&L

### Design constraints

The backtester is intentionally simple:

- **Daily granularity only.** Not suitable for intraday strategies (EMA cross, RSI divergence, volume breakout) — those are designed around 30m bars and would behave differently on daily data.
- **Long-only.** SELL signals indicate positions to exit or avoid, not to short.
- **Equal position sizing.** Capital is split evenly across all open positions.
- **No transaction costs.** Add a cost parameter to `run_backtest.py` when you want more realistic results.
- **Look-ahead free.** On each bar, the strategy only sees data up to (but not including) that bar.

---

## Running tests

```bash
cd /path/to/nightly-trading-alerts
export $(cat .env | xargs) && pytest
```

To run a specific test file:

```bash
pytest tests/test_engine.py
pytest tests/test_daily_return.py -v
```

Tests use in-memory SQLite and synthetic price data — no network calls,
no real credentials required. The `WATCHLIST` env var is still needed
because `tickers.py` is imported at module level; set a dummy value if
running tests without a `.env`:

```bash
WATCHLIST=TEST.SI pytest
```

---

## CI / GitHub Actions

Every pull request runs linting and the full test suite automatically via
`.github/workflows/ci.yml`. The workflow triggers on PR open and on every
new commit pushed to the PR branch.

```
Lint (ruff) → Tests (pytest)
```

To see results, open a PR and click the **Checks** tab.

Linting rules are configured in `pyproject.toml`. The ruleset is intentionally
minimal (`E`, `F`, `I`) — errors, undefined names, and import ordering — to
catch real bugs without generating noise on stylistic choices.

---

## Configuration reference

All non-secret settings live in `config.py`:

```python
# EMA crossover (30m bars)
EMA_FAST = 20          # fast EMA period
EMA_SLOW = 50          # slow EMA period

# Volume breakout (30m bars)
BREAKOUT_WINDOW   = 20   # bars to look back for recent high/low
VOLUME_MULTIPLIER = 1.5  # minimum volume ratio vs rolling average

# Cross-sectional strategies (daily bars)
CROSS_TOPN = 3           # top/bottom N tickers flagged as BUY/SELL

# RSI divergence (30m bars)
RSI_PERIOD       = 14   # RSI calculation period
RSI_SWING_WINDOW = 3    # half-width for swing point detection
RSI_LOOKBACK     = 40   # bars to scan back for a prior swing
```

Intraday periods are in **30-minute bars**. `EMA_FAST=20` = 20 × 30m = 10 hours of market time.

---

## Adding a new strategy

**Per-ticker strategy** (processes each ticker independently, 30m data):

```python
# signals/my_strategy.py
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

**Cross-sectional strategy** (ranks all tickers together, daily data):

```python
# signals/my_cross_strategy.py
from signals.base_cross import BaseCrossStrategy
import pandas as pd

class MyCrossStrategy(BaseCrossStrategy):

    @property
    def name(self) -> str:
        return "My cross-sectional strategy"

    def compute_all(self, data: dict[str, pd.DataFrame]) -> list[dict]:
        # data is {ticker: df} for all tickers simultaneously
        results = []
        for ticker, df in data.items():
            results.append({
                "ticker": ticker,
                "signal": "HOLD",
                "close":  df["close"].iloc[-1],
                "detail": "explanation string",
            })
        return results
```

Then for either type:

1. Add to `signals/__init__.py`: `from signals.my_strategy import MyStrategy`
2. Add to `main.py` STRATEGIES list: `(MyStrategy(), "30m")`

No other changes needed.