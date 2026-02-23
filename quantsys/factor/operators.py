"""Factor operators — pandas-based building blocks for alpha expressions.

Follows the operator taxonomy from WorldQuant 101 Alphas paper.
All operators are pure functions: (pd.Series, ...) -> pd.Series.
"""

import numpy as np
import pandas as pd

# --- Time-series operators ---


def delay(x: pd.Series, d: int) -> pd.Series:
    """Value of x d days ago."""
    return x.shift(d)


def delta(x: pd.Series, d: int) -> pd.Series:
    """Today's value minus d days ago: x - delay(x, d)."""
    return x.diff(d)


def ts_sum(x: pd.Series, d: int) -> pd.Series:
    """Rolling sum over past d days."""
    return x.rolling(d, min_periods=d).sum()


def ts_mean(x: pd.Series, d: int) -> pd.Series:
    """Rolling mean over past d days."""
    return x.rolling(d, min_periods=d).mean()


def ts_stddev(x: pd.Series, d: int) -> pd.Series:
    """Rolling standard deviation over past d days."""
    return x.rolling(d, min_periods=d).std()


def ts_min(x: pd.Series, d: int) -> pd.Series:
    """Rolling minimum over past d days."""
    return x.rolling(d, min_periods=d).min()


def ts_max(x: pd.Series, d: int) -> pd.Series:
    """Rolling maximum over past d days."""
    return x.rolling(d, min_periods=d).max()


def ts_argmin(x: pd.Series, d: int) -> pd.Series:
    """Position of rolling minimum within the window (0-indexed from window start)."""
    return x.rolling(d, min_periods=d).apply(lambda s: s.values.argmin(), raw=False)


def ts_argmax(x: pd.Series, d: int) -> pd.Series:
    """Position of rolling maximum within the window (0-indexed from window start)."""
    return x.rolling(d, min_periods=d).apply(lambda s: s.values.argmax(), raw=False)


def ts_rank(x: pd.Series, d: int) -> pd.Series:
    """Percentile rank of current value within rolling window."""
    return x.rolling(d, min_periods=d).apply(
        lambda s: pd.Series(s).rank().iloc[-1] / len(s), raw=False
    )


def ts_corr(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    """Rolling Pearson correlation between x and y."""
    return x.rolling(d, min_periods=d).corr(y)


def ts_cov(x: pd.Series, y: pd.Series, d: int) -> pd.Series:
    """Rolling covariance between x and y."""
    return x.rolling(d, min_periods=d).cov(y)


def decay_linear(x: pd.Series, d: int) -> pd.Series:
    """Linearly weighted moving average: weights [1, 2, ..., d] / sum(1..d)."""
    weights = np.arange(1, d + 1, dtype=float)
    weights /= weights.sum()

    def _weighted_mean(s: np.ndarray) -> float:
        return float(np.dot(s, weights))

    return x.rolling(d, min_periods=d).apply(_weighted_mean, raw=True)


def ts_product(x: pd.Series, d: int) -> pd.Series:
    """Rolling product over past d days."""
    return x.rolling(d, min_periods=d).apply(np.prod, raw=True)


# --- Cross-sectional operators ---


def rank(x: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank (0 to 1)."""
    return x.rank(pct=True)


def scale(x: pd.Series) -> pd.Series:
    """Rescale so that sum of absolute values equals 1."""
    abs_sum = x.abs().sum()
    if abs_sum == 0:
        return x * 0.0
    return x / abs_sum


# --- Helper / element-wise operators ---


def returns(close: pd.Series) -> pd.Series:
    """Simple percentage returns."""
    return close.pct_change()


def vwap(amount: pd.Series, volume: pd.Series) -> pd.Series:
    """Volume-weighted average price."""
    return amount / volume


def adv(volume: pd.Series, d: int) -> pd.Series:
    """Average daily volume over d days."""
    return ts_mean(volume, d)


def signedpower(x: pd.Series, a: float) -> pd.Series:
    """sign(x) * |x|^a."""
    return sign(x) * abs_op(x).pow(a)


def log_op(x: pd.Series) -> pd.Series:
    """Natural logarithm."""
    return np.log(x)


def sign(x: pd.Series) -> pd.Series:
    """Sign function: -1, 0, or 1."""
    return np.sign(x)


def abs_op(x: pd.Series) -> pd.Series:
    """Absolute value."""
    return x.abs()
