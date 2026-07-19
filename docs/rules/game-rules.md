# MiniDungeons 2 - baza wiedzy o zasadach gry

Zrodla lokalne:

- `docs/reference/articles/1802.06881v1_MCTS.pdf` - zrodlo eksperymentu: persony, metryki, MCTS, ewoluowane heurystyki, zestaw 11 map i protokol badan.
- `docs/reference/articles/minidungeons_2.pdf` - zrodlo zasad gry: opis silnika MiniDungeons 2, obiektow, przeciwnikow, oszczepu, portali i kolejnosci tur.

Status implementacji (2026-07-19): parametry silnika sa w
`data/rules/md2_rules.json`, wagi person w `data/rules/personas.json`,
a rozstrzygniecia niejednoznacznosci w `docs/rules/ambiguity-resolutions.md`.
Wykonuje je `src/minidungeons/domain/engine.py`, a
`docs/rules/implementation-decisions.md` oddziela reguly zrodlowe od decyzji
rekonstrukcyjnych. Sformułowania „decyzja do przyjęcia” w dalszej części tego
dokumentu należy czytać jako historię analizy; finalny wybór zapisuje JSON.

Cel dokumentu: zebrac w jednym miejscu wszystkie zasady gry MiniDungeons 2 opisane w artykule, oddzielic je od rzeczy niewyjasnionych oraz wskazac, ktore decyzje implementacyjne mozemy przyjac samodzielnie bez niszczenia sensu eksperymentu.

Ten dokument dotyczy logiki gry i pomiarow. Warstwa wizualna nie musi byc odtworzona 1:1, jesli zachowana jest logika kafli, obiektow, przeciwnikow, metryk i eksperymentow.

## 1. Status informacji

W dokumencie uzywane sa trzy statusy:

- **Opisane wprost** - artykul jasno podaje zasade.
- **Widoczne w artykule** - informacja jest dostepna z rysunkow, np. mapy w Fig. 2, ale nie jako plik danych.
- **Nieokreslone** - artykul wspomina element, ale nie daje pelnej reguly implementacyjnej.

Najwazniejszy wniosek:

- Da sie odtworzyc system badawczy i sens porownania metod.
- Nie da sie zagwarantowac identycznych liczb jak u autorow bez oryginalnego kodu i plikow map.
- W miejscach nieokreslonych nalezy przyjac deterministyczne reguly implementacyjne i opisac je w pracy.

## 1.1. Co dopowiada artykul MiniDungeons 2

`minidungeons_2.pdf` jest bardzo wazny, bo nie opisuje wynikow MCTS, tylko bazowe zasady gry. Po jego dodaniu czesc rzeczy przestaje byc nieznana:

- plansza ma 10x20 kafli,
- kafle sa scianami albo kaflami przechodnimi,
- kafel przechodni moze zawierac obiekt i/lub postac,
- poziom konczy sie po dotarciu bohatera do wyjscia albo smierci bohatera,
- bohater rusza sie pierwszy, potem obiekty i postacie odpowiadaja deterministycznie w sekwencji,
- bohater ma jeden oszczep,
- bohater zadaje 1 obrazenie przez kolizje albo rzut oszczepem,
- oszczep mozna rzucic w dowolna inna postac w nieprzerwanym line of sight,
- oszczep zostaje na kaflu, na ktory zostal rzucony, i bohater musi tam dojsc, zeby go odzyskac,
- portale dzialaja dla "character", czyli dla postaci, nie tylko dla bohatera,
- portal natychmiast przenosi na sparowany portal w tej samej turze,
- goblin idzie 1 krok w strone bohatera po najkrotszej sciezce, jesli ma line of sight,
- wizard zadaje 1 obrazenie z dystansu w line of sight do 5 kafli, w innym przypadku idzie 1 krok w strone bohatera,
- blob wybiera najblizszego widocznego bohatera albo potion, a przy remisie preferuje potion,
- blob zadaje obrazenia postaciom nie-bedacym blobami, laczy sie z innymi blobami i traci poziom mocy po otrzymaniu obrazen,
- ogre wybiera najblizszego widocznego bohatera albo skarb, a przy remisie preferuje skarb,
- Minitaur zawsze idzie po najkrotszej sciezce A* do bohatera, ignorujac inne postacie i obiekty,
- Minitaur nie ma HP, nie ginie i po otrzymaniu obrazen jest ogluszony na 3 rundy.

Wazna niespojnosc miedzy zrodlami:

- `minidungeons_2.pdf` pisze, ze bohater zaczyna poziom z 1-10 HP.
- `1802.06881v1_MCTS.pdf` w eksperymencie MCTS przyjmuje start z 10 HP.
- Dla tej pracy wazniejszy jest eksperyment MCTS, wiec implementacja badawcza powinna startowac z 10 HP. Niespojnosc trzeba opisac w pracy jako decyzje reprodukcyjna.

## 2. Czego nie wolno zmienic, bo tworzy clue eksperymentu

Te elementy sa krytyczne dla sensu pracy:

- cztery persony: Runner, Monster Killer, Treasure Collector, Completionist,
- funkcje uzytecznosci person z artykulu,
- metryki rozgrywki z Table I,
- podzial map: trening GP na mapach 1, 2, 3, 4, 7, 10; test na wszystkich 11 mapach,
- porownanie MCTS-UCB1 z MCTS z ewoluowana polityka drzewa,
- dodanie RL/PPO jako metody porownawczej z tego samego tematu pracy,
- ta sama logika celu gry: dojscie do wyjscia,
- smierc po spadku HP do zera,
- turowosc i deterministycznosc srodowiska,
- rozne typy obiektow i przeciwnikow,
- wyniki w formie metryk jak w artykule.

## 3. Co mozna zdefiniowac samodzielnie

Te elementy moga zostac przyjete jako nasze reguly implementacyjne, jesli sa deterministyczne i opisane:

- symbole w plikach map,
- format pliku mapy,
- format eksportu wynikow,
- sposob rysowania map i heatmap,
- tie-breakery ruchu,
- szczegoly rzadkich kolizji nieopisanych w artykule,
- sposob wyboru jednej z kilku rownych sciezek A*,
- kolejnosc rozpatrywania akcji o tej samej ocenie,
- reprezentacja obserwacji dla PPO,
- szczegoly UI albo brak UI.

## 4. Ogolny model gry

Status: **opisane wprost**.

MiniDungeons 2 jest:

- deterministyczna gra,
- gra turowa,
- gra roguelike,
- gra jednoosobowa,
- gra na siatce kafli,
- gra z bohaterem przechodzacym przez poziom,
- gra z celem dotarcia do wyjscia.

Konsekwencje implementacyjne:

- ten sam stan i ta sama akcja musza dawac ten sam kolejny stan,
- element losowy moze wystepowac w agentach, np. rollout MCTS, ale nie powinien wynikac z zasad gry,
- srodowisko musi pozwalac na klonowanie stanu, bo MCTS wykonuje symulacje przyszlosci,
- srodowisko musi jasno rozpoznawac stany terminalne: zwyciestwo, smierc, timeout eksperymentu.

## 5. Plansza i kafle

Status: **opisane wprost / widoczne w artykule**.

Z artykulu:

- plansza ma rozmiar 10x20,
- kazdy kafel jest albo sciana, albo przechodnim polem,
- na przechodnim polu moze znajdowac sie obiekt,
- na przechodnim polu moze znajdowac sie postac,
- na przechodnim polu moze nie byc niczego,
- obiekty gry to m.in. skarby, mikstury, portale, pulapki i wyjscie.

Widoczne w artykule:

- Fig. 2 pokazuje wszystkie 11 map,
- mapy sa staly zestawem testowym,
- mapy nie sa generowane proceduralnie podczas eksperymentu,
- Fig. 3 pokazuje liczbe typow obiektow interaktywnych na mapach.

Nieokreslone:

- oryginalny format plikow map,
- dokladne symbole kafli,
- dokladne dane map jako tekst,
- czy na jednym kaflu moze byc wiecej niz jedna postac poza specjalnymi kolizjami.

Decyzja implementacyjna do przyjecia:

- uzywamy tekstowego formatu map,
- przepisujemy logike 11 map z Fig. 2,
- kazdy kafel ma warstwe terenu oraz opcjonalnie warstwe obiektu i warstwe postaci,
- postacie domyslnie blokuja pole, chyba ze reguly specjalne mowia inaczej.

## 6. Warunki zwyciestwa i porazki

Status: **opisane wprost**.

Zwyciestwo:

- gracz wygrywa po dotarciu bohatera do wyjscia.

Porazka:

- bohater przegrywa, gdy skoncza mu sie HP,
- bohater zaczyna z 10 HP,
- smierc nastepuje po spadku HP do 0 lub mniej.

Nieokreslone:

- czy zwyciestwo ma pierwszenstwo przed smiercia, jesli oba zdarzenia wystapia w tej samej turze,
- czy wejscie na wyjscie natychmiast konczy ture przed ruchem NPC,
- czy timeout eksperymentu jest stanem gry, czy tylko przerwaniem agenta.

Decyzja implementacyjna do przyjecia:

- wejscie bohatera na wyjscie natychmiast konczy gre zwyciestwem,
- jesli HP bohatera spadnie do 0 przed wejsciem na wyjscie, gra konczy sie smiercia,
- timeout nie jest regula gry, tylko warunkiem eksperymentu.

## 7. HP i obrazenia

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- wszystkie postacie maja HP, z wyjatkiem Minitaura, ktory nie ma HP,
- postacie moga zadawac obrazenia,
- bohater startuje z 10 HP w eksperymencie MCTS z `1802.06881v1_MCTS.pdf`,
- bazowy opis MD2 z `minidungeons_2.pdf` dopuszcza start bohatera z 1-10 HP,
- potion leczy bohatera o 1 HP do maksimum 10,
- pulapka zadaje 1 obrazenie kazdej postaci, ktora przez nia przechodzi,
- bohater zadaje 1 obrazenie innym postaciom przez kolizje,
- goblin ma 1 HP i zadaje 1 obrazenie przy kolizji,
- wizard ma 1 HP i zadaje 1 obrazenie zakleciem,
- wizard nie zadaje obrazen przez kolizje,
- blob poziomu 1 ma 1 HP i zadaje 1 obrazenie,
- blob poziomu 2 ma 2 HP i zadaje 2 obrazenia,
- blob poziomu 3 ma 3 HP i zadaje 3 obrazenia,
- ogre ma 2 HP i zadaje 2 obrazenia,
- Minitaur zadaje 1 obrazenie przy kolizji,
- oszczep zadaje 1 obrazenie innej postaci.

Nieokreslone:

- czy postac moze zginac od pulapki podczas swojej tury i czy wtedy znika natychmiast,
- czy potwor po otrzymaniu smiertelnych obrazen zadaje jeszcze obrazenia w tej samej kolizji.

Decyzja implementacyjna do przyjecia:

- kolizja bohatera z potworem oznacza, ze bohater zadaje 1 obrazenie, a potwor zadaje swoje obrazenia, jesli jego typ ma obrazenia kolizyjne,
- dla eksperymentu startowe HP bohatera ustawiamy na 10,
- smierc postaci po obrazeniach rozpatrujemy natychmiast,
- dla kazdej kolizji zapisujemy event do metryk.

## 8. Tura i kolejnosc ruchu

Status: **opisane wprost**.

Z artykulu:

- gracz wykonuje pierwszy ruch w kazdej turze,
- po graczu obiekty i postacie odpowiadaja deterministycznie,
- w praktyce dla implementacji najwazniejsze sa reakcje NPC,
- NPC ruszaja sie wedlug swojej pierwotnej pozycji na mapie,
- kolejnosc NPC idzie od lewego gornego rogu,
- kolejnosc jest wierszami od lewej do prawej,
- kolejnosc poczatkowa zostaje zachowana nawet wtedy, gdy NPC pozniej zmieniaja pozycje.

Nieokreslone:

- czy NPC, ktory zginal przed swoja kolejka, jest pomijany natychmiast,
- czy nowy blob powstaly po zlaczeniu zachowuje kolejke jednego z blobow,
- jak traktowac NPC, ktory zostal ogluszony,
- czy NPC wykonuje akcje po tym, jak bohater juz wygral w tej turze.

Decyzja implementacyjna do przyjecia:

- jesli gra jest terminalna po ruchu bohatera, NPC nie ruszaja sie,
- martwe NPC sa usuwane przed ich kolejka,
- scalony blob przejmuje nizszy indeks kolejki z laczacych sie blobow,
- ogluszony Minitaur pozostaje w kolejce, ale jego akcja to brak ruchu.

## 9. Ruch

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- postac moze poruszyc sie o 1 kafel,
- kierunki ruchu to North, South, East, West,
- ruch jest dozwolony, jesli kafel w tym kierunku nie jest sciana,
- kafel przechodni moze zawierac obiekt i/lub postac,
- postac wchodzaca w portal jest natychmiast teleportowana do sparowanego portalu.

Nieokreslone:

- czy ruch poza plansze jest akcja nielegalna czy no-op,
- czy postac moze wejsc na kafel zajety przez inna postac,
- czy postac moze wejsc na portal, pulapke, potion, skarb, wyjscie,
- czy NPC moga wejsc na wyjscie,
- czy obiekty podlogowe blokuja ruch.

Decyzja implementacyjna do przyjecia:

- legalne akcje bohatera nie zawieraja ruchu w sciane ani poza plansze,
- obiekty podlogowe nie blokuja ruchu,
- postacie blokuja ruch, chyba ze dana kolizja jest celowa albo specjalna,
- portal dziala dla wszystkich postaci, ale `TU` liczymy tylko dla uzyc bohatera,
- wyjscie jest interaktywne tylko dla bohatera.

## 10. Line of sight

Status: **wspomniane, ale nie zdefiniowane szczegolowo**.

Z artykulu:

- oszczep moze trafic potwora w nieprzerwanym line of sight,
- goblin podaza za bohaterem, jesli ma nieprzerwany line of sight,
- wizard atakuje lub podchodzi, jesli ma line of sight,
- blob reaguje na potion lub bohatera, jesli ma line of sight,
- ogre reaguje na skarb lub bohatera, jesli ma line of sight.

Nieokreslone:

- czy line of sight dziala tylko w czterech kierunkach,
- czy line of sight dziala po przekatnych,
- czy line of sight moze isc po dowolnej prostej,
- czy sciany sa jedynymi blokerami widzenia,
- czy NPC blokuja widzenie,
- czy obiekty blokuja widzenie,
- czy pulapki i portale blokuja widzenie,
- czy dystans wizardow liczony jest Manhattanem, Euklidesowo, czy po linii widzenia.

Decyzja implementacyjna do przyjecia:

- line of sight dziala w czterech kierunkach osiowych,
- sciany blokuja line of sight,
- postacie i obiekty nie blokuja line of sight,
- dystans w line of sight liczony jest liczba kafli w osi.

Uwaga:

- To jest jedna z wazniejszych decyzji implementacyjnych, bo wplywa na ruch przeciwnikow i uzycie oszczepu.

## 11. Bohater

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- bohater jest postacia gracza,
- zaczyna z 10 HP,
- celem bohatera jest dotarcie do wyjscia,
- bohater wykonuje pierwszy ruch w turze,
- bohater moze poruszac sie w czterech kierunkach,
- bohater dostaje jeden wielorazowy oszczep na poczatku poziomu,
- bohater zadaje 1 obrazenie innym postaciom przy kolizji,
- bohater zadaje 1 obrazenie innym postaciom rzutem oszczepem.

Nieokreslone:

- czy bohater moze czekac,
- czy bohater moze rzucic oszczepem jako akcja zamiast ruchu,
- czy rzut oszczepem konczy ture bohatera,
- czy bohater moze przejsc przez innych przeciwnikow bez walki.

Decyzja implementacyjna do przyjecia:

- akcje bohatera to ruchy oraz rzut oszczepem, gdy oszczep jest dostepny i cel jest w line of sight,
- rzut oszczepem zuzywa akcje bohatera w turze,
- bohater nie ma osobnego przycisku melee; atak melee wynika z kolizji.

## 12. Oszczep

Status: **opisane wprost / czesciowo nieokreslone w szczegolach**.

Z artykulu:

- bohater dostaje jeden wielorazowy oszczep na poczatku kazdego poziomu,
- bohater moze rzucic oszczepem,
- oszczep zadaje 1 obrazenie dowolnej innej postaci w nieprzerwanym line of sight,
- po uzyciu oszczepu bohater musi przejsc na kafel, na ktory oszczep zostal rzucony, aby go podniesc i uzyc ponownie,
- oszczep pozostaje na kaflu, na ktory zostal rzucony,
- gra moze byc nieskonczona, bo gracz moze poruszac sie w te i z powrotem i ciagle radzic sobie z Minitaurem oszczepem.

Nieokreslone:

- czy po zabiciu potwora oszczep zostaje na tym samym polu,
- czy oszczep moze przeleciec przez potwora,
- czy oszczep moze trafic tylko pierwszego potwora w linii,
- czy oszczep moze byc rzucony na puste pole,
- czy oszczep moze lezec na polu z obiektem,
- czy NPC moga wejsc na oszczep,
- czy bohater automatycznie podnosi oszczep po wejsciu na jego kafel,
- czy rzut oszczepem jest liczony jako krok.

Decyzja implementacyjna do przyjecia:

- oszczep mozna rzucic tylko w inna postac widoczna w osiowym line of sight,
- oszczep trafia wybrana postac i laduje na jej aktualnym kaflu,
- jesli potwor ginie, oszczep zostaje na tym kaflu,
- bohater automatycznie podnosi oszczep po wejsciu na kafel oszczepu,
- rzut oszczepem liczymy jako akcje i metryke `JT`, ale nie jako krok ruchu `ST`.

## 13. Obiekty podlogowe

### 13.1. Wyjscie

Status: **opisane wprost**.

Z artykulu:

- wyjscie jest celem poziomu,
- gracz wygrywa po dotarciu do wyjscia.

Nieokreslone:

- czy NPC moga wejsc na wyjscie,
- czy wyjscie blokuje ruch NPC,
- czy wyjscie ma dodatkowy efekt dla obiektow.

Decyzja implementacyjna:

- wyjscie dziala tylko dla bohatera,
- dla NPC jest zwyklym przechodnim polem albo polem neutralnym, zaleznie od wygody implementacji; nalezy wybrac jedna wersje i opisac.

### 13.2. Potion

Status: **opisane wprost**.

Z artykulu:

- potion zwieksza HP bohatera o 1,
- potion nie pozwala przekroczyc 10 HP,
- potion jest konsumowany przez bohatera,
- potion jest konsumowany przez bloba,
- po konsumpcji potion nie moze zostac uzyty ponownie.

Nieokreslone:

- czy inne NPC niz blob moga wejsc na potion,
- czy potion blokuje ruch,
- czy blob po zjedzeniu potiona leczy sie albo tylko go usuwa.

Decyzja implementacyjna:

- potion nie blokuje ruchu,
- bohater leczy sie o 1,
- blob usuwa potion bez leczenia, jesli artykul nie mowi inaczej,
- inne NPC ignoruja potion.

### 13.3. Treasure

Status: **opisane wprost**.

Z artykulu:

- treasure zwieksza treasure score bohatera,
- treasure jest konsumowany przez bohatera,
- treasure jest konsumowany przez ogre,
- po konsumpcji treasure nie moze zostac uzyty ponownie,
- ogre po zjedzeniu skarbu zmienia sprite na ladniejszy.

Nieokreslone:

- czy zmiana sprite ma efekt mechaniczny,
- czy inne NPC niz ogre moga wejsc na treasure,
- czy treasure blokuje ruch.

Decyzja implementacyjna:

- treasure nie blokuje ruchu,
- zmiana sprite ogre nie ma efektu mechanicznego,
- inne NPC ignoruja treasure.

### 13.4. Portal

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- portale wystepuja parami,
- gdy postac wchodzi w portal, zostaje natychmiast przeniesiona do drugiego portalu,
- teleportacja dzieje sie w tej samej turze,
- siedem map zawiera zestaw portali dajacych skroty przez poziom.

Nieokreslone:

- czy para portali jest jednoznaczna wizualnie w Fig. 2,
- czy moze byc wiecej niz jedna para portali na mapie,
- czy teleportacja moze przeniesc bohatera na zajety kafel,
- czy po teleportacji rozpatrywane sa obiekty na kaflu docelowym,
- czy wejscie na portal liczy sie jako `TU`,
- czy teleportacja liczy sie jako dodatkowy krok.

Decyzja implementacyjna:

- portale dzialaja dla bohatera i NPC,
- wejscie bohatera na portal zwieksza `TU`,
- teleportacja nie zwieksza `ST` poza ruchem wejscia na portal,
- pole docelowe portalu nie moze byc sciana,
- jesli pole docelowe jest zajete, nalezy zdefiniowac blokade albo kolizje.

### 13.5. Trap

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- trap zadaje 1 obrazenie kazdej postaci wchodzacej na jej kafel,
- obrazenia sa zadawane za kazdym razem,
- szesc map zawiera jedna lub wiecej pulapek.

Nieokreslone:

- czy trap dziala takze przy opuszczeniu kafla, czy tylko przy wejsciu,
- czy trap dziala na latajacy/rzucany oszczep,
- czy trap znika po aktywacji,
- czy trap moze zabic NPC,
- czy trap dziala na Minitaura, skoro nie ma HP.

Decyzja implementacyjna:

- trap dziala przy wejsciu postaci na kafel,
- trap nie znika,
- trap zadaje obrazenia bohaterowi i NPC z HP,
- Minitaur moze zostac ogluszony albo zignorowac trap; trzeba wybrac jedna wersje.

## 14. Przeciwnicy

### 14.1. Goblin / Melee Goblin

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- goblin porusza sie o 1 kafel w kazdej turze,
- porusza sie w strone bohatera po najkrotszej sciezce,
- rusza sie tylko wtedy, gdy ma nieprzerwany line of sight do bohatera,
- ma 1 HP,
- zadaje 1 obrazenie przy kolizji,
- unika kolizji z innymi goblinami i goblin wizardami.

Nieokreslone:

- jak goblin wybiera kierunek, gdy ma kilka ruchow przyblizajacych do bohatera,
- czy goblin moze kolidowac z blobem, ogre, Minitaurem,
- co znaczy dokladnie "unika kolizji": wybiera inny ruch, stoi, czy przechodzi przez cel.

Decyzja implementacyjna:

- goblin rusza sie po najkrotszej sciezce do bohatera, ale tylko gdy ma line of sight,
- jesli ruch docelowy jest zablokowany przez goblina lub wizarda, goblin nie rusza sie,
- kolizja z bohaterem zadaje bohaterowi 1 obrazenie.

### 14.2. Goblin Wizard / Ranged Goblin

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- wizard rzuca zaklecie w bohatera, jesli ma nieprzerwany line of sight w zasiegu 5 kafli,
- zaklecie zadaje 1 obrazenie,
- w przeciwnym razie rusza sie o 1 kafel w strone bohatera,
- wizard ma 1 HP,
- wizard nie zadaje obrazen przez kolizje.

Nieokreslone:

- czy zasieg 5 jest liczony wlacznie czy wylacznie,
- jak liczony jest dystans,
- czy zaklecie przechodzi przez inne NPC,
- czy wizard moze poruszyc sie po rzuceniu zaklecia,
- czy ruch "otherwise" wymaga line of sight, czy wizard idzie do bohatera takze bez line of sight,
- co dzieje sie przy kolizji bohatera z wizardem.

Decyzja implementacyjna:

- zasieg 5 jest liczony wlacznie,
- dystans liczony jest po osi line of sight,
- wizard albo rzuca zaklecie, albo sie rusza, nigdy oba w tej samej turze,
- kolizja z wizardem nie zadaje obrazen bohaterowi, ale moze pozwalac na usuniecie wizarda zgodnie z przyjeta regula walki.

### 14.3. Blob

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- blob nie rusza sie, jesli nie widzi potiona ani bohatera,
- blob reaguje na potion albo bohatera w line of sight,
- blob rusza sie o 1 kafel w strone najblizszego widocznego celu,
- w remisie preferuje potion przed bohaterem,
- blob po kolizji z potionem konsumuje potion,
- blob po kolizji z innym blobem scala sie w silniejszego bloba,
- blob poziomu 1 ma 1 HP i zadaje 1 obrazenie,
- blob poziomu 2 ma 2 HP i zadaje 2 obrazenia,
- blob poziomu 3 ma 3 HP i zadaje 3 obrazenia,
- blob zadaje obrazenia kolidujacej postaci, ktora nie jest blobem,
- silniejszy blob po otrzymaniu obrazen traci jeden poziom mocy.

Nieokreslone:

- co jesli blob widzi kilka potionow w tej samej odleglosci,
- co jesli blob widzi kilka sciezek do tego samego celu,
- czy blob moze scalac sie powyzej poziomu 3,
- ktory blob znika po scaleniu,
- jaki indeks kolejki ma scalony blob,
- czy blob leczy sie po zjedzeniu potiona,
- czy blob moze wejsc na treasure, portal, trap, exit.

Decyzja implementacyjna:

- blob ma maksymalnie poziom 3,
- dwa bloby scalaja sie do poziomu `min(3, level_a + level_b)`,
- scalony blob zostaje na kaflu kolizji,
- otrzymanie obrazen przez blob poziomu 2 lub 3 obniza poziom o 1,
- otrzymanie obrazen przez blob poziomu 1 zabija bloba,
- nie leczy sie od potiona, tylko go usuwa,
- przy rownych celach wybiera cel w stalej kolejnosc N, S, E, W albo wedlug indeksu kafla; nalezy wybrac jedna wersje.

### 14.4. Ogre

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- ogre nie rusza sie, jesli nie widzi skarbu ani bohatera,
- ogre reaguje na skarb albo bohatera w line of sight,
- ogre rusza sie o 1 kafel w strone najblizszego celu,
- w remisie preferuje skarb przed bohaterem,
- ogre po kolizji ze skarbem konsumuje skarb,
- ogre po zjedzeniu skarbu zmienia sprite,
- ogre ma 2 HP,
- ogre zadaje 2 obrazenia temu, z czym koliduje,
- ogre zadaje obrazenia takze innym ogres.

Nieokreslone:

- czy zmiana sprite po skarbie ma wplyw na mechanike,
- co jesli ogre widzi kilka skarbow w tej samej odleglosci,
- czy ogre moze kolidowac ze wszystkimi typami potworow,
- czy ogre atakuje bloby, gobliny i wizardy,
- czy ogre moze zabic innego ogre,
- czy ogre dostaje obrazenia zwrotne od innych postaci.

Decyzja implementacyjna:

- zmiana sprite jest czysto wizualna,
- ogre zadaje 2 obrazenia w kazdej dozwolonej kolizji,
- przy kolizji ogre-ogre oba otrzymuja 2 obrazenia,
- przy rownych celach stosujemy deterministyczny tie-breaker.

### 14.5. Minitaur

Status: **opisane wprost / czesciowo nieokreslone**.

Z artykulu:

- Minitaur zawsze porusza sie o 1 krok wzdluz najkrotszej sciezki do bohatera,
- najkrotsza sciezka jest wyznaczana przez A*,
- podczas wyznaczania sciezki ignoruje inne postacie i obiekty,
- Minitaur ignoruje line of sight,
- kolizja z Minitaurem zadaje 1 obrazenie,
- Minitaur nie ma HP,
- Minitaur nie moze zginac,
- jesli Minitaur otrzyma obrazenia, zostaje ogluszony na 3 rundy,
- ogluszonego Minitaura mozna minac/przejsc przez niego.

Nieokreslone:

- czy Minitaur moze wejsc na pulapke,
- czy pulapka oglusza Minitaura,
- czy oszczep zawsze oglusza Minitaura,
- jak A* rozstrzyga wiele rownych sciezek,
- jak rozpatrzyc faktyczna kolizje, jesli sciezka A* prowadzi przez NPC albo obiekt,
- kiedy dokladnie zmniejsza sie licznik ogluszenia,
- czy "3 rounds" oznacza 3 pelne tury gracza czy 3 kolejki Minitaura.

Decyzja implementacyjna:

- oszczep oglusza Minitaura na 3 jego akcje,
- podczas ogluszenia Minitaur nie rusza sie i mozna przejsc przez jego kafel,
- A* stosuje staly porzadek sasiadow,
- Minitaur traktuje sciany jako blokady, a inne postacie i obiekty ignoruje przy planowaniu sciezki,
- jesli ruch Minitaura wchodzi w inna postac, rozpatrujemy kolizje wedlug macierzy kolizji.

## 15. Kolizje

Status: **czesciowo opisane, czesciowo nieokreslone**.

Opisane wprost:

- bohater lub blob konsumuje potion,
- bohater lub ogre konsumuje treasure,
- postac po wejsciu w portal teleportuje sie,
- postac wchodzaca na trap dostaje 1 obrazenie,
- bohater zadaje 1 obrazenie innym postaciom przy kolizji,
- goblin zadaje 1 obrazenie przy kolizji,
- wizard nie zadaje obrazen przy kolizji,
- blob zadaje obrazenia rowne poziomowi przy kolizji z postacia nie-bedaca blobem,
- blob + blob powoduje scalenie,
- ogre zadaje 2 obrazenia temu, z czym koliduje, w tym innym ogres,
- Minitaur zadaje 1 obrazenie przy kolizji,
- ogluszony Minitaur moze byc mijany.

Nieokreslone:

- pelna macierz kolizji miedzy kazda para typow,
- czy kolizje sa symetryczne,
- czy obrazenia sa zadawane przed ruchem, po ruchu, czy w trakcie,
- czy postac moze wejsc na pole zajete przez postac, ktora zginie od tej kolizji,
- czy NPC moga zajmowac ten sam kafel po kolizji,
- czy obiekty podlogowe zostaja pod postacia po kolizji.

Minimalna macierz do zdefiniowania w implementacji:

| Kolizja | Status z artykulu | Decyzja potrzebna |
| --- | --- | --- |
| Hero + potion | opisane | leczy +1 i usuwa potion |
| Blob + potion | opisane | usuwa potion |
| Hero + treasure | opisane | zwieksza TO i usuwa treasure |
| Ogre + treasure | opisane | usuwa treasure |
| Dowolna postac + portal | opisane | teleportuje na sparowany portal |
| Dowolna postac + trap | opisane | 1 obrazenie przy wejsciu |
| Blob + blob | opisane | scalenie |
| Ogre + ogre | opisane | obrazenia 2 |
| Hero + goblin | opisane | hero zadaje 1, goblin zadaje 1 |
| Hero + wizard | opisane czesciowo | hero zadaje 1, wizard nie zadaje kolizyjnie |
| Hero + blob | opisane czesciowo | hero zadaje 1, blob zadaje obrazenia rowne poziomowi |
| Hero + ogre | opisane czesciowo | hero zadaje 1, ogre zadaje 2 |
| Hero + Minitaur | opisane | hero dostaje 1, Minitaur po obrazeniu jest ogluszony |
| Goblin + goblin/wizard | opisane czesciowo | goblin unika |
| NPC + portal | opisane | teleportuje jak kazda postac |
| NPC + exit | nieokreslone | zdefiniowac |
| NPC + javelin | nieokreslone | zdefiniowac |

## 16. Mapy

Status: **widoczne w artykule / czesciowo opisane**.

Z artykulu:

- istnieje 11 map MiniDungeons 2,
- wszystkie 11 sa pokazane w Fig. 2,
- trening ewolucji polityk uzywa map 1, 2, 3, 4, 7, 10,
- test agentow uzywa wszystkich 11 map,
- wszystkie mapy zawieraja co najmniej jednego Minitaura,
- mapa 2 ma dwoch Minotaurow/Minitaurs,
- mapy 1 i 9 nie zawieraja ogres,
- mapy 4 i 10 maja wiecej ranged goblins niz melee goblins,
- mapa 1 ma wiecej melee goblins niz ranged goblins,
- siedem map zawiera portale,
- szesc map zawiera pulapki,
- mapy roznia sie liczba scian, choke pointow, dead endow i dlugoscia najkrotszej sciezki.

Nieokreslone:

- oryginalne pliki map,
- dokladne wspolrzedne kazdego obiektu jako tekst,
- pelna lista liczebnosci obiektow dla kazdej mapy poza tym, co da sie odczytac z Fig. 3,
- parowanie portali,
- czy Fig. 2 wystarcza do bezblednego rozpoznania wszystkich typow kafli,
- czy kolory/sprite'y z Fig. 2 sa jednoznaczne.

Decyzja implementacyjna:

- mapy przepisujemy recznie z Fig. 2,
- po przepisaniu tworzymy raport liczebnosci obiektow i porownujemy z Fig. 3,
- jesli liczebnosci sie zgadzaja, mapa jest zaakceptowana jako rekonstrukcja logiczna,
- w pracy opisujemy mapy jako rekonstrukcje na podstawie Fig. 2.

## 17. Cechy poziomow uzywane w analizie

Status: **czesciowo opisane**.

Artykul wspomina nastepujace cechy poziomow:

- liczba interaktywnych obiektow,
- liczba treasures,
- liczba potions,
- liczba goblins,
- liczba wizards,
- liczba minitaurs,
- liczba blobs,
- liczba ogres,
- liczba portali,
- liczba pulapek,
- liczba scian,
- choke points,
- dead ends,
- dlugosc najkrotszej sciezki miedzy wejsciem a wyjsciem,
- open areas,
- wiele innych niewymienionych cech.

Opisane definicje:

- dead ends to kafle z tylko jednym polaczonym przechodnim sasiadem,
- choke points wedlug tekstu sa kaflami z dwoma polaczonymi przechodnimi sasiadami,
- open areas sa kaflami, gdzie wszystkie sasiednie kafle sa nie-scianami.

Nieokreslone:

- pelna lista "many others",
- czy sasiedzi liczeni sa tylko w 4 kierunkach,
- czy obiekty i postacie wplywaja na cechy poziomu,
- czy portale sa uwzgledniane w najkrotszej sciezce,
- czy pulapki sa traktowane jako przechodnie,
- czy wyjscie i wejscie sa liczone jako przechodnie.

Decyzja implementacyjna:

- cechy topologiczne liczymy na statycznej mapie,
- sasiedzi to 4 kierunki,
- obiekty nie blokuja topologii,
- sciezka wejscie-wyjscie liczona jest po polach przechodnich, opcjonalnie bez portali w bazowej wersji.

## 18. Metryki rozgrywki

Status: **opisane w Table I / czesciowo nieokreslone**.

Metryki z artykulu:

| Skrot | Nazwa | Status |
| --- | --- | --- |
| ST | Steps Taken | opisane jako liczba krokow |
| PE | Proximity to Exit | uzywane, ale bez pelnego wzoru |
| PD | Potions Drunk | opisane, ratio do liczby potions |
| TO | Treasures Opened | opisane, ratio do liczby treasures |
| MTK | Minitaur Knockouts | opisane przez mechanike Minitaura |
| MS | Monsters Slain | opisane, ratio do liczby monsters |
| JT | Javelins Thrown | opisane jako liczba rzutow oszczepem |
| HL | Health Left | opisane jako pozostale HP |
| TU | Teleports Used | opisane przez portale |
| TS | Traps Sprung | opisane przez pulapki |
| Rbar | Average MCTS reward | wymienione, ale nieopisane szczegolowo |
| IC | Interactive Objects Consumed | uzywane, czesciowo niejednoznaczne |

Z artykulu:

- `PD`, `MS`, `TO`, `IC` sa wartosciami ratio,
- `PD` jest ratio wzgledem wszystkich potions,
- `MS` jest ratio wzgledem wszystkich monsters,
- `TO` jest ratio wzgledem wszystkich treasures,
- `IC` jest ratio wzgledem wszystkich non-monster game objects wedlug zdania pod Table I,
- Completionist w opisie celu obejmuje monsters, potions, treasures.

Uwaga o niespojnosci:

- Tekst opisuje Completionist jako osobe konsumujaca/killing monsters, potions, treasures.
- Zdanie o `IC` mowi o ratio z "all non-monster game objects".
- To tworzy potencjalna niespojnosc: czy `IC` zawiera monsters, czy nie.

Decyzja implementacyjna:

- dla eksperymentu glownego warto zdefiniowac `IC` jako ratio wszystkich obiektow istotnych dla Completionist: monsters slain + potions drunk + treasures opened, bo to zgadza sie z opisem persony,
- w pracy nalezy zaznaczyc, ze artykul ma tu niejednoznaczne sformulowanie,
- mozna dodatkowo raportowac `IC_non_monster`, zeby zachowac pelna transparentnosc.

## 19. Proximity to Exit

Status: **wspomniane, ale nieopisane wzorem**.

Z artykulu:

- `PE` jest uzywane w funkcjach uzytecznosci,
- dla przykladu fitness Monster Killer autorzy pisza, ze `PE = 0`, jesli wyjscie zostalo osiagniete,
- Runner maksymalizuje `PE - 0.01 * ST`,
- `PE` jest nazywane proximity to exit.

Nieokreslone:

- czy `PE` jest dystansem, czy odwrotnoscia dystansu,
- czy wieksze `PE` oznacza blizej wyjscia,
- jak `PE = 0` po osiagnieciu wyjscia pasuje do maksymalizacji funkcji Runner,
- czy `PE` jest normalizowane,
- czy uzywa Manhattan distance, A*, shortest path, czy odleglosci Euklidesowej,
- czy portale sa uwzgledniane.

Decyzja implementacyjna:

- nalezy wybrac jedna definicje i trzymac ja dla wszystkich agentow,
- bezpieczna opcja: `PE = 1 - shortest_path_distance_to_exit / max_shortest_path_distance_on_map`, a po osiagnieciu wyjscia `PE = 1`,
- jesli chcemy byc blizej zdania "PE = 0 if exit was reached", mozna zdefiniowac `PE` jako negatywny znormalizowany dystans albo osobno nazwac metryke `distance_to_exit`,
- w pracy trzeba jasno wskazac wybrana interpretacje.

## 20. Persony

Status: **opisane wprost**.

### Runner

Cel:

- dotrzec do wyjscia,
- zrobic to w jak najmniejszej liczbie ruchow.

Utility:

```text
U_R = PE - 0.01 * ST       jesli bohater zyje
U_R = PE - 0.01 * ST - 5   jesli bohater umarl
```

### Monster Killer

Cel:

- zabic jak najwiecej potworow,
- drugorzednie zblizyc sie do wyjscia.

Utility:

```text
U_MK = 0.7 * MS + 0.3 * PE       jesli bohater zyje
U_MK = 0.7 * MS + 0.3 * PE - 5   jesli bohater umarl
```

### Treasure Collector

Cel:

- zebrac jak najwiecej skarbow,
- drugorzednie zblizyc sie do wyjscia.

Utility:

```text
U_TC = 0.7 * TO + 0.3 * PE       jesli bohater zyje
U_TC = 0.7 * TO + 0.3 * PE - 5   jesli bohater umarl
```

### Completionist

Cel:

- konsumowac obiekty,
- zabijac potwory,
- zbierac potions i treasures,
- drugorzednie zblizyc sie do wyjscia.

Utility:

```text
U_C = 0.7 * IC + 0.3 * PE       jesli bohater zyje
U_C = 0.7 * IC + 0.3 * PE - 5   jesli bohater umarl
```

Nieokreslone:

- dokladna definicja `IC`,
- dokladna definicja `PE`,
- czy utility liczone jest tylko po rolloutach, czy takze po kazdym realnym ruchu poza MCTS.

## 21. MCTS jako czesc systemu grywalnego

Status: **opisane wprost jako metoda, nie jako zasada gry**.

Z artykulu:

- wszystkie persony uzywaja MCTS do sformulowania sekwencji akcji,
- MiniDungeons 2 jest deterministyczne, wiec persona buduje jedno drzewo na mape,
- budowa drzewa konczy sie po znalezieniu zwycieskiego stanu terminalnego albo po timeout,
- agent bierze najlepsza znaleziona sekwencje akcji,
- rollout symuluje 10 losowych ruchow przed backpropagation,
- baseline uzywa UCB1,
- evolved MCTS zastepuje UCB1 wyewoluowana formula.

Nieokreslone:

- dokladny timeout dla kazdego eksperymentu poza wzmianka o maksimum 300 sekund w wynikach,
- czy 10 losowych ruchow obejmuje tury NPC,
- jak wybierana jest najlepsza sekwencja,
- jak rozstrzygane sa remisy w ocenie wezlow,
- czy drzewo jest naprawde jedno na cala mape, czy aktualizowane po kolejnych akcjach,
- jak dokladnie reprezentowane sa akcje z oszczepem.

Decyzja implementacyjna:

- rollout obejmuje pelne tury gry: akcja bohatera + reakcja NPC,
- losowy rollout wybiera legalne akcje bohatera,
- po wyborze najlepszej sekwencji mozna wykonac cala sekwencje albo pierwszy ruch i kontynuowac wedlug zalozenia; trzeba to opisac,
- timeout ustawiamy jawnie w konfiguracji eksperymentu.

## 22. Wiedza brakujaca mimo wzmianki w artykule

Najwazniejsze braki do uzupelnienia decyzja implementacyjna po uwzglednieniu obu lokalnych PDF-ow:

1. Oryginalne pliki map.
2. Dokladne wspolrzedne i parowanie portali.
3. Pelna definicja line of sight.
4. Pelna definicja `PE`.
5. Pelna definicja `IC`.
6. Pelna macierz rzadkich kolizji postac-postac, szczegolnie NPC-NPC poza przypadkami opisanymi wprost.
7. Tie-breakery dla ruchu NPC.
8. Tie-breakery dla A* Minitaura.
9. Zachowanie NPC na wyjsciu, pulapkach i oszczepie.
10. Szczegolowa mechanika oszczepu po zabiciu celu i przy wielu celach w jednej linii.
11. Kolejnosc rozpatrywania obrazen i smierci.
12. Zachowanie scalonego bloba w kolejce tur.
13. Czy trap oglusza Minitaura.
14. Czy obiekty i NPC blokuja line of sight.
15. Czy ruch w sciane jest nielegalny, czy jest akcja bez efektu.
16. Czy akcja "czekaj" istnieje.
17. Czy rzut oszczepem liczy sie do `ST`.
18. Dokladny budzet czasu/iteracji MCTS.
19. Dokladna implementacja "average MCTS reward".
20. Pelna lista cech poziomow okreslona jako "many others".
21. Roznica startowego HP bohatera: 1-10 HP w opisie MD2 kontra 10 HP w eksperymencie MCTS.

## 23. Minimalny zestaw decyzji przed kodowaniem

Przed implementacja pelnego srodowiska trzeba zamknac te decyzje:

- format map tekstowych,
- symbole wszystkich kafli i przeciwnikow,
- definicja line of sight,
- definicja kolejnosci rozpatrywania walki bohater-potwor,
- definicja oszczepu,
- definicja `PE`,
- definicja `IC`,
- pelna macierz kolizji,
- tie-breaker ruchu,
- tie-breaker A*,
- liczenie `TU` przy portalach uzytych przez NPC,
- zasady pulapek dla Minitaura,
- czy istnieje akcja wait,
- czy MCTS wykonuje cala sekwencje czy tylko pierwszy ruch.

## 24. Proponowane zdanie do pracy

W pracy warto uzyc podobnego opisu:

```text
Srodowisko MiniDungeons 2 zostalo zrekonstruowane na podstawie opisu mechanik,
metryk i map przedstawionych w publikacji zrodlowej. Celem implementacji jest
zachowanie zgodnosci metodologicznej z eksperymentem autorow, a nie bitowa
reprodukcja oryginalnego silnika. W przypadkach, w ktorych publikacja nie
okresla jednoznacznie reguly sytuacji brzegowej, przyjeto deterministyczne
reguly implementacyjne opisane w rozdziale dotyczacym srodowiska.
```

## 25. Checklist zgodnosci z artykulem

Srodowisko mozna uznac za zgodne metodologicznie, gdy:

- ma 11 map logicznie odtworzonych z Fig. 2,
- mapy maja rozmiar 10x20, z udokumentowanym wyjatkiem mapy 5 o rozmiarze 11x14,
- ma bohatera z 10 HP,
- ma wyjscie jako warunek zwyciestwa,
- ma smierc po utracie HP,
- ma potions, treasures, portals, traps,
- ma oszczep wielorazowy,
- ma line of sight,
- ma goblins, wizards, blobs, ogres, minitaurs,
- ma stala kolejnosc tur NPC wedlug pozycji poczatkowej,
- liczy metryki z Table I,
- implementuje Runner, Monster Killer, Treasure Collector, Completionist,
- pozwala uruchomic MCTS-UCB1,
- pozwala uruchomic MCTS z ewoluowana polityka drzewa,
- pozwala uruchomic PPO/RL jako rozszerzenie,
- zapisuje wyniki dla 50 prob na mape,
- rozdziela mapy treningowe i testowe tak jak artykul.

## 26. Najblizszy krok

Stan obecny:

- zamrozony benchmark `md2-reconstructed-v1`: 11 map w `data/maps/md2/benchmark/`,
  pary portali w `portal_pairs.json`, wymiary i hashe w `benchmark_manifest.json`,
- mapa 5 jest jawnym wyjatkiem 11x14 potwierdzonym siatka kontrolna,
- liczebnosci obiektow sa zgodne z Fig. 3 (`docs/benchmark/object_counts.md`),
- ograniczenia rekonstrukcji opisuje `docs/benchmark/uncertainties.md`,
- spojnosci i sum kontrolnych pilnuje `tools/validate_stage0.py`,
- deterministyczny, klonowalny silnik jest w `src/minidungeons/domain/engine.py`;
  parametry w `data/rules/md2_rules.json` i `data/rules/personas.json`,
  testy mechanik w `tests/domain/test_rules_engine.py`.

Najblizszy krok to dluzszy sanity check Random Agenta na wszystkich 11 mapach,
a po nim implementacja MCTS-UCB1.
