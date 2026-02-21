"""Event definitions for backtest engine."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class BarEvent:
    """Market data bar event."""

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float

    @classmethod
    def from_dict(cls, data: Dict) -> "BarEvent":
        """Create BarEvent from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            symbol=data["symbol"],
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
            volume=int(data["volume"]),
            amount=float(data["amount"]),
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
        }


@dataclass
class SignalEvent:
    """Trading signal event from strategy."""

    timestamp: datetime
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    weight: float = 1.0  # Position weight (0.0 to 1.0)
    confidence: float = 1.0  # Signal confidence (0.0 to 1.0)
    metadata: Optional[Dict] = None

    def __post_init__(self):
        """Validate signal."""
        if self.action not in ("BUY", "SELL", "HOLD"):
            raise ValueError(f"Invalid action: {self.action}")
        if not 0 <= self.weight <= 1:
            raise ValueError(f"Weight must be between 0 and 1, got {self.weight}")


@dataclass
class OrderEvent:
    """Order event."""

    timestamp: datetime
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    order_type: str = "MARKET"  # "MARKET", "LIMIT"
    limit_price: Optional[float] = None
    signal_id: Optional[str] = None

    def __post_init__(self):
        """Validate order."""
        if self.side not in ("BUY", "SELL"):
            raise ValueError(f"Invalid side: {self.side}")
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")


@dataclass
class FillEvent:
    """Order fill event."""

    timestamp: datetime
    symbol: str
    side: str
    quantity: int
    fill_price: float
    commission: float
    slippage: float
    order_id: Optional[str] = None

    @property
    def total_cost(self) -> float:
        """Total cost including commission and slippage."""
        return self.fill_price * self.quantity + self.commission + self.slippage

    @property
    def value(self) -> float:
        """Fill value (price * quantity)."""
        return self.fill_price * self.quantity
