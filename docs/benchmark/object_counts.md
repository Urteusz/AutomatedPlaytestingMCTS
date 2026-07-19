# Object counts in frozen reconstructed maps

Status: **validated against Fig. 3 and frozen as `md2-reconstructed-v1`**.

## Dimensions

| Map | Rows | Cols | Decision |
| --- | ---: | ---: | --- |
| map01 | 20 | 10 | standard MD2 size |
| map02 | 20 | 10 | standard MD2 size |
| map03 | 20 | 10 | standard MD2 size |
| map04 | 20 | 10 | standard MD2 size |
| map05 | 14 | 11 | grid-confirmed published-image exception |
| map06 | 20 | 10 | standard MD2 size |
| map07 | 20 | 10 | standard MD2 size |
| map08 | 20 | 10 | standard MD2 size |
| map09 | 20 | 10 | standard MD2 size |
| map10 | 20 | 10 | standard MD2 size |
| map11 | 20 | 10 | standard MD2 size |

## Interactive objects from Fig. 3

| Map | r | p | g | w | M | b | o | Total | Fig. 3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| map01 | 2 | 2 | 7 | 1 | 1 | 2 | 0 | 15 | match |
| map02 | 5 | 5 | 3 | 2 | 2 | 2 | 2 | 21 | match |
| map03 | 8 | 4 | 4 | 2 | 1 | 3 | 1 | 23 | match |
| map04 | 8 | 8 | 2 | 6 | 1 | 1 | 2 | 28 | match |
| map05 | 4 | 7 | 2 | 2 | 1 | 1 | 1 | 18 | match |
| map06 | 7 | 4 | 2 | 3 | 1 | 2 | 1 | 20 | match |
| map07 | 7 | 4 | 1 | 4 | 1 | 2 | 1 | 20 | match |
| map08 | 7 | 5 | 3 | 3 | 1 | 2 | 1 | 22 | match |
| map09 | 7 | 2 | 2 | 2 | 1 | 2 | 0 | 16 | match |
| map10 | 7 | 4 | 1 | 4 | 1 | 2 | 1 | 20 | match |
| map11 | 7 | 4 | 4 | 2 | 1 | 3 | 1 | 22 | match |

Legend: `r` treasure, `p` potion, `g` melee goblin, `w` wizard,
`M` minitaur, `b` blob, `o` ogre.

## Portals and traps (not included in Fig. 3 totals)

| Map | P | ^ |
| --- | ---: | ---: |
| map01 | 2 | 1 |
| map02 | 2 | 1 |
| map03 | 0 | 0 |
| map04 | 0 | 0 |
| map05 | 0 | 0 |
| map06 | 2 | 0 |
| map07 | 2 | 2 |
| map08 | 2 | 1 |
| map09 | 0 | 0 |
| map10 | 2 | 3 |
| map11 | 2 | 1 |

The article-level invariants are satisfied:

- seven maps contain one portal pair,
- six maps contain at least one trap,
- every map contains a Minitaur,
- map02 contains two Minitaurs,
- map01 and map09 contain no ogres,
- map04 and map10 contain more wizards than melee goblins,
- map01 contains more melee goblins than wizards.
