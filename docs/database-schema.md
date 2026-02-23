# QuantSys Database Schema

SQLite database, default path: `data/quantsys.db`

## Table Overview


| Table | Purpose | Primary Key | Data Source |
|---|---|---|---|
| `market_data` | Minute-level OHLCV | `(symbol, timestamp)` | akshare `stock_zh_a_hist_min_em()` via `DataCollector.download_minute_data()` |
| `daily_data` | Daily OHLCV | `(symbol, date)` | akshare `stock_zh_a_hist()` via `DataCollector.download_daily_data()` |
| `index_daily_data` | Market index daily OHLCV | `(symbol, date)` | akshare `stock_zh_index_daily()` via `DataCollector.download_index_daily_data()` |
| `factors` | Precomputed technical indicators | `(symbol, timestamp)` | Computed from `market_data` / `daily_data` (no automated pipeline yet) |
| `strategies` | Strategy definitions | `id` (auto) | Written by `StrategyLoader` or LLM code generator |
| `backtest_results` | Backtest run results | `id` (auto) | Written by `BacktestEngine` after each backtest run |
| `paper_accounts` | Paper trading accounts | `id` (auto) | Created by `quant paper` CLI commands |
| `paper_trades` | Paper trading records | `id` (auto) | Written by paper trading engine on each simulated fill |


---

## Market Data Tables

### `market_data` — Minute-level OHLCV

Stores intraday bar data (1m/5m/15m/30m/60m).

- **Data source**: akshare `ak.stock_zh_a_hist_min_em(symbol, period, start_date, end_date, adjust="qfq")`
- **Writer**: `DataCollector.download_minute_data()` / `DataCollector.parallel_download(freq="1m")`
- **CLI**: `quant data download -s 000001.SZ --start 2024-01-01 --end 2024-12-31 --freq 1m`


| Column       | Type              | Description                    |
| ------------ | ----------------- | ------------------------------ |
| `symbol`     | TEXT NOT NULL     | Stock symbol, e.g. `000001.SZ` |
| `timestamp`  | DATETIME NOT NULL | Bar timestamp                  |
| `open`       | REAL              | Open price (forward-adjusted)  |
| `high`       | REAL              | High price                     |
| `low`        | REAL              | Low price                      |
| `close`      | REAL              | Close price                    |
| `volume`     | INTEGER           | Volume (shares)                |
| `amount`     | REAL              | Turnover (CNY)                 |
| `adj_factor` | REAL DEFAULT 1.0  | Forward adjustment factor      |


Indexes: `idx_market_symbol(symbol)`, `idx_market_time(timestamp)`

### `daily_data` — Daily OHLCV

Stores daily bar data for individual stocks.

- **Data source**: akshare `ak.stock_zh_a_hist(symbol, period="daily", start_date, end_date, adjust="qfq")`
- **Writer**: `DataCollector.download_daily_data()` / `DataCollector.parallel_download(freq="1d")`
- **CLI**: `quant data download -s 000001.SZ --start 2024-01-01 --end 2024-12-31 --freq 1d`


| Column       | Type             | Description                    |
| ------------ | ---------------- | ------------------------------ |
| `symbol`     | TEXT NOT NULL    | Stock symbol, e.g. `000001.SZ` |
| `date`       | DATE NOT NULL    | Trading date                   |
| `open`       | REAL             | Open price (forward-adjusted)  |
| `high`       | REAL             | High price                     |
| `low`        | REAL             | Low price                      |
| `close`      | REAL             | Close price                    |
| `volume`     | INTEGER          | Volume (shares)                |
| `amount`     | REAL             | Turnover (CNY)                 |
| `adj_factor` | REAL DEFAULT 1.0 | Forward adjustment factor      |


Indexes: `idx_daily_symbol(symbol)`, `idx_daily_date(date)`

### `index_daily_data` — Market Index Daily OHLCV

Stores daily data for broad market / sector indices (e.g. CSI 300, SSE Composite).

- **Data source**: akshare `ak.stock_zh_index_daily(symbol)` (symbol format: `sh000001` / `sz399001`)
- **Writer**: `DataCollector.download_index_daily_data()` / `DataCollector.download_all_indices()`
- **CLI**: `quant data index --code 000300 --start 2020-01-01` or `quant data index --all`


| Column   | Type          | Description                         |
| -------- | ------------- | ----------------------------------- |
| `symbol` | TEXT NOT NULL | Index code, e.g. `000300` (CSI 300) |
| `date`   | DATE NOT NULL | Trading date                        |
| `open`   | REAL          | Open                                |
| `high`   | REAL          | High                                |
| `low`    | REAL          | Low                                 |
| `close`  | REAL          | Close                               |
| `volume` | INTEGER       | Volume                              |
| `amount` | REAL          | Turnover                            |


Indexes: `idx_index_daily_symbol(symbol)`, `idx_index_daily_date(date)`

Built-in index codes:


| Code     | Name   |
| -------- | ------ |
| `000001` | 上证综指   |
| `399001` | 深证成指   |
| `000300` | 沪深300  |
| `000905` | 中证500  |
| `000852` | 中证1000 |
| `399006` | 创业板指   |
| `000688` | 科创50   |


---

## Factor Table

### `factors` — Precomputed Technical Indicators

Stores precomputed technical factors aligned to market data timestamps.

- **Data source**: Computed from `market_data` or `daily_data` price series (MA, RSI, MACD, ATR)
- **Writer**: No automated pipeline yet — currently populated by manual scripts or test code
- **Note**: Table schema is defined but no `FactorCalculator` module exists; factors are computed inline by strategies at runtime


| Column      | Type              | Description                        |
| ----------- | ----------------- | ---------------------------------- |
| `symbol`    | TEXT NOT NULL     | Stock symbol                       |
| `timestamp` | DATETIME NOT NULL | Aligned to `market_data.timestamp` |
| `ma_5`      | REAL              | 5-period moving average            |
| `ma_10`     | REAL              | 10-period moving average           |
| `ma_20`     | REAL              | 20-period moving average           |
| `ma_60`     | REAL              | 60-period moving average           |
| `rsi_14`    | REAL              | 14-period RSI                      |
| `macd_dif`  | REAL              | MACD DIF line                      |
| `macd_dea`  | REAL              | MACD DEA (signal) line             |
| `macd_hist` | REAL              | MACD histogram                     |
| `atr_14`    | REAL              | 14-period ATR                      |


Indexes: `idx_factors_symbol(symbol)`, `idx_factors_time(timestamp)`

---

## Strategy & Backtest Tables

### `strategies` — Strategy Definitions

Registry of strategy metadata. `params` stores default parameter JSON.

- **Data source**: Application-generated — written when registering a strategy
- **Writer**: `StrategyLoader` on strategy registration, or LLM code generator (`quantsys/skills/code_generate/generator.py`)


| Column        | Type                 | Description                 |
| ------------- | -------------------- | --------------------------- |
| `id`          | INTEGER PK AUTO      | Unique ID                   |
| `name`        | TEXT UNIQUE NOT NULL | Strategy name               |
| `description` | TEXT                 | Human-readable description  |
| `code_path`   | TEXT NOT NULL        | Path to strategy `.py` file |
| `params`      | TEXT                 | Default parameters (JSON)   |
| `created_at`  | TIMESTAMP            | Creation time               |
| `updated_at`  | TIMESTAMP            | Last update time            |


Index: `idx_strategies_name(name)`

### `backtest_results` — Backtest Run Results

Stores full backtest output: metrics, trade log, and equity curve.

- **Data source**: Application-generated — written after each backtest completes
- **Writer**: `BacktestEngine` at the end of `run()`, serializes metrics/trades/equity_curve to JSON
- **CLI**: `quant backtest run ...`


| Column         | Type            | Description                 |
| -------------- | --------------- | --------------------------- |
| `id`           | INTEGER PK AUTO | Unique ID                   |
| `strategy_id`  | INTEGER FK      | References `strategies.id`  |
| `start_date`   | DATE            | Backtest start              |
| `end_date`     | DATE            | Backtest end                |
| `symbols`      | TEXT            | Comma-separated symbol list |
| `metrics`      | TEXT            | Performance metrics (JSON)  |
| `trades`       | TEXT            | Trade log (JSON)            |
| `equity_curve` | TEXT            | Equity curve series (JSON)  |
| `created_at`   | TIMESTAMP       | Run time                    |


Index: `idx_backtest_strategy(strategy_id)`

---

## Paper Trading Tables

### `paper_accounts` — Paper Trading Accounts

Each account tracks cash and positions for simulated trading.

- **Data source**: Application-generated — created when user sets up a paper trading account
- **Writer**: Paper trading module via `quant paper` CLI commands


| Column         | Type                 | Description            |
| -------------- | -------------------- | ---------------------- |
| `id`           | INTEGER PK AUTO      | Unique ID              |
| `name`         | TEXT UNIQUE NOT NULL | Account name           |
| `initial_cash` | REAL DEFAULT 1000000 | Starting capital (CNY) |
| `current_cash` | REAL                 | Available cash         |
| `positions`    | TEXT                 | Open positions (JSON)  |
| `created_at`   | TIMESTAMP            | Creation time          |


### `paper_trades` — Paper Trading Records

Individual trade records for paper accounts.

- **Data source**: Application-generated — written on each simulated trade execution
- **Writer**: Paper trading engine on each fill event


| Column       | Type            | Description                    |
| ------------ | --------------- | ------------------------------ |
| `id`         | INTEGER PK AUTO | Unique ID                      |
| `account_id` | INTEGER FK      | References `paper_accounts.id` |
| `symbol`     | TEXT            | Stock symbol                   |
| `side`       | TEXT            | `BUY` or `SELL`                |
| `quantity`   | INTEGER         | Number of shares               |
| `price`      | REAL            | Execution price                |
| `timestamp`  | DATETIME        | Execution time                 |


Index: `idx_paper_trades_account(account_id)`

---

## Notes

- **Auto-commit**: `Database.execute()` and `executemany()` auto-commit write operations. Use `transaction()` context manager only for multi-statement atomic blocks.
- **Symbol format**: Individual stocks use `000001.SZ` / `600519.SH` format. Index codes are bare numbers like `000300`.
- **JSON fields**: `params`, `metrics`, `trades`, `equity_curve`, `positions` are stored as JSON text. Use `to_json()` / `from_json()` helpers from `quantsys.data.database`.
- **Adjustment**: Price data is forward-adjusted (`qfq`) at download time. The `adj_factor` column stores the ratio for re-adjustment if needed.

