"""SQLite database wrapper for QuantSys."""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class Database:
    """Thread-safe SQLite database wrapper."""

    _instances: Dict[str, "Database"] = {}
    _lock = threading.Lock()

    def __new__(cls, db_path: Union[str, Path]) -> "Database":
        """Singleton pattern per database path."""
        path_str = str(Path(db_path).resolve())
        with cls._lock:
            if path_str not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[path_str] = instance
            return cls._instances[path_str]

    def __init__(self, db_path: Union[str, Path]) -> None:
        """Initialize database connection."""
        if self._initialized:
            return

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                detect_types=sqlite3.PARSE_DECLTYPES,
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable foreign keys
            self._local.connection.execute("PRAGMA foreign_keys = ON")
        return self._local.connection

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(
        self, sql: str, params: Optional[tuple] = None
    ) -> sqlite3.Cursor:
        """Execute SQL query."""
        conn = self._get_connection()
        if params is None:
            params = ()
        return conn.execute(sql, params)

    def executemany(self, sql: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """Execute SQL query with multiple parameter sets."""
        conn = self._get_connection()
        return conn.executemany(sql, params_list)

    def fetchall(
        self, sql: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dicts."""
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def fetchone(
        self, sql: str, params: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch single row as dict."""
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    def create_tables(self) -> None:
        """Create all database tables."""
        schema = self._get_schema()
        with self.transaction() as conn:
            conn.executescript(schema)

    def drop_tables(self) -> None:
        """Drop all tables (use with caution)."""
        tables = [
            "market_data",
            "daily_data",
            "factors",
            "strategies",
            "backtest_results",
            "paper_accounts",
            "paper_trades",
        ]
        with self.transaction() as conn:
            for table in tables:
                conn.execute(f"DROP TABLE IF EXISTS {table}")

    def list_tables(self) -> List[str]:
        """List all tables in database."""
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        rows = self.fetchall(sql)
        return [row["name"] for row in rows]

    def close(self) -> None:
        """Close database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

    def _get_schema(self) -> str:
        """Get database schema SQL."""
        return """
-- 原始行情数据（分钟级）
CREATE TABLE IF NOT EXISTS market_data (
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    amount REAL,
    adj_factor REAL DEFAULT 1.0,
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_market_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_time ON market_data(timestamp);

-- 日线数据（用于快速筛选）
CREATE TABLE IF NOT EXISTS daily_data (
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    amount REAL,
    adj_factor REAL DEFAULT 1.0,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_symbol ON daily_data(symbol);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_data(date);

-- 预计算因子库
CREATE TABLE IF NOT EXISTS factors (
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    ma_5 REAL,
    ma_10 REAL,
    ma_20 REAL,
    ma_60 REAL,
    rsi_14 REAL,
    macd_dif REAL,
    macd_dea REAL,
    macd_hist REAL,
    atr_14 REAL,
    PRIMARY KEY (symbol, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_factors_symbol ON factors(symbol);
CREATE INDEX IF NOT EXISTS idx_factors_time ON factors(timestamp);

-- 策略定义
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    code_path TEXT NOT NULL,
    params TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name);

-- 回测结果
CREATE TABLE IF NOT EXISTS backtest_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER,
    start_date DATE,
    end_date DATE,
    symbols TEXT,
    metrics TEXT,  -- JSON
    trades TEXT,   -- JSON
    equity_curve TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);

CREATE INDEX IF NOT EXISTS idx_backtest_strategy ON backtest_results(strategy_id);

-- 模拟盘账户
CREATE TABLE IF NOT EXISTS paper_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    initial_cash REAL DEFAULT 1000000,
    current_cash REAL,
    positions TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 模拟盘交易记录
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    symbol TEXT,
    side TEXT,  -- BUY/SELL
    quantity INTEGER,
    price REAL,
    timestamp DATETIME,
    FOREIGN KEY (account_id) REFERENCES paper_accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_account ON paper_trades(account_id);
"""


# Helper functions for JSON serialization
def to_json(data: Any) -> str:
    """Convert data to JSON string."""
    return json.dumps(data, ensure_ascii=False)


def from_json(data: str) -> Any:
    """Parse JSON string to data."""
    return json.loads(data)
