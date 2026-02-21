"""Stock symbol management."""

from dataclasses import dataclass
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
from loguru import logger


@dataclass
class StockInfo:
    """Stock information."""

    symbol: str  # e.g., "000001.SZ"
    code: str  # e.g., "000001"
    exchange: str  # "SZ" or "SH"
    name: str
    industry: Optional[str] = None
    market_cap: Optional[float] = None


class SymbolManager:
    """Manage stock symbols and metadata."""

    # Exchange mapping
    EXCHANGE_MAP = {
        "sh": "SH",
        "sz": "SZ",
        "SH": "SH",
        "SZ": "SZ",
    }

    def __init__(self) -> None:
        """Initialize symbol manager."""
        self._stock_list: Optional[pd.DataFrame] = None
        self._symbol_cache: Dict[str, StockInfo] = {}

    def get_all_stocks(self, refresh: bool = False) -> pd.DataFrame:
        """Get all A-share stocks.

        Args:
            refresh: Force refresh from API

        Returns:
            DataFrame with stock information
        """
        if self._stock_list is None or refresh:
            try:
                self._stock_list = ak.stock_zh_a_spot_em()
            except Exception as e:
                logger.error(f"Failed to fetch stock list: {e}")
                raise

        return self._stock_list

    def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """Get information for a specific stock.

        Args:
            symbol: Stock symbol (e.g., "000001.SZ")

        Returns:
            StockInfo or None if not found
        """
        if symbol in self._symbol_cache:
            return self._symbol_cache[symbol]

        code, exchange = self.parse_symbol(symbol)

        df = self.get_all_stocks()

        # Find matching row
        row = df[df["代码"] == code]

        if row.empty:
            return None

        info = StockInfo(
            symbol=symbol,
            code=code,
            exchange=exchange,
            name=row.iloc[0]["名称"],
            industry=row.iloc[0].get("所属行业"),
            market_cap=row.iloc[0].get("总市值"),
        )

        self._symbol_cache[symbol] = info
        return info

    def parse_symbol(self, symbol: str) -> tuple:
        """Parse symbol into code and exchange.

        Args:
            symbol: Symbol string (e.g., "000001.SZ" or "sz000001")

        Returns:
            Tuple of (code, exchange)
        """
        if "." in symbol:
            # Format: 000001.SZ
            code, exchange = symbol.split(".")
            return code, exchange.upper()
        else:
            # Format: sz000001
            if symbol.lower().startswith("sh"):
                return symbol[2:], "SH"
            elif symbol.lower().startswith("sz"):
                return symbol[2:], "SZ"
            else:
                # Guess exchange from code prefix
                code = symbol
                if code.startswith("6"):
                    return code, "SH"
                else:
                    return code, "SZ"

    def to_akshare_format(self, symbol: str) -> str:
        """Convert to akshare format (sh000001 or sz000001).

        Args:
            symbol: Symbol in standard format (e.g., "000001.SZ")

        Returns:
            Akshare format symbol
        """
        code, exchange = self.parse_symbol(symbol)
        return f"{exchange.lower()}{code}"

    def from_akshare_format(self, ak_symbol: str) -> str:
        """Convert from akshare format to standard format.

        Args:
            ak_symbol: Akshare symbol (e.g., "sz000001")

        Returns:
            Standard format symbol (e.g., "000001.SZ")
        """
        if ak_symbol.lower().startswith("sh"):
            return f"{ak_symbol[2:]}.SH"
        elif ak_symbol.lower().startswith("sz"):
            return f"{ak_symbol[2:]}.SZ"
        else:
            raise ValueError(f"Invalid akshare symbol format: {ak_symbol}")

    def filter_by_industry(self, industry: str) -> List[str]:
        """Filter stocks by industry.

        Args:
            industry: Industry name

        Returns:
            List of symbols
        """
        df = self.get_all_stocks()

        if "所属行业" not in df.columns:
            logger.warning("Industry column not available")
            return []

        filtered = df[df["所属行业"].str.contains(industry, na=False)]

        symbols = []
        for _, row in filtered.iterrows():
            code = row["代码"]
            exchange = "SH" if code.startswith("6") else "SZ"
            symbols.append(f"{code}.{exchange}")

        return symbols

    def filter_by_market_cap(
        self,
        min_cap: Optional[float] = None,
        max_cap: Optional[float] = None,
    ) -> List[str]:
        """Filter stocks by market capitalization.

        Args:
            min_cap: Minimum market cap (in billions)
            max_cap: Maximum market cap (in billions)

        Returns:
            List of symbols
        """
        df = self.get_all_stocks()

        if "总市值" not in df.columns:
            logger.warning("Market cap column not available")
            return []

        # Convert to billions for comparison
        df["总市值_亿"] = df["总市值"] / 1e8

        if min_cap is not None:
            df = df[df["总市值_亿"] >= min_cap]

        if max_cap is not None:
            df = df[df["总市值_亿"] <= max_cap]

        symbols = []
        for _, row in df.iterrows():
            code = row["代码"]
            exchange = "SH" if code.startswith("6") else "SZ"
            symbols.append(f"{code}.{exchange}")

        return symbols

    def get_index_components(self, index_code: str) -> List[str]:
        """Get components of an index.

        Args:
            index_code: Index code (e.g., "000300" for CSI 300)

        Returns:
            List of constituent symbols
        """
        try:
            df = ak.index_stock_cons_weight_em(symbol=index_code)
        except Exception as e:
            logger.error(f"Failed to fetch index components for {index_code}: {e}")
            return []

        symbols = []
        for _, row in df.iterrows():
            code = row["成分券代码"]
            exchange = "SH" if code.startswith("6") else "SZ"
            symbols.append(f"{code}.{exchange}")

        return symbols
