from typing import Any, Dict, List
from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class RsiMaCombined(BaseStrategy):
    """
    A combined trading strategy that uses RSI for entry/exit signals and a moving average
    as a trend filter. The strategy only takes long positions when the price is above 
    the 60-day moving average (trend filter) and RSI is below 35 (oversold condition). 
    It exits when RSI rises above 75 (overbought) or when price falls below the 60-day MA.
    """
    name = "RsiMaCombined"
    params = {
        "rsi_period": 14,
        "ma_period": 60,
        "rsi_oversold": 35,
        "rsi_overbought": 75,
        "position_pct": 1.0
    }

    def __init__(self, params: Dict[str, Any] = None) -> None:
        super().__init__(params)
        self.rsi_period = self.params.get("rsi_period", 14)
        self.ma_period = self.params.get("ma_period", 60)
        self.rsi_oversold = self.params.get("rsi_oversold", 35)
        self.rsi_overbought = self.params.get("rsi_overbought", 75)
        self.position_pct = self.params.get("position_pct", 1.0)
        
        self.price_history: List[float] = []
        self.in_position: bool = False

    def _calculate_rsi(self) -> float:
        """Calculate RSI based on price history."""
        if len(self.price_history) < self.rsi_period + 1:
            return 50.0
        
        gains = []
        losses = []
        for i in range(-self.rsi_period, 0):
            delta = self.price_history[i] - self.price_history[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(delta))
        
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_ma(self) -> float:
        """Calculate simple moving average."""
        if len(self.price_history) < self.ma_period:
            return float('inf')  # Avoid trading until enough data
        return sum(self.price_history[-self.ma_period:]) / self.ma_period

    def on_bar(self, bar: BarEvent) -> Dict[str, Any]:
        """
        Process each new price bar and generate trading signals.
        
        Returns:
            Dict with 'action' ('BUY', 'SELL', 'HOLD') and 'weight' (float between 0 and 1).
        """
        self.price_history.append(bar.close)
        
        # Wait until we have enough data
        if len(self.price_history) < self.ma_period:
            return {"action": "HOLD", "weight": 0.0}
        
        current_price = bar.close
        ma = self._calculate_ma()
        rsi = self._calculate_rsi()
        
        # Exit conditions
        if self.in_position:
            if rsi > self.rsi_overbought or current_price < ma:
                self.in_position = False
                return {"action": "SELL", "weight": 0.0}
            else:
                return {"action": "HOLD", "weight": self.position_pct}
        
        # Entry condition
        if not self.in_position:
            if rsi < self.rsi_oversold and current_price > ma:
                self.in_position = True
                return {"action": "BUY", "weight": self.position_pct}
        
        return {"action": "HOLD", "weight": 0.0}