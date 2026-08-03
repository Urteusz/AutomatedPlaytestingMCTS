# Plan pracy inżynierskiej

## 1. Tytuł i pytanie badawcze

**Automatyczne testowanie poziomów gry MiniDungeons 2 z wykorzystaniem
proceduralnych person: reprodukcja MCTS z artykułu źródłowego oraz porównanie
z agentami uczenia ze wzmocnieniem**

Wersja krótsza: *Automatyczne testowanie poziomów gier z wykorzystaniem
proceduralnych person: MCTS, heurystyki ewolucyjne i PPO*.

Pytanie główne:

> Czy proceduralne persony Runner, Monster Killer, Treasure Collector
> i Completionist, sterowane przez MCTS-UCB1, MCTS z ewoluowaną polityką drzewa
> oraz PPO, uzyskują istotnie różne, mierzalne style zachowania podczas
> automatycznego testowania poziomów MiniDungeons 2?

Pytania pomocnicze:

1. Czy MCTS z ewoluowaną polityką drzewa osiąga lepsze wyniki niż MCTS-UCB1?
2. Czy PPO potrafi odtworzyć zachowania person zdefiniowanych funkcjami
   użyteczności?
3. Czy różne persony rzeczywiście preferują inne interakcje z poziomem?
4. Które cechy poziomów wpływają na skuteczność poszczególnych person?
5. Jaki jest kompromis między jakością gry, czasem decyzji i generalizacją
   na nowe mapy?

## 2. Hipotezy

| Id | Hipoteza |
| --- | --- |
| H1 | Persony MCTS z ewoluowaną polityką drzewa osiągną wyższe wartości swoich głównych metryk niż persony MCTS-UCB1. |
| H2 | Runner będzie miał najwyższy win rate i najkrótsze ścieżki do wyjścia. |
| H3 | Monster Killer zabije większy odsetek przeciwników niż pozostałe persony. |
| H4 | Treasure Collector zbierze większy odsetek skarbów niż pozostałe persony. |
| H5 | Completionist będzie miał najwyższy lub jeden z najwyższych odsetków interakcji ze wszystkimi obiektami interaktywnymi. |
| H6 | PPO nauczy się zachowań zbliżonych do person, ale z innym kompromisem między jakością wyników, czasem decyzji i kosztem treningu. |

## 3. Podstawa źródłowa

Praca odtwarza metodę z publikacji: **Christoffer Holmgård, Michael Cerny Green,
Antonios Liapis, Julian Togelius, „Automated Playtesting with Procedural
Personas through MCTS with Evolved Heuristics", arXiv:1802.06881.**

Gra MiniDungeons 2 jest środowiskiem eksperymentalnym, nie celem pracy. Wartością
jest sprawdzenie, czy proceduralne persony sterowane różnymi algorytmami
wytwarzają różne, mierzalne style zachowania na tych samych poziomach.

Podział źródeł i reguła rozstrzygania konfliktów:

- `minidungeons_2.pdf` → mechanika gry;
- `1802.06881v1_MCTS.pdf` → metryki, persony, podział map, protokół badań;
- przy konflikcie dotyczącym eksperymentu wygrywa artykuł MCTS. Przykład:
  startowe HP bohatera to 10, mimo że opis MD2 podaje zakres 1–10.

Oryginalne pliki map są niedostępne — mapy odtworzono z Fig. 2 i obrazów
źródłowych. W pracy trzeba jawnie napisać, że użyto rekonstrukcji, i **nie
obiecywać liczb identycznych z artykułem**. Porównania algorytmów są ważne
w ramach tej samej lokalnej implementacji. Rejestr niepewności:
`docs/benchmark.md`.

## 4. Zakres pracy (SMART)

**Specific.** Odtworzenie zasad MD2 i 11 map, implementacja metryk, czterech
person, baseline MCTS-UCB1, MCTS z ewoluowaną polityką drzewa oraz agenta PPO;
eksperymenty na 11 mapach; porównanie w tabelach, wykresach i testach
statystycznych.

**Measurable.** Wyniki liczbowe zapisywane per przebieg gry — pełny kontrakt
danych w sekcji 7, wymagane tabele i wykresy w sekcji 10.

**Available.** Oba artykuły źródłowe, obrazy map, zamrożony benchmark, baza
zasad i Python z bibliotekami naukowymi. Brakujące: oryginalne pliki map
(obejście wyżej).

**Relevant.** Autorzy wskazują persony jako sztucznych testerów poziomów —
przydatne, gdy nie ma ludzkich testerów, trzeba szybko ocenić wiele poziomów
albo poziomy są generowane proceduralnie. Rozszerzenie o PPO pozwala zapytać,
czy agent uczący się przez wzmocnienie odtworzy te same style.

**Time-bounded.** Kamienie milowe w sekcji 9.

## 5. Stan projektu

| Zakres | Stan |
| --- | --- |
| Benchmark 11 map, zamrożony i zwalidowany | **gotowe** (`md2-reconstructed-v1`, 2026-07-19) |
| Deterministyczny, klonowalny silnik MD2 | **gotowe** (`domain/engine.py`) |
| Reguły i decyzje rekonstrukcyjne spisane | **gotowe** (`docs/rules/`) |
| Cztery persony i funkcje użyteczności | **gotowe** (`domain/personas.py`) |
| Agent losowy jako punkt odniesienia | **gotowe** (`cli/random_agent.py`) |
| MCTS-UCB1, jedno drzewo na mapę | **gotowe** (`domain/mcts.py`) |
| Eksperyment wznawialny + raport Tabeli II | **gotowe** (`cli/mcts_experiment.py`) |
| Przeliczenie baseline UCB1 na pełnym zakresie | **do zrobienia** — `data/results/` jest pusty |
| MCTS z ewoluowaną polityką drzewa (GP) | do zrobienia |
| PPO jako rozszerzenie porównawcze | do zrobienia |
| Analiza cech poziomów, tabele i wykresy | do zrobienia |
| Testy statystyczne | do zrobienia |

Struktura katalogów i sposób uruchamiania: `README.md`.
Zasady gry i metryki: `docs/rules/game-rules.md`.
Persony i ich wzory: `docs/rules/game-rules.md`, sekcja 16.

Technologie jeszcze niewprowadzone (projekt nie ma dziś żadnych zewnętrznych
zależności): numpy, pandas, scipy, matplotlib lub seaborn, Gymnasium,
Stable-Baselines3, opcjonalnie tqdm.

## 6. Agenci do zaimplementowania

### 6.1. MCTS-UCB1 — gotowe

Baseline zgodny z artykułem: osobne uruchomienia dla każdej persony, ta sama
funkcja użyteczności, klasyczna polityka drzewa.

```text
UCB = w_i / n_i + c * sqrt(ln(t) / n_i)
```

gdzie `w_i` to suma wyników dziecka, `n_i` liczba jego odwiedzin, `t` suma
odwiedzin rodzeństwa, a `c = sqrt(2)`.

Protokół: 4 persony × 11 map × 50 prób, stałe seedy, rollout 10 losowych ruchów,
jedno drzewo na mapę. Szczegóły polityki kończenia szukania:
`docs/rules/game-rules.md`, sekcja 17.

### 6.2. MCTS z ewoluowaną polityką drzewa

Cel: odtworzyć główny element artykułu, zastępując UCB1 formułą wyewoluowaną
przez programowanie genetyczne.

Reprezentacja:

- chromosom jako drzewo wyrażenia matematycznego;
- operatory: dodawanie, odejmowanie, mnożenie, bezpieczne dzielenie;
- liście: stałe z zakresu `[-1, 1]` albo metryki rozgrywki.

Parametry z artykułu:

| Parametr | Wartość |
| --- | --- |
| populacja | 100 osobników |
| liczba wysp | 5 |
| liczba generacji | 100 |
| niezależne uruchomienia | 3 |
| elityzm | 15% |
| mutacja | 10% |
| mapy treningowe | 1, 2, 3, 4, 7, 10 |
| test | wszystkie 11 map |

### 6.3. PPO

Cel: rozszerzenie względem artykułu — sprawdzenie, czy uczenie ze wzmocnieniem
odtwarza zachowania person.

Wymagania:

- wrapper środowiska zgodny z Gymnasium;
- przestrzeń akcji obejmująca ruchy i docelowo oszczep;
- obserwacja: stan lokalny albo pełna siatka mapy;
- reward wynikający z funkcji użyteczności persony;
- osobny model dla każdej persony;
- trening na tych samych 6 mapach co GP, test na wszystkich 11;
- zapis krzywych uczenia, modeli i konfiguracji.

## 7. Kontrakt danych wynikowych

Każdy przebieg gry zapisuje jeden rekord. Minimalne kolumny:

```text
run_id, seed, map_id, agent_type, persona, trial,
won, died, steps, decision_time_sec, total_time_sec,
hp_left, proximity_to_exit,
monsters_slain, monster_ratio,
potions_drunk, potion_ratio,
treasures_opened, treasure_ratio,
interactive_consumed, interactive_ratio,
javelins_thrown, teleports_used, traps_sprung, minitaur_knockouts
```

Obecny `cli/mcts_experiment.py` zapisuje podzbiór tych kolumn plus
`search_policy`; przy dodawaniu GP i PPO schemat trzeba rozszerzyć do pełnej
listy, zachowując `search_policy` jako rozróżnienie wariantów.

Dodatkowo trzeba zapisywać trace, potrzebny do heatmap:

- lista pozycji bohatera i lista akcji;
- zdarzenia po każdej turze;
- pozycje odwiedzone na mapie;
- końcowy powód zakończenia gry.

## 8. Statystyka

- średnia arytmetyczna, odchylenie standardowe, 95% przedział ufności;
- dwustronny test t-Studenta z poprawką Welcha, poziom istotności `p < 0.05`;
- korelacja Pearsona dla cech poziomów.

Porównania do wykonania:

- MCTS-GP vs MCTS-UCB1 dla tej samej persony;
- PPO vs MCTS-UCB1 dla tej samej persony;
- PPO vs MCTS-GP dla tej samej persony;
- persony między sobą w ramach tego samego agenta.

## 9. Plan eksperymentów i harmonogram

Eksperymenty 0 (walidacja map) i 1 (sanity check agenta losowego) są wykonane.

| Nr | Eksperyment | Procedura | Wyniki | Kryterium zaliczenia |
| --- | --- | --- | --- | --- |
| 2 | Baseline MCTS-UCB1 | 4 persony × 11 map × 50 prób, stałe seedy, rollout 10 | Tabela II, heatmapy, porównanie person | pełny CSV w `data/results/`, tabela odtwarzalna przez `--report-only` |
| 3 | Ewolucja polityki drzewa | trening na mapach 1, 2, 3, 4, 7, 10; 3 niezależne uruchomienia; wybór najlepszej formuły per persona; test na 11 mapach | najlepsze formuły, przebieg fitnessu, testy istotności | istotna różnica względem UCB1 albo jawny wniosek o jej braku |
| 4 | PPO | osobny model per persona, trening na 6 mapach, test na 11, 50 prób na mapę | krzywe uczenia, metryki końcowe, analiza czasu decyzji | model uczy się stabilnie i produkuje porównywalne metryki |
| 5 | Analiza poziomów | korelacja Pearsona między cechami map a metrykami person | mapy najlepsze i najgorsze dla każdej persony | zidentyfikowane cechy istotnie skorelowane |

Cechy map do eksperymentu 5: liczba ścian, pól pustych, martwych końców,
wąskich przejść, skarbów, mikstur, potworów każdego typu, portali i pułapek
oraz długość najkrótszej ścieżki wejście–wyjście. Definicje:
`docs/rules/game-rules.md`, sekcja 14.

Kamienie milowe:

| Termin | Warunek zaliczenia |
| --- | --- |
| koniec VIII.2026 | opanowane wszystkie potrzebne technologie |
| koniec IX.2026 | aplikacja dowodzi, że eksperyment da się wykonać — pełny baseline UCB1 policzony |
| koniec X.2026 | zaimplementowana większość funkcji: MCTS-GP działa, PPO produkuje pierwsze wyniki |
| koniec XI.2026 | wyniki w formie zbliżonej do publikacji: testy Welcha, 95% CI, korelacje, heatmapy, wykresy radarowe |
| XII.2026 | pierwsza pełna wersja tekstu, bez pustych rozdziałów |
| połowa I.2027 | praca gotowa do oddania |

## 10. Wymagane tabele i wykresy

Tabele:

1. Zasady i symbole gry.
2. Metryki rozgrywki.
3. Funkcje użyteczności person.
4. Cechy map.
5. Liczebności obiektów w zrekonstruowanych mapach.
6. Niepewności rekonstrukcji map i przyjęte decyzje.
7. Wyniki MCTS-UCB1.
8. Wyniki MCTS-GP.
9. Wyniki PPO.
10. Porównanie wszystkich agentów.
11. Liczba map z istotną przewagą jednego agenta nad drugim.
12. Korelacje cech poziomów z wynikami person.

Wykresy:

1. Liczba obiektów interaktywnych na mapach.
2. Krzywe fitnessu GP.
3. Krzywe uczenia PPO.
4. Wykresy radarowe person.
5. Heatmapy odwiedzin dla wybranych map.
6. Win rate (słupkowy).
7. Monster ratio, treasure ratio, potion ratio i interactive ratio (słupkowe).
8. Porównanie czasu decyzji agentów.

## 11. Struktura pracy

1. **Wstęp** — motywacja, problem automatycznego testowania poziomów, cel,
   pytania badawcze.
2. **Przegląd literatury** — proceduralne persony, player modeling, MCTS,
   MCTS w grach jednoosobowych, programowanie genetyczne, uczenie ze
   wzmocnieniem i PPO, MiniDungeons 2 jako środowisko.
3. **Opis gry MiniDungeons 2** — mapa, obiekty, przeciwnicy, tury, oszczep,
   warunki zwycięstwa i porażki, metryki.
4. **Metoda badawcza** — persony, funkcje użyteczności, MCTS-UCB1, MCTS z GP,
   PPO, protokół eksperymentalny, testy statystyczne.
5. **Implementacja** — architektura, reprezentacja stanu, system zasad, agenci,
   zapis wyników, generowanie wykresów.
6. **Eksperymenty i wyniki** — opis map, wyniki trzech agentów, porównania,
   heatmapy, korelacje cech poziomów.
7. **Dyskusja** — interpretacja różnic między personami, czy PPO odtwarza
   persony, ograniczenia reprodukcji, ograniczenia map i czasu obliczeń.
8. **Wnioski** — odpowiedzi na pytania badawcze, co udało się odtworzyć,
   co wnosi rozszerzenie PPO, kierunki dalszego rozwoju.

## 12. Ryzyka otwarte

| Ryzyko | Plan awaryjny |
| --- | --- |
| Zbyt wolny MCTS-GP | ograniczyć budżet czasu i liczbę iteracji, cache'ować cechy map, uruchamiać partiami, opisać kompromis czas–jakość |
| PPO uczy się niestabilnie | zacząć od prostszej obserwacji i nagrody, ograniczyć porównanie do zachowania końcowego, pokazać krzywe uczenia, traktować PPO jako rozszerzenie, nie warunek reprodukcji |
| Niepewności rekonstrukcji map | utrzymywać `docs/benchmark.md` jako jawny rejestr, porównywać algorytmy na tych samych mapach, nie obiecywać liczb identycznych z artykułem |

Ryzyko rozjazdu między opisem gry i opisem eksperymentu jest zamknięte regułą
z sekcji 3. Ryzyko zbyt czasochłonnych pełnych zasad MD2 zmaterializowało się
i zostało obsłużone — silnik implementuje pełny zestaw mechanik.

## 13. Definicja ukończenia projektu

- zrekonstruowane mapy zamrożone i opisane, niepewności udokumentowane,
  pary portali w metadanych;
- środowisko gry działa deterministycznie;
- wszystkie persony mają funkcje użyteczności;
- MCTS-UCB1, MCTS-GP i PPO działają dla 4 person;
- eksperymenty zapisują surowe wyniki, a analiza generuje tabele i wykresy;
- wyniki są interpretowalne;
- repozytorium pozwala odtworzyć eksperyment;
- praca opisuje zarówno sukcesy, jak i ograniczenia.

## 14. Najbliższy krok

Przeliczyć pełny baseline UCB1 — 11 map × 4 persony × 50 prób:

```powershell
.\.venv\Scripts\python.exe -m src.minidungeons.cli.mcts_experiment --trials 50 --time-limit 300
```

Eksperyment jest wznawialny, więc można go prowadzić partiami. Po zakończeniu
wygenerować Tabelę II przez `--report-only` i dopiero wtedy zaczynać GP.
