import unittest

from src.minidungeons.domain.expression import (
    TERMINAL_ORDER,
    BinOp,
    Const,
    ExpressionError,
    Var,
    compile_expression,
    from_dict,
    parse,
    protected_division,
    to_dict,
    to_infix,
)
from src.minidungeons.domain.selection_policy import load_tree_policies


def terminals(**overrides: float) -> tuple[float, ...]:
    values = [0.0] * len(TERMINAL_ORDER)
    for name, value in overrides.items():
        values[TERMINAL_ORDER.index(name)] = value
    return tuple(values)


class ExpressionTests(unittest.TestCase):
    def test_parse_respects_precedence_and_parentheses(self) -> None:
        self.assertEqual(
            BinOp("+", Const(2.0), BinOp("*", Const(3.0), Var("ST"))),
            parse("2 + 3*ST"),
        )
        self.assertEqual(
            BinOp("*", BinOp("+", Const(2.0), Const(3.0)), Var("ST")),
            parse("(2 + 3)*ST"),
        )

    def test_unary_minus_folds_into_the_binary_operator_set(self) -> None:
        self.assertEqual(Const(-0.5), parse("-0.5"))
        self.assertEqual(BinOp("-", Const(0.0), Var("PE")), parse("-PE"))

    def test_rejects_operators_and_variables_outside_the_paper(self) -> None:
        for text in ("ST ** 2", "max(ST, PE)", "ST % 2", "UNKNOWN + 1"):
            with self.subTest(text=text), self.assertRaises(ExpressionError):
                parse(text)

    def test_json_roundtrip_preserves_the_tree(self) -> None:
        expression = parse("2*PD + 2*MS + TO + 3*Rbar + ST + PE + 0.19")
        self.assertEqual(expression, from_dict(to_dict(expression)))

    def test_protected_division_returns_one_for_zero_denominator(self) -> None:
        self.assertEqual(1.0, protected_division(5.0, 0.0))
        self.assertEqual(2.5, protected_division(5.0, 2.0))
        score = compile_expression(parse("ST / PD"))
        self.assertEqual(1.0, score(terminals(ST=4.0, PD=0.0), 0.0))

    def test_rbar_is_passed_separately_from_state_metrics(self) -> None:
        score = compile_expression(parse("Rbar*(1 - HL)"))
        self.assertAlmostEqual(-9.0 * 2.0, score(terminals(HL=10.0), 2.0))


class PublishedFormulaTests(unittest.TestCase):
    """Formuly eq. (6)-(9) z arXiv:1802.06881."""

    def setUp(self) -> None:
        self.formulas = load_tree_policies()["policies"]

    def test_every_persona_has_a_parsable_formula(self) -> None:
        for persona, text in self.formulas.items():
            with self.subTest(persona=persona):
                self.assertTrue(to_infix(parse(text)))

    def test_runner_formula_degenerates_under_binary_pe(self) -> None:
        """Czlon PE*PE*(PE+1) z eq. (6) jest zerem dla PE w {0, -1}.

        Dotyczy odczytu terminali ze STANU W WEZLE (`terminal_source="node"`).
        Przy `terminal_source="rollout"` srednia binarnego PE po symulacjach jest
        ciagla, wiec czlon sie nie zeruje - i ta konfiguracja wypada najlepiej
        (2/9 wygranych vs 0/9 dla ciaglego PE). Ciagle PE jest gorsze, bo
        PE^2*(PE+1) jest niemonotoniczne: maksimum wypada w ~2/3 drogi od
        wyjscia, wiec formula nagradza bledzenie.
        """

        score = compile_expression(parse(self.formulas["runner"]))
        at_exit = score(terminals(ST=7.0, HL=10.0, PE=0.0), -1.07)
        elsewhere = score(terminals(ST=7.0, HL=10.0, PE=-1.0), -1.07)
        self.assertEqual(at_exit, elsewhere)

        # przy ciaglym PE formula juz roznicuje stany
        midway = score(terminals(ST=7.0, HL=10.0, PE=-0.5), -1.07)
        self.assertNotEqual(at_exit, midway)


if __name__ == "__main__":
    unittest.main()
