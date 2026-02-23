# Data CLI Guide

All data commands are under `quant data`. Run `quant data --help` to see available subcommands.

## Prerequisites

```bash
# Initialize database (first time only)
quant init

# Verify database is ready
quant data status
```

---

## 1. Download Single Stock

Download historical data for one symbol. Saves to `market_data` (minute) or `daily_data` (daily) table.

```bash
# Daily data for Ping An Bank, full year 2024
quant data download -s 000001.SZ --start 2024-01-01 --end 2024-12-31 --freq 1d

# Minute data (1m) for Kweichow Moutai, recent month
quant data download -s 600519.SH --start 2025-01-01 --end 2025-01-31 --freq 1m
```

**Options:**

| Option | Required | Default | Description |
|---|---|---|---|
| `-s / --symbol` | Yes | — | Stock symbol, e.g. `000001.SZ`, `600519.SH` |
| `--start` | Yes | — | Start date `YYYY-MM-DD` |
| `--end` | Yes | — | End date `YYYY-MM-DD` |
| `--freq` | No | `1m` | `1m` (minute) or `1d` (daily) |

**Symbol format**: Code + exchange suffix. SZ = Shenzhen, SH = Shanghai.

| Prefix | Exchange | Example |
|---|---|---|
| `000xxx` | `.SZ` | `000001.SZ` (平安银行) |
| `002xxx` | `.SZ` | `002594.SZ` (比亚迪) |
| `300xxx` | `.SZ` | `300750.SZ` (宁德时代) |
| `600xxx` | `.SH` | `600519.SH` (贵州茅台) |
| `601xxx` | `.SH` | `601318.SH` (中国平安) |
| `688xxx` | `.SH` | `688981.SH` (中芯国际) |

---

## 2. Batch / Parallel Download

Download multiple stocks in parallel using multithreading.

```bash
# Download 3 stocks, daily data, 4 threads (default)
quant data update -s "000001.SZ,600519.SH,000858.SZ" --start 2024-01-01 --freq 1d

# Download with 8 threads for faster speed
quant data update -s "000001.SZ,600519.SH,300750.SZ,601318.SH" \
  --start 2023-01-01 --end 2025-01-01 --freq 1d --workers 8

# Minute data for multiple stocks
quant data update -s "000001.SZ,600519.SH" --start 2025-01-01 --freq 1m -w 2

# Download ALL A-shares (daily), uses all 4 default threads
quant data update --batch --start 2024-01-01 --freq 1d

# Download ALL A-shares with 16 threads
quant data update --batch --start 2024-01-01 --freq 1d --workers 16
```

**Options:**

| Option | Required | Default | Description |
|---|---|---|---|
| `-s / --symbols` | * | — | Comma-separated symbol list |
| `--batch` | * | — | Download all A-shares |
| `--start` | No | `2023-01-01` | Start date |
| `--end` | No | Today | End date |
| `--freq` | No | `1d` | `1m` or `1d` |
| `-w / --workers` | No | `4` | Number of parallel threads |

\* Either `--symbols` or `--batch` is required.

**Output example:**

```
Downloading 3 symbols (1d) with 4 workers...
  [1/3] 600519.SH: 243 records
  [2/3] 000001.SZ: 243 records
  [3/3] 000858.SZ: 243 records

Done: 3/3 succeeded, 729 total records
```

---

## 3. Index (Market) Data

Download broad market index data. Saves to `index_daily_data` table.

```bash
# List all built-in index codes
quant data index --list

# Download CSI 300 index
quant data index --code 000300 --start 2020-01-01

# Download SSE Composite index with custom end date
quant data index -c 000001 --start 2020-01-01 --end 2025-12-31

# Download ALL common indices at once
quant data index --all --start 2020-01-01
```

**Built-in indices:**

| Code | Name | CLI Example |
|---|---|---|
| `000001` | 上证综指 | `quant data index -c 000001` |
| `399001` | 深证成指 | `quant data index -c 399001` |
| `000300` | 沪深300 | `quant data index -c 000300` |
| `000905` | 中证500 | `quant data index -c 000905` |
| `000852` | 中证1000 | `quant data index -c 000852` |
| `399006` | 创业板指 | `quant data index -c 399006` |
| `000688` | 科创50 | `quant data index -c 000688` |

**Options:**

| Option | Required | Default | Description |
|---|---|---|---|
| `-c / --code` | * | — | Index code |
| `--all` | * | — | Download all common indices |
| `--list` | * | — | Print available index codes |
| `--start` | No | `2020-01-01` | Start date |
| `--end` | No | Today | End date |

\* At least one of `--code`, `--all`, or `--list` is required.

---

## 4. Check Data Status

View record counts, date ranges, and symbol counts for all data tables.

```bash
quant data status
```

**Output example:**

```
Data Status:
--------------------------------------------------
  market_data              12,500 records
  daily_data                3,200 records
  index_daily_data          8,400 records
  factors                       0 records

  Minute data range: 2024-01-02 09:31:00 ~ 2024-12-31 15:00:00
  Minute data symbols: 5

  Daily data range: 2023-01-03 ~ 2025-01-20
  Daily data symbols: 10

  Index data range: 2020-01-02 ~ 2025-01-20
  Index data symbols: 7
```

---

## 5. Data Processing Pipeline

### What happens during download

Each download goes through these steps internally:

```
akshare API call
  → Raw DataFrame (Chinese column names)
    → Standardize columns (Chinese → English)
      → Type conversion (timestamp parsing, volume capping)
        → INSERT OR REPLACE into SQLite
```

### Column name mapping

**Minute data** (`_standardize_minute_df`):

| akshare (Chinese) | Database (English) |
|---|---|
| 时间 | `timestamp` |
| 开盘 | `open` |
| 收盘 | `close` |
| 最高 | `high` |
| 最低 | `low` |
| 成交量 | `volume` |
| 成交额 | `amount` |

**Daily data** (`_standardize_daily_df`):

| akshare (Chinese) | Database (English) |
|---|---|
| 日期 | `date` |
| 开盘 | `open` |
| 收盘 | `close` |
| 最高 | `high` |
| 最低 | `low` |
| 成交量 | `volume` |
| 成交额 | `amount` |

### Data cleaning rules

| Rule | Detail |
|---|---|
| Forward adjustment | All prices are forward-adjusted (`adjust="qfq"`) at download time |
| Volume capping | Volume values are capped at `2,147,483,647` (SQLite INTEGER max) |
| NaN volume | `NaN` volume is replaced with `0` |
| Duplicate handling | `INSERT OR REPLACE` — re-downloading the same date range safely overwrites existing records |
| Timestamp parsing | All timestamps are parsed to Python `datetime` before insertion |
| Index date filtering | Index API returns full history; filtered to `[start, end]` range before saving |

---

## 6. Python API Examples

For use in scripts or notebooks outside the CLI.

```python
from quantsys.config import get_settings
from quantsys.data import Database, DataCollector, SymbolManager, COMMON_INDICES

settings = get_settings()
db = Database(settings.db_path)
collector = DataCollector(db)

# --- Single stock ---
df = collector.download_daily_data("000001.SZ", "2024-01-01", "2024-12-31")

# --- Parallel download ---
results = collector.parallel_download(
    symbols=["000001.SZ", "600519.SH", "300750.SZ"],
    start="2024-01-01",
    end="2024-12-31",
    freq="1d",
    max_workers=4,
)
for r in results:
    print(f"{r.symbol}: {'OK' if r.success else r.error} ({r.records} records)")

# --- Index data ---
collector.download_index_daily_data("000300", "2020-01-01", "2025-01-01")
collector.download_all_indices("2020-01-01", "2025-01-01")

# --- Stock universe ---
sm = SymbolManager()
all_stocks = sm.get_all_stocks()                        # Full A-share list
csi300 = sm.get_index_components("000300")              # CSI 300 constituents
banks = sm.filter_by_industry("银行")                    # Filter by industry
large_caps = sm.filter_by_market_cap(min_cap=1000)      # Market cap > 1000 billion
info = sm.get_stock_info("600519.SH")                   # Single stock metadata

# --- Query data from database ---
rows = db.fetchall(
    "SELECT * FROM daily_data WHERE symbol = ? AND date >= ? ORDER BY date",
    ("000001.SZ", "2024-01-01"),
)

index_rows = db.fetchall(
    "SELECT * FROM index_daily_data WHERE symbol = ? ORDER BY date",
    ("000300",),
)
```

---

## Typical Workflow

```bash
# 1. Initialize
quant init

# 2. Download index data for market overview
quant data index --all --start 2020-01-01

# 3. Download stock pool (e.g. a few target stocks)
quant data update -s "000001.SZ,600519.SH,000858.SZ,300750.SZ" \
  --start 2023-01-01 --freq 1d --workers 4

# 4. Check what's in the database
quant data status

# 5. Run backtest with the downloaded data
quant backtest run ...
```
