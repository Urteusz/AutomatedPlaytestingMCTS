# Źródła do rekonstrukcji MiniDungeons 2 / MCTS

Data sprawdzenia: 7 września 2026. Punktem odniesienia są załączone strony arXiv:1802.06881v1 oraz MD2/FDG 2015. Nie zmieniono implementacji projektu. Wyniki obliczeniowe poniżej pochodzą z osobnego, lokalnego skryptu weryfikacyjnego.

**Najważniejsze znalezisko: publiczny kod z udziałem Michaela Cerny’ego Greena zawiera jawną normalizację odległości, LOS i zapisane drzewa person. Nie jest to jednak udokumentowany snapshot eksperymentu z 2018 roku.**

| Pytanie | Wynik |
|---|---|
| 1. PE | Znaleziono wzór w późniejszym kodzie: odwrócona normalizacja długości ścieżki A*, zakres [0,1], wartość 1 na wyjściu. Brak ostatecznego potwierdzenia wersji 2018. |
| 2. LOS | Znaleziono dokładny algorytm. Kierunek promienia zmienia wynik: 123 lub 118 rzutów na mapie 2. Odtworzono 118 po odwróceniu wywołania względem znalezionego kodu. |
| 3. Mapa 8 | Znaleziono szczegóły przestrzeni akcji i implementacji MCTS; przyczyny dokładnie 72 sekund nie rozstrzygnięto. |
| 4. C > R w baseline | Nie znaleziono rozstrzygnięcia. Późniejszy kod różni się od opisu baseline i utility C. |
| 5. 2–5 mln węzłów | Nie znaleziono przypisania tej liczby do konkretnej grupy ani sprzętu eksperymentu. |

## Pochodzenie znalezionego kodu

**Źródło:** [MiniDungeons 3D game and research](https://github.com/MasterMilkX/minidungeons-3d), repozytorium MasterMilkX; historia wskazuje M Charity i Michaela Greena, 2022. Sprawdzony commit: `c203372c30fdab288124a35e680e2fe2275cfb79`, 6 maja 2022.

Michael Green dodał symulator 29 kwietnia 2022 w [commicie be09632](https://github.com/MasterMilkX/minidungeons-3d/commit/be09632ba91d4f475eeb28d88d0145977f13dbf7), opisanym:

> a ton of scripts from the old game

Pliki `SimUtilityCalculator.cs` i `SimLevel.cs` są identyczne w tym commicie i sprawdzonym końcu gałęzi. To kod przeniesiony ze starszej gry przez współautora publikacji; historia repozytorium nie ujawnia jednak daty powstania tej starszej wersji. **Wiarygodność: wysoka dla działania udostępnionego kodu, ograniczona dla zgodności z wykonaniem eksperymentu 2018.**

## 1. Definicja PE

[SimUtilityCalculator.cs, wiersze 23–60](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/SimUtilityCalculator.cs#L23) najpierw oblicza długość ścieżki dla każdego przechodniego kafla:

```csharp
int length = level.AStar(tile.Point, level.SimExit.Point).Length;
```

Następnie:

```csharp
double normalizedLength = 1d-((double)length - (double)minLength) / ((double)maxLength - (double)minLength);
```

Zatem dla osiągalnych kafli zwykłej mapy:

**PE(s) = 1 − (L(s) − Lmin)/(Lmax − Lmin).**

Wynik trafia do `_distanceToExit`, a następnie do utility Runnera, MK i TC. Nie jest to wartość binarna ani ujemna odległość. Na najbliższym kaflu — wyjściu — wynosi 1, na najdalszym 0. Osobno należy traktować nieosiągalne kafle i zdegenerowane mapy.

[SimAStar.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Pathfinding/SimAStar.cs#L5) stosuje heurystykę Manhattan. [SpatialAStar.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Pathfinding/SpatialAStar.cs#L140) buduje ścieżki po czterech sąsiadach, a ścieżka do tego samego kafla ma jeden element. [SimMapNode.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Pathfinding/SimMapNode.cs#L16) uzależnia przechodniość od bazowego kafla. To **długość najkrótszej ścieżki omijającej ściany**, nie sama odległość Manhattan między współrzędnymi. W tej bazie ścieżek portale nie tworzą dodatkowych krawędzi, a postacie nie blokują kafli. Dla spójnej mapy wzór odpowiada **1 − dBFS/dmax**, ponieważ stałe doliczenie kafla początkowego znosi się w normalizacji.

**Co łączy kod z artykułem?** Odczytałem serializowane drzewa:

- [GenProgram99R.txt](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Assets/Resources/MCTSEvolvedAgents/GenProgram99R.txt): po uproszczeniu daje `a·ST·PE²·(PE+1) + R̄·(1−HL)`, gdzie `a = 1/0.5433292³ = 6.234632548540564`, czyli 6.235 po zaokrągleniu — wzór (6).
- [GenProgram99TC.txt](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Assets/Resources/MCTSEvolvedAgents/GenProgram99TC.txt): daje `2PD + 2MS + TO + 3R̄ + ST + PE + 0.1903189`, czyli wzór (8) z dokładniejszą stałą.

To silne powiązanie, ale nie dowód, że każda funkcja zachowała wersję z 2018. Dodatkowo [drzewo C](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Assets/Resources/MCTSEvolvedAgents/GenProgram99C.txt) zawiera składnik `HL·MS`, którego nie ma w podanym wzorze (9), a [drzewo MK](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Assets/Resources/MCTSEvolvedAgents/GenProgram99MK.txt) także różni się od (7). Nie należy traktować całego zestawu jako identycznego z publikacją.

**Rozstrzygnięcie historyczne:** nie znaleziono jednoznacznego potwierdzenia, że zdanie „PE = 0 if the exit was reached” jest literówką. Późniejszy kod stanowi mocny dowód na wariant dodatni, lecz pozostaje sprzeczność wersji.

**Własny wniosek matematyczny:** zamiana `−d/dmax` na `1−d/dmax` dodaje stałą do utility: +1 dla R, +0.3 dla MK/TC/C. W standardowym UCB1, przy identycznych pozostałych zasadach i jednakowym przesunięciu każdej nagrody, nie zmienia to rankingu odwiedzonych dzieci. Nie wyjaśnia więc samoistnie różnicy win rate baseline. Dla nieliniowych ewoluowanych tree policies przesunięcie PE ma natomiast znaczenie.

## 2. Geometria LOS i liczba 118

[SimLevel.cs, wiersze 409–464](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/SimLevel.cs#L409) sprawdza ściany na dyskretnym promieniu; postacie go nie zasłaniają. Promień przechodzi `1+dx+dy` kafli, poruszając się w każdej iteracji w jednej osi. W remisie błędu wybiera oś Y. Dlatego widoczność może być niesymetryczna. [Wywołanie dla oszczepu](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/SimLevel.cs#L420) brzmi:

```csharp
LineOfSight(SimHero.Point, Monsters[monster].Point)
```

**Własna weryfikacja:** mapa 2 z repozytorium jest identyczna z lokalną `map02.txt` po zamianie symboli, także dla obiektów. Przeniesienie algorytmu daje:

| Wariant sprawdzania | Kafle | Ruchy | Rzuty | (ruchy + rzuty)/kafle |
|---|---:|---:|---:|---:|
| Bohater → potwór, tak jak w kodzie | 105 | 240 | 123 | 3.457143 |
| Potwór → bohater, odwrócony eksperymentalnie | 105 | 240 | **118** | **3.409524** |

Liczenie obejmuje także cel na kaflu, na który hipotetycznie przestawiono bohatera. Tak działa znaleziony [StaticLevelComplexityCheck.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/HelperTools/StaticLevelComplexityCheck.cs#L22): przestawia bohatera na każdy pusty kafel bazowy, zachowując rozmieszczenie potworów, i zbiera akcje bez wykonywania tur.

**Wniosek:** znaleziono algorytm i kierunek dający opublikowane 118, ale nie znaleziono historycznego wywołania uzasadniającego odwrócenie argumentów. To wynik kontrolowany, nie potwierdzenie, że autorzy liczyli tak w 2015. Przykład asymetrii: promień (0,0)→(1,1) odwiedza pośrednio (0,1); odwrotny odwiedza (1,0).

## 3. Mapa 8 i przestrzeń akcji

W [GetPossibleHeroActions](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/SimLevel.cs#L465) są cztery legalne kierunki i cele oszczepu; nie ma dodawania ruchów w ściany ani samodzielnej akcji czekania. Lista celów oszczepu **nie filtruje Alive**. To szczegół wymagający porównania z rekonstrukcją. Nie dowodzi, że odpowiada za 72 s.

**Platforma jest potwierdzona źródłem historycznym:** Christoffer Holmgård, *Procedural Personas for Player Decision Modeling and Procedural Content Generation*, rozprawa doktorska, IT University of Copenhagen, sierpień 2015, sekcja 5.3, s. 38 (PDF s. 60):

> implemented in Mono (Xamarin, 2004) using the Unity (Unity Technologies, 2005) game engine

[PDF rozprawy](https://en.itu.dk/-/media/EN/Research/PhD-Programme/PhD-defences/2015/Holmgard2015_Procedural_Personas_for_Player_Decision_Modeling_and_Procedural_Content_Generation-1-pdf.pdf). Wiarygodność wysoka dla platformy MD2; brak identyfikacji sprzętu eksperymentu 2018.

[Tree.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Controllers/MCTS/Tree.cs#L115) ujawnia też losowanie rolloutów:

```csharp
int chosenIndex = rnd.Next(possibleActions.Count - 1);
```

Przy co najmniej dwóch akcjach pomija ono ostatnią pozycję listy. Kod klonuje stan przy ekspansji i rolloucie. **To obserwacje dotyczące 2022; nie ustalono, czy występowały w 2018.**

**Korekta metodologiczna, niezależna od źródeł:** z czasu wyszukiwania MCTS nie wynika konieczność zwiększenia branching factor do 5–5.7. `b⁸` szacuje poziom pełnego drzewa o stałym rozgałęzieniu, a MCTS nie musi przeszukiwać poziomów równomiernie. Liczba symulowanych ruchów nie jest liczbą nowych węzłów; koszt węzła obejmuje również rollout i selekcję. 72 s nie identyfikuje samo w sobie przestrzeni akcji. Przyczyny dokładnego czasu **nie znaleziono**.

## 4. Kolejność C > R w baseline

**Nie znaleziono rozstrzygnięcia.** Istnieje ważna przeszkoda w użyciu późniejszego kodu jako repliki baseline:

[Node.cs, GetUCTScore](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Controllers/MCTS/Node.cs#L90) ma wyłączony składnik eksploracyjny, miesza średnią nagrodę z maksimum przy Q=0.25, a bez ewoluowanego drzewa zwraca ten wynik. Nie jest to opisany w artykule standardowy UCB1. Fragment:

```csharp
double reward = (1 - Q) * (TotalValue / nj) + Q * MaxValue;
```

Ponadto [CompletionistUtility](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/SimUtilityCalculator.cs#L203) używa średniej trzech osobno znormalizowanych stosunków, a wariant ze wspólnym `interactablesRatio` jest zakomentowany. Nie można na tej podstawie przypisać takiej utility eksperymentowi 2018.

## 5. „Between two and five million nodes”

**Nie znaleziono rozstrzygnięcia: baseline czy evolved, ani CPU/RAM czy tabeli liczby węzłów.** Udostępniony przez Liapisa [PDF artykułu](https://antoniosliapis.com/papers/automated_playtesting_with_procedural_personas_through_mcts_with_evolved_heuristics.pdf) zachowuje to zdanie oraz problematyczną wartość PE=0. Nie dopowiada rozróżnienia.

Późniejszy [Tree.cs](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/Controllers/MCTS/Tree.cs#L22) ma limit 10 000 iteracji. Licznik rośnie także przy przejściu selekcji, więc nawet jego log „Tree Size” nie jest automatycznie liczbą utworzonych węzłów. Nie wolno użyć tego limitu jako rekonstrukcji deklaracji 2–5 mln.

## Dodatkowo: dzielenie w Evolute C#

**Źródło:** *Evolute_C#*, konto autora projektu `itay2541`, wydanie `EvoluteC#0.2_23.2.2013.rar`, 23 lutego 2013. [Pliki SourceForge](https://sourceforge.net/projects/evolute-csharp/files/), [archiwum wydania](https://sourceforge.net/projects/evolute-csharp/files/EvoluteC%230.2_23.2.2013.rar/download).

Pobrałem archiwum i odczytałem `FunctionTypes.cs`, wiersze 149–155. Metoda Divide kończy się:

```csharp
return (fLeftValue / fRightValue);
```

Oba argumenty mają typ float. **Brak ochrony zwracającej 1 przy zerowym mianowniku.** Takie dzielenie może dać Infinity lub NaN. Identyczna metoda występuje w [kopii biblioteki w repozytorium MD3](https://github.com/MasterMilkX/minidungeons-3d/blob/c203372c30fdab288124a35e680e2fe2275cfb79/MiniDungeons3D/Assets/Scripts/simulator/EvoluteC%23/FunctionTypes.cs#L149). To potwierdza operator tej wersji biblioteki, ale nie wyklucza nieudostępnionych zmian autorów w 2018 ani obsługi niepoprawnych wyników na innym poziomie. Wiarygodność wysoka dla biblioteki, niepełna dla historycznego eksperymentu.

## Sprawdzone tropy i granice wyszukiwania

| Trop | Co sprawdzono i wynik |
|---|---|
| MCTS 2015 | Holmgård, Liapis, Togelius, Yannakakis, *Monte-Carlo Tree Search for Persona Based Player Modeling* (2015), [PDF](https://www.antoniosliapis.com/papers/monte-carlo_tree_search_for_persona_based_player_modeling.pdf), [DOI i metadane](https://doi.org/10.1609/aiide.v11i5.12849). Tabela 1: „reducing the distance to the exit (Di)”. Nie znaleziono normalizacji PE. Inny protokół: do 10 000 akcji w playoucie, budżet decyzji. Wysoka wiarygodność dla poprzednika. |
| Rozprawa Holmgårda | Pobrano i przeszukano 270 stron pod kątem PE, odległości, LOS, Unity i sprzętu; szczególnie rozdziały 5 i 11. Potwierdzono Mono/Unity; nie znaleziono wzoru PE ani geometrii LOS dla eksperymentu 2018. Fragment o A* w starszych rozdziałach dotyczy MD1 i nie stanowi dowodu transferu reguł. |
| Strona projektu Liapisa | [MiniDungeons 2](https://antoniosliapis.com/projects/project_minidungeons_2.php) prowadzi do publikacji; brak linku do historycznego repozytorium/builda MD2. |
| Wersje artykułu | [arXiv](https://arxiv.org/abs/1802.06881) pokazuje tylko v1. Publikacja czasopismowa istnieje: Holmgård, Green, Liapis, Togelius, IEEE Transactions on Games 11(4), 352–362, grudzień 2019, online 20 lutego 2018, [DOI 10.1109/TG.2018.2808198](https://ieeexplore.ieee.org/document/8295256/). Sprawdzono publiczną kopię Liapisa; nie twierdzę, że zweryfikowano pełny PDF wydawcy. |
| GitHub autorów | Przejrzano publiczne repozytoria mcgreentn, holmgard, sentientdesigns i wyniki wyszukiwania MiniDungeons wraz z forkami. [DungeonExplorer](https://github.com/holmgard/DungeonExplorer) zwracał pusty repozytorium w API (409). |
| Kod MD1 | [sentientdesigns/minidungeons](https://github.com/sentientdesigns/minidungeons) opisuje uproszczone MD1 i nie jest implementacją eksperymentu MD2. Sprawdzono opis repozytorium, nie wykonano audytu wszystkich jego plików. |
| Analiza Greena | [md2_mechanic_analysis](https://github.com/mcgreentn/md2_mechanic_analysis), 2021+: dane, notebooki i analiza; przegląd drzewa nie ujawnił silnika C#. |
| MD3 | Publiczny [build Greena](https://github.com/mcgreentn/minidungeons-3d-build) oraz znalezione repozytorium źródłowe z jego udziałem; źródła opisane wyżej. Nie uruchamiano builda gry. |
| Evolute | Główna strona projektu miała timeout; katalog SourceForge i pobranie archiwum 2013 zadziałały. Nie było potrzeby zastępować archiwum kopią Internet Archive. |
| Bravi i in. 2017 | Ivan Bravi, Ahmed Khalifa, Christoffer Holmgård, Julian Togelius, *Evolving Game-Specific UCB Alternatives for General Video Game Playing* (2017), [rekord Uniwersytetu Maltańskiego](https://www.um.edu.mt/library/oar/handle/123456789/82028). PDF oznaczony Restricted Access; nie potwierdzono z jego treści konwencji dzielenia. |
| Strony Togeliusa/Khalify | Próby otwarcia stron przyniosły błędy pobierania/certyfikatu albo brak użytecznych linków. Nie oznacza to braku publikacji na tych serwerach. |
| Nowsza praca 2019 | Green, Khalifa, Alsoughayer, Surana, Liapis, Togelius, *Two-step Constructive Approaches for Dungeon Generation* (2019), [tekst](https://arxiv.org/html/1906.04660v1). Tabela 1 podaje dla maga „within 3 tiles”, wobec 5 w załącznikach; brak algorytmu LOS i wzoru PE. To nie jest druga nazwa publikacji IEEE, lecz osobna praca. |

Nie przeprowadzono pełnego audytu wszystkich historycznych repozytoriów GitLab, archiwów internetowych, materiałów Cazenave’a i Whitleya ani osobnej pełnotekstowej analizy każdej publikacji MD1. „Nie znaleziono” oznacza wynik opisanych sprawdzeń, nie dowód nieistnienia źródła. Nie kontaktowano się z autorami.

## Weryfikacja lokalna

Skrypt: `tmp/source_research_20260907/verify_findings.py`. Uruchomienie z katalogu projektu:

```powershell
python tmp/source_research_20260907/verify_findings.py
```

Sprawdza tożsamość mapy 2 po translacji znaków, liczy 105/240/123/118 i odczytuje wszystkie cztery serializowane drzewa. Pobrane źródła i metadane commitów zachowano w tym samym katalogu roboczym. Żaden z pięciu punktów nie został automatycznie „naprawiony” w silniku na podstawie tych wyników.

