"""MCTS dla person MiniDungeons 2 - petla wspolna dla kazdej tree policy."""

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
    """Konfiguracja wezlow wynikajaca z tree policy; `Node` nie zna konkretnej polityki."""

    collect_terminals: bool = False
    pe_mode: str = "binary"

    @classmethod
    def for_policy(cls, policy: SelectionPolicy) -> "TreeSpec":
        return cls(
            collect_terminals=policy.needs_terminals,
            pe_mode=policy.pe_mode,
        )


DEFAULT_SPEC = TreeSpec()

# odczytania "best sequence of actions it discovered" (sekcja V)
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
        self.action = action
        self.spec = spec
        self.children: dict[Action, "Node"] = {}
        self.untried = list(env.legal_actions())
        self.visits: int = 0
        self.total_utility = 0.0
        # wyczerpany = terminalny albo rozwiniety z samymi wyczerpanymi dziecmi;
        # polityka bez czlonu eksploracyjnego inaczej wybiera martwy lisc w kolko
        self.exhausted = not self.untried
        # sumy zmiennych Tabeli I po stanach koncowych symulacji, jak R (sekcja V-A)
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
        _, info = self.env.step(action)
        self.played.append(action if isinstance(action, Action) else Action.move(action))
        # kafel portalu tez jest odwiedzony - bez niego slad przeskakuje przez mape
        for event in info["events"]:
            if event["type"] == "teleport" and event.get("actor") == "hero":
                self.path.append(event["from"])  # type: ignore[arg-type]
        self.path.append(self.env.hero_position)
        return info

    def _iterate(self, persona: str, rng: random.Random) -> Node:
        """Jedna iteracja MCTS; zwraca lisc, na ktorym skonczyla sie selekcja."""

        node = self.root
        while not node.untried and node.viable_children():
            node = node.best_child(self.policy)
        if node.untried and not node.env.done:
            node = node.expand(rng)
        value, terminals = self.rollout(node.env, persona, rng)
        self.backpropagate(node, value, terminals)
        return node

    def rollout(
        self, env: MiniDungeon, persona: str, rng: random.Random, depth: int = 10
    ) -> tuple[float, tuple[float, ...] | None]:
        sim = env.clone()
        for _ in range(depth):
            legal = sim.legal_actions()
            if not legal:
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
            current.refresh_exhausted()
            current = current.parent

    def search(self, persona: str, iterations: int, seed: int = 0) -> Action | None:
        """Jeden ruch: zbuduj drzewo w zadanym budzecie i oddaj najlepsza akcje."""

        rng = random.Random(seed)
        for _ in range(iterations):
            if self.root.exhausted:
                break
            self._iterate(persona, rng)
        # decyzja po sredniej, bez czlonu eksploracyjnego
        return max(self.root.children.values(), key=Node.mean_utility).action

    def _build_tree(
        self,
        persona: str,
        rng: random.Random,
        deadline: float | None,
        max_iterations: int | None,
    ) -> tuple[list[Action] | None, int]:
        """Buduj drzewo do wygranej albo wyczerpania budzetu; zwraca (sciezka | None, iteracje).

        Wygrana tylko w rollout-cie sie nie liczy - potrzebny terminalny wezel drzewa.
        """

        iterations = 0
        while not self.root.exhausted:
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
        """Protokol z artykulu: jedno drzewo na mape, potem odegranie najlepszej sekwencji.

        Konczy pierwszy osiagniety budzet; tylko iteracyjny jest odtwarzalny.
        """

        if time_limit_s is None and max_iterations is None:
            raise ValueError(
                "Podaj time_limit_s, max_iterations albo oba - inaczej petla nie ma stopu"
            )
        rng = random.Random(seed)
        deadline = None if time_limit_s is None else time.perf_counter() + time_limit_s
        winning_actions, iterations = self._build_tree(persona, rng, deadline, max_iterations)
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
        # odtwarzalne, bo MD2 jest deterministyczny
        actions: list[Action] = []
        current = node
        while current.parent is not None:
            actions.append(current.action)
            current = current.parent
        return list(reversed(actions))

    def _fallback_sequence(self, persona: str, mode: str) -> list[Action]:
        """Sekwencja odgrywana po wyczerpaniu budzetu bez wygranej (sekcja V: "best sequence").

        utility - wezel o najwyzszej utility persony; mean / visits - zejscie zachlanne.
        """

        if mode == "utility":
            return self._best_utility_node_sequence(persona)
        if mode == "mean":
            return self._greedy_descent(Node.mean_utility)
        if mode == "visits":
            return self._greedy_descent(lambda node: float(node.visits))
        raise ValueError(f"Nieznany fallback {mode!r}; oczekiwano {FALLBACKS}")

    def _greedy_descent(self, key) -> list[Action]:
        """Zejscie zachlanne od korzenia po `key` do pierwszego wezla bez dzieci."""

        actions: list[Action] = []
        node = self.root
        while node.children:
            node = max(node.children.values(), key=key)
            actions.append(node.action)
        return actions

    def _best_utility_node_sequence(self, persona: str) -> list[Action]:
        """Sciezka do wezla o najwyzszej utility persony (eq. 2-5) na jego stanie.

        Remis rozstrzyga krotsza sciezka, bo eq. 2-5 karza kazdy krok (-0,01*ST).
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
