"""MCTS for all personalities in MiniDungeons 2 - right now only for UCB1"""

from __future__ import annotations

import math
from pathlib import Path
import random
import time

from .engine import Action, Coord, MiniDungeon

from .personas import utility


class Node:
    """Jeden wezel drzewa: zamrozony stan gry i statystyki symulacji."""

    def __init__(self, env: MiniDungeon, parent: "Node | None", action: Action | None) -> None:
        self.env = env
        self.parent = parent
        self.action = action  # akcja, ktora doprowadzila do tego stanu
        self.children: dict[Action, "Node"] = {}
        self.untried = list(env.legal_actions())
        self.visits: int = 0
        self.total_utility = 0.0

    def expand(self, rng: random.Random) -> "Node":
        chosen = rng.choice(self.untried)
        self.untried.remove(chosen)
        new_env = self.env.clone()
        new_env.step(chosen)
        child = Node(new_env, self, chosen)
        self.children[chosen] = child
        return child

    def best_child(self, c: float = math.sqrt(2)) -> "Node":
        total_visits = sum(child.visits for child in self.children.values())

        best_node = None
        best_score = float("-inf")

        for child in self.children.values():
            average_utility = child.total_utility / child.visits

            exploration_bonus = c * math.sqrt(
                math.log(total_visits) / child.visits
            )

            ucb_score = average_utility + exploration_bonus

            if ucb_score > best_score:
                best_score = ucb_score
                best_node = child

        if best_node is None:
            raise ValueError("Nie można wybrać dziecka: węzeł nie ma dzieci")

        return best_node

class MonteCarloTreeSearch:
    """MCTS holds one game state and performs another action on it."""

    def __init__(self, map_path: str | Path) -> None:
        self.env = MiniDungeon(map_path)
        self.root = Node(self.env.clone(), None, None)
        # slad faktycznie odegranej partii - akcje z rollout-ow tu nie trafiaja
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

    def search(self, persona: str, iterations: int, seed: int = 0) -> Action | None:
        rng = random.Random(seed)
        for _ in range(iterations):
            node = self.root
            # 1. selekcja: schodz po UCB1, poki wezel jest w pelni rozwiniety
            while not node.untried and node.children:
                node = node.best_child()
            # 2. ekspansja: jesli jest co rozwijac i gra sie nie skonczyla
            if node.untried and not node.env.done:
                node = node.expand(rng)
            # 3. symulacja (tutaj interesuje nas tylko utility)
            value = self.rollout(node.env, persona, rng)
            # 4. propagacja
            self.backpropagate(node, value)
        # decyzja: najlepsza SREDNIA, bez czlonu eksploracyjnego
        return max(
            self.root.children.values(),
            key=lambda n: n.total_utility / n.visits,
        ).action

    def rollout(
        self, env: MiniDungeon, persona: str, rng: random.Random, depth: int = 10
    ) -> float:
        # gramy na kopii - stan wezla zostaje zamrozony
        sim = env.clone()
        for _ in range(depth):
            legal = sim.legal_actions()
            if not legal:  # smierc albo wyjscie - koniec wczesniej
                break
            sim.step(rng.choice(legal))
        return utility(persona, sim)

    def backpropagate(self, node: Node, value: float) -> None:
        # razem z korzeniem - jego visits to licznik "t" w UCB1 dzieci
        current: Node | None = node
        while current is not None:
            current.visits += 1
            current.total_utility += value
            current = current.parent

    def play_single_tree(
        self,
        persona: str,
        time_limit_s: float = 300.0,
        seed: int = 0,
    ) -> dict[str, int | float | bool]:
        """Protokol z artykulu: jedno drzewo na mape, budowane do znalezienia
        wygrywajacego wezla albo timeoutu; potem odegranie najlepszej sekwencji.

        Zwyciestwo osiagniete tylko podczas rollout-u wplywa na backpropagation
        przez utility, ale losowe akcje symulacji nie staja sie sekwencja do
        odegrania - do zakonczenia szukania potrzebny jest terminalny wezel
        drzewa (polityka "tree_terminal_only").
        """

        rng = random.Random(seed)
        deadline = time.perf_counter() + time_limit_s
        winning_actions: list[Action] | None = None
        iterations = 0
        while time.perf_counter() < deadline:
            iterations += 1
            node = self.root
            while not node.untried and node.children:
                node = node.best_child()
            if node.untried and not node.env.done:
                node = node.expand(rng)
            self.backpropagate(node, self.rollout(node.env, persona, rng))
            # zwyciestwo w terminalnym wezle drzewa
            if node.env.done and node.env.metrics.reached_exit:
                winning_actions = self._path_to(node)
                break
        # rozroznienie sladu: wygrana z drzewa czy zachlanny fallback
        self.from_tree = winning_actions is not None
        if winning_actions is None:
            winning_actions = self._greedy_sequence()
        for action in winning_actions:
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

    def _greedy_sequence(self) -> list[Action]:
        # brak wygranej w budzecie czasu - zachlannie po najwyzszej sredniej utility
        actions: list[Action] = []
        node = self.root
        while node.children:
            node = max(node.children.values(), key=lambda n: n.total_utility / n.visits)
            actions.append(node.action)
        return actions

