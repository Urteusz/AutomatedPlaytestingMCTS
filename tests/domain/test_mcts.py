from pathlib import Path
import math
import random
import tempfile
import unittest
from unittest.mock import patch

from src.minidungeons.domain import Action, MiniDungeon
from src.minidungeons.domain.mcts import MonteCarloTreeSearch, Node, TreeSpec
from src.minidungeons.domain.selection_policy import EvolvedPolicy, UCB1Policy
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

    def test_best_child_uses_parent_visits_as_t(self) -> None:
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

        # t w UCB1 to licznik odwiedzin rodzica; w spojnym drzewie zachodzi
        # parent.visits == 1 + sum(n_i), bo rodzic ma tez wlasne odwiedzenie.
        parent.visits = 1 + exploit.visits + explore.visits
        t = parent.visits
        exploit_score = 0.5 + math.sqrt(2) * math.sqrt(math.log(t) / 100)
        explore_score = math.sqrt(2) * math.sqrt(math.log(t) / 20)

        self.assertGreater(exploit_score, explore_score)
        self.assertIs(exploit, parent.best_child(UCB1Policy()))

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

        value, terminals = agent.rollout(agent.env, "runner", PreferEastRandom(), depth=10)
        self.assertIsNone(terminals)  # UCB1 nie zbiera zmiennych Tabeli I

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

    def test_single_tree_falls_back_to_best_discovered_sequence_on_timeout(self) -> None:
        """Bez terminalnego wezla z wyjsciem szukanie nie moze zglosic wygranej.

        Rollout zwraca tylko utility, wiec zwyciestwo napotkane w losowej
        symulacji nie staje sie sekwencja do odegrania - zostaje "best sequence
        of actions it discovered" (sekcja V artykulu). Runner z binarnym PE nie
        zyskuje niczym poza wyjsciem, a kazdy krok kosztuje 0,01, wiec
        najlepszym odkrytym stanem jest sam korzen: agent stoi.
        """

        map_path = self.make_map("#####", "#E.X#", "#####")
        agent = MonteCarloTreeSearch(map_path)

        with (
            patch.object(agent, "rollout", return_value=(0.0, None)),
            patch(
                "src.minidungeons.domain.mcts.time.perf_counter",
                side_effect=[0.0, 0.0, 2.0],
            ),
        ):
            result = agent.play_single_tree("runner", time_limit_s=1.0, seed=0)

        self.assertEqual(1, result["iterations"])
        self.assertFalse(result["reached_exit"])
        self.assertEqual(0, result["steps"])

    def test_best_discovered_sequence_reaches_a_deep_high_utility_node(self) -> None:
        """Regresja na defekt zmierzony w pelnym przebiegu: zejscie zachlanne po
        `mean_utility` dziecka trafialo w wezel z jednym szczesliwym rolloutem i
        urywalo sie na nim, wiec 181 z 250 partii fallbackowych odgrywalo jedna
        akcje. Teraz liczy sie uzytecznosc STANU wezla, wiec Treasure Collector
        idzie po skarb lezacy trzy kroki dalej, nawet gdy pierwszy krok wyglada
        w statystykach slabo.
        """

        # wyjscie zamurowane, wiec wygrana jest niemozliwa i partia MUSI przejsc
        # przez sekwencje awaryjna - inaczej test mierzylby zwykla wygrana
        map_path = self.make_map("#######", "#E..r#X", "#######")
        agent = MonteCarloTreeSearch(map_path)
        result = agent.play_single_tree("treasure_collector", time_limit_s=None,
                                        max_iterations=400, seed=0)

        self.assertFalse(result["reached_exit"])
        self.assertEqual(1.0, result["treasure_ratio"])  # skarb zabrany
        self.assertGreaterEqual(result["steps"], 3)

    def test_single_tree_stops_for_explicit_winning_tree_node(self) -> None:
        map_path = self.make_map("####", "#EX#", "####")
        agent = MonteCarloTreeSearch(map_path)

        result = agent.play_single_tree("runner", time_limit_s=1.0, seed=0)

        self.assertEqual(1, result["iterations"])
        self.assertTrue(result["reached_exit"])
        self.assertEqual(1, result["steps"])

    def test_exhausted_subtrees_stop_being_selected(self) -> None:
        """Polityka bez czlonu eksploracyjnego (eq. 6-9) nie odczepi sie sama od
        martwego liscia, wiec wyczerpanie musi byc jawnym znacznikiem."""

        env = MiniDungeon(self.make_map("####", "#EX#", "####"))
        parent = Node(env, None, None)
        child = parent.expand(random.Random(0))

        self.assertTrue(child.env.done)
        self.assertTrue(child.exhausted)  # terminalny lisc od razu wyczerpany
        self.assertNotIn(child, parent.viable_children())

        parent.untried.clear()
        parent.refresh_exhausted()
        self.assertTrue(parent.exhausted)  # wyczerpanie propaguje sie w gore

    def test_single_tree_stops_when_the_whole_tree_is_exhausted(self) -> None:
        map_path = self.make_map("####", "#EX#", "####")
        agent = MonteCarloTreeSearch(map_path)

        result = agent.play_single_tree("runner", time_limit_s=5.0, seed=0)

        # bez znacznika wyczerpania petla krecilaby sie do konca budzetu czasu
        self.assertLess(int(result["iterations"]), 10)
        self.assertTrue(result["reached_exit"])

    def test_search_returns_action_with_best_average_utility(self) -> None:
        agent = MonteCarloTreeSearch(
            self.make_map("#####", "#E.X#", "#####")
        )

        action = agent.search("runner", iterations=1, seed=0)

        self.assertEqual(Action.move("E"), action)


class SearchBudgetTests(unittest.TestCase):
    """Budzet iteracyjny - fitness GP musi byc odtwarzalny, a czas nim nie jest."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        # korytarz na 6 krokow: wygrywajacy wezel drzewa jest poza zasiegiem
        # kilku iteracji, wiec limit iteracji faktycznie ucina petle
        path = Path(self.temp_directory.name) / "corridor.txt"
        path.write_text("#########\n#E.....X#\n#########\n", encoding="utf-8")
        self.map_path = path

    def test_iteration_budget_caps_the_loop(self) -> None:
        agent = MonteCarloTreeSearch(self.map_path)

        result = agent.play_single_tree(
            "runner", time_limit_s=None, seed=0, max_iterations=5
        )

        self.assertEqual(5, result["iterations"])
        self.assertFalse(result["reached_exit"])

    def test_iteration_budget_is_reproducible(self) -> None:
        """To wlasnie odroznia budzet iteracyjny od czasowego - patrz
        docs/rules/decisions.md o determinizmie."""

        runs = [
            MonteCarloTreeSearch(self.map_path).play_single_tree(
                "runner", time_limit_s=None, seed=0, max_iterations=200
            )
            for _ in range(3)
        ]

        self.assertEqual(runs[0], runs[1])
        self.assertEqual(runs[1], runs[2])

    def test_whichever_budget_runs_out_first_stops_the_search(self) -> None:
        agent = MonteCarloTreeSearch(self.map_path)

        with patch(
            "src.minidungeons.domain.mcts.time.perf_counter",
            side_effect=[0.0, 0.0, 0.0, 9.0],
        ):
            result = agent.play_single_tree(
                "runner", time_limit_s=1.0, seed=0, max_iterations=1000
            )

        # czas skonczyl sie przed iteracjami, mimo hojnego max_iterations
        self.assertEqual(2, result["iterations"])

    def test_search_without_any_budget_is_rejected(self) -> None:
        agent = MonteCarloTreeSearch(self.map_path)

        with self.assertRaises(ValueError):
            agent.play_single_tree("runner", time_limit_s=None, seed=0)


class TreeSpecTests(unittest.TestCase):
    """Wezly nie znaja polityk - dostaja od nich tylko `TreeSpec`."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        path = Path(self.temp_directory.name) / "fixture.txt"
        path.write_text("#####\n#E.X#\n#####\n", encoding="utf-8")
        self.map_path = path

    def test_ucb1_does_not_pay_for_table_one_variables(self) -> None:
        agent = MonteCarloTreeSearch(self.map_path, policy=UCB1Policy())

        self.assertFalse(agent.spec.collect_terminals)
        self.assertIsNone(agent.root.terminal_sums)

    def test_evolved_policy_requirements_reach_the_nodes(self) -> None:
        policy = EvolvedPolicy("PE + Rbar", pe_mode="graded")
        agent = MonteCarloTreeSearch(self.map_path, policy=policy)

        self.assertEqual(
            TreeSpec(collect_terminals=True, pe_mode="graded"),
            agent.spec,
        )
        self.assertIsNotNone(agent.root.terminal_sums)

    def test_children_inherit_the_spec_of_their_parent(self) -> None:
        spec = TreeSpec(collect_terminals=True, pe_mode="graded")
        parent = Node(MiniDungeon(self.map_path), None, None, spec)

        child = parent.expand(random.Random(0))

        self.assertIs(spec, child.spec)
        self.assertIsNotNone(child.terminal_sums)


if __name__ == "__main__":
    unittest.main()
