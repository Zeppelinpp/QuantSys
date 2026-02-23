"""Tests for factor registry."""

import pytest

from quantsys.factor.registry import FactorMeta, FactorRegistry


@pytest.fixture
def registry():
    r = FactorRegistry()
    r.discover()
    return r


class TestFactorRegistry:
    def test_discover_loads_factors(self, registry):
        factors = registry.list_factors()
        assert len(factors) == 20

    def test_get_existing_factor(self, registry):
        meta = registry.get("WQ002")
        assert meta is not None
        assert meta.name == "Alpha#002"
        assert meta.category == "reversal"
        assert "close" in meta.data_requirements

    def test_get_nonexistent_factor(self, registry):
        assert registry.get("NONEXIST") is None

    def test_list_by_category(self, registry):
        momentum = registry.list_factors(category="momentum")
        assert len(momentum) == 7
        assert all(f.category == "momentum" for f in momentum)

    def test_search(self, registry):
        results = registry.search("volume")
        assert len(results) > 0

    def test_get_summary(self, registry):
        summary = registry.get_summary()
        assert "WQ002" in summary
        assert "reversal" in summary

    def test_get_detail(self, registry):
        detail = registry.get_detail(["WQ002", "WQ017"])
        assert "formula" in detail
        assert "compute_fn" in detail
        assert "WQ002" in detail
        assert "WQ017" in detail

    def test_compute_fn_resolvable(self, registry):
        meta = registry.get("WQ002")
        module_path, func_name = meta.compute_fn.rsplit(":", 1)
        import importlib

        mod = importlib.import_module(module_path)
        assert hasattr(mod, func_name)
