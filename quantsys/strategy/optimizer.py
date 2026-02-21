"""Strategy parameter optimizer using Bayesian optimization."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger
from skopt import gp_minimize
from skopt.space import Integer, Real, Space

from quantsys.backtest.engine import BacktestEngine
from quantsys.backtest.metrics import BacktestMetrics
from quantsys.config import Settings, get_settings
from quantsys.data.database import Database


@dataclass
class OptimizationResult:
    """Optimization result."""

    strategy_name: str
    best_params: Dict[str, Any]
    best_score: float
    optimization_history: List[Dict]
    n_iterations: int
    duration_seconds: float


class StrategyOptimizer:
    """Bayesian optimizer for strategy parameters."""

    def __init__(
        self,
        strategy_class: type,
        database: Optional[Database] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Initialize optimizer.

        Args:
            strategy_class: Strategy class to optimize
            database: Database instance
            settings: Application settings
        """
        self.strategy_class = strategy_class
        self.db = database
        self.settings = settings or get_settings()

        if self.db is None:
            self.db = Database(self.settings.db_path)

    def optimize(
        self,
        param_space: Dict[str, Tuple[str, Any, Any]],
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        objective: str = "sharpe_ratio",
        n_iterations: int = 50,
        n_initial_points: int = 10,
        initial_cash: float = 1_000_000.0,
    ) -> OptimizationResult:
        """Run Bayesian optimization.

        Args:
            param_space: Parameter space definition
                Format: {"param_name": ("type", min, max)}
                Types: "int", "float"
            start_date: Backtest start date
            end_date: Backtest end date
            symbols: List of symbols
            objective: Metric to maximize ("sharpe_ratio", "total_return", "sortino_ratio")
            n_iterations: Number of optimization iterations
            n_initial_points: Number of random initial points
            initial_cash: Initial cash

        Returns:
            OptimizationResult with best parameters
        """
        start_time = datetime.now()

        # Convert param space to skopt format
        dimensions = self._convert_param_space(param_space)
        param_names = list(param_space.keys())

        logger.info(
            f"Starting optimization: {objective}, {n_iterations} iterations, "
            f"parameter space: {param_space}"
        )

        # Objective function
        def objective_function(x: List) -> float:
            params = {name: value for name, value in zip(param_names, x)}
            score = self._evaluate_params(
                params,
                start_date,
                end_date,
                symbols,
                objective,
                initial_cash,
            )
            # Return negative for minimization
            return -score if score is not None else 0.0

        # Run optimization
        result = gp_minimize(
            objective_function,
            dimensions,
            n_calls=n_iterations,
            n_initial_points=n_initial_points,
            random_state=42,
            verbose=False,
        )

        # Build history
        history = []
        for i in range(len(result.x_iters)):
            params = {name: value for name, value in zip(param_names, result.x_iters[i])}
            history.append({
                "iteration": i,
                "params": params,
                "score": -result.func_vals[i],
            })

        best_params = {name: value for name, value in zip(param_names, result.x)}

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            f"Optimization complete: best {objective}={-result.fun:.4f}, "
            f"params={best_params}"
        )

        return OptimizationResult(
            strategy_name=self.strategy_class.name,
            best_params=best_params,
            best_score=-result.fun,
            optimization_history=history,
            n_iterations=n_iterations,
            duration_seconds=duration,
        )

    def _convert_param_space(
        self, param_space: Dict[str, Tuple[str, Any, Any]]
    ) -> List[Space]:
        """Convert parameter space to skopt dimensions."""
        dimensions = []
        for name, (ptype, min_val, max_val) in param_space.items():
            if ptype == "int":
                dimensions.append(Integer(int(min_val), int(max_val), name=name))
            elif ptype == "float":
                dimensions.append(Real(min_val, max_val, name=name))
            else:
                raise ValueError(f"Unknown parameter type: {ptype}")
        return dimensions

    def _evaluate_params(
        self,
        params: Dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        symbols: List[str],
        objective: str,
        initial_cash: float,
    ) -> Optional[float]:
        """Evaluate a parameter set."""
        try:
            # Create strategy instance
            strategy = self.strategy_class(params=params)

            # Run backtest
            engine = BacktestEngine(
                start_date=start_date,
                end_date=end_date,
                symbols=symbols,
                strategy=strategy,
                initial_cash=initial_cash,
                database=self.db,
            )

            result = engine.run()

            # Return objective value
            metrics = result.metrics
            value = getattr(metrics, objective, None)

            if value is None or np.isnan(value):
                return None

            return float(value)

        except Exception as e:
            logger.warning(f"Evaluation failed for params {params}: {e}")
            return None