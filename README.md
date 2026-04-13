# Trading Signal System — Phase 1

Nightly EMA crossover signals for SGX/US tickers, delivered via Telegram.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
Edit `config.py` and fill in your Telegram credentials:

```python
TELEGRAM_TOKEN   = "123456:ABC-..."   # from @BotFather
TELEGRAM_CHAT_ID = "987654321"        # from api.telegram.org/bot<TOKEN>/getUpdates
```

**Getting your Telegram credentials:**
1. Open Telegram → search `@BotFather` → send `/newbot`
2. Follow prompts → copy the token into `config.py`
3. Start a chat with your new bot (send it any message)
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
5. Find `"chat": {"id": ...}` — that is your `TELEGRAM_CHAT_ID`

### 3. Edit tickers
In `main.py`, edit the `TICKERS` list:
```python
TICKERS = [
    "ES3.SI",   # STI ETF
    "D05.SI",   # DBS
    # add more here...
]
```

SGX tickers use the `.SI` suffix on Yahoo Finance.

### 4. Test run
```bash
python main.py
```

If Telegram is not configured yet, the report prints to stdout instead.

### 5. Schedule nightly runs

**Linux/macOS (cron):**
```bash
crontab -e
```
Add this line to run at 19:00 SGT (11:00 UTC) every weekday:
```
0 11 * * 1-5 cd /path/to/trading_signals && /usr/bin/python3 main.py >> logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
- Open Task Scheduler → Create Basic Task
- Trigger: Daily at 7:00 PM
- Action: Start a program → `python.exe`
- Arguments: `C:\path\to\trading_signals\main.py`

---

## Project structure
```
trading_signals/
├── main.py               # Pipeline entry point
├── config.py             # Credentials & settings
├── requirements.txt
├── data/
│   ├── fetcher.py        # yfinance download + SQLite storage
│   └── prices.db         # created automatically on first run
├── signals/
│   └── engine.py         # BaseStrategy + EMACrossStrategy
├── alerts/
│   └── telegram_bot.py   # Telegram send_message wrapper
├── backtest/             # Phase 2 — vectorbt scripts go here
└── logs/
    └── pipeline.log      # auto-created
```

---

## Adding a new strategy (Phase 2)

```python
# signals/engine.py
class MyMLStrategy(BaseStrategy):
    def compute(self, df: pd.DataFrame) -> dict:
        # feature engineering, model inference, etc.
        return {"signal": "BUY", "detail": "...", "close": df["close"].iloc[-1]}
```

Then in `main.py`:
```python
from signals.engine import MyMLStrategy
signals = compute_signals(data, strategy=MyMLStrategy())
```

No other changes needed.
