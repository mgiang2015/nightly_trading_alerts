"""
backtest/backtester.py — Simple generic daily backtester.

Design principles:
  - Daily granularity only (matches the cross-sectional strategies from the paper)
  - Long-only, equal position sizing
  - Signals generated fresh each bar using a rolling window to avoid look-ahead
  - Works with any BaseStrategy or BaseCrossStrategy via compute_signals()
  - Pluggable commission function — defaults to FSMOne SGX fee structure (used by repo owner)
  - Minimum position size guard prevents fee-eroding micro-trades

Mechanics:
  - Each day, run the strategy on all data up to (but not including) that day
  - Enter on the OPEN of the next bar after a BUY signal
  - Exit on the OPEN of the next bar after a SELL or when signal flips to HOLD
  - Commission deducted on both entry and exit
  - Trades smaller than min_position_size are skipped entirely
  - Capital is split equally among all open positions
  - Uninvested capital earns 0% (cash drag is visible in results)

Capital safety
  - capital_each = available_cash / (new_buys + open_positions)
  - Trades where capital_each < min_position_size are skipped
  - This means the portfolio naturally caps at a finite number of positions
  - You can never go into negative capital

Metrics reported:
  - Total return, CAGR, Sharpe, max drawdown (same as the paper)
  - Total and average commission paid
  - Capital utilisation (avg % of capital deployed)
  - Skipped trades (due to insufficient capital or min position size)
"""

import numpy as np
import pandas as pd
from signals.engine import compute_signals
from signals.base import BaseStrategy
from signals.base_cross import BaseCrossStrategy


# ── Commission functions ──────────────────────────────────────────────────────

def commission_fsmone(trade_value: float) -> float:
    """
    FSMOne SGX equity commission:
        0.08% of trade value, minimum SGD 8.80 per trade side.
    Applied separately on entry and exit.
    Break-even position size: SGD 11,000 (below this, minimum applies).
    """
    return max(8.80, trade_value * 0.0008)


def commission_zero(trade_value: float) -> float:
    """No commission — compare with commission_fsmone to see fee drag."""
    return 0.0


# ── Metrics ───────────────────────────────────────────────────────────────────

def _cagr(equity: pd.Series) -> float:
    n_years = len(equity) / 252
    if n_years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1


def _sharpe(equity: pd.Series) -> float:
    daily_returns = equity.pct_change().dropna()
    if daily_returns.std() == 0:
        return 0.0
    return (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return float(drawdown.min())


# ── Core backtester ───────────────────────────────────────────────────────────

def run_backtest(
    data: dict[str, pd.DataFrame],
    strategy: BaseStrategy | BaseCrossStrategy,
    initial_capital: float = 10_000.0,
    warmup_bars: int = 60,
    commission_fn=commission_fsmone,
    min_position_size: float = 5_000.0,
    rebalance_every: int = 1,
) -> dict:
    """
    Run a daily backtest of the given strategy over the provided data.

    Parameters
    ----------
    data               : dict of {ticker: OHLCV DataFrame} — daily granularity
    strategy           : any BaseStrategy or BaseCrossStrategy instance
    initial_capital    : starting portfolio value in SGD (default: 10,000)
    warmup_bars        : bars to skip so indicators have enough history (default: 60)
    commission_fn      : callable(trade_value) -> SGD fee per trade side.
                         Defaults to commission_fsmone (0.08%, min SGD 8.80).
                         Pass commission_zero to run without fees.
    min_position_size  : minimum SGD value per trade (default: 5,000).
                         Trades smaller than this are skipped entirely.
                         At SGD 5,000, FSMOne fee = SGD 8.80 = 0.176% per side.
                         Raise this to SGD 11,000 for true break-even on fees.
    rebalance_every    : how many trading days between signal evaluations.
                         1 = daily rebalancing (default)
                         5 = weekly rebalancing (evaluate every 5 trading days)
                         On non-rebalance days, existing positions are held and
                         marked-to-market but no new entries or exits are made.

    Returns
    -------
    dict with keys:
        equity_curve      : pd.Series of daily portfolio value (net of fees)
        trades            : pd.DataFrame of individual trades with fees
        metrics           : dict of summary statistics
    """
    all_dates = sorted(
        set(d for df in data.values() for d in df.index)
    )
    if len(all_dates) < warmup_bars + 2:
        raise ValueError(
            f"Not enough data: {len(all_dates)} bars, need at least {warmup_bars + 2}"
        )

    capital          = initial_capital
    positions        = {}
    equity           = []
    trades           = []
    total_commission = 0.0
    skipped_trades   = 0
    capital_deployed = []
    rebalance_count  = 0   # tracks how many rebalance days have elapsed

    for i, date in enumerate(all_dates):
        if i < warmup_bars:
            equity.append(capital)
            capital_deployed.append(0.0)
            continue

        window = {
            ticker: df[df.index < date]
            for ticker, df in data.items()
            if (df.index < date).any()
        }
        if not window:
            equity.append(capital)
            capital_deployed.append(0.0)
            continue

        is_rebalance_day = (rebalance_count % rebalance_every == 0)
        rebalance_count += 1

        if not is_rebalance_day:
            # Hold existing positions, mark-to-market only — no entries/exits
            holdings_value = 0.0
            for ticker, pos in positions.items():
                today_rows = data[ticker][data[ticker].index == date]
                if today_rows.empty:
                    prior = data[ticker][data[ticker].index < date]
                    price = float(prior["close"].iloc[-1]) if not prior.empty else pos["entry_price"]
                else:
                    price = float(today_rows["close"].iloc[0])
                holdings_value += price * pos["shares"]
            total_equity = capital + holdings_value
            equity.append(total_equity)
            capital_deployed.append(
                (holdings_value / total_equity * 100) if total_equity > 0 else 0.0
            )
            continue

        results, _ = compute_signals(window, strategy=strategy)
        signal_map = {r["ticker"]: r["signal"] for r in results}

        # ── Exits ─────────────────────────────────────────────────────────────
        for ticker in list(positions.keys()):
            sig = signal_map.get(ticker, "HOLD")
            if sig in ("SELL", "HOLD"):
                today_rows = data[ticker][data[ticker].index == date]
                if today_rows.empty:
                    continue
                exit_price  = float(today_rows["open"].iloc[0])
                pos         = positions.pop(ticker)
                proceeds    = exit_price * pos["shares"]
                exit_comm   = commission_fn(proceeds)
                pnl_gross   = (exit_price - pos["entry_price"]) * pos["shares"]
                pnl_net     = pnl_gross - pos["entry_comm"] - exit_comm
                capital    += proceeds - exit_comm
                total_commission += exit_comm
                trades.append({
                    "ticker":       ticker,
                    "entry_date":   pos["entry_date"],
                    "exit_date":    date,
                    "entry_price":  round(pos["entry_price"], 4),
                    "exit_price":   round(exit_price, 4),
                    "shares":       round(pos["shares"], 4),
                    "commission":   round(pos["entry_comm"] + exit_comm, 4),
                    "pnl_gross":    round(pnl_gross, 4),
                    "pnl_net":      round(pnl_net, 4),
                    "return_pct":   round((exit_price / pos["entry_price"] - 1) * 100, 3),
                })

        # ── Entries ───────────────────────────────────────────────────────────
        buy_tickers = [
            t for t, s in signal_map.items()
            if s == "BUY" and t not in positions
        ]

        if buy_tickers:
            n_slots      = len(buy_tickers)
            capital_each = capital / (n_slots + len(positions)) if n_slots else 0

            if capital_each < min_position_size:
                # Not enough capital per slot — skip all new entries this bar
                skipped_trades += n_slots
            else:
                for ticker in buy_tickers:
                    today_rows = data[ticker][data[ticker].index == date]
                    if today_rows.empty:
                        skipped_trades += 1
                        continue
                    entry_price = float(today_rows["open"].iloc[0])
                    if entry_price <= 0:
                        skipped_trades += 1
                        continue
                    shares      = capital_each / entry_price
                    trade_value = shares * entry_price
                    entry_comm  = commission_fn(trade_value)
                    capital    -= trade_value + entry_comm
                    total_commission += entry_comm
                    positions[ticker] = {
                        "shares":      shares,
                        "entry_price": entry_price,
                        "entry_date":  date,
                        "entry_comm":  entry_comm,
                    }

        # ── Mark-to-market ────────────────────────────────────────────────────
        holdings_value = 0.0
        for ticker, pos in positions.items():
            today_rows = data[ticker][data[ticker].index == date]
            if today_rows.empty:
                prior = data[ticker][data[ticker].index < date]
                price = float(prior["close"].iloc[-1]) if not prior.empty else pos["entry_price"]
            else:
                price = float(today_rows["close"].iloc[0])
            holdings_value += price * pos["shares"]

        total_equity = capital + holdings_value
        equity.append(total_equity)
        capital_deployed.append(
            (holdings_value / total_equity * 100) if total_equity > 0 else 0.0
        )

    # ── Close open positions at end ───────────────────────────────────────────
    last_date = all_dates[-1]
    for ticker, pos in positions.items():
        last_rows  = data[ticker][data[ticker].index <= last_date]
        exit_price = float(last_rows["close"].iloc[-1]) if not last_rows.empty else pos["entry_price"]
        proceeds   = exit_price * pos["shares"]
        exit_comm  = commission_fn(proceeds)
        pnl_gross  = (exit_price - pos["entry_price"]) * pos["shares"]
        pnl_net    = pnl_gross - pos["entry_comm"] - exit_comm
        total_commission += exit_comm
        trades.append({
            "ticker":       ticker,
            "entry_date":   pos["entry_date"],
            "exit_date":    last_date,
            "entry_price":  round(pos["entry_price"], 4),
            "exit_price":   round(exit_price, 4),
            "shares":       round(pos["shares"], 4),
            "commission":   round(pos["entry_comm"] + exit_comm, 4),
            "pnl_gross":    round(pnl_gross, 4),
            "pnl_net":      round(pnl_net, 4),
            "return_pct":   round((exit_price / pos["entry_price"] - 1) * 100, 3),
        })

    equity_series    = pd.Series(equity, index=all_dates, name="equity")
    trades_df        = pd.DataFrame(trades) if trades else pd.DataFrame()
    deployed_series  = pd.Series(capital_deployed, index=all_dates)

    total_return = (equity_series.iloc[-1] / initial_capital) - 1
    cagr         = _cagr(equity_series)
    sharpe       = _sharpe(equity_series)
    mdd          = _max_drawdown(equity_series)
    n_trades     = len(trades)

    win_rate = 0.0
    avg_comm = 0.0
    if not trades_df.empty and "pnl_net" in trades_df.columns:
        win_rate = (trades_df["pnl_net"] > 0).mean()
        avg_comm = trades_df["commission"].mean()

    # Max concurrent positions seen at any point
    max_concurrent = 0
    open_count = 0
    for t in trades_df.itertuples() if not trades_df.empty else []:
        open_count += 1
        max_concurrent = max(max_concurrent, open_count)
        open_count = max(0, open_count - 1)

    metrics = {
        "initial_capital":      initial_capital,
        "final_value":          round(equity_series.iloc[-1], 2),
        "total_return_pct":     round(total_return * 100, 2),
        "cagr_pct":             round(cagr * 100, 2),
        "sharpe":               round(sharpe, 3),
        "max_drawdown_pct":     round(mdd * 100, 2),
        "n_trades":             n_trades,
        "skipped_trades":       skipped_trades,
        "win_rate_pct":         round(win_rate * 100, 1),
        "total_commission":     round(total_commission, 2),
        "avg_commission":       round(avg_comm, 2),
        "avg_capital_deployed": round(deployed_series.mean(), 1),
        "max_capital_deployed": round(deployed_series.max(), 1),
        "min_position_size":    min_position_size,
        "rebalance_every":      rebalance_every,
    }

    return {
        "equity_curve":     equity_series,
        "trades":           trades_df,
        "capital_deployed": deployed_series,
        "metrics":          metrics,
    }


def print_summary(result: dict, strategy_name: str = ""):
    """Print a formatted backtest summary to stdout."""
    m = result["metrics"]
    t = result["trades"]
    header = f"Backtest — {strategy_name}" if strategy_name else "Backtest results"
    print(f"\n{'─' * 56}")
    print(f"  {header}")
    print(f"{'─' * 56}")
    print(f"  Initial capital   : SGD {m['initial_capital']:>12,.2f}")
    print(f"  Final value       : SGD {m['final_value']:>12,.2f}")
    print(f"  Total return      :     {m['total_return_pct']:>+10.2f}%")
    print(f"  CAGR              :     {m['cagr_pct']:>+10.2f}%")
    print(f"  Sharpe ratio      :     {m['sharpe']:>10.3f}")
    print(f"  Max drawdown      :     {m['max_drawdown_pct']:>10.2f}%")
    print(f"{'─' * 56}")
    freq = "Daily" if m["rebalance_every"] == 1 else f"Every {m['rebalance_every']} days"
    print(f"  Rebalance         :     {freq:>16}")
    print(f"  Trades executed   :     {m['n_trades']:>10}")
    print(f"  Trades skipped    :     {m['skipped_trades']:>10}  (below min position size)")
    if m["n_trades"] > 0:
        print(f"  Win rate          :     {m['win_rate_pct']:>9.1f}%")
    if not t.empty and "return_pct" in t.columns:
        avg_ret = t["return_pct"].mean()
        print(f"  Avg trade return  :     {avg_ret:>+9.2f}%")
    print(f"{'─' * 56}")
    print(f"  Total commission  : SGD {m['total_commission']:>12,.2f}")
    print(f"  Avg comm / trade  : SGD {m['avg_commission']:>12,.2f}")
    print(f"  Min position size : SGD {m['min_position_size']:>12,.2f}")
    print(f"{'─' * 56}")
    print(f"  Avg capital used  :     {m['avg_capital_deployed']:>9.1f}%")
    print(f"  Max capital used  :     {m['max_capital_deployed']:>9.1f}%")
    print(f"{'─' * 56}\n")