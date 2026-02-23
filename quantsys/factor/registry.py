"""Factor registry — discovers and indexes YAML factor definitions."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class FactorMeta:
    """Metadata for a single factor."""

    id: str
    name: str
    source: str
    category: str
    formula: str
    description: str
    data_requirements: List[str]
    lookback_window: int
    compute_fn: str
    tags: List[str] = field(default_factory=list)
    notes: str = ""


class FactorRegistry:
    """Registry that discovers and indexes factor definitions from YAML files."""

    def __init__(self) -> None:
        self._factors: Dict[str, FactorMeta] = {}

    def discover(self) -> None:
        """Scan YAML files in the definitions directory and load all factors."""
        defs_dir = Path(__file__).parent / "definitions"
        if not defs_dir.exists():
            return

        for yaml_file in sorted(defs_dir.glob("*.yaml")):
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "factors" not in data:
                continue

            for entry in data["factors"]:
                meta = FactorMeta(
                    id=entry["id"],
                    name=entry["name"],
                    source=entry["source"],
                    category=entry["category"],
                    formula=entry["formula"],
                    description=entry["description"],
                    data_requirements=entry["data_requirements"],
                    lookback_window=entry["lookback_window"],
                    compute_fn=entry["compute_fn"],
                    tags=entry.get("tags", []),
                    notes=entry.get("notes", ""),
                )
                self._factors[meta.id] = meta

    def get(self, factor_id: str) -> Optional[FactorMeta]:
        """Look up a factor by ID. Returns None if not found."""
        return self._factors.get(factor_id)

    def list_factors(self, category: Optional[str] = None) -> List[FactorMeta]:
        """List all factors, optionally filtered by category."""
        factors = list(self._factors.values())
        if category is not None:
            factors = [f for f in factors if f.category == category]
        return factors

    def search(self, query: str) -> List[FactorMeta]:
        """Case-insensitive substring search on name, description, and tags."""
        q = query.lower()
        results = []
        for f in self._factors.values():
            searchable = f"{f.name} {f.description} {' '.join(f.tags)}".lower()
            if q in searchable:
                results.append(f)
        return results

    def get_summary(self) -> str:
        """Level 2 summary: one line per factor."""
        lines = []
        for f in self._factors.values():
            lines.append(f"[{f.category}] {f.id}: {f.name} - {f.description}")
        return "\n".join(lines)

    def get_detail(self, factor_ids: List[str]) -> str:
        """Level 3 detail: full definition for selected factors."""
        blocks = []
        for fid in factor_ids:
            meta = self._factors.get(fid)
            if meta is None:
                blocks.append(f"# {fid}: NOT FOUND")
                continue
            blocks.append(
                f"# {meta.id}: {meta.name}\n"
                f"source: {meta.source}\n"
                f"category: {meta.category}\n"
                f"formula: {meta.formula}\n"
                f"description: {meta.description}\n"
                f"data_requirements: {meta.data_requirements}\n"
                f"lookback_window: {meta.lookback_window}\n"
                f"compute_fn: {meta.compute_fn}\n"
                f"tags: {meta.tags}\n"
                f"notes: {meta.notes}"
            )
        return "\n\n".join(blocks)
