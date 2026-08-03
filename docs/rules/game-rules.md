# MiniDungeons 2 — zasady gry

Baza wiedzy o logice gry i pomiarach. Warstwa wizualna nie musi być odtworzona
1:1, jeśli zachowana jest logika kafli, obiektów, przeciwników i metryk.

## Źródła i podział odpowiedzialności

| Plik | Odpowiada na pytanie |
| --- | --- |
| `docs/reference/articles/minidungeons_2.pdf` | jak działa gra: obiekty, przeciwnicy, oszczep, portale, kolejność tur |
| `docs/reference/articles/1802.06881v1_MCTS.pdf` | jak autorzy badali persony: metryki (Table I), 11 map, protokół MCTS |

W razie konfliktu dla eksperymentu ważniejszy jest artykuł MCTS — dlatego
bohater startuje z 10 HP, a nie z zakresu 1–10 HP z opisu MD2.

Ten dokument jest w trybie twierdzącym: opisuje, jak gra działa w tej
implementacji. Miejsca, w których publikacje milczą, są rozstrzygnięte
w `docs/rules/decisions.md` — każda sekcja odsyła do właściwych
identyfikatorów decyzji. Wartości liczbowe wykonuje
`data/rules/md2_rules.json`, a `src/minidungeons/domain/engine.py` jest
ostatecznym źródłem prawdy o zachowaniu.

## 1. Model gry

MiniDungeons 2 jest deterministyczną, turową, jednoosobową grą roguelike
na siatce kafli. Bohater przechodzi przez poziom, a celem jest dotarcie
do wyjścia.

Konsekwencje dla implementacji:

- ten sam stan i ta sama akcja dają ten sam kolejny stan;
- losowość występuje wyłącznie w agentach (rollout MCTS), nigdy w regułach gry;
- stan musi być klonowalny, bo MCTS symuluje przyszłość;
- stany terminalne to zwycięstwo i śmierć; timeout jest warunkiem eksperymentu,
  nie regułą gry.

## 2. Plansza i kafle

- plansza ma 10 kolumn i 20 wierszy; `map05` jest jawnym wyjątkiem 11 × 14,
  potwierdzonym siatką kontrolną (`docs/benchmark.md`);
- każdy kafel jest ścianą albo polem przechodnim;
- kafel przechodni ma warstwę terenu oraz opcjonalnie warstwę obiektu
  i warstwę postaci;
- obiekty gry to skarby, mikstury, portale, pułapki i wyjście;
- obiekty podłogowe nie blokują ruchu; postacie blokują, o ile reguła kolizji
  nie mówi inaczej;
- 11 map jest stałym zestawem testowym, nie są generowane proceduralnie.

Format tekstowy i symbole opisuje `docs/benchmark.md`.

## 3. Zwycięstwo i porażka

- bohater wygrywa natychmiast po wejściu na wyjście; NPC nie odpowiadają
  w tej turze;
- bohater przegrywa, gdy jego HP spadnie do 0 lub mniej;
- jeśli HP spadnie do zera przed wejściem na wyjście, gra kończy się śmiercią.

Decyzje: `terminal_turn_order`.

## 4. HP i obrażenia

Wszystkie postacie mają HP z wyjątkiem Minitaura. To jedyna tabela parametrów
w tym dokumencie — wartości wykonywalne są w `data/rules/md2_rules.json`.

| Postać / obiekt | HP | Obrażenia | Uwagi |
| --- | ---: | ---: | --- |
| Bohater | 10 (maks. 10) | 1 przez kolizję, 1 oszczepem | brak osobnej akcji melee |
| Goblin | 1 | 1 przy kolizji | |
| Wizard | 1 | 1 zaklęciem z zasięgu ≤ 5 | nie zadaje obrażeń przy kolizji |
| Blob poziom 1 | 1 | 1 | obrażenie zabija |
| Blob poziom 2 | 2 | 2 | obrażenie obniża poziom o 1 |
| Blob poziom 3 | 3 | 3 | poziom maksymalny |
| Ogr | 2 | 2 | rani również inne ogry |
| Minitaur | brak | 1 przy kolizji | nie ginie; obrażenie ogłusza na 3 jego akcje |
| Pułapka | — | 1 każdej wchodzącej postaci | nie znika po aktywacji |
| Mikstura | — | leczy bohatera o 1 do maks. 10 | blob usuwa ją bez leczenia |
| Oszczep | — | 1 | |

Śmierć postaci po obrażeniach rozpatrujemy natychmiast. Kolizja bohatera
z potworem oznacza, że bohater zadaje 1 obrażenie, a potwór zadaje swoje,
jeśli jego typ ma obrażenia kolizyjne. Obrażenia są jednoczesne.

Decyzje: `hero_start_hp`, `collision_timing`.

## 5. Tura i kolejność ruchu

- bohater wykonuje pierwszy ruch w każdej turze;
- po nim NPC odpowiadają deterministycznie;
- kolejność NPC wynika z ich **początkowej** pozycji na mapie, wierszami
  od lewego górnego rogu, i nie zmienia się, gdy NPC później się przemieszczą;
- martwe NPC są usuwane przed swoją kolejką;
- scalony blob przejmuje niższy indeks kolejki z łączących się blobów;
- ogłuszony Minitaur pozostaje w kolejce, ale jego akcją jest brak ruchu;
- jeśli gra jest terminalna po ruchu bohatera, NPC nie ruszają się.

Decyzje: `blob_merge_and_turn_order`, `terminal_turn_order`.

## 6. Ruch

- postać porusza się o 1 kafel w jednym z czterech kierunków;
- kolejność rozpatrywania sąsiadów to **N, E, S, W** — to tie-break dla
  równych ścieżek;
- ruch w ścianę lub poza planszę jest akcją **nielegalną**, nie akcją bez
  efektu — takie ruchy nie pojawiają się na liście legalnych akcji;
- postać wchodząca na portal jest natychmiast teleportowana do sparowanego
  portalu w tej samej turze;
- wyjście jest interaktywne tylko dla bohatera;
- portale działają dla wszystkich postaci, ale metrykę `TU` liczymy wyłącznie
  dla użyć bohatera.

Decyzje: `equal_path_tie_break`, `illegal_move`, `npc_exit_behavior`.

## 7. Linia wzroku

- linia wzroku działa **tylko w czterech kierunkach osiowych**;
- blokują ją wyłącznie ściany;
- postacie i obiekty jej nie blokują;
- dystans liczymy liczbą kafli w osi.

To jedna z najważniejszych decyzji rekonstrukcyjnych, bo wpływa na ruch
wszystkich przeciwników i na dostępność rzutu oszczepem.

Decyzje: `line_of_sight_geometry`.

## 8. Bohater

- jest postacią gracza i wykonuje pierwszy ruch w turze;
- zaczyna z 10 HP i jednym wielorazowym oszczepem;
- jego celem jest dotarcie do wyjścia;
- akcje bohatera to ruchy oraz rzut oszczepem, gdy oszczep jest dostępny
  i cel jest w linii wzroku;
- rzut zużywa akcję bohatera w turze;
- nie ma osobnego przycisku ataku wręcz — atak wynika z kolizji;
- nie ma akcji czekania.

Decyzje: `wait_action`, `illegal_move`.

## 9. Oszczep

- bohater dostaje jeden wielorazowy oszczep na początku każdego poziomu;
- oszczep zadaje 1 obrażenie dowolnej innej postaci w nieprzerwanej,
  osiowej linii wzroku;
- inne postacie **nie zasłaniają** celu;
- oszczep ląduje na aktualnym kaflu wybranego celu i zostaje tam także wtedy,
  gdy cel zginie;
- bohater podnosi oszczep automatycznie po wejściu na jego kafel;
- rzut liczy się do metryki `JT`, ale **nie** do liczby kroków `ST`.

Artykuł zauważa, że gra może być nieskończona: gracz może chodzić w tę i we
w tę, wciąż radząc sobie z Minitaurem oszczepem. Dlatego eksperyment potrzebuje
jawnego limitu czasu.

Decyzje: `javelin_details`.

## 10. Obiekty podłogowe

### 10.1. Wyjście

Cel poziomu. Wejście bohatera kończy grę zwycięstwem. Dla NPC jest neutralnym
polem przechodnim.

### 10.2. Mikstura

Leczy bohatera o 1 HP, nie pozwalając przekroczyć 10. Jest konsumowana przez
bohatera i przez bloba — blob usuwa ją, ale się nie leczy. Pozostałe NPC ją
ignorują. Po konsumpcji nie może zostać użyta ponownie. Nie blokuje ruchu.

### 10.3. Skarb

Zwiększa wynik skarbów bohatera. Jest konsumowany przez bohatera i przez ogra.
Ogr po zjedzeniu skarbu zmienia sprite — zmiana jest czysto wizualna, bez
efektu mechanicznego. Pozostałe NPC ignorują skarb. Nie blokuje ruchu.

### 10.4. Portal

- portale występują parami; siedem map zawiera jedną parę dającą skrót;
- wejście postaci w portal przenosi ją natychmiast do sparowanego portalu
  w tej samej turze;
- pole docelowe nie może być ścianą;
- jeśli pole docelowe jest zajęte, **teleport jest zablokowany** i postać
  zostaje na portalu wejściowym;
- teleportacja nie zwiększa `ST` poza samym ruchem wejścia na portal;
- wejście bohatera na portal zwiększa `TU`.

Decyzje: `portal_occupied_destination`.

### 10.5. Pułapka

- zadaje 1 obrażenie każdej postaci wchodzącej na jej kafel, za każdym razem;
- nie znika po aktywacji;
- rani bohatera i NPC posiadające HP;
- Minitaura, który nie ma HP, **ogłusza na trzy jego akcje**;
- sześć map zawiera co najmniej jedną pułapkę.

Decyzje: `trap_minitaur`.

## 11. Przeciwnicy

### 11.1. Goblin

- porusza się o 1 kafel w stronę bohatera po najkrótszej ścieżce,
  ale **tylko gdy ma nieprzerwaną linię wzroku**; bez niej stoi;
- ma 1 HP i zadaje 1 obrażenie przy kolizji;
- omija kolizje z innymi goblinami i z wizardami: ich pola są nieprzejezdne
  wewnątrz przeszukiwania ścieżki, więc goblin **obchodzi je inną trasą**;
  stoi dopiero wtedy, gdy żadna ścieżka nie istnieje;
- w bloba, ogra i Minitaura może wejść, wywołując kolizję.

Decyzje: `goblin_avoidance_scope`, `blocked_path_detour`.

### 11.2. Wizard (goblin dystansowy)

- jeśli ma nieprzerwaną linię wzroku do bohatera w zasięgu **5 kafli włącznie**,
  rzuca zaklęcie zadające 1 obrażenie;
- w przeciwnym razie podchodzi o 1 kafel w stronę bohatera — ale tylko przy
  zachowanej linii wzroku; bez niej stoi;
- nigdy nie atakuje i nie rusza się w tej samej turze;
- ma 1 HP i **nie zadaje obrażeń przez kolizję**;
- dystans liczony jest po osi linii wzroku;
- omija gobliny i wizardy tak samo jak goblin.

Decyzje: `wizard_without_los`, `goblin_avoidance_scope`, `blocked_path_detour`.

### 11.3. Blob

- nie rusza się, jeśli nie widzi mikstury ani bohatera;
- rusza się o 1 kafel w stronę najbliższego widocznego celu;
- przy równym dystansie **preferuje miksturę** przed bohaterem; dalszy remis
  rozstrzyga porządek wierszowy (klucz: dystans, obiekt przed bohaterem,
  wiersz, kolumna);
- konsumuje miksturę po wejściu na jej kafel, ale się nie leczy;
- po kolizji z innym blobem scala się w silniejszego: poziomy sumują się
  do `min(3, a + b)`, scalony blob zostaje na kaflu kolizji;
- otrzymanie obrażeń obniża poziom o 1; blob poziomu 1 ginie;
- zadaje obrażenia równe swojemu poziomowi każdej kolidującej postaci,
  która nie jest blobem.

Decyzje: `target_tie_break`, `blob_merge_and_turn_order`.

### 11.4. Ogr

- nie rusza się, jeśli nie widzi skarbu ani bohatera;
- rusza się o 1 kafel w stronę najbliższego widocznego celu;
- przy równym dystansie **preferuje skarb** przed bohaterem; tie-break jak
  u bloba;
- konsumuje skarb po wejściu na jego kafel;
- ma 2 HP i zadaje 2 obrażenia w każdej dozwolonej kolizji, w tym innym ogrom
  — przy kolizji ogr–ogr obaj otrzymują 2 obrażenia.

Decyzje: `target_tie_break`.

### 11.5. Minitaur

- **zawsze** porusza się o 1 krok najkrótszą ścieżką A* do bohatera,
  ignorując linię wzroku;
- przy planowaniu ścieżki traktuje ściany jako blokady, a inne postacie
  i obiekty ignoruje;
- A* stosuje stały porządek sąsiadów (N, E, S, W);
- jeśli jego ruch wchodzi w inną postać, rozpatrujemy kolizję według macierzy;
- zadaje 1 obrażenie przy kolizji;
- **nie ma HP i nie może zginąć**; po otrzymaniu obrażeń jest ogłuszony
  na 3 swoje akcje;
- podczas ogłuszenia nie rusza się i można przejść przez jego kafel;
- każda mapa zawiera Minitaura, `map02` zawiera dwa.

Decyzje: `trap_minitaur`, `equal_path_tie_break`.

## 12. Macierz kolizji

| Kolizja | Rozstrzygnięcie |
| --- | --- |
| bohater + mikstura | leczy +1 (maks. 10), usuwa miksturę |
| blob + mikstura | usuwa miksturę, bez leczenia |
| bohater + skarb | zwiększa `TO`, usuwa skarb |
| ogr + skarb | usuwa skarb, zmiana sprite'a bez efektu |
| dowolna postać + portal | teleport na sparowany portal, o ile cel wolny |
| dowolna postać + pułapka | 1 obrażenie przy wejściu; Minitaur ogłuszony |
| bohater + goblin | bohater zadaje 1, goblin zadaje 1 |
| bohater + wizard | bohater zadaje 1; wizard nie zadaje kolizyjnie |
| bohater + blob | bohater zadaje 1; blob zadaje obrażenia równe poziomowi |
| bohater + ogr | bohater zadaje 1, ogr zadaje 2 |
| bohater + Minitaur | bohater otrzymuje 1; Minitaur zostaje ogłuszony |
| blob + blob | scalenie do `min(3, a + b)` |
| ogr + ogr | obaj otrzymują 2 obrażenia |
| goblin/wizard + goblin/wizard | omijanie trasą, nie kolizja |
| NPC + wyjście | neutralne pole przechodnie |
| NPC + leżący oszczep | nie modelowane (patrz „Świadomie otwarte") |

Obrażenia w kolizji są jednoczesne, a wchodząca postać zajmuje pole tylko
wtedy, gdy okupant zniknie.

Decyzje: `collision_timing`, `npc_exit_behavior`, `blocked_path_detour`.

## 13. Mapy

Artykuł podaje 11 map (Fig. 2) i następujące niezmienniki:

- trening ewolucji polityk używa map 1, 2, 3, 4, 7, 10;
- test agentów używa wszystkich 11 map;
- każda mapa zawiera co najmniej jednego Minitaura, `map02` dwa;
- `map01` i `map09` nie zawierają ogrów;
- `map04` i `map10` mają więcej wizardów niż goblinów walczących wręcz;
- `map01` ma więcej goblinów walczących wręcz niż wizardów;
- siedem map zawiera portale, sześć zawiera pułapki;
- mapy różnią się liczbą ścian, wąskich przejść, martwych końców
  i długością najkrótszej ścieżki.

Procedura rekonstrukcji: przepisujemy logikę mapy z Fig. 2, tworzymy raport
liczebności obiektów, porównujemy z Fig. 3 i akceptujemy mapę, gdy liczebności
się zgadzają. W pracy opisujemy mapy jako rekonstrukcję.

Wyniki tej procedury, poprawki audytu i sumy kontrolne: `docs/benchmark.md`.

## 14. Cechy poziomów używane w analizie

Artykuł wymienia cechy poziomów służące do korelacji z wynikami person: liczbę
obiektów interaktywnych, liczbę skarbów, mikstur, goblinów, wizardów,
Minitaurów, blobów, ogrów, portali, pułapek i ścian, wąskie przejścia
(choke points), martwe końce (dead ends), obszary otwarte (open areas),
długość najkrótszej ścieżki wejście–wyjście oraz „wiele innych"
niewymienionych wprost.

Definicje podane w artykule:

- **martwe końce** — kafle z dokładnie jednym połączonym sąsiadem przechodnim;
- **wąskie przejścia** — kafle z dwoma połączonymi sąsiadami przechodnimi;
- **obszary otwarte** — kafle, których wszyscy sąsiedzi są nie-ścianami.

Przyjęte uzupełnienia:

- cechy topologiczne liczymy na statycznej mapie;
- sąsiedztwo to 4 kierunki;
- obiekty nie wpływają na topologię;
- ścieżka wejście–wyjście liczona jest po polach przechodnich,
  w wersji bazowej bez portali.

Pełna lista „many others" nie jest znana i nie da się jej odtworzyć.

## 15. Metryki rozgrywki (Table I)

| Skrót | Nazwa | Postać |
| --- | --- | --- |
| `ST` | Steps Taken | liczba kroków |
| `PE` | Proximity to Exit | patrz niżej |
| `PD` | Potions Drunk | ratio do liczby mikstur |
| `TO` | Treasures Opened | ratio do liczby skarbów |
| `MTK` | Minitaur Knockouts | liczba ogłuszeń |
| `MS` | Monsters Slain | ratio do liczby zabijalnych potworów |
| `JT` | Javelins Thrown | liczba rzutów |
| `HL` | Health Left | pozostałe HP |
| `TU` | Teleports Used | liczba użyć portalu przez bohatera |
| `TS` | Traps Sprung | liczba pułapek wdepniętych przez bohatera |
| `R̄` | Average MCTS reward | wymienione, ale nieopisane w artykule |
| `IC` | Interactive Objects Consumed | patrz niżej |

`PD`, `MS`, `TO` i `IC` są wartościami względnymi (ratio).

Dwie metryki artykuł zostawia niedomknięte i wymagają jawnej interpretacji
w pracy:

- **`PE`** — artykuł maksymalizuje `PE`, podaje `PE = 0` po osiągnięciu wyjścia
  i nie podaje wzoru. Przyjęto `PE = -dystans / maksymalny dystans` po
  statycznej najkrótszej ścieżce: **0 na wyjściu, −1 w najdalszym punkcie
  mapy**. Portale są pomijane. To jedyny wariant spełniający jednocześnie
  „maksymalizuj" i „zero na wyjściu".
- **`IC`** — opis Completionisty obejmuje potwory, a notka pod Table I nazywa
  `IC` obiektami nie-potworami. Przyjęto wariant zgodny z opisem persony:
  zabici przez bohatera wrogowie + wypite mikstury + otwarte skarby, dzielone
  przez ich początkową sumę. Silnik raportuje dodatkowo
  `interactive_non_monster_ratio`, żeby zachować przejrzystość.

Decyzje: `proximity_to_exit`, `interactive_objects_consumed`,
`monsters_slain_denominator`.

## 16. Persony

Cztery persony różnią się wyłącznie funkcją użyteczności. Wagi i kara śmierci
są w `data/rules/personas.json`, a wykonuje je
`src/minidungeons/domain/personas.py`.

| Persona | Cel | Użyteczność (żywy) |
| --- | --- | --- |
| Runner | dotrzeć do wyjścia w jak najmniejszej liczbie ruchów | `PE - 0.01 · ST` |
| Monster Killer | zabić jak najwięcej potworów, drugorzędnie zbliżyć się do wyjścia | `0.7 · MS + 0.3 · PE` |
| Treasure Collector | zebrać jak najwięcej skarbów, drugorzędnie zbliżyć się do wyjścia | `0.7 · TO + 0.3 · PE` |
| Completionist | konsumować obiekty i zabijać potwory, drugorzędnie zbliżyć się do wyjścia | `0.7 · IC + 0.3 · PE` |

Śmierć bohatera odejmuje **5** od użyteczności każdej persony.

## 17. MCTS w protokole artykułu

Fakty z artykułu:

- wszystkie persony używają MCTS do sformułowania sekwencji akcji;
- MiniDungeons 2 jest deterministyczne, więc persona buduje **jedno drzewo
  na mapę**;
- budowa drzewa kończy się po znalezieniu zwycięskiego stanu terminalnego
  albo po timeoucie (w wynikach wspomniane maksimum 300 sekund);
- agent bierze najlepszą znalezioną sekwencję akcji;
- rollout symuluje 10 losowych ruchów przed propagacją;
- baseline używa UCB1, a wariant badany zastępuje UCB1 formułą wyewoluowaną
  przez programowanie genetyczne.

Uzupełnienia tej implementacji:

- rollout obejmuje pełne tury gry: akcja bohatera + reakcja NPC;
- losowy rollout wybiera legalne akcje bohatera;
- zwycięstwo napotkane wyłącznie w rollout wpływa na wynik tylko przez
  użyteczność w propagacji — jego losowe akcje nie stają się sekwencją
  do odegrania. Do zakończenia szukania potrzebny jest terminalny węzeł drzewa;
- po wyczerpaniu budżetu czasu agent odgrywa ścieżkę zachłanną po najwyższej
  średniej użyteczności;
- budżet czasu jest jawnym parametrem eksperymentu.

Szczegóły uruchamiania: `README.md`.

## 18. Checklist zgodności metodologicznej

Środowisko jest zgodne z artykułem, gdy:

- ma 11 map logicznie odtworzonych z Fig. 2;
- mapy mają rozmiar 10 × 20, z udokumentowanym wyjątkiem `map05` 11 × 14;
- bohater ma 10 HP, wyjście jest warunkiem zwycięstwa, a utrata HP śmiercią;
- ma mikstury, skarby, portale i pułapki;
- ma wielorazowy oszczep i linię wzroku;
- ma gobliny, wizardy, bloby, ogry i Minitaury;
- ma stałą kolejność tur NPC według pozycji początkowej;
- liczy metryki z Table I;
- implementuje Runnera, Monster Killera, Treasure Collectora i Completionistę;
- pozwala uruchomić MCTS-UCB1;
- pozwala uruchomić MCTS z ewoluowaną polityką drzewa;
- pozwala uruchomić PPO/RL jako rozszerzenie;
- zapisuje wyniki dla 50 prób na mapę;
- rozdziela mapy treningowe i testowe tak jak artykuł.

## 19. Proponowany opis do pracy

```text
Środowisko MiniDungeons 2 zostało zrekonstruowane na podstawie opisu mechanik,
metryk i map przedstawionych w publikacji źródłowej. Celem implementacji jest
zachowanie zgodności metodologicznej z eksperymentem autorów, a nie bitowa
reprodukcja oryginalnego silnika. W przypadkach, w których publikacja nie
określa jednoznacznie reguły sytuacji brzegowej, przyjęto deterministyczne
reguły implementacyjne opisane w rozdziale dotyczącym środowiska.
```
