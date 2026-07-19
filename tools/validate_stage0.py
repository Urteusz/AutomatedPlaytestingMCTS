"""Validate the frozen MiniDungeons 2 reconstructed benchmark (Stage 0)."""

from __future__ import annotations

from collections import Counter, deque
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAP_DIR = ROOT / "data" / "maps" / "md2" / "benchmark"
MANIFEST_PATH = MAP_DIR / "benchmark_manifest.json"
PORTAL_PAIRS_PATH = MAP_DIR / "portal_pairs.json"
ALLOWED_SYMBOLS = set("#.EXrpP^gwboM")
EXPECTED_MAP_IDS = [f"map{i:02d}" for i in range(1, 12)]


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_rows(path: Path) -> list[str]:
    with path.open(encoding="utf-8") as handle:
        return [line.rstrip("\r\n") for line in handle if line.strip()]


def _normalized_layout_hash(rows: list[str]) -> str:
    # hash po znormalizowanych liniach, zeby koncowki CRLF nie psuly sum
    data = ("\n".join(rows) + "\n").encode("utf-8")
    return sha256(data).hexdigest()


def _positions(rows: list[str], symbol: str) -> list[list[int]]:
    return [
        [row, column]
        for row, line in enumerate(rows)
        for column, value in enumerate(line)
        if value == symbol
    ]


def _reachable(rows: list[str], start: tuple[int, int]) -> set[tuple[int, int]]:
    reached = {start}
    queue = deque([start])
    while queue:
        row, column = queue.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = row + dr, column + dc
            if not (0 <= nr < len(rows) and 0 <= nc < len(rows[nr])):
                continue
            if rows[nr][nc] == "#" or (nr, nc) in reached:
                continue
            reached.add((nr, nc))
            queue.append((nr, nc))
    return reached


def validate_benchmark() -> tuple[list[str], list[str]]:
    """Return (errors, summaries) without modifying the benchmark."""
    errors: list[str] = []
    summaries: list[str] = []

    try:
        manifest = _read_json(MANIFEST_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read {MANIFEST_PATH}: {exc}"], []
    try:
        portal_data = _read_json(PORTAL_PAIRS_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read {PORTAL_PAIRS_PATH}: {exc}"], []

    if manifest.get("benchmark_id") != "md2-reconstructed-v1":
        errors.append("unexpected benchmark_id")

    manifest_maps = manifest.get("maps", {})
    portal_maps = portal_data.get("maps", {})
    if sorted(manifest_maps) != EXPECTED_MAP_IDS:
        errors.append("manifest must contain exactly map01 through map11")
    unknown_portal_maps = sorted(set(portal_maps) - set(EXPECTED_MAP_IDS))
    if unknown_portal_maps:
        errors.append(f"portal_pairs references unknown maps: {unknown_portal_maps}")
    empty_portal_maps = sorted(map_id for map_id, pairs in portal_maps.items() if not pairs)
    if empty_portal_maps:
        errors.append(
            f"portal_pairs must omit maps without portals instead of empty records: {empty_portal_maps}"
        )

    actual_layouts = sorted(path.stem for path in MAP_DIR.glob("map??.txt"))
    if actual_layouts != EXPECTED_MAP_IDS:
        errors.append(f"layout files differ from expected set: {actual_layouts}")

    for map_id in EXPECTED_MAP_IDS:
        cfg = manifest_maps.get(map_id)
        if not isinstance(cfg, dict):
            continue

        layout_path = MAP_DIR / cfg["layout"]
        try:
            rows = _read_rows(layout_path)
        except OSError as exc:
            errors.append(f"{map_id}: cannot read layout: {exc}")
            continue

        expected_rows = cfg["rows"]
        expected_columns = cfg["columns"]
        widths = {len(row) for row in rows}
        if len(rows) != expected_rows:
            errors.append(f"{map_id}: rows {len(rows)} != {expected_rows}")
        if widths != {expected_columns}:
            errors.append(f"{map_id}: row widths {sorted(widths)} != [{expected_columns}]")

        counter = Counter("".join(rows))
        unknown = sorted(set(counter) - ALLOWED_SYMBOLS)
        if unknown:
            errors.append(f"{map_id}: unknown symbols {unknown}")
        if counter["E"] != 1 or counter["X"] != 1:
            errors.append(f"{map_id}: expected one E and one X")

        if _normalized_layout_hash(rows) != cfg["layout_sha256"]:
            errors.append(f"{map_id}: layout hash differs from frozen v1")

        actual_portals = sorted(_positions(rows, "P"))
        configured_pairs = portal_maps.get(map_id, [])
        configured_portals = sorted(
            position for pair in configured_pairs for position in pair
        )
        if any(len(pair) != 2 for pair in configured_pairs):
            errors.append(f"{map_id}: every portal pair must have two endpoints")
        if len({tuple(position) for position in configured_portals}) != len(
            configured_portals
        ):
            errors.append(f"{map_id}: a portal endpoint is used more than once")
        if actual_portals != configured_portals:
            errors.append(
                f"{map_id}: portal metadata {configured_portals} != map {actual_portals}"
            )

        entrances = _positions(rows, "E")
        exits = _positions(rows, "X")
        if len(entrances) == 1 and len(exits) == 1 and len(widths) == 1:
            reached = _reachable(rows, tuple(entrances[0]))
            passable = {
                (row, column)
                for row, line in enumerate(rows)
                for column, value in enumerate(line)
                if value != "#"
            }
            if tuple(exits[0]) not in reached:
                errors.append(f"{map_id}: exit is unreachable from entrance")
            if reached != passable:
                errors.append(
                    f"{map_id}: {len(passable - reached)} passable tiles are disconnected"
                )

        summaries.append(
            f"{map_id}: {len(rows)}x{next(iter(widths), 0)}, "
            f"objects={sum(counter[s] for s in 'rpgwboM')}, "
            f"portals={counter['P']}, traps={counter['^']}"
        )

    return errors, summaries


def main() -> int:
    errors, summaries = validate_benchmark()
    for summary in summaries:
        print(summary)
    if errors:
        print("\nSTAGE 0 VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("\nSTAGE 0 OK: md2-reconstructed-v1 is internally consistent and frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
