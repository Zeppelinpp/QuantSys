"""Momentum strategy example."""

from typing import Any, Dict, List

from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Simple moving average crossover momentum strategy.

    Buys when price crosses above MA, sells when price crosses below MA.
    """

    name = "MomentumStrategy"
    params = {
        "ma_period": 20,
        "position_pct": 0.95,  # Use 95% of equity
    }

    def __init__(self, params: Dict[str, Any] = None) -> None:
        """Initialize strategy."""
        super().__init__(params)
        self.price_history: List[float] = []

    def on_start(self, context: Dict[str, Any]) -> None:
        """Initialize on backtest start."""
        self.price_history = []

    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """Process bar and generate signal."""
        close = bar.close
        self.price_history.append(close)

        # Need enough data for MA calculation
        if len(self.price_history) < self.params["ma_period"]:
            return {"action": "HOLD"}

        # Calculate moving average
        ma = sum(self.price_history[-self.params["ma_period"] :]) / self.params[
            "ma_period"
        ]

        # Generate signals
        if close > ma and self.position <= 0:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        elif close < ma and self.position > 0:
            return {"action": "SELL", "weight": 1.0}

        return {"action": "HOLD"}
