"""
data/fetcher.py — Fetch OHLCV candles via yfinance and persist to SQLite.

Supports two intervals, stored in separate logical partitions of the same DB:
  - "30m"  : intraday candles (Yahoo max lookback: 60 days)
  - "1d"   : daily candles   (Yahoo max lookback: 2 years via period="2y")

Both share the same prices table, keyed by (ticker, interval, datetime).
"""

import sqlite3
import logging
from pathlib import Path

import yfinance as yf
import pandas as pd

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"

# Interval configurations
INTERVALS = {
    "30m": {"period": "60d"},
    "1d":  {"period": "2y"},
}


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker    TEXT,
            interval  TEXT,
            datetime  TEXT,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    INTEGER,
            PRIMARY KEY (ticker, interval, datetime)
        )
    """)
    conn.commit()
    return conn


def _fetch_ticker(ticker: str, interval: str) -> pd.DataFrame:
    """Download OHLCV candles for a single ticker at the given interval."""
    cfg = INTERVALS.get(interval)
    if cfg is None:
        raise ValueError(f"Unsupported interval '{interval}'. Choose from: {list(INTERVALS)}")
    try:
        df = yf.download(
            ticker,
            period=cfg["period"],
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            log.warning(f"No data returned for {ticker} ({interval})")
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index = pd.to_datetime(df.index, utc=True).strftime("%Y-%m-%d %H:%M:%S%z")
        df.index.name = "datetime"
        return df
    except Exception as e:
        log.error(f"Failed to fetch {ticker} ({interval}): {e}")
        return pd.DataFrame()


def _upsert(conn: sqlite3.Connection, ticker: str, interval: str, df: pd.DataFrame):
    """Insert or replace candles for a ticker+interval."""
    rows = [
        (ticker, interval, dt, row.open, row.high, row.low, row.close, int(row.volume))
        for dt, row in df.iterrows()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()


def _load_from_db(conn: sqlite3.Connection, ticker: str, interval: str) -> pd.DataFrame:
    """Read all stored candles for a ticker+interval, oldest first."""
    df = pd.read_sql_query(
        "SELECT datetime, open, high, low, close, volume FROM prices "
        "WHERE ticker=? AND interval=? ORDER BY datetime",
        conn, params=(ticker, interval),
    )
    df.set_index("datetime", inplace=True)
    return df


def fetch_all(tickers: list[str], interval: str = "30m") -> dict[str, pd.DataFrame]:
    """
    Fetch & store candles for all tickers at the given interval.
    Returns a dict of {ticker: dataframe}.

    interval : "30m" (default) for intraday strategies
               "1d"            for daily cross-sectional strategies
    """
    if interval not in INTERVALS:
        raise ValueError(f"Unsupported interval '{interval}'. Choose from: {list(INTERVALS)}")

    conn = _get_conn()

    result = {}
    for ticker in tickers:
        log.info(f"Fetching {ticker} ({interval})")
        df = _fetch_ticker(ticker, interval)
        if df.empty:
            continue
        _upsert(conn, ticker, interval, df)
        result[ticker] = _load_from_db(conn, ticker, interval)
        print(f"  ✓ {ticker:12s} {len(result[ticker])} candles  ({interval})")
    conn.close()
    return result