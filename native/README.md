# `native/` — silnik MD2 + MCTS w C++ dla pętli fitnessu GP

Port tej jednej ścieżki, która w profilu kosztuje najwięcej i jest budżetowana
**iteracjami**, a nie czasem: `gp_fitness.evaluate_playthrough`, czyli jedna
partia jednego chromosomu na jednej mapie. To jest ta część, w której szybszy
kod naprawdę skraca zegar.

Nie rusza niczego w `src/` — to osobny moduł, ładowany albo nie.

## Wynik zmierzony na tej maszynie

| | Python (CPython 3.13) | C++ (MSVC 14.38, /O2) |
| --- | ---: | ---: |
| 24 partie × 2000 iteracji | 35,3 s | **0,46 s** |
| iteracji na sekundę, 1 rdzeń | 1 028 | **79 278** |
| pełna ewolucja (12 uruchomień × 60 000 partii), 1 rdzeń | 294 h | **3,8 h** |
| pełna ewolucja, 12–14 workerów | 14,6 h (zmierzone) | **~11 min** |

**Przyspieszenie ×77.** Powtórz u siebie: `python native/bench.py`.

## Budowa

```bash
pip install pybind11 setuptools
```

```bash
python native/setup.py build_ext --inplace
```

Moduł ląduje jako `native/md2native*.pyd` (Windows) albo `.so` (Linux).
Wymaga kompilatora z C++17 — na Windows Visual Studio Build Tools.

## Weryfikacja — uruchom PRZED użyciem wyników

```bash
python native/difftest.py
```

Test różnicowy ma trzy poziomy, od najtańszego do rozstrzygającego:

1. **generator losowy** — `randbelow` z C++ wobec `random.Random(seed)._randbelow`
   z CPythona, 8 zakresów × 6 seedów × 200 losowań;
2. **silnik** — te same sekwencje akcji odegrane po obu stronach, porównanie
   stanu po **każdym** kroku: pozycja, HP, wszystkie metryki, pozycje żywych NPC;
   11 map × 20 przebiegów × 120 kroków;
3. **cała partia** — `evaluate_playthrough` po obu stronach: fitness, główna
   metryka, liczba iteracji i **odegrana sekwencja akcji co do akcji**.

Poziom 3 jest rozstrzygający: identyczna sekwencja akcji oznacza, że zgadza się
losowanie, reguły gry, selekcja, ekspansja, rollout i backpropagacja naraz.

Stan na 2026-09-20: **wszystkie trzy przechodzą**, a rozszerzony przebieg
(176 partii — 11 map × 8 formuł × 2 seedy × 2000 iteracji, formuły eq. 6–9
artykułu i nasze wyewoluowane) dał **0 rozjazdów**, przy porównaniu `utility`
na dokładną równość `float`, nie na tolerancję.

Po co ten rygor: wcześniejsze „×195" w notatkach projektu pochodziło z lustra
w C#, które liczyło **mniej pracy** niż silnik. Bez testu różnicowego port
powtórzyłby ten sam błąd, tylko drożej.

## Podpięcie pod ewolucję

Sygnatura i klucze wyniku są identyczne z `domain.gp_fitness.evaluate_playthrough`,
więc podmiana to jeden import w `src/minidungeons/cli/evolve.py`:

```python
# było
from minidungeons.domain.gp_fitness import evaluate_playthrough
# jest
import sys; sys.path.insert(0, str(PROJECT_ROOT / "native"))
from mdnative import evaluate_playthrough
```

`run_in_pool` pickluje funkcję przez referencję (moduł + nazwa), a `sys.path`
dziedziczy się do procesów potomnych, więc workery zaimportują ten sam moduł.
Reszty `evolve.py` nie trzeba ruszać — zadania są krotkami pozycyjnymi w tej
samej kolejności.

## Co jest w środku

| plik | co |
| --- | --- |
| `src/pyrandom.hpp` | MT19937 z semantyką CPythona (`init_by_array`, `getrandbits`, `_randbelow`) |
| `src/engine.hpp/.cpp` | reguły MD2: ruch, kolizje, potwory, portale, pułapki, LOS, BFS/A\* |
| `src/expr.hpp` | parser formuł z priorytetami Pythona + ewaluator postfiksowy |
| `src/mcts.hpp` | drzewo, selekcja, rollout, backpropagacja, trzy warianty sekwencji awaryjnej |
| `src/module.cpp` | granica pybind11 — **jedno przejście na partię** |
| `mdnative.py` | wrapper: czyta `data/rules/` i `data/maps/`, buduje `Level` raz na mapę |

Dwie decyzje, które dają większość zysku:

* **granica na poziomie partii, nie iteracji.** Zmierzone w projekcie: przejście
  Python↔C++ kosztuje 29 ns, a iteracja robi ich ~800 — port pojedynczej funkcji
  dawał ×1,19. Tu granica jest przekraczana raz na partię, więc jej koszt znika.
* **tablica LOS liczona raz na mapę.** Widoczność zależy wyłącznie od terenu
  (postacie nie zasłaniają), więc `ncells × ncells` bitów wystarczy policzyć przy
  budowie poziomu. W Pythonie DDA chodzi przy każdym pytaniu o widoczność.

Reguł ani person moduł nie ma u siebie — czyta `data/rules/md2_rules.json`
i `data/rules/personas.json` przez wrapper. Wagi person wchodzą w oryginalnej
kolejności z JSON-a, bo suma zmiennoprzecinkowa nie jest przemienna i inna
kolejność dałaby inny ostatni bit.

## Ograniczenia

* **Mapa do 256 kafli i 24 NPC** (`MAX_CELLS`, `MAX_NPCS` w `engine.hpp`).
  Największa mapa benchmarku ma 220 kafli i 12 NPC. Przy większej mapie moduł
  rzuca wyjątek, nie liczy po cichu źle.
* **To jest port dla budżetu iteracyjnego.** Tryb czasowy działa, ale węzeł waży
  ~850 B, więc 300 s przy 80 tys. iteracji/s to miliony węzłów i kilka GB na
  workera. Do przebiegów Tabeli II albo ogranicz budżet węzłami, albo zostań
  przy Pythonie — tam i tak ścianą jest limit 300 s, nie szybkość kodu.
* Budżet czasowy jest z natury nieodtwarzalny — tak samo jak w Pythonie.
  Fitness GP liczy się na iteracjach właśnie dlatego.
