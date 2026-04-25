# Signals — Strategy Reference

This folder contains all trading strategy implementations. Each strategy
generates BUY, SELL, or HOLD signals that are consumed by the nightly
pipeline and backtest engine.

---

## Architecture

Two interfaces are available depending on how a strategy generates signals:

**`BaseStrategy`** (`base.py`) — processes each ticker independently. Takes
a single ticker's OHLCV DataFrame and returns a signal dict. Suitable for
technical indicators that are self-contained per stock (EMA, RSI, volume).

**`BaseCrossStrategy`** (`base_cross.py`) — processes all tickers together
and ranks them against each other before assigning signals. Takes the full
`{ticker: DataFrame}` dict and returns a list of signal dicts. Required for
cross-sectional strategies where a signal depends on relative performance
across the universe (e.g. Daily Return mean reversion).

`engine.py` detects which interface a strategy implements and routes
accordingly — no changes to `main.py` or `run_backtest.py` are needed when
swapping strategies.

---

## Strategy index

| Strategy | Type | Data | Purpose |
|---|---|---|---|
| `EMACrossStrategy` | Per-ticker | 30m candles | Scaffolding — trend following |
| `VolumeBreakoutStrategy` | Per-ticker | 30m candles | Scaffolding — breakout with volume confirmation |
| `RSIDivergenceStrategy` | Per-ticker | 30m candles | Momentum divergence with trend filter |
| `DailyReturnStrategy` | Cross-sectional | Daily candles | Mean reversion based on NTU FYP paper |

---

## 1. EMA Crossover (`ema_cross.py`) — Scaffolding

Computes two exponential moving averages over 30-minute candles. A **BUY**
signal fires when the fast EMA crosses above the slow EMA (golden cross).
A **SELL** fires when the fast EMA crosses below the slow EMA (death cross).
HOLD on all other bars.

Default periods: `EMA_FAST = 20` bars (10 hours), `EMA_SLOW = 50` bars
(25 hours of SGX market time).

This strategy is implemented as a working baseline that establishes the
pipeline, signal format, and test infrastructure. It is not intended as a
proven edge on SGX — use the backtester to evaluate performance before
committing capital.

---

## 2. Volume-Confirmed Breakout (`volume_breakout.py`) — Scaffolding

Identifies price breakouts from a recent trading range confirmed by
above-average volume. A **BUY** fires when the close exceeds the highest
high of the prior N bars AND volume is at least `VOLUME_MULTIPLIER` times
the rolling average. A **SELL** fires on a breakdown below the recent low
with the same volume condition. HOLD otherwise.

Default parameters: `BREAKOUT_WINDOW = 20` bars, `VOLUME_MULTIPLIER = 1.5`.

The volume condition exists to filter out false breakouts, which are common
on SGX due to thin liquidity — a single block trade can move price above a
recent high without representing genuine market interest. A confirmed
breakout should show elevated volume from multiple participants.

This strategy is also implemented as scaffolding — a clean two-condition
signal that demonstrates the `BaseStrategy` interface alongside the EMA
strategy.

---

## 3. RSI Divergence with EMA Trend Filter (`rsi_divergence.py`)

Detects RSI divergence against price, confirmed by slow EMA trend direction.

**Bullish divergence (BUY):** price makes a lower low but RSI makes a higher
low — momentum is improving while price weakens. Only fires when slow EMA is
sloping upward.

**Bearish divergence (SELL):** price makes a higher high but RSI makes a
lower high — momentum is fading while price pushes higher. Only fires when
slow EMA is sloping downward.

HOLD when no divergence is detected or the EMA filter blocks the signal.
Signals are infrequent by design — the double condition (divergence + trend
filter) means many nights produce nothing.

Default parameters: `RSI_PERIOD = 14`, `RSI_SWING_WINDOW = 3`,
`RSI_LOOKBACK = 40`, `EMA_SLOW = 50`.

---

## 4. Daily Return Mean Reversion (`daily_return.py`)

Ranks all tickers by their 1-day return. The bottom-N tickers (biggest losers)
are flagged **BUY** and the top-N (biggest winners) are flagged **SELL**. All
others are HOLD. Signals depend on relative ranking across the full universe —
this is a cross-sectional strategy, not per-ticker.

Default: `CROSS_TOPN = 3` (top and bottom 3 of 25 tickers).

The thesis is that SGX stocks exhibit short-term mean reversion — daily losers
tend to partially recover the next day, and daily winners tend to give back
gains. This is supported by SGX's relative inefficiency compared to larger
markets. The strategy is long-only: SELL signals indicate positions to exit,
not to short.

Key caveat: the paper's published Sharpe ratios (up to 4.675) assume both long
and short positions and are pre-transaction-cost. Daily rebalancing generates
frequent trades; SGX brokerage fees will reduce real returns.

### Relevant research

- Cen Yu (2023). *Systematic Multi-Factor Trading Strategy Based on SGX Market*.
  NTU Final Year Project.
  [hdl.handle.net/10356/167306](https://hdl.handle.net/10356/167306).
  **Primary source.** Tests daily return cross-sectional ranking on 25 STI
  stocks from 2012–2022. Best Sharpe ratio of 4.675 with hedging and volatility
  targeting.

---

## Adding a new strategy

See the project root `README.md` for full instructions. In brief:

1. Choose the right base class:
   - `BaseStrategy` for per-ticker signals (processes each stock alone)
   - `BaseCrossStrategy` for cross-sectional signals (ranks all stocks together)

2. Create `signals/my_strategy.py` implementing the chosen interface.

3. Add to `signals/__init__.py` and the `STRATEGIES` list in `main.py`.

4. Document it in this file. For scaffolding strategies, a short description
   of what it does is sufficient. For research-backed strategies, include the
   rationale and relevant citations.

5. Perform backtesting