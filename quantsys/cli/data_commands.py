"""Data management CLI commands."""

from datetime import datetime

import click
from loguru import logger

from quantsys.config import get_settings
from quantsys.data import Database
from quantsys.data.collector import COMMON_INDICES, DataCollector, DownloadResult


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

        click.echo(f"Downloaded {len(df)} records for {symbol}")
    except Exception as e:
        logger.error(f"Failed to download data: {e}")
        raise click.ClickException(str(e))


@data.command()
@click.option("--symbols", "-s", help="Comma-separated list of symbols")
@click.option("--batch", is_flag=True, help="Download all A-shares")
@click.option("--start", default="2023-01-01", help="Start date")
@click.option("--end", help="End date (default: today)")
@click.option("--freq", default="1d", type=click.Choice(["1m", "1d"]), help="Data frequency")
@click.option("--workers", "-w", default=4, help="Parallel download threads")
def update(symbols: str, batch: bool, start: str, end: str, freq: str, workers: int) -> None:
    """Update market data with parallel download."""
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

    end = end or datetime.now().strftime("%Y-%m-%d")
    click.echo(f"Downloading {len(symbol_list)} symbols ({freq}) with {workers} workers...")

    def _on_progress(result: DownloadResult, done: int, total: int) -> None:
        status = f"{result.records} records" if result.success else f"FAILED: {result.error}"
        click.echo(f"  [{done}/{total}] {result.symbol}: {status}")

    results = collector.parallel_download(
        symbols=symbol_list,
        start=start,
        end=end,
        freq=freq,
        max_workers=workers,
        progress_callback=_on_progress,
    )

    succeeded = sum(1 for r in results if r.success)
    total_records = sum(r.records for r in results if r.success)
    click.echo(f"\nDone: {succeeded}/{len(results)} succeeded, {total_records:,} total records")


@data.command("index")
@click.option("--code", "-c", help="Index code (e.g., 000300 for CSI 300)")
@click.option("--all", "all_indices", is_flag=True, help="Download all common indices")
@click.option("--start", default="2020-01-01", help="Start date (YYYY-MM-DD)")
@click.option("--end", help="End date (default: today)")
@click.option("--list", "list_indices", is_flag=True, help="List available common indices")
def index_cmd(
    code: str, all_indices: bool, start: str, end: str, list_indices: bool
) -> None:
    """Download market index data."""
    if list_indices:
        click.echo("Common indices:")
        for idx_code, name in COMMON_INDICES.items():
            click.echo(f"  {idx_code}  {name}")
        return

    settings = get_settings()
    db = Database(settings.db_path)
    collector = DataCollector(db)
    end = end or datetime.now().strftime("%Y-%m-%d")

    if all_indices:
        click.echo(f"Downloading {len(COMMON_INDICES)} indices from {start} to {end}...")
        results = collector.download_all_indices(start, end)
        for idx_code, result in results.items():
            name = COMMON_INDICES.get(idx_code, idx_code)
            if result.success:
                click.echo(f"  {idx_code} {name}: {result.records} records")
            else:
                click.echo(f"  {idx_code} {name}: FAILED - {result.error}")
    elif code:
        try:
            df = collector.download_index_daily_data(code, start, end)
            name = COMMON_INDICES.get(code, code)
            click.echo(f"Downloaded {len(df)} records for {code} ({name})")
        except Exception as e:
            raise click.ClickException(str(e))
    else:
        raise click.ClickException("Specify --code, --all, or --list")


@data.command()
def status() -> None:
    """Show data status."""
    settings = get_settings()
    db = Database(settings.db_path)

    tables = ["market_data", "daily_data", "index_daily_data", "factors"]

    click.echo("Data Status:")
    click.echo("-" * 50)

    for table in tables:
        try:
            result = db.fetchone(f"SELECT COUNT(*) as count FROM {table}")
            count = result["count"] if result else 0
            click.echo(f"  {table:20s} {count:>10,} records")
        except Exception:
            click.echo(f"  {table:20s} not available")

    # Show date ranges
    for table, date_col, label in [
        ("market_data", "timestamp", "Minute data"),
        ("daily_data", "date", "Daily data"),
        ("index_daily_data", "date", "Index data"),
    ]:
        try:
            result = db.fetchone(
                f"SELECT MIN({date_col}) as min_d, MAX({date_col}) as max_d FROM {table}"
            )
            if result and result["min_d"]:
                click.echo(f"\n  {label} range: {result['min_d']} ~ {result['max_d']}")

                # Show symbol count for this table
                sym_result = db.fetchone(
                    f"SELECT COUNT(DISTINCT symbol) as cnt FROM {table}"
                )
                if sym_result:
                    click.echo(f"  {label} symbols: {sym_result['cnt']}")
        except Exception:
            pass
