"""RSI bounce strategy example."""

from typing import Any, Dict, List

from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class RSIBounceStrategy(BaseStrategy):
    """RSI oversold bounce strategy.

    Buys when RSI < oversold threshold, sells when RSI > overbought threshold.
    """

    name = "RSIBounceStrategy"
    params = {
        "period": 14,
        "oversold": 30,
        "overbought": 70,
        "position_pct": 0.95,
    }

    def __init__(self, params: Dict[str, Any] = None) -> None:
        """Initialize strategy."""
        super().__init__(params)
        self.price_history: List[float] = []
        self.rsi_history: List[float] = []

    def on_start(self, context: Dict[str, Any]) -> None:
        """Initialize on backtest start."""
        self.price_history = []
        self.rsi_history = []

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate RSI for given prices."""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, period + 1):
            change = prices[-i] - prices[-i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """Process bar and generate signal."""
        close = bar.close
        self.price_history.append(close)

        # Need enough data for RSI calculation
        if len(self.price_history) < self.params["period"] + 1:
            return {"action": "HOLD"}

        # Calculate RSI
        rsi = self._calculate_rsi(self.price_history, self.params["period"])
        self.rsi_history.append(rsi)

        # Generate signals
        if rsi < self.params["oversold"] and self.position <= 0:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        elif rsi > self.params["overbought"] and self.position > 0:
            return {"action": "SELL", "weight": 1.0}

        return {"action": "HOLD"}
