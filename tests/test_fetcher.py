"""
tests/test_fetcher.py — Tests for the SQLite storage layer in data/fetcher.py.

We test _upsert and _load_from_db using an in-memory DB (no files on disk).
_fetch_ticker is excluded: it calls yfinance over the network, which makes
tests slow and flaky. Verify it manually with a real run instead.
"""

import pandas as pd
from tests.conftest import make_ohlcv
from data.fetcher import _upsert, _load_from_db


class TestUpsert:

    def test_rows_are_stored(self, mem_db):
        df = make_ohlcv([100.0, 101.0, 102.0])
        _upsert(mem_db, "AAA", df)
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 3

    def test_upsert_replaces_on_duplicate_datetime(self, mem_db):
        """Re-inserting the same datetime should update, not duplicate."""
        df1 = make_ohlcv([100.0])
        df2 = make_ohlcv([999.0])   # same index, different close
        _upsert(mem_db, "AAA", df1)
        _upsert(mem_db, "AAA", df2)
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 1
        cursor = mem_db.execute("SELECT close FROM prices WHERE ticker='AAA'")
        assert cursor.fetchone()[0] == 999.0

    def test_multiple_tickers_stored_independently(self, mem_db):
        _upsert(mem_db, "AAA", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "BBB", make_ohlcv([200.0, 201.0, 202.0]))
        c_aaa = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='AAA'").fetchone()[0]
        c_bbb = mem_db.execute("SELECT COUNT(*) FROM prices WHERE ticker='BBB'").fetchone()[0]
        assert c_aaa == 2
        assert c_bbb == 3

    def test_empty_dataframe_stores_nothing(self, mem_db):
        _upsert(mem_db, "AAA", pd.DataFrame())
        cursor = mem_db.execute("SELECT COUNT(*) FROM prices")
        assert cursor.fetchone()[0] == 0


class TestLoadFromDb:

    def test_returns_dataframe(self, mem_db):
        _upsert(mem_db, "AAA", make_ohlcv([100.0, 101.0]))
        df = _load_from_db(mem_db, "AAA")
        assert isinstance(df, pd.DataFrame)

    def test_returns_correct_row_count(self, mem_db):
        _upsert(mem_db, "AAA", make_ohlcv([10.0, 20.0, 30.0]))
        df = _load_from_db(mem_db, "AAA")
        assert len(df) == 3

    def test_returns_expected_columns(self, mem_db):
        _upsert(mem_db, "AAA", make_ohlcv([100.0]))
        df = _load_from_db(mem_db, "AAA")
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}

    def test_rows_ordered_oldest_first(self, mem_db):
        closes = [100.0, 200.0, 300.0]
        _upsert(mem_db, "AAA", make_ohlcv(closes))
        df = _load_from_db(mem_db, "AAA")
        assert list(df["close"]) == closes

    def test_only_returns_requested_ticker(self, mem_db):
        _upsert(mem_db, "AAA", make_ohlcv([100.0, 101.0]))
        _upsert(mem_db, "BBB", make_ohlcv([200.0]))
        df = _load_from_db(mem_db, "AAA")
        assert len(df) == 2

    def test_empty_result_for_unknown_ticker(self, mem_db):
        df = _load_from_db(mem_db, "UNKNOWN")
        assert df.empty
