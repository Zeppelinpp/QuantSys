"""Tests for data validator."""

import pandas as pd
import pytest

from quantsys.data.validator import DataValidator, ValidationError


class TestDataValidator:
    """Test data validation functionality."""

    def test_validate_ohlc_valid(self):
        """Test OHLC validation with valid data."""
        df = pd.DataFrame({
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
        })

        validator = DataValidator()
        errors = validator.validate_ohlc(df)
        assert len(errors) == 0

    def test_validate_ohlc_invalid_low_high(self):
        """Test OHLC validation with low > high."""
        df = pd.DataFrame({
            "open": [10.0],
            "high": [9.0],  # high < low
            "low": [11.0],
            "close": [10.0],
        })

        validator = DataValidator()
        errors = validator.validate_ohlc(df)
        # Expect 3 errors: low/high, open outside range, close outside range
        assert len(errors) == 3
        assert errors[0].error_type == "ohlc_logic"
        assert "low" in errors[0].message and "high" in errors[0].message

    def test_validate_ohlc_open_outside_range(self):
        """Test OHLC validation with open outside low-high range."""
        df = pd.DataFrame({
            "open": [15.0],  # open > high
            "high": [12.0],
            "low": [10.0],
            "close": [11.0],
        })

        validator = DataValidator()
        errors = validator.validate_ohlc(df)
        assert len(errors) == 1
        assert errors[0].column == "open"

    def test_validate_price_range(self):
        """Test price range validation."""
        df = pd.DataFrame({
            "open": [10.0, 0.0, 20000.0],
            "high": [11.0, 5.0, 25000.0],
            "low": [9.0, -1.0, 15000.0],
            "close": [10.5, 2.0, 22000.0],
        })

        validator = DataValidator()
        errors = validator.validate_price_range(df, min_price=0.01, max_price=10000.0)

        # Should have errors for row 1 (zero and negative) and row 2 (above max)
        assert len(errors) > 0

    def test_validate_volume(self):
        """Test volume validation."""
        df = pd.DataFrame({
            "volume": [1000, 0, -100],
        })

        validator = DataValidator()
        errors = validator.validate_volume(df)

        assert len(errors) == 1
        assert errors[0].column == "volume"
        assert errors[0].error_type == "volume_negative"

    def test_full_validation(self):
        """Test complete validation flow."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="min"),
            "open": [10.0, 11.0, 12.0],
            "high": [11.0, 12.0, 13.0],
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "volume": [1000, 2000, 3000],
        })

        validator = DataValidator()
        result = validator.validate(df)

        assert result["is_valid"] is True
        assert result["error_count"] == 0
        assert result["total_rows"] == 3
