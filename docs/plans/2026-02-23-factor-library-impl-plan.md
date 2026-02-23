# Factor Library Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a WorldQuant 101 factor library with operator-based architecture, integrate with backtest engine, and upgrade Agent to quantitative expert persona.

**Architecture:** ~30 pandas-based operators compose into 20 factor functions. YAML catalog provides agent-readable metadata. FactorRegistry discovers factors, FactorEngine computes them. BaseStrategy gains `_get_factor()` for pre-computed factor lookup. Agent system prompt is rewritten with quant domain knowledge.

**Tech Stack:** Python 3.11+, pandas, numpy, PyYAML, pytest

**Design doc:** `docs/plans/2026-02-23-factor-library-design.md`

---

### Task 1: Operators Module — Tests

**Files:**
- Create: `tests/unit/test_operators.py`

**Step 1: Write operator tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_operators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'quantsys.factor'`

**Step 3: Commit**

```bash
git add tests/unit/test_operators.py
git commit -m "test: add operator unit tests for factor library"
```

---

### Task 2: Operators Module — Implementation

**Files:**
- Create: `quantsys/factor/__init__.py`
- Create: `quantsys/factor/operators.py`

**Step 1: Create module init**

```python
"""Factor library for QuantSys."""
```

**Step 2: Implement all operators**

Create `quantsys/factor/operators.py` with all operators as pure functions.

Every function signature: `(x: pd.Series, ...) -> pd.Series`

Implementation guidance for each operator:

| Function | Implementation |
|----------|---------------|
| `delay(x, d)` | `x.shift(d)` |
| `delta(x, d)` | `x.diff(d)` |
| `ts_sum(x, d)` | `x.rolling(d, min_periods=d).sum()` |
| `ts_mean(x, d)` | `x.rolling(d, min_periods=d).mean()` |
| `ts_stddev(x, d)` | `x.rolling(d, min_periods=d).std()` |
| `ts_min(x, d)` | `x.rolling(d, min_periods=d).min()` |
| `ts_max(x, d)` | `x.rolling(d, min_periods=d).max()` |
| `ts_argmin(x, d)` | `x.rolling(d, min_periods=d).apply(lambda s: s.values.argmin(), raw=False)` |
| `ts_argmax(x, d)` | `x.rolling(d, min_periods=d).apply(lambda s: s.values.argmax(), raw=False)` |
| `ts_rank(x, d)` | `x.rolling(d, min_periods=d).apply(lambda s: pd.Series(s).rank().iloc[-1] / len(s), raw=False)` |
| `ts_corr(x, y, d)` | `x.rolling(d, min_periods=d).corr(y)` |
| `ts_cov(x, y, d)` | `x.rolling(d, min_periods=d).cov(y)` |
| `decay_linear(x, d)` | rolling apply with weights `[1, 2, ..., d] / sum(1..d)` |
| `ts_product(x, d)` | `x.rolling(d, min_periods=d).apply(np.prod, raw=True)` |
| `rank(x)` | `x.rank(pct=True)` |
| `scale(x)` | `x / x.abs().sum()` |
| `returns(close)` | `close.pct_change()` |
| `vwap(amount, volume)` | `amount / volume` |
| `adv(volume, d)` | `ts_mean(volume, d)` |
| `signedpower(x, a)` | `sign(x) * abs_op(x).pow(a)` |
| `log_op(x)` | `np.log(x)` |
| `sign(x)` | `np.sign(x)` |
| `abs_op(x)` | `x.abs()` |

All operators must use `min_periods=d` on rolling operations to produce NaN for insufficient data (no partial windows).

**Step 3: Run tests**

Run: `uv run pytest tests/unit/test_operators.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add quantsys/factor/__init__.py quantsys/factor/operators.py
git commit -m "feat: implement factor operators module (30 base operators)"
```

---

### Task 3: YAML Factor Definitions

**Files:**
- Create: `quantsys/factor/definitions/wq101_reversal.yaml`
- Create: `quantsys/factor/definitions/wq101_momentum.yaml`
- Create: `quantsys/factor/definitions/wq101_volatility.yaml`

**Step 1: Create YAML files**

Refer to the WorldQuant 101 Alphas paper for exact formulas: https://arxiv.org/pdf/1601.00991.pdf

Each YAML file groups factors by category. Every factor entry must have all fields from the design doc:
`id`, `name`, `source`, `category`, `formula`, `description`, `data_requirements`, `lookback_window`, `compute_fn`, `tags`, `notes`.

Distribution:
- `wq101_reversal.yaml`: WQ002, WQ003, WQ004, WQ006, WQ014, WQ020, WQ026, WQ033, WQ044, WQ053, WQ101 (11 factors)
- `wq101_momentum.yaml`: WQ008, WQ009, WQ012, WQ017, WQ023, WQ035, WQ041 (7 factors)
- `wq101_volatility.yaml`: WQ028, WQ054 (2 factors)

`compute_fn` format: `"quantsys.factor.library.wq101:alpha{NNN}"` (e.g. `"quantsys.factor.library.wq101:alpha002"`)

**Step 2: Validate YAML syntax**

Run: `uv run python -c "import yaml; [yaml.safe_load(open(f)) for f in __import__('glob').glob('quantsys/factor/definitions/*.yaml')]; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add quantsys/factor/definitions/
git commit -m "feat: add YAML factor definitions for 20 WorldQuant 101 alphas"
```

---

### Task 4: Factor Registry — Tests + Implementation

**Files:**
- Create: `tests/unit/test_factor_registry.py`
- Create: `quantsys/factor/registry.py`

**Step 1: Write registry tests**

```python
"""Tests for factor registry."""

import pytest

from quantsys.factor.registry import FactorMeta, FactorRegistry


@pytest.fixture
def registry():
    r = FactorRegistry()
    r.discover()
    return r


class TestFactorRegistry:
    def test_discover_loads_factors(self, registry):
        factors = registry.list_factors()
        assert len(factors) == 20

    def test_get_existing_factor(self, registry):
        meta = registry.get("WQ002")
        assert meta is not None
        assert meta.name == "Alpha#002"
        assert meta.category == "reversal"
        assert "close" in meta.data_requirements

    def test_get_nonexistent_factor(self, registry):
        assert registry.get("NONEXIST") is None

    def test_list_by_category(self, registry):
        momentum = registry.list_factors(category="momentum")
        assert len(momentum) == 7
        assert all(f.category == "momentum" for f in momentum)

    def test_search(self, registry):
        results = registry.search("volume")
        assert len(results) > 0

    def test_get_summary(self, registry):
        summary = registry.get_summary()
        assert "WQ002" in summary
        assert "reversal" in summary

    def test_get_detail(self, registry):
        detail = registry.get_detail(["WQ002", "WQ017"])
        assert "formula" in detail
        assert "compute_fn" in detail
        assert "WQ002" in detail
        assert "WQ017" in detail

    def test_compute_fn_resolvable(self, registry):
        meta = registry.get("WQ002")
        module_path, func_name = meta.compute_fn.rsplit(":", 1)
        import importlib
        mod = importlib.import_module(module_path)
        assert hasattr(mod, func_name)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_factor_registry.py -v`
Expected: FAIL

**Step 3: Implement FactorRegistry**

`quantsys/factor/registry.py`:

- `FactorMeta`: dataclass with all YAML fields
- `FactorRegistry.__init__()`: empty dict
- `discover()`: scan `quantsys/factor/definitions/*.yaml` using `importlib.resources` or `Path(__file__).parent / "definitions"`, parse with `yaml.safe_load`, create `FactorMeta` for each entry
- `get(factor_id)`: dict lookup, return `None` if missing
- `list_factors(category=None)`: filter by category if provided
- `search(query)`: case-insensitive substring match on name, description, tags
- `get_summary()`: format Level 2 string — `"[{category}] {id}: {name} - {description}"` per factor
- `get_detail(factor_ids)`: format Level 3 string — full YAML-like output of selected factors

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_factor_registry.py -v`
Expected: ALL PASS (except `test_compute_fn_resolvable` — that will pass after Task 5)

**Step 5: Commit**

```bash
git add tests/unit/test_factor_registry.py quantsys/factor/registry.py
git commit -m "feat: implement factor registry with YAML discovery"
```

---

### Task 5: Factor Library (wq101.py) — Tests + Implementation

**Files:**
- Create: `tests/unit/test_wq101.py`
- Create: `quantsys/factor/library/__init__.py`
- Create: `quantsys/factor/library/wq101.py`
- Create: `quantsys/factor/library/classic.py` (placeholder)

**Step 1: Write factor tests**

Test 3 representative factors (simple, medium, complex) with known data:

```python
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

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
    })


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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_wq101.py -v`
Expected: FAIL

**Step 3: Implement wq101.py**

Every alpha function follows the same signature:

```python
def alpha{NNN}(df: pd.DataFrame) -> pd.Series:
```

Where `df` contains columns: `open`, `high`, `low`, `close`, `volume`, `amount`.

Implement all 20 factors using operators from `quantsys.factor.operators`. Reference the WorldQuant 101 paper for exact formulas. Key factors:

| Function | Formula |
|----------|---------|
| `alpha002` | `-1 * ts_corr(rank(delta(log_op(volume), 2)), rank((close - open) / open), 6)` |
| `alpha003` | `-1 * ts_corr(rank(open), rank(volume), 10)` |
| `alpha004` | `-1 * ts_rank(rank(low), 9)` |
| `alpha006` | `-1 * ts_corr(open, volume, 10)` |
| `alpha008` | `-1 * rank(ts_sum(open, 5) * ts_sum(returns, 5) - delay(ts_sum(open, 5) * ts_sum(returns, 5), 10))` |
| `alpha009` | Conditional: if `ts_min(delta(close,1),5) > 0` then `delta(close,1)`, elif `ts_max(delta(close,1),5) < 0` then `delta(close,1)`, else `-1*delta(close,1)` |
| `alpha012` | `sign(delta(volume, 1)) * (-1 * delta(close, 1))` |
| `alpha014` | `-1 * rank(delta(returns, 3)) * ts_corr(open, volume, 10)` |
| `alpha017` | `-1 * rank(ts_rank(close, 10)) * rank(delta(delta(close, 1), 1)) * rank(ts_rank(volume / adv(volume, 20), 5))` |
| `alpha020` | `-1 * rank(open - delay(high, 1)) * rank(open - delay(close, 1)) * rank(open - delay(low, 1))` |
| `alpha023` | Conditional on `ts_mean(high, 20)`: if `< high` then `-1 * delta(high, 2)` else `0` |
| `alpha026` | `-1 * ts_max(ts_corr(ts_rank(volume, 5), ts_rank(high, 5), 5), 3)` |
| `alpha028` | `scale(ts_corr(adv(volume, 20), low, 5) + (high + low) / 2 - close)` |
| `alpha033` | `rank(-(1 - (open / close)))` |
| `alpha035` | `ts_rank(volume, 32) * (1 - ts_rank(close + high - low, 16)) * (1 - ts_rank(returns, 32))` |
| `alpha041` | `signedpower(high * low, 0.5) - vwap(amount, volume)` |
| `alpha044` | `-1 * ts_corr(high, rank(volume), 5)` |
| `alpha053` | `-1 * delta((close - low - (high - close)) / (close - low + 1e-8), 9)` |
| `alpha054` | `-1 * (low - close) * signedpower(open, 5) / ((low - high) * signedpower(close, 5) + 1e-8)` |
| `alpha101` | `(close - open) / (high - low + 1e-8)` |

Also create `quantsys/factor/library/classic.py` as a placeholder:

```python
"""Classic academic factors (Amihud, Fama-French, etc.) — placeholder for future."""
```

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_wq101.py -v`
Expected: ALL PASS

**Step 5: Run full registry test (compute_fn now resolvable)**

Run: `uv run pytest tests/unit/test_factor_registry.py::TestFactorRegistry::test_compute_fn_resolvable -v`
Expected: PASS

**Step 6: Commit**

```bash
git add quantsys/factor/library/ tests/unit/test_wq101.py
git commit -m "feat: implement 20 WorldQuant 101 factor functions"
```

---

### Task 6: Factor Engine — Tests + Implementation

**Files:**
- Create: `tests/unit/test_factor_engine.py`
- Create: `quantsys/factor/engine.py`

**Step 1: Write engine tests**

```python
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

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="B"),
        "symbol": "000001.SZ",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
    })


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
        assert "close" in result.columns  # original columns preserved

    def test_compute_unknown_factor(self, engine, ohlcv_df):
        with pytest.raises(KeyError):
            engine.compute("NONEXIST", ohlcv_df)

    def test_validate_data_success(self, engine, ohlcv_df):
        assert engine.validate_data("WQ002", ohlcv_df) is True

    def test_validate_data_missing_column(self, engine, ohlcv_df):
        df_no_volume = ohlcv_df.drop(columns=["volume"])
        assert engine.validate_data("WQ002", df_no_volume) is False

    def test_validate_data_insufficient_rows(self, engine):
        short_df = pd.DataFrame({
            "open": [1.0], "high": [1.0], "low": [1.0],
            "close": [1.0], "volume": [100.0], "amount": [100.0],
        })
        assert engine.validate_data("WQ002", short_df) is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_factor_engine.py -v`
Expected: FAIL

**Step 3: Implement FactorEngine**

`quantsys/factor/engine.py`:

- `__init__(registry)`: store registry
- `compute(factor_id, df)`: look up FactorMeta, resolve `compute_fn` string to callable via `importlib.import_module` + `getattr`, call it with df, return Series
- `compute_batch(factor_ids, df)`: call `compute()` for each, add as `factor_{id}` columns to a copy of df, return enriched DataFrame
- `validate_data(factor_id, df)`: check `data_requirements` columns exist and `len(df) >= lookback_window`

Cache resolved callables in a dict to avoid repeated `importlib` calls.

**Step 4: Run tests**

Run: `uv run pytest tests/unit/test_factor_engine.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add tests/unit/test_factor_engine.py quantsys/factor/engine.py
git commit -m "feat: implement factor computation engine"
```

---

### Task 7: BaseStrategy Factor Support

**Files:**
- Modify: `quantsys/strategy/base.py`
- Create: `tests/unit/test_strategy_factors.py`

**Step 1: Write test**

```python
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
        strategy.factor_data = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "factor_WQ002": [0.1, 0.6, 0.8],
            "factor_WQ033": [0.5, 0.3, 0.7],
        })
        bar = BarEvent(
            timestamp=ts, symbol="000001.SZ",
            open=10.0, high=10.5, low=9.5, close=10.2,
            volume=1000, amount=10200.0,
        )
        assert strategy._get_factor(bar, "WQ002") == pytest.approx(0.8)
        assert strategy._get_factor(bar, "WQ033") == pytest.approx(0.7)

    def test_get_factor_returns_none_without_data(self):
        strategy = DummyFactorStrategy()
        bar = BarEvent(
            timestamp=pd.Timestamp("2024-01-01"), symbol="000001.SZ",
            open=10.0, high=10.5, low=9.5, close=10.2,
            volume=1000, amount=10200.0,
        )
        assert strategy._get_factor(bar, "WQ002") is None

    def test_get_factor_returns_none_for_missing_timestamp(self):
        strategy = DummyFactorStrategy()
        strategy.factor_data = pd.DataFrame({
            "timestamp": pd.to_datetime(["2024-01-01"]),
            "factor_WQ002": [0.5],
        })
        bar = BarEvent(
            timestamp=pd.Timestamp("2024-06-01"), symbol="000001.SZ",
            open=10.0, high=10.5, low=9.5, close=10.2,
            volume=1000, amount=10200.0,
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
```

**Step 2: Run test to verify fail**

Run: `uv run pytest tests/unit/test_strategy_factors.py -v`
Expected: FAIL — `AttributeError: 'DummyFactorStrategy' object has no attribute 'required_factors'`

**Step 3: Modify BaseStrategy**

Add to `quantsys/strategy/base.py`:
- Class attribute: `required_factors: List[str] = []`
- Instance attribute in `__init__`: `self.factor_data: Optional[pd.DataFrame] = None`
- Method `_get_factor(self, bar: BarEvent, factor_id: str) -> Optional[float]`: timestamp lookup in `factor_data`

Add `import pandas as pd` to imports. Add `List` to typing imports.

**Step 4: Run test**

Run: `uv run pytest tests/unit/test_strategy_factors.py -v`
Expected: ALL PASS

**Step 5: Run existing strategy tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add quantsys/strategy/base.py tests/unit/test_strategy_factors.py
git commit -m "feat: add factor data support to BaseStrategy"
```

---

### Task 8: BacktestEngine Factor Injection

**Files:**
- Modify: `quantsys/backtest/engine.py`

**Step 1: Add factor injection to run()**

In `BacktestEngine.run()`, after `data = self._load_data()` and before `self.strategy.on_start(...)`, add:

```python
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
```

**Step 2: Run existing backtest tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS (no regressions — existing strategies have empty `required_factors`)

**Step 3: Commit**

```bash
git add quantsys/backtest/engine.py
git commit -m "feat: inject pre-computed factor data into strategy at backtest start"
```

---

### Task 9: Agent System Prompt Upgrade

**Files:**
- Modify: `quantsys/agent/core.py`

**Step 1: Replace SYSTEM_PROMPT**

Replace the existing `SYSTEM_PROMPT` class attribute in `Agent` with:

```python
SYSTEM_PROMPT = """You are QuantSys Agent — a senior quantitative analyst and trading system expert \
specializing in A-share (China) markets.

## Identity & Expertise

You have deep knowledge in:
- Factor investing: WorldQuant 101 alphas, Fama-French factors, Barra risk model concepts
- Technical analysis: price-volume patterns, momentum, mean-reversion, volatility regimes
- A-share specifics: T+1 settlement, 10% daily price limit (20% for ChiNext/STAR), \
lot size 100 shares, stamp duty 0.05% on sells, transfer fee 0.001%, commission ~0.03% (min 5 yuan)
- Backtest methodology: lookahead bias prevention, survivorship bias, overfitting risks, \
walk-forward validation, out-of-sample testing
- Portfolio construction: position sizing, risk budgeting, sector diversification

## Behavior Guidelines

- Be precise with numbers: returns as percentages, Sharpe to 2 decimals, drawdown as percentage
- Always warn about overfitting when optimization results look too good (Sharpe > 3, etc.)
- Suggest benchmark comparison (CSI 300 / CSI 500) when presenting backtest results
- Prefer simple, robust strategies over complex models — complexity must justify itself
- Proactively check data quality and coverage before backtesting
- Communicate in the user's language (Chinese or English)

## Available Commands
{commands}

## Workflow

1. Understand intent: research, backtest, generate strategy, factor analysis, or general question
2. Select the appropriate skill/command
3. Gather required parameters — ask if anything is missing
4. Execute and present results with actionable interpretation
5. Suggest logical next steps (optimize? different factors? compare with benchmark?)"""
```

**Step 2: Verify no syntax errors**

Run: `uv run python -c "from quantsys.agent.core import Agent; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add quantsys/agent/core.py
git commit -m "feat: upgrade agent system prompt to quantitative expert persona"
```

---

### Task 10: /factor Skill

**Files:**
- Create: `quantsys/skills/factor_analysis/SKILL.md`

**Step 1: Create skill file**

```markdown
---
name: "因子分析"
description: "浏览、检索和使用量化因子库（WorldQuant 101等），支持因子计算和因子策略生成"
commands:
  - /factor
---

## 使用说明

当用户涉及因子相关操作时，加载因子注册表并提供以下能力：

### 子命令

- `/factor list [类别]` — 展示所有或按类别筛选的因子列表
- `/factor search <关键词>` — 按名称、描述、标签搜索因子
- `/factor show <ID>` — 展示因子完整定义（公式、参数、数据要求）
- `/factor compute <ID> --symbol <代码> [--start DATE] [--end DATE]` — 计算因子值
- `/factor strategy <ID1> <ID2> ...` — 基于选定因子生成组合策略

### 使用因子注册表

```python
from quantsys.factor.registry import FactorRegistry

registry = FactorRegistry()
registry.discover()

# Level 2: 因子摘要
summary = registry.get_summary()

# Level 3: 选定因子详情
detail = registry.get_detail(["WQ002", "WQ017"])
```

### 计算因子值

```python
from quantsys.factor.engine import FactorEngine

engine = FactorEngine(registry)
result = engine.compute("WQ002", df)
batch = engine.compute_batch(["WQ002", "WQ017"], df)
```

### 生成因子策略

当用户要求基于因子生成策略时：
1. 使用 `registry.get_detail()` 获取选定因子的完整定义
2. 将因子定义注入 LLM prompt
3. 生成的策略需声明 `required_factors` 并使用 `self._get_factor(bar, factor_id)`
4. 保存到 `quantsys/strategy/generated/`

### 因子类别

- **momentum** — 动量因子：捕捉价格趋势延续
- **reversal** — 反转因子：捕捉价格均值回归
- **volatility** — 波动率因子：利用波动率变化获利

### 示例

```
/factor list momentum
/factor show WQ002
/factor compute WQ002 --symbol 000001.SZ --start 2024-01-01 --end 2024-12-31
/factor strategy WQ002 WQ017 WQ041
```
```

**Step 2: Verify skill discovery**

Run: `uv run python -c "from quantsys.agent.skill_registry import SkillRegistry; from pathlib import Path; r = SkillRegistry(); r.scan_skills([Path('quantsys/skills')]); print([s.name for s in r.skills.values()])"`
Expected: Output includes `'因子分析'`

**Step 3: Commit**

```bash
git add quantsys/skills/factor_analysis/SKILL.md
git commit -m "feat: add /factor agent skill for factor library interaction"
```

---

### Task 11: Enhance StrategyGenerator for Factors

**Files:**
- Modify: `quantsys/skills/code_generate/generator.py`
- Modify: `quantsys/skills/code_generate/SKILL.md`

**Step 1: Add factor-aware generation to StrategyGenerator**

In `StrategyGenerator`, modify the `generate()` method to accept optional `factor_ids` parameter:

```python
def generate(
    self,
    description: str,
    strategy_type: str = "momentum",
    name: Optional[str] = None,
    factor_ids: Optional[List[str]] = None,
) -> Path:
```

Modify `_generate_with_llm()` to accept `factor_ids` and inject factor context when provided:

```python
def _generate_with_llm(self, description, class_name, strategy_type, factor_ids=None):
    # ... existing base prompt ...

    if factor_ids:
        from quantsys.factor.registry import FactorRegistry
        registry = FactorRegistry()
        registry.discover()
        factor_context = registry.get_detail(factor_ids)

        prompt += f"""

IMPORTANT: This strategy uses pre-computed factors from the QuantSys factor library.
The strategy class MUST declare: required_factors = {factor_ids}
In on_bar(), use self._get_factor(bar, "FACTOR_ID") to get the pre-computed factor value.
_get_factor returns None if data is unavailable — always check for None.

Factor definitions:
{factor_context}
"""

    # ... call LLM ...
```

**Step 2: Update SKILL.md**

Add factor strategy examples to `quantsys/skills/code_generate/SKILL.md`:

```markdown
### 因子策略生成

```
/generate "用WQ002和WQ017的等权组合做多因子策略" --factors WQ002 WQ017
/generate "当WQ002>0.7买入，<0.3卖出" --factors WQ002
```
```

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add quantsys/skills/code_generate/generator.py quantsys/skills/code_generate/SKILL.md
git commit -m "feat: enhance strategy generator with factor context injection"
```

---

### Task 12: Integration Smoke Test

**Files:**
- Create: `tests/unit/test_factor_integration.py`

**Step 1: Write end-to-end integration test**

```python
"""Integration test: factor computation + strategy + backtest engine."""

import numpy as np
import pandas as pd
import pytest

from quantsys.backtest.engine import BacktestEngine
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

        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="B"),
            "symbol": "000001.SZ",
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "amount": amount,
        })

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

        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="B"),
            "symbol": "000001.SZ",
            "open": open_, "high": high, "low": low, "close": close,
            "volume": volume, "amount": amount,
        })

        strategy = SimpleFactorStrategy()
        strategy.factor_data = engine.compute_batch(["WQ033"], df)

        strategy.on_start({"symbols": ["000001.SZ"]})

        signals = []
        for _, row in df.iterrows():
            bar = BarEvent(
                timestamp=row["timestamp"], symbol="000001.SZ",
                open=row["open"], high=row["high"], low=row["low"],
                close=row["close"], volume=int(row["volume"]), amount=row["amount"],
            )
            signal = strategy.on_bar(bar)
            signals.append(signal)

        actions = [s["action"] for s in signals]
        assert "HOLD" in actions
        # The strategy should generate at least some non-HOLD signals
        non_hold = [a for a in actions if a != "HOLD"]
        assert len(non_hold) > 0, "Strategy generated no trading signals"
```

**Step 2: Run integration tests**

Run: `uv run pytest tests/unit/test_factor_integration.py -v`
Expected: ALL PASS

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/unit/test_factor_integration.py
git commit -m "test: add factor library integration tests"
```

---

### Task 13: Final — Lint, Type Check, Update Docs

**Files:**
- Modify: `CLAUDE.md` (add factor module to architecture section)

**Step 1: Run linters**

Run: `uv run black quantsys/factor/ tests/unit/test_operators.py tests/unit/test_wq101.py tests/unit/test_factor_registry.py tests/unit/test_factor_engine.py tests/unit/test_strategy_factors.py tests/unit/test_factor_integration.py`

Run: `uv run ruff check quantsys/factor/ tests/ --fix`

Run: `uv run mypy quantsys/factor/`

Fix any issues found.

**Step 2: Update CLAUDE.md architecture section**

Add under "Architecture":

```markdown
### Factor library (`quantsys/factor/`)
- `operators.py` — ~30 pandas-based operators (rank, delta, ts_corr, etc.) used to compose factors.
- `library/wq101.py` — 20 WorldQuant 101 alpha implementations. Each function takes a DataFrame and returns a Series.
- `definitions/*.yaml` — YAML catalog with factor metadata (name, formula, description, data requirements). Agent reads these for context injection.
- `registry.py` — Discovers YAML definitions, resolves `compute_fn` to Python callables. Provides `get_summary()` (Level 2) and `get_detail()` (Level 3) for progressive agent context.
- `engine.py` — Computes factors: `compute(factor_id, df)` for single, `compute_batch(ids, df)` for multiple. BacktestEngine calls this automatically when strategy declares `required_factors`.
```

**Step 3: Final full test run**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: lint, type annotations, update CLAUDE.md with factor module docs"
```
