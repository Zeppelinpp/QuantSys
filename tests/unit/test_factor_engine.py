"""Tests for factor computation engine."""

import numpy as np
import pandas as pd
import pytest

from quantsys.factor.engine import FactorEngine
from quantsys.factor.registry import FactorRegistry


@pytest.fixture
def engine():
    registry = FactorRegistry()
    registry.discover()
    return FactorEngine(registry)


@pytest.fixture
def ohlcv_df():
    np.random.seed(42)
    n = 60
    close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
    open_ = close + np.random.randn(n) * 0.1
    high = np.maximum(open_, close) + np.abs(np.random.randn(n) * 0.15)
    low = np.minimum(open_, close) - np.abs(np.random.randn(n) * 0.15)
    volume = np.random.randint(1000, 10000, n).astype(float)
    amount = close * volume

    return pd.DataFrame(
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


class TestFactorEngine:
    def test_compute_single(self, engine, ohlcv_df):
        result = engine.compute("WQ033", ohlcv_df)
        assert isinstance(result, pd.Series)
        assert len(result) == len(ohlcv_df)

    def test_compute_batch(self, engine, ohlcv_df):
        result = engine.compute_batch(["WQ002", "WQ012", "WQ033"], ohlcv_df)
        assert isinstance(result, pd.DataFrame)
        assert "factor_WQ002" in result.columns
        assert "factor_WQ012" in result.columns
        assert "factor_WQ033" in result.columns
        assert "close" in result.columns

    def test_compute_unknown_factor(self, engine, ohlcv_df):
        with pytest.raises(KeyError):
            engine.compute("NONEXIST", ohlcv_df)

    def test_validate_data_success(self, engine, ohlcv_df):
        assert engine.validate_data("WQ002", ohlcv_df) is True

    def test_validate_data_missing_column(self, engine, ohlcv_df):
        df_no_volume = ohlcv_df.drop(columns=["volume"])
        assert engine.validate_data("WQ002", df_no_volume) is False

    def test_validate_data_insufficient_rows(self, engine):
        short_df = pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [100.0],
                "amount": [100.0],
            }
        )
        assert engine.validate_data("WQ002", short_df) is False
