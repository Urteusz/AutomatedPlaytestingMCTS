# Plan powolnego tworzenia pracy inzynierskiej

## 1. Tytul roboczy

**Automatyczne testowanie poziomow gry MiniDungeons 2 z wykorzystaniem proceduralnych person: reprodukcja MCTS z artykulu zrodlowego oraz porownanie z agentami uczenia ze wzmocnieniem**

Wersja krotsza:

**Automatyczne testowanie poziomow gier z wykorzystaniem proceduralnych person: MCTS, heurystyki ewolucyjne i PPO**

## 2. Sens pracy

Celem pracy jest stopniowe zbudowanie aplikacji badawczej, ktora odtwarza metode automatycznego testowania poziomow gry opisana w artykule:

**Christoffer Holmgard, Michael Cerny Green, Antonios Liapis, Julian Togelius, "Automated Playtesting with Procedural Personas through MCTS with Evolved Heuristics", arXiv:1802.06881.**

Praca nie ma polegac tylko na napisaniu gry. Gra MiniDungeons 2 jest srodowiskiem eksperymentalnym, w ktorym porownywane sa rozne modele sztucznych graczy. Glowna wartoscia pracy jest sprawdzenie, czy proceduralne persony sterowane przez rozne algorytmy podejmowania decyzji wytwarzaja rozne, mierzalne style zachowania na tych samych poziomach.

Stan projektu:

- deterministyczny silnik znajduje sie w `src/minidungeons/domain/engine.py`,
- wykonywalne reguly i cztery persony sa zaimplementowane oraz przetestowane,
- `GameService` udostepnia jeden interfejs dla REST, CLI i przyszlego MCTS,
- opcjonalny adapter FastAPI udostepnia katalog map oraz sesje rozgrywki,
- lokalne artykuly znajduja sie w `docs/reference/articles/`,
- zamrozony benchmark 11 map znajduje sie w `data/maps/md2/benchmark/`,
- obrazy zrodlowe i siatki kontrolne sa w `data/maps/md2/source-images/`,
- reguly sa opisane w `docs/rules/game-rules.md`, a parametry silnika i person
  w `data/rules/md2_rules.json` i `data/rules/personas.json`,
- `map5_grid_11x14.png` potwierdza kompletna mape 11x14 jako jawny wyjatek,
- nie ma jeszcze MCTS, ewolucji heurystyk, PPO, bazy wynikow ani warstwy analitycznej.

Plan zaklada powolne, bezpieczne rozwijanie projektu: najpierw zgodne z artykulami srodowisko gry, potem MCTS, potem ewolucja heurystyk, potem PPO, a dopiero na koncu komplet wynikow i pisanie finalnych rozdzialow.

Podzial zrodel jest nastepujacy:

- `docs/reference/articles/minidungeons_2.pdf` odpowiada na pytanie "jak dziala gra MiniDungeons 2".
- `docs/reference/articles/1802.06881v1_MCTS.pdf` odpowiada na pytanie "jak autorzy badali persony MCTS i jakie wyniki/metody trzeba odtworzyc".
- W miejscach konfliktu dla eksperymentu wazniejszy jest artykul MCTS, np. startowe 10 HP bohatera.

## 3. Zasada SMART dla zakresu pracy

### Specific - zakres konkretny

Praca ma dotyczyc bardzo konkretnego problemu:

**Czy proceduralne persony gracza, zdefiniowane przez funkcje uzytecznosci i sterowane przez MCTS, MCTS z ewoluowana polityka drzewa oraz PPO, pozwalaja automatycznie testowac poziomy gry MiniDungeons 2 i wykrywac roznice miedzy stylami gry?**

Konkretne elementy pracy:

- odtworzenie zasad gry MiniDungeons 2 na podstawie publikacji zrodlowej,
- rekonstrukcja 11 map z obrazow w artykule i `data/maps/md2/source-images/`,
- weryfikacja liczebnosci obiektow map wzgledem Fig. 3 z artykulu,
- implementacja mierzalnych metryk rozgrywki,
- implementacja czterech person: Runner, Monster Killer, Treasure Collector, Completionist,
- implementacja baseline MCTS-UCB1,
- implementacja MCTS z ewoluowana polityka drzewa,
- implementacja agenta PPO jako rozszerzenia porownawczego,
- przeprowadzenie eksperymentow na 11 mapach,
- porownanie wynikow w formie tabel, wykresow i testow statystycznych.

### Measurable - zakres mierzalny

Aplikacja ma produkowac wyniki liczbowe, ktore da sie zapisac, porownac i opisac w pracy.

Minimalne metryki:

- win rate,
- death rate,
- liczba krokow,
- czas decyzji lub czas przejscia,
- liczba zabitych potworow,
- stosunek zabitych potworow do wszystkich potworow,
- liczba wypitych mikstur,
- stosunek wypitych mikstur do wszystkich mikstur,
- liczba otwartych skarbow,
- stosunek otwartych skarbow do wszystkich skarbow,
- stosunek skonsumowanych obiektow interaktywnych,
- pozostale HP,
- dystans lub bliskosc do wyjscia,
- liczba uzyc portalu,
- liczba aktywacji pulapek,
- liczba rzutow oszczepem,
- liczba ogluszen Minitaura.

Minimalne wyniki pracy:

- tabela srednich metryk z 95% przedzialami ufnosci,
- tabela istotnych roznic miedzy agentami,
- wykres liczby obiektow na mapach,
- wykresy radarowe person,
- heatmapy odwiedzin pol mapy,
- krzywe uczenia PPO,
- porownanie czasu decyzji MCTS i PPO,
- interpretacja, ktore mapy sprzyjaja ktorym personom.

### Available - zakres osiagalny

Praca nie moze zalezec od czegos, do czego nie ma dostepu.

Od poczatku dostepne sa:

- artykul zrodlowy eksperymentu `docs/reference/articles/1802.06881v1_MCTS.pdf`,
- artykul zrodlowy zasad gry `docs/reference/articles/minidungeons_2.pdf`,
- zgloszenie tematu pracy,
- obecny kod projektu,
- lokalne mapy testowe,
- obrazy map w `data/maps/md2/source-images/`,
- pierwsza rekonstrukcja map w `data/maps/md2/benchmark/`,
- baza zasad w `docs/rules/game-rules.md`,
- Python,
- biblioteki naukowe i uczenia maszynowego mozliwe do zainstalowania lokalnie.

Oryginalne pliki map MiniDungeons 2 nie sa dostepne jako dane tekstowe, ale mapy sa widoczne jako obrazy. Dlatego nalezy:

- jawnie opisac w pracy, ze uzyto rekonstrukcji map,
- wskazac, ze rekonstrukcja powstala na podstawie Fig. 2 i `data/maps/md2/source-images/`,
- porownac liczebnosci obiektow z Fig. 3,
- oznaczyc niepewne kafle i przypadki, zwlaszcza `Map5`,
- zachowac zgodnosc metodologii z artykulem,
- nie twierdzic, ze uzyskane liczby sa identyczna reprodukcja wynikow autorow,
- porownywac algorytmy w ramach tej samej lokalnej implementacji.

Wazna decyzja reprodukcyjna:

- `minidungeons_2.pdf` opisuje start bohatera z 1-10 HP, natomiast artykul MCTS uzywa 10 HP.
- W eksperymentach pracy przyjmujemy 10 HP, bo celem jest porownanie metod wedlug protokolu MCTS.

### Real / Relevant - zakres realny i istotny

Motywacja pracy wynika bezposrednio z artykulu zrodlowego.

Autorzy wskazuja, ze proceduralne persony moga dzialac jako sztuczni testerzy poziomow gier. Taki system moze pomoc projektantom, gdy:

- nie ma jeszcze ludzkich testerow,
- trzeba szybko ocenic wiele poziomow,
- poziomy sa generowane proceduralnie,
- projektant chce zobaczyc, jak rozne style gry beda reagowac na ten sam poziom.

Rozszerzenie o PPO jest istotne, bo pozwala zadac pytanie, czy agent uczacy sie przez wzmocnienie potrafi odtworzyc podobne style zachowania jak persony MCTS korzystajace z tych samych funkcji uzytecznosci.

### Time-bounded - zakres ograniczony w czasie

Praca ma byc prowadzona etapami:

- do konca sierpnia 2026: opanowane wszystkie potrzebne technologie,
- do konca wrzesnia 2026: aplikacja udowadnia, ze eksperyment da sie wykonac,
- do konca pazdziernika 2026: aplikacja implementuje wiekszosc zalozonych funkcji,
- do konca listopada 2026: aplikacja generuje wyniki w formie zblizonej do publikacji zrodlowej,
- od poczatku grudnia 2026 do polowy stycznia 2027: powstaje tresc pracy.

## 4. Pytanie badawcze

Glowne pytanie badawcze:

**Czy proceduralne persony Runner, Monster Killer, Treasure Collector i Completionist, sterowane przez MCTS-UCB1, MCTS z ewoluowana polityka drzewa oraz PPO, uzyskuja istotnie rozne, mierzalne style zachowania podczas automatycznego testowania poziomow MiniDungeons 2?**

Pytania pomocnicze:

1. Czy MCTS z ewoluowana polityka drzewa osiaga lepsze wyniki niz klasyczny MCTS-UCB1?
2. Czy PPO potrafi odtworzyc zachowania person zdefiniowanych funkcjami uzytecznosci?
3. Czy rozne persony rzeczywiscie preferuja inne interakcje z poziomem?
4. Ktore cechy poziomow wplywaja na skutecznosc poszczegolnych person?
5. Jaki jest kompromis miedzy jakoscia gry, czasem decyzji i generalizacja na nowe mapy?

## 5. Hipotezy robocze

H1: Persony MCTS z ewoluowana polityka drzewa beda osiagac wyzsze wartosci swoich glownych metryk niz persony MCTS-UCB1.

H2: Runner bedzie mial najwyzszy win rate i najkrotsze sciezki do wyjscia.

H3: Monster Killer bedzie zabijal wiekszy odsetek przeciwnikow niz pozostale persony.

H4: Treasure Collector bedzie zbieral wiekszy odsetek skarbow niz pozostale persony.

H5: Completionist bedzie mial najwyzszy lub jeden z najwyzszych odsetkow interakcji ze wszystkimi obiektami interaktywnymi.

H6: PPO bedzie w stanie nauczyc sie zachowan zblizonych do person, ale moze miec inny kompromis miedzy jakoscia wynikow, czasem decyzji i kosztem treningu.

## 6. Zakres implementacji gry

### Etap 0 - baza wiedzy i rekonstrukcja map

Ten etap zostal zakonczony 19 lipca 2026. Benchmark `md2-reconstructed-v1` jest zweryfikowany, opisany i zamrozony jako fundament dalszej implementacji.

Istniejace artefakty:

- `docs/reference/articles/1802.06881v1_MCTS.pdf` - lokalny artykul z protokolem MCTS, personami, metrykami i wynikami,
- `docs/reference/articles/minidungeons_2.pdf` - lokalny artykul doprecyzowujacy zasady gry MiniDungeons 2,
- `docs/rules/game-rules.md` - baza wiedzy o zasadach gry, elementach opisanych w artykule i brakach definicyjnych,
- `data/maps/md2/source-images/Map1.png` ... `data/maps/md2/source-images/Map11.png` - obrazy map z warstwy wizualnej,
- `data/maps/md2/benchmark/map01.txt` ... `data/maps/md2/benchmark/map11.txt` - rekonstrukcja logiczna map,
- `docs/benchmark/legend.md` - legenda symboli map,
- `docs/benchmark/object_counts.md` - liczebnosci obiektow w zrekonstruowanych mapach,
- `docs/benchmark/uncertainties.md` - lista rzeczy, ktorych nie da sie ustalic pewnie ze zdjec.

Wynik zamkniecia etapu:

- rozdzielono zasady gry z `minidungeons_2.pdf` od metody badawczej z `1802.06881v1_MCTS.pdf`,
- zaakceptowano `map05.txt` jako potwierdzony siatka wyjatek 11x14,
- doprowadzono liczebnosci `r`, `p`, `g`, `w`, `b`, `o`, `M` do zgodnosci z Fig. 3,
- zapisano pary portali w `data/maps/md2/benchmark/portal_pairs.json`,
- zapisano decyzje i ograniczenia w `docs/benchmark/uncertainties.md`,
- zamrozono wymiary, liczebnosci, sumy kontrolne i zrodla w `data/maps/md2/benchmark/benchmark_manifest.json`,
- dodano automatyczna walidacje `tools/validate_stage0.py` oraz test `tests/test_stage0.py`.

### Etap 1 - obecna uproszczona wersja

Ten etap juz istnieje i sluzy jako baza techniczna.

Obecne zasady:

- mapa jest siatka kafli,
- `#` oznacza sciane,
- `.` oznacza puste pole,
- `E` oznacza wejscie,
- `X` oznacza wyjscie,
- `r` oznacza skarb,
- `p` oznacza miksture,
- `m` oznacza prostego potwora,
- bohater porusza sie w czterech kierunkach,
- bohater nie moze wejsc w sciane,
- wejscie na skarb zwieksza liczbe zebranych skarbow,
- wejscie na miksture leczy,
- wejscie na potwora zadaje obrazenia i usuwa potwora,
- wejscie na wyjscie konczy gre zwyciestwem,
- spadek HP do zera konczy gre smiercia.

Ten etap nie jest jeszcze zgodny z pelnym MiniDungeons 2, ale jest dobrym smoke-testem dla przyszlych agentow.

### Etap 2 - pelniejsze MiniDungeons 2

Na podstawie `minidungeons_2.pdf` i `1802.06881v1_MCTS.pdf` nalezy dodac:

- maksymalne HP bohatera rowne 10,
- startowe HP bohatera rowne 10 dla eksperymentu MCTS,
- mikstury leczace o 1 HP do maksimum 10,
- pulapki zadajace 1 obrazenie przy kazdym przejsciu,
- portale dzialajace parami dla postaci, nie tylko dla bohatera,
- oszczep bohatera,
- obrazenia bohatera: 1 obrazenie przez kolizje albo oszczep,
- line-of-sight,
- kolejnosc tur: najpierw bohater, potem NPC,
- stala kolejnosc ruchu NPC wedlug poczatkowego polozenia na mapie,
- rozne typy przeciwnikow,
- metryki wymagane przez artykul.

Decyzje implementacyjne, ktore musza zostac zapisane przed kodowaniem:

- definicja line-of-sight,
- definicja `PE` jako proximity to exit,
- definicja `IC` dla Completionist,
- pelna macierz kolizji postac-obiekt i postac-postac,
- tie-breakery ruchu NPC oraz A*,
- zasady oszczepu po trafieniu i podniesieniu,
- sposob liczenia `TU`, gdy portal zostanie uzyty przez NPC,
- zasady pulapek dla Minitaura.

### Etap 3 - przeciwnicy

Do odtworzenia sa nastepujace typy przeciwnikow:

1. **Melee enemy / Goblin**
   - porusza sie o 1 pole w strone bohatera po najkrotszej sciezce,
   - robi to tylko wtedy, gdy ma nieprzerwany line-of-sight,
   - unika kolizji z goblinami i wizardami,
   - zadaje obrazenia przy kolizji.

2. **Ranged enemy / Goblin Wizard**
   - jesli widzi bohatera w zasiegu do 5 pol, zadaje 1 obrazenie z dystansu,
   - w przeciwnym razie podchodzi o 1 pole w strone bohatera,
   - ma 1 HP,
   - nie zadaje obrazen przez kolizje.

3. **Blob**
   - nie rusza sie bez line-of-sight do bohatera albo mikstury,
   - preferuje miksture przed bohaterem w przypadku remisu,
   - po wejsciu na miksture konsumuje ja,
   - po zderzeniu z innym blobem laczy sie w silniejszego bloba,
   - poziomy bloba maja odpowiednio 1, 2 albo 3 HP i tyle samo obrazen,
   - po otrzymaniu obrazen silniejszy blob traci poziom mocy.

4. **Ogre**
   - nie rusza sie bez line-of-sight do bohatera albo skarbu,
   - preferuje skarb przed bohaterem w przypadku remisu,
   - po wejsciu na skarb konsumuje go,
   - ma 2 HP,
   - zadaje 2 obrazenia przy kolizji.

5. **Minitaur**
   - zawsze porusza sie o 1 pole najkrotsza sciezka do bohatera,
   - sciezka jest liczona algorytmem A*,
   - podczas planowania ignoruje inne postacie i obiekty,
   - zadaje 1 obrazenie przy kolizji,
   - nie moze zostac zabity,
   - po otrzymaniu obrazen zostaje ogluszony na 3 tury.

## 7. Persony i funkcje uzytecznosci

### Runner

Cel: jak najszybciej dotrzec do wyjscia.

Metryki:

- `PE` - bliskosc wyjscia,
- `ST` - liczba krokow,
- kara za smierc.

Funkcja:

```text
U_R = PE - 0.01 * ST                  gdy bohater zyje
U_R = PE - 0.01 * ST - 5              gdy bohater umarl
```

### Monster Killer

Cel: zabic jak najwiecej potworow, a drugorzednie dotrzec blisko wyjscia.

Metryki:

- `MS` - stosunek zabitych potworow,
- `PE` - bliskosc wyjscia,
- kara za smierc.

Funkcja:

```text
U_MK = 0.7 * MS + 0.3 * PE            gdy bohater zyje
U_MK = 0.7 * MS + 0.3 * PE - 5        gdy bohater umarl
```

### Treasure Collector

Cel: zebrac jak najwiecej skarbow, a drugorzednie dotrzec blisko wyjscia.

Metryki:

- `TO` - stosunek otwartych skarbow,
- `PE` - bliskosc wyjscia,
- kara za smierc.

Funkcja:

```text
U_TC = 0.7 * TO + 0.3 * PE            gdy bohater zyje
U_TC = 0.7 * TO + 0.3 * PE - 5        gdy bohater umarl
```

### Completionist

Cel: skonsumowac jak najwiecej interaktywnych obiektow oraz dotrzec blisko wyjscia.

Metryki:

- `IC` - stosunek skonsumowanych obiektow interaktywnych,
- `PE` - bliskosc wyjscia,
- kara za smierc.

Funkcja:

```text
U_C = 0.7 * IC + 0.3 * PE             gdy bohater zyje
U_C = 0.7 * IC + 0.3 * PE - 5         gdy bohater umarl
```

## 8. Agenci do zaimplementowania

### Random Agent

Cel:

- sanity check srodowiska,
- szybkie wykrywanie bledow w zasadach,
- najprostszy punkt odniesienia.

Ten agent juz czesciowo istnieje.

### MCTS-UCB1

Cel:

- baseline zgodny z artykulem,
- oddzielne uruchomienia dla kazdej persony,
- ta sama funkcja uzytecznosci persony, ale klasyczna polityka drzewa.

Wymagania:

- selection,
- expansion,
- simulation,
- backpropagation,
- rollout na 10 losowych ruchow,
- wybor legalnych akcji,
- klonowanie stanu gry,
- brak modyfikacji oryginalnego stanu podczas symulacji,
- deterministyczne seedy eksperymentow.

Wzor UCB1:

```text
UCB = w_i / n_i + c * sqrt(ln(t) / n_i)
```

gdzie:

- `w_i` - suma wynikow dziecka,
- `n_i` - liczba odwiedzin dziecka,
- `t` - liczba odwiedzin rodzica,
- `c = sqrt(2)`.

### MCTS z ewoluowana polityka drzewa

Cel:

- odtworzyc glowny element artykulu,
- zastapic UCB1 formula wyewoluowana przez programowanie genetyczne.

Reprezentacja:

- chromosom jako drzewo wyrazenia matematycznego,
- operatory: dodawanie, odejmowanie, mnozenie, bezpieczne dzielenie,
- liscie: stale z zakresu `[-1, 1]` albo metryki rozgrywki.

Parametry z artykulu:

- populacja: 100 osobnikow,
- liczba wysp: 5,
- liczba generacji: 100,
- liczba niezaleznych uruchomien: 3,
- elityzm: 15%,
- mutacja: 10%,
- mapy treningowe: 1, 2, 3, 4, 7, 10,
- test: wszystkie 11 map.

### PPO

Cel:

- rozszerzenie pracy wzgledem artykulu,
- sprawdzenie, czy uczenie ze wzmocnieniem odtwarza zachowania person.

Wymagania:

- wrapper srodowiska zgodny z Gymnasium,
- przestrzen akcji obejmujaca ruchy i docelowo oszczep,
- obserwacja zawierajaca stan lokalny lub pelna siatke mapy,
- reward wynikajacy z funkcji uzytecznosci persony,
- trening na tych samych 6 mapach co GP,
- test na wszystkich 11 mapach,
- zapis krzywych uczenia,
- zapis modeli i konfiguracji eksperymentow.

## 9. Architektura projektu

Projekt jest uporzadkowany warstwowo; kolejne algorytmy nalezy dodawac do tej struktury:

```text
MiniDungeonsMCTS/
  data/
    maps/md2/benchmark/
    maps/md2/source-images/
    rules/
  docs/
    architecture/
    project/
    reference/articles/
    rules/
  src/minidungeons/
    domain/
    application/
    infrastructure/
    api/
    cli/
  tests/
    domain/
    application/
    data/
  tools/
  pyproject.toml
  README.md
```

Szczegoly odpowiedzialnosci warstw opisuje `docs/architecture/backend.md`.

## 10. Dane wynikowe

Kazdy przebieg gry powinien zapisywac jeden rekord.

Minimalne kolumny:

- `run_id`,
- `seed`,
- `map_id`,
- `agent_type`,
- `persona`,
- `trial`,
- `won`,
- `died`,
- `steps`,
- `decision_time_sec`,
- `total_time_sec`,
- `hp_left`,
- `proximity_to_exit`,
- `monsters_slain`,
- `monster_ratio`,
- `potions_drunk`,
- `potion_ratio`,
- `treasures_opened`,
- `treasure_ratio`,
- `interactive_consumed`,
- `interactive_ratio`,
- `javelins_thrown`,
- `teleports_used`,
- `traps_sprung`,
- `minitaur_knockouts`.

Dodatkowo nalezy zapisywac trace:

- lista pozycji bohatera,
- lista akcji,
- zdarzenia po kazdej turze,
- pozycje odwiedzone na mapie,
- koncowy powod zakonczenia gry.

Trace jest potrzebny do heatmap.

## 11. Eksperymenty

### Eksperyment 0 - walidacja rekonstrukcji map

Status: **wykonany dla benchmarku `md2-reconstructed-v1`**.

Cel:

- potwierdzic, ze mapy z `data/maps/md2/benchmark/` nadaja sie jako benchmark,
- wykryc roznice miedzy rekonstrukcja a obrazami z `data/maps/md2/source-images/`,
- ustalic, czy `Map5` jest pelna mapa, czy wymaga ponownego zrzutu obrazu.

Procedura:

- wczytac wszystkie mapy TXT,
- sprawdzic wymiary, liczbe wejsc, wyjsc, Minitaurs i portali,
- policzyc liczby treasures, potions, goblins, wizards, blobs, ogres i minitaurs,
- porownac liczby z Fig. 3 z artykulu,
- recznie przejrzec wszystkie niezgodnosci,
- zapisac finalna decyzje w `docs/benchmark/uncertainties.md`.

Wyniki:

- tabela liczebnosci obiektow,
- lista map zaakceptowanych,
- lista kafli lub map wymagajacych poprawki,
- decyzja: `map05.txt` zostaje w benchmarku jako potwierdzony siatka wyjatek 11x14.

### Eksperyment 1 - sanity check srodowiska

Cel:

- sprawdzic, czy gra dziala,
- sprawdzic, czy metryki sie zliczaja,
- uruchomic losowego agenta na wszystkich mapach.

Wyniki:

- win rate losowego agenta,
- srednia liczba krokow,
- srednie interakcje z obiektami,
- lista bledow zasad do poprawienia.

### Eksperyment 2 - MCTS-UCB1

Cel:

- odtworzyc baseline z artykulu.

Procedura:

- 4 persony,
- 11 map,
- 50 prob na mape,
- stale seedy,
- rollout na 10 losowych ruchow.

Wyniki:

- tabela srednich metryk,
- heatmapy,
- porownanie person miedzy soba.

### Eksperyment 3 - ewolucja polityki drzewa

Cel:

- uzyskac persony MCTS z wyewoluowanymi formula wyboru wezla.

Procedura:

- trening na mapach 1, 2, 3, 4, 7, 10,
- 3 niezalezne uruchomienia,
- wybor najlepszej formuly dla kazdej persony,
- test na wszystkich 11 mapach.

Wyniki:

- najlepsze formuly,
- przebieg fitnessu w generacjach,
- porownanie z MCTS-UCB1,
- testy istotnosci.

### Eksperyment 4 - PPO

Cel:

- sprawdzic, czy PPO moze pelnic role proceduralnej persony.

Procedura:

- osobny model PPO dla kazdej persony,
- trening na tych samych mapach co GP,
- test na wszystkich 11 mapach,
- 50 prob na mape.

Wyniki:

- krzywe uczenia,
- metryki koncowe,
- porownanie z MCTS-UCB1 i MCTS-GP,
- analiza czasu decyzji.

### Eksperyment 5 - analiza poziomow

Cel:

- sprawdzic, ktore cechy map wplywaja na zachowania person.

Cechy map:

- liczba scian,
- liczba pol pustych,
- liczba martwych koncow,
- liczba waskich przejsc,
- dlugosc najkrotszej sciezki wejscie-wyjscie,
- liczba skarbow,
- liczba mikstur,
- liczba potworow kazdego typu,
- liczba portali,
- liczba pulapek.

Analiza:

- korelacja Pearsona miedzy cechami poziomow a metrykami person,
- interpretacja map najlepszych i najgorszych dla kazdej persony.

## 12. Statystyka

W pracy nalezy zastosowac:

- srednia arytmetyczna,
- odchylenie standardowe,
- 95% przedzial ufnosci,
- dwustronny test t-Studenta z poprawka Welcha,
- poziom istotnosci `p < 0.05`,
- korelacje Pearsona dla cech poziomow.

Porownania:

- MCTS-GP vs MCTS-UCB1 dla tej samej persony,
- PPO vs MCTS-UCB1 dla tej samej persony,
- PPO vs MCTS-GP dla tej samej persony,
- persony miedzy soba w ramach tego samego agenta.

## 13. Oczekiwane tabele i wykresy

### Tabele

1. Tabela zasad i symboli gry.
2. Tabela metryk rozgrywki.
3. Tabela funkcji uzytecznosci person.
4. Tabela cech map.
5. Tabela liczebnosci obiektow w zrekonstruowanych mapach.
6. Tabela niepewnosci rekonstrukcji map i przyjetych decyzji.
7. Tabela wynikow MCTS-UCB1.
8. Tabela wynikow MCTS-GP.
9. Tabela wynikow PPO.
10. Tabela porownawcza wszystkich agentow.
11. Tabela liczby map z istotna przewaga jednego agenta nad drugim.
12. Tabela korelacji cech poziomow z wynikami person.

### Wykresy

1. Liczba obiektow interaktywnych na mapach.
2. Krzywe fitnessu GP.
3. Krzywe uczenia PPO.
4. Wykresy radarowe person.
5. Heatmapy odwiedzin dla wybranych map.
6. Wykresy slupkowe win rate.
7. Wykresy slupkowe monster ratio, treasure ratio, potion ratio i interactive ratio.
8. Porownanie czasu decyzji agentow.

## 14. Harmonogram szczegolowy

### Lipiec 2026 - fundament i zasady

Cele:

- utrzymac formalny zakres pracy w `docs/project/roadmap.md`,
- utrzymac baze zasad w `docs/rules/game-rules.md`,
- zweryfikowac rekonstrukcje map w `data/maps/md2/benchmark/`,
- zamrozic format map i symbole obiektow,
- zaprojektowac API srodowiska,
- dopisac testy obecnego uproszczonego srodowiska.

Zadania:

- utrzymac `docs/reference/articles/minidungeons_2.pdf` jako zrodlo mechaniki i `docs/reference/articles/1802.06881v1_MCTS.pdf` jako zrodlo eksperymentu,
- porownac `docs/benchmark/object_counts.md` z Fig. 3 z artykulu,
- przejrzec `docs/benchmark/uncertainties.md`,
- zdecydowac co robimy z `Map5.png` i `map05.txt`,
- dodac metadane par portali,
- zamrozic format map,
- ustalic format wynikow CSV/JSON,
- spisac jawne decyzje implementacyjne dla line-of-sight, `PE`, `IC`, kolejnosci obrazen, kolizji i tie-breakerow.

Efekt miesiaca:

- dokument projektowy zasad gry,
- pierwsza wersja map MD2 zaakceptowana albo oznaczona jako wymagajaca poprawek,
- stabilny plan eksperymentow,
- testy podstawowych zasad,
- jasna decyzja, ze w pracy uzywamy rekonstrukcji map na podstawie Fig. 2 i `data/maps/md2/source-images/`.

### Sierpien 2026 - technologie i pelne srodowisko

Cele:

- opanowac technologie,
- zaimplementowac wiekszosc zasad gry,
- przygotowac srodowisko pod MCTS i PPO.

Technologie:

- Python,
- pytest,
- numpy,
- pandas,
- scipy,
- matplotlib lub seaborn,
- Gymnasium,
- Stable-Baselines3,
- opcjonalnie tqdm i pydantic.

Zadania:

- dodac portale,
- dodac pulapki,
- dodac oszczep,
- dodac line-of-sight,
- dodac przeciwnikow,
- dodac A* dla Minitaura,
- dodac klonowanie stanu,
- dodac pelne metryki,
- dodac deterministic seeding.

Efekt miesiaca:

- wszystkie technologie wybrane i opanowane,
- srodowisko gry nadaje sie do uruchamiania agentow,
- podstawowe testy zasad przechodza.

### Wrzesien 2026 - dowod wykonalnosci eksperymentu

Cele:

- zaimplementowac MCTS-UCB1,
- zaimplementowac persony,
- uruchomic pierwsze pelne eksperymenty.

Zadania:

- napisac MCTS z selection, expansion, simulation, backpropagation,
- dodac rollout 10 krokow,
- dodac funkcje uzytecznosci person,
- uruchomic 4 persony na 11 mapach,
- zapisac wyniki do CSV,
- wygenerowac pierwsze tabele i heatmapy.

Efekt miesiaca:

- aplikacja udowadnia, ze eksperyment da sie wykonac,
- istnieje pierwszy kompletny baseline MCTS-UCB1,
- wiadomo, czy wydajnosc jest wystarczajaca.

### Pazdziernik 2026 - wiekszosc funkcji

Cele:

- dodac GP dla polityk MCTS,
- dodac PPO,
- przygotowac automatyzacje eksperymentow.

Zadania:

- zaimplementowac drzewa wyrazen GP,
- zaimplementowac mutacje, crossover, elityzm i wyspy,
- trenowac formuly dla kazdej persony,
- przygotowac Gymnasium wrapper,
- uruchomic pierwsze treningi PPO,
- dodac konfiguracje eksperymentow,
- dodac generowanie wykresow.

Efekt miesiaca:

- aplikacja implementuje wiekszosc zalozonych funkcji,
- dziala MCTS-UCB1,
- dziala MCTS-GP,
- PPO uruchamia sie i produkuje pierwsze wyniki.

### Listopad 2026 - finalne wyniki

Cele:

- wygenerowac finalne dane,
- przygotowac tabele i wykresy w formie pracy,
- wykonac testy statystyczne.

Zadania:

- uruchomic wszystkie eksperymenty na finalnych seedach,
- zapisac surowe wyniki,
- policzyc summary,
- policzyc 95% CI,
- wykonac testy Welcha,
- wykonac korelacje Pearsona,
- wygenerowac heatmapy,
- wygenerowac wykresy radarowe,
- opisac najwazniejsze obserwacje.

Efekt miesiaca:

- aplikacja produkuje wyniki w formie zblizonej do artykulu zrodlowego,
- wszystkie dane potrzebne do pracy sa gotowe,
- mozna zaczac pisanie finalnej tresci.

### Grudzien 2026 - pisanie pracy

Cele:

- napisac wiekszosc rozdzialow,
- polaczyc wyniki z narracja badawcza.

Rozdzialy:

- wstep,
- cel i zakres pracy,
- przeglad literatury,
- opis MiniDungeons 2,
- proceduralne persony,
- MCTS,
- programowanie genetyczne,
- PPO,
- implementacja systemu,
- metodologia eksperymentow.

Efekt miesiaca:

- pierwsza pelna wersja tekstu pracy,
- brak pustych rozdzialow,
- wszystkie wykresy wstawione w robocze miejsca.

### Styczen 2027 - finalizacja

Cele:

- poprawic tekst,
- dopracowac wnioski,
- przygotowac prace do oddania.

Zadania:

- napisac dyskusje wynikow,
- napisac ograniczenia pracy,
- napisac wnioski,
- sprawdzic spojnosci terminologii,
- sprawdzic podpisy tabel i rysunkow,
- sprawdzic bibliografie,
- sprawdzic, czy wszystkie wyniki da sie odtworzyc z repozytorium,
- przygotowac finalna wersje PDF.

Efekt:

- gotowa praca inzynierska do polowy stycznia.

## 15. Struktura pracy inzynierskiej

Proponowana struktura:

1. **Wstep**
   - motywacja,
   - problem automatycznego testowania poziomow,
   - cel pracy,
   - pytania badawcze.

2. **Przeglad literatury**
   - proceduralne persony,
   - player modeling,
   - MCTS,
   - MCTS w grach jednoosobowych,
   - programowanie genetyczne,
   - uczenie ze wzmocnieniem i PPO,
   - MiniDungeons 2 jako srodowisko eksperymentalne.

3. **Opis gry MiniDungeons 2**
   - mapa,
   - obiekty,
   - przeciwnicy,
   - tury,
   - oszczep,
   - warunki zwyciestwa i porazki,
   - metryki.

4. **Metoda badawcza**
   - persony,
   - funkcje uzytecznosci,
   - MCTS-UCB1,
   - MCTS z GP,
   - PPO,
   - protokol eksperymentalny,
   - testy statystyczne.

5. **Implementacja**
   - architektura aplikacji,
   - reprezentacja stanu,
   - system zasad,
   - agenci,
   - zapis wynikow,
   - generowanie wykresow.

6. **Eksperymenty i wyniki**
   - opis map,
   - wyniki MCTS-UCB1,
   - wyniki MCTS-GP,
   - wyniki PPO,
   - porownania,
   - heatmapy,
   - korelacje cech poziomow.

7. **Dyskusja**
   - interpretacja roznic miedzy personami,
   - czy PPO odtwarza persony,
   - ograniczenia reprodukcji,
   - ograniczenia map i czasu obliczen.

8. **Wnioski**
   - odpowiedzi na pytania badawcze,
   - co udalo sie odtworzyc,
   - co wnosi rozszerzenie PPO,
   - kierunki dalszego rozwoju.

## 16. Ryzyka i plan awaryjny

### Ryzyko 1 - niepewnosci rekonstrukcji map

Plan:

- uzyc `data/maps/md2/source-images/` i Fig. 2 jako podstawy rekonstrukcji,
- trzymac mapy w `data/maps/md2/benchmark/`,
- utrzymywac `uncertainties.md` jako jawny rejestr niepewnosci,
- porownac liczebnosci obiektow z Fig. 3,
- jawnie opisac zaakceptowany wyjatek `map5_grid_11x14.png`/`map05.txt` 11x14 wzgledem ogolnej reguly 10x20,
- dodac osobne metadane par portali,
- porownywac algorytmy na tych samych mapach,
- nie obiecywac identycznych wynikow jak w artykule,
- opisac w pracy, ze wyniki sa reprodukcja metodologiczna, a nie bitowa reprodukcja oryginalnego silnika.

### Ryzyko 1a - rozjazd miedzy opisem gry i opisem eksperymentu

Plan:

- mechanike gry brac z `minidungeons_2.pdf`,
- metryki, persony, podzial map i protokol badan brac z `1802.06881v1_MCTS.pdf`,
- gdy zrodla sa niespojne, jawnie wybrac wariant z artykulu MCTS, jesli dotyczy wynikow eksperymentu,
- przyklad: startowe HP bohatera ustawiamy na 10, mimo ze opis MD2 mowi o zakresie 1-10 HP.

### Ryzyko 2 - zbyt wolny MCTS-GP

Plan:

- ograniczyc budzet czasu,
- ograniczyc liczbe iteracji,
- cache'owac cechy map,
- uruchamiac eksperymenty partiami,
- w pracy opisac kompromis miedzy czasem i jakoscia.

### Ryzyko 3 - PPO uczy sie niestabilnie

Plan:

- zaczac od prostszej obserwacji i nagrod,
- ograniczyc porownanie do zachowania koncowego,
- pokazac krzywe uczenia,
- potraktowac PPO jako rozszerzenie porownawcze, nie jako warunek reprodukcji artykulu.

### Ryzyko 4 - pelne zasady MD2 sa zbyt czasochlonne

Plan:

- najpierw zaimplementowac minimalny zestaw wymagany do metryk,
- kazda uproszczona zasade opisac w pracy,
- nie ukrywac roznic wzgledem artykulu,
- zachowac najwazniejsze mechaniki: persony, metryki, MCTS, GP, PPO.

## 17. Definicja ukonczenia projektu

Projekt mozna uznac za gotowy, gdy:

- zrekonstruowane mapy sa zamrozone i opisane,
- niepewnosci map sa jawnie udokumentowane,
- pary portali sa zapisane w metadanych,
- srodowisko gry dziala deterministycznie,
- wszystkie persony maja funkcje uzytecznosci,
- MCTS-UCB1 dziala dla 4 person,
- MCTS-GP dziala dla 4 person,
- PPO dziala przynajmniej jako porownanie dla 4 person,
- eksperymenty zapisuja surowe wyniki,
- analiza generuje tabele i wykresy,
- wyniki sa interpretowalne,
- repozytorium pozwala odtworzyc eksperyment,
- praca opisuje zarowno sukcesy, jak i ograniczenia.

## 18. Najblizszy maly krok po tym dokumencie

Etap 0 jest zakonczony. Zamrozony benchmark znajduje sie w:

```text
data/maps/md2/benchmark/
```

Jego spojnosc sprawdzaja:

```text
python tools/validate_stage0.py
python -m unittest discover -s tests -v
```

Najblizszy etap to **Etap 2 - pelniejsze MiniDungeons 2**, a nie jeszcze MCTS:

- zaprojektowac pelny, klonowalny `GameState`,
- rozdzielic warstwy terenu, obiektow i postaci,
- zaimplementowac deterministyczne `legal_actions()` i pelna ture `step()`,
- dodac portale, pulapki, line of sight, oszczep i przeciwnikow,
- dodac pelne metryki oraz testy kazdej reguly,
- uruchomic Random Agenta na wszystkich 11 zamrozonych mapach.

MCTS-UCB1 zaczyna sie dopiero wtedy, gdy klon stanu i ta sama akcja zawsze daja
identyczny kolejny stan bez modyfikowania stanu zrodlowego.
