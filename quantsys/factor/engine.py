"""Factor computation engine — resolves and runs factor functions."""

import importlib
from typing import Callable, Dict, List

import pandas as pd
from loguru import logger

from .registry import FactorRegistry


class FactorEngine:
    """Computes factors by resolving compute_fn references to Python callables."""

    def __init__(self, registry: FactorRegistry) -> None:
        self._registry = registry
        self._fn_cache: Dict[str, Callable] = {}

    def compute(self, factor_id: str, df: pd.DataFrame) -> pd.Series:
        """Compute a single factor.

        Args:
            factor_id: Factor ID (e.g. "WQ002")
            df: OHLCV DataFrame

        Raises:
            KeyError: If factor_id is not in registry
        """
        meta = self._registry.get(factor_id)
        if meta is None:
            raise KeyError(f"Unknown factor: {factor_id}")

        fn = self._resolve_fn(meta.compute_fn)
        return fn(df)

    def compute_batch(self, factor_ids: List[str], df: pd.DataFrame) -> pd.DataFrame:
        """Compute multiple factors and merge into a copy of df.

        Returns DataFrame with original columns plus factor_{id} columns.
        """
        result = df.copy()
        for fid in factor_ids:
            result[f"factor_{fid}"] = self.compute(fid, df)
        return result

    def validate_data(self, factor_id: str, df: pd.DataFrame) -> bool:
        """Check whether df has the required columns and sufficient rows."""
        meta = self._registry.get(factor_id)
        if meta is None:
            return False

        for col in meta.data_requirements:
            if col not in df.columns:
                logger.debug(f"Missing column '{col}' for factor {factor_id}")
                return False

        if len(df) < meta.lookback_window:
            logger.debug(
                f"Insufficient rows ({len(df)}) for factor {factor_id} "
                f"(needs {meta.lookback_window})"
            )
            return False

        return True

    def _resolve_fn(self, compute_fn: str) -> Callable:  # type: ignore[type-arg]
        """Resolve a 'module.path:func_name' string to a callable."""
        if compute_fn in self._fn_cache:
            return self._fn_cache[compute_fn]

        module_path, func_name = compute_fn.rsplit(":", 1)
        mod = importlib.import_module(module_path)
        fn: Callable = getattr(mod, func_name)  # type: ignore[type-arg]
        self._fn_cache[compute_fn] = fn
        return fn
