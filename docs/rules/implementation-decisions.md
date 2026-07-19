# MiniDungeons 2 — decyzje implementacyjne v1

Status: **obowiązujący zestaw zasad rekonstrukcji metodologicznej**.

Źródła pierwotne:

- `docs/reference/articles/minidungeons_2.pdf`, sekcja 2 — mechanika gry;
- `docs/reference/articles/1802.06881v1_MCTS.pdf`, sekcje IV–V i Table I — wariant
  eksperymentalny, metryki i persony.

Parametry wykonywalne znajdują się w `data/rules/md2_rules.json` (silnik)
i `data/rules/personas.json` (persony). Ten dokument jest
ich skrótem dla człowieka. Nie twierdzimy, że decyzje rekonstrukcyjne są
oryginalnym kodem autorów.

## Reguły określone przez publikacje

- gra jest deterministyczna, turowa i używa czterech kierunków ruchu;
- bohater zaczyna eksperyment MCTS z 10 HP i wygrywa po wejściu na wyjście;
- bohater działa pierwszy, a NPC później w stałej kolejności ich początkowych
  pozycji, wierszami od lewego górnego rogu;
- potion leczy bohatera o 1 do maksimum 10, treasure zwiększa wynik skarbów,
  trap zadaje 1 obrażenie przy każdym wejściu, a portal teleportuje natychmiast;
- bohater ma jeden odzyskiwalny oszczep zadający 1 obrażenie;
- Goblin, Wizard, Blob, Ogre i Minitaur zachowują się zgodnie z opisami w
  publikacjach;
- Minitaur nie ma HP, nie ginie i po obrażeniu jest wyłączony na 3 rundy;
- wzory Runnera, Monster Killera, Treasure Collectora i Completionista są
  zapisane bezpośrednio w JSON i wykonywane przez `src/personas.py`.

## Niejednoznaczności zamknięte deterministyczną decyzją

| Problem | Decyzja v1 |
| --- | --- |
| HP startowe: 1–10 kontra 10 | 10 HP, zgodnie z eksperymentem MCTS |
| Geometria line-of-sight | tylko osie N/E/S/W; blokują wyłącznie ściany |
| Remisy ścieżek | N, E, S, W; cele remisowe dalej w porządku wierszowym |
| Akcja czekania | brak; legalne są ruchy i dostępne rzuty oszczepem |
| Ruch w ścianę/poza mapę | akcja nielegalna, nie no-op |
| Kolejność obrażeń kolizyjnych | obrażenia jednoczesne; mover wchodzi tylko po usunięciu celu |
| Wizard bez line-of-sight | stoi; powyżej zasięgu 5 idzie tylko przy zachowanym LOS |
| Oszczep i wiele celów | można wybrać dowolnego widocznego potwora; postacie nie zasłaniają |
| Pole lądowania oszczepu | bieżące pole wybranego celu; podniesienie automatyczne po wejściu |
| Zajęty portal docelowy | teleport zablokowany; postać pozostaje na portalu wejściowym |
| Trap kontra Minitaur | traktowany jako obrażenie i ogłusza na 3 akcje Minitaura |
| Łączenie Blobów | suma poziomów do maksimum 3; zostaje niższy indeks kolejki |
| NPC na wyjściu | neutralne pole przechodnie; wygrywa tylko bohater |
| `PE` | ujemny znormalizowany dystans najkrótszej statycznej ścieżki; 0 na wyjściu |
| Portale w `PE` | pomijane |
| `IC` | zabici przez bohatera wrogowie + wypite potiony + otwarte skarby |
| Mianownik `MS` | początkowe zabijalne potwory, bez Minitaurów |
| Zaliczenie `MS` | tylko zabicie przez kolizję bohatera lub oszczep |
| Wejście na wyjście | natychmiastowy terminal; NPC nie odpowiadają w tej turze |

## Świadomie otwarte poza etapem zasad gry

- dokładna definicja `Average MCTS reward` (`R̄`) należy do implementacji MCTS;
- publikacja nie podaje pełnego budżetu iteracji/czasu dla każdego wariantu;
- bez oryginalnego silnika nie można potwierdzić bitowej zgodności rzadkich
  kolizji ani ukrytych warstw obiektów pod sprite'ami;
- definicje `PE` i `IC` są jawnie wybranymi interpretacjami i powinny być
  raportowane w pracy.

## Pliki wykonawcze

- `data/rules/md2_rules.json` — parametry liczbowe silnika;
- `data/rules/personas.json` — wagi person i kara śmierci;
- `docs/rules/ambiguity-resolutions.md` — rozstrzygnięcia niejednoznaczności;
- `src/minidungeons/domain/rules.py` — wczytywanie konfiguracji;
- `src/minidungeons/domain/engine.py` — deterministyczny, klonowalny silnik;
- `src/minidungeons/domain/personas.py` — funkcje użyteczności person;
- `tests/domain/test_rules_engine.py` — testy mechanik i sytuacji brzegowych.
