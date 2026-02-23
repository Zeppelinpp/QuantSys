from typing import Any, Dict, List
from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class RsiMaV1(BaseStrategy):
    """Combined RSI and Moving Average strategy using OR logic for entry and exit signals.
    
    BUY when: RSI < 35 OR price crosses above MA20 from below
    SELL when: RSI > 70 OR price crosses below MA20 from above
    """
    name = "RsiMaV1"
    params = {
        "ma_period": 20,
        "rsi_period": 14,
        "rsi_oversold": 35,
        "rsi_overbought": 70,
        "position_pct": 0.95
    }

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self.price_history: List[float] = []
        self._prev_close = None
        self._prev_ma = None

    def _calculate_ma(self, prices: List[float], period: int) -> float:
        """Calculate simple moving average."""
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(len(prices) - period, len(prices)):
            delta = prices[i] - prices[i - 1]
            if delta >= 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(delta))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """Execute strategy logic on each bar."""
        current_price = bar.close
        self.price_history.append(current_price)
        
        # Need enough data to calculate indicators
        if len(self.price_history) < max(self.params["ma_period"], self.params["rsi_period"] + 1):
            return {"action": "HOLD"}
        
        # Calculate indicators
        ma = self._calculate_ma(self.price_history, self.params["ma_period"])
        rsi = self._calculate_rsi(self.price_history, self.params["rsi_period"])
        
        # Determine crossover signals
        ma_cross_above = False
        ma_cross_below = False
        
        if self._prev_close is not None and self._prev_ma is not None:
            if self._prev_close <= self._prev_ma and current_price > ma:
                ma_cross_above = True
            if self._prev_close >= self._prev_ma and current_price < ma:
                ma_cross_below = True
        
        # Update previous values for next iteration
        self._prev_close = current_price
        self._prev_ma = ma
        
        # Generate signals
        buy_signal = (rsi < self.params["rsi_oversold"]) or ma_cross_above
        sell_signal = (rsi > self.params["rsi_overbought"]) or ma_cross_below
        
        # Execute actions based on position and signals
        if not self.position and buy_signal:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        elif self.position and sell_signal:
            return {"action": "SELL", "weight": 1.0}
        else:
            return {"action": "HOLD"}