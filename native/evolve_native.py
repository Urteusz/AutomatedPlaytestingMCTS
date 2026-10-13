"""Ewolucja GP na natywnym silniku - te same argumenty co `cli/evolve.py`.

Podmieniamy wylacznie funkcje oceny partii; caly protokol GP (wyspy, elityzm,
mutacja, wybor runu) zostaje pythonowy i nietkniety. `run_in_pool` pickluje
funkcje przez referencje, a `sys.path` dziedziczy sie do workerow, wiec
kazdy worker zaimportuje ten sam `mdnative`.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import mdnative  # noqa: E402

import minidungeons.cli.evolve as evolve_cli  # noqa: E402

evolve_cli.evaluate_playthrough = mdnative.evaluate_playthrough

if __name__ == "__main__":
    evolve_cli.main()
