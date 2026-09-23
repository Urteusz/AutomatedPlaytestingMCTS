"""Drzewa wyrazen ewoluowanej tree policy (arXiv:1802.06881, sekcja V-B).

Wezly: +, -, *, /; liscie: zmienna z Tabeli I albo stala.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterator

if TYPE_CHECKING:
    from .engine import MiniDungeon

# Kolejnosc zmiennych w krotce cache'owanej w wezle drzewa MCTS (Tabela I).
# R (Rbar) jest statystyka wezla, nie stanu gry, wiec stoi osobno.
TERMINAL_ORDER = ("ST", "PE", "PD", "TO", "MTK", "MS", "JT", "HL", "TU", "TS", "IC")
RBAR = "Rbar"
VARIABLE_NAMES = TERMINAL_ORDER + (RBAR,)

# Tabela I -> klucze z MiniDungeon.metric_values(). PD, TO, MS i IC sa
# stosunkami, zgodnie z przypisem pod Tabela I w artykule.
METRIC_KEYS = {
    "ST": "steps",
    "PE": "proximity_to_exit",
    "PD": "potion_ratio",
    "TO": "treasure_ratio",
    "MTK": "minitaur_knockouts",
    "MS": "monster_ratio",
    "JT": "javelins",
    "HL": "health_left",
    "TU": "teleports",
    "TS": "traps",
    "IC": "interactive_ratio",
}

BINARY_OPS = ("+", "-", "*", "/")
_AST_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


class ExpressionError(ValueError):
    """Wyrazenie poza zbiorem funkcji i terminali z artykulu."""


def protected_division(numerator: float, denominator: float) -> float:
    """Dzielenie ochronne; 1.0 przy zerowym mianowniku (artykul nie podaje konwencji)."""

    return numerator / denominator if denominator else 1.0


@dataclass(frozen=True, slots=True)
class Const:
    value: float

    def depth(self) -> int:
        return 0


@dataclass(frozen=True, slots=True)
class Var:
    name: str

    def depth(self) -> int:
        return 0


@dataclass(frozen=True, slots=True)
class BinOp:
    op: str
    left: "Expr"
    right: "Expr"

    def depth(self) -> int:
        return 1 + max(self.left.depth(), self.right.depth())


Expr = Const | Var | BinOp


def iter_subtrees(expression: Expr) -> Iterator[Expr]:
    """Przejscie preorder - punkt zaczepienia dla krzyzowania poddrzew."""

    yield expression
    if isinstance(expression, BinOp):
        yield from iter_subtrees(expression.left)
        yield from iter_subtrees(expression.right)


def size(expression: Expr) -> int:
    return sum(1 for _ in iter_subtrees(expression))


def parse(text: str) -> Expr:
    """Zbuduj drzewo z zapisu infiksowego, np. "2*PD + 3*Rbar + 0.19".

    `ast` sluzy tylko do parsowania; przepuszczamy wylacznie wezly ze zbioru artykulu.
    """

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"Nie mozna sparsowac wyrazenia {text!r}: {exc}") from exc
    return _from_ast(tree.body)


def _from_ast(node: ast.expr) -> Expr:
    if isinstance(node, ast.BinOp):
        op = _AST_OPS.get(type(node.op))
        if op is None:
            raise ExpressionError(
                f"Operator {type(node.op).__name__} poza zbiorem {BINARY_OPS}"
            )
        return BinOp(op, _from_ast(node.left), _from_ast(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        # zwijamy -x, zeby zbior operatorow zostal wylacznie binarny
        inner = _from_ast(node.operand)
        if isinstance(inner, Const):
            return Const(-inner.value)
        return BinOp("-", Const(0.0), inner)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _from_ast(node.operand)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Const(float(node.value))
    if isinstance(node, ast.Name):
        if node.id not in VARIABLE_NAMES:
            raise ExpressionError(
                f"Nieznana zmienna {node.id!r}; dozwolone: {VARIABLE_NAMES}"
            )
        return Var(node.id)
    raise ExpressionError(f"Niedozwolony element wyrazenia: {ast.dump(node)}")


def to_source(expression: Expr) -> str:
    """Kod Pythona dla `compile_expression`; `v` to krotka terminali, `r` to R."""

    if isinstance(expression, Const):
        return repr(expression.value)
    if isinstance(expression, Var):
        if expression.name == RBAR:
            return "r"
        return f"v[{TERMINAL_ORDER.index(expression.name)}]"
    left, right = to_source(expression.left), to_source(expression.right)
    if expression.op == "/":
        return f"_pdiv({left}, {right})"
    return f"({left} {expression.op} {right})"


def to_infix(expression: Expr) -> str:
    """Czytelny zapis infiksowy formuly."""

    if isinstance(expression, Const):
        value = expression.value
        return repr(int(value)) if value == int(value) else repr(value)
    if isinstance(expression, Var):
        return expression.name
    return f"({to_infix(expression.left)} {expression.op} {to_infix(expression.right)})"


def compile_expression(expression: Expr) -> Callable[[tuple[float, ...], float], float]:
    """Skompiluj drzewo raz - formula liczy sie dla kazdego dziecka w selekcji."""

    source = f"lambda v, r: {to_source(expression)}"
    return eval(compile(source, "<tree_policy>", "eval"), {"_pdiv": protected_division})


def evaluate(expression: Expr, terminals: tuple[float, ...], average_reward: float) -> float:
    """Ewaluacja bez kompilacji, do testow."""

    return compile_expression(expression)(terminals, average_reward)


def to_dict(expression: Expr) -> dict[str, object]:
    if isinstance(expression, Const):
        return {"const": expression.value}
    if isinstance(expression, Var):
        return {"var": expression.name}
    return {
        "op": expression.op,
        "left": to_dict(expression.left),
        "right": to_dict(expression.right),
    }


def from_dict(data: dict[str, object]) -> Expr:
    if "const" in data:
        return Const(float(data["const"]))  # type: ignore[arg-type]
    if "var" in data:
        name = str(data["var"])
        if name not in VARIABLE_NAMES:
            raise ExpressionError(f"Nieznana zmienna {name!r}")
        return Var(name)
    op = str(data["op"])
    if op not in BINARY_OPS:
        raise ExpressionError(f"Nieznany operator {op!r}")
    return BinOp(op, from_dict(data["left"]), from_dict(data["right"]))  # type: ignore[arg-type]


PE_MODES = ("binary", "normalized", "manhattan", "graded")


def resolve_pe(environment: "MiniDungeon", pe_mode: str) -> float:
    """Wartosc terminala PE w wybranym wariancie.

    binary: 0 na wyjsciu, -1 wpp; normalized/manhattan: 1 - dystans/maks (manhattan
    bez wiedzy o scianach); graded: -dystans/maks.
    """

    if pe_mode == "binary":
        return environment.proximity_to_exit()
    if pe_mode == "normalized":
        return environment.normalized_proximity_to_exit()
    if pe_mode == "manhattan":
        return environment.manhattan_proximity_to_exit()
    if pe_mode == "manhattan":
        return environment.manhattan_proximity_to_exit()
    if pe_mode == "graded":
        return environment.graded_proximity_to_exit()
    raise ValueError(f"Nieznany pe_mode {pe_mode!r}; oczekiwano {PE_MODES}")


def terminal_values(environment: "MiniDungeon", *, pe_mode: str = "binary") -> tuple[float, ...]:
    """Zmienne Tabeli I dla stanu w wezle, w kolejnosci TERMINAL_ORDER.

    HL jest znormalizowane do [0,1] jak w kodzie autorow (`Health/10d`).
    """

    metrics = environment.metric_values()
    values = [float(metrics[METRIC_KEYS[name]]) for name in TERMINAL_ORDER]
    if pe_mode != "binary":
        values[TERMINAL_ORDER.index("PE")] = resolve_pe(environment, pe_mode)
    max_hp = float(getattr(environment, "PLAYER_MAX_HP", 10) or 10)
    values[TERMINAL_ORDER.index("HL")] /= max_hp
    return tuple(values)
