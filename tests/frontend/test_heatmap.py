"""Logika podgladu heatmap: skale, metryki person i skladanie warstwy cieplnej.

Rysowanie nie jest tu testowane - wymagaloby okna. Testowane jest wszystko, co
decyduje o liczbach na ekranie, bo to one ida potem do pracy.
"""

import csv
import tempfile
import unittest
from pathlib import Path

try:
    from src.minidungeons.frontend import heatmap
except SystemExit:  # brak pygame-ce, czyli brak extras "gui"
    heatmap = None


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class OutcomeLoadingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "wyniki.csv"

    def write_csv(self, rows):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["persona", "map", "trial", "win"])
            writer.writeheader()
            writer.writerows(rows)

    def test_win_column_becomes_a_bool_keyed_by_trial(self):
        self.write_csv([
            {"persona": "runner", "map": "map01", "trial": "0", "win": "1"},
            {"persona": "runner", "map": "map01", "trial": "1", "win": "0"},
        ])
        outcomes = heatmap.load_outcomes(self.path)
        self.assertTrue(outcomes[("runner", "map01", 0)])
        self.assertFalse(outcomes[("runner", "map01", 1)])

    def test_missing_csv_leaves_the_metrics_empty_instead_of_crashing(self):
        missing = Path(self.directory.name) / "nie-ma.csv"
        self.assertEqual({}, heatmap.load_outcomes(missing))
        self.assertEqual([], heatmap.load_rows(missing))


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class SelectionTests(unittest.TestCase):
    def dataset(self):
        records = [
            {"persona": "runner", "map": "map01", "trial": 0, "path": [(0, 0), (0, 1)]},
            {"persona": "runner", "map": "map01", "trial": 1, "path": [(0, 0)]},
            {"persona": "completionist", "map": "map01", "trial": 0, "path": [(2, 2)]},
            {"persona": "runner", "map": "map02", "trial": 0, "path": [(9, 9)]},
        ]
        won = {
            ("runner", "map01", 0): True,
            ("runner", "map01", 1): False,
            ("completionist", "map01", 0): False,
            ("runner", "map02", 0): True,
        }
        return heatmap.Dataset(Path("wyniki.csv"), records, won)

    def test_single_persona_averages_over_its_own_games(self):
        heat, games = heatmap.selected_paths(self.dataset(), "map01", "runner")
        self.assertEqual(2, games)
        self.assertAlmostEqual(1.0, heat[(0, 0)])
        self.assertAlmostEqual(0.5, heat[(0, 1)])

    def test_other_maps_do_not_leak_in(self):
        heat, _ = heatmap.selected_paths(self.dataset(), "map01", "runner")
        self.assertNotIn((9, 9), heat)

    def test_persona_without_games_on_this_map_gives_empty_heat(self):
        heat, games = heatmap.selected_paths(self.dataset(), "map02", "completionist")
        self.assertEqual(0, games)
        self.assertEqual({}, heat)

    def test_all_personas_view_weighs_personas_equally(self):
        heat, games = heatmap.selected_paths(self.dataset(), "map01", heatmap.ALL_PERSONAS)
        self.assertEqual(3, games)
        self.assertAlmostEqual(0.5, heat[(0, 0)])  # runner 1,0 / completionist 0
        self.assertAlmostEqual(0.5, heat[(2, 2)])  # completionist 1,0 / runner 0

    def test_win_rate_reads_from_the_csv(self):
        dataset = self.dataset()
        self.assertAlmostEqual(0.5, heatmap.win_rate(dataset, "map01", "runner"))
        self.assertAlmostEqual(1.0, heatmap.win_rate(dataset, "map02", "runner"))
        self.assertIsNone(heatmap.win_rate(dataset, "map07", "runner"))

    def test_win_rate_over_all_personas_covers_every_row_of_the_map(self):
        # runner 1/2 + completionist 0/1 -> 1 wygrana na 3 partie
        self.assertAlmostEqual(1 / 3, heatmap.win_rate(self.dataset(), "map01", heatmap.ALL_PERSONAS))


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class ScaleTests(unittest.TestCase):
    def test_linear_scale_is_a_plain_fraction_of_the_peak(self):
        self.assertAlmostEqual(0.25, heatmap.normalized(0.5, 2.0, "liniowa"))

    def test_sqrt_and_log_lift_rarely_visited_tiles(self):
        low = heatmap.normalized(0.05, 2.0, "liniowa")
        self.assertGreater(heatmap.normalized(0.05, 2.0, "sqrt"), low)
        self.assertGreater(heatmap.normalized(0.05, 2.0, "log"), low)

    def test_every_scale_maps_the_peak_to_one(self):
        for scale in heatmap.SCALES:
            self.assertAlmostEqual(1.0, heatmap.normalized(2.0, 2.0, scale), msg=scale)

    def test_empty_heat_does_not_divide_by_zero(self):
        self.assertEqual(0.0, heatmap.normalized(0.0, 0.0, "liniowa"))


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class ColorTests(unittest.TestCase):
    def test_ends_of_the_ramp_match_the_declared_stops(self):
        self.assertEqual(heatmap.HEAT_STOPS[0][1], heatmap.heat_color(0.0))
        self.assertEqual(heatmap.HEAT_STOPS[-1][1], heatmap.heat_color(1.0))

    def test_values_outside_the_range_are_clamped(self):
        self.assertEqual(heatmap.heat_color(0.0), heatmap.heat_color(-5.0))
        self.assertEqual(heatmap.heat_color(1.0), heatmap.heat_color(9.0))

    @staticmethod
    def luminance(color):
        red, green, blue = color
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue

    def test_ramp_gets_darker_all_the_way_up(self):
        """Wymog skali sekwencyjnej: jasnosc maleje monotonicznie. To ona, a nie
        odcien, koduje wielkosc - dlatego skala jest jednobarwna."""

        levels = [self.luminance(heat_color) for _, heat_color in heatmap.HEAT_STOPS]
        self.assertEqual(levels, sorted(levels, reverse=True))

    def test_ramp_is_one_hue(self):
        """Czerwony musi byc dominujacy w kazdym kroku, a zielony i niebieski
        rowne sobie z dokladnoscia do kilku poziomow - inaczej rampa skreca
        w inny odcien i zaczyna sugerowac kategorie."""

        for _, (red, green, blue) in heatmap.HEAT_STOPS:
            self.assertGreater(red, green)
            self.assertGreater(red, blue)
            self.assertLess(abs(green - blue), 10)

    def test_full_range_of_the_ramp_is_used(self):
        self.assertAlmostEqual(0.0, heatmap.HEAT_STOPS[0][0])
        self.assertAlmostEqual(1.0, heatmap.HEAT_STOPS[-1][0])

    def test_every_declared_stop_is_hit_exactly(self):
        for position, color in heatmap.HEAT_STOPS:
            self.assertEqual(color, heatmap.heat_color(position), msg=str(position))

    def test_between_two_stops_the_ramp_is_linear(self):
        (low, low_color), (high, high_color) = heatmap.HEAT_STOPS[0], heatmap.HEAT_STOPS[1]
        middle = heatmap.heat_color((low + high) / 2)
        for channel, (start, end) in enumerate(zip(low_color, high_color)):
            self.assertAlmostEqual((start + end) / 2, middle[channel], delta=1)

    def test_ramp_has_no_flat_stretch(self):
        colors = [heatmap.heat_color(step / 20) for step in range(21)]
        self.assertEqual(len(colors), len(set(colors)))


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class StatsTableTests(unittest.TestCase):
    """Tabela metryk zastapila zakladki person, wiec musi zawierac je wszystkie."""

    def dataset(self, rows):
        records = [{"persona": "runner", "map": "map01", "trial": 0, "path": [(0, 0)]}]
        return heatmap.Dataset(Path("wyniki.csv"), records, {}, rows)

    def row(self, persona, **values):
        base = {"persona": persona, "map": "map01", "monster_ratio": "0.5",
                "potion_ratio": "0.25", "treasure_ratio": "0", "interactive_ratio": "0.4",
                "health_left": "8", "turns": "20"}
        return {**base, **values}

    def test_every_persona_and_the_average_have_a_row(self):
        self.assertEqual(len(heatmap.PERSONA_ROWS), len(heatmap.PERSONA_CHOICES))
        for persona in heatmap.PERSONA_CHOICES:
            self.assertIn(persona, heatmap.PERSONA_ROW_LABEL)
            self.assertIn(persona, heatmap.PERSONA_LABEL)
        self.assertEqual(heatmap.ALL_PERSONAS, heatmap.PERSONA_ROWS[-1])

    def test_metrics_are_averaged_per_persona_and_over_all_of_them(self):
        dataset = self.dataset([
            self.row("runner", monster_ratio="0.2"),
            self.row("runner", monster_ratio="0.4"),
            self.row("completionist", monster_ratio="0.9"),
        ])
        self.assertAlmostEqual(0.3, dataset.stats[("map01", "runner")]["monster_ratio"])
        self.assertAlmostEqual(0.9, dataset.stats[("map01", "completionist")]["monster_ratio"])
        self.assertAlmostEqual(0.5, dataset.stats[("map01", heatmap.ALL_PERSONAS)]["monster_ratio"])

    def test_row_without_csv_shows_dashes_instead_of_crashing(self):
        cells = heatmap.stat_text(self.dataset([]), "map01", "runner")
        self.assertEqual(["-"] * (1 + len(heatmap.STAT_COLUMNS)), cells)

    def test_row_formats_ratios_as_percent_and_counts_as_numbers(self):
        dataset = self.dataset([self.row("runner")])
        cells = heatmap.stat_text(dataset, "map01", "runner")
        self.assertEqual("-", cells[0])  # brak win w tym CSV
        self.assertEqual(["50%", "25%", "0%", "40%", "8.0", "20.0"], cells[1:])

    def test_older_csv_without_a_metric_column_is_tolerated(self):
        row = self.row("runner")
        del row["turns"]
        stats = self.dataset([row]).stats[("map01", "runner")]
        self.assertAlmostEqual(0.0, stats["turns"])


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class HudFitTests(unittest.TestCase):
    """Teksty HUD musza sie miescic w najwezszym oknie - ucietej podpowiedzi nie
    widac w zadnym tescie logiki, tylko na ekranie."""

    @classmethod
    def setUpClass(cls):
        import pygame

        # sam modul czcionek, bez pygame.init() - pomiar tekstu nie potrzebuje
        # okna ani audio, a pelna inicjalizacja kosztuje kilka sekund na test
        pygame.font.init()

    def test_hint_fits_the_narrowest_window(self):
        width = heatmap.board.font(18).size(heatmap.HINT)[0]
        self.assertLess(width, heatmap.MIN_WINDOW_WIDTH - 10, msg=heatmap.HINT)

    def test_stats_table_fits_the_narrowest_window(self):
        right_edge = 10 + heatmap.STAT_NAME_WIDTH + (1 + len(heatmap.STAT_COLUMNS)) * heatmap.STAT_COLUMN_WIDTH
        self.assertLessEqual(right_edge, heatmap.MIN_WINDOW_WIDTH - 10)

    def test_persona_labels_fit_the_name_column(self):
        for persona, label in heatmap.PERSONA_ROW_LABEL.items():
            width = heatmap.board.font(18).size(label + " <")[0]
            self.assertLess(width, heatmap.STAT_NAME_WIDTH, msg=persona)

    def test_hud_height_covers_every_line_it_draws(self):
        table_bottom = 82 + (len(heatmap.PERSONA_ROWS) + 1) * heatmap.STAT_LINE_HEIGHT
        last_line = 6 + table_bottom + 6 + 18
        self.assertLessEqual(last_line, heatmap.HUD_HEIGHT)


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class HoverTests(unittest.TestCase):
    """Kursor nad sciana ma nie dawac ani obwodki, ani wpisu w HUD."""

    @classmethod
    def setUpClass(cls):
        from src.minidungeons.domain import MiniDungeon
        from src.minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR

        cls.env = MiniDungeon(MD2_BENCHMARK_DIR / "map02.txt")

    def pixel(self, cell):
        return heatmap.board.cell_rect(cell).center

    def test_floor_tile_is_reported(self):
        self.assertEqual(".", self.env.terrain[18][1])
        self.assertEqual((18, 1), heatmap.hovered_cell(self.pixel((18, 1)), self.env))

    def test_wall_tile_is_not_reported(self):
        self.assertEqual("#", self.env.terrain[11][2])
        self.assertIsNone(heatmap.hovered_cell(self.pixel((11, 2)), self.env))

    def test_every_wall_of_the_map_is_ignored(self):
        for row in range(self.env.height):
            for column in range(self.env.width):
                expected = None if self.env.terrain[row][column] == "#" else (row, column)
                self.assertEqual(
                    expected,
                    heatmap.hovered_cell(self.pixel((row, column)), self.env),
                    msg=f"({row}, {column})",
                )

    def test_hud_area_below_the_board_is_not_a_tile(self):
        below = (10, heatmap.board.block_max_size * self.env.height + 20)
        self.assertIsNone(heatmap.hovered_cell(below, self.env))


@unittest.skipIf(heatmap is None, "wymaga pygame-ce (pip install -e .[gui])")
class MapSelectionTests(unittest.TestCase):
    def view(self, count=3):
        records = [{"persona": "runner", "map": f"map{index + 1:02d}", "trial": 0, "path": [(0, 0)]}
                   for index in range(count)]
        return heatmap.View(heatmap.Dataset(Path("a.csv"), records, {}))

    def test_default_view_shows_the_first_map_and_the_average(self):
        view = self.view()
        self.assertEqual("map01", view.map_name)
        self.assertEqual(heatmap.ALL_PERSONAS, view.persona)

    def test_number_key_picks_the_map_at_that_index(self):
        view = self.view()
        self.assertTrue(view.select_map(2))
        self.assertEqual("map03", view.map_name)

    def test_key_beyond_the_available_maps_changes_nothing(self):
        view = self.view()
        view.select_map(1)
        self.assertFalse(view.select_map(7))
        self.assertEqual("map02", view.map_name)

    def test_keys_cover_all_eleven_benchmark_maps(self):
        """1-9, 0 i minus to 11 pozycji - dokladnie tyle, ile map w benchmarku."""

        indexes = sorted(set(heatmap.MAP_KEYS.values()))
        self.assertEqual(list(range(11)), indexes)

    def test_top_row_and_keypad_hit_the_same_maps(self):
        import pygame

        for row_key, pad_key in ((pygame.K_1, pygame.K_KP1), (pygame.K_0, pygame.K_KP0),
                                 (pygame.K_MINUS, pygame.K_KP_MINUS)):
            self.assertEqual(heatmap.MAP_KEYS[row_key], heatmap.MAP_KEYS[pad_key])


if __name__ == "__main__":
    unittest.main()
