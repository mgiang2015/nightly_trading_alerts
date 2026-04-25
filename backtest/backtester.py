"""
backtest/backtester.py — Simple generic daily backtester.

Design principles:
  - Daily granularity only (matches the cross-sectional strategies from the paper)
  - Long-only, equal position sizing
  - Signals generated fresh each bar using a rolling window to avoid look-ahead
  - Works with any BaseStrategy or BaseCrossStrategy via compute_signals()
  - No external dependencies beyond pandas and numpy

Mechanics:
  - Each day, run the strategy on all data up to (but not including) that day
  - Enter on the OPEN of the next bar after a BUY signal
  - Exit on the OPEN of the next bar after a SELL or when signal flips to HOLD
  - Capital is split equally among all open positions
  - Uninvested capital earns 0% (cash drag is visible in results)

Metrics reported (same as the paper):
  - Total return
  - CAGR
  - Sharpe ratio  (annualised, risk-free rate = 0)
  - Max drawdown
"""

import numpy as np
import pandas as pd

from signals.base import BaseStrategy
from signals.base_cross import BaseCrossStrategy
from signals.engine import compute_signals

# ── Metrics ───────────────────────────────────────────────────────────────────

def _cagr(equity: pd.Series) -> float:
    """Compound Annual Growth Rate from a daily equity curve."""
    n_years = len(equity) / 252
    if n_years <= 0 or equity.iloc[0] <= 0:
        return 0.0
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / n_years) - 1


def _sharpe(equity: pd.Series) -> float:
    """Annualised Sharpe ratio (risk-free rate = 0)."""
    daily_returns = equity.pct_change().dropna()
    if daily_returns.std() == 0:
        return 0.0
    return (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)


def _max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    peak = equity.cummax()
    drawdown = (equity - peak) / peak
    return float(drawdown.min())   # negative value; caller negates for display


# ── Core backtester ───────────────────────────────────────────────────────────

def run_backtest(
    data: dict[str, pd.DataFrame],
    strategy: BaseStrategy | BaseCrossStrategy,
    initial_capital: float = 10_000.0,
    warmup_bars: int = 60,
) -> dict:
    """
    Run a daily backtest of the given strategy over the provided data.

    Parameters
    ----------
    data            : dict of {ticker: OHLCV DataFrame} — daily granularity
    strategy        : any BaseStrategy or BaseCrossStrategy instance
    initial_capital : starting portfolio value in SGD (default: 10,000)
    warmup_bars     : number of bars to skip at the start so indicators
                      have enough history before the first trade (default: 60)

    Returns
    -------
    dict with keys:
        equity_curve  : pd.Series of daily portfolio value
        trades        : pd.DataFrame of individual trades
        metrics       : dict of summary statistics
    """
    # Align all tickers to a common daily index (union of all dates)
    all_dates = sorted(
        set(d for df in data.values() for d in df.index)
    )
    if len(all_dates) < warmup_bars + 2:
        raise ValueError(
            f"Not enough data: {len(all_dates)} bars, need at least {warmup_bars + 2}"
        )

    capital   = initial_capital
    positions = {}   # {ticker: {"shares": float, "entry_price": float, "entry_date": date}}
    equity    = []
    trades    = []

    for i, date in enumerate(all_dates):
        if i < warmup_bars:
            equity.append(capital)
            continue

        # ── Slice data up to (not including) current bar to avoid look-ahead ──
        window = {
            ticker: df[df.index < date]
            for ticker, df in data.items()
            if (df.index < date).any()
        }
        if not window:
            equity.append(capital)
            continue

        # ── Generate signals ──────────────────────────────────────────────────
        results, _ = compute_signals(window, strategy=strategy)
        signal_map = {r["ticker"]: r["signal"] for r in results}

        # ── Execute exits first (free up capital before entries) ──────────────
        for ticker in list(positions.keys()):
            sig = signal_map.get(ticker, "HOLD")
            if sig in ("SELL", "HOLD"):
                # Exit at today's open
                today_df = data[ticker]
                today_rows = today_df[today_df.index == date]
                if today_rows.empty:
                    continue
                exit_price = float(today_rows["open"].iloc[0])
                pos        = positions.pop(ticker)
                pnl        = (exit_price - pos["entry_price"]) * pos["shares"]
                proceeds   = exit_price * pos["shares"]
                capital   += proceeds
                trades.append({
                    "ticker":      ticker,
                    "entry_date":  pos["entry_date"],
                    "exit_date":   date,
                    "entry_price": round(pos["entry_price"], 4),
                    "exit_price":  round(exit_price, 4),
                    "shares":      round(pos["shares"], 4),
                    "pnl":         round(pnl, 4),
                    "return_pct":  round((exit_price / pos["entry_price"] - 1) * 100, 3),
                })

        # ── Execute entries ───────────────────────────────────────────────────
        buy_tickers = [
            t for t, s in signal_map.items()
            if s == "BUY" and t not in positions
        ]
        if buy_tickers:
            n_slots       = len(buy_tickers)
            capital_each  = capital / (n_slots + len(positions)) if n_slots else 0

            for ticker in buy_tickers:
                today_df   = data[ticker]
                today_rows = today_df[today_df.index == date]
                if today_rows.empty:
                    continue
                entry_price = float(today_rows["open"].iloc[0])
                if entry_price <= 0:
                    continue
                shares = capital_each / entry_price
                capital -= shares * entry_price
                positions[ticker] = {
                    "shares":      shares,
                    "entry_price": entry_price,
                    "entry_date":  date,
                }

        # ── Mark-to-market portfolio value ────────────────────────────────────
        holdings_value = 0.0
        for ticker, pos in positions.items():
            today_df   = data[ticker]
            today_rows = today_df[today_df.index == date]
            if today_rows.empty:
                # Use last known close if ticker has no data today
                prior = today_df[today_df.index < date]
                price = float(prior["close"].iloc[-1]) if not prior.empty else pos["entry_price"]
            else:
                price = float(today_rows["close"].iloc[0])
            holdings_value += price * pos["shares"]

        equity.append(capital + holdings_value)

    # ── Close any open positions at last available close ──────────────────────
    last_date = all_dates[-1]
    for ticker, pos in positions.items():
        today_df   = data[ticker]
        last_rows  = today_df[today_df.index <= last_date]
        exit_price = float(last_rows["close"].iloc[-1]) if not last_rows.empty else pos["entry_price"]
        pnl        = (exit_price - pos["entry_price"]) * pos["shares"]
        trades.append({
            "ticker":      ticker,
            "entry_date":  pos["entry_date"],
            "exit_date":   last_date,
            "entry_price": round(pos["entry_price"], 4),
            "exit_price":  round(exit_price, 4),
            "shares":      round(pos["shares"], 4),
            "pnl":         round(pnl, 4),
            "return_pct":  round((exit_price / pos["entry_price"] - 1) * 100, 3),
        })

    equity_series = pd.Series(equity, index=all_dates, name="equity")

    total_return = (equity_series.iloc[-1] / initial_capital) - 1
    cagr         = _cagr(equity_series)
    sharpe       = _sharpe(equity_series)
    mdd          = _max_drawdown(equity_series)
    n_trades     = len(trades)
    trades_df    = pd.DataFrame(trades) if trades else pd.DataFrame()

    win_rate = 0.0
    if not trades_df.empty and "pnl" in trades_df.columns:
        win_rate = (trades_df["pnl"] > 0).mean()

    metrics = {
        "initial_capital":  initial_capital,
        "final_value":      round(equity_series.iloc[-1], 2),
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct":         round(cagr * 100, 2),
        "sharpe":           round(sharpe, 3),
        "max_drawdown_pct": round(mdd * 100, 2),   # negative
        "n_trades":         n_trades,
        "win_rate_pct":     round(win_rate * 100, 1),
    }

    return {
        "equity_curve": equity_series,
        "trades":       trades_df,
        "metrics":      metrics,
    }


def print_summary(result: dict, strategy_name: str = ""):
    """Print a formatted backtest summary to stdout."""
    m = result["metrics"]
    t = result["trades"]
    header = f"Backtest — {strategy_name}" if strategy_name else "Backtest results"
    print(f"\n{'─' * 52}")
    print(f"  {header}")
    print(f"{'─' * 52}")
    print(f"  Initial capital : SGD {m['initial_capital']:>12,.2f}")
    print(f"  Final value     : SGD {m['final_value']:>12,.2f}")
    print(f"  Total return    :     {m['total_return_pct']:>+10.2f}%")
    print(f"  CAGR            :     {m['cagr_pct']:>+10.2f}%")
    print(f"  Sharpe ratio    :     {m['sharpe']:>10.3f}")
    print(f"  Max drawdown    :     {m['max_drawdown_pct']:>10.2f}%")
    print(f"  Trades          :     {m['n_trades']:>10}")
    if m["n_trades"] > 0:
        print(f"  Win rate        :     {m['win_rate_pct']:>9.1f}%")
    if not t.empty:
        avg_ret = t["return_pct"].mean()
        print(f"  Avg trade ret   :     {avg_ret:>+9.2f}%")
    print(f"{'─' * 52}\n")