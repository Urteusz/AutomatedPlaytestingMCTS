"""Ewolucja tree policy wedlug protokolu artykulu (sekcja VI-A).

Protokol: dla kazdej persony 3 niezalezne uruchomienia po 100 generacji,
populacja 100 osobnikow w 5 wyspach, fitness usredniany po 6 mapach
treningowych. Zwyciezcze uruchomienie wybiera sie po **glownej metryce
persony**, nie po fitnessie (`gp_fitness.CORE_METRIC`).

Ten modul odpowiada wylacznie za: argumenty, rozdzielenie fitnessu na procesy,
dziennik generacji i wybor formul. Operatory genetyczne siedza w
`domain/evolution.py`, definicja fitnessu w `domain/gp_fitness.py`, a wznawialny
zapis i pula procesow w `infrastructure/experiment_runner.py`.

Wznawianie dziala na poziomie **uruchomienia** (persona x run): ukonczone
uruchomienia zapisuja sie do JSON-a i po restarcie sa pomijane. Populacji w
trakcie generacji nie checkpointujemy - przerwane uruchomienie liczy sie od
poczatku.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Sequence

from minidungeons.domain.evolution import GenerationStats, evolve
from minidungeons.domain.expression import PE_MODES, Expr, size, to_infix
from minidungeons.domain.gp_fitness import (
    CORE_METRIC,
    TRAINING_MAP_NAMES,
    evaluate_playthrough,
)
from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.infrastructure.experiment_runner import (
    CsvSchema,
    Row,
    configure_parent_interrupts,
    durable_writer,
    needs_header,
    run_in_pool,
)
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR, PROJECT_ROOT

RESULTS_DIR = PROJECT_ROOT / "data" / "results"
DEFAULT_LOG = RESULTS_DIR / "gp_generations.csv"
DEFAULT_OUT = RESULTS_DIR / "gp_runs.json"
DEFAULT_POLICIES = PROJECT_ROOT / "data" / "rules" / "evolved_policies.json"

SCHEMA = CsvSchema(
    fields=(
        "persona", "run", "generation", "best_fitness", "mean_fitness",
        "unique", "size", "playthroughs", "seconds", "formula",
    ),
    key=("persona", "run", "generation"),
    integers=frozenset({"run", "generation", "unique", "size", "playthroughs"}),
    floats=frozenset({"best_fitness", "mean_fitness", "seconds"}),
)


# --- fitness na puli procesow -----------------------------------------------


class PooledFitness:
    """Fitness calej populacji naraz, liczony w puli procesow.

    Dwie oszczednosci, obie wynikajace z determinizmu silnika:

    * **deduplikacja w generacji** - elitaryzm i migracja przenosza te same
      chromosomy dalej, wiec populacja 100 osobnikow ma zwykle znacznie mniej
      unikalnych formul;
    * **cache miedzy generacjami** - para (formula, mapa, seed) wyznacza wynik
      jednoznacznie, wiec elita nigdy nie jest liczona drugi raz.
    """

    def __init__(
        self,
        persona: str,
        map_paths: Sequence[Path],
        *,
        seeds: Sequence[int],
        max_iterations: int,
        pe_mode: str,
        workers: int,
        utility_pe: str = "manhattan",
        ic_mode: str = "mean3",
        fallback: str = "visits",
    ) -> None:
        self.persona = persona
        self.map_paths = {path.stem: path for path in map_paths}
        self.seeds = tuple(seeds)
        self.max_iterations = max_iterations
        self.pe_mode = pe_mode
        self.utility_pe = utility_pe
        self.ic_mode = ic_mode
        self.fallback = fallback
        self.workers = workers
        self.utilities: dict[tuple[str, str, int], float] = {}
        self.cores: dict[tuple[str, str, int], float] = {}
        self.playthroughs = 0  # partie rozegrane w ostatniej generacji

    def _store(self, row: Row) -> None:
        key = (str(row["formula"]), str(row["map"]), int(row["seed"]))  # type: ignore[arg-type]
        self.utilities[key] = float(row["utility"])  # type: ignore[arg-type]
        self.cores[key] = float(row["core"])  # type: ignore[arg-type]

    def _missing(self, formulas: Sequence[str]) -> list[tuple[object, ...]]:
        tasks: list[tuple[object, ...]] = []
        seen: set[tuple[str, str, int]] = set()
        for formula in formulas:
            for map_name, map_path in self.map_paths.items():
                for seed in self.seeds:
                    key = (formula, map_name, seed)
                    if key in self.utilities or key in seen:
                        continue
                    seen.add(key)
                    tasks.append((
                        formula, self.persona, str(map_path), seed,
                        self.max_iterations, self.pe_mode,
                        self.utility_pe, self.ic_mode, self.fallback,
                    ))
        return tasks

    def _mean(self, table: dict[tuple[str, str, int], float], formula: str) -> float:
        values = [
            table[(formula, map_name, seed)]
            for map_name in self.map_paths
            for seed in self.seeds
        ]
        return sum(values) / len(values)

    def scores(self, population: Sequence[Expr]) -> list[float]:
        """`FitnessFn` dla `evolution.evolve` - wyzej znaczy lepiej."""

        formulas = [to_infix(tree) for tree in population]
        tasks = self._missing(formulas)
        self.playthroughs = len(tasks)
        if tasks:
            interrupted = run_in_pool(
                evaluate_playthrough, tasks, workers=self.workers, on_result=self._store
            )
            if interrupted:
                raise KeyboardInterrupt
        return [self._mean(self.utilities, formula) for formula in formulas]

    def core_value(self, formula: str) -> float:
        """Glowna metryka persony dla formuly policzonej juz w fitnessie."""

        return self._mean(self.cores, formula)


# --- pojedyncze uruchomienie ewolucji ---------------------------------------


def format_duration(seconds: float) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}"


def run_evolution(
    persona: str,
    run_index: int,
    args: argparse.Namespace,
    map_paths: Sequence[Path],
    append: Callable[[Row], None],
) -> dict[str, Any]:
    """Jedno niezalezne uruchomienie GP; zwraca opis najlepszego osobnika."""

    fitness = PooledFitness(
        persona,
        map_paths,
        seeds=range(args.seeds_per_map),
        max_iterations=args.iterations,
        pe_mode=args.pe_mode,
        workers=args.workers,
    )
    seed = args.seed + run_index
    started = time.perf_counter()
    last: GenerationStats | None = None
    generation_started = started

    for stats in evolve(
        fitness.scores,
        generations=args.generations,
        population_size=args.population,
        islands=args.islands,
        elitism=args.elitism,
        mutation_rate=args.mutation,
        seed=seed,
    ):
        now = time.perf_counter()
        elapsed = now - started
        append({
            "persona": persona,
            "run": run_index,
            "generation": stats.generation,
            "best_fitness": round(stats.best_fitness, 6),
            "mean_fitness": round(stats.mean_fitness, 6),
            "unique": stats.unique_chromosomes,
            "size": size(stats.best_expression),
            "playthroughs": fitness.playthroughs,
            "seconds": round(now - generation_started, 3),
            "formula": to_infix(stats.best_expression),
        })
        eta = elapsed / stats.generation * (args.generations - stats.generation)
        print(
            f"[{persona} run {run_index + 1}/{args.runs}] {stats.line()}  "
            f"partii={fitness.playthroughs:>3d}  {format_duration(elapsed)}"
            f" eta {format_duration(eta)}",
            flush=True,
        )
        generation_started = now
        last = stats

    assert last is not None  # evolve zawsze oddaje co najmniej jedna generacje
    formula = to_infix(last.best_expression)
    return {
        "persona": persona,
        "run": run_index,
        "seed": seed,
        "formula": formula,
        "fitness": round(last.best_fitness, 6),
        "core_metric": CORE_METRIC[persona],
        "core_value": round(fitness.core_value(formula), 6),
        "generations": args.generations,
        "wall_time_s": round(time.perf_counter() - started, 1),
    }


# --- wynikowy JSON ----------------------------------------------------------


def load_runs(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {"schema_version": 1, "config": {}, "runs": []}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_runs(path: Path, document: dict[str, Any]) -> None:
    """Zapis przez plik tymczasowy - 9-godzinny przebieg nie moze stracic
    dotychczasowych uruchomien na przerwanym zapisie."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def best_per_persona(runs: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Wybor z artykulu: po glownej metryce persony, remis rozstrzyga fitness."""

    best: dict[str, dict[str, Any]] = {}
    for entry in runs:
        persona = str(entry["persona"])
        current = best.get(persona)
        rank = (float(entry["core_value"]), float(entry["fitness"]))
        if current is None or rank > (float(current["core_value"]), float(current["fitness"])):
            best[persona] = entry
    return best


def promote(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Przepisz zwycieskie formuly do pliku polityk czytanego przez `--policy ours`."""

    document = load_runs(args.out)
    runs = document.get("runs", [])
    if not runs:
        parser.error(f"{args.out} nie zawiera zadnego ukonczonego uruchomienia")
    chosen = best_per_persona(runs)
    config = document.get("config", {})
    policies = {
        persona: entry["formula"]
        for persona, entry in sorted(chosen.items())
    }
    payload = {
        "schema_version": 1,
        "source": f"Wlasna ewolucja GP (cli/evolve.py), wybor po glownej metryce persony; zrodlo: {args.out.name}",
        "pe_mode": config.get("pe_mode", args.pe_mode),
        "policies": policies,
        "notes": {
            persona: (
                f"run {entry['run']} z {len([r for r in runs if r['persona'] == persona])}, "
                f"seed {entry['seed']}, fitness {entry['fitness']}, "
                f"{entry['core_metric']}={entry['core_value']} na mapach treningowych"
            )
            for persona, entry in sorted(chosen.items())
        },
    }
    args.policies_out.parent.mkdir(parents=True, exist_ok=True)
    with args.policies_out.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(f"zapisano {len(policies)} formul do: {args.policies_out}")
    for persona, entry in sorted(chosen.items()):
        print(f"  {persona:18s} {entry['core_metric']}={entry['core_value']:.3f}  {entry['formula']}")


# --- CLI --------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--personas", nargs="*", default=list(PERSONA_NAMES))
    parser.add_argument("--runs", type=int, default=3, help="niezalezne uruchomienia GP na persone")
    parser.add_argument("--generations", type=int, default=100)
    parser.add_argument("--population", type=int, default=100)
    parser.add_argument("--islands", type=int, default=5)
    parser.add_argument("--elitism", type=float, default=0.15)
    parser.add_argument("--mutation", type=float, default=0.10)
    parser.add_argument(
        "--utility-pe", choices=("binary", "normalized", "manhattan"), default="manhattan",
        help="PE w uzytecznosci person - MUSI byc takie samo jak w przebiegu oceniajacym",
    )
    parser.add_argument(
        "--ic-mode", choices=("mean3", "combined"), default="mean3",
        help="definicja IC; mean3 za kodem autorow, dotyczy Completionisty",
    )
    parser.add_argument(
        "--fallback", choices=("utility", "mean", "visits"), default="visits",
        help="sekwencja po wyczerpaniu budzetu - jak w przebiegu oceniajacym",
    )
    parser.add_argument(
        "--iterations", type=int, default=2000,
        help="budzet iteracji MCTS na jedna partie fitnessu (czas nie jest odtwarzalny)",
    )
    parser.add_argument(
        "--seeds-per-map", type=int, default=1,
        help="ile partii na mape na osobnika; wiecej = mniejszy overfitting, wiecej czasu",
    )
    parser.add_argument(
        "--maps", nargs="*", default=list(TRAINING_MAP_NAMES),
        help="mapy treningowe; domyslnie 6 map z sekcji VI-A",
    )
    parser.add_argument(
        "--pe-mode", choices=PE_MODES, default="manhattan",
        help="terminal PE tree policy; MUSI byc taki sam jak w przebiegu oceniajacym",
    )
    parser.add_argument("--seed", type=int, default=0, help="seed GP dla uruchomienia 0; kolejne dostaja +1")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="dziennik generacji (CSV, krzywe fitnessu)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="ukonczone uruchomienia i zwycieskie formuly (JSON)")
    parser.add_argument("--restart", action="store_true", help="licz od zera zamiast wznawiac")
    parser.add_argument(
        "--promote", action="store_true",
        help="nie ewoluuj; przepisz zwycieskie formuly z --out do --policies-out",
    )
    parser.add_argument("--policies-out", type=Path, default=DEFAULT_POLICIES)
    return parser


def resolve_maps(names: Sequence[str], parser: argparse.ArgumentParser) -> list[Path]:
    paths = []
    for name in names:
        path = MD2_BENCHMARK_DIR / f"{name}.txt"
        if not path.exists():
            parser.error(f"nie znaleziono mapy {name!r} w {MD2_BENCHMARK_DIR}")
        paths.append(path)
    return paths


def main() -> None:
    configure_parent_interrupts()
    parser = build_parser()
    args = parser.parse_args()

    if args.promote:
        promote(args, parser)
        return

    for name in args.personas:
        if name not in PERSONA_NAMES:
            parser.error(f"nieznana persona {name!r}; mam: {list(PERSONA_NAMES)}")
    for value, label in (
        (args.runs, "--runs"), (args.generations, "--generations"),
        (args.population, "--population"), (args.islands, "--islands"),
        (args.iterations, "--iterations"), (args.seeds_per_map, "--seeds-per-map"),
        (args.workers, "--workers"),
    ):
        if value < 1:
            parser.error(f"{label} musi wynosic co najmniej 1")

    map_paths = resolve_maps(args.maps, parser)
    document = {"schema_version": 1, "config": {}, "runs": []} if args.restart else load_runs(args.out)
    document["config"] = {
        "generations": args.generations, "population": args.population,
        "islands": args.islands, "elitism": args.elitism, "mutation": args.mutation,
        "iterations": args.iterations, "seeds_per_map": args.seeds_per_map,
        "maps": [path.stem for path in map_paths],
        "pe_mode": args.pe_mode,
        "utility_pe": args.utility_pe,
        "ic_mode": args.ic_mode,
        "fallback": args.fallback,
        "seed": args.seed,
    }
    done = {(str(entry["persona"]), int(entry["run"])) for entry in document["runs"]}
    # Kolejnosc "wszerz": najpierw uruchomienie 0 dla wszystkich person, potem 1
    # itd. Przerwane w polowie zadanie zostawia wtedy komplet person po jednym
    # uruchomieniu, a nie komplet uruchomien dla polowy person.
    wanted = [
        (persona, run_index)
        for run_index in range(args.runs)
        for persona in args.personas
    ]
    todo = [pair for pair in wanted if pair not in done]

    print(
        f"{len(wanted)} uruchomien (persony={args.personas}, runs={args.runs}), "
        f"{args.generations} generacji x {args.population} osobnikow x "
        f"{len(map_paths)} map x {args.seeds_per_map} seedow, "
        f"budzet {args.iterations} iteracji, pe_mode={args.pe_mode}, "
        f"utility_pe={args.utility_pe}, ic={args.ic_mode}, fallback={args.fallback}, "
        f"workers={args.workers}; "
        f"gotowe={len(done)}, pozostalo={len(todo)}",
        flush=True,
    )
    if not todo:
        print("nie ma czego liczyc - wszystkie uruchomienia sa juz w pliku wynikow")
        return

    args.log.parent.mkdir(parents=True, exist_ok=True)
    create_file = needs_header(args.log, restart=args.restart)
    started = time.perf_counter()
    interrupted = False
    finished = 0
    with ExitStack() as stack:
        handle = stack.enter_context(
            args.log.open("w" if create_file else "a", newline="", encoding="utf-8")
        )
        append = durable_writer(handle, SCHEMA, write_header=create_file)
        for persona, run_index in todo:
            try:
                entry = run_evolution(persona, run_index, args, map_paths, append)
            except KeyboardInterrupt:
                interrupted = True
                print(
                    f"\nPrzerwano w trakcie uruchomienia {persona} run {run_index + 1}. "
                    "Ukonczone uruchomienia sa zapisane; to jedno policzy sie od poczatku.",
                    flush=True,
                )
                break
            document["runs"].append(entry)
            save_runs(args.out, document)
            finished += 1
            remaining = len(todo) - finished
            print(
                f"ukonczone: {persona} run {run_index + 1}/{args.runs}  "
                f"fitness={entry['fitness']:+.4f}  "
                f"{entry['core_metric']}={entry['core_value']:.3f}  "
                f"czas={format_duration(entry['wall_time_s'])}  "
                f"zostalo {remaining} uruchomien, eta "
                f"{format_duration((time.perf_counter() - started) / finished * remaining)}\n"
                f"  {entry['formula']}",
                flush=True,
            )

    print(f"\nczas calosci: {format_duration(time.perf_counter() - started)}")
    print(f"dziennik generacji: {args.log}")
    print(f"uruchomienia: {args.out}")
    if not interrupted and document["runs"]:
        print("\nnajlepsze uruchomienie per persona (po glownej metryce):")
        for persona, entry in sorted(best_per_persona(document["runs"]).items()):
            print(
                f"  {persona:18s} run {entry['run']}  "
                f"{entry['core_metric']}={entry['core_value']:.3f}  {entry['formula']}"
            )
        print("\nprzepisanie do pliku polityk: dodaj --promote do tej samej komendy")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    main()
