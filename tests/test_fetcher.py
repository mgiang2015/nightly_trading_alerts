"""
tests/test_fetcher.py — Tests for the SQLite storage layer in data/fetcher.py.

We test _upsert, _load_from_db, and _migrate using an in-memory DB.
_fetch_ticker is excluded: it calls yfinance over the network.
"""

import sqlite3
import pandas as pd
from tests.conftest import make_ohlcv
from data.fetcher import _upsert, _load_from_db, _migrate


class TestUpsert:

    def test_rows_are_stored(self, mem_db):
        df = make_ohlcv([100.0, 101.0, 102.0])
        _upsert(mem_db, "AAA", "30m", df)
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 3

    def test_upsert_replaces_on_duplicate_datetime(self, mem_db):
        """Re-inserting the same ticker+interval+datetime should update, not duplicate."""
        df1 = make_ohlcv([100.0])
        df2 = make_ohlcv([999.0])
        _upsert(mem_db, "AAA", "30m", df1)
        _upsert(mem_db, "AAA", "30m", df2)
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 1
        cursor = mem_db.execute("SELECT close FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 999.0

    def test_multiple_tickers_stored_independently(self, mem_db):
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "BBB", "30m", make_ohlcv([200.0, 201.0, 202.0]))
        c_aaa = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'").fetchone()[0]
        c_bbb = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='BBB'").fetchone()[0]
        assert c_aaa == 2
        assert c_bbb == 3

    def test_intervals_stored_independently(self, mem_db):
        """Same ticker stored at 30m and 1d should not collide."""
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "AAA", "1d",  make_ohlcv([200.0, 201.0, 202.0]))
        c_30m = mem_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker='AAA' AND interval='30m'"
        ).fetchone()[0]
        c_1d  = mem_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker='AAA' AND interval='1d'"
        ).fetchone()[0]
        assert c_30m == 2
        assert c_1d  == 3

    def test_empty_dataframe_stores_nothing(self, mem_db):
        _upsert(mem_db, "AAA", "30m", pd.DataFrame())
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices")
        assert cursor.fetchone()[0] == 0


class TestLoadFromDb:

    def test_returns_dataframe(self, mem_db):
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0, 101.0]))
        df = _load_from_db(mem_db, "AAA", "30m")
        assert isinstance(df, pd.DataFrame)

    def test_returns_correct_row_count(self, mem_db):
        _upsert(mem_db, "AAA", "1d", make_ohlcv([10.0, 20.0, 30.0]))
        df = _load_from_db(mem_db, "AAA", "1d")
        assert len(df) == 3

    def test_returns_expected_columns(self, mem_db):
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0]))
        df = _load_from_db(mem_db, "AAA", "30m")
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}

    def test_rows_ordered_oldest_first(self, mem_db):
        closes = [100.0, 200.0, 300.0]
        _upsert(mem_db, "AAA", "1d", make_ohlcv(closes))
        df = _load_from_db(mem_db, "AAA", "1d")
        assert list(df["close"]) == closes

    def test_only_returns_requested_ticker(self, mem_db):
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "BBB", "30m", make_ohlcv([200.0]))
        df = _load_from_db(mem_db, "AAA", "30m")
        assert len(df) == 2

    def test_only_returns_requested_interval(self, mem_db):
        """Loading 1d data should not return 30m rows for the same ticker."""
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "AAA", "1d",  make_ohlcv([200.0]))
        df = _load_from_db(mem_db, "AAA", "1d")
        assert len(df) == 1
        assert df["close"].iloc[0] == 200.0

    def test_empty_result_for_unknown_ticker(self, mem_db):
        df = _load_from_db(mem_db, "UNKNOWN", "30m")
        assert df.empty


class TestMigrate:

    def test_migrate_adds_interval_column(self):
        """A pre-migration DB (no interval column) should be migrated cleanly."""
        conn = sqlite3.connect(":memory:")
        # Create old schema without interval column
        conn.execute("""
            CREATE TABLE prices (
                ticker   TEXT,
                datetime TEXT,
                open     REAL,
                high     REAL,
                low      REAL,
                close    REAL,
                volume   INTEGER,
                PRIMARY KEY (ticker, datetime)
            )
        """)
        conn.execute(
            "INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
            ("AAA", "2024-01-01 09:00:00+0800", 1.0, 1.0, 1.0, 1.0, 1000)
        )
        conn.commit()

        _migrate(conn)

        cols = [row[1] for row in conn.execute("PRAGMA table_info(prices)")]
        assert "interval" in cols

        # Existing row should be preserved
        row = conn.execute("SELECT ticker, close FROM prices").fetchone()
        assert row[0] == "AAA"
        assert row[1] == 1.0
        conn.close()

    def test_migrate_is_idempotent(self, mem_db):
        """Calling _migrate on an already-migrated DB should not raise or corrupt data."""
        _upsert(mem_db, "AAA", "30m", make_ohlcv([100.0]))
        _migrate(mem_db)   # should be a no-op
        df = _load_from_db(mem_db, "AAA", "30m")
        assert len(df) == 1