"""Paper trading CLI commands."""

import click
from rich.console import Console
from rich.table import Table

from quantsys.config import get_settings
from quantsys.data import Database
from quantsys.paper.manager import AccountManager

console = Console()


@click.group()
def paper() -> None:
    """Paper trading commands."""
    pass


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
@click.option("--cash", "-c", default=1_000_000.0, help="Initial cash")
def create(name: str, cash: float) -> None:
    """Create a new paper trading account."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    try:
        account = manager.create_account(name, cash)
        console.print(f"[green]Created account '{name}' with ${cash:,.2f}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@paper.command()
def list() -> None:
    """List all paper trading accounts."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    accounts = manager.list_accounts()

    if not accounts:
        console.print("[dim]No accounts found.[/dim]")
        return

    table = Table(title="Paper Trading Accounts")
    table.add_column("Name", style="cyan")
    table.add_column("Initial Cash", justify="right")
    table.add_column("Current Cash", justify="right")
    table.add_column("Created")

    for acc in accounts:
        table.add_row(
            acc["name"],
            f"${acc['initial_cash']:,.2f}",
            f"${acc['current_cash']:,.2f}",
            acc["created_at"][:10],
        )

    console.print(table)


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
def status(name: str) -> None:
    """Show account status."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    account = manager.get_account(name)
    if not account:
        console.print(f"[red]Account '{name}' not found[/red]")
        return

    state = account.get_state()

    console.print(f"\n[bold cyan]Account: {name}[/bold cyan]")
    console.print(f"Cash: ${state['cash']:,.2f}")
    console.print(f"Positions Value: ${state['positions_value']:,.2f}")
    console.print(f"Total Value: ${state['total_value']:,.2f}")
    console.print(f"Total Return: {state['total_return']:.2%}")

    if state["positions"]:
        table = Table(title="Positions")
        table.add_column("Symbol", style="cyan")
        table.add_column("Quantity", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Market Price", justify="right")
        table.add_column("Market Value", justify="right")
        table.add_column("Unrealized P&L", justify="right")

        for symbol, pos in state["positions"].items():
            pnl_color = "green" if pos["unrealized_pnl"] >= 0 else "red"
            table.add_row(
                symbol,
                str(pos["quantity"]),
                f"${pos['avg_cost']:.2f}",
                f"${pos['market_price']:.2f}",
                f"${pos['market_value']:,.2f}",
                f"[{pnl_color}]${pos['unrealized_pnl']:,.2f}[/{pnl_color}]",
            )

        console.print(table)


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
@click.option("--limit", "-l", default=20, help="Number of trades to show")
def trades(name: str, limit: int) -> None:
    """Show trade history."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    account = manager.get_account(name)
    if not account:
        console.print(f"[red]Account '{name}' not found[/red]")
        return

    trade_list = manager.get_trades(name, limit)

    if not trade_list:
        console.print("[dim]No trades found.[/dim]")
        return

    table = Table(title=f"Recent Trades - {name}")
    table.add_column("Time", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Side", style="bold")
    table.add_column("Quantity", justify="right")
    table.add_column("Price", justify="right")

    for trade in trade_list:
        side_color = "green" if trade["side"] == "BUY" else "red"
        table.add_row(
            trade["timestamp"][:16],
            trade["symbol"],
            f"[{side_color}]{trade['side']}[/{side_color}]",
            str(trade["quantity"]),
            f"${trade['price']:.2f}",
        )

    console.print(table)


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
@click.confirmation_option(prompt="Are you sure you want to delete this account?")
def delete(name: str) -> None:
    """Delete a paper trading account."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    if manager.delete_account(name):
        console.print(f"[green]Deleted account '{name}'[/green]")
    else:
        console.print(f"[red]Account '{name}' not found[/red]")


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
@click.option("--symbol", "-s", required=True, help="Stock symbol")
@click.option("--quantity", "-q", required=True, type=int, help="Quantity")
@click.option("--price", "-p", required=True, type=float, help="Price")
def buy(name: str, symbol: str, quantity: int, price: float) -> None:
    """Execute a buy order (paper trading)."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    account = manager.get_account(name)
    if not account:
        console.print(f"[red]Account '{name}' not found[/red]")
        return

    # Simple commission calculation
    commission = max(price * quantity * 0.0003, 5.0)

    if account.buy(symbol, quantity, price, commission):
        manager.save_account(account)
        manager.record_trade(account.account_id, symbol, "BUY", quantity, price)
        console.print(f"[green]Bought {quantity} {symbol} @ ${price:.2f}[/green]")
    else:
        console.print("[red]Order failed[/red]")


@paper.command()
@click.option("--name", "-n", required=True, help="Account name")
@click.option("--symbol", "-s", required=True, help="Stock symbol")
@click.option("--quantity", "-q", required=True, type=int, help="Quantity")
@click.option("--price", "-p", required=True, type=float, help="Price")
def sell(name: str, symbol: str, quantity: int, price: float) -> None:
    """Execute a sell order (paper trading)."""
    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    account = manager.get_account(name)
    if not account:
        console.print(f"[red]Account '{name}' not found[/red]")
        return

    # Commission + stamp duty
    value = price * quantity
    commission = max(value * 0.0003, 5.0) + value * 0.0005

    if account.sell(symbol, quantity, price, commission):
        manager.save_account(account)
        manager.record_trade(account.account_id, symbol, "SELL", quantity, price)
        console.print(f"[green]Sold {quantity} {symbol} @ ${price:.2f}[/green]")
    else:
        console.print("[red]Order failed[/red]")
