# Odpowiedź na `niejasnosci_md2.md` — weryfikacja źródłowa i stan w repo

Plik odpowiada punkt po punkcie na zewnętrzny dokument `niejasnosci_md2.md`.
Dla każdego twierdzenia: czy potwierdza się w źródle (cytaty sprawdzone
w obu PDF-ach niezależnie od analizowanego dokumentu) i jak jest to rozwiązane
w repo — z odwołaniem do `docs/rules/decisions.md`, `docs/rules/game-rules.md`
i kodu.

Werdykty: zgoda / odrzucone / częściowo / otwarte.

---

## A. Domknięte

Wszystkie pięć punktów potwierdza się w źródłach i jest tak zaimplementowanych.
W `decisions.md` są opisane jako wymuszone przez dane, nie jako decyzje
arbitralne.

### A1. `IC` zawiera potwory — zgoda

Footnote pod Table I w MCTS: *„the values represent the ratio out of all
potions, monsters, treasures, and all non-monster game objects in the map,
respectively"* — nazywa `IC` obiektami nie-potworowymi, ale Table II łamie
nierówność `IC ≤ max(PD,TO)` w każdym z 8 wierszy. Footnote jest błędem
redakcyjnym; rządzi opis persony (§V-A, eq. 5: `UC = 0.7·IC + 0.3·PE`,
Completionist „consuming as many potions and treasures, and killing as many
monsters as possible").

W repo: [engine.py](../../src/minidungeons/domain/engine.py),
`metric_values()` — `interactive_ratio` liczy
`potions_drunk + treasures_opened + monsters_slain`;
`interactive_non_monster_ratio` jest dodatkowe, dla przejrzystości.
`decisions.md` → `interactive_objects_consumed`.

### A2. Mianownik `MS` bez Minitaurów — zgoda

MD2: *„A Minitaur does not have HP and does not die"* — potwór bez HP nie może
być „zabity", więc nie wchodzi do mianownika.

W repo: [engine.py](../../src/minidungeons/domain/engine.py) —
`_initial_killable_monsters = sum(kind != "minitaur" ...)`.
`decisions.md` → `monsters_slain_denominator`.

### A3. Przestrzeń akcji 105/240/118/3,41 — zgoda, liczby potwierdzone dosłownie

MD2 §3: *„The level displayed in Fig. 1 contains 105 tiles which the Hero may
occupy. Across these tiles 240 moves are possible and, in the start
configuration, 118 of these tiles allow the Hero to throw the Javelin. On
average this corresponds to an estimated branching factor of 3.41 per state."*

W repo: wnioski z tych liczb są w `decisions.md` jako `illegal_move` (ruch
w ścianę nielegalny), `wait_action` (brak czekania), `javelin_details` (rzut
parametryzowany celem). Test rekonstrukcji poziomu z Fig. 1: B2 niżej
i `docs/benchmark.md`, sekcja „`map02` = poziom z MD2 Fig. 1".

### A4. `R̄` = średnia propagowana użyteczność — zgoda

Zgadza się z eq. 1 (UCB1: `wi/ni + c·√(ln t/ni)`) i z opisami eq. 6–9 w §VI-B.

W repo: `R̄` to `Node.mean_utility` (`total_utility / visits`,
[mcts.py](../../src/minidungeons/domain/mcts.py)) — człon UCB1
w [selection_policy.py](../../src/minidungeons/domain/selection_policy.py)
i terminal `R` wyewoluowanych formuł
([expression.py](../../src/minidungeons/domain/expression.py)).

### A5. HP startowe = 10 — zgoda

`game-rules.md` §4 i `decisions.md` → `hero_start_hp`.

---

## B. Silnie wskazane

### B1. Wizard bez LOS podchodzi — odrzucone

MD2 opisuje Goblin Wizarda tak: *„Goblin Wizards deal 1 ranged damage to the
Hero, if they have an unbroken line of sight and are within 5 tiles of the
Hero; otherwise, they move 1 step toward the Hero. Goblin Wizards have 1 HP and
deal no damage on collision."* — klauzula „otherwise" nie ma warunku LOS.

Artykuł MCTS opisuje tę samą regułę dokładniej: *„cast a spell at the hero if
they have an unbroken line of sight within 5 tiles of the player... If they are
over 5 tiles from the player but have line of sight, they will move 1 tile
towards the player."* Oba zachowania są warunkowane LOS, a dla braku LOS nie ma
klauzuli. Zdanie z MD2 czytane dosłownie daje wizardowi wieczny pościg przez
całą mapę.

Rozstrzyga prawy panel MD2 Fig. 1: wizardy startujące z `[1, 3]` i `[13, 7]`
stoją po trzech turach na swoich polach, a wersja „otherwise" przesunęłaby je
na `[3, 2]` i `[15, 6]` (ich LOS do bohatera jest przez cały ten czas
przerwany).

W repo: reguła `monsters.wizard.moves_without_los` (domyślnie `false`, wersja
MCTS; `true` daje wersję MD2). `decisions.md` → `wizard_without_los`,
`game-rules.md` §11.2. Pasywny wizard nie jest więc kandydatem na wyjaśnienie
win rate baseline'u (B5).

### B2. LOS jako pełny raycast 2D vs tylko osie — częściowo

Żaden z PDF-ów nie podaje geometrii LOS poza słowami „unbroken line of sight".
Opis goblina („move 1 step toward the Hero along the shortest path", „avoid
colliding with other Goblins or Goblin Wizards") sugeruje pathfinding bardziej
złożony niż czysta oś, ale to przesłanka pośrednia, nie dowód geometrii LOS.

Test 1 (rekonstrukcja poziomu z Fig. 1 i policzenie 118 dostępnych rzutów):
liczba 118 nie jest odtwarzana przez żaden wariant — 21 kombinacji (geometria ×
reguła narożnika × blokery), dokładny DDA całkowitoliczbowy zweryfikowany
brute-force'em na liczbach wymiernych (39 800 par, zero rozjazdów). Osie dają
70, `axis8` 95, raycast 143; najbliżej są 116 i 123, ale tylko przy założeniu,
że LOS blokują postacie albo obiekty, co jest dopasowywaniem pod liczbę. `105`
i `240` odtwarzamy dokładnie, więc rozbieżność siedzi w definicji LOS albo
w tym, co autorzy liczyli jako „118 of these tiles" (zdanie źródłowe jest
wewnętrznie niespójne: 118 > 105 kafli).

Test 1 wyklucza natomiast osiowy LOS — prawym panelem Fig. 1, nie liczbą. Ogr
z `(12,2)` widzi osiowo tylko `(12,1)` i `(13,2)`; bohater nie dojdzie z `(18,1)`
do żadnego z nich w 3 turach, więc pod osiami ogr nie może się ruszyć, a na
obrazku zjadł skarb z `(13,1)` i stoi na `(14,1)`. Stąd domyślne `axis8`.
Fig. 1 nie rozróżnia `axis8` od raycasta — wszystkie warianty skośne dają
identyczny prawy panel, więc wybór między nimi jest decyzją, nie ustaleniem.
`decisions.md` → `line_of_sight_geometry`.

Otwarte: definitywnie rozstrzygnęłaby to tylko referencyjna implementacja
autorów albo kontakt z nimi w sprawie zdania o 118.

### B3. Zmienne polityki drzewa znormalizowane do `[0,1]` — zgoda co do interpretacji

Równania 6–9 i proza z §VI-B zgadzają się z cytatami analizy, w tym zdanie
o eq. 7: *„this tree policy is the only one among eq. (6–9) which does not
include R̄"*. Opisy słowne („strongly prioritizes proximity to exit",
„actively prefers reaching the exit with low health", „these variables are
multiplied to any other metric") mają sens tylko przy zmiennych nieujemnych
w `[0,1]`.

W repo: eq. 6–9 i własne formuły GP liczone są nad terminalami Tabeli I
w [expression.py](../../src/minidungeons/domain/expression.py) i
[selection_policy.py](../../src/minidungeons/domain/selection_policy.py);
tryb `PE` terminala wybiera pole `pe_mode` w `data/rules/*_policies.json`.

### B4. `PE` w funkcji użyteczności jest stopniowalne — odrzucone empirycznie

Argument lingwistyczny („jak blisko wyjścia skończył" nie ma sensu przy dwóch
wartościach) przegrywa z danymi: `graded` (`PE = -dystans/max_dystans`) na
baseline UCB1 dawał win rate R 47% / MK 23% / TC 18% / C 29% — poziom person
ewoluowanych z artykułu, nie baseline'u (artykuł: poniżej 15% dla wszystkich,
C > R). `binary` (`PE = 0` na wyjściu, `−1` wszędzie indziej) jako jedyny
odtwarza oba fakty: win rate 9–18% i kolejność C > R.

W repo: `binary` w użyteczności person
([personas.py](../../src/minidungeons/domain/personas.py)); wariant stopniowany
zostaje wyłącznie jako terminal `PE` tree policy. Mechanizm i uzasadnienie
rozdziału: `decisions.md`, sekcja „Dlaczego `PE` jest binarne".

### B5. Dlaczego baseline wygrywał 47% — potwierdzone dla kandydata nr 1

MCTS §III-A, eq. 1: *„It is typically chosen that c = √2, since this value has
been shown to guarantee convergence to a value function within finite time for
single-player games terminal states and rewards bounded to the range [0, 1]."*

W repo: UCB1 w
[selection_policy.py](../../src/minidungeons/domain/selection_policy.py) używa
`c = √2`, ale propagowana wartość to surowa użyteczność persony z
[personas.py](../../src/minidungeons/domain/personas.py) — dla Runnera
`PE - 0.01·ST` z karą śmierci `-5`. To wartości poza `[0,1]`, w tym ujemne,
czyli dokładnie warunek, który według artykułu unieważnia gwarancję zbieżności
`c = √2`. Rozbieżność jest niezależna od `wizard_without_los`
i `line_of_sight_geometry`. Weryfikuje ją Test 3 (przeskalowanie nagrody);
nie jest on przesłanką do zmiany `PE`, które wybrano empirycznie (B4).

Z trzech kandydatów analizy (skala nagrody, pasywny wizard, osiowy LOS):
skala nagrody ma potwierdzenie źródłowe, pasywny wizard jest regułą z artykułu
(B1), osiowy LOS jest wykluczony (B2).

### B6. Blob traci poziom proporcjonalnie do obrażeń — odrzucone, źródło mówi co innego

MD2: *„A more powerful Blob which receives damage loses one power level."* —
zawsze dokładnie jeden poziom, niezależnie od źródła i wielkości obrażeń. Ogr
zadający 2 obrażenia zbija bloba poziomu 3 do poziomu 2, nie 1.

W repo: [engine.py](../../src/minidungeons/domain/engine.py), obsługa obrażeń
bloba:

```python
if npc.kind == "blob":
    if npc.power <= 1:
        npc.hp = 0
    else:
        npc.power -= 1
        npc.hp = npc.power
```

Implementacja jest zgodna ze źródłem; proponowanego w analizie
`blob_damage_magnitude` nie wprowadzamy.

---

## C. Otwarte — punkty z nowymi dowodami

Większości tabeli C nie da się rozstrzygnąć z tekstu (obie publikacje milczą),
ale trzy pozycje mają nowe dowody:

- `best_sequence_selection` — cytat: *„It will immediately cease construction
  once a winning terminal state is discovered or it reaches timeout, wherein it
  will take the best sequence of actions it discovered."* W repo: gdy
  w drzewie powstanie wygrywający węzeł terminalny, odgrywana jest ścieżka do
  niego (`MonteCarloTreeSearch._path_to`). Sekwencja awaryjna
  (`_fallback_sequence`) działa tylko, gdy w budżecie nie znaleziono wygranej;
  jej warianty i pomiary: `decisions.md`, sekcja „Sekwencja odgrywana po
  wyczerpaniu budżetu". Status: zgodne z artykułem.

- `st_counts_javelin` — cytat z §VI-D (map 8): *„the Treasure Collector takes
  on average 11.6 actions (the Runner takes 8, the Monster Killer 9 and the
  Completionist 9.2)"* — to liczby „actions". Nie rozstrzyga to, czy metryka
  `ST` z Table I też liczy rzuty; zostaje na poziomie pewności C.

- `plan_length_cap` — cytaty: *„trees will contain between two and five million
  nodes"* i *„up to a maximum of 300 seconds"* — głębokość jest ograniczona
  budżetem czasu, nie długością planu.

---

## D. Nieodtwarzalne

- Budżet iteracji (2–5 mln węzłów) — cytat: *„On average, trees will contain
  between two and five million nodes."* Służy jako oszacowanie budżetu
  ewaluacji przy planowaniu własnych przebiegów.

- `±0%` w Table II dla baseline C — częściowa korekta. `±0%` występuje nie
  tylko dla baseline Completionist (Monsters 28% ± 0%, Win Rate 13% ± 0%,
  Time 278 ± 0), ale też dla win rate Evolved Runner i Evolved Completionist
  (oba 100% ± 0%). Nie musi to być błąd redakcyjny: w grze w pełni
  deterministycznej, jeśli drzewo konsekwentnie znajduje tę samą wygraną
  niezależnie od ziarna rolloutu, wariancja wyniku może realnie wynosić zero.
  Rekomendacja „nie kalibruj się do baseline C" zostaje, ale dlatego, że bez
  surowych danych autorów nie wiadomo, czy zerowa wariancja jest artefaktem
  redakcyjnym, czy konsekwencją determinizmu.

---

## E. Testy

Kolejność testów z analizy bez zmian. Liczby docelowe dla Testu 1
(105/240/118/3,41) i Testu 5 (map 6/8/9, czasy 2,06 s i 23 s) są potwierdzone
dosłownie w źródle.

Uzupełnienie do Testu 5: §VI-D dla map 8 podaje też, że wszystkie persony piją
zero mikstur i zbierają dokładnie jeden skarb, a różnica w `IC` na tej mapie
wynika wyłącznie z liczby zabitych potworów (TC 19% vs MK 11% vs C 12%) —
dodatkowy, ciasny punkt kontrolny.

---

## F. Stan

Rozstrzygnięte: A1–A5, B1 (wizard bez LOS stoi), B2 w zakresie wykluczenia osi
(Test 1 wykonany), B4 (`PE` binarne w użyteczności), B6 (blob bez zmian),
implementacja eq. 6–9.

Otwarte:

1. Test 3 — skala nagrody w UCB1 (`c = √2` wymaga `[0,1]`), najsilniej
   potwierdzony kandydat z B5.
2. Rozbieżność 118 rzutów z B2 — bez referencyjnej implementacji
   nierozstrzygalna.
