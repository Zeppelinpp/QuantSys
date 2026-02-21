"""Strategy loader for dynamic strategy loading."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Type

from loguru import logger

from .base import BaseStrategy


class StrategyLoader:
    """Load strategies from Python files."""

    @staticmethod
    def load_from_file(file_path: str) -> Type[BaseStrategy]:
        """Load a strategy class from a Python file.

        Args:
            file_path: Path to the strategy Python file

        Returns:
            Strategy class
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Strategy file not found: {file_path}")

        # Load module
        spec = importlib.util.spec_from_file_location("strategy_module", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules["strategy_module"] = module
        spec.loader.exec_module(module)

        # Find strategy class
        strategy_class = None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
            ):
                strategy_class = obj
                break

        if strategy_class is None:
            raise ValueError(f"No strategy class found in {file_path}")

        logger.info(f"Loaded strategy: {strategy_class.__name__} from {file_path}")
        return strategy_class

    @staticmethod
    def load_from_module(module_name: str, class_name: str) -> Type[BaseStrategy]:
        """Load a strategy class from an installed module.

        Args:
            module_name: Module name
            class_name: Class name

        Returns:
            Strategy class
        """
        module = importlib.import_module(module_name)
        strategy_class = getattr(module, class_name)

        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"{class_name} is not a subclass of BaseStrategy")

        return strategy_class

    @staticmethod
    def create_strategy(
        file_path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> BaseStrategy:
        """Load and instantiate a strategy.

        Args:
            file_path: Path to strategy file
            params: Strategy parameters

        Returns:
            Strategy instance
        """
        strategy_class = StrategyLoader.load_from_file(file_path)
        return strategy_class(params)
