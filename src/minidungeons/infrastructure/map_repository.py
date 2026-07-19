"""Read-only catalog of the frozen MiniDungeons 2 benchmark maps."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..errors import MapNotFoundError
from .paths import MD2_BENCHMARK_DIR


@dataclass(frozen=True)
class MapInfo:
    """Public metadata and resolved layout path for one map."""

    map_id: str
    path: Path
    rows: int
    columns: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.map_id,
            "rows": self.rows,
            "columns": self.columns,
        }


class MapRepository:
    """Load map metadata from the benchmark manifest and resolve safe paths."""

    def __init__(self, benchmark_dir: str | Path | None = None) -> None:
        self.benchmark_dir = Path(benchmark_dir or MD2_BENCHMARK_DIR).resolve()
        self.manifest_path = self.benchmark_dir / "benchmark_manifest.json"
        self._manifest = self._read_manifest()
        self._maps = self._build_catalog()

    @property
    def benchmark_id(self) -> str:
        return str(self._manifest["benchmark_id"])

    def list(self) -> tuple[MapInfo, ...]:
        return tuple(self._maps[map_id] for map_id in sorted(self._maps))

    def get(self, map_id: str) -> MapInfo:
        try:
            return self._maps[map_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._maps))
            raise MapNotFoundError(f"Unknown map {map_id!r}; available: {available}") from exc

    def _read_manifest(self) -> dict[str, Any]:
        try:
            with self.manifest_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot load benchmark manifest {self.manifest_path}: {exc}") from exc
        if not isinstance(data.get("maps"), dict) or not data.get("benchmark_id"):
            raise RuntimeError(f"Invalid benchmark manifest: {self.manifest_path}")
        return data

    def _build_catalog(self) -> dict[str, MapInfo]:
        catalog: dict[str, MapInfo] = {}
        for map_id, raw in self._manifest["maps"].items():
            layout = (self.benchmark_dir / raw["layout"]).resolve()
            # layout ma lezec w katalogu benchmarku, bez sciezek na zewnatrz
            if layout.parent != self.benchmark_dir or not layout.is_file():
                raise RuntimeError(f"Unsafe or missing layout for {map_id}: {layout}")
            catalog[map_id] = MapInfo(
                map_id=map_id,
                path=layout,
                rows=int(raw["rows"]),
                columns=int(raw["columns"]),
            )
        return catalog
