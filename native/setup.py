"""Budowa modułu `md2native`.

    pip install pybind11 setuptools
    python native/setup.py build_ext --inplace

Moduł ładuje obok tego pliku (`native/md2native*.pyd` na Windows,
`.so` na Linuksie), więc `native/` wystarczy dodać do `sys.path`.
"""

from __future__ import annotations

import os
import sys

from setuptools import Extension, setup

try:
    import pybind11
except ImportError:  # pragma: no cover - komunikat jest tu ważniejszy niż traceback
    sys.exit("Brak pybind11. Uruchom: pip install pybind11 setuptools")

# Ścieżka do katalogu, w którym znajduje się ten plik setup.py (native/)
HERE = os.path.abspath(os.path.dirname(__file__))

if sys.platform == "win32":
    compile_args = ["/O2", "/std:c++17", "/EHsc", "/W3"]
    link_args: list[str] = []
else:
    compile_args = ["-O3", "-std=c++17", "-fno-math-errno", "-Wall"]
    link_args = []

setup(
    name="md2native",
    version="0.1.0",
    description="Natywny silnik MiniDungeons 2 + MCTS dla pętli fitnessu GP",
    ext_modules=[
        Extension(
            "md2native",
            sources=[
                os.path.join(HERE, "src", "module.cpp"),
                os.path.join(HERE, "src", "engine.cpp"),
            ],
            include_dirs=[
                pybind11.get_include(),
                os.path.join(HERE, "src"),
            ],
            language="c++",
            extra_compile_args=compile_args,
            extra_link_args=link_args,
        )
    ],
)
