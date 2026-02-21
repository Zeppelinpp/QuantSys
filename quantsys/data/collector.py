"""Data collector using akshare."""

from datetime import datetime
from typing import List, Optional

import akshare as ak
import pandas as pd
from loguru import logger

from quantsys.config import get_settings

from .database import Database


class DataCollector:
    """A-share data collector using akshare."""

    def __init__(self, database: Database) -> None:
        """Initialize collector with database."""
        self.db = database
        self.settings = get_settings()

    def download_minute_data(
        self,
        symbol: str,
        start: str,
        end: str,
        period: str = "1",
    ) -> pd.DataFrame:
        """Download minute-level data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "000001.SZ")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            period: Minute period ("1", "5", "15", "30", "60")

        Returns:
            DataFrame with columns: symbol, timestamp, open, high, low, close, volume, amount
        """
        # Convert symbol format: 000001.SZ -> sz000001
        code, exchange = symbol.split(".")
        ak_symbol = f"{exchange.lower()}{code}"

        logger.info(f"Downloading minute data for {symbol} from {start} to {end}")

        try:
            # akshare minute data
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period=period,
                start_date=start,
                end_date=end,
                adjust="qfq",  # 前复权
            )
        except Exception as e:
            logger.error(f"Failed to download data for {symbol}: {e}")
            raise

        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()

        # Standardize column names
        df = self._standardize_minute_df(df, symbol)

        # Save to database
        self._save_minute_data(df)

        return df

    def download_daily_data(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Download daily data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "000001.SZ")
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            DataFrame with daily OHLCV data
        """
        code, exchange = symbol.split(".")

        logger.info(f"Downloading daily data for {symbol} from {start} to {end}")

        try:
            # akshare daily data
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
                adjust="qfq",
            )
        except Exception as e:
            logger.error(f"Failed to download daily data for {symbol}: {e}")
            raise

        if df.empty:
            logger.warning(f"No daily data returned for {symbol}")
            return pd.DataFrame()

        # Standardize column names
        df = self._standardize_daily_df(df, symbol)

        # Save to database
        self._save_daily_data(df)

        return df

    def get_stock_list(self) -> List[str]:
        """Get list of all A-share stock symbols.

        Returns:
            List of symbols in format "000001.SZ"
        """
        logger.info("Fetching A-share stock list")

        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as e:
            logger.error(f"Failed to fetch stock list: {e}")
            raise

        # Convert to standard format
        symbols = []
        for _, row in df.iterrows():
            code = row["代码"]
            # Determine exchange based on code prefix
            if code.startswith("6"):
                exchange = "SH"
            else:
                exchange = "SZ"
            symbols.append(f"{code}.{exchange}")

        return symbols

    def incremental_update(
        self,
        symbols: List[str],
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> None:
        """Incrementally update data for symbols.

        Only downloads data newer than what's already in the database.
        """
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        for symbol in symbols:
            # Check latest date in database
            result = self.db.fetchone(
                "SELECT MAX(timestamp) as max_ts FROM market_data WHERE symbol = ?",
                (symbol,),
            )

            if result and result["max_ts"]:
                # Start from next day
                latest = pd.Timestamp(result["max_ts"])
                symbol_start = (latest + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                # No existing data, use provided start
                symbol_start = start or "2020-01-01"

            if symbol_start > end:
                logger.info(f"{symbol} is up to date")
                continue

            try:
                self.download_minute_data(symbol, symbol_start, end)
                logger.info(f"Updated {symbol} from {symbol_start} to {end}")
            except Exception as e:
                logger.error(f"Failed to update {symbol}: {e}")
                continue

    def _standardize_minute_df(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Standardize minute data DataFrame."""
        # Map Chinese column names to English
        column_map = {
            "时间": "timestamp",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }

        df = df.rename(columns=column_map)

        # Add symbol column
        df["symbol"] = symbol

        # Ensure timestamp is datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # Select and order columns
        cols = ["symbol", "timestamp", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in cols if c in df.columns]]

        return df

    def _standardize_daily_df(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Standardize daily data DataFrame."""
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }

        df = df.rename(columns=column_map)
        df["symbol"] = symbol
        df["date"] = pd.to_datetime(df["date"]).dt.date

        cols = ["symbol", "date", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in cols if c in df.columns]]

        return df

    def _save_minute_data(self, df: pd.DataFrame) -> None:
        """Save minute data to database."""
        if df.empty:
            return

        records = []
        for _, row in df.iterrows():
            volume = row["volume"]
            if pd.isna(volume):
                volume = 0
            else:
                volume = int(min(volume, 2_147_483_647))  # Cap at SQLite max integer

            records.append((
                row["symbol"],
                row["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                volume,
                row["amount"],
            ))

        self.db.executemany(
            """
            INSERT OR REPLACE INTO market_data
            (symbol, timestamp, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        logger.info(f"Saved {len(records)} minute records to database")

    def _save_daily_data(self, df: pd.DataFrame) -> None:
        """Save daily data to database."""
        if df.empty:
            return

        records = []
        for _, row in df.iterrows():
            volume = row["volume"]
            if pd.isna(volume):
                volume = 0
            else:
                volume = int(min(volume, 2_147_483_647))  # Cap at SQLite max integer

            records.append((
                row["symbol"],
                row["date"].strftime("%Y-%m-%d"),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                volume,
                row["amount"],
            ))

        self.db.executemany(
            """
            INSERT OR REPLACE INTO daily_data
            (symbol, date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        logger.info(f"Saved {len(records)} daily records to database")
