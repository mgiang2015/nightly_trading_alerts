"""
signals/ — Re-exports all public strategy classes and the runner for
           convenient single-line imports in main.py and tests.

Usage:
    from signals import compute_signals, EMACrossStrategy
    from signals import VolumeBreakoutStrategy, RSIDivergenceStrategy
    from signals import DailyReturnStrategy, TrendFilteredDailyReturnStrategy
"""

from signals.base import BaseStrategy
from signals.base_cross import BaseCrossStrategy
from signals.daily_return import DailyReturnStrategy
from signals.ema_cross import EMACrossStrategy
from signals.engine import compute_signals
from signals.rsi_divergence import RSIDivergenceStrategy
from signals.trend_filtered_daily_return import TrendFilteredDailyReturnStrategy
from signals.volume_breakout import VolumeBreakoutStrategy

__all__ = [
    "BaseStrategy",
    "BaseCrossStrategy",
    "EMACrossStrategy",
    "VolumeBreakoutStrategy",
    "RSIDivergenceStrategy",
    "DailyReturnStrategy",
    "TrendFilteredDailyReturnStrategy",
    "compute_signals",
]