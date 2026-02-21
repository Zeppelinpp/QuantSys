"""Tests for backtest engine."""

from datetime import datetime

import pytest

from quantsys.backtest.engine import BacktestEngine
from quantsys.backtest.events import BarEvent
from quantsys.backtest.execution import ExecutionConfig
from quantsys.backtest.portfolio import Portfolio, Position
from quantsys.strategy.base import BaseStrategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""

    name = "MockStrategy"
    params = {"threshold": 100.0}

    def __init__(self, params=None):
        super().__init__(params)
        self.bars = []

    def on_bar(self, bar: BarEvent):
        """Simple strategy: buy when price > threshold."""
        self.bars.append(bar.close)

        if len(self.bars) < 2:
            return {"action": "HOLD"}

        if bar.close > self.params["threshold"] and self.position <= 0:
            return {"action": "BUY", "weight": 1.0}
        elif bar.close <= self.params["threshold"] and self.position > 0:
            return {"action": "SELL", "weight": 1.0}

        return {"action": "HOLD"}


class TestPortfolio:
    """Test portfolio functionality."""

    def test_initial_state(self):
        """Test initial portfolio state."""
        portfolio = Portfolio(initial_cash=1000000)
        assert portfolio.cash == 1000000
        assert portfolio.get_equity() == 1000000
        assert len(portfolio.positions) == 0

    def test_update_market(self):
        """Test market price update."""
        portfolio = Portfolio(initial_cash=1000000)

        # Create a position
        position = Position(symbol="TEST", quantity=100, avg_cost=50.0)
        portfolio.positions["TEST"] = position

        # Update market
        portfolio.update_market(
            datetime.now(),
            {"TEST": 55.0}
        )

        assert position.market_price == 55.0
        assert position.market_value == 5500.0
        assert position.unrealized_pnl == 500.0

    def test_position_add_trade(self):
        """Test adding trades to position."""
        from quantsys.backtest.events import FillEvent

        position = Position(symbol="TEST")

        # Buy 100 shares at $50
        fill_buy = FillEvent(
            timestamp=datetime.now(),
            symbol="TEST",
            side="BUY",
            quantity=100,
            fill_price=50.0,
            commission=5.0,
            slippage=0.0,
        )
        position.add_trade(fill_buy)

        assert position.quantity == 100
        assert position.avg_cost > 0

        # Sell 50 shares at $55
        fill_sell = FillEvent(
            timestamp=datetime.now(),
            symbol="TEST",
            side="SELL",
            quantity=50,
            fill_price=55.0,
            commission=5.0,
            slippage=0.0,
        )
        position.add_trade(fill_sell)

        assert position.quantity == 50
        assert position.realized_pnl > 0


class TestExecutionHandler:
    """Test execution handler."""

    def test_calculate_slippage(self):
        """Test slippage calculation."""
        from quantsys.backtest.execution import ExecutionHandler

        config = ExecutionConfig(
            small_order_threshold=1000,
            medium_order_threshold=10000,
            small_slippage=0.0001,
            medium_slippage=0.0005,
            large_slippage=0.001,
        )
        handler = ExecutionHandler(config)

        # Small order
        assert handler._calculate_slippage(500, 100.0) == 0.0001

        # Medium order
        assert handler._calculate_slippage(5000, 100.0) == 0.0005

        # Large order
        assert handler._calculate_slippage(20000, 100.0) == 0.001

    def test_calculate_commission(self):
        """Test commission calculation."""
        from quantsys.backtest.execution import ExecutionHandler

        config = ExecutionConfig(
            commission_rate=0.0003,
            min_commission=5.0,
            stamp_duty_rate=0.0005,
            transfer_fee_rate=0.00001,
        )
        handler = ExecutionHandler(config)

        # Buy order - no stamp duty
        commission_buy = handler._calculate_commission("BUY", 100.0, 1000)
        expected = max(100.0 * 1000 * 0.0003, 5.0) + 100.0 * 1000 * 0.00001
        assert commission_buy == pytest.approx(expected, rel=1e-5)

        # Sell order - with stamp duty
        commission_sell = handler._calculate_commission("SELL", 100.0, 1000)
        expected = max(100.0 * 1000 * 0.0003, 5.0)
        expected += 100.0 * 1000 * 0.0005  # stamp duty
        expected += 100.0 * 1000 * 0.00001  # transfer fee
        assert commission_sell == pytest.approx(expected, rel=1e-5)


class TestBacktestEngine:
    """Test backtest engine."""

    def test_engine_initialization(self):
        """Test engine initialization."""
        strategy = MockStrategy()

        engine = BacktestEngine(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            symbols=["000001.SZ"],
            strategy=strategy,
            initial_cash=1000000,
        )

        assert engine.start_date == datetime(2024, 1, 1)
        assert engine.end_date == datetime(2024, 1, 31)
        assert engine.symbols == ["000001.SZ"]
        assert engine.initial_cash == 1000000
