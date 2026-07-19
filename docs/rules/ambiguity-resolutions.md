# Ambiguity resolutions

Decyzje podjete tam, gdzie artykuly (`minidungeons_2.pdf`, `1802.06881v1_MCTS.pdf`)
nie definiuja zachowania jednoznacznie. Silnik implementuje je na sztywno;
`data/rules/md2_rules.json` zawiera tylko wartosci liczbowe.

| Id | Status w zrodlach | Decyzja | Powod |
| --- | --- | --- | --- |
| hero_start_hp | konflikt | 10 | Papier o rozgrywce dopuszcza 1-10 HP; reprodukowany eksperyment MCTS startuje jawnie z 10 HP. |
| line_of_sight_geometry | nieokreslone | ortogonalnie, sciany blokuja, postacie i obiekty nie | Papiery wymagaja nieprzerwanej linii wzroku, ale nie definiuja geometrii ani blokerow. |
| equal_path_tie_break | nieokreslone | N, E, S, W; rowne cele w kolejnosci row-major | Deterministyczny silnik i powtarzalny MCTS wymagaja stalego tie-breaka. |
| wait_action | nieokreslone | niedostepna | Papiery wymieniaja ruch i rzut oszczepem, nie wspominaja o czekaniu. |
| collision_timing | nieokreslone | obrazenia kolizji sa jednoczesne; wchodzacy zajmuje pole tylko gdy okupant znika | Papiery opisuja obrazenia przy kolizji, ale nie kolejnosc obrazen, smierci i ruchu. |
| wizard_without_los | roznica sformulowan | stoi w miejscu | Papier MCTS opisuje ruch tylko przy istniejacej linii wzroku poza zasiegiem 5. |
| javelin_details | czesciowo nieokreslone | dowolny widoczny potwor; inne postacie nie blokuja; oszczep laduje na polu celu; automatyczny podbior | Pole ladowania jest opisane, ale posrednie postacie i moment podbioru nie. |
| portal_occupied_destination | nieokreslone | teleport zablokowany, postac zostaje na portalu wejsciowym | Papiery nie definiuja teleportu na zajety portal. |
| trap_minitaur | nieokreslone | pulapka ogłusza Minitaura na trzy jego akcje | Pulapki dzialaja na kazda postac, a Minitaur zamienia obrazenia na ogluszenie zamiast utraty HP. |
| blob_merge_and_turn_order | czesciowo nieokreslone | moce sumuja sie do poziomu 3; scalony blob zachowuje nizsza oryginalna kolejnosc tury | Papiery definiuja trzy poziomy mocy i scalanie, ale nie dokladna arytmetyke ani tozsamosc w kolejce. |
| npc_exit_behavior | nieokreslone | neutralna, przechodnia podloga | Tylko Bohater ma zdefiniowana interakcje z Wyjsciem. |
| proximity_to_exit | wewnetrznie niejednoznaczne | ujemny znormalizowany statyczny dystans najkrotszej sciezki; 0 przy wyjsciu; portale ignorowane | Papier maksymalizuje PE i podaje PE=0 przy wyjsciu, ale nie podaje wzoru. |
| interactive_objects_consumed | wewnetrznie sprzeczne | zabojstwa Bohatera + mikstury + skarby, dzielone przez ich poczatkowa sume | Opis Completionisty obejmuje potwory, a notka z Tabeli I nazywa IC obiektami nie-potworami. |
| monsters_slain_denominator | nieokreslone | poczatkowe zabijalne potwory bez Minitaurow; licza sie tylko kolizje Bohatera i oszczep | Minitaury nie moga zginac i maja osobna metryke knockoutow. |
| terminal_turn_order | nieokreslone | dotarcie do Wyjscia konczy gre przed odpowiedziami NPC | Papiery mowia, ze poziom konczy sie na Wyjsciu, ale nie czy pozostale tury NPC sie wykonuja. |
| goblin_avoidance_scope | czesciowo nieokreslone | goblin i czarodziej omijaja tylko gobliny i czarodziejow; w bloba, ogra i minitaura moga wejsc i wywolac kolizje | Papier mowi "Goblins avoid colliding with other Goblins and Goblin Wizards" i milczy o pozostalych; dla czarodzieja przyjeto symetrycznie te sama regule. |
