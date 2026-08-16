"""Slady partii i agregacja pod heatmape."""

import tempfile
import unittest
from pathlib import Path

from src.minidungeons.infrastructure.traces import (
    average_visits,
    cell_counts,
    load_traces,
    mean_visits,
    paths_by_persona,
    trace_path_for,
    trace_record,
    write_trace,
)


class TracePathTests(unittest.TestCase):
    def test_sidecar_sits_next_to_the_csv(self):
        self.assertEqual(
            Path("data/results/ucb1_pe_paths.jsonl"),
            trace_path_for("data/results/ucb1_pe.csv"),
        )


class TraceRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "slady.jsonl"

    def write(self, records):
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                write_trace(handle, record)

    def test_record_survives_round_trip_with_tuple_path(self):
        self.write([
            trace_record(
                persona="runner", map_name="map01", trial=0,
                actions=["move:E", "move:S"], path=[(1, 4), (1, 5)], from_tree=True,
            )
        ])
        loaded = load_traces(self.path)
        self.assertEqual(1, len(loaded))
        self.assertEqual([(1, 4), (1, 5)], loaded[0]["path"])
        self.assertEqual(["move:E", "move:S"], loaded[0]["actions"])
        self.assertTrue(loaded[0]["from_tree"])

    def test_repeated_key_keeps_the_last_entry(self):
        """Slad idzie na disk przed wierszem CSV, wiec przy wznowieniu po Ctrl+C
        ta sama proba moze byc zapisana dwa razy."""

        base = dict(persona="runner", map_name="map01", trial=7, from_tree=False)
        self.write([
            trace_record(**base, actions=["move:E"], path=[(0, 0)]),
            trace_record(**base, actions=["move:W"], path=[(9, 9)]),
        ])
        loaded = load_traces(self.path)
        self.assertEqual(1, len(loaded))
        self.assertEqual([(9, 9)], loaded[0]["path"])

    def test_missing_file_is_an_error_not_an_empty_list(self):
        with self.assertRaises(FileNotFoundError):
            load_traces(Path(self.directory.name) / "nie-ma.jsonl")

    def test_broken_line_names_its_number(self):
        self.write([
            trace_record(
                persona="runner", map_name="map01", trial=0,
                actions=[], path=[(0, 0)], from_tree=False,
            )
        ])
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write("nie-json\n")
        with self.assertRaises(ValueError) as caught:
            load_traces(self.path)
        self.assertIn("linia 2", str(caught.exception))

    def test_truncated_record_is_reported_not_a_bare_keyerror(self):
        """Proces ubity w trakcie zapisu zostawia ogon, ktory bywa poprawnym
        JSON-em bez czesci pol."""

        self.path.write_text('{"persona": "runner", "map": "map01"}\n', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            load_traces(self.path)
        self.assertIn("linia 1", str(caught.exception))


class GroupingTests(unittest.TestCase):
    def records(self):
        return [
            {"persona": "runner", "map": "map01", "trial": 0, "path": [(0, 0), (0, 1)]},
            {"persona": "runner", "map": "map02", "trial": 0, "path": [(5, 5)]},
            {"persona": "completionist", "map": "map01", "trial": 0, "path": [(0, 1)]},
        ]

    def test_map_filter_keeps_tiles_from_one_map_only(self):
        grouped = paths_by_persona(self.records(), map_name="map01")
        self.assertEqual({"runner", "completionist"}, set(grouped))
        self.assertEqual([[(0, 0), (0, 1)]], grouped["runner"])

    def test_without_filter_all_maps_land_in_one_bucket(self):
        grouped = paths_by_persona(self.records())
        self.assertEqual(2, len(grouped["runner"]))


class VisitCountTests(unittest.TestCase):
    def test_revisit_in_one_game_counts_twice(self):
        self.assertEqual({(0, 0): 2, (0, 1): 1}, cell_counts([[(0, 0), (0, 1), (0, 0)]]))

    def test_mean_is_per_game_not_per_step(self):
        # dwie partie: kafel (0,0) odwiedzony 2x i 1x -> 1,5 na partie
        heat = mean_visits([[(0, 0), (0, 1), (0, 0)], [(0, 0)]])
        self.assertAlmostEqual(1.5, heat[(0, 0)])
        self.assertAlmostEqual(0.5, heat[(0, 1)])

    def test_no_paths_gives_no_heat_instead_of_dividing_by_zero(self):
        self.assertEqual({}, mean_visits([]))


class AverageVisitTests(unittest.TestCase):
    def test_each_persona_weighs_the_same_regardless_of_game_count(self):
        """Runner ma tu jedna partie, completionist trzy. Srednia srednich musi
        dac 0,5 na kaflu odwiedzanym tylko przez runnera - przy zwyklym scalaniu
        sciezek wyszloby 0,25."""

        heat = average_visits({
            "runner": [[(0, 0)]],
            "completionist": [[(1, 1)], [(1, 1)], [(1, 1)]],
        })
        self.assertAlmostEqual(0.5, heat[(0, 0)])
        self.assertAlmostEqual(0.5, heat[(1, 1)])

    def test_persona_without_games_does_not_pull_the_average_down(self):
        heat = average_visits({"runner": [[(0, 0)]], "treasure_collector": []})
        self.assertAlmostEqual(1.0, heat[(0, 0)])

    def test_no_persona_with_games_gives_no_heat(self):
        self.assertEqual({}, average_visits({"runner": [], "completionist": []}))


if __name__ == "__main__":
    unittest.main()
