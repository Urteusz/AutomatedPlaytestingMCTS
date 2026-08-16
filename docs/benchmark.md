# Zamrożony benchmark map `md2-reconstructed-v1`

Status: **zamrożony 2026-07-19**. Etap 0 zakończony.

Układy map zostały odtworzone z `data/maps/md2/source-images/Map*.png` i Fig. 2
artykułu `docs/reference/articles/1802.06881v1_MCTS.pdf`. Liczebności obiektów
sprawdzono względem Fig. 3 tego samego artykułu.

To rekonstrukcja metodologiczna, nie oryginalny zbiór danych MD2. Zamrożenie nie
oznacza, że ukryte kafle podłogi ani niejednoznaczne podstawy sprite'ów są
bitowo identyczne z niedostępnymi oryginalnymi plikami map.

**Każda późniejsza poprawka mapy wymaga nowej wersji benchmarku i nowych sum
kontrolnych.** `md2-reconstructed-v1` nie może być po cichu zmieniony po
rozpoczęciu eksperymentów.

## Symbole

```text
# ściana / pole nieprzechodnie
. podłoga / puste pole przechodnie
E start bohatera / wejście
X wyjście
r skarb
p mikstura
P portal
^ pułapka
g goblin walczący wręcz
w goblin dystansowy / wizard
b blob
o ogr
M minitaur
```

## Decyzje formatu

- współrzędne w metadanych używają zerowego indeksowania `[wiersz, kolumna]`;
- mapy mają standardowo 10 kolumn i 20 wierszy — z jawnym wyjątkiem `map05.txt`
  (11 × 14, patrz niżej);
- każda mapa ma dokładnie jedno `E` i jedno `X`;
- końcówki i pary portali są w `portal_pairs.json`;
- duże sprite'y postaci nachodzą na sąsiednie wiersze wizualne. Ich logiczny
  kafel bazowy oraz obiekt widoczny za górną częścią sprite'a przypisano
  osobno podczas audytu wizualnego;
- format TXT przechowuje jeden symbol na kafel. Jeśli przyszłe dowody wykażą,
  że obiekt i postać startują na tym samym kaflu logicznym, schemat trzeba
  zwersjonować, a nie po cichu przeciążać znak postaci;
- bohater startuje z oszczepem z reguły gry; oszczep nie jest symbolem mapy.

## Wymiary

| Mapa | Wiersze | Kolumny | Decyzja |
| --- | ---: | ---: | --- |
| map01 | 20 | 10 | standardowy rozmiar MD2 |
| map02 | 20 | 10 | standardowy rozmiar MD2 |
| map03 | 20 | 10 | standardowy rozmiar MD2 |
| map04 | 20 | 10 | standardowy rozmiar MD2 |
| map05 | 14 | 11 | wyjątek potwierdzony siatką kontrolną |
| map06 | 20 | 10 | standardowy rozmiar MD2 |
| map07 | 20 | 10 | standardowy rozmiar MD2 |
| map08 | 20 | 10 | standardowy rozmiar MD2 |
| map09 | 20 | 10 | standardowy rozmiar MD2 |
| map10 | 20 | 10 | standardowy rozmiar MD2 |
| map11 | 20 | 10 | standardowy rozmiar MD2 |

## Liczebności obiektów względem Fig. 3

| Mapa | r | p | g | w | M | b | o | Razem | Fig. 3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| map01 | 2 | 2 | 7 | 1 | 1 | 2 | 0 | 15 | zgodne |
| map02 | 5 | 5 | 3 | 2 | 2 | 2 | 2 | 21 | zgodne |
| map03 | 8 | 4 | 4 | 2 | 1 | 3 | 1 | 23 | zgodne |
| map04 | 8 | 8 | 2 | 6 | 1 | 1 | 2 | 28 | zgodne |
| map05 | 4 | 7 | 2 | 2 | 1 | 1 | 1 | 18 | zgodne |
| map06 | 7 | 4 | 2 | 3 | 1 | 2 | 1 | 20 | zgodne |
| map07 | 7 | 4 | 1 | 4 | 1 | 2 | 1 | 20 | zgodne |
| map08 | 7 | 5 | 3 | 3 | 1 | 2 | 1 | 22 | zgodne |
| map09 | 7 | 2 | 2 | 2 | 1 | 2 | 0 | 16 | zgodne |
| map10 | 7 | 4 | 1 | 4 | 1 | 2 | 1 | 20 | zgodne |
| map11 | 7 | 4 | 4 | 2 | 1 | 3 | 1 | 22 | zgodne |

## Portale i pułapki (nie wchodzą do sum z Fig. 3)

| Mapa | P | ^ |
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

Warstwa wizualna nie oznacza identyfikatorów portali. Każda mapa z portalami ma
dokładnie dwa, więc para jest jednoznaczna i zamrożona w `portal_pairs.json`.

Niezmienniki podane w artykule są spełnione:

- siedem map zawiera jedną parę portali,
- sześć map zawiera co najmniej jedną pułapkę,
- każda mapa zawiera Minitaura,
- map02 zawiera dwa Minitaury,
- map01 i map09 nie zawierają ogrów,
- map04 i map10 mają więcej wizardów niż goblinów walczących wręcz,
- map01 ma więcej goblinów walczących wręcz niż wizardów.

## Poprawki naniesione w audycie końcowym

| Mapa | Współrzędna | Decyzja | Dowód |
| --- | --- | --- | --- |
| map04 | `[11, 8]` | dodano miksturę | druga mikstura widoczna nad nałożonymi sprite'ami wizardów; wymagana dla sumy 8 z Fig. 3 |
| map04 | `[14, 5]` | podłoga → ściana | obraz źródłowy pokazuje ścianę w wierszu 15, kolumnie 6 (indeks od 1); zmienia topologię, nie liczebności |
| map07 | `[8, 2]` | przesunięto bazę Minitaura | siatka 10×20 umieszcza górny sprite nad ścianą w wierszu 7, a dolną część na podłodze w wierszu 8 |
| map08 | `[4, 8]` | ogr → podłoga | to górna część jedynego ogra o bazie `[5, 8]`; Fig. 3 podaje 1 |
| map09 | `[1, 3]` | ściana → skarb | skrzynia widoczna za górnym sprite'em Minitaura; wymagana dla sumy 7 z Fig. 3 |
| map11 | `[1, 6]` | ściana → skarb | skrzynia widoczna za górnym sprite'em Minitaura; wymagana dla sumy 7 z Fig. 3 |
| map11 | `[5, 8]` | ściana → skarb | skrzynia widoczna przy prawej krawędzi korytarza; wymagana dla sumy 7 z Fig. 3 |

## Wyjątek map05: 11 × 14

`map05.txt` ma 11 kolumn i 14 wierszy i jest przyjęty do benchmarku v1. Siatka
kontrolna `data/maps/md2/source-images/map5_grid_11x14.png` odsłania wszystkie
11 pełnych kolumn i 14 pełnych wierszy. Potwierdza też wewnętrzne
czterokafelkowe segmenty ścian i pionową ścianę w kolumnie 7, które zginęły
we wcześniejszej transkrypcji 10 × 13.

Siatka potwierdza końcowe pozycje dolnych wierszy: wyjście `[11, 7]`, Minitaur
`[12, 6]`, goblin `[12, 7]`, mikstura `[12, 9]`. Zawartość audytowana jako
`map05_copy.txt` została podniesiona do kanonicznego `map05.txt`; symbol wyjścia
znormalizowano z małego `x` na wymagane wielkie `X`.

Mapa 5 pozostaje wyraźnie mniejsza od standardowych map w opublikowanej Fig. 2,
więc **niestandardowe wymiary 11 × 14 muszą być zaraportowane w pracy**.

## Pewność rekonstrukcji i akceptacja

| Mapa | Pewność | Decyzja |
| --- | --- | --- |
| map01 | wysoka | przyjęta |
| map02 | średnia | przyjęta |
| map03 | średnio-wysoka | przyjęta |
| map04 | średnia | przyjęta po poprawce mikstury |
| map05 | wysoka | przyjęta jako wyjątek 11 × 14 potwierdzony siatką |
| map06 | średnia | przyjęta |
| map07 | wysoka | przyjęta po poprawce bazy Minitaura |
| map08 | średnia | przyjęta po poprawce ogra |
| map09 | średnio-wysoka | przyjęta po poprawce skarbu |
| map10 | średnia | przyjęta |
| map11 | średnia | przyjęta po poprawkach skarbów |

## `map02` = poziom z MD2 Fig. 1

MD2 §3 podaje dla poziomu z Fig. 1 cztery liczby: 105 kafli przechodnich,
240 możliwych ruchów, 118 dostępnych rzutów oszczepem, branching factor 3,41.
`map02` odtwarza dokładnie dwie z nich bez żadnego dopasowywania:

- **105** kafli przechodnich (policzone z `map02.txt`);
- **240** możliwych ruchów, średni stopień `240/105 = 2,2857` = cytowane
  w artykule „2,29".

To razem z liczebnością person (2 Minitaury, 2 Wizardy, 2 Bloby, 3 Gobliny,
2 Ogry — zgodne z Fig. 3) czyni `map02` niemal na pewno tym samym poziomem,
który artykuł pokazuje na Fig. 1 (stan początkowy i stan po trzech turach
bohatera idącego prosto w górę od wejścia).

Trzeci ruch bohatera potwierdzony niezależnie: dopiero po wejściu w wiersz 15
goblin (start `[15, 3]`) łapie linię wzroku, rusza się najkrótszą ścieżką
w stronę bohatera i ginie wchodząc na pułapkę `[15, 2]`, leżącą dokładnie
między nimi — zgodne z prawym panelem Fig. 1. Zamrożone jako
`../tests/domain/test_rules_engine.py::test_map02_matches_md2_figure1_after_three_north_moves`.

Prawy panel Fig. 1 rozstrzygnął też **zachowanie wizarda bez linii wzroku**:
oba wizardy (`[1, 3]` i `[13, 7]`) stoją tam po trzech turach na swoich polach,
choć bohater jest cały czas poza ich linią wzroku. Wyklucza to dosłowne
czytanie „otherwise, they move 1 step toward the Hero" z opisu MD2 na rzecz
wersji z artykułu MCTS, gdzie ruch też wymaga LOS — patrz `wizard_without_los`
w `docs/rules/decisions.md`.

Prawy panel Fig. 1 dał też **refutację osiowej linii wzroku**: ogr ze startu
`[12, 2]` opuszcza swoje pole, zjada skarb z `[13, 1]` i kończy na `[14, 1]`
jako „fancy". Osiowo widzi z `[12, 2]` wyłącznie `[12, 1]` i `[13, 2]`, do
których bohater nie dojdzie w trzech turach, więc pod osiami nie mógłby wykonać
ani jednego ruchu. Stąd domyślne `line_of_sight.geometry: "axis8"` w regułach.

Liczba dostępnych rzutów oszczepem (118) **nadal się nie zgadza** i nie zgadza
się z żadnym wariantem: osie 70, `axis8` z domyślnymi narożnikami 95, raycast
143 (21 przetestowanych kombinacji geometrii, reguł narożnika i blokerów,
dokładny DDA zweryfikowany brute-force'em). Nie jest to więc test geometrii, tylko niewyjaśniona
rozbieżność — patrz `line_of_sight_geometry` w `docs/rules/decisions.md`.
Nasza liczba jest zamrożona w
`test_map02_javelin_target_count_stays_below_the_published_118`, żeby
rozbieżność nie zniknęła po cichu.

## Pozostałe ograniczenia metodologiczne

- oryginalne tekstowe mapy MD2 są niedostępne;
- duże sprite'y zasłaniają część tła podłogi i ścian oraz nachodzą na sąsiednie
  wiersze wizualne; deterministyczne kafle logiczne wybrano na podstawie
  podstaw sprite'ów i ciągłości korytarzy;
- rzadkie kolizje, linia wzroku i tie-breakery NPC to decyzje reguł silnika,
  nie brakujące dane map — opisuje je `docs/rules/decisions.md`.

## Walidacja

```powershell
.\.venv\Scripts\python.exe tools\validate_stage0.py
```

Udane uruchomienie potwierdza wymiary, symbole, liczebności z Fig. 3,
niezmienniki z artykułu, pary portali, spójność (connectivity), obrazy źródłowe
i zamrożone sumy kontrolne. Ten sam warunek sprawdza `../tests/data/test_stage0.py`.
