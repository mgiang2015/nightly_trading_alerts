"""
signals/base_cross.py — Abstract base class for cross-sectional strategies.

Cross-sectional strategies rank all tickers against each other before
assigning signals, so they need to see the full dataset at once rather
than processing each ticker independently like BaseStrategy does.
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseCrossStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name shown in the Telegram footer."""

    @abstractmethod
    def compute_all(self, data: dict[str, pd.DataFrame]) -> list[dict]:
        """
        Accept the full ticker dataset and return a list of result dicts,
        one per ticker, each containing at minimum:
            ticker : str
            signal : "BUY" | "SELL" | "HOLD"
            detail : human-readable explanation string
        """
