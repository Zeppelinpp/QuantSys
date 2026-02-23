"""Tests for strategy factor integration."""

import pandas as pd
import pytest

from quantsys.backtest.events import BarEvent
from quantsys.strategy.base import BaseStrategy


class DummyFactorStrategy(BaseStrategy):
    name = "DummyFactorStrategy"
    required_factors = ["WQ002", "WQ033"]

    def on_bar(self, bar):
        val = self._get_factor(bar, "WQ002")
        if val is not None and val > 0.5:
            return {"action": "BUY", "weight": 0.95}
        return {"action": "HOLD"}


class TestStrategyFactorSupport:
    def test_get_factor_returns_value(self):
        strategy = DummyFactorStrategy()
        ts = pd.Timestamp("2024-01-03")
        strategy.factor_data = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "factor_WQ002": [0.1, 0.6, 0.8],
                "factor_WQ033": [0.5, 0.3, 0.7],
            }
        )
        bar = BarEvent(
            timestamp=ts,
            symbol="000001.SZ",
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.2,
            volume=1000,
            amount=10200.0,
        )
        assert strategy._get_factor(bar, "WQ002") == pytest.approx(0.8)
        assert strategy._get_factor(bar, "WQ033") == pytest.approx(0.7)

    def test_get_factor_returns_none_without_data(self):
        strategy = DummyFactorStrategy()
        bar = BarEvent(
            timestamp=pd.Timestamp("2024-01-01"),
            symbol="000001.SZ",
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.2,
            volume=1000,
            amount=10200.0,
        )
        assert strategy._get_factor(bar, "WQ002") is None

    def test_get_factor_returns_none_for_missing_timestamp(self):
        strategy = DummyFactorStrategy()
        strategy.factor_data = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(["2024-01-01"]),
                "factor_WQ002": [0.5],
            }
        )
        bar = BarEvent(
            timestamp=pd.Timestamp("2024-06-01"),
            symbol="000001.SZ",
            open=10.0,
            high=10.5,
            low=9.5,
            close=10.2,
            volume=1000,
            amount=10200.0,
        )
        assert strategy._get_factor(bar, "WQ002") is None

    def test_required_factors_default_empty(self):
        class PlainStrategy(BaseStrategy):
            name = "Plain"

            def on_bar(self, bar):
                return {"action": "HOLD"}

        s = PlainStrategy()
        assert s.required_factors == []
        assert s.factor_data is None
