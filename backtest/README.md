# Backtesting

This folder contains the backtesting engine and its results. Backtesting lets
you simulate how a trading strategy would have performed on historical data —
before you risk any real money on it.

---

## How to run

```bash
cd /path/to/nightly-trading-alerts
export $(cat .env | xargs) && python run_backtest.py
```

`run_backtest.py` lives in the project root (one level above this folder).
That is the only file you need to edit.

---

## Configuration parameters

Open `run_backtest.py` and edit the variables at the top of the file.

### `STRATEGY`

The strategy you want to test. Swap this to any strategy class:

```python
STRATEGY = DailyReturnStrategy(top_n=3)    # default
STRATEGY = EMACrossStrategy()
STRATEGY = VolumeBreakoutStrategy()
STRATEGY = RSIDivergenceStrategy()
```

Each strategy has its own parameters in brackets. For example,
`DailyReturnStrategy(top_n=3)` means "flag the 3 most oversold stocks as BUY
and the 3 most overbought as SELL each day." Increasing `top_n` means more
positions open simultaneously.

---

### `TICKERS`

The list of stocks to include in the backtest.

```python
TICKERS = WATCHLIST                        # all 25 STI stocks from .env (default)
TICKERS = ["D05.SI", "O39.SI", "U11.SI"]  # custom subset
```

More tickers gives a more realistic picture of the strategy's cross-sectional
behaviour (especially for `DailyReturnStrategy` which ranks stocks against each
other). Fewer tickers runs faster and is useful for quick experiments.

---

### `PERIOD`

How much historical data to fetch from Yahoo Finance.

```python
PERIOD = "5y"    # 5 years (default, ~1,250 trading days)
PERIOD = "max"   # full available history (~10–20 years for STI stocks)
PERIOD = "2y"    # 2 years (faster, less data)
PERIOD = "1y"    # 1 year (very limited — results may not be reliable)
```

Longer periods produce more statistically reliable results because the strategy
goes through more market conditions (bull runs, crashes, sideways markets).
5 years is a good minimum. Use `"max"` when you want the most thorough test.

---

### `INITIAL_CAPITAL`

The simulated starting amount in SGD.

```python
INITIAL_CAPITAL = 10_000.0   # default
```

This does not affect the percentage-based metrics (total return %, CAGR, Sharpe,
max drawdown). It only changes the absolute dollar figures (final value, P&L per
trade). Set it to whatever you would realistically invest.

---

### `WARMUP_BARS`

The number of trading days to skip at the start before the first trade.

```python
WARMUP_BARS = 60   # default (approximately 3 months)
```

Indicators like EMA and RSI need a certain amount of historical data before they
produce meaningful values. During the warmup period the backtester runs the
strategy but does not open any positions. The default of 60 days is sufficient
for all current strategies. You generally do not need to change this.

---

## Understanding the results

When you run the backtest, a summary is printed to the terminal:

```
────────────────────────────────────────────────────────
  Backtest — Daily Return mean reversion (top/bottom 3)
────────────────────────────────────────────────────────
  Initial capital : SGD       10,000.00
  Final value     : SGD       18,432.11
  Total return    :              +84.32%
  CAGR            :              +12.97%
  Sharpe ratio    :               1.243
  Max drawdown    :              -22.41%
  Trades          :                 312
  Win rate        :               54.2%
  Avg trade ret   :               +0.83%
────────────────────────────────────────────────────────
```

Here is what each line means:

---

### Initial capital
The amount of SGD you started with — set by `INITIAL_CAPITAL` in your config.

---

### Final value
How much the portfolio would be worth at the end of the backtest period, after
all positions are closed.

> **Example:** Starting with SGD 10,000 and ending with SGD 18,432 means the
> strategy grew your money by SGD 8,432 over the period.

---

### Total return
The overall percentage gain or loss from start to finish.

> **Example:** +84.32% means the portfolio grew by 84.32% over the full period.
> A negative number means the strategy lost money overall.

This is the simplest measure of performance but does not account for how long
the period was. Two strategies both showing +50% total return are very different
if one took 2 years and the other took 10 years — which is why CAGR exists.

---

### CAGR (Compound Annual Growth Rate)
The equivalent yearly return if the strategy grew at a steady rate each year.
This is the most useful single number for comparing strategies across different
time periods.

> **Example:** +12.97% CAGR means the strategy grew at the same rate as if it
> earned 12.97% every single year, compounded. This lets you compare fairly: a
> strategy running for 2 years and one running for 10 years can both be
> expressed as a yearly rate.

**Benchmark:** The STI index historically returns around 5–8% per year. A
strategy consistently above 10% CAGR is performing well. Below the index
CAGR means you would have been better off buying an STI ETF.

---

### Sharpe ratio
A measure of how much return you earn for each unit of risk taken. Higher is
better. It answers the question: "is this strategy's return worth the
volatility it puts you through?"

| Sharpe ratio | What it means |
|---|---|
| Below 0 | Strategy loses money on a risk-adjusted basis |
| 0 – 0.5 | Poor — not worth the risk |
| 0.5 – 1.0 | Acceptable |
| 1.0 – 2.0 | Good — solid risk-adjusted returns |
| Above 2.0 | Excellent — rare in real markets |

The NTU FYP paper's best strategies reached Sharpe ratios of 3–4 with market
beta hedging. Without hedging, a Sharpe above 1.0 is a good result.

> **Example:** 1.243 is a good result — the strategy earns meaningfully more
> than what the volatility would suggest as fair compensation.

---

### Max drawdown
The largest peak-to-trough loss the portfolio experienced at any point during
the backtest. Always shown as a negative number.

> **Example:** -22.41% means that at some point during the backtest, the
> portfolio fell 22.41% from its highest value before recovering. If your
> portfolio peaked at SGD 15,000 and then dropped to SGD 11,640 before
> climbing again, that is a 22.41% drawdown.

This is the most important risk metric. It tells you the worst-case paper loss
you would have had to stomach without panic-selling. A strategy with a great
CAGR but -60% max drawdown is hard to hold through in practice.

**Rule of thumb:** For a personal account without hedging, a max drawdown
below 30% is comfortable. Above 40% starts becoming psychologically difficult
to hold.

---

### Trades
The total number of individual buy-and-sell round trips completed during the
backtest period.

> **Example:** 312 trades over 5 years is roughly 62 trades per year, or about
> 5 per month — a moderate frequency for a daily strategy.

A very high trade count on a short period may indicate the strategy is too
reactive (entering and exiting too often). A very low trade count may mean the
signals are too rare to be useful in practice.

---

### Win rate
The percentage of trades that closed with a profit (exit price higher than
entry price).

> **Example:** 54.2% means 54.2 out of every 100 trades made money. The
> remaining 45.8% were losers.

Win rate alone does not determine whether a strategy is profitable. A strategy
that wins 40% of the time but makes 3× on winners and loses 1× on losers is
far more profitable than one that wins 70% of the time but makes tiny gains
and takes large losses. Always look at win rate alongside average trade return.

---

### Avg trade return
The average percentage gain or loss across all individual trades.

> **Example:** +0.83% means on average each trade returned 0.83%. Small
> but positive — consistent with a mean-reversion strategy that makes many
> small gains rather than a few large ones.

A negative average trade return with a high win rate is a red flag — it can
indicate a strategy that wins small and loses big, which eventually blows up.

---

## Output files

Two CSV files are saved to `backtest/results/` after each run:

### `{strategy_name}_equity.csv`
A daily record of the total portfolio value from start to finish. Each row is
one trading day. You can open this in Excel or plot it in Python to visualise
the equity curve — the shape of this curve tells you a lot about the strategy's
behaviour over time.

```
datetime, equity
2020-01-02, 10000.00
2020-01-03, 10043.21
2020-01-06, 10091.54
...
```

### `{strategy_name}_trades.csv`
A log of every individual trade. Each row is one completed buy-and-sell.

| Column | Meaning |
|---|---|
| `ticker` | The stock that was traded |
| `entry_date` | The date the position was opened (bought) |
| `exit_date` | The date the position was closed (sold) |
| `entry_price` | The price paid per share on entry |
| `exit_price` | The price received per share on exit |
| `shares` | The number of shares held |
| `pnl` | Profit or loss in SGD for this trade (negative = loss) |
| `return_pct` | Percentage return for this trade |

---

## Important limitations

**No transaction costs.** Real-world trading involves brokerage fees (typically
SGD 10–25 per trade on SGX, or 0.08–0.1% of trade value). With 300+ trades
over 5 years, fees can meaningfully reduce actual returns. A strategy with
+12% CAGR before costs may drop to +9–10% after realistic fees.

**Long-only.** The backtester never shorts a stock. SELL signals cause the
strategy to exit an existing position, not open a short. The paper's best
results involved short selling — those Sharpe ratios are not directly
replicable here without a short-selling broker account.

**Equal position sizing.** Capital is split evenly across all open positions.
This is simple but not optimal — in practice you might size positions based on
conviction, volatility, or risk budget.

**No slippage.** Trades execute at the exact open price. In reality, large
orders or illiquid stocks can move the price against you slightly.

**Past performance does not guarantee future results.** A strategy that worked
well on 2020–2025 data may not work the same way going forward, especially as
more market participants adopt similar signals.