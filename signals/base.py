"""
signals/base.py — Abstract base class for all trading strategies.
"""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name shown in the Telegram footer."""

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> dict:
        """
        Accept a DataFrame with columns [open, high, low, close, volume].
        Return a dict with at minimum:
            signal : "BUY" | "SELL" | "HOLD"
            detail : human-readable explanation string
        """