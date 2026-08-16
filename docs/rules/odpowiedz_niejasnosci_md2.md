# Odpowiedź na `niejasnosci_md2.md` — weryfikacja źródłowa i stan w repo

Ten plik odpowiada punkt po punkcie na `niejasnosci_md2.md` (dostarczony z
zewnątrz). Dla każdego twierdzenia: **czy potwierdza się w źródle** (sam
odczytałem oba PDF-y ponownie, cytaty poniżej są zweryfikowane niezależnie od
tego dokumentu) i **co z tym jest u nas** — z odwołaniem do
`docs/rules/decisions.md`, `docs/rules/game-rules.md` i konkretnych linii kodu.

Skrót werdyktu: **zgoda** / **odrzucone** / **częściowo** / **nie dotyczy jeszcze**.

---

## A. Domknięte

Wszystkie pięć potwierdza się w źródłach i wszystkie pięć **już jest tak
zaimplementowane u nas**. Różnica jest wyłącznie w uzasadnieniu wpisanym do
`decisions.md` — dziś opisane jako decyzja arbitralna, a powinno być opisane
jako wymuszone przez dane. Warto poprawić tylko tekst uzasadnienia, kod i
zachowanie zostają bez zmian.

### A1. `IC` zawiera potwory — **zgoda**

Sam sprawdziłem Table I i footnote w MCTS: dokładny tekst to *„the values
represent the ratio out of all potions, monsters, treasures, and all
non-monster game objects in the map, respectively"* — footnote rzeczywiście
nazywa `IC` obiektami nie-potworowymi, a Table II (odczytane przeze mnie
niezależnie) łamie nierówność `IC ≤ max(PD,TO)` w każdym z 8 wierszy, dokładnie
jak w analizie. Footnote jest redakcyjnym błędem, opis persony (§V-A, eq. 5:
`UC = 0.7·IC + 0.3·PE`, gdzie Completionist „consuming as many potions and
treasures, and killing as many monsters as possible") rządzi.

**U nas:** [engine.py:289-292](../../src/minidungeons/domain/engine.py#L289-L292)
— `interactive_ratio` liczy `potions_drunk + treasures_opened + monsters_slain`.
Dokładnie to. `interactive_non_monster_ratio` (linie 293-296) jest dodatkowe,
do przejrzystości. Zgodne z `decisions.md` → `interactive_objects_consumed`.
Zmień tylko uzasadnienie w dokumencie na powyższy dowód arytmetyczny.

### A2. Mianownik `MS` bez Minitaurów — **zgoda**

Zweryfikowałem opis Minitaura w MD2: *„A Minitaur does not have HP and does
not die"* — potwory bez HP nie mogą być „zabite", więc nie mogą wchodzić do
mianownika metryki „zabici".

**U nas:** [engine.py:186](../../src/minidungeons/domain/engine.py#L186) —
`_initial_killable_monsters = sum(kind != "minitaur" for kind, _, _ in
npc_specs)`. Dokładnie to. Zgodne z `decisions.md` →
`monsters_slain_denominator`.

### A3. Przestrzeń akcji 105/240/118/3,41 — **zgoda, liczby potwierdzone dosłownie**

Cytat z MD2 §3, sprawdzony osobiście: *„The level displayed in Fig. 1 contains
105 tiles which the Hero may occupy. Across these tiles 240 moves are
possible and, in the start configuration, 118 of these tiles allow the Hero
to throw the Javelin. On average this corresponds to an estimated branching
factor of 3.41 per state."* Liczby zgadzają się co do joty z analizą.

**U nas:** trzy wnioski z tych liczb już są w `decisions.md`:
`illegal_move` (ruch w ścianę nielegalny), `wait_action` (brak czekania),
`javelin_details` (rzut parametryzowany celem). Zgodne. To, co **nie** jest
jeszcze zrobione: sam test rekonstrukcji poziomu z Fig. 1 i policzenie
105/240/118 na naszej mapie — patrz sekcja Testy niżej, to wciąż otwarta
praca, nie decyzja.

### A4. `R̄` = średnia propagowana użyteczność — **zgoda, ale nieużywane jeszcze w praktyce**

Zgadza się z eq. 1 (UCB1: `wi/ni + c·√(ln t/ni)`) i z opisami eq. 6-9 w §VI-B.

**U nas:** [mcts.py:43](../../src/minidungeons/domain/mcts.py#L43) —
`average_utility = child.total_utility / child.visits` jest dokładnie tym
członem. **Ale** repo dziś implementuje wyłącznie baseline UCB1
(`mcts.py`) — wyewoluowane formuły drzewa (eq. 6-9, gdzie `R̄` faktycznie
występuje jako zmienna wejściowa formuły) **nie są jeszcze zaimplementowane
w kodzie**. To nie jest niedomknięta decyzja, tylko brakująca funkcjonalność —
patrz B3.

### A5. HP startowe = 10 — **zgoda, bez zmian**

`docs/rules/game-rules.md` §4 i `decisions.md` → `hero_start_hp` już to mówią.

---

## B. Silnie wskazane

### B1. Wizard bez LOS podchodzi — **WYCOFANE 2026-08-06, patrz dopisek na końcu sekcji**

Sam znalazłem w MD2 zdanie opisujące Goblin Wizarda w całości: *„Goblin
Wizards deal 1 ranged damage to the Hero, if they have an unbroken line of
sight and are within 5 tiles of the Hero; **otherwise, they move 1 step
toward the Hero**. Goblin Wizards have 1 HP and deal no damage on
collision."* Nie ma tam żadnego warunku LOS przy klauzuli „otherwise" —
sekcja mówi wprost „move 1 step toward the Hero" bez zastrzeżeń.

Wizard bez LOS stał w miejscu (`npc_stay`) zamiast podejść BFS-em w stronę
bohatera tak jak goblin. **Naprawione** —
[engine.py:579-588](../../src/minidungeons/domain/engine.py#L579-L588) teraz
próbuje ataku tylko przy LOS, a poza tym zawsze wykonuje ten sam
`_next_step_bfs` + `_move_npc_or_stay`, który ma goblin. `decisions.md` →
`wizard_without_los` i `game-rules.md` §11.2 zaktualizowane.

**Skutek:** pasywny wizard był jednym z trzech kandydatów w B5 na wyjaśnienie
zawyżonego win rate baseline'u — patrz niżej.

**WYCOFANE (2026-08-06).** Analiza wyżej pominęła to, że artykuł MCTS opisuje
tę samą regułę inaczej i **dokładniej**: *„cast a spell at the hero if they have
an unbroken line of sight within 5 tiles of the player... If they are over 5
tiles from the player **but have line of sight**, they will move 1 tile towards
the player."* Oba zachowania są tam warunkowane LOS, a dla braku LOS nie ma
żadnej klauzuli. Zdanie z MD2 („otherwise") jest skrótem, który czytany
dosłownie daje wizardowi wieczny pościg przez całą mapę.

Rozstrzyga prawy panel MD2 Fig. 1: wizardy startujące z `[1, 3]` i `[13, 7]`
stoją tam po trzech turach na swoich polach, a wersja „otherwise" przesunęłaby
je na `[3, 2]` i `[15, 6]` (ich LOS do bohatera jest przez cały ten czas
przerwany). Silnik wrócił więc do zachowania z artykułu MCTS, ale sterowanego
regułą `monsters.wizard.moves_without_los` (domyślnie `false`), żeby oba
warianty dały się porównać na benchmarku. To ten sam wzorzec, co
`line_of_sight.geometry` z B2.

**Skutek dla B5:** pasywny wizard **przestaje być kandydatem** na wyjaśnienie
zawyżonego win rate — jest teraz regułą, nie błędem. Zostają skala nagrody
w UCB1 (Test 3) i budżet iteracji.

### B2. LOS jako pełny raycast 2D vs tylko osie — **wciąż otwarte, brak rozstrzygnięcia w źródle**

Przeszukałem oba PDF-y pod kątem definicji geometrii LOS — **żaden nie podaje
niczego poza słowami „unbroken line of sight"**. Potwierdzam, że opis goblina
(„move 1 step toward the Hero along the shortest path", „avoid colliding with
other Goblins or Goblin Wizards") jest dosłowny i rzeczywiście sugeruje
pathfinding bardziej złożony niż czysta oś — ale to przesłanka pośrednia, nie
dowód geometrii LOS.

**U nas:** `has_line_of_sight` liczyło wyłącznie dystans osiowy (ten sam wiersz
lub kolumna). Zgodne z `decisions.md` → `line_of_sight_geometry`, jawnie
oznaczone tam jako decyzja arbitralna. **Zgadzam się z analizą: nie zmieniać
"na wyczucie".** Test 1 (rekonstrukcja poziomu z Fig. 1 i policzenie 118
dostępnych rzutów) jest jedynym twardym testem — i teraz wiem, że liczby
docelowe (105/240/118/3,41) są potwierdzone dosłownie w źródle, więc test jest
wykonalny.

**Wynik Testu 1 (wykonany):** liczba 118 **nie została odtworzona przez żaden
wariant** — 21 kombinacji (geometria × reguła narożnika × blokery), dokładny DDA
całkowitoliczbowy zweryfikowany brute-force'em na liczbach wymiernych (39 800
par, zero rozjazdów). Osie dają 70, `axis8` 102, raycast bez narożników 143;
najbliżej są 116 i 123, ale tylko przy założeniu, że LOS blokują postacie albo
obiekty, co jest dopasowywaniem pod liczbę. `105` i `240` odtwarzamy dokładnie,
więc rekonstrukcja mapy jest poprawna i rozbieżność siedzi w samej definicji
LOS albo w tym, co autorzy liczyli jako „118 of these tiles" (zdanie źródłowe
jest wewnętrznie niespójne: 118 > 105 kafli).

**Co Test 1 jednak rozstrzygnął:** osiowy LOS jest **wykluczony** — nie liczbą,
a prawym panelem Fig. 1. Ogr z `(12,2)` widzi osiowo tylko `(12,1)` i `(13,2)`;
bohater nie dojdzie z `(18,1)` do żadnego z nich w 3 turach, więc pod osiami ogr
nie może się ruszyć, a na obrazku zjadł skarb z `(13,1)` i stoi na `(14,1)`.
Stąd domyślne `axis8`. Fig. 1 **nie** rozróżnia natomiast `axis8` od raycasta
ani reguł narożników — wszystkie warianty skośne dają identyczny prawy panel,
więc wybór między nimi zostaje decyzją, nie ustaleniem.

**Co nadal otwarte:** definitywnie rozstrzygnęłaby to tylko referencyjna
implementacja autorów (jeśli jest publicznie dostępna) albo kontakt z nimi w
sprawie zdania o 118.

### B3. Zmienne polityki drzewa znormalizowane do `[0,1]` — **zgoda co do interpretacji, ale formuły jeszcze nie istnieją w kodzie**

Sam odczytałem równania 6-9 i prozę z §VI-B — dokładnie zgadzają się z cytatami
w analizie, w tym kluczowe zdanie o eq. 7: *„this tree policy is the only one
among eq. (6–9) which does not include R̄"* (to dodatkowy szczegół, którego
analiza nie przytoczyła, ale nie zmienia wniosku). Zgadzam się z rozumowaniem:
opisy słowne („strongly prioritizes proximity to exit", „actively prefers
reaching the exit with low health", „these variables are multiplied to any
other metric") mają sens tylko przy zmiennych nieujemnych w `[0,1]`.

**U nas:** to najważniejsza luka do zaraportowania — **`src/minidungeons/domain/mcts.py`
implementuje wyłącznie UCB1 (baseline)**. Nie ma tam żadnej ścieżki, która
liczyłaby eq. 6-9 jako politykę drzewa. Innymi słowy: `tree_policy_variable_scaling`
nie jest dziś "brakującym wpisem w decisions.md" — to brakująca funkcja w
silniku. Zanim to wejdzie do dokumentu decyzji, trzeba dopisać kod, który
faktycznie liczy `tR, tMK, tTC, tC` z osobno znormalizowanymi `[0,1]`
zmiennymi wejściowymi (Test 2 z analizy odnosi się właśnie do tego kodu, który
jeszcze nie istnieje).

### B4. `PE` w funkcji użyteczności jest stopniowalne — **odrzucone empirycznie**

Argument lingwistyczny („jak blisko wyjścia skończył" nie ma sensu przy dwóch
wartościach) jest sam w sobie rozsądny, ale przegrywa z danymi: `graded`
(`PE = -dystans/max_dystans`) na baseline UCB1 dawał win rate **R 47% / MK
23% / TC 18% / C 29%** — poziom person **ewoluowanych** z artykułu, nie
baseline'u (artykuł: poniżej 15% dla wszystkich, C > R). `binary` (`PE = 0`
na wyjściu, `−1` wszędzie indziej) jako jedyny odtwarza oba fakty: win rate
9-18% i kolejność C > R.

**U nas:** [engine.py:289-292](../../src/minidungeons/domain/engine.py#L289-L292)
implementuje wyłącznie `binary` — `graded` usunięty z kodu i konfiguracji,
nie ma już przełącznika. Mechanizm dlaczego to działa: patrz `decisions.md`.

### B5. Dlaczego baseline wygrywał 47% — **potwierdzone dosłownie dla kandydata nr 1, silny materiał do zmiany**

To najmocniejszy punkt całej analizy i sam zweryfikowałem cytat źródłowy:
MCTS §III-A, eq. 1: *„It is typically chosen that c = √2, since this value
has been shown to guarantee convergence to a value function within finite
time for single-player games terminal states and **rewards bounded to the
range [0, 1]**."*

**U nas:** [mcts.py:36](../../src/minidungeons/domain/mcts.py#L36) —
`best_child(self, c: float = math.sqrt(2))` używa dokładnie `c = √2`, ale
propagowana wartość to surowa użyteczność persony z
[personas.py](../../src/minidungeons/domain/personas.py) — dla Runnera
`PE - 0.01·ST` z `PE ∈ {0,-1}` (binary), z karą śmierci `-5`. To wartości
**poza `[0,1]`**, w tym ujemne — dokładnie warunek, który wg samego artykułu
unieważnia gwarancję zbieżności `c=√2`. To jest **potwierdzona rozbieżność w
kodzie**, niezależna od `wizard_without_los` i od `line_of_sight_geometry`.
Zgadzam się z kolejnością naprawy z sekcji F analizy: Test 3 (przeskalowanie
nagrody) przed dotykaniem `PE`. Uwaga: `PE` już wybrano empirycznie (`binary`,
patrz B4) — Test 3 sprawdza mechanizm baseline'u, nie jest przesłanką do
zmiany `PE`.

Do trzech kandydatów z analizy (skala nagrody, pasywny wizard, osiowy LOS)
dochodzi teraz potwierdzenie źródłowe dla dwóch z nich (skala nagrody — cytat
wyżej; wizard — B1). Trzeci (LOS 2D vs osie) zostaje otwarty do Testu 1.

### B6. Blob traci poziom proporcjonalnie do obrażeń — **ODRZUCONE, źródło mówi co innego**

Tu analiza się myli, i mam na to dosłowny cytat z MD2, którego "niejasnosci_md2.md"
nie przytacza: *„A more powerful Blob which receives damage **loses one power
level**."* Nie „traci HP równe obrażeniom", tylko **zawsze dokładnie jeden
poziom**, niezależnie od źródła i wielkości obrażeń. Ogr zadający 2 obrażenia
zbija bloba poziomu 3 do poziomu **2**, nie do poziomu 1.

**U nas:** [engine.py:452-462](../../src/minidungeons/domain/engine.py#L452-L462):

```python
if npc.kind == "blob":
    if npc.power <= 1:
        npc.hp = 0
    else:
        npc.power -= 1
        npc.hp = npc.power
```

To jest **już poprawne** — flat `-1` niezależnie od `amount`. **Nie
wprowadzać** `blob_damage_magnitude` z analizy; to zmieniłoby poprawną
implementację na niezgodną ze źródłem. Warto natomiast dopisać do
`decisions.md` jedno zdanie z tym dosłownym cytatem, żeby ta wątpliwość nie
wracała.

---

## C. Otwarte — punkty, które sam sprawdziłem

Większości tabeli C nie da się rozstrzygnąć z tekstu (potwierdzam — obie
publikacje rzeczywiście milczą), ale trzy pozycje mają nowe dowody:

- **`best_sequence_selection`** — potwierdzony dosłowny cytat: *„It will
  immediately cease construction once a winning terminal state is discovered
  or it reaches timeout, wherein it will take the best sequence of actions it
  discovered."* **U nas to już jest poprawnie zaimplementowane** dla głównej
  ścieżki: [mcts.py:158-159](../../src/minidungeons/domain/mcts.py#L158-L159)
  — gdy znaleziony zostanie wygrywający węzeł terminalny w drzewie,
  odtwarzana jest ścieżka do niego (`_path_to`), a nie zejście zachłanne.
  Zachłanne zejście po średniej użyteczności (`_greedy_sequence`,
  [mcts.py:182-189](../../src/minidungeons/domain/mcts.py#L182-L189)) jest
  używane **tylko jako fallback**, gdy w budżecie czasu nie znaleziono żadnej
  wygranej — co jest rozsądnym uzupełnieniem tam, gdzie artykuł nie mówi nic
  (bo autorzy zakładali, że drzewo zawsze znajdzie zwycięstwo). Status: zamknij
  ten wpis jako zgodny, nie jako lukę.

- **`st_counts_javelin`** — potwierdziłem cytat z §VI-D (map 8): *„the
  Treasure Collector takes on average 11.6 actions (the Runner takes 8, the
  Monster Killer 9 and the Completionist 9.2)"* — to faktycznie liczby
  „actions", zgodne z tym, co cytuje analiza. To nadal nie rozstrzyga
  jednoznacznie, czy metryka `ST` z Table I (a nie ten fragment prozy w
  VI-D) też liczy rzuty — zostaje na poziomie pewności C, zgodnie z oceną
  analizy.

- **`plan_length_cap`** — potwierdziłem: *„trees will contain between two and
  five million nodes"* i limit *„up to a maximum of 300 seconds"* — zgadza
  się z oceną analizy, że głębokość jest ograniczona budżetem czasu, nie
  długością planu.

---

## D. Nieodtwarzalne

- **Budżet iteracji (2-5 mln węzłów)** — potwierdzony dosłownie: *„On
  average, trees will contain between two and five million nodes."* Zgadzam
  się z klasyfikacją: to faktyczne oszacowanie budżetu ewaluacji, do
  wykorzystania przy planowaniu własnych przebiegów (patrz też pamięć sesji o
  luce 585k/375k iteracji vs 2-5 mln węzłów w artykule).

- **`±0%` w Table II dla baseline C — częściowa korekta.** Sam sprawdziłem
  całą Table II: `±0%` występuje nie tylko dla baseline Completionist
  (Monsters 28%±0%, Win Rate 13%±0%, Time 278±0), ale też dla **win rate
  Evolved Runner i Evolved Completionist (oba 100%±0%)**. To nie musi być
  błąd redakcyjny — w grze w pełni deterministycznej, jeśli drzewo o budżecie
  2-5 mln węzłów konsekwentnie znajduje tę samą wygraną niezależnie od ziarna
  losowego rolloutu, wariancja **wyniku** (a niekoniecznie samej metryki)
  może realnie wynosić zero w wielu z 550 prób. Rekomendacja z analizy
  („nie kalibruj się do baseline C") zostaje słuszna, ale z innego powodu —
  nie dlatego, że liczby są ewidentnym błędem, tylko dlatego, że nie wiadomo,
  czy zerowa wariancja jest artefaktem redakcyjnym czy realną konsekwencją
  determinizmu; oba wyjaśnienia są równie prawdopodobne bez dostępu do
  surowych danych autorów.

---

## E. Testy — bez zmian w priorytetyzacji

Zgadzam się z kolejnością testów z analizy. Jedyna aktualizacja: liczby
docelowe dla Testu 1 (105/240/118/3,41) i Testu 5 (map 6/8/9, czasy 2,06 s i
23 s) są teraz **potwierdzone dosłownie przeze mnie w źródle**, nie tylko
przytoczone przez autora analizy — więc te testy można zacząć pisać od razu,
bez dalszej weryfikacji tekstu źródłowego.

Jedno uzupełnienie do Testu 5, którego nie było w analizie: §VI-D dla map 8
podaje też, że wszystkie persony piją zero mikstur i zbierają dokładnie jeden
skarb (potwierdzone dosłownie), a różnica w `IC` na tej mapie wynika
wyłącznie z liczby zabitych potworów (TC 19% vs MK 11% vs C 12%) — dodatkowy,
bardzo ciasny punkt kontrolny do tego samego testu.

---

## F. Stan po przeglądzie

Zrobione:

1. **B1 — wizard naprawiony** w
   [engine.py:579-588](../../src/minidungeons/domain/engine.py#L579-L588).
2. **B6 — blob bez zmian**, kod już zgodny z cytatem „loses one power level".
3. **A1-A5, `target_tie_break`, `wait_action`, `illegal_move`, `javelin_details`,
   `interactive_objects_consumed`, `monsters_slain_denominator`** przeniesione
   w `decisions.md` z „decyzja arbitralna" na „wymuszone danymi/opisem", z
   cytatami źródłowymi.
4. **`game-rules.md`** — §11.2 (wizard), §15 (`PE`/`IC`) i reguła precedencji
   MD2/MCTS zaktualizowane pod nowy stan.
5. **`graded` PE usunięty z kodu i konfiguracji** — `binary` jest jedyną
   implementacją, bo to on odtwarza wyniki artykułu (B4).
6. Testy (`pytest`) przechodzą bez zmian po poprawkach.

Zostaje do zrobienia, wymaga osobnej pracy eksperymentalnej, nie samej zmiany
dokumentu:

1. **Test 3** (skala nagrody w UCB1, `c=√2` wymaga `[0,1]`) — najtańszy,
   rozstrzyga najsilniej potwierdzony kandydat z B5.
2. ~~**Test 1** (LOS przez liczbę 118 z Fig. 1) — rozstrzyga `line_of_sight_geometry`.~~
   **Wykonany.** Liczba 118 nie jest odtwarzana przez żaden wariant, ale prawy
   panel Fig. 1 wyklucza osie; geometria to teraz `line_of_sight.geometry`
   w regułach, domyślnie `axis8`. Szczegóły w B2 wyżej.
3. **Implementacja eq. 6-9** jako kod silnika — dopiero wtedy Test 2 i B3/B4
   mają czego dotyczyć.
