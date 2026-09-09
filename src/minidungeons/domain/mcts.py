"""MCTS dla person MiniDungeons 2 - petla wspolna dla kazdej tree policy.

Podzial odpowiedzialnosci:

* `TreeSpec` - czego tree policy potrzebuje od wezlow (patrz `selection_policy`);
* `Node`     - zamrozony stan gry plus statystyki symulacji;
* `MonteCarloTreeSearch` - jedna iteracja (`_iterate`), budowa drzewa
  (`_build_tree`) i dwa protokoly na niej oparte: `search` (jeden ruch) oraz
  `play_single_tree` (cala partia, protokol z artykulu).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import time

from .engine import Action, Coord, MiniDungeon
from .expression import TERMINAL_ORDER, terminal_values
from .selection_policy import SelectionPolicy, UCB1Policy

from .personas import utility


@dataclass(frozen=True, slots=True)
class TreeSpec:
    """Konfiguracja wezlow wynikajaca z tree policy.

    Dzieki temu `Node` nie zna zadnej konkretnej polityki - dostaje gotowa
    specyfikacje i przekazuje ja dzieciom. UCB1 zostawia wartosci domyslne,
    wiec nie placi za zmienne Tabeli I ani czasem, ani pamiecia.
    """

    collect_terminals: bool = False
    pe_mode: str = "binary"

    @classmethod
    def for_policy(cls, policy: SelectionPolicy) -> "TreeSpec":
        return cls(
            collect_terminals=policy.needs_terminals,
            pe_mode=policy.pe_mode,
        )


DEFAULT_SPEC = TreeSpec()

# warianty "best sequence of actions it discovered" (sekcja V) - patrz
# `_fallback_sequence` i docs/rules/decisions.md
FALLBACKS = ("utility", "mean", "visits")


class Node:
    """Jeden wezel drzewa: zamrozony stan gry i statystyki symulacji."""

    def __init__(
        self,
        env: MiniDungeon,
        parent: "Node | None",
        action: Action | None,
        spec: TreeSpec = DEFAULT_SPEC,
    ) -> None:
        self.env = env
        self.parent = parent
        self.action = action  # akcja, ktora doprowadzila do tego stanu
        self.spec = spec
        self.children: dict[Action, "Node"] = {}
        self.untried = list(env.legal_actions())
        self.visits: int = 0
        self.total_utility = 0.0
        # wezel wyczerpany = terminalny albo w calosci rozwiniety i majacy same
        # wyczerpane dzieci. Bez tego polityka bez czlonu eksploracyjnego (np.
        # ewoluowana formula) potrafi w nieskonczonosc wybierac martwy lisc.
        self.exhausted = not self.untried
        # suma zmiennych Tabeli I po stanach koncowych symulacji przechodzacych
        # przez ten wezel - ta sama semantyka co R (sekcja V-A artykulu)
        self.terminal_sums: list[float] | None = (
            [0.0] * len(TERMINAL_ORDER) if spec.collect_terminals else None
        )

    def expand(self, rng: random.Random) -> "Node":
        chosen = rng.choice(self.untried)
        self.untried.remove(chosen)
        new_env = self.env.clone()
        new_env.step(chosen)
        child = Node(new_env, self, chosen, self.spec)
        self.children[chosen] = child
        return child

    def mean_terminals(self) -> tuple[float, ...]:
        assert self.terminal_sums is not None
        if not self.visits:
            return tuple(self.terminal_sums)
        return tuple(value / self.visits for value in self.terminal_sums)

    def mean_utility(self) -> float:
        return self.total_utility / self.visits

    def viable_children(self) -> list["Node"]:
        return [child for child in self.children.values() if not child.exhausted]

    def refresh_exhausted(self) -> None:
        if self.exhausted or self.untried or not self.children:
            return
        self.exhausted = all(child.exhausted for child in self.children.values())

    def best_child(self, policy: SelectionPolicy) -> "Node":
        return policy.select(self)


class MonteCarloTreeSearch:
    """Jedno drzewo nad jednym stanem gry plus slad odegranej partii."""

    def __init__(self, map_path: str | Path, policy: SelectionPolicy | None = None) -> None:
        self.policy = policy if policy is not None else UCB1Policy()
        self.spec = TreeSpec.for_policy(self.policy)
        self.env = MiniDungeon(map_path)
        self.root = Node(self.env.clone(), None, None, self.spec)
        self.played: list[Action] = []
        self.path: list[Coord] = [self.env.hero_position]
        self.from_tree: bool | None = None

    @property
    def done(self) -> bool:
        return self.env.done

    def legal_actions(self) -> tuple[Action, ...]:
        return self.env.legal_actions()

    def step(self, action: Action | str) -> dict[str, object]:
        # mutuje stan w miejscu i zwraca opis zdarzen tej tury
        _, info = self.env.step(action)
        self.played.append(action if isinstance(action, Action) else Action.move(action))
        # kafel portalu tez jest odwiedzony, wiec zapisujemy go przed miejscem
        # docelowym - inaczej w sladzie powstalby przeskok przez pol mapy
        for event in info["events"]:
            if event["type"] == "teleport" and event.get("actor") == "hero":
                self.path.append(event["from"])  # type: ignore[arg-type]
        self.path.append(self.env.hero_position)
        return info

    # --- rdzen algorytmu -------------------------------------------------

    def _iterate(self, persona: str, rng: random.Random) -> Node:
        """Jedna iteracja MCTS. Zwraca lisc, na ktorym skonczyla sie selekcja.

        Wolajacy sprawdza na zwroconym wezle wlasny warunek stopu - dzieki temu
        `search` i `play_single_tree` dziela caly przebieg iteracji.
        """

        node = self.root
        # 1. selekcja: schodz tree policy, poki wezel jest w pelni rozwiniety
        while not node.untried and node.viable_children():
            node = node.best_child(self.policy)
        # 2. ekspansja: jesli jest co rozwijac i gra sie nie skonczyla
        if node.untried and not node.env.done:
            node = node.expand(rng)
        # 3. symulacja i 4. propagacja
        value, terminals = self.rollout(node.env, persona, rng)
        self.backpropagate(node, value, terminals)
        return node

    def rollout(
        self, env: MiniDungeon, persona: str, rng: random.Random, depth: int = 10
    ) -> tuple[float, tuple[float, ...] | None]:
        # gramy na kopii - stan wezla zostaje zamrozony
        sim = env.clone()
        for _ in range(depth):
            legal = sim.legal_actions()
            if not legal:  # smierc albo wyjscie - koniec wczesniej
                break
            sim.step(rng.choice(legal))
        terminals = None
        if self.spec.collect_terminals:
            terminals = terminal_values(sim, pe_mode=self.spec.pe_mode)
        return utility(persona, sim), terminals

    def backpropagate(
        self, node: Node, value: float, terminals: tuple[float, ...] | None = None
    ) -> None:
        # razem z korzeniem - jego visits to licznik "t" w UCB1 dzieci
        current: Node | None = node
        while current is not None:
            current.visits += 1
            current.total_utility += value
            if terminals is not None and current.terminal_sums is not None:
                sums = current.terminal_sums
                for index, sample in enumerate(terminals):
                    sums[index] += sample
            # znacznik wyczerpania idzie ta sama sciezka co statystyki
            current.refresh_exhausted()
            current = current.parent

    # --- protokoly oparte na powyzszej petli -----------------------------

    def search(self, persona: str, iterations: int, seed: int = 0) -> Action | None:
        """Jeden ruch: zbuduj drzewo w zadanym budzecie i oddaj najlepsza akcje."""

        rng = random.Random(seed)
        for _ in range(iterations):
            if self.root.exhausted:  # cale drzewo przeszukane
                break
            self._iterate(persona, rng)
        # decyzja: najlepsza SREDNIA, bez czlonu eksploracyjnego
        return max(self.root.children.values(), key=Node.mean_utility).action

    def _build_tree(
        self,
        persona: str,
        rng: random.Random,
        deadline: float | None,
        max_iterations: int | None,
    ) -> tuple[list[Action] | None, int]:
        """Buduj drzewo do wygranej albo do wyczerpania budzetu.

        Zwraca sekwencje akcji do wygrywajacego wezla (albo None) i liczbe
        wykonanych iteracji. Zwyciestwo osiagniete tylko podczas rollout-u
        wplywa na backpropagation przez utility, ale losowe akcje symulacji nie
        staja sie sekwencja do odegrania - potrzebny jest terminalny wezel
        drzewa (polityka "tree_terminal_only").
        """

        iterations = 0
        while not self.root.exhausted:  # inaczej dalsze iteracje sa puste
            if deadline is not None and time.perf_counter() >= deadline:
                break
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1
            node = self._iterate(persona, rng)
            if node.env.done and node.env.metrics.reached_exit:
                return self._path_to(node), iterations
        return None, iterations

    def play_single_tree(
        self,
        persona: str,
        time_limit_s: float | None = 300.0,
        seed: int = 0,
        *,
        max_iterations: int | None = None,
        fallback: str = "utility",
    ) -> dict[str, int | float | bool]:
        """Protokol z artykulu: jedno drzewo na mape, potem odegranie najlepszej
        sekwencji.

        Budzet jest czasowy (`time_limit_s`), iteracyjny (`max_iterations`) albo
        jednoczesnie jeden i drugi - konczy pierwszy osiagniety. Sam budzet
        iteracyjny jest odtwarzalny, czasowy nie, wiec fitness GP liczy sie na
        iteracjach.
        """

        if time_limit_s is None and max_iterations is None:
            raise ValueError(
                "Podaj time_limit_s, max_iterations albo oba - inaczej petla nie ma stopu"
            )
        rng = random.Random(seed)
        deadline = None if time_limit_s is None else time.perf_counter() + time_limit_s
        winning_actions, iterations = self._build_tree(persona, rng, deadline, max_iterations)
        # rozroznienie sladu: wygrana z drzewa czy zachlanny fallback
        self.from_tree = winning_actions is not None
        sequence = (
            winning_actions if winning_actions is not None
            else self._fallback_sequence(persona, fallback)
        )
        for action in sequence:
            if self.env.done:
                break
            self.step(action)
        result = self.env.metric_values()
        result["iterations"] = iterations
        return result

    def _path_to(self, node: Node) -> list[Action]:
        # akcje od korzenia do wezla; odtwarzalne, bo MD2 jest deterministyczny
        actions: list[Action] = []
        current = node
        while current.parent is not None:
            actions.append(current.action)
            current = current.parent
        return list(reversed(actions))

    def _fallback_sequence(self, persona: str, mode: str) -> list[Action]:
        """Sekwencja odgrywana po wyczerpaniu budzetu bez wygranej.

        Artykul, sekcja V: agent "will take the best sequence of actions it
        discovered", ale nie mowi, co znaczy "best". Trzy odczytania, wszystkie
        wybieralne, bo roznica jest MIERZALNA na metrykach obiektowych Tabeli II:

        * "utility" - sciezka do wezla o najwyzszej uzytecznosci persony
          policzonej na stanie tego wezla (`_best_utility_node_sequence`);
        * "mean"    - zejscie zachlanne po `mean_utility` dziecka;
        * "visits"  - zejscie po liczbie wizyt, czyli "robust child" - marsz
          glowna, wypracowana galezia drzewa.

        Pomiary i wybor: docs/rules/decisions.md.
        """

        if mode == "utility":
            return self._best_utility_node_sequence(persona)
        if mode == "mean":
            return self._greedy_descent(Node.mean_utility)
        if mode == "visits":
            return self._greedy_descent(lambda node: float(node.visits))
        raise ValueError(f"Nieznany fallback {mode!r}; oczekiwano {FALLBACKS}")

    def _greedy_descent(self, key) -> list[Action]:
        """Zejscie zachlanne od korzenia po podanym kluczu, do pierwszego wezla
        bez dzieci."""

        actions: list[Action] = []
        node = self.root
        while node.children:
            node = max(node.children.values(), key=key)
            actions.append(node.action)
        return actions

    def _best_utility_node_sequence(self, persona: str) -> list[Action]:
        """Sciezka do wezla o najwyzszej uzytecznosci persony.

        Artykul, sekcja V: agent buduje jedno drzewo na mape i przerywa budowe
        po znalezieniu wygranej "or it reaches timeout, wherein it will take the
        **best sequence of actions it discovered**". Odkryta sekwencja to
        sciezka od korzenia do wezla, a "najlepsza" mierzymy uzytecznoscia
        persony na stanie tego wezla - ta sama funkcja, ktora ocenia stany
        koncowe symulacji (eq. 2-5).

        Poprzednia wersja schodzila zachlannie po `mean_utility` dziecka i byla
        zla z dwoch powodow: srednia z jednego szczesliwego rolloutu bije
        rzetelna srednia z tysiecy symulacji, a marsz urywal sie na pierwszym
        nierozwinietym wezle. Zmierzone na 250 partiach fallbackowych pelnego
        przebiegu: 181 z nich odgrywalo DOKLADNIE JEDNA akcje.

        Remisy rozstrzyga krotsza sciezka - zgodnie z duchem eq. 2-5, gdzie
        kazdy krok jest karany (-0,01*ST).
        """

        best_node = self.root
        best_score = utility(persona, self.root.env)
        best_depth = 0
        stack: list[tuple[Node, int]] = [(self.root, 0)]
        while stack:
            node, depth = stack.pop()
            score = utility(persona, node.env)
            if score > best_score or (score == best_score and depth < best_depth):
                best_node, best_score, best_depth = node, score, depth
            for child in node.children.values():
                stack.append((child, depth + 1))
        return self._path_to(best_node)
