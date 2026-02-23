"""Backtest CLI commands."""

from datetime import datetime
from pathlib import Path

import click
from loguru import logger
from rich.console import Console
from rich.table import Table

from quantsys.backtest.engine import BacktestEngine
from quantsys.backtest.execution import ExecutionConfig
from quantsys.config import get_settings
from quantsys.data import Database
from quantsys.strategy.loader import StrategyLoader

console = Console()


@click.group()
def backtest() -> None:
    """Backtest commands."""
    pass


@backtest.command()
@click.argument("strategy_file", type=click.Path(exists=True))
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--symbols", "-s", required=True, help="Comma-separated symbols (e.g., 000001.SZ)")
@click.option("--cash", default=1_000_000.0, help="Initial cash")
@click.option("--commission", default=0.0003, help="Commission rate")
@click.option("--output", "-o", help="Output file for results (JSON)")
@click.option("--benchmark", "-b", default="000300", help="Benchmark index code (default: 000300 CSI300)")
def run(
    strategy_file: str,
    start: str,
    end: str,
    symbols: str,
    cash: float,
    commission: float,
    output: str,
    benchmark: str,
) -> None:
    """Run backtest for a strategy."""
    settings = get_settings()

    # Parse dates
    start_date = datetime.strptime(start, "%Y-%m-%d")
    end_date = datetime.strptime(end, "%Y-%m-%d")

    # Parse symbols
    symbol_list = [s.strip() for s in symbols.split(",")]

    # Load strategy
    try:
        strategy = StrategyLoader.create_strategy(strategy_file)
    except Exception as e:
        raise click.ClickException(f"Failed to load strategy: {e}")

    # Create database connection
    db = Database(settings.db_path)

    # Create execution config
    exec_config = ExecutionConfig(commission_rate=commission)

    # Create and run engine
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        symbols=symbol_list,
        strategy=strategy,
        initial_cash=cash,
        database=db,
        execution_config=exec_config,
        benchmark_symbol=benchmark,
    )

    try:
        result = engine.run()
    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        raise click.ClickException(str(e))

    # Display results
    _display_results(result)

    # Save results if output specified
    if output:
        import json

        with open(output, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        console.print(f"\n[green]Results saved to {output}[/green]")


def _display_results(result) -> None:
    """Display backtest results in a nice format."""
    console.print("\n[bold cyan]Backtest Results[/bold cyan]")
    console.print(f"Strategy: {result.strategy_name}")
    console.print(f"Period: {result.start_date.date()} to {result.end_date.date()}")
    console.print(f"Symbols: {', '.join(result.symbols)}")

    # Metrics table
    table = Table(title="Performance Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    m = result.metrics
    table.add_row("Total Return", f"{m.total_return:.2%}")
    table.add_row("Annualized Return", f"{m.annualized_return:.2%}")
    table.add_row("Volatility", f"{m.volatility:.2%}")
    table.add_row("Sharpe Ratio", f"{m.sharpe_ratio:.2f}")
    table.add_row("Sortino Ratio", f"{m.sortino_ratio:.2f}")
    table.add_row("Max Drawdown", f"{m.max_drawdown:.2%}")
    table.add_row("Max DD Duration", f"{m.max_drawdown_duration} periods")
    table.add_row("Total Trades", str(m.total_trades))
    table.add_row("Win Rate", f"{m.win_rate:.1%}")
    table.add_row("Profit Factor", f"{m.profit_factor:.2f}")

    if m.benchmark_return is not None:
        table.add_row("", "")
        table.add_row("Benchmark Return", f"{m.benchmark_return:.2%}")
        excess = m.excess_return or 0.0
        style = "green" if excess >= 0 else "red"
        sign = "+" if excess >= 0 else ""
        table.add_row("Excess Return", f"[{style}]{sign}{excess:.2%}[/{style}]")
        if m.alpha is not None:
            table.add_row("Alpha", f"{m.alpha:.4f}")
        if m.beta is not None:
            table.add_row("Beta", f"{m.beta:.2f}")

    console.print(table)
