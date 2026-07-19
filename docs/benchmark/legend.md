# MiniDungeons 2 reconstructed map legend

Status: **frozen benchmark `md2-reconstructed-v1` (2026-07-19)**.

The layouts were reconstructed from `data/maps/md2/source-images/Map*.png` and Fig. 2 of
`docs/reference/articles/1802.06881v1_MCTS.pdf`. Object counts were checked against
Fig. 3 of the same article. This is a methodological reconstruction, not the
original MD2 data set.

## Symbols

```text
# wall / impassable tile
. floor / passable empty tile
E hero start / entrance
X exit
r treasure
p potion
P portal
^ trap
g melee goblin
w ranged goblin / wizard
b blob
o ogre
M minitaur
```

## Format decisions

- Coordinates in metadata use zero-based `[row, column]` order.
- Maps normally have 10 columns and 20 rows.
- `map05.txt` is intentionally 11 columns by 14 rows. The explicit cell overlay
  `data/maps/md2/source-images/map5_grid_11x14.png` confirms all 11 columns and 14 rows,
  including the internal wall geometry. Map 5 is therefore a smaller,
  non-standard layout despite the general 10x20 statement in the MD2 game
  description.
- Each benchmark map has exactly one `E` and one `X`.
- Portal endpoints and pairings are stored in `portal_pairs.json`.
- Large character sprites overlap neighboring visual rows. Their logical base
  tile and any object visible behind the upper sprite were assigned separately
  during the visual audit.
- The initial-layout TXT format stores one entity symbol per tile. If future
  primary evidence proves that an object and character start on the same
  logical tile, the schema must be versioned instead of silently overloading a
  character.
- The hero starts with the javelin by rule; it is not a map symbol.

## Benchmark files

- `data/maps/md2/benchmark/benchmark_manifest.json` freezes the list of
  available maps, their layout dimensions and layout hashes.
- `data/maps/md2/benchmark/portal_pairs.json` freezes portal pairings.
- `docs/benchmark/object_counts.md` is the human-readable Fig. 3 comparison.
- `docs/benchmark/uncertainties.md` records accepted limitations and audit
  decisions.
- `tools/validate_stage0.py` validates the complete frozen benchmark.
