"""
signals/ — Re-exports all public strategy classes and the runner for
           convenient single-line imports in main.py and tests.

Usage:
    from signals import compute_signals, EMACrossStrategy
    from signals import VolumeBreakoutStrategy, RSIDivergenceStrategy
"""

from signals.base import BaseStrategy
from signals.ema_cross import EMACrossStrategy
from signals.volume_breakout import VolumeBreakoutStrategy
from signals.rsi_divergence import RSIDivergenceStrategy
from signals.daily_return import DailyReturnStrategy
from signals.engine import compute_signals

__all__ = [
    "BaseStrategy",
    "EMACrossStrategy",
    "VolumeBreakoutStrategy",
    "RSIDivergenceStrategy",
    "DailyReturnStrategy",
    "compute_signals",
]