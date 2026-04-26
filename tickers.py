# tickers.py — Loads watchlist from the WATCHLIST environment variable.
# Set in .env as a comma-separated string, e.g.:
#   WATCHLIST=ES3.SI,D05.SI,O39.SI,U11.SI

import os

_raw = os.environ.get("WATCHLIST", "")
if not _raw:
    raise EnvironmentError("WATCHLIST environment variable is not set. Add it to your .env file.")

WATCHLIST = [t.strip() for t in _raw.split(",") if t.strip()]


# ── Sector classification ─────────────────────────────────────────────────────
# Used by the fundamental filter to apply sector-appropriate thresholds.
# Three sectors are supported:
#   "bank"        — DBS, OCBC, UOB. P/B only; D/E is meaningless for banks.
#   "reit"        — All SGX REITs. D/E and dividend yield matter; P/B less so.
#   "industrial"  — Everything else. Standard P/B and D/E thresholds apply.
#
# Any ticker not listed here defaults to "industrial".

SECTOR_MAP = {
    # Banks
    "D05.SI": "bank",
    "O39.SI": "bank",
    "U11.SI": "bank",

    # REITs
    "C38U.SI": "reit",   # CapitaLand Integrated Commercial Trust
    "A17U.SI": "reit",   # Ascendas REIT
    "M44U.SI": "reit",   # Mapletree Logistics Trust
    "ME8U.SI": "reit",   # Mapletree Industrial Trust
    "N2IU.SI": "reit",   # Mapletree Pan Asia Commercial Trust

    # Industrials / others (explicit for clarity — same as default)
    "Z74.SI":  "industrial",   # Singtel
    "BN4.SI":  "industrial",   # Keppel Corp
    "9CI.SI":  "industrial",   # CapitaLand Investment
    "S68.SI":  "industrial",   # SGX Ltd
    "S63.SI":  "industrial",   # ST Engineering
    "F34.SI":  "industrial",   # Wilmar International
    "C07.SI":  "industrial",   # Jardine Cycle & Carriage
    "J36.SI":  "industrial",   # Jardine Matheson
    "Y92.SI":  "industrial",   # Thai Beverage
    "G13.SI":  "industrial",   # Genting Singapore
    "C09.SI":  "industrial",   # City Developments
    "C52.SI":  "industrial",   # ComfortDelGro
    "C6L.SI":  "industrial",   # Singapore Airlines
    "S58.SI":  "industrial",   # SATS
    "U96.SI":  "industrial",   # Sembcorp Industries
    "U14.SI":  "industrial",   # UOL Group
    "V03.SI":  "industrial",   # Venture Corporation
}