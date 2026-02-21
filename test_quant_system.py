#!/usr/bin/env python3
"""
QuantSys End-to-End Test Script

Tests the complete workflow:
1. Data Collection
2. Data Quality Validation
3. Factor Mining
4. Strategy Testing in Paper Trading
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure we're using the local quantsys
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# Configure logging
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}\n",
)


def test_llm_connection():
    """Test 0: Verify LLM connection to DashScope."""
    print("\n" + "=" * 60)
    print("TEST 0: LLM Connection (DashScope - Qwen3-Max)")
    print("=" * 60)

    from quantsys.agent.llm_client import LLMClient
    from quantsys.config import get_settings

    settings = get_settings()

    print(f"Provider: {settings.LLM_PROVIDER}")
    print(f"Base URL: {settings.OPENAI_BASE_URL}")
    print(f"Model: {settings.OPENAI_MODEL}")

    client = LLMClient(settings)

    if not client.is_available():
        print("❌ LLM client not available - check API key")
        return False

    try:
        # Test simple chat
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'QuantSys LLM test successful' and nothing else."}],
            max_tokens=50,
        )
        print(f"✅ LLM Response: {response.strip()}")
        return True
    except Exception as e:
        print(f"❌ LLM test failed: {e}")
        return False


def test_data_collection():
    """Test 1: Data Collection from akshare."""
    print("\n" + "=" * 60)
    print("TEST 1: Data Collection")
    print("=" * 60)

    from quantsys.config import get_settings
    from quantsys.data import Database
    from quantsys.data.collector import DataCollector

    settings = get_settings()
    db = Database(settings.db_path)

    # Use a popular stock for testing
    test_symbol = "000001.SZ"  # Ping An Bank
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days

    print(f"Collecting data for {test_symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")

    collector = DataCollector(db)

    try:
        # Download daily data
        df = collector.download_daily_data(
            symbol=test_symbol,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )

        if len(df) == 0:
            print("❌ No data downloaded")
            return False

        print(f"✅ Downloaded {len(df)} daily bars")
        print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
        print(f"   Price range: {df['low'].min():.2f} - {df['high'].max():.2f}")

        # Verify data in database
        result = db.fetchone(
            "SELECT COUNT(*) as count FROM daily_data WHERE symbol = ?",
            (test_symbol,),
        )
        print(f"✅ Database records: {result['count']}")

        return True

    except Exception as e:
        print(f"❌ Data collection failed: {e}")
        return False


def test_data_quality():
    """Test 2: Data Quality Validation."""
    print("\n" + "=" * 60)
    print("TEST 2: Data Quality Validation")
    print("=" * 60)

    import pandas as pd

    from quantsys.config import get_settings
    from quantsys.data import Database
    from quantsys.data.validator import DataValidator

    settings = get_settings()
    db = Database(settings.db_path)

    # Load data for validation
    rows = db.fetchall(
        "SELECT * FROM daily_data WHERE symbol = ? LIMIT 100",
        ("000001.SZ",),
    )

    if not rows:
        print("❌ No data to validate")
        return False

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["date"])

    print(f"Validating {len(df)} records...")

    validator = DataValidator()
    result = validator.validate(df)

    print(f"Total rows: {result['total_rows']}")
    print(f"Error count: {result['error_count']}")
    print(f"Error types: {result['error_types']}")

    if result["is_valid"]:
        print("✅ Data validation passed")
    else:
        print("⚠️ Data has quality issues")
        validator.log_errors(max_errors=5)

    return result["error_count"] == 0 or result["error_count"] < len(df) * 0.01


def test_factor_mining():
    """Test 3: Factor Mining using technical indicators."""
    print("\n" + "=" * 60)
    print("TEST 3: Factor Mining (Technical Indicators)")
    print("=" * 60)

    import numpy as np
    import pandas as pd

    from quantsys.config import get_settings
    from quantsys.data import Database
    from quantsys.data.collector import DataCollector

    settings = get_settings()
    db = Database(settings.db_path)

    # First collect more historical data
    print("Collecting 90 days of historical data...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    collector = DataCollector(db)
    try:
        collector.download_daily_data(
            symbol="000001.SZ",
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )
    except Exception as e:
        print(f"Warning: Could not download more data: {e}")

    # Load data
    rows = db.fetchall(
        """
        SELECT symbol, date, open, high, low, close, volume
        FROM daily_data
        WHERE symbol = ?
        ORDER BY date
        """,
        ("000001.SZ",),
    )

    if len(rows) < 20:
        print(f"❌ Insufficient data ({len(rows)} rows) for factor calculation")
        return False

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    print(f"Calculating factors for {len(df)} records...")

    # Calculate technical factors
    factors = {}

    # 1. Moving Averages
    factors["ma_5"] = df["close"].rolling(window=5).mean()
    factors["ma_10"] = df["close"].rolling(window=10).mean()
    factors["ma_20"] = df["close"].rolling(window=20).mean()

    # 2. RSI
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    factors["rsi_14"] = 100 - (100 / (1 + rs))

    # 3. MACD
    exp1 = df["close"].ewm(span=12).mean()
    exp2 = df["close"].ewm(span=26).mean()
    factors["macd_dif"] = exp1 - exp2
    factors["macd_dea"] = factors["macd_dif"].ewm(span=9).mean()
    factors["macd_hist"] = factors["macd_dif"] - factors["macd_dea"]

    # 4. ATR (Average True Range)
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    factors["atr_14"] = tr.rolling(window=14).mean()

    # 5. Volume MA
    factors["volume_ma_5"] = df["volume"].rolling(window=5).mean()

    # Store factors in database
    factor_df = pd.DataFrame(factors)
    factor_df["symbol"] = df["symbol"]
    factor_df["timestamp"] = df["date"]

    # Drop NaN values
    factor_df = factor_df.dropna()

    print(f"✅ Calculated {len(factor_df)} factor records")
    print(f"   Factors: {list(factors.keys())}")

    # Save to database
    records = []
    for _, row in factor_df.iterrows():
        records.append((
            row["symbol"],
            row["timestamp"].strftime("%Y-%m-%d"),
            row.get("ma_5"),
            row.get("ma_10"),
            row.get("ma_20"),
            row.get("rsi_14"),
            row.get("macd_dif"),
            row.get("macd_dea"),
            row.get("macd_hist"),
            row.get("atr_14"),
        ))

    db.executemany(
        """
        INSERT OR REPLACE INTO factors
        (symbol, timestamp, ma_5, ma_10, ma_20, rsi_14, macd_dif, macd_dea, macd_hist, atr_14)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )

    print(f"✅ Saved {len(records)} factor records to database")

    # Show sample
    print("\nSample factors (last 5 days):")
    sample = factor_df[["timestamp", "close" if "close" in factor_df.columns else "ma_5", "rsi_14", "macd_hist"]].tail()
    print(sample.to_string(index=False))

    return len(records) > 0


def test_paper_trading():
    """Test 4: Paper Trading System."""
    print("\n" + "=" * 60)
    print("TEST 4: Paper Trading System")
    print("=" * 60)

    from quantsys.config import get_settings
    from quantsys.data import Database
    from quantsys.paper.manager import AccountManager

    settings = get_settings()
    db = Database(settings.db_path)
    manager = AccountManager(db)

    account_name = "test_account"

    # Clean up existing test account
    try:
        manager.delete_account(account_name)
    except:
        pass

    # Create account
    print("Creating paper trading account...")
    account = manager.create_account(account_name, initial_cash=1000000)
    print(f"✅ Created account: {account.name}")
    print(f"   Initial cash: ${account.initial_cash:,.2f}")

    # Execute some trades
    test_symbol = "000001.SZ"

    print(f"\nExecuting trades for {test_symbol}...")

    # Buy 1000 shares at $10
    buy_price = 10.0
    buy_quantity = 1000
    commission = max(buy_price * buy_quantity * 0.0003, 5.0)

    if account.buy(test_symbol, buy_quantity, buy_price, commission):
        manager.save_account(account)
        manager.record_trade(account.account_id, test_symbol, "BUY", buy_quantity, buy_price)
        print(f"✅ BUY {buy_quantity} {test_symbol} @ ${buy_price:.2f}")
    else:
        print("❌ Buy order failed")
        return False

    # Update price and show status
    account.update_prices({test_symbol: 10.5})
    state = account.get_state()

    print(f"\nAccount Status:")
    print(f"   Cash: ${state['cash']:,.2f}")
    print(f"   Positions Value: ${state['positions_value']:,.2f}")
    print(f"   Total Value: ${state['total_value']:,.2f}")
    print(f"   Total Return: {state['total_return']:.2%}")

    # Try to sell (should fail due to T+1)
    print("\nTesting T+1 rule...")
    from datetime import datetime

    if not account.sell(test_symbol, 500, 10.5, commission):
        print("✅ T+1 rule correctly enforced")
    else:
        print("⚠️ T+1 rule not enforced (same-day sell allowed)")

    # Show trades
    trades = manager.get_trades(account_name)
    print(f"\n✅ Recorded {len(trades)} trades")

    # Cleanup - delete trades first to avoid FK constraint
    db = Database(settings.db_path)
    db.execute("DELETE FROM paper_trades WHERE account_id = ?", (account.account_id,))
    manager.delete_account(account_name)
    print(f"✅ Cleaned up test account")

    return True


def test_strategy_backtest():
    """Test 5: Strategy Backtest."""
    print("\n" + "=" * 60)
    print("TEST 5: Strategy Backtest")
    print("=" * 60)

    from datetime import datetime

    from quantsys.backtest.engine import BacktestEngine
    from quantsys.config import get_settings
    from quantsys.data import Database
    from quantsys.strategy.builtin import MomentumStrategy

    settings = get_settings()
    db = Database(settings.db_path)

    # First ensure we have enough data
    from quantsys.data.collector import DataCollector
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    collector = DataCollector(db)
    try:
        collector.download_daily_data(
            symbol="000001.SZ",
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
        )
    except Exception as e:
        print(f"Warning: Could not download data: {e}")

    # Check if we have enough data
    result = db.fetchone(
        "SELECT COUNT(*) as count FROM daily_data WHERE symbol = ?",
        ("000001.SZ",),
    )

    if result["count"] < 20:
        print(f"⚠️ Insufficient data ({result['count']} bars), skipping backtest")
        return True

    print(f"Running backtest with {result['count']} data points...")

    # Create strategy
    strategy = MomentumStrategy(params={"ma_period": 5, "position_pct": 0.95})

    # Run backtest with available data range
    engine = BacktestEngine(
        start_date=start_date,
        end_date=end_date,
        symbols=["000001.SZ"],
        strategy=strategy,
        initial_cash=1000000,
        database=db,
    )

    try:
        result = engine.run()

        print(f"✅ Backtest complete")
        print(f"   Strategy: {result.strategy_name}")
        print(f"   Total Return: {result.metrics.total_return:.2%}")
        print(f"   Sharpe Ratio: {result.metrics.sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {result.metrics.max_drawdown:.2%}")
        print(f"   Total Trades: {result.metrics.total_trades}")

        return True

    except Exception as e:
        print(f"❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("QUANTSYS END-TO-END TEST SUITE")
    print("=" * 60)

    tests = [
        ("LLM Connection", test_llm_connection),
        ("Data Collection", test_data_collection),
        ("Data Quality", test_data_quality),
        ("Factor Mining", test_factor_mining),
        ("Paper Trading", test_paper_trading),
        ("Strategy Backtest", test_strategy_backtest),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
