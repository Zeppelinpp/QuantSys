"""Tests for symbol manager."""

import pytest

from quantsys.data.symbols import SymbolManager


class TestSymbolManager:
    """Test symbol management functionality."""

    def test_parse_symbol_standard_format(self):
        """Test parsing standard symbol format."""
        manager = SymbolManager()

        code, exchange = manager.parse_symbol("000001.SZ")
        assert code == "000001"
        assert exchange == "SZ"

        code, exchange = manager.parse_symbol("600000.SH")
        assert code == "600000"
        assert exchange == "SH"

    def test_parse_symbol_akshare_format(self):
        """Test parsing akshare format."""
        manager = SymbolManager()

        code, exchange = manager.parse_symbol("sz000001")
        assert code == "000001"
        assert exchange == "SZ"

        code, exchange = manager.parse_symbol("sh600000")
        assert code == "600000"
        assert exchange == "SH"

    def test_parse_symbol_code_only(self):
        """Test parsing code-only format."""
        manager = SymbolManager()

        # Shanghai stocks start with 6
        code, exchange = manager.parse_symbol("600000")
        assert code == "600000"
        assert exchange == "SH"

        # Shenzhen stocks
        code, exchange = manager.parse_symbol("000001")
        assert code == "000001"
        assert exchange == "SZ"

    def test_to_akshare_format(self):
        """Test conversion to akshare format."""
        manager = SymbolManager()

        assert manager.to_akshare_format("000001.SZ") == "sz000001"
        assert manager.to_akshare_format("600000.SH") == "sh600000"

    def test_from_akshare_format(self):
        """Test conversion from akshare format."""
        manager = SymbolManager()

        assert manager.from_akshare_format("sz000001") == "000001.SZ"
        assert manager.from_akshare_format("sh600000") == "600000.SH"

    def test_from_akshare_format_invalid(self):
        """Test invalid akshare format raises error."""
        manager = SymbolManager()

        with pytest.raises(ValueError):
            manager.from_akshare_format("invalid")
