import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # tylko dla typow - w runtime zerwaloby cykl mcts <-> selectionPolicy
    from .mcts import Node


class SelectionPolicy(ABC):
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

        for child in parent.children.values():
            average_utility = child.total_utility / child.visits

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

# class TreePolicy(SelectionPolicy):
#     def __init__(self, child: Node, parent: Node|Node):
#         self.child = child
#         self.parent = parent
#
#     def search(self):
#         total_visits = sum(child.visits for child in self.children.values())
#
#         return best_node
