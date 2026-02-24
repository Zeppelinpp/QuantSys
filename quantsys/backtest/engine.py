"""Backtest engine for QuantSys."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from quantsys.data.database import Database

from .events import BarEvent, FillEvent, OrderEvent, SignalEvent
from .execution import ExecutionConfig, ExecutionHandler
from .metrics import BacktestMetrics, calculate_metrics
from .portfolio import Portfolio


@dataclass
class BacktestResult:
    """Backtest result container."""

    strategy_name: str
    start_date: datetime
    end_date: datetime
    symbols: List[str]
    metrics: BacktestMetrics
    equity_curve: List[Dict] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)
    signals: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "symbols": self.symbols,
            "metrics": self.metrics.to_dict(),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "signals": self.signals,
        }


class BacktestEngine:
    """Event-driven backtest engine."""

    def __init__(
        self,
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        strategy: Any,
        initial_cash: float = 1_000_000.0,
        database: Optional[Database] = None,
        execution_config: Optional[ExecutionConfig] = None,
        benchmark_symbol: Optional[str] = None,
    ) -> None:
        """Initialize backtest engine.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols to trade
            strategy: Strategy instance
            initial_cash: Initial cash
            database: Database instance (optional)
            execution_config: Execution configuration (optional)
            benchmark_symbol: Index symbol for benchmark comparison (e.g. "000300")
        """
        self.start_date = start_date
        self.end_date = end_date
        self.symbols = symbols
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.benchmark_symbol = benchmark_symbol

        self.db = database
        self.portfolio = Portfolio(initial_cash=initial_cash)
        self.execution = ExecutionHandler(config=execution_config)

        # Event history
        self.signals: List[SignalEvent] = []
        self.orders: List[OrderEvent] = []
        self.fills: List[FillEvent] = []

        # Current bar data for each symbol
        self.current_bars: Dict[str, Dict] = {}
        self.next_bars: Dict[str, Dict] = {}

    def run(self) -> BacktestResult:
        """Run the backtest.

        Returns:
            BacktestResult with all metrics and history
        """
        logger.info(
            f"Starting backtest: {self.start_date.date()} to {self.end_date.date()}, "
            f"symbols: {self.symbols}"
        )

        # Load market data
        data = self._load_data()
        if data.empty:
            raise ValueError("No data loaded for backtest")

        # Pre-compute factor data if the strategy declares required_factors
        if getattr(self.strategy, "required_factors", None):
            from quantsys.factor.engine import FactorEngine
            from quantsys.factor.registry import FactorRegistry

            registry = FactorRegistry()
            registry.discover()
            factor_engine = FactorEngine(registry)
            self.strategy.factor_data = factor_engine.compute_batch(
                self.strategy.required_factors, data
            )
            logger.info(
                f"Pre-computed {len(self.strategy.required_factors)} factors: "
                f"{self.strategy.required_factors}"
            )

        # Initialize strategy
        self.strategy.on_start(
            {
                "symbols": self.symbols,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "initial_cash": self.initial_cash,
            }
        )

        # Process each timestamp
        timestamps = sorted(data["timestamp"].unique())

        for i, timestamp in enumerate(timestamps):
            # Get data for current timestamp
            current_data = data[data["timestamp"] == timestamp]

            # Update current bars
            self.current_bars = {}
            for _, row in current_data.iterrows():
                self.current_bars[row["symbol"]] = row.to_dict()

            # Get next bars for execution
            if i + 1 < len(timestamps):
                next_timestamp = timestamps[i + 1]
                next_data = data[data["timestamp"] == next_timestamp]
                self.next_bars = {}
                for _, row in next_data.iterrows():
                    self.next_bars[row["symbol"]] = row.to_dict()
            else:
                self.next_bars = {}

            # Process bar event
            self._process_bar(timestamp)

        # Stop strategy
        self.strategy.on_stop(
            {
                "portfolio": self.portfolio.get_state(),
                "trades": len(self.fills),
            }
        )

        # Load benchmark data if specified
        benchmark_returns = None
        if self.benchmark_symbol:
            benchmark_returns = self._load_benchmark_returns()

        # Calculate metrics
        metrics = calculate_metrics(
            self.portfolio.equity_curve,
            self.fills,
            benchmark_returns=benchmark_returns,
        )

        logger.info(
            f"Backtest complete: total_return={metrics.total_return:.2%}, "
            f"sharpe={metrics.sharpe_ratio:.2f}, max_dd={metrics.max_drawdown:.2%}"
        )

        # Build result
        result = BacktestResult(
            strategy_name=getattr(self.strategy, "name", "Unknown"),
            start_date=self.start_date,
            end_date=self.end_date,
            symbols=self.symbols,
            metrics=metrics,
            equity_curve=[
                {
                    "timestamp": state.timestamp.isoformat(),
                    "cash": state.cash,
                    "positions_value": state.positions_value,
                    "total_value": state.total_value,
                }
                for state in self.portfolio.equity_curve
            ],
            trades=[
                {
                    "timestamp": fill.timestamp.isoformat(),
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.fill_price,
                    "commission": fill.commission,
                }
                for fill in self.fills
            ],
            signals=[
                {
                    "timestamp": sig.timestamp.isoformat(),
                    "symbol": sig.symbol,
                    "action": sig.action,
                    "weight": sig.weight,
                }
                for sig in self.signals
            ],
        )

        return result

    def _load_data(self) -> pd.DataFrame:
        """Load market data from database."""
        if self.db is None:
            from quantsys.config import get_settings

            settings = get_settings()
            self.db = Database(settings.db_path)

        # Build query
        symbols_str = ",".join(f"'{s}'" for s in self.symbols)
        start_str = self.start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_str = self.end_date.strftime("%Y-%m-%d %H:%M:%S")

        # Try minute data first
        sql = f"""
        SELECT symbol, timestamp, open, high, low, close, volume, amount
        FROM market_data
        WHERE symbol IN ({symbols_str})
          AND timestamp >= '{start_str}'
          AND timestamp <= '{end_str}'
        ORDER BY timestamp, symbol
        """

        rows = self.db.fetchall(sql)

        # Fall back to daily data if no minute data
        if not rows:
            logger.info("No minute data found, trying daily data...")
            sql = f"""
            SELECT symbol, date as timestamp, open, high, low, close, volume, amount
            FROM daily_data
            WHERE symbol IN ({symbols_str})
              AND date >= '{start_str[:10]}'
              AND date <= '{end_str[:10]}'
            ORDER BY date, symbol
            """
            rows = self.db.fetchall(sql)

        if not rows:
            logger.warning("No data found for backtest period")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        logger.info(f"Loaded {len(df)} bars for {df['symbol'].nunique()} symbols")

        return df

    def _process_bar(self, timestamp: datetime) -> None:
        """Process a single bar."""
        # Update portfolio with current prices
        prices = {symbol: bar["close"] for symbol, bar in self.current_bars.items()}
        self.portfolio.update_market(timestamp, prices)

        # Generate signals for each symbol
        for symbol, bar_data in self.current_bars.items():
            bar_event = BarEvent.from_dict(bar_data)

            # Sync strategy.position with portfolio for this symbol
            pos = self.portfolio.get_position(symbol)
            self.strategy.set_position(pos.quantity if pos else 0)

            # Get signal from strategy
            signal = self.strategy.on_bar(bar_event)

            if signal and signal["action"] != "HOLD":
                signal_event = SignalEvent(
                    timestamp=timestamp,
                    symbol=symbol,
                    action=signal["action"],
                    weight=signal.get("weight", 1.0),
                )
                self.signals.append(signal_event)

                # Create order from signal
                self._process_signal(signal_event)

    def _process_signal(self, signal: SignalEvent) -> None:
        """Process a signal and create order."""
        # Determine order quantity based on signal weight
        if signal.action == "BUY":
            # Calculate position size
            equity = self.portfolio.get_equity()
            position_value = equity * signal.weight

            # Get next bar's open price for estimation
            next_bar = self.next_bars.get(signal.symbol)
            if next_bar is None:
                return

            price = next_bar["open"]
            quantity = int(position_value / price / 100) * 100  # Round to 100 shares

            if quantity <= 0:
                return

            side = "BUY"

        else:  # SELL
            # Sell all or partial position
            position = self.portfolio.get_position(signal.symbol)
            if position is None or position.quantity <= 0:
                return

            quantity = int(position.quantity * signal.weight)
            if quantity <= 0:
                return

            side = "SELL"

        order = OrderEvent(
            timestamp=signal.timestamp,
            symbol=signal.symbol,
            side=side,
            quantity=quantity,
        )

        self.orders.append(order)
        self._process_order(order)

    def _process_order(self, order: OrderEvent) -> None:
        """Process an order and create fill."""
        # Validate order
        next_bar = self.next_bars.get(order.symbol)
        if not self.portfolio.submit_order(order, next_bar):
            return

        # Execute order
        current_bar = self.current_bars.get(order.symbol)
        fill = self.execution.execute_order(order, next_bar, current_bar)

        if fill:
            self.fills.append(fill)
            self.portfolio.process_fill(fill)

    def _load_benchmark_returns(self) -> Optional[np.ndarray]:
        """Load benchmark index returns aligned to backtest period."""
        if self.db is None:
            return None

        start_str = self.start_date.strftime("%Y-%m-%d")
        end_str = self.end_date.strftime("%Y-%m-%d")

        sql = f"""
        SELECT date, close FROM index_daily_data
        WHERE symbol = '{self.benchmark_symbol}'
          AND date >= '{start_str}'
          AND date <= '{end_str}'
        ORDER BY date
        """
        rows = self.db.fetchall(sql)
        if len(rows) < 2:
            logger.warning(f"Insufficient benchmark data for {self.benchmark_symbol}")
            return None

        prices = np.array([r["close"] for r in rows], dtype=float)
        returns = np.diff(prices) / prices[:-1]
        return returns
