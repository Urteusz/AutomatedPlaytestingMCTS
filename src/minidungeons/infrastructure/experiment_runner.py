"""Wspolna mechanika dlugich eksperymentow: wznawialny CSV i pula procesow.

Kazdy driver w tym projekcie (baseline UCB1, ewoluowana tree policy, ewolucja
GP) potrzebuje tego samego: liczyc godzinami, przezyc Ctrl+C bez utraty
policzonych prob i wznowic sie bez powtarzania pracy. Ten modul dostarcza te
mechanike raz; drivery wnosza wlasny schemat wiersza i wlasna funkcje zadania.

Odpowiedzialnosci, ktorych ten modul NIE ma: argumenty CLI, formatowanie tabel
i cokolwiek z domeny gry.
"""

from __future__ import annotations

import csv
from concurrent.futures import (
    FIRST_COMPLETED,
    CancelledError,
    Future,
    ProcessPoolExecutor,
    as_completed,
    wait,
)
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import signal
import statistics
from typing import Any, Callable, Iterator, Mapping, Sequence

ResultKey = tuple[object, ...]
Row = dict[str, object]
Task = tuple[object, ...]


# --- schemat wiersza --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CsvSchema:
    """Kolumny wyniku plus reguly typowania przy odczycie z CSV.

    `key` to kolumny identyfikujace pojedyncza probe - po nich wznawianie
    poznaje, ze dana praca jest juz policzona. Kolumny spoza `integers`
    i `floats` wracaja z pliku jako tekst.
    """

    fields: tuple[str, ...]
    key: tuple[str, ...]
    integers: frozenset[str] = field(default_factory=frozenset)
    floats: frozenset[str] = field(default_factory=frozenset)

    def cast(self, name: str, value: object) -> object:
        if name in self.integers:
            return int(value)  # type: ignore[arg-type]
        if name in self.floats:
            return float(value)  # type: ignore[arg-type]
        return str(value)

    def row_key(self, row: Mapping[str, object]) -> ResultKey:
        return tuple(self.cast(name, row[name]) for name in self.key)

    def normalize(self, raw: Mapping[str, str]) -> Row:
        """Zamien wiersz CSV na typy, ktore zwraca funkcja zadania."""

        missing = [name for name in self.fields if raw.get(name) in (None, "")]
        if missing:
            raise ValueError(f"niepelny wiersz CSV; brak pol: {', '.join(missing)}")
        return {name: self.cast(name, raw[name]) for name in self.fields}


# --- wznawialny dziennik wynikow --------------------------------------------


def load_results(path: Path, schema: CsvSchema) -> dict[ResultKey, Row]:
    """Wczytaj policzone proby, zeby przerwany eksperyment dalo sie wznowic."""

    if not path.exists() or path.stat().st_size == 0:
        return {}
    results: dict[ResultKey, Row] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(schema.fields):
            raise ValueError(
                f"{path} ma niezgodny naglowek; uzyj innego pliku wyjsciowego albo --restart"
            )
        for line_number, raw_row in enumerate(reader, start=2):
            try:
                row = schema.normalize(raw_row)
            except (TypeError, ValueError) as error:
                raise ValueError(f"bledny wiersz {line_number} w {path}: {error}") from error
            results[schema.row_key(row)] = row
    return results


def needs_header(path: Path, *, restart: bool) -> bool:
    """Czy plik powstaje od nowa (naglowek + tryb "w") czy dopisujemy ("a")."""

    return restart or not path.exists() or path.stat().st_size == 0


def durable_writer(
    handle: Any, schema: CsvSchema, *, write_header: bool
) -> Callable[[Row], None]:
    """Zwroc funkcje dopisujaca jeden wiersz z flush + fsync.

    Synchronizacja po kazdym wierszu jest celowa: eksperyment trwa godzinami
    i musi przezyc twarde ubicie procesu bez utraty policzonych prob.
    """

    writer = csv.DictWriter(handle, fieldnames=list(schema.fields))

    def flush() -> None:
        handle.flush()
        os.fsync(handle.fileno())

    if write_header:
        writer.writeheader()
        flush()

    def append(row: Row) -> None:
        writer.writerow(row)
        flush()

    return append


# --- pula procesow ----------------------------------------------------------


def configure_parent_interrupts() -> None:
    """Traktuj Ctrl+Break jak Ctrl+C (Windows)."""

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)


def ignore_interrupt_in_worker() -> None:
    """Ctrl+C obsluguje tylko rodzic; workery koncza rozpoczete proby."""

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)


def _submit_next(
    pool: ProcessPoolExecutor,
    task_iterator: Iterator[Task],
    futures: dict[Future, Task],
    task_function: Callable[..., Row],
) -> None:
    try:
        task = next(task_iterator)
    except StopIteration:
        return
    futures[pool.submit(task_function, *task)] = task


def run_in_pool(
    task_function: Callable[..., Row],
    tasks: Sequence[Task],
    *,
    workers: int,
    on_result: Callable[[Row], None],
) -> bool:
    """Policz `tasks` w puli procesow, trzymajac `workers` prob w locie.

    `task_function` musi byc importowalna na poziomie modulu (pickle), a kazdy
    element `tasks` to komplet jej argumentow pozycyjnych. Wyniki trafiaja do
    `on_result` w kolejnosci ukonczenia, w procesie rodzica.

    Zwraca True, jesli uzytkownik przerwal Ctrl+C: rozpoczete proby sa wtedy
    dokanczane i raportowane, nowe nie startuja.
    """

    task_iterator = iter(tasks)
    futures: dict[Future, Task] = {}
    interrupted = False
    pool = ProcessPoolExecutor(max_workers=workers, initializer=ignore_interrupt_in_worker)
    try:
        for _ in range(min(workers, len(tasks))):
            _submit_next(pool, task_iterator, futures, task_function)

        try:
            while futures:
                finished, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in finished:
                    on_result(future.result())
                    del futures[future]
                    _submit_next(pool, task_iterator, futures, task_function)
        except KeyboardInterrupt:
            interrupted = True
            print(
                "\nPrzerwa zgloszona. Koncze i zapisuje aktualnie wykonywane proby; "
                "nie uruchamiam nowych...",
                flush=True,
            )
            for future in list(futures):
                if future.cancel():
                    del futures[future]
            for future in as_completed(futures):
                try:
                    row = future.result()
                except (BrokenProcessPool, CancelledError):
                    # Sygnal konsoli potrafi dojsc do swiezo zrodzonego workera
                    # na Windowsie, zanim ruszy jego initializer. Niedokonczona
                    # proba nie ma wiersza w CSV, wiec powtorzy sie po wznowieniu.
                    pass
                else:
                    on_result(row)
                del futures[future]
    finally:
        pool.shutdown(wait=True, cancel_futures=interrupted)
    return interrupted


# --- statystyka -------------------------------------------------------------


def mean_with_ci95(values: Sequence[float]) -> tuple[float, float]:
    """Srednia arytmetyczna i polowa szerokosci dwustronnego 95% CI."""

    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, 0.0
    return mean, 1.96 * statistics.stdev(values) / math.sqrt(len(values))
