"""Data management CLI commands."""

import click
from loguru import logger

from quantsys.config import get_settings
from quantsys.data import Database
from quantsys.data.collector import DataCollector


@click.group()
def data() -> None:
    """Data management commands."""
    pass


@data.command()
@click.option("--symbol", "-s", required=True, help="Stock symbol (e.g., 000001.SZ)")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", required=True, help="End date (YYYY-MM-DD)")
@click.option("--freq", default="1m", type=click.Choice(["1m", "1d"]), help="Data frequency")
def download(symbol: str, start: str, end: str, freq: str) -> None:
    """Download historical data for a symbol."""
    settings = get_settings()
    db = Database(settings.db_path)

    collector = DataCollector(db)

    try:
        if freq == "1m":
            df = collector.download_minute_data(symbol, start, end)
        else:
            df = collector.download_daily_data(symbol, start, end)

        click.echo(f"✓ Downloaded {len(df)} records for {symbol}")
    except Exception as e:
        logger.error(f"Failed to download data: {e}")
        raise click.ClickException(str(e))


@data.command()
@click.option("--symbols", "-s", help="Comma-separated list of symbols")
@click.option("--batch", is_flag=True, help="Download all A-shares")
@click.option("--start", default="2023-01-01", help="Start date")
@click.option("--end", help="End date (default: today)")
def update(symbols: str, batch: bool, start: str, end: str) -> None:
    """Update market data (incremental)."""
    settings = get_settings()
    db = Database(settings.db_path)
    collector = DataCollector(db)

    if batch:
        click.echo("Fetching A-share stock list...")
        symbol_list = collector.get_stock_list()
        click.echo(f"Found {len(symbol_list)} stocks")
    elif symbols:
        symbol_list = [s.strip() for s in symbols.split(",")]
    else:
        raise click.ClickException("Either --symbols or --batch must be specified")

    # TODO: Implement batch download with progress bar
    click.echo(f"Would update {len(symbol_list)} symbols from {start} to {end or 'today'}")


@data.command()
def status() -> None:
    """Show data status."""
    settings = get_settings()
    db = Database(settings.db_path)

    # Count records in each table
    VALID_TABLES = {"market_data", "daily_data", "factors"}

    click.echo("Data Status:")
    click.echo("-" * 40)

    for table in VALID_TABLES:
        try:
            result = db.fetchone("SELECT COUNT(*) as count FROM " + table)
            count = result["count"] if result else 0
            click.echo(f"  {table}: {count:,} records")
        except Exception:
            click.echo(f"  {table}: not available")

    # Show date range
    try:
        result = db.fetchone(
            "SELECT MIN(timestamp) as min_date, MAX(timestamp) as max_date FROM market_data"
        )
        if result and result["min_date"]:
            click.echo(f"\nMinute data range: {result['min_date']} to {result['max_date']}")
    except Exception:
        pass
