import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from .expression import Expr, compile_expression, parse, to_infix
from .rules import PROJECT_ROOT

if TYPE_CHECKING:  # tylko dla typow - w runtime zerwaloby cykl mcts <-> selection_policy
    from .mcts import Node

DEFAULT_TREE_POLICIES_PATH = PROJECT_ROOT / "data" / "rules" / "tree_policies.json"


class SelectionPolicy(ABC):
    """Kryterium zejscia w fazie selekcji plus deklaracja potrzeb wobec wezlow.

    Dwa atrybuty klasowe to caly kontrakt miedzy polityka a drzewem; `mcts`
    czyta je raz przez `TreeSpec.for_policy` i nigdy nie pyta o konkretna klase:

    * `needs_terminals`  - czy wezly maja liczyc zmienne Tabeli I (UCB1: nie,
      wiec nie placi za nie ani czasem, ani pamiecia);
    * `pe_mode`          - wariant terminala PE (jeden z `expression.PE_MODES`:
      "binary", "normalized", "manhattan", "graded" - patrz
      `expression.resolve_pe`). Dotyczy WYLACZNIE tree policy - utility person
      zostaje binarne (docs/rules/decisions.md).

    Zmienne Tabeli I sa zawsze srednia po stanach koncowych symulacji, bo tak
    mowi sekcja V-A artykulu: "The different personas use metrics collected from
    the game's state after 10 random moves" - ta sama semantyka co R.
    """

    needs_terminals: bool = False
    pe_mode: str = "binary"

    @abstractmethod
    def select(self, parent: "Node") -> "Node":
        """Wybierz dziecko `parent` do zejscia w fazie selekcji."""

class UCB1Policy(SelectionPolicy):
    def __init__(self, c: float = math.sqrt(2)):
        self.c = c

    def select(self, parent: "Node") -> "Node":
        # t z UCB1 to licznik odwiedzin rodzica (patrz komentarz w backpropagate)
        total_visits = parent.visits
        best_node = None
        best_score = float("-inf")

        for child in parent.viable_children():
            average_utility = child.mean_utility()

            exploration_bonus = self.c * math.sqrt(
                math.log(total_visits) / child.visits
            )

            ucb_score = average_utility + exploration_bonus

            if ucb_score > best_score:
                best_score = ucb_score
                best_node = child

        if best_node is None:
            raise ValueError("Nie można wybrać dziecka: węzeł nie ma dzieci")

        return best_node


class EvolvedPolicy(SelectionPolicy):
    """Tree policy z arXiv:1802.06881: formula z GP calkowicie zastepuje UCB1.

    Formula nie ma czlonu eksploracyjnego - jedyne wejscie statystyczne to R
    (srednia nagroda wezla). Reszta MCTS zostaje bez zmian: rollout 10 losowych
    ruchow, backpropagacja utility persony, wybor koncowej akcji po sredniej.
    """

    needs_terminals = True

    def __init__(
        self,
        expression: Expr | str,
        *,
        pe_mode: str = "binary",
        label: str = "",
    ) -> None:
        self.expression: Expr = parse(expression) if isinstance(expression, str) else expression
        self.pe_mode = pe_mode
        self.label = label
        self._score = compile_expression(self.expression)

    def __repr__(self) -> str:
        return f"EvolvedPolicy({self.label or to_infix(self.expression)!r})"

    def select(self, parent: "Node") -> "Node":
        best_node = None
        best_score = float("-inf")
        score = self._score
        for child in parent.viable_children():
            value = score(child.mean_terminals(), child.mean_utility())
            if value > best_score:
                best_score = value
                best_node = child
        if best_node is None:
            raise ValueError("Nie można wybrać dziecka: węzeł nie ma dzieci")
        return best_node


def load_tree_policies(path: str | Path | None = None) -> dict[str, object]:
    with open(path or DEFAULT_TREE_POLICIES_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def evolved_policy_for(
    persona: str,
    *,
    path: str | Path | None = None,
    pe_mode: str | None = None,
) -> EvolvedPolicy:
    """Zbuduj polityke persony z pliku formul (domyslnie eq. 6-9 z artykulu)."""

    data = load_tree_policies(path)
    formulas = data["policies"]
    if persona not in formulas:
        raise ValueError(f"Brak formuly dla persony {persona!r}; mam: {sorted(formulas)}")
    mode = pe_mode or str(data.get("pe_mode", "binary"))
    return EvolvedPolicy(formulas[persona], pe_mode=mode, label=persona)
