"""Performance metrics calculation for backtest."""

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class BacktestMetrics:
    """Backtest performance metrics."""

    # Returns
    total_return: float
    annualized_return: float

    # Risk
    volatility: float
    max_drawdown: float
    max_drawdown_duration: int

    # Ratios
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float

    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float

    # Benchmark relative (positive = beat index, negative = lost)
    alpha: Optional[float] = None
    beta: Optional[float] = None
    excess_return: Optional[float] = None
    benchmark_return: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "alpha": self.alpha,
            "beta": self.beta,
            "excess_return": self.excess_return,
            "benchmark_return": self.benchmark_return,
        }


def _detect_periods_per_year(timestamps: List) -> int:
    """Auto-detect data frequency and return annualization factor."""
    if len(timestamps) < 2:
        return 252
    diffs = [
        (timestamps[i + 1] - timestamps[i]).total_seconds()
        for i in range(min(20, len(timestamps) - 1))
    ]
    median_diff = sorted(diffs)[len(diffs) // 2]
    if median_diff > 3600:  # > 1 hour gap → daily data
        return 252
    return 252 * 240  # minute-level


def calculate_metrics(
    equity_curve: List,
    trades: List,
    risk_free_rate: float = 0.03,
    periods_per_year: Optional[int] = None,
    benchmark_returns: Optional[np.ndarray] = None,
) -> BacktestMetrics:
    """Calculate performance metrics from equity curve and trades.

    Args:
        equity_curve: List of PortfolioState objects
        trades: List of FillEvent objects
        risk_free_rate: Annual risk-free rate
        periods_per_year: Override for annualization (auto-detected if None)
        benchmark_returns: Benchmark daily returns for alpha/beta/excess calc

    Returns:
        BacktestMetrics object
    """
    if len(equity_curve) < 2:
        raise ValueError("Need at least 2 data points in equity curve")

    values = np.array([state.total_value for state in equity_curve])
    timestamps = [state.timestamp for state in equity_curve]

    if periods_per_year is None:
        periods_per_year = _detect_periods_per_year(timestamps)

    returns = np.diff(values) / values[:-1]

    # Total return
    total_return = (values[-1] - values[0]) / values[0]

    # Annualized return
    n_periods = len(returns)
    annualized_return = (1 + total_return) ** (periods_per_year / n_periods) - 1

    # Volatility (annualized)
    volatility = np.std(returns) * np.sqrt(periods_per_year)

    # Sharpe ratio
    excess_returns = returns - risk_free_rate / periods_per_year
    sharpe_ratio = (
        np.mean(excess_returns) / np.std(returns) * np.sqrt(periods_per_year)
        if np.std(returns) > 0
        else 0.0
    )

    # Sortino ratio
    downside_returns = returns[returns < 0]
    downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 0.0
    sortino_ratio = (
        np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year)
        if downside_std > 0
        else 0.0
    )

    # Maximum drawdown
    cummax = np.maximum.accumulate(values)
    drawdowns = (values - cummax) / cummax
    max_drawdown = float(np.min(drawdowns))

    # Max drawdown duration
    max_dd_duration = 0
    current_dd_duration = 0
    for i in range(len(values)):
        if values[i] < cummax[i]:
            current_dd_duration += 1
            max_dd_duration = max(max_dd_duration, current_dd_duration)
        else:
            current_dd_duration = 0

    # Calmar ratio
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # Trade P&L: track cost basis per symbol to compute realized profit
    cost_basis: Dict[str, dict] = {}
    trade_pnl: List[float] = []
    for trade in trades:
        sym = trade.symbol
        if trade.side == "BUY":
            if sym not in cost_basis:
                cost_basis[sym] = {"qty": 0, "total_cost": 0.0}
            info = cost_basis[sym]
            info["qty"] += trade.quantity
            info["total_cost"] += trade.total_cost
        elif trade.side == "SELL":
            info = cost_basis.get(sym)
            if info and info["qty"] > 0:
                avg_cost = info["total_cost"] / info["qty"]
                pnl = (trade.fill_price - avg_cost) * trade.quantity - trade.commission
                trade_pnl.append(pnl)
                info["qty"] -= trade.quantity
                info["total_cost"] = info["qty"] * avg_cost

    total_trades = len(trades)
    winning_trades = sum(1 for pnl in trade_pnl if pnl > 0)
    losing_trades = sum(1 for pnl in trade_pnl if pnl <= 0)
    sell_count = len(trade_pnl)
    win_rate = winning_trades / sell_count if sell_count > 0 else 0.0

    wins = [pnl for pnl in trade_pnl if pnl > 0]
    losses = [pnl for pnl in trade_pnl if pnl <= 0]
    avg_win = float(np.mean(wins)) if wins else 0.0
    avg_loss = float(np.mean(losses)) if losses else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Benchmark comparison
    alpha = None
    beta = None
    excess_return = None
    benchmark_return = None

    if benchmark_returns is not None and len(benchmark_returns) > 0:
        benchmark_total = float(np.prod(1 + benchmark_returns) - 1)
        benchmark_return = benchmark_total
        excess_return = total_return - benchmark_total

        min_len = min(len(returns), len(benchmark_returns))
        if min_len > 1:
            alpha, beta = calculate_alpha_beta(returns[-min_len:], benchmark_returns[-min_len:])

    return BacktestMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        volatility=volatility,
        max_drawdown=max_drawdown,
        max_drawdown_duration=max_dd_duration,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        alpha=alpha,
        beta=beta,
        excess_return=excess_return,
        benchmark_return=benchmark_return,
    )


def calculate_alpha_beta(
    returns: np.ndarray,
    benchmark_returns: np.ndarray,
) -> tuple:
    """Calculate alpha and beta relative to benchmark.

    Args:
        returns: Strategy returns
        benchmark_returns: Benchmark returns

    Returns:
        Tuple of (alpha, beta)
    """
    # Align arrays
    min_len = min(len(returns), len(benchmark_returns))
    returns = returns[-min_len:]
    benchmark_returns = benchmark_returns[-min_len:]

    # Calculate beta
    covariance = np.cov(returns, benchmark_returns)[0, 1]
    benchmark_variance = np.var(benchmark_returns)
    beta = covariance / benchmark_variance if benchmark_variance > 0 else 0

    # Calculate alpha
    alpha = np.mean(returns) - beta * np.mean(benchmark_returns)

    return alpha, beta
