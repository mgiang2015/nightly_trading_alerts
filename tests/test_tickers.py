"""
tests/test_tickers.py — Tests for WATCHLIST env var loading.

We reload the tickers module inside each test so env var changes take effect.
"""

import importlib
import os
import pytest


def _load(env_value):
    """Set WATCHLIST env var and reload the tickers module."""
    if env_value is None:
        os.environ.pop("WATCHLIST", None)
    else:
        os.environ["WATCHLIST"] = env_value
    import tickers
    importlib.reload(tickers)
    return tickers


class TestWatchlist:

    def test_single_ticker(self):
        mod = _load("ES3.SI")
        assert mod.WATCHLIST == ["ES3.SI"]

    def test_multiple_tickers(self):
        mod = _load("ES3.SI,D05.SI,O39.SI")
        assert mod.WATCHLIST == ["ES3.SI", "D05.SI", "O39.SI"]

    def test_whitespace_trimmed(self):
        mod = _load("ES3.SI , D05.SI , O39.SI")
        assert mod.WATCHLIST == ["ES3.SI", "D05.SI", "O39.SI"]

    def test_missing_env_var_raises(self):
        os.environ.pop("WATCHLIST", None)
        import tickers
        with pytest.raises(EnvironmentError, match="WATCHLIST"):
            importlib.reload(tickers)

    def test_empty_env_var_raises(self):
        with pytest.raises(EnvironmentError, match="WATCHLIST"):
            _load("")

    def teardown_method(self):
        """Restore a valid WATCHLIST after each test so other tests aren't affected."""
        os.environ["WATCHLIST"] = "TEST.SI"
