"""Paper trading account."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger


@dataclass
class Position:
    """Position in paper trading account."""

    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    market_price: float = 0.0

    @property
    def market_value(self) -> float:
        """Current market value."""
        return self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        if self.quantity > 0:
            return self.market_value - (self.quantity * self.avg_cost)
        return 0.0


@dataclass
class Trade:
    """Trade record."""

    timestamp: datetime
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    price: float
    commission: float
    pnl: Optional[float] = None  # Realized P&L for sells


class PaperAccount:
    """Virtual trading account for paper trading."""

    def __init__(
        self,
        name: str,
        initial_cash: float = 1_000_000.0,
        account_id: Optional[int] = None,
    ) -> None:
        """Initialize paper account.

        Args:
            name: Account name
            initial_cash: Initial cash balance
            account_id: Database ID (if loaded from DB)
        """
        self.account_id = account_id
        self.name = name
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.created_at = datetime.now()

        # Track buy dates for T+1
        self._buy_dates: Dict[str, datetime] = {}

    def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Execute buy order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            commission: Commission paid
            timestamp: Trade timestamp

        Returns:
            True if successful
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Check if we have enough cash
        total_cost = price * quantity + commission
        if total_cost > self.cash:
            logger.warning(
                f"Insufficient cash: need {total_cost:.2f}, have {self.cash:.2f}"
            )
            return False

        # Get or create position
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)

        position = self.positions[symbol]

        # Update average cost
        total_shares = position.quantity + quantity
        if total_shares > 0:
            position.avg_cost = (
                (position.quantity * position.avg_cost) + (quantity * price)
            ) / total_shares

        position.quantity = total_shares
        position.market_price = price

        # Deduct cash
        self.cash -= total_cost

        # Record buy date for T+1
        self._buy_dates[symbol] = timestamp

        # Record trade
        self.trades.append(
            Trade(
                timestamp=timestamp,
                symbol=symbol,
                side="BUY",
                quantity=quantity,
                price=price,
                commission=commission,
            )
        )

        logger.info(
            f"BUY {quantity} {symbol} @ {price:.2f}, cash={self.cash:.2f}"
        )
        return True

    def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Execute sell order.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Execution price
            commission: Commission paid
            timestamp: Trade timestamp

        Returns:
            True if successful
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Check T+1 rule
        if symbol in self._buy_dates:
            buy_date = self._buy_dates[symbol]
            if timestamp.date() <= buy_date.date():
                logger.warning(f"Cannot sell {symbol}: T+1 rule violation")
                return False

        # Check if we have position
        position = self.positions.get(symbol)
        if not position or position.quantity < quantity:
            logger.warning(
                f"Insufficient shares: want {quantity}, have "
                f"{position.quantity if position else 0}"
            )
            return False

        # Calculate realized P&L
        cost_basis = quantity * position.avg_cost
        proceeds = quantity * price - commission
        realized_pnl = proceeds - cost_basis

        # Update position
        position.quantity -= quantity
        position.market_price = price

        # Add cash
        self.cash += proceeds

        # Record trade
        self.trades.append(
            Trade(
                timestamp=timestamp,
                symbol=symbol,
                side="SELL",
                quantity=quantity,
                price=price,
                commission=commission,
                pnl=realized_pnl,
            )
        )

        logger.info(
            f"SELL {quantity} {symbol} @ {price:.2f}, pnl={realized_pnl:.2f}, "
            f"cash={self.cash:.2f}"
        )
        return True

    def update_prices(self, prices: Dict[str, float], timestamp: Optional[datetime] = None) -> None:
        """Update market prices for positions.

        Args:
            prices: Dict of symbol -> price
            timestamp: Update timestamp
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].market_price = price

    def get_portfolio_value(self) -> float:
        """Get total portfolio value (cash + positions)."""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        return self.positions.get(symbol)

    def get_state(self) -> Dict:
        """Get account state as dictionary."""
        positions_value = sum(p.market_value for p in self.positions.values())
        total_value = self.cash + positions_value

        return {
            "account_id": self.account_id,
            "name": self.name,
            "cash": self.cash,
            "initial_cash": self.initial_cash,
            "positions_value": positions_value,
            "total_value": total_value,
            "total_return": (total_value - self.initial_cash) / self.initial_cash,
            "positions": {
                symbol: {
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                    "market_price": pos.market_price,
                    "market_value": pos.market_value,
                    "unrealized_pnl": pos.unrealized_pnl,
                }
                for symbol, pos in self.positions.items()
                if pos.quantity > 0
            },
        }

    def to_db_record(self) -> Dict:
        """Convert to database record format."""
        import json

        return {
            "name": self.name,
            "initial_cash": self.initial_cash,
            "current_cash": self.cash,
            "positions": json.dumps({
                symbol: {
                    "quantity": pos.quantity,
                    "avg_cost": pos.avg_cost,
                }
                for symbol, pos in self.positions.items()
            }),
        }
