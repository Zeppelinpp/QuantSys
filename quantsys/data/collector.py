"""Data collector using akshare."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

import akshare as ak
import pandas as pd
from loguru import logger

from quantsys.config import get_settings

from .database import Database

COMMON_INDICES: Dict[str, str] = {
    "000001": "上证综指",
    "399001": "深证成指",
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "399006": "创业板指",
    "000688": "科创50",
}


@dataclass
class DownloadResult:
    """Result of a single download task."""

    symbol: str
    success: bool
    records: int = 0
    error: Optional[str] = None


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
        code, exchange = symbol.split(".")

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

    def download_index_daily_data(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Download daily data for a market index.

        Args:
            index_code: Index code (e.g., "000300" for CSI 300)
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)

        Returns:
            DataFrame with daily OHLCV data
        """
        name = COMMON_INDICES.get(index_code, index_code)
        logger.info(f"Downloading index data for {index_code} ({name}) from {start} to {end}")

        try:
            df = ak.stock_zh_index_daily(
                symbol=f"sh{index_code}" if index_code.startswith(("000", "9")) else f"sz{index_code}",
            )
        except Exception as e:
            logger.error(f"Failed to download index data for {index_code}: {e}")
            raise

        if df.empty:
            logger.warning(f"No index data returned for {index_code}")
            return pd.DataFrame()

        df = self._standardize_index_df(df, index_code)

        # Filter date range
        start_dt = pd.to_datetime(start).date()
        end_dt = pd.to_datetime(end).date()
        df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]

        if df.empty:
            logger.warning(f"No index data in range for {index_code}")
            return pd.DataFrame()

        self._save_index_daily_data(df)
        return df

    def download_all_indices(
        self,
        start: str,
        end: str,
        indices: Optional[Dict[str, str]] = None,
    ) -> Dict[str, DownloadResult]:
        """Download daily data for common market indices.

        Args:
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            indices: Custom index dict {code: name}, defaults to COMMON_INDICES
        """
        targets = indices or COMMON_INDICES
        results: Dict[str, DownloadResult] = {}

        for code, name in targets.items():
            try:
                df = self.download_index_daily_data(code, start, end)
                results[code] = DownloadResult(
                    symbol=code, success=True, records=len(df)
                )
            except Exception as e:
                results[code] = DownloadResult(
                    symbol=code, success=False, error=str(e)
                )
                logger.error(f"Failed to download index {code} ({name}): {e}")

        return results

    def parallel_download(
        self,
        symbols: List[str],
        start: str,
        end: str,
        freq: str = "1d",
        max_workers: int = 4,
        progress_callback: Optional[Callable[[DownloadResult, int, int], None]] = None,
    ) -> List[DownloadResult]:
        """Download data for multiple symbols in parallel.

        Args:
            symbols: List of stock symbols
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
            freq: "1d" for daily, "1m"/"5m"/... for minute
            max_workers: Max concurrent download threads
            progress_callback: Called after each download with (result, completed, total)

        Returns:
            List of DownloadResult for each symbol
        """
        total = len(symbols)
        results: List[DownloadResult] = []
        completed = 0

        def _download_one(symbol: str) -> DownloadResult:
            try:
                if freq == "1d":
                    df = self.download_daily_data(symbol, start, end)
                else:
                    period = freq.replace("m", "")
                    df = self.download_minute_data(symbol, start, end, period=period)
                return DownloadResult(symbol=symbol, success=True, records=len(df))
            except Exception as e:
                return DownloadResult(symbol=symbol, success=False, error=str(e))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_download_one, s): s for s in symbols}

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback(result, completed, total)
                elif result.success:
                    logger.info(
                        f"[{completed}/{total}] {result.symbol}: "
                        f"{result.records} records"
                    )
                else:
                    logger.error(
                        f"[{completed}/{total}] {result.symbol}: "
                        f"FAILED - {result.error}"
                    )

        succeeded = sum(1 for r in results if r.success)
        logger.info(
            f"Parallel download complete: {succeeded}/{total} succeeded"
        )
        return results

    def _standardize_index_df(self, df: pd.DataFrame, index_code: str) -> pd.DataFrame:
        """Standardize index data DataFrame."""
        column_map = {
            "date": "date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
        }

        rename_map = {}
        for old_name, new_name in column_map.items():
            if old_name in df.columns:
                rename_map[old_name] = new_name
        df = df.rename(columns=rename_map)

        df["symbol"] = index_code
        df["date"] = pd.to_datetime(df["date"]).dt.date

        if "amount" not in df.columns:
            df["amount"] = 0.0

        cols = ["symbol", "date", "open", "high", "low", "close", "volume", "amount"]
        df = df[[c for c in cols if c in df.columns]]
        return df

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

    def _save_index_daily_data(self, df: pd.DataFrame) -> None:
        """Save index daily data to database."""
        if df.empty:
            return

        records = []
        for _, row in df.iterrows():
            volume = row.get("volume", 0)
            if pd.isna(volume):
                volume = 0
            else:
                volume = int(min(volume, 2_147_483_647))

            records.append((
                row["symbol"],
                row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                volume,
                row.get("amount", 0.0),
            ))

        self.db.executemany(
            """
            INSERT OR REPLACE INTO index_daily_data
            (symbol, date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )

        logger.info(f"Saved {len(records)} index daily records to database")
