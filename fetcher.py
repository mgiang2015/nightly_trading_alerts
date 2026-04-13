"""
data/fetcher.py — Fetch EOD OHLCV data via yfinance and persist to SQLite.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf
import pandas as pd
from config import LOOKBACK_DAYS

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker  TEXT,
            date    TEXT,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.commit()
    return conn


def _fetch_ticker(ticker: str, days: int) -> pd.DataFrame:
    """Download OHLCV for a single ticker. Returns empty df on failure."""
    start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = yf.download(ticker, start=start, progress=False, auto_adjust=True)
        if df.empty:
            log.warning(f"No data returned for {ticker}")
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index = pd.to_datetime(df.index).strftime("%Y-%m-%d")
        df.index.name = "date"
        return df
    except Exception as e:
        log.error(f"Failed to fetch {ticker}: {e}")
        return pd.DataFrame()


def _upsert(conn: sqlite3.Connection, ticker: str, df: pd.DataFrame):
    """Insert or replace rows for a ticker."""
    rows = [
        (ticker, date, row.open, row.high, row.low, row.close, int(row.volume))
        for date, row in df.iterrows()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows
    )
    conn.commit()


def _load_from_db(conn: sqlite3.Connection, ticker: str, days: int) -> pd.DataFrame:
    """Read the last N days of a ticker from SQLite."""
    since = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM prices "
        "WHERE ticker=? AND date>=? ORDER BY date",
        conn, params=(ticker, since),
    )
    df.set_index("date", inplace=True)
    return df


def fetch_all(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    Fetch & store data for all tickers.
    Returns a dict of {ticker: dataframe}.
    """
    conn = _get_conn()
    result = {}
    for ticker in tickers:
        log.info(f"Fetching {ticker}")
        df = _fetch_ticker(ticker, LOOKBACK_DAYS)
        if df.empty:
            continue
        _upsert(conn, ticker, df)
        result[ticker] = _load_from_db(conn, ticker, LOOKBACK_DAYS)
        print(f"  ✓ {ticker:10s} {len(result[ticker])} rows")
    conn.close()
    return result
