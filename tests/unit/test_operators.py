"""Tests for factor operators."""

import numpy as np
import pandas as pd
import pytest

from quantsys.factor.operators import (
    abs_op,
    adv,
    decay_linear,
    delay,
    delta,
    log_op,
    rank,
    returns,
    scale,
    sign,
    signedpower,
    ts_argmax,
    ts_argmin,
    ts_corr,
    ts_cov,
    ts_max,
    ts_mean,
    ts_min,
    ts_product,
    ts_rank,
    ts_stddev,
    ts_sum,
    vwap,
)


@pytest.fixture
def sample_series():
    return pd.Series([10.0, 11.0, 9.0, 12.0, 8.0, 13.0, 7.0, 14.0, 6.0, 15.0])


@pytest.fixture
def sample_volume():
    return pd.Series([100, 150, 120, 200, 80, 180, 90, 210, 70, 190], dtype=float)


class TestTimeSeriesOperators:
    def test_delay(self, sample_series):
        result = delay(sample_series, 2)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 10.0
        assert result.iloc[4] == 9.0

    def test_delta(self, sample_series):
        result = delta(sample_series, 1)
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == 1.0  # 11 - 10
        assert result.iloc[2] == -2.0  # 9 - 11

    def test_ts_sum(self, sample_series):
        result = ts_sum(sample_series, 3)
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(30.0)  # 10+11+9

    def test_ts_mean(self, sample_series):
        result = ts_mean(sample_series, 3)
        assert result.iloc[2] == pytest.approx(10.0)

    def test_ts_stddev(self, sample_series):
        result = ts_stddev(sample_series, 3)
        assert result.iloc[2] > 0

    def test_ts_min(self, sample_series):
        result = ts_min(sample_series, 3)
        assert result.iloc[2] == 9.0
        assert result.iloc[4] == 8.0

    def test_ts_max(self, sample_series):
        result = ts_max(sample_series, 3)
        assert result.iloc[2] == 11.0
        assert result.iloc[4] == 12.0

    def test_ts_argmin(self, sample_series):
        result = ts_argmin(sample_series, 3)
        assert not pd.isna(result.iloc[2])

    def test_ts_argmax(self, sample_series):
        result = ts_argmax(sample_series, 3)
        assert not pd.isna(result.iloc[2])

    def test_ts_rank(self, sample_series):
        result = ts_rank(sample_series, 5)
        assert result.iloc[4] >= 0.0
        assert result.iloc[4] <= 1.0

    def test_ts_corr(self, sample_series, sample_volume):
        result = ts_corr(sample_series, sample_volume, 5)
        valid = result.dropna()
        assert len(valid) > 0
        assert all(-1 <= v <= 1 for v in valid)

    def test_ts_cov(self, sample_series, sample_volume):
        result = ts_cov(sample_series, sample_volume, 5)
        assert len(result.dropna()) > 0

    def test_decay_linear(self, sample_series):
        result = decay_linear(sample_series, 3)
        assert len(result.dropna()) > 0

    def test_ts_product(self, sample_series):
        small = pd.Series([1.01, 1.02, 0.99, 1.03, 0.98])
        result = ts_product(small, 3)
        assert result.iloc[2] == pytest.approx(1.01 * 1.02 * 0.99)


class TestCrossSectionalOperators:
    def test_rank(self, sample_series):
        result = rank(sample_series)
        assert result.min() >= 0.0
        assert result.max() <= 1.0

    def test_scale(self, sample_series):
        result = scale(sample_series)
        assert result.abs().sum() == pytest.approx(1.0)


class TestHelperOperators:
    def test_returns(self):
        prices = pd.Series([100.0, 102.0, 101.0, 105.0])
        result = returns(prices)
        assert result.iloc[1] == pytest.approx(0.02)
        assert result.iloc[2] == pytest.approx(-1.0 / 102.0, rel=1e-6)

    def test_vwap(self):
        amount = pd.Series([1000.0, 2000.0, 1500.0])
        volume = pd.Series([100.0, 200.0, 150.0])
        result = vwap(amount, volume)
        assert all(result == 10.0)

    def test_adv(self, sample_volume):
        result = adv(sample_volume, 5)
        assert result.iloc[4] == pytest.approx(130.0)  # mean(100,150,120,200,80)

    def test_signedpower(self):
        x = pd.Series([-2.0, -1.0, 0.0, 1.0, 2.0])
        result = signedpower(x, 2)
        assert result.iloc[0] == pytest.approx(-4.0)
        assert result.iloc[4] == pytest.approx(4.0)

    def test_log_op(self):
        x = pd.Series([1.0, np.e, np.e**2])
        result = log_op(x)
        assert result.iloc[0] == pytest.approx(0.0)
        assert result.iloc[1] == pytest.approx(1.0)

    def test_sign(self):
        x = pd.Series([-5.0, 0.0, 3.0])
        result = sign(x)
        assert list(result) == [-1.0, 0.0, 1.0]

    def test_abs_op(self):
        x = pd.Series([-3.0, 0.0, 5.0])
        result = abs_op(x)
        assert list(result) == [3.0, 0.0, 5.0]
