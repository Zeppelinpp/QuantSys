from typing import Any, Dict, List
from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class RsiMaV2(BaseStrategy):
    name = "RsiMaV2"
    params = {
        "ma_period": 20,
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
        "position_pct": 0.95
    }

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self.price_history: List[float] = []

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
            if delta > 0:
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
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """
        Combined RSI and Moving Average strategy logic.
        
        BUY when price is above MA and RSI is below oversold level.
        SELL when price is below MA and RSI is above overbought level.
        """
        self.price_history.append(bar.close)
        
        # Not enough data yet
        if len(self.price_history) < max(self.params["ma_period"], self.params["rsi_period"] + 1):
            return {"action": "HOLD"}
        
        ma = self._calculate_ma(self.price_history, self.params["ma_period"])
        rsi = self._calculate_rsi(self.price_history, self.params["rsi_period"])
        current_price = bar.close
        
        # Buy signal: price above MA and RSI below oversold
        if not self.position and current_price > ma and rsi < self.params["oversold"]:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        
        # Sell signal: price below MA and RSI above overbought
        if self.position and current_price < ma and rsi > self.params["overbought"]:
            return {"action": "SELL", "weight": 1.0}
        
        return {"action": "HOLD"}