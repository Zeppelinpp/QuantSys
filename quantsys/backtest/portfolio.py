"""Portfolio and position management for backtest."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger

from .events import FillEvent, OrderEvent


@dataclass
class Position:
    """Position in a single symbol."""

    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Track trade history for this position
    trades: List[Dict] = field(default_factory=list)

    def update_market_price(self, price: float) -> None:
        """Update market price and recalculate values."""
        self.market_price = price
        self.market_value = self.quantity * price
        if self.quantity > 0:
            self.unrealized_pnl = self.market_value - (self.quantity * self.avg_cost)

    def add_trade(self, fill: FillEvent) -> None:
        """Process a fill event and update position."""
        if fill.side == "BUY":
            # Calculate new average cost
            total_cost = (self.quantity * self.avg_cost) + fill.total_cost
            self.quantity += fill.quantity
            if self.quantity > 0:
                self.avg_cost = total_cost / self.quantity
        else:  # SELL
            # Calculate realized P&L
            cost_basis = fill.quantity * self.avg_cost
            proceeds = fill.value - fill.commission
            trade_pnl = proceeds - cost_basis
            self.realized_pnl += trade_pnl
            self.quantity -= fill.quantity

        self.trades.append({
            "timestamp": fill.timestamp,
            "side": fill.side,
            "quantity": fill.quantity,
            "price": fill.fill_price,
            "commission": fill.commission,
        })

        # Update market value
        self.update_market_price(fill.fill_price)


@dataclass
class PortfolioState:
    """Snapshot of portfolio state."""

    timestamp: datetime
    cash: float
    positions_value: float
    total_value: float
    unrealized_pnl: float
    realized_pnl: float


class Portfolio:
    """Portfolio manager for backtest."""

    def __init__(self, initial_cash: float = 1_000_000.0) -> None:
        """Initialize portfolio."""
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.equity_curve: List[PortfolioState] = []
        self.trades: List[FillEvent] = []

        # Track buy dates for T+1 rule
        self.buy_dates: Dict[str, datetime] = {}

    def update_market(self, timestamp: datetime, prices: Dict[str, float]) -> None:
        """Update portfolio with latest market prices."""
        positions_value = 0.0
        unrealized_pnl = 0.0

        for symbol, price in prices.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                position.update_market_price(price)
                positions_value += position.market_value
                unrealized_pnl += position.unrealized_pnl

        total_value = self.cash + positions_value

        # Record state
        state = PortfolioState(
            timestamp=timestamp,
            cash=self.cash,
            positions_value=positions_value,
            total_value=total_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=sum(p.realized_pnl for p in self.positions.values()),
        )
        self.equity_curve.append(state)

    def can_trade(self, symbol: str, side: str, timestamp: datetime) -> bool:
        """Check if trading is allowed (T+1 rule)."""
        if side == "SELL" and symbol in self.buy_dates:
            buy_date = self.buy_dates[symbol]
            if timestamp.date() <= buy_date.date():
                logger.debug(f"Cannot sell {symbol}: T+1 rule (bought on {buy_date.date()})")
                return False
        return True

    def submit_order(self, order: OrderEvent, next_bar: Optional[Dict] = None) -> bool:
        """Validate and submit an order.

        Returns:
            True if order is valid and can be submitted
        """
        # Check T+1 rule
        if not self.can_trade(order.symbol, order.side, order.timestamp):
            return False

        # Check if we have enough cash for buys
        if order.side == "BUY":
            if next_bar is None:
                return False
            estimated_cost = order.quantity * next_bar["open"] * 1.002  # Include fees
            if estimated_cost > self.cash:
                logger.warning(
                    f"Insufficient cash for order: need {estimated_cost:.2f}, have {self.cash:.2f}"
                )
                return False

        # Check if we have enough shares for sells
        if order.side == "SELL":
            position = self.positions.get(order.symbol)
            if position is None or position.quantity < order.quantity:
                logger.warning(
                    f"Insufficient shares for sell: want {order.quantity}, have "
                    f"{position.quantity if position else 0}"
                )
                return False

        return True

    def process_fill(self, fill: FillEvent) -> None:
        """Process a fill event and update portfolio."""
        # Get or create position
        if fill.symbol not in self.positions:
            self.positions[fill.symbol] = Position(symbol=fill.symbol)

        position = self.positions[fill.symbol]

        # Update cash
        if fill.side == "BUY":
            self.cash -= fill.total_cost
            # Record buy date for T+1
            self.buy_dates[fill.symbol] = fill.timestamp
        else:  # SELL
            self.cash += fill.value - fill.commission

        # Update position
        position.add_trade(fill)

        # Record trade
        self.trades.append(fill)

        logger.debug(
            f"Portfolio updated: cash={self.cash:.2f}, {fill.symbol} position={position.quantity}"
        )

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)

    def get_equity(self) -> float:
        """Get total equity (cash + positions)."""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    def get_state(self) -> Dict:
        """Get current portfolio state."""
        positions_value = sum(p.market_value for p in self.positions.values())
        return {
            "cash": self.cash,
            "positions_value": positions_value,
            "total_value": self.cash + positions_value,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "market_price": pos.market_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                }
                for symbol, pos in self.positions.items()
                if pos.quantity > 0
            },
        }
