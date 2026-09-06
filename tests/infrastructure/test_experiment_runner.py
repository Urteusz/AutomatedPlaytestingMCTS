from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from src.minidungeons.infrastructure.experiment_runner import (
    CsvSchema,
    durable_writer,
    load_results,
    mean_with_ci95,
    needs_header,
    run_in_pool,
)

SCHEMA = CsvSchema(
    fields=("persona", "map", "trial", "win", "score"),
    key=("persona", "map", "trial"),
    integers=frozenset({"trial", "win"}),
    floats=frozenset({"score"}),
)


def square_task(persona: str, number: int) -> dict[str, object]:
    """Zadanie puli musi byc importowalne z poziomu modulu (pickle)."""

    return {"persona": persona, "value": number * number}


class CsvSchemaTests(unittest.TestCase):
    def test_normalize_restores_the_types_returned_by_the_task(self) -> None:
        raw = {"persona": "runner", "map": "map01", "trial": "3", "win": "1", "score": "0.25"}

        row = SCHEMA.normalize(raw)

        self.assertEqual(
            {"persona": "runner", "map": "map01", "trial": 3, "win": 1, "score": 0.25},
            row,
        )
        self.assertIsInstance(row["trial"], int)
        self.assertIsInstance(row["score"], float)

    def test_row_key_uses_only_the_key_columns(self) -> None:
        row = {"persona": "runner", "map": "map01", "trial": 3, "win": 1, "score": 0.25}

        self.assertEqual(("runner", "map01", 3), SCHEMA.row_key(row))

    def test_incomplete_row_names_the_missing_columns(self) -> None:
        raw = {"persona": "runner", "map": "map01", "trial": "3", "win": "", "score": "0.25"}

        with self.assertRaises(ValueError) as caught:
            SCHEMA.normalize(raw)

        self.assertIn("win", str(caught.exception))


class ResultLogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.path = Path(self.temp_directory.name) / "results.csv"

    def write(self, *rows: dict[str, object]) -> None:
        with self.path.open("w", newline="", encoding="utf-8") as handle:
            append = durable_writer(handle, SCHEMA, write_header=True)
            for row in rows:
                append(row)

    def test_round_trip_through_the_csv_keeps_keys_and_types(self) -> None:
        row = {"persona": "runner", "map": "map01", "trial": 0, "win": 1, "score": 0.5}
        self.write(row)

        results = load_results(self.path, SCHEMA)

        self.assertEqual({("runner", "map01", 0): row}, results)

    def test_missing_or_empty_file_resumes_from_scratch(self) -> None:
        self.assertEqual({}, load_results(self.path, SCHEMA))
        self.path.write_text("", encoding="utf-8")
        self.assertEqual({}, load_results(self.path, SCHEMA))

    def test_foreign_header_is_rejected_instead_of_silently_appending(self) -> None:
        self.path.write_text("zupelnie,inne,kolumny\n1,2,3\n", encoding="utf-8")

        with self.assertRaises(ValueError) as caught:
            load_results(self.path, SCHEMA)

        self.assertIn("niezgodny naglowek", str(caught.exception))

    def test_needs_header_distinguishes_fresh_file_from_resume(self) -> None:
        self.assertTrue(needs_header(self.path, restart=False))  # nie istnieje
        self.write({"persona": "runner", "map": "map01", "trial": 0, "win": 1, "score": 0.5})
        self.assertFalse(needs_header(self.path, restart=False))  # dopisujemy
        self.assertTrue(needs_header(self.path, restart=True))  # --restart


class PoolTests(unittest.TestCase):
    def test_every_task_is_run_exactly_once_and_reported(self) -> None:
        collected: list[dict[str, object]] = []
        tasks = [("runner", number) for number in range(6)]

        interrupted = run_in_pool(
            square_task, tasks, workers=2, on_result=collected.append
        )

        self.assertFalse(interrupted)
        self.assertEqual({0, 1, 4, 9, 16, 25}, {row["value"] for row in collected})
        self.assertEqual(6, len(collected))

    def test_empty_task_list_is_a_no_op(self) -> None:
        collected: list[dict[str, object]] = []

        interrupted = run_in_pool(square_task, [], workers=2, on_result=collected.append)

        self.assertFalse(interrupted)
        self.assertEqual([], collected)


class StatisticsTests(unittest.TestCase):
    def test_constant_sample_has_no_confidence_interval(self) -> None:
        self.assertEqual((0.25, 0.0), mean_with_ci95([0.25, 0.25, 0.25, 0.25]))

    def test_single_observation_reports_mean_without_an_interval(self) -> None:
        self.assertEqual((2.0, 0.0), mean_with_ci95([2.0]))


if __name__ == "__main__":
    unittest.main()
