"""Integration test: factor computation + strategy + backtest engine."""

import numpy as np
import pandas as pd
import pytest

from quantsys.backtest.events import BarEvent
from quantsys.factor.engine import FactorEngine
from quantsys.factor.registry import FactorRegistry
from quantsys.strategy.base import BaseStrategy


class SimpleFactorStrategy(BaseStrategy):
    """Test strategy that buys when Alpha#033 > 0.6, sells when < 0.4."""

    name = "SimpleFactorStrategy"
    required_factors = ["WQ033"]
    params = {"buy_threshold": 0.6, "sell_threshold": 0.4, "position_pct": 0.95}

    def on_bar(self, bar: BarEvent) -> dict:
        val = self._get_factor(bar, "WQ033")
        if val is None:
            return {"action": "HOLD"}
        if val > self.params["buy_threshold"] and self.position <= 0:
            return {"action": "BUY", "weight": self.params["position_pct"]}
        elif val < self.params["sell_threshold"] and self.position > 0:
            return {"action": "SELL", "weight": 1.0}
        return {"action": "HOLD"}


class TestFactorIntegration:
    def test_factor_engine_computes_all_20(self):
        registry = FactorRegistry()
        registry.discover()
        engine = FactorEngine(registry)

        np.random.seed(42)
        n = 100
        close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
        open_ = close + np.random.randn(n) * 0.1
        high = np.maximum(open_, close) + np.abs(np.random.randn(n) * 0.15)
        low = np.minimum(open_, close) - np.abs(np.random.randn(n) * 0.15)
        volume = np.random.randint(1000, 10000, n).astype(float)
        amount = close * volume

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=n, freq="B"),
                "symbol": "000001.SZ",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
            }
        )

        all_ids = [f.id for f in registry.list_factors()]
        result = engine.compute_batch(all_ids, df)

        for fid in all_ids:
            col = f"factor_{fid}"
            assert col in result.columns, f"Missing column {col}"
            valid = result[col].dropna()
            assert len(valid) > 0, f"Factor {fid} has no valid values"

    def test_factor_strategy_runs_without_error(self):
        """Verify a factor-based strategy can run through the backtest loop."""
        registry = FactorRegistry()
        registry.discover()
        engine = FactorEngine(registry)

        np.random.seed(42)
        n = 60
        close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
        open_ = close + np.random.randn(n) * 0.1
        high = np.maximum(open_, close) + np.abs(np.random.randn(n) * 0.15)
        low = np.minimum(open_, close) - np.abs(np.random.randn(n) * 0.15)
        volume = np.random.randint(1000, 10000, n).astype(float)
        amount = close * volume

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=n, freq="B"),
                "symbol": "000001.SZ",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "amount": amount,
            }
        )

        strategy = SimpleFactorStrategy()
        strategy.factor_data = engine.compute_batch(["WQ033"], df)

        strategy.on_start({"symbols": ["000001.SZ"]})

        signals = []
        for _, row in df.iterrows():
            bar = BarEvent(
                timestamp=row["timestamp"],
                symbol="000001.SZ",
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=int(row["volume"]),
                amount=row["amount"],
            )
            signal = strategy.on_bar(bar)
            signals.append(signal)

        actions = [s["action"] for s in signals]
        assert "HOLD" in actions
        non_hold = [a for a in actions if a != "HOLD"]
        assert len(non_hold) > 0, "Strategy generated no trading signals"
