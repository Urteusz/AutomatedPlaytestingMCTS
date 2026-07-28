from __future__ import annotations

import csv
import io
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.minidungeons.cli.mcts_experiment import mean_with_ci95, summarize
from src.minidungeons.infrastructure.paths import PROJECT_ROOT


class MctsExperimentResumeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.output = Path(self.temp_directory.name) / "resume.csv"

    def run_experiment(self, trials: int, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "src.minidungeons.cli.mcts_experiment",
                "--trials",
                str(trials),
                "--time-limit",
                "0",
                "--workers",
                "1",
                "--personas",
                "runner",
                "--maps",
                "map01",
                "--out",
                str(self.output),
                *extra_args,
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def read_rows(self) -> list[dict[str, str]]:
        with self.output.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_existing_trials_are_kept_and_only_missing_trials_are_run(self) -> None:
        first = self.run_experiment(1)
        resumed = self.run_experiment(2)
        complete = self.run_experiment(2)

        self.assertIn("zapisane=0, pozostalo=1", first.stdout)
        self.assertIn("zapisane=1, pozostalo=1", resumed.stdout)
        self.assertIn("zapisane=2, pozostalo=0", complete.stdout)
        rows = self.read_rows()
        self.assertEqual(2, len(rows))
        self.assertEqual({"0", "1"}, {row["trial"] for row in rows})

    def test_restart_discards_previous_progress(self) -> None:
        self.run_experiment(2)
        restarted = self.run_experiment(1, "--restart")

        self.assertIn("zapisane=0, pozostalo=1", restarted.stdout)
        rows = self.read_rows()
        self.assertEqual(1, len(rows))
        self.assertEqual("0", rows[0]["trial"])

    def test_report_only_prints_table_without_running_new_trials(self) -> None:
        self.run_experiment(2)
        rows_before = self.read_rows()

        report = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.minidungeons.cli.mcts_experiment",
                "--report-only",
                "--out",
                str(self.output),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("Wczytano 2 prob z:", report.stdout)
        self.assertIn("TABELA II", report.stdout)
        self.assertEqual(rows_before, self.read_rows())

    def test_report_only_rejects_missing_results_file(self) -> None:
        missing = Path(self.temp_directory.name) / "nie-ma-takiego.csv"

        report = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.minidungeons.cli.mcts_experiment",
                "--report-only",
                "--out",
                str(missing),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertNotEqual(0, report.returncode)
        self.assertIn("nie znaleziono pliku z wynikami", report.stderr)


class Ucb1ReportTests(unittest.TestCase):
    """Testy tabeli podsumowujacej, przeniesione z osobnego skryptu raportu."""

    def test_mean_with_ci95_for_constant_sample(self) -> None:
        self.assertEqual((0.25, 0.0), mean_with_ci95([0.25, 0.25, 0.25, 0.25]))

    def test_summary_uses_the_table_ii_layout(self) -> None:
        rows: list[dict[str, object]] = []
        for persona in ("runner", "monster_killer", "treasure_collector", "completionist"):
            rows.append(
                {
                    "persona": persona,
                    "monster_ratio": 0.25,
                    "potion_ratio": 0.05,
                    "treasure_ratio": 0.1,
                    "interactive_ratio": 0.2,
                    "win": 1,
                    "time_sec": 12.0,
                }
            )

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            summarize(rows)
        output = buffer.getvalue()

        self.assertIn("TABELA II (średnia ± 95% CI)", output)
        self.assertIn("Metric", output)
        self.assertIn("MK", output)
        self.assertIn("TC", output)
        self.assertIn("Interactive Objects", output)
        self.assertIn("25% ± 0%", output)
        self.assertIn("12 ± 0", output)
        self.assertIn("Liczba prób (n)", output)


if __name__ == "__main__":
    unittest.main()
