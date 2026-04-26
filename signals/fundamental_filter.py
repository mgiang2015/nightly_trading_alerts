"""
signals/fundamental_filter.py — Weekly fundamental quality filter.

Fetches Price-to-Book, dividend yield, and Debt-to-Equity from yfinance
for each ticker and caches results in SQLite for FUND_CACHE_DAYS days.

Role in the pipeline
--------------------
This is NOT a strategy — it generates no BUY/SELL/HOLD signals.
It annotates existing signal dicts with two keys:
    fund_caution : bool   — True if the stock fails one or more thresholds
    fund_reasons : list   — human-readable list of failed checks

The Telegram formatter renders a ⚠️ caution marker on flagged signals.
Signals are never suppressed — the flag is informational, leaving the
final call to the trader.

Sector-aware thresholds
-----------------------
Different threshold sets are applied per sector (defined in tickers.py):
    bank       — P/B only (D/E is meaningless for banks)
    reit       — D/E and dividend yield (MAS gearing limits apply)
    industrial — Standard P/B and D/E
Any ticker not in SECTOR_MAP defaults to "industrial".

Supported metrics (all sourced from yfinance Ticker.info, no paid API needed)
    Price-to-Book (P/B)    — max_pb threshold
    Dividend yield         — min_div_yield threshold
    Debt-to-Equity (D/E)   — max_de threshold
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

from config import FUND_THRESHOLDS, FUND_CACHE_DAYS
from tickers import SECTOR_MAP

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"


# ── Cache layer ───────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker        TEXT PRIMARY KEY,
            pb_ratio      REAL,
            div_yield     REAL,
            de_ratio      REAL,
            fetched_at    TEXT
        )
    """)
    conn.commit()
    return conn


def _is_stale(fetched_at: str | None) -> bool:
    """Return True if cached data is older than FUND_CACHE_DAYS."""
    if fetched_at is None:
        return True
    try:
        age = datetime.utcnow() - datetime.fromisoformat(fetched_at)
        return age > timedelta(days=FUND_CACHE_DAYS)
    except ValueError:
        return True


def _load_cache(conn: sqlite3.Connection, ticker: str) -> dict | None:
    row = conn.execute(
        "SELECT pb_ratio, div_yield, de_ratio, fetched_at FROM fundamentals WHERE ticker=?",
        (ticker,),
    ).fetchone()
    if row is None:
        return None
    return {
        "pb_ratio":   row[0],
        "div_yield":  row[1],
        "de_ratio":   row[2],
        "fetched_at": row[3],
    }


def _save_cache(conn: sqlite3.Connection, ticker: str, data: dict):
    conn.execute(
        "INSERT OR REPLACE INTO fundamentals VALUES (?,?,?,?,?)",
        (
            ticker,
            data.get("pb_ratio"),
            data.get("div_yield"),
            data.get("de_ratio"),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()


# ── Fetch from yfinance ───────────────────────────────────────────────────────

def _fetch_fundamentals(ticker: str) -> dict:
    """
    Fetch P/B, dividend yield, and D/E from yfinance.
    Returns a dict with None for any unavailable metric.
    """
    try:
        info  = yf.Ticker(ticker).info
        pb    = info.get("priceToBook")
        div   = info.get("dividendYield")
        de    = info.get("debtToEquity")
        # yfinance returns dividendYield as a fraction (e.g. 0.04 = 4%)
        div_pct = round(div * 100, 2) if div is not None else None
        # D/E is sometimes expressed as a percentage (e.g. 45.3 = 0.453)
        if de is not None and de > 10:
            de = de / 100
        return {
            "pb_ratio":  round(pb, 2) if pb is not None else None,
            "div_yield": div_pct,
            "de_ratio":  round(de, 2) if de is not None else None,
        }
    except Exception as e:
        log.warning(f"Failed to fetch fundamentals for {ticker}: {e}")
        return {"pb_ratio": None, "div_yield": None, "de_ratio": None}


# ── Sector-aware threshold checks ─────────────────────────────────────────────

def _get_sector(ticker: str) -> str:
    """Return the sector for a ticker, defaulting to 'industrial'."""
    return SECTOR_MAP.get(ticker, "industrial")


def _check_thresholds(ticker: str, data: dict) -> list[str]:
    """
    Apply sector-appropriate thresholds to the fundamental data.
    Returns a list of human-readable caution reasons (empty = clean).
    """
    sector     = _get_sector(ticker)
    thresholds = FUND_THRESHOLDS.get(sector, FUND_THRESHOLDS["industrial"])

    reasons = []
    pb  = data.get("pb_ratio")
    div = data.get("div_yield")
    de  = data.get("de_ratio")

    max_pb        = thresholds.get("max_pb")
    min_div_yield = thresholds.get("min_div_yield")
    max_de        = thresholds.get("max_de")

    if max_pb is not None and pb is not None and pb > max_pb:
        reasons.append(f"P/B {pb:.1f}x > {max_pb}x ({sector})")

    if min_div_yield is not None and div is not None and div < min_div_yield:
        reasons.append(f"Div yield {div:.1f}% < {min_div_yield}% ({sector})")

    if max_de is not None and de is not None and de > max_de:
        reasons.append(f"D/E {de:.2f} > {max_de} ({sector})")

    return reasons


# ── Public API ────────────────────────────────────────────────────────────────

def annotate_signals(signals: list[dict]) -> list[dict]:
    """
    Annotate each signal dict with fundamental caution data.

    Adds keys to each BUY/SELL signal:
        fund_caution : bool       — True if any threshold is breached
        fund_reasons : list[str]  — reasons for caution (empty if clean)
        fund_sector  : str        — sector classification applied
        fund_pb      : float|None — Price-to-Book ratio
        fund_div     : float|None — Dividend yield (%)
        fund_de      : float|None — Debt-to-Equity ratio

    HOLD and ERROR signals are passed through unchanged.
    Uses cached data where available; fetches from yfinance if stale.
    """
    conn = _get_conn()
    annotated = []

    for signal in signals:
        if signal.get("signal") not in ("BUY", "SELL"):
            annotated.append(signal)
            continue

        ticker = signal["ticker"]
        cached = _load_cache(conn, ticker)

        if cached is None or _is_stale(cached.get("fetched_at")):
            log.info(f"Fetching fundamentals for {ticker}")
            data = _fetch_fundamentals(ticker)
            _save_cache(conn, ticker, data)
        else:
            data = cached

        reasons = _check_thresholds(ticker, data)
        annotated.append({
            **signal,
            "fund_caution": len(reasons) > 0,
            "fund_reasons": reasons,
            "fund_sector":  _get_sector(ticker),
            "fund_pb":      data.get("pb_ratio"),
            "fund_div":     data.get("div_yield"),
            "fund_de":      data.get("de_ratio"),
        })

    conn.close()
    return annotated