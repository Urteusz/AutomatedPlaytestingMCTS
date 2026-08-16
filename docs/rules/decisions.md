# MiniDungeons 2 — decyzje rekonstrukcyjne v1

Status: **obowiązujący zestaw zasad rekonstrukcji**.

Ten plik oddziela reguły wzięte z publikacji od decyzji podjętych tam, gdzie
publikacje milczą albo są niespójne. Wartości liczbowe są w
`data/rules/md2_rules.json` i `data/rules/personas.json`; ten dokument jest ich
skrótem dla człowieka wraz z uzasadnieniem. Nie twierdzimy, że decyzje
rekonstrukcyjne odpowiadają oryginalnemu kodowi autorów.

Źródła:

- `docs/reference/articles/minidungeons_2.pdf`, sekcja 2 — mechanika gry;
- `docs/reference/articles/1802.06881v1_MCTS.pdf`, sekcje IV–V i Table I —
  wariant eksperymentalny, metryki i persony.

## Reguły określone przez publikacje

- gra jest deterministyczna, turowa i używa czterech kierunków ruchu;
- bohater zaczyna eksperyment MCTS z 10 HP i wygrywa po wejściu na wyjście;
- bohater działa pierwszy, a NPC później w stałej kolejności ich początkowych
  pozycji, wierszami od lewego górnego rogu;
- potion leczy bohatera o 1 do maksimum 10, treasure zwiększa wynik skarbów,
  trap zadaje 1 obrażenie przy każdym wejściu, a portal teleportuje natychmiast;
- bohater ma jeden odzyskiwalny oszczep zadający 1 obrażenie;
- Goblin, Wizard, Blob, Ogre i Minitaur zachowują się zgodnie z opisami
  w publikacjach;
- Minitaur nie ma HP, nie ginie i po obrażeniu jest wyłączony na 3 rundy;
- wzory Runnera, Monster Killera, Treasure Collectora i Completionista są
  zapisane w `data/rules/personas.json`;
- `R̄` (Average MCTS reward) to średnia użyteczność propagowana do węzła,
  człon `wᵢ/nᵢ` z UCB1 (MCTS eq. 1).

## Niejednoznaczności zamknięte deterministyczną decyzją

| Id | Status w źródłach | Decyzja v1 | Powód |
| --- | --- | --- | --- |
| `hero_start_hp` | konflikt | 10 HP | Opis MD2 dopuszcza 1–10 HP; reprodukowany eksperyment MCTS startuje jawnie z 10 HP. |
| `line_of_sight_geometry` | nieokreślone; osie **refutowane** obrazkiem | cztery osie **oraz** dokładne skosy 45° (`line_of_sight.geometry: "axis8"`), narożnik blokuje, gdy oba kafle boczne są ścianami (`corners: "permissive"`), blokują wyłącznie ściany; przełączniki zostawione na `axis4`/`raycast` i `transparent`/`strict` | Publikacje wymagają „unbroken line of sight" i nie definiują ani geometrii, ani blokerów. **Osie są wykluczone**: na prawym panelu MD2 Fig. 1 (po 3 turach) ogr opuszcza `(12,2)`, zjada skarb z `(13,1)` i staje na `(14,1)`, a osiowo widzi z `(12,2)` tylko `(12,1)` i `(13,2)`, do których bohater nie dojdzie w 3 turach — więc nie mógłby się ruszyć. Wyboru **spośród wariantów skośnych Fig. 1 nie rozstrzyga** (wszystkie dają ten sam prawy panel), a liczba 118 rzutów z MD2 §Complexity nie jest odtwarzana przez żaden z 21 dokładnie policzonych wariantów (osie 70, `axis8` 95, raycast 143). `axis8` wybrane jako minimalne rozszerzenie zgodne z Fig. 1, z całkowitą liczbą kafli na każdym promieniu (czyli jednoznacznym „within 5 tiles") i zaniżonym, nie zawyżonym branchingiem (3,19 vs 3,41). `permissive` zamiast `transparent`, bo `transparent` przepuszczał wzrok **przez punkt styku dwóch ścian** — na `map02` ogr z `(13,1)` widział skarb `(10,4)` przez zerowej szerokości szczelinę między `(11,2)` i `(12,3)` i szedł w bok zamiast na bohatera. `strict` odrzucone, bo blokuje też muśnięcie pojedynczego narożnika przy otwartym drugim boku i zmienia panel Fig. 1 (goblin `[12, 5]` przestaje się ruszać). Test: `test_sight_does_not_squeeze_between_two_wall_corners_on_map02`. |
| `los_distance_metric` | nieokreślone | `chebyshev` (długość promienia w kaflach) | Przy skosach „closest" i „within 5 tiles" przestają być jednoznaczne. Chebyshev = liczba kafli wzdłuż promienia, więc jest spójny z geometrią LOS i przy `axis4` sprowadza się do starego dystansu osiowego. Alternatywa `manhattan` (realny koszt przejścia po siatce 4-spójnej) jest w regułach; liczba 118 na nią nie wpływa, bo oszczep nie ma limitu zasięgu. |
| `equal_path_tie_break` | nieokreślone | kolejność sąsiadów N, E, S, W | Deterministyczny silnik i powtarzalny MCTS wymagają stałego tie-breaka. |
| `target_tie_break` | częściowo wymuszone | klucz sortowania `(dystans, obiekt przed bohaterem, wiersz, kolumna)` | MD2: przy równym dystansie Blob i Ogre wybierają obiekt przed bohaterem (cytat dosłowny); dalszy remis (wiersz, kolumna) jest arbitralny. |
| `blocked_path_detour` | nieokreślone | omijana postać jest nieprzejezdna **wewnątrz** przeszukiwania, więc NPC obchodzi ją inną ścieżką; stoi dopiero, gdy żadna ścieżka nie istnieje | „Unika kolizji" czytamy jako zmianę trasy, nie jako rezygnację z ruchu — inaczej jeden goblin blokowałby drugiego na stałe. |
| `goblin_avoidance_scope` | częściowo nieokreślone | goblin i wizard omijają tylko gobliny i wizardy; w bloba, ogra i Minitaura mogą wejść i wywołać kolizję | Publikacja mówi „Goblins avoid colliding with other Goblins and Goblin Wizards" i milczy o pozostałych; dla wizarda przyjęto symetrycznie tę samą regułę. |
| `wait_action` | wymuszone danymi | niedostępna; legalne są ruchy i dostępne rzuty oszczepem | MD2 §3: branching factor 3,41 = (240+118)/105; akcja czekania dałaby 4,41. |
| `illegal_move` | wymuszone danymi | ruch w ścianę lub poza planszę jest akcją nielegalną, nie no-op | MD2 §3: 240 ruchów / 105 kafli = 2,29 średniego stopnia; ruch-w-ścianę jako no-op dałby ≥ 4 na kafel. |
| `collision_timing` | nieokreślone | obrażenia kolizji są jednoczesne; wchodzący zajmuje pole tylko wtedy, gdy okupant zniknie | Publikacje opisują obrażenia przy kolizji, ale nie kolejność obrażeń, śmierci i ruchu. |
| `wizard_without_los` | **konflikt między publikacjami, rozstrzygnięty obrazkiem** | w LOS do 5 kafli rzuca czar; w LOS powyżej 5 kafli podchodzi o 1 kafel; **bez LOS stoi** (wersja artykułu MCTS; `monsters.wizard.moves_without_los: false`) | Artykuł MCTS §IV: „cast a spell... if they have an unbroken line of sight within 5 tiles... If they are over 5 tiles from the player **but have line of sight**, they will move 1 tile towards the player" — oba działania wymagają LOS, bez LOS nie ma klauzuli. MD2 §2 mówi przy tej samej regule „otherwise, they move 1 step toward the Hero", bez warunku LOS, co dawałoby wieczny pościg. Rozstrzyga prawy panel MD2 Fig. 1: żaden z wizardów (`[1, 3]` i `[13, 7]`) nie zmienia pola przez 3 tury, a wersja MD2 przesunęłaby je na `[3, 2]` i `[15, 6]` — ich linia wzroku do bohatera jest przez cały ten czas przerwana. Wersja MD2 została zachowana jako `moves_without_los: true`. Test: `test_wizard_without_line_of_sight_stays_unless_rules_say_otherwise`. |
| `javelin_details` | częściowo wymuszone | dowolny widoczny potwór; inne postacie nie zasłaniają; oszczep ląduje na polu celu i zostaje tam po jego śmierci; podniesienie automatyczne po wejściu | MD2 §3: 118 > 105 wymusza parametryzację celem, nie liczbę kafli; pole lądowania jest opisane, pośrednie postacie i moment podbioru — nie. |
| `portal_occupied_destination` | nieokreślone | teleport zablokowany; postać zostaje na portalu wejściowym | Publikacje nie definiują teleportu na zajęty portal. |
| `trap_minitaur` | nieokreślone | pułapka ogłusza Minitaura na trzy jego akcje | Pułapki działają na każdą postać, a Minitaur zamienia obrażenia na ogłuszenie zamiast utraty HP; publikacja nie łączy tych dwóch zdań wprost. |
| `blob_merge_and_turn_order` | częściowo nieokreślone | poziomy sumują się do maksimum 3; scalony blob zachowuje niższy oryginalny indeks kolejki | Publikacje definiują trzy poziomy mocy i scalanie, ale nie arytmetykę ani tożsamość w kolejce. |
| `npc_exit_behavior` | nieokreślone | wyjście jest dla NPC neutralną, przechodnią podłogą; wygrywa tylko bohater | Tylko bohater ma zdefiniowaną interakcję z wyjściem. |
| `terminal_turn_order` | nieokreślone | wejście na wyjście kończy grę przed odpowiedziami NPC | Publikacje mówią, że poziom kończy się na wyjściu, ale nie czy pozostałe tury NPC się wykonują. |
| `proximity_to_exit` | rozstrzygnięte empirycznie | `PE = 0` na kaflu wyjścia, `−1` wszędzie indziej | Jedyny wariant, który na baseline UCB1 odtwarza win rate artykułu (< 15% dla wszystkich person, C > R); patrz sekcja niżej. |
| `interactive_objects_consumed` | rozstrzygnięte arytmetycznie | `IC` = zabici przez bohatera wrogowie + wypite potiony + otwarte skarby, dzielone przez ich początkową sumę | Footnote Table I nazywa `IC` obiektami nie-potworami, ale to łamie `IC ≤ max(PD,TO)` w 8 z 8 wierszy Table II — footnote jest błędem redakcyjnym; opis persony Completionisty rządzi. |
| `monsters_slain_denominator` | wymuszone opisem | mianownik to początkowe zabijalne potwory bez Minitaurów; liczą się tylko kolizje bohatera i oszczep | MD2: Minitaur nie ma HP i nie może zginąć, więc nie wchodzi do mianownika metryki „zabici". |
| `hero_only_counters` | nieokreślone | `TS` i `TU` liczą wyłącznie pułapki i portale użyte przez **bohatera**; aktywacje przez NPC są pomijane | Table I opisuje styl gry persony, więc licznik musi mierzyć decyzje bohatera, nie ruch tła. Pułapki nadal ranią NPC — tylko nie wchodzą do metryki. |

## Dlaczego `PE` jest binarne

Wariant `graded` (`PE = -dystans/maksymalny dystans`) na baseline UCB1 (2200
partii, 4 persony × 11 map × 50 prób, limit 300 s) dał win rate **R 47% /
MK 23% / TC 18% / C 29%** — poziom i kolejność person **ewoluowanych** z
artykułu (R = C = 100% > MK 73% > TC 54%), nie baseline'u (artykuł: poniżej
15% dla wszystkich, C wygrywa częściej niż R). `binary` (`PE = 0` na wyjściu,
`−1` wszędzie indziej) odtwarza oba: win rate **C 18,2% / MK 16,4% / R 9,1% /
TC 9,1%** (55 partii/personę) i kolejność C > R. Sweep interpretacji (runner,
6 map, 30 partii/wariant) potwierdza, że tylko `binary` zbija wynik — `graded`,
Manhattan, euklides i Chebyshev dają 77-90% niezależnie od geometrii.

Mechanizm: przy `binary` Runner ma utility ≈ `−1 − 0,01·kroki`, więc jedyne,
co optymalizuje, to nie ruszać się. Completionist ma `0,7·IC`, gęsty sygnał do
zbierania obiektów, a wyjście trafia po drodze — stąd odwrócenie kolejności.

`graded` został usunięty z kodu i konfiguracji — `binary` jest jedyną
implementacją `PE`.

Otwarta uwaga mechanizmowa, nie powód do zmiany: `c = √2` w UCB1 wymaga
nagrody ograniczonej do `[0,1]` (MCTS §III-A, cytat dosłowny), a baseline
propaguje surową użyteczność persony — ujemną, do −6 z karą śmierci. To może
współtłumaczyć niski win rate baseline'u niezależnie od `PE`. Do
zweryfikowania: **Test 3** — przeliczyć baseline z użytecznością
znormalizowaną do `[0,1]` przy `c = √2`.

## Świadomie otwarte

- eq. 6-9 (wyewoluowana polityka drzewa) nie są jeszcze zaimplementowane —
  silnik MCTS uruchamia dziś wyłącznie baseline UCB1;
- publikacja nie podaje pełnego budżetu iteracji ani czasu dla każdego wariantu;
- bez oryginalnego silnika nie można potwierdzić bitowej zgodności rzadkich
  kolizji ani ukrytych warstw obiektów pod sprite'ami;
- kolizja NPC z leżącym oszczepem nie jest opisana w publikacjach i nie jest
  modelowana w silniku;
- definicja `PE` jest jawnie wybraną interpretacją i musi być raportowana
  w pracy.

## Pliki wykonawcze

| Plik | Rola |
| --- | --- |
| `data/rules/md2_rules.json` | parametry liczbowe silnika |
| `data/rules/personas.json` | wagi person i kara śmierci |
| `src/minidungeons/domain/rules.py` | wczytywanie konfiguracji |
| `src/minidungeons/domain/engine.py` | deterministyczny, klonowalny silnik |
| `src/minidungeons/domain/personas.py` | funkcje użyteczności person |
| `tests/domain/test_rules_engine.py` | testy mechanik i sytuacji brzegowych |
