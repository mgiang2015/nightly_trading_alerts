"""
data/fetcher.py — Fetch 30m OHLCV candles via yfinance and persist to SQLite.

Yahoo Finance retains a maximum of 60 days of 30m intraday data.
"""

import sqlite3
import logging
from pathlib import Path

import yfinance as yf
import pandas as pd

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "prices.db"

# Yahoo Finance maximum lookback for 30m interval
INTERVAL = "30m"
PERIOD   = "60d"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker    TEXT,
            datetime  TEXT,
            open      REAL,
            high      REAL,
            low       REAL,
            close     REAL,
            volume    INTEGER,
            PRIMARY KEY (ticker, datetime)
        )
    """)
    conn.commit()
    return conn


def _fetch_ticker(ticker: str) -> pd.DataFrame:
    """Download 30m OHLCV candles for a single ticker."""
    try:
        df = yf.download(
            ticker, period=PERIOD, interval=INTERVAL,
            progress=False, auto_adjust=True,
        )
        if df.empty:
            log.warning(f"No data returned for {ticker}")
            return pd.DataFrame()
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        # Store timestamps as UTC ISO strings
        df.index = pd.to_datetime(df.index, utc=True).strftime("%Y-%m-%d %H:%M:%S%z")
        df.index.name = "datetime"
        return df
    except Exception as e:
        log.error(f"Failed to fetch {ticker}: {e}")
        return pd.DataFrame()


def _upsert(conn: sqlite3.Connection, ticker: str, df: pd.DataFrame):
    """Insert or replace candles for a ticker."""
    rows = [
        (ticker, dt, row.open, row.high, row.low, row.close, int(row.volume))
        for dt, row in df.iterrows()
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?)", rows
    )
    conn.commit()


def _load_from_db(conn: sqlite3.Connection, ticker: str) -> pd.DataFrame:
    """Read all stored candles for a ticker, oldest first."""
    df = pd.read_sql_query(
        "SELECT datetime, open, high, low, close, volume FROM prices "
        "WHERE ticker=? ORDER BY datetime",
        conn, params=(ticker,),
    )
    df.set_index("datetime", inplace=True)
    return df


def fetch_all(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    Fetch & store 30m candles for all tickers.
    Returns a dict of {ticker: dataframe}.
    """
    conn = _get_conn()
    result = {}
    for ticker in tickers:
        log.info(f"Fetching {ticker} ({INTERVAL})")
        df = _fetch_ticker(ticker)
        if df.empty:
            continue
        _upsert(conn, ticker, df)
        result[ticker] = _load_from_db(conn, ticker)
        print(f"  ✓ {ticker:10s} {len(result[ticker])} candles")
    conn.close()
    return result