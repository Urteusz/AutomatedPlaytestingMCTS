# MiniDungeons MCTS

Deterministyczna rekonstrukcja MiniDungeons 2 przygotowana jako środowisko do
testowania agentów i implementacji Monte Carlo Tree Search. Etap map i zasad
jest zamrożony; modułem badawczym jest MCTS.

## Jak program działa teraz

1. `MiniDungeon` czyta plik mapy oraz reguły z JSON i buduje stan początkowy.
2. `MiniDungeon.step()` wykonuje akcję bohatera, a potem deterministyczne tury NPC.
3. Stan udostępnia `legal_actions()`, `clone()`, `state_key()` i metryki gry.
4. `MonteCarloTreeSearch` buduje drzewo na klonach stanu, a liście ocenia
   funkcją użyteczności wybranej persony. Kryterium zejścia dostarcza
   `domain/selection_policy` — UCB1 albo formuła wyewoluowana przez GP.
5. `cli/mcts_experiment` definiuje pojedynczą próbę, a `experiment_runner`
   rozdziela je na procesy i zapisuje wznawialny CSV.

```mermaid
flowchart LR
    Exp[cli/mcts_experiment] --> MCTS[domain/mcts]
    Exp --> Run[infrastructure/experiment_runner]
    Rnd[cli/random_agent] --> Env
    MCTS --> Env[domain/engine: MiniDungeon]
    MCTS --> Pers[domain/personas: utility]
    MCTS --> Pol[domain/selection_policy: UCB1 / evolved]
    Pol --> Expr[domain/expression: drzewa wyrażeń]
    Evo[domain/evolution: GP] --> Expr
    Evl[cli/evolve] --> Evo
    Evl --> Run
    Evl --> Fit[domain/gp_fitness: f = utility persony]
    Fit --> MCTS
    Evl --> Pols[(data/rules/evolved_policies.json)]
    Pols --> Pol
    Env --> Rules[(data/rules)]
    Env --> Maps[(data/maps/md2/benchmark)]
    Run --> Results[(data/results/*.csv)]
    Exp --> Traces[(data/results/*_paths.jsonl)]
    Play[frontend/game_loop] --> Env
    Heat[frontend/heatmap] --> Env
    Heat --> Traces
    Heat --> Results
```

Agent MCTS tworzy `MiniDungeon` bezpośrednio ze ścieżki do pliku mapy — między
algorytmem a domeną nie ma warstwy serwisowej ani repozytorium.

### Granice warstw

| Warstwa | Odpowiedzialność | Nie zna |
| --- | --- | --- |
| `domain/engine` | stan, akcje, NPC, reguły, metryki | person, MCTS, wejścia-wyjścia |
| `domain/personas` | funkcje użyteczności czterech person | drzewa MCTS |
| `domain/mcts` | węzeł, UCB1, selekcja, ekspansja, rollout, propagacja | CSV, procesów, argumentów CLI |
| `infrastructure` | kanoniczne ścieżki, ślady partii, wznawialny CSV i pula procesów | przebiegu tury, person, tree policy |
| `cli` | argumenty, definicja pojedynczej próby, formatowanie tabel | logiki potworów |
| `frontend` | rysowanie planszy, ręczna rozgrywka, heatmapy | reguł gry — akcje bierze z `legal_actions()` |

Zależności biegną do środka: `cli` woła `domain`, a `domain/mcts` woła
`domain/engine`. Silnik nie wie o istnieniu MCTS. Warstwa HTTP (FastAPI,
`GameService`, sesje REST) istniała we wcześniejszej wersji i została usunięta —
MCTS z niej nie korzystał. Jeśli powstanie wizualizacja, adapter należy dopisać
**obok** domeny, nie pod agentem.

## Jak czytać kod MCTS

Cały algorytm to **jedna pętla** w `MonteCarloTreeSearch._iterate()`. Reszta
`domain/mcts.py` to dwa protokoły zbudowane na tej pętli i różniące się wyłącznie
warunkiem stopu. Jeśli czytasz ten kod pierwszy raz, zacznij od `_iterate` —
wszystko inne jest jego opakowaniem.

Jedna iteracja, w kolejności:

1. **Selekcja** — schodź w dół, póki węzeł jest w pełni rozwinięty:
   `node.best_child(policy)` → `policy.select(node)`. Wybór spośród
   `viable_children()`, czyli dzieci jeszcze niewyczerpanych.
2. **Ekspansja** — jeśli zostały nieprzetestowane akcje i gra trwa,
   `node.expand(rng)` tworzy **jedno** losowe dziecko na sklonowanym stanie.
3. **Symulacja** — `rollout()` gra 10 losowych ruchów na kopii i zwraca
   użyteczność persony (`personas.utility`). Stan węzła zostaje zamrożony.
4. **Propagacja** — `backpropagate()` dolicza wizytę i użyteczność każdemu
   przodkowi aż do korzenia włącznie, i odświeża znacznik wyczerpania.

Dwa protokoły nad tą pętlą:

| Metoda | Budżet | Kiedy kończy | Co zwraca |
| --- | --- | --- | --- |
| `search()` | liczba iteracji | wyczerpanie budżetu albo całego drzewa | jedna akcja o najwyższej średniej użyteczności |
| `play_single_tree()` | czas, iteracje albo oba | **pierwszy wygrywający węzeł drzewa** albo koniec budżetu | metryki całej odegranej partii |

`play_single_tree` to protokół z artykułu: jedno drzewo na mapę, budowane aż do
znalezienia terminalnego węzła z wyjściem, potem odegranie tej sekwencji.
Zwycięstwo napotkane wyłącznie w rolloucie **nie** kończy szukania — losowe ruchy
symulacji nie są sekwencją do odegrania. Bez wygranej zostaje `_greedy_sequence()`,
a `from_tree` mówi, który z tych dwóch przypadków zaszedł.

### Trzy pojęcia, które mylą przy pierwszym czytaniu

**`TreeSpec`** — tree policy deklaruje trzy rzeczy (`needs_terminals`, `pe_mode`,
`terminal_source`), a `TreeSpec.for_policy()` zbiera je raz przy tworzeniu drzewa.
Dzięki temu `Node` nie zna żadnej konkretnej polityki — dostaje gotową
specyfikację i przekazuje ją dzieciom. UCB1 zostawia wartości domyślne i nie płaci
za zmienne Tabeli I ani czasem, ani pamięcią.

**`exhausted`** — węzeł wyczerpany to terminalny liść albo węzeł w pełni
rozwinięty, którego wszystkie dzieci są wyczerpane. UCB1 wychodzi z martwej
gałęzi sam, dzięki członowi eksploracyjnemu; ewoluowana formuła (eq. 6–9) nie ma
takiego członu i bez tego znacznika potrafiłaby wybierać ten sam martwy liść
w nieskończoność.

**`terminal_source`** — zmienne Tabeli I dla ewoluowanej polityki biorą się albo
ze stanu zamrożonego w węźle (`"node"`), albo ze średniej po stanach końcowych
symulacji przechodzących przez węzeł (`"rollout"`, ta sama semantyka co `R`).
Domyślne jest `"rollout"`, bo daje lepsze wyniki — szczegóły w
`data/rules/tree_policies.json`.

## Szybki start

Projekt nie ma zewnętrznych zależności — wystarczy biblioteka standardowa.

Losowy agent jako punkt odniesienia:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.random_agent --map data\maps\md2\benchmark\map01.txt --trials 10 --quiet
```

Eksperyment MCTS-UCB1 według protokołu Tabeli II z artykułu:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.mcts_experiment --trials 50 --time-limit 300
```

Domyślnie liczy wszystkie 11 map i 4 persony, zapisując wyniki do
`data/results/ucb1_tree_terminal.csv`. Eksperyment jest **wznawialny**: po
przerwaniu przez Ctrl+C wystarczy uruchomić identyczną komendę, a policzone
próby zostaną pominięte. `--restart` nadpisuje plik od zera.

## Raport z policzonych wyników

Sama tabela z istniejącego CSV, bez uruchamiania choćby jednej próby:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.mcts_experiment --report-only
```

Inny plik wskazuje `--out`:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.mcts_experiment --report-only --out data\results\inny_eksperyment.csv
```

Drukuje układ z Tabeli II — Monsters, Potions, Treasures, Interactive Objects,
Win Rate oraz Time — jako średnia ± 95% przedział ufności dla R, MK, TC i C.

## Ewolucja tree policy

Formuła zastępująca UCB1 nie jest wpisywana ręcznie — wyłania ją programowanie
genetyczne, protokołem z sekcji VI-A artykułu: 4 persony × 3 niezależne
uruchomienia × 100 generacji × 100 osobników na 5 wyspach, fitness uśredniany po
sześciu mapach treningowych (1, 2, 3, 4, 7, 10).

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.evolve --workers 12
```

Fitness osobnika to **użyteczność persony na koniec partii** (`f_R = U_R`), a nie
osobny wzór. Partia idzie budżetem **iteracyjnym**, nie czasowym — czas nie jest
odtwarzalny, więc fitness liczony na nim zmieniałby się z obciążeniem maszyny.
Sprawdzone: identyczna generacja przy 8 i przy 15 workerach daje ten sam
`best_fitness`.

Eksperyment jest wznawialny **na poziomie uruchomienia** (persona × run):
ukończone uruchomienia lądują w `data/results/gp_runs.json` i po restarcie są
pomijane; przerwane liczy się od pierwszej generacji. Uruchomienia idą wszerz —
najpierw run 0 dla wszystkich person, potem run 1 — żeby przerwanie w połowie
zostawiło komplet person, a nie komplet uruchomień dla połowy person.

Dziennik generacji (`data/results/gp_generations.csv`) ma po wierszu na
generację: `best_fitness`, `mean_fitness`, liczba unikalnych chromosomów,
rozmiar i postać najlepszej formuły. To materiał na wykres krzywych fitnessu.

Zwycięskie formuły przepisuje się do pliku polityk osobnym wywołaniem:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.evolve --promote
```

Wybór spośród trzech uruchomień idzie **po głównej metryce persony**, nie po
fitnessie — tak jak w artykule. Po `--promote` wyewoluowane persony gra się tym
samym eksperymentem co baseline, przełącznikiem `--policy ours`.

Koszt zmierzony na Ryzenie 7 7700 przy budżecie 2000 iteracji: ~160 s na pierwszą
generację (600 partii) i ~120 s na kolejne, gdy cache zaczyna łapać elitę —
czyli około 3 h na jedno uruchomienie i 35–45 h na pełny protokół.

## Ręczna rozgrywka

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.frontend.game_loop --map data\maps\md2\benchmark\map04.txt
```

WSAD lub strzałki to ruch, klik w potwora z linią wzroku (albo Tab i Enter) to
rzut oszczepem, `R` restartuje partię. Wymaga `pygame-ce`
(`pip install -e .[gui]`).

## Heatmapa odwiedzin

Plansza rysowana dokładnie tak jak w ręcznej rozgrywce, z nałożoną **średnią
liczbą wizyt bohatera na kaflu w przeliczeniu na jedną partię**: im częściej
bohater bywał na kaflu, tym mocniejsza czerwień — od jasnego różu po ciemną
czerwień. Kafle nieodwiedzone zostają szare. Wymaga `pygame-ce`
(`pip install -e .[gui]`).

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.frontend.heatmap
```

Bez argumentów bierze wszystkie pliki z `data/results/`, które mają obok siebie
ślady partii (`ucb1_pe.csv` → `ucb1_pe_paths.jsonl`). Konkretny wybór na
start:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.frontend.heatmap --results data\results\ucb1_pe.csv --map map04 --persona completionist --scale sqrt
```

Pod planszą jest pasek zakładek — po jednej na personę plus `SREDNIA` na
początku — a każda zakładka pokazuje **win rate tej persony na bieżącej mapie**,
więc rozbicie na persony widać bez przełączania. Aktywna zakładka jest obwiedziona
na żółto.

| Klawisz | Działanie |
| --- | --- |
| **Tab** | następna persona; cykl domyka się z powrotem na `SREDNIA`. To samo robi klik w zakładkę |
| ← → | mapa |
| `F` | przełączenie pliku wyników — tym porównuje się różne przebiegi |
| `W` | filtr: wszystkie partie / tylko wygrane / tylko przegrane |
| `L` | skala: liniowa / sqrt / log |
| `S` | zapis PNG do `data/results/heatmaps/` |

Dwie rzeczy o liczbach, bo przechodzą do pracy:

- średnia jest **na partię, nie na krok** — kafel odwiedzony dwa razy w jednej
  partii liczy się podwójnie, więc heatmapa pokazuje też zawracanie;
- widok zbiorczy to **średnia średnich** po personach, żeby persona z dłuższymi
  partiami nie przesłoniła pozostałych.

Skala jest **jednobarwna z monotonicznie malejącą jasnością** — to jasność, nie
odcień, koduje wielkość. Tęcza (granat → zieleń → czerwień) była pierwszą wersją
i była błędem: skoki odcienia sugerują kategorie, więc taką mapę czyta się tylko
z legendy. Kroki wzięte z profilu jasności skali sekwencyjnej przeniesionego na
czerwień; monotoniczności pilnuje test.

Filtr wygranych i win rate na zakładkach pochodzą z CSV — ślad nie zapisuje
wyniku partii. Win rate na zakładce jest zawsze z całego CSV, niezależnie od
ustawionego filtra, bo odpowiada na pytanie „która persona radzi sobie na tej
mapie", a nie opisuje aktualnie oglądanego podzbioru partii. Skala liniowa spłaszcza mapę, bo rozkład wizyt ma ciężki ogon; do
oglądania rzadko odwiedzanych rejonów jest `sqrt` i `log`.

## Użycie z Pythona

```python
from src.minidungeons.domain import MiniDungeon
from src.minidungeons.domain.mcts import MonteCarloTreeSearch

# samo środowisko
state = MiniDungeon("data/maps/md2/benchmark/map04.txt")
child = state.clone()
child.step(child.legal_actions()[0])

# agent MCTS na jednej mapie
agent = MonteCarloTreeSearch("data/maps/md2/benchmark/map04.txt")
metrics = agent.play_single_tree("runner", time_limit_s=30.0, seed=0)
```

## Dwie nazwy tego samego pakietu

Ten sam kod da się zaimportować dwiema drogami i **trzeba o tym wiedzieć**:

- `src.minidungeons...` — działa wprost z katalogu repozytorium, tak importują
  testy i tak wygląda uruchamianie przez `python -m src.minidungeons...`;
- `minidungeons...` — nazwa pakietu z `pyproject.toml`, dostępna po
  `pip install -e .`, używana przez skróty `minidungeons-random`,
  `minidungeons-mcts`, `minidungeons-play` i `minidungeons-heatmap`.

Python traktuje je jak **dwa osobne moduły** o niezależnym stanie. Dopóki
mieszają się w jednym procesie, jest to źródło trudnych do wyśledzenia błędów;
w pracy z repozytorium trzymaj się jednej drogi (`src.minidungeons`).

## Najważniejsze katalogi

```text
data/                         niezmienne wejścia eksperymentu
  maps/md2/benchmark/         11 map, manifest i pary portali
  maps/md2/source-images/     obrazy źródłowe i siatki kontrolne
  rules/                      parametry silnika i person (JSON)
  results/                    wyniki, ślady partii i heatmapy (poza gitem)
docs/
  rules/                      zasady gry i decyzje rekonstrukcyjne
  project/                    plan pracy inżynierskiej
  reference/articles/         publikacje źródłowe
  benchmark.md                walidacja i niepewności rekonstrukcji map
src/minidungeons/
  domain/                     silnik gry, persony, reguły, MCTS i ewolucja GP
  infrastructure/             ścieżki, ślady partii, runner eksperymentów
  cli/                        programy konsolowe: agent losowy i eksperyment
  frontend/                   pygame, wymaga extras `gui`:
                                game_loop.py — ręczna rozgrywka
                                heatmap.py   — heatmapa odwiedzin z policzonych przebiegów
tests/                        testy według warstw
tools/                        walidator zamrożonego benchmarku
```

## Testy i walidacja

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\validate_stage0.py
```

## Dokumentacja

Cztery dokumenty, każdy odpowiada na jedno pytanie:

| Dokument | Odpowiada na pytanie |
| --- | --- |
| [Zasady gry](docs/rules/game-rules.md) | jak działa MiniDungeons 2, jakie są metryki i persony |
| [Decyzje rekonstrukcyjne](docs/rules/decisions.md) | co wzięliśmy z publikacji, a co rozstrzygnęliśmy sami i dlaczego |
| [Benchmark map](docs/benchmark.md) | skąd wzięło się 11 map, jak je zwalidowano i czego nie da się ustalić pewnie |
| [Plan pracy](docs/project/roadmap.md) | co jest zrobione, co zostało i w jakim terminie |

Publikacje źródłowe: `docs/reference/articles/`.
