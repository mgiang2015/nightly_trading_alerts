"""
conftest.py — Shared fixtures for all tests.
"""

import sqlite3

import numpy as np
import pandas as pd
import pytest


def make_ohlcv(closes: list[float]) -> pd.DataFrame:
    """
    Build a minimal OHLCV DataFrame from a list of close prices.
    Open/high/low are derived simply; volume is constant.
    Indexed by datetime strings to match the real fetcher output.
    """
    n = len(closes)
    closes = np.array(closes, dtype=float)
    df = pd.DataFrame({
        "open":   closes * 0.999,
        "high":   closes * 1.002,
        "low":    closes * 0.998,
        "close":  closes,
        "volume": [100_000] * n,
    })
    df.index = [f"2024-01-{i+1:02d} 09:00:00+0800" for i in range(n)]
    df.index.name = "datetime"
    return df


@pytest.fixture
def mem_db():
    """In-memory SQLite connection with the prices table already created."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE prices (
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
    yield conn
    conn.close()