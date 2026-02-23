# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the CLI
python quant_cli.py [command]   # or: quant [command] after install

# Initialize the database
quant init

# Download market data (A-share only, via akshare)
quant data download --symbol 000001.SZ --start 2024-01-01 --end 2024-12-31 --freq 1d

# Run tests
pytest                                                        # all tests
pytest tests/unit/test_database.py                            # single file
pytest tests/unit/test_database.py::TestDatabase::test_init  # single test
pytest -k "test_transaction"                                  # keyword match

# Lint / format / type-check
black quantsys/ tests/
ruff check quantsys/ tests/
mypy quantsys/
```

Config: line-length 100, target py311. Tests live in `tests/unit/`. The top-level `test_quant_system.py` is not picked up by pytest (testpaths = `["tests"]`).

## Architecture

QuantSys is an A-share quantitative trading system built around a central SQLite database (`data/quantsys.db`). Five subsystems interact through it:

### Data layer (`quantsys/data/`)
- `database.py` — Thread-safe SQLite singleton per resolved path. Connections are thread-local. **`execute()` and `executemany()` auto-commit writes** — no need to wrap in `transaction()` for simple inserts.
- `collector.py` — Downloads OHLCV from akshare, maps Chinese column names to English, saves to `market_data` (minute) or `daily_data` (daily).
- Symbol format: `000001.SZ` / `600519.SH` externally; converted to `sz000001` / `sh600519` for akshare calls.

### Backtest engine (`quantsys/backtest/`)
Event-driven synchronous loop: `BarEvent → SignalEvent → OrderEvent → FillEvent`.
- Orders execute at the **next bar's open** (configurable).
- T+1 enforced: cannot sell on the same day as purchase.
- Commission: 万3 base + 千0.5 stamp duty on sells + transfer fee. Tiered slippage by order size.
- `BacktestEngine._load_data()` queries `market_data` first, falls back to `daily_data`.

### Strategy system (`quantsys/strategy/`)
- All strategies implement `BaseStrategy` ABC with `on_bar(BarEvent) -> dict` plus `on_start`/`on_stop` hooks.
- `StrategyLoader` loads arbitrary `.py` files at runtime via `importlib.util`.
- `StrategyOptimizer` uses `scikit-optimize` Bayesian search (`gp_minimize`); runs a full backtest per candidate, minimises negative of chosen metric.

### Agent / chat (`quantsys/agent/`, `quantsys/cli/chat_mode.py`)
- `ChatInterface` (prompt_toolkit REPL): slash commands load skills, `@file` inlines file content into the LLM message.
- Skills are directories with a `SKILL.md` (YAML frontmatter: `name`, `description`, `commands`). `SkillRegistry` discovers them by walking `quantsys/skills/` and any `user_skills/` directory.
- When `/command` is typed, `Agent.load_skill()` injects the full `SKILL.md` into `ContextManager` as a system message. Any text typed after the command on the same line is forwarded to the LLM immediately.
- `LLMClient` abstracts Anthropic and OpenAI-compatible APIs; provider selected by `LLM_PROVIDER` in `.env`.

### Factor library (`quantsys/factor/`)
- `operators.py` — ~30 pandas-based operators (rank, delta, ts_corr, etc.) used to compose factors.
- `library/wq101.py` — 20 WorldQuant 101 alpha implementations. Each function takes a DataFrame and returns a Series.
- `definitions/*.yaml` — YAML catalog with factor metadata (name, formula, description, data requirements). Agent reads these for context injection.
- `registry.py` — Discovers YAML definitions, resolves `compute_fn` to Python callables. Provides `get_summary()` (Level 2) and `get_detail()` (Level 3) for progressive agent context.
- `engine.py` — Computes factors: `compute(factor_id, df)` for single, `compute_batch(ids, df)` for multiple. BacktestEngine calls this automatically when strategy declares `required_factors`.

### Settings (`quantsys/config/settings.py`)
`pydantic-settings` `BaseSettings`, reads from `.env`. `get_settings()` is `@lru_cache`-wrapped. Key vars: `ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `DATABASE_PATH` (default `data/quantsys.db`).

## Key conventions

- **Database writes must commit**: use `db.executemany()` or `db.execute()` directly — both auto-commit. The `transaction()` context manager is for multi-statement atomic blocks.
- **Skill SKILL.md frontmatter** must include `commands:` list (slash-prefixed strings, e.g. `/data`) for the completer and registry to pick them up.
- The completion menu style is overridden to `noinherit` to suppress prompt_toolkit's default gray background. Use `CompleteStyle.MULTI_COLUMN`.
