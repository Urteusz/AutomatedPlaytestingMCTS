"""Canonical project data paths used by local adapters."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
RULES_DIR = DATA_DIR / "rules"
MD2_BENCHMARK_DIR = DATA_DIR / "maps" / "md2" / "benchmark"
DEFAULT_RULES_PATH = RULES_DIR / "md2_rules.json"
