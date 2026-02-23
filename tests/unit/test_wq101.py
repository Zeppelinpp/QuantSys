"""Tests for WorldQuant 101 factor implementations."""

import numpy as np
import pandas as pd
import pytest

from quantsys.factor.library.wq101 import alpha002, alpha012, alpha033


@pytest.fixture
def ohlcv_df():
    """50-day OHLCV DataFrame with realistic price patterns."""
    np.random.seed(42)
    n = 50
    close = 10.0 + np.cumsum(np.random.randn(n) * 0.2)
    open_ = close + np.random.randn(n) * 0.1
    high = np.maximum(open_, close) + np.abs(np.random.randn(n) * 0.15)
    low = np.minimum(open_, close) - np.abs(np.random.randn(n) * 0.15)
    volume = np.random.randint(1000, 10000, n).astype(float)
    amount = close * volume

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "amount": amount,
        }
    )


class TestAlpha033:
    """Alpha#033 is simple: rank(-(1 - (open / close)))"""

    def test_returns_series(self, ohlcv_df):
        result = alpha033(ohlcv_df)
        assert isinstance(result, pd.Series)
        assert len(result) == len(ohlcv_df)

    def test_values_between_0_and_1(self, ohlcv_df):
        result = alpha033(ohlcv_df)
        valid = result.dropna()
        assert valid.min() >= 0.0
        assert valid.max() <= 1.0


class TestAlpha012:
    """Alpha#012: sign(delta(volume, 1)) * (-1 * delta(close, 1))"""

    def test_returns_series(self, ohlcv_df):
        result = alpha012(ohlcv_df)
        assert isinstance(result, pd.Series)

    def test_first_value_is_nan(self, ohlcv_df):
        result = alpha012(ohlcv_df)
        assert pd.isna(result.iloc[0])

    def test_logic(self, ohlcv_df):
        result = alpha012(ohlcv_df)
        valid_idx = result.dropna().index[0]
        i = valid_idx
        vol_change = np.sign(ohlcv_df["volume"].iloc[i] - ohlcv_df["volume"].iloc[i - 1])
        price_change = ohlcv_df["close"].iloc[i] - ohlcv_df["close"].iloc[i - 1]
        expected = vol_change * (-1 * price_change)
        assert result.iloc[i] == pytest.approx(expected)


class TestAlpha002:
    """Alpha#002: -1 * ts_corr(rank(delta(log(volume), 2)), rank((close-open)/open), 6)"""

    def test_returns_series(self, ohlcv_df):
        result = alpha002(ohlcv_df)
        assert isinstance(result, pd.Series)

    def test_has_valid_values(self, ohlcv_df):
        result = alpha002(ohlcv_df)
        valid = result.dropna()
        assert len(valid) > 20

    def test_bounded(self, ohlcv_df):
        result = alpha002(ohlcv_df)
        valid = result.dropna()
        assert valid.min() >= -1.0
        assert valid.max() <= 1.0
