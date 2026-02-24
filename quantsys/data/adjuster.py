"""Adjustment factor calculator for stock splits and dividends."""

from datetime import datetime

import akshare as ak
import pandas as pd
from loguru import logger

from .database import Database


class Adjuster:
    """Calculate and apply adjustment factors."""

    def __init__(self, database: Database) -> None:
        """Initialize adjuster with database."""
        self.db = database

    def download_adjustment_factors(self, symbol: str) -> pd.DataFrame:
        """Download adjustment factor history for a symbol.

        Args:
            symbol: Stock symbol (e.g., "000001.SZ")

        Returns:
            DataFrame with adjustment factor history
        """
        code, exchange = symbol.split(".")

        logger.info(f"Downloading adjustment factors for {symbol}")

        try:
            # Get stock split and dividend data
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                adjust="qfq",  # Forward adjusted
            )

            if df.empty:
                return pd.DataFrame()

            # Also get unadjusted data to calculate factors
            df_unadj = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                adjust="",
            )

            if df_unadj.empty:
                return pd.DataFrame()

            # Calculate adjustment factor
            df_factors = self._calculate_factors(df, df_unadj, symbol)

            return df_factors

        except Exception as e:
            logger.error(f"Failed to download adjustment factors for {symbol}: {e}")
            raise

    def _calculate_factors(
        self,
        df_adj: pd.DataFrame,
        df_unadj: pd.DataFrame,
        symbol: str,
    ) -> pd.DataFrame:
        """Calculate adjustment factors from adjusted and unadjusted prices."""
        # Merge on date
        df_adj = df_adj.rename(columns={"收盘": "close_adj"})
        df_unadj = df_unadj.rename(columns={"收盘": "close_unadj"})

        df_merged = pd.merge(
            df_adj[["日期", "close_adj"]],
            df_unadj[["日期", "close_unadj"]],
            on="日期",
        )

        # Calculate factor: adj_factor = close_adj / close_unadj
        # Handle potential division by zero
        df_merged["adj_factor"] = df_merged["close_adj"] / df_merged["close_unadj"].replace(
            0, pd.NA
        )
        df_merged = df_merged.dropna(subset=["adj_factor"])

        # Standardize
        df_merged["symbol"] = symbol
        df_merged = df_merged.rename(columns={"日期": "date"})
        df_merged["date"] = pd.to_datetime(df_merged["date"]).dt.date

        return df_merged[["symbol", "date", "adj_factor"]]

    def update_adjustment_factors(self, symbol: str) -> None:
        """Update adjustment factors in database."""
        df = self.download_adjustment_factors(symbol)

        if df.empty:
            logger.warning(f"No adjustment factors for {symbol}")
            return

        with self.db.transaction() as conn:
            # Update daily_data table
            for _, row in df.iterrows():
                conn.execute(
                    """
                    UPDATE daily_data
                    SET adj_factor = ?
                    WHERE symbol = ? AND date = ?
                    """,
                    (row["adj_factor"], symbol, row["date"].strftime("%Y-%m-%d")),
                )

            # Update market_data table (apply daily factor to all minute bars)
            for _, row in df.iterrows():
                conn.execute(
                    """
                    UPDATE market_data
                    SET adj_factor = ?
                    WHERE symbol = ? AND DATE(timestamp) = ?
                    """,
                    (row["adj_factor"], symbol, row["date"].strftime("%Y-%m-%d")),
                )

        logger.info(f"Updated adjustment factors for {symbol}")

    def get_adjusted_price(
        self,
        symbol: str,
        timestamp: datetime,
        price: float,
    ) -> float:
        """Get adjusted price for a given timestamp.

        Args:
            symbol: Stock symbol
            timestamp: Timestamp
            price: Original price

        Returns:
            Adjusted price
        """
        result = self.db.fetchone(
            """
            SELECT adj_factor FROM market_data
            WHERE symbol = ? AND timestamp = ?
            """,
            (symbol, timestamp.strftime("%Y-%m-%d %H:%M:%S")),
        )

        if result and result["adj_factor"]:
            return price * result["adj_factor"]

        return price

    def apply_adjustment(
        self,
        df: pd.DataFrame,
        adj_col: str = "adj_factor",
    ) -> pd.DataFrame:
        """Apply adjustment factors to price columns in DataFrame.

        Args:
            df: DataFrame with price columns and adj_factor
            adj_col: Column name for adjustment factor

        Returns:
            DataFrame with adjusted prices
        """
        if adj_col not in df.columns:
            logger.warning(f"No {adj_col} column found, skipping adjustment")
            return df

        price_cols = ["open", "high", "low", "close"]

        df_adj = df.copy()

        for col in price_cols:
            if col in df_adj.columns:
                df_adj[col] = df_adj[col] * df_adj[adj_col]

        return df_adj
