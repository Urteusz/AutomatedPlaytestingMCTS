from pathlib import Path
import math
import random
import tempfile
import unittest
from unittest.mock import patch

from src.minidungeons.domain import Action, MiniDungeon
from src.minidungeons.domain.mcts import MonteCarloTreeSearch, Node
from src.minidungeons.domain.personas import utility


class PreferEastRandom:
    """Minimal deterministic choice policy for rollout reconstruction tests."""

    @staticmethod
    def choice(actions):
        return next(
            action
            for action in actions
            if action.kind == "move" and action.direction == "E"
        )


class MctsPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

    def make_map(self, *rows: str) -> Path:
        path = Path(self.temp_directory.name) / "fixture.txt"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def test_best_child_uses_sum_of_child_visits_as_t(self) -> None:
        env = MiniDungeon(self.make_map("#####", "#E.X#", "#####"))
        parent = Node(env, None, None)
        exploit = Node(env.clone(), parent, Action.move("E"))
        explore = Node(env.clone(), parent, Action.move("W"))
        exploit.visits, exploit.total_utility = 100, 50.0
        explore.visits, explore.total_utility = 20, 0.0
        parent.children = {
            exploit.action: exploit,
            explore.action: explore,
        }

        # Gdyby implementacja uzywala parent.visits zamiast sumy n_i,
        # ta sztucznie duza wartosc zmienilaby wybor na explore.
        parent.visits = 1_000_000_000
        t = exploit.visits + explore.visits
        exploit_score = 0.5 + math.sqrt(2) * math.sqrt(math.log(t) / 100)
        explore_score = math.sqrt(2) * math.sqrt(math.log(t) / 20)

        self.assertGreater(exploit_score, explore_score)
        self.assertIs(exploit, parent.best_child())

    def test_expansion_creates_one_child_without_mutating_parent_state(self) -> None:
        env = MiniDungeon(self.make_map("#####", "#E.X#", "#####"))
        parent = Node(env, None, None)
        parent_state = parent.env.state_key()
        original_actions = set(parent.untried)

        child = parent.expand(random.Random(0))

        self.assertIs(parent, child.parent)
        self.assertIs(child, parent.children[child.action])
        self.assertIn(child.action, original_actions)
        self.assertNotIn(child.action, parent.untried)
        self.assertEqual(parent_state, parent.env.state_key())
        self.assertNotEqual(parent.env.state_key(), child.env.state_key())
        self.assertEqual(0, child.visits)

    def test_rollout_leaves_node_unchanged_and_returns_persona_utility(self) -> None:
        map_path = self.make_map("#####", "#E.X#", "#####")
        agent = MonteCarloTreeSearch(map_path)
        node_state = agent.env.state_key()

        value = agent.rollout(agent.env, "runner", PreferEastRandom(), depth=10)

        self.assertEqual(node_state, agent.env.state_key())

        # PreferEastRandom jest deterministyczny, a MD2 nie ma losowosci,
        # wiec ten sam przebieg da sie odtworzyc z korzenia.
        replay = agent.env.clone()
        for _ in range(2):
            replay.step(Action.move("E"))
        self.assertTrue(replay.metrics.reached_exit)
        self.assertAlmostEqual(utility("runner", replay), value)

    def test_backpropagation_updates_every_ancestor_and_visit_invariants(self) -> None:
        map_path = self.make_map("#####", "#E.X#", "#####")
        agent = MonteCarloTreeSearch(map_path)
        root = agent.root
        child = root.expand(random.Random(0))

        agent.backpropagate(child, 0.25)

        self.assertEqual(1, root.visits)
        self.assertEqual(1, child.visits)
        self.assertAlmostEqual(0.25, root.total_utility)
        self.assertAlmostEqual(0.25, child.total_utility)
        self.assertEqual(root.visits, sum(node.visits for node in root.children.values()))
        self.assertEqual(
            child.visits,
            sum(node.visits for node in child.children.values()) + 1,
        )

        grandchild = child.expand(random.Random(0))
        agent.backpropagate(grandchild, -0.5)

        self.assertEqual(2, root.visits)
        self.assertEqual(2, child.visits)
        self.assertEqual(1, grandchild.visits)
        self.assertAlmostEqual(-0.25, root.total_utility)
        self.assertAlmostEqual(-0.25, child.total_utility)
        self.assertAlmostEqual(-0.5, grandchild.total_utility)
        self.assertEqual(root.visits, sum(node.visits for node in root.children.values()))
        self.assertEqual(
            child.visits,
            sum(node.visits for node in child.children.values()) + 1,
        )

    def test_single_tree_falls_back_to_greedy_sequence_on_timeout(self) -> None:
        """Bez terminalnego wezla z wyjsciem szukanie nie moze zglosic wygranej.

        Rollout zwraca tylko utility, wiec zwyciestwo napotkane w losowej
        symulacji nie staje sie sekwencja do odegrania - zostaje sciezka
        zachlanna po najwyzszej sredniej utility.
        """

        map_path = self.make_map("#####", "#E.X#", "#####")
        agent = MonteCarloTreeSearch(map_path)

        with (
            patch.object(agent, "rollout", return_value=0.0),
            patch(
                "src.minidungeons.domain.mcts.time.perf_counter",
                side_effect=[0.0, 0.0, 2.0],
            ),
        ):
            result = agent.play_single_tree("runner", time_limit_s=1.0, seed=0)

        self.assertEqual(1, result["iterations"])
        self.assertFalse(result["reached_exit"])
        self.assertEqual(1, result["steps"])

    def test_single_tree_stops_for_explicit_winning_tree_node(self) -> None:
        map_path = self.make_map("####", "#EX#", "####")
        agent = MonteCarloTreeSearch(map_path)

        result = agent.play_single_tree("runner", time_limit_s=1.0, seed=0)

        self.assertEqual(1, result["iterations"])
        self.assertTrue(result["reached_exit"])
        self.assertEqual(1, result["steps"])

    def test_search_returns_action_with_best_average_utility(self) -> None:
        agent = MonteCarloTreeSearch(
            self.make_map("#####", "#E.X#", "#####")
        )

        action = agent.search("runner", iterations=1, seed=0)

        self.assertEqual(Action.move("E"), action)


if __name__ == "__main__":
    unittest.main()
