# tickers.py — Loads watchlist from the WATCHLIST environment variable.
# Set in .env as a comma-separated string, e.g.:
#   WATCHLIST=ES3.SI,D05.SI,O39.SI,U11.SI

import os

_raw = os.environ.get("WATCHLIST", "")
if not _raw:
    raise EnvironmentError("WATCHLIST environment variable is not set. Add it to your .env file.")

WATCHLIST = [t.strip() for t in _raw.split(",") if t.strip()]