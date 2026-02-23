"""Base strategy class for QuantSys."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from quantsys.backtest.events import BarEvent


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    name: str = "BaseStrategy"
    params: Dict[str, Any] = {}
    required_factors: List[str] = []

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        """Initialize strategy with parameters.

        Args:
            params: Strategy parameters (overrides defaults)
        """
        self.params = self.params.copy()
        if params:
            self.params.update(params)

        self.position: int = 0
        self.data: Dict[str, Any] = {}
        self.factor_data: Optional[pd.DataFrame] = None

    @abstractmethod
    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """Process a new bar and generate trading signal.

        Args:
            bar: BarEvent with OHLCV data

        Returns:
            Signal dict: {'action': 'BUY'|'SELL'|'HOLD', 'weight': float}
        """
        pass

    def on_start(self, context: Dict[str, Any]) -> None:
        """Called when backtest starts.

        Args:
            context: Backtest context with symbols, dates, etc.
        """
        pass

    def on_stop(self, context: Dict[str, Any]) -> None:
        """Called when backtest ends.

        Args:
            context: Backtest results summary
        """
        pass

    def _get_factor(self, bar: BarEvent, factor_id: str) -> Optional[float]:
        """Look up a pre-computed factor value for the current bar's timestamp.

        Returns None if factor_data is unavailable or the timestamp is missing.
        """
        if self.factor_data is None:
            return None

        col = f"factor_{factor_id}"
        if col not in self.factor_data.columns:
            return None

        mask = self.factor_data["timestamp"] == bar.timestamp
        matched = self.factor_data.loc[mask, col]
        if matched.empty:
            return None

        val = matched.iloc[0]
        if pd.isna(val):
            return None
        return float(val)

    def get_position(self) -> int:
        """Get current position size."""
        return self.position

    def set_position(self, position: int) -> None:
        """Set current position size."""
        self.position = position
