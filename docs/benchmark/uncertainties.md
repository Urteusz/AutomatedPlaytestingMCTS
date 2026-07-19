# MD2 benchmark audit decisions and accepted uncertainties

Status: **Stage 0 complete; benchmark `md2-reconstructed-v1` frozen on
2026-07-19**.

## What "frozen" means

All 11 local images, their grid overlays, the reconstructed TXT layouts and
Fig. 2/3 of the MCTS article were reviewed together. The benchmark passes the
automated validator and is ready to be used consistently by every agent.

It remains a methodological reconstruction. Freezing it does not claim that
its hidden floor tiles or ambiguous sprite bases are byte-identical to the
unavailable original MD2 map files.

## Corrections made during the final audit

Coordinates use zero-based `[row, column]`.

| Map | Coordinate | Final decision | Evidence |
| --- | --- | --- | --- |
| map04 | `[11, 8]` | add potion | second potion is visible above the stacked wizard sprites; required for Fig. 3 count 8 |
| map04 | `[14, 5]` | floor -> wall | source image shows a wall at one-based row 15, column 6; the correction changes topology but not object counts |
| map07 | `[8, 2]` | move Minitaur logical base | the 10x20 grid places the upper sprite over a wall in row 7 and its lower body/base on the floor in row 8 |
| map08 | `[4, 8]` | ogre -> floor | this is the upper part of the single ogre whose base is `[5, 8]`; Fig. 3 count is 1 |
| map09 | `[1, 3]` | wall -> treasure | chest is visible behind the upper Minitaur sprite; required for Fig. 3 count 7 |
| map11 | `[1, 6]` | wall -> treasure | chest is visible behind the upper Minitaur sprite; required for Fig. 3 count 7 |
| map11 | `[5, 8]` | wall -> treasure | chest is visible at the right edge of the corridor; required for Fig. 3 count 7 |

## Map 5 decision

`map05.txt` has 11 columns by 14 rows and is accepted for benchmark v1. The
explicit overlay `data/maps/md2/source-images/map5_grid_11x14.png` exposes 11 complete
columns and 14 complete rows. It also confirms the internal four-cell wall
segments and the vertical wall at column 7 that were lost in the earlier
10x13 transcription. Map 5 remains visibly smaller than the standard maps in
published Fig. 2, so the non-standard 11x14 dimensions must be reported in the
thesis.

The grid confirms the final lower-row positions: exit `[11, 7]`, Minitaur
`[12, 6]`, goblin `[12, 7]` and potion `[12, 9]`. The content originally
audited as `map05_copy.txt` was promoted to the canonical `map05.txt`; the exit
symbol was normalized from lowercase `x` to the format's required uppercase
`X`.

## Confidence and acceptance

| Map | Confidence | Benchmark decision |
| --- | --- | --- |
| map01 | high | accepted |
| map02 | medium | accepted |
| map03 | medium-high | accepted |
| map04 | medium | accepted after potion correction |
| map05 | high | accepted as grid-confirmed 11x14 exception |
| map06 | medium | accepted |
| map07 | high | accepted after grid-confirmed Minitaur correction |
| map08 | medium | accepted after ogre correction |
| map09 | medium-high | accepted after treasure correction |
| map10 | medium | accepted |
| map11 | medium | accepted after treasure corrections |

## Remaining methodological limitations

- Original textual MD2 maps are unavailable.
- Large sprites obscure some floor/wall backgrounds and overlap adjacent visual
  rows; deterministic logical tiles were chosen from sprite bases and corridor
  continuity.
- The visual layer does not label portal IDs. Every portal map contains exactly
  two portals, so each map has one unambiguous pair, frozen in
  `portal_pairs.json`.
- Rare gameplay collisions, line of sight and NPC tie-breakers are engine-rule
  decisions, not unresolved map data. They belong to Stage 1.
- Any later map correction requires a new benchmark version and updated hashes;
  `md2-reconstructed-v1` must not be silently changed after experiments begin.

## Validation command

```text
python tools/validate_stage0.py
```

A successful run confirms dimensions, symbols, Fig. 3 counts, article-level
invariants, portal pairings, connectivity, source images and frozen hashes.
