"""Execution handler for backtest engine."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from loguru import logger

from .events import FillEvent, OrderEvent


@dataclass
class ExecutionConfig:
    """Execution configuration."""

    # Commission rates
    commission_rate: float = 0.0003  # 万3
    min_commission: float = 5.0  # Minimum 5 yuan
    stamp_duty_rate: float = 0.0005  # 印花税千0.5 (sell only)
    transfer_fee_rate: float = 0.00001  # 过户费万0.01

    # Slippage model
    small_order_threshold: int = 1000  # Shares
    medium_order_threshold: int = 10000  # Shares
    small_slippage: float = 0.0001  # 1 bps
    medium_slippage: float = 0.0005  # 5 bps
    large_slippage: float = 0.001  # 10 bps

    # Execution rules
    price_type: str = "next_open"  # "next_open" or "current_close"


class ExecutionHandler:
    """Handles order execution with realistic market simulation."""

    def __init__(self, config: Optional[ExecutionConfig] = None) -> None:
        """Initialize execution handler."""
        self.config = config or ExecutionConfig()
        self.order_history: List[OrderEvent] = []
        self.fill_history: List[FillEvent] = []

    def execute_order(
        self,
        order: OrderEvent,
        next_bar: Optional[Dict],
        current_bar: Optional[Dict] = None,
    ) -> Optional[FillEvent]:
        """Execute an order and return fill event.

        Args:
            order: The order to execute
            next_bar: The next bar's data (for next_open price_type)
            current_bar: The current bar's data (for current_close price_type)

        Returns:
            FillEvent if order is filled, None otherwise
        """
        if next_bar is None and current_bar is None:
            logger.warning(f"No price data for order execution: {order}")
            return None

        # Determine execution price
        if self.config.price_type == "next_open":
            if next_bar is None:
                logger.warning("Next bar required for next_open execution")
                return None
            execution_price = next_bar["open"]
            timestamp = next_bar["timestamp"]
        else:
            if current_bar is None:
                logger.warning("Current bar required for current_close execution")
                return None
            execution_price = current_bar["close"]
            timestamp = current_bar["timestamp"]

        # Check limit price for limit orders
        if order.order_type == "LIMIT" and order.limit_price is not None:
            if order.side == "BUY" and execution_price > order.limit_price:
                logger.debug(
                    f"Limit order not filled: price {execution_price} > limit {order.limit_price}"
                )
                return None
            if order.side == "SELL" and execution_price < order.limit_price:
                logger.debug(
                    f"Limit order not filled: price {execution_price} < limit {order.limit_price}"
                )
                return None

        # Calculate slippage
        slippage = self._calculate_slippage(order.quantity, execution_price)

        # Adjust fill price by slippage
        if order.side == "BUY":
            fill_price = execution_price * (1 + slippage)
        else:
            fill_price = execution_price * (1 - slippage)

        # Calculate commission
        commission = self._calculate_commission(order.side, fill_price, order.quantity)

        # Create fill event
        fill = FillEvent(
            timestamp=timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage * execution_price * order.quantity,
            order_id=str(id(order)),
        )

        self.order_history.append(order)
        self.fill_history.append(fill)

        logger.debug(
            f"Order filled: {order.side} {order.quantity} {order.symbol} @ {fill_price:.2f} "
            f"(commission: {commission:.2f}, slippage: {slippage * 100:.2f}%)"
        )

        return fill

    def _calculate_slippage(self, quantity: int, price: float) -> float:
        """Calculate slippage based on order size."""
        if quantity < self.config.small_order_threshold:
            return self.config.small_slippage
        elif quantity < self.config.medium_order_threshold:
            return self.config.medium_slippage
        else:
            return self.config.large_slippage

    def _calculate_commission(self, side: str, price: float, quantity: int) -> float:
        """Calculate total commission including fees."""
        value = price * quantity

        # Base commission
        commission = max(value * self.config.commission_rate, self.config.min_commission)

        # Stamp duty (sell only)
        if side == "SELL":
            commission += value * self.config.stamp_duty_rate

        # Transfer fee
        commission += value * self.config.transfer_fee_rate

        return commission

    def check_price_limits(
        self,
        symbol: str,
        side: str,
        price: float,
        prev_close: float,
        price_limit_pct: float = 0.1,  # A-shares typically 10%
    ) -> bool:
        """Check if price is within daily limits (涨停/跌停).

        Returns:
            True if order can be executed, False otherwise
        """
        upper_limit = prev_close * (1 + price_limit_pct)
        lower_limit = prev_close * (1 - price_limit_pct)

        if side == "BUY" and price >= upper_limit:
            logger.debug(f"Cannot buy {symbol} at {price}: at upper limit {upper_limit}")
            return False

        if side == "SELL" and price <= lower_limit:
            logger.debug(f"Cannot sell {symbol} at {price}: at lower limit {lower_limit}")
            return False

        return True
