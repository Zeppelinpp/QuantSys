"""WorldQuant 101 Alpha implementations.

Each function takes an OHLCV DataFrame (columns: open, high, low, close, volume, amount)
and returns a pd.Series of factor values.

References: Kakushadze, Z. (2016). "101 Formulaic Alphas".
"""

import pandas as pd

from quantsys.factor.operators import (
    adv,
    delay,
    delta,
    log_op,
    rank,
    returns,
    scale,
    sign,
    signedpower,
    ts_corr,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank,
    ts_sum,
    vwap,
)


def alpha002(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_corr(rank(delta(log(volume), 2)), rank((close - open) / open), 6)"""
    x = rank(delta(log_op(df["volume"]), 2))
    y = rank((df["close"] - df["open"]) / df["open"])
    return -1 * ts_corr(x, y, 6)


def alpha003(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_corr(rank(open), rank(volume), 10)"""
    return -1 * ts_corr(rank(df["open"]), rank(df["volume"]), 10)


def alpha004(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_rank(rank(low), 9)"""
    return -1 * ts_rank(rank(df["low"]), 9)


def alpha006(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_corr(open, volume, 10)"""
    return -1 * ts_corr(df["open"], df["volume"], 10)


def alpha008(df: pd.DataFrame) -> pd.Series:
    """-1 * rank(ts_sum(open,5)*ts_sum(returns,5) - delay(ts_sum(open,5)*ts_sum(returns,5), 10))"""
    ret = returns(df["close"])
    product = ts_sum(df["open"], 5) * ts_sum(ret, 5)
    return -1 * rank(product - delay(product, 10))


def alpha009(df: pd.DataFrame) -> pd.Series:
    """Conditional delta(close,1) based on recent trend direction."""
    d = delta(df["close"], 1)
    cond_pos = ts_min(d, 5) > 0
    cond_neg = ts_max(d, 5) < 0
    result = pd.Series(-1 * d, index=df.index)
    result[cond_pos] = d[cond_pos]
    result[cond_neg] = d[cond_neg]
    return result


def alpha012(df: pd.DataFrame) -> pd.Series:
    """sign(delta(volume, 1)) * (-1 * delta(close, 1))"""
    return sign(delta(df["volume"], 1)) * (-1 * delta(df["close"], 1))


def alpha014(df: pd.DataFrame) -> pd.Series:
    """-1 * rank(delta(returns, 3)) * ts_corr(open, volume, 10)"""
    ret = returns(df["close"])
    return -1 * rank(delta(ret, 3)) * ts_corr(df["open"], df["volume"], 10)


def alpha017(df: pd.DataFrame) -> pd.Series:
    """-1 * rank(ts_rank(close,10)) * rank(delta(delta(close,1),1)) * rank(ts_rank(volume/adv(volume,20),5))"""
    a = rank(ts_rank(df["close"], 10))
    b = rank(delta(delta(df["close"], 1), 1))
    c = rank(ts_rank(df["volume"] / adv(df["volume"], 20), 5))
    return -1 * a * b * c


def alpha020(df: pd.DataFrame) -> pd.Series:
    """-1 * rank(open-delay(high,1)) * rank(open-delay(close,1)) * rank(open-delay(low,1))"""
    a = rank(df["open"] - delay(df["high"], 1))
    b = rank(df["open"] - delay(df["close"], 1))
    c = rank(df["open"] - delay(df["low"], 1))
    return -1 * a * b * c


def alpha023(df: pd.DataFrame) -> pd.Series:
    """if ts_mean(high,20) < high: -1*delta(high,2) else 0"""
    cond = ts_mean(df["high"], 20) < df["high"]
    result = pd.Series(0.0, index=df.index)
    result[cond] = -1 * delta(df["high"], 2)[cond]
    return result


def alpha026(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_max(ts_corr(ts_rank(volume,5), ts_rank(high,5), 5), 3)"""
    corr = ts_corr(ts_rank(df["volume"], 5), ts_rank(df["high"], 5), 5)
    return -1 * ts_max(corr, 3)


def alpha028(df: pd.DataFrame) -> pd.Series:
    """scale(ts_corr(adv(volume,20), low, 5) + (high+low)/2 - close)"""
    x = ts_corr(adv(df["volume"], 20), df["low"], 5)
    midpoint = (df["high"] + df["low"]) / 2 - df["close"]
    return scale(x + midpoint)


def alpha033(df: pd.DataFrame) -> pd.Series:
    """rank(-(1 - (open / close)))"""
    return rank(-(1 - (df["open"] / df["close"])))


def alpha035(df: pd.DataFrame) -> pd.Series:
    """ts_rank(volume,32) * (1-ts_rank(close+high-low,16)) * (1-ts_rank(returns,32))"""
    ret = returns(df["close"])
    a = ts_rank(df["volume"], 32)
    b = 1 - ts_rank(df["close"] + df["high"] - df["low"], 16)
    c = 1 - ts_rank(ret, 32)
    return a * b * c


def alpha041(df: pd.DataFrame) -> pd.Series:
    """signedpower(high * low, 0.5) - vwap(amount, volume)"""
    return signedpower(df["high"] * df["low"], 0.5) - vwap(df["amount"], df["volume"])


def alpha044(df: pd.DataFrame) -> pd.Series:
    """-1 * ts_corr(high, rank(volume), 5)"""
    return -1 * ts_corr(df["high"], rank(df["volume"]), 5)


def alpha053(df: pd.DataFrame) -> pd.Series:
    """-1 * delta((close-low-(high-close)) / (close-low+eps), 9)"""
    inner = (df["close"] - df["low"] - (df["high"] - df["close"])) / (
        df["close"] - df["low"] + 1e-8
    )
    return -1 * delta(inner, 9)


def alpha054(df: pd.DataFrame) -> pd.Series:
    """-1 * (low-close) * signedpower(open,5) / ((low-high)*signedpower(close,5) + eps)"""
    numerator = (df["low"] - df["close"]) * signedpower(df["open"], 5)
    denominator = (df["low"] - df["high"]) * signedpower(df["close"], 5) + 1e-8
    return -1 * numerator / denominator


def alpha101(df: pd.DataFrame) -> pd.Series:
    """(close - open) / (high - low + eps)"""
    return (df["close"] - df["open"]) / (df["high"] - df["low"] + 1e-8)
