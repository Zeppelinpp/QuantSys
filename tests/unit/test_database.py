"""Tests for database module."""

import os
import tempfile
from pathlib import Path

import pytest

from quantsys.data.database import Database


class TestDatabase:
    """Test database functionality."""

    def test_init_creates_tables(self):
        """Test that init creates all required tables."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db = Database(db_path)
            db.create_tables()

            # Check tables exist
            tables = db.list_tables()
            assert "market_data" in tables
            assert "daily_data" in tables
            assert "factors" in tables
            assert "strategies" in tables
            assert "backtest_results" in tables
            assert "paper_accounts" in tables
            assert "paper_trades" in tables
        finally:
            os.unlink(db_path)

    def test_singleton_connection(self):
        """Test that Database is a singleton per path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db1 = Database(db_path)
            db2 = Database(db_path)
            assert db1 is db2
        finally:
            os.unlink(db_path)

    def test_execute_and_fetch(self):
        """Test execute and fetch operations."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db = Database(db_path)
            db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO test (name) VALUES (?)", ("test_name",))

            result = db.fetchone("SELECT * FROM test WHERE name = ?", ("test_name",))
            assert result is not None
            assert result["name"] == "test_name"
        finally:
            os.unlink(db_path)

    def test_transaction_rollback(self):
        """Test transaction rollback on error."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db = Database(db_path)
            db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value INTEGER UNIQUE)")

            try:
                with db.transaction() as conn:
                    conn.execute("INSERT INTO test (value) VALUES (1)")
                    conn.execute("INSERT INTO test (value) VALUES (1)")  # Duplicate
            except Exception:
                pass

            # Should have 0 rows due to rollback
            result = db.fetchone("SELECT COUNT(*) as count FROM test")
            assert result["count"] == 0
        finally:
            os.unlink(db_path)
