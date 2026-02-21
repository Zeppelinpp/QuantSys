#!/usr/bin/env python3
"""QuantSys CLI entry point."""

import click
from loguru import logger

from quantsys.config import get_settings
from quantsys.data import Database


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """QuantSys - A-share quantitative trading system."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Setup logging
    settings = get_settings()
    log_level = "DEBUG" if verbose else settings.LOG_LEVEL
    logger.remove()
    logger.add(
        lambda msg: click.echo(msg, err=True),
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )
    if settings.log_path:
        logger.add(
            settings.log_path,
            level=log_level,
            rotation="10 MB",
            retention="30 days",
        )


@cli.command()
def init() -> None:
    """Initialize QuantSys (create database, directories)."""
    settings = get_settings()
    settings.ensure_directories()

    db = Database(settings.db_path)
    db.create_tables()

    click.echo(f"✓ Database initialized at {settings.db_path}")
    click.echo(f"✓ Directories created")
    click.echo("\nNext steps:")
    click.echo("  1. Copy config/.env.example to .env and configure")
    click.echo("  2. Run 'quant data update' to download market data")


@cli.command()
def version() -> None:
    """Show version information."""
    click.echo("QuantSys v0.1.0")


@cli.command()
def chat() -> None:
    """Start interactive chat with Agent."""
    from quantsys.cli.chat_mode import start_chat
    start_chat()


# Import and register subcommands
from quantsys.cli import backtest_commands, data_commands  # noqa: E402

cli.add_command(data_commands.data)
cli.add_command(backtest_commands.backtest)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
