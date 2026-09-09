import json
from pathlib import Path
import tempfile
import unittest

from src.minidungeons.domain import Action, MiniDungeon, load_personas, load_rules, utility_from_metrics
from src.minidungeons.domain.rules import DEFAULT_RULES_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAP_DIR = PROJECT_ROOT / "data" / "maps" / "md2" / "benchmark"


class RulesEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.fixture_index = 0

    def make_env(self, *rows, portal_pairs=None, line_of_sight=None, wizard=None):
        self.fixture_index += 1
        path = Path(self.temp_directory.name) / f"fixture{self.fixture_index}.txt"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        overrides = line_of_sight or wizard
        return MiniDungeon(
            path,
            rules_path=self.make_rules(line_of_sight, wizard) if overrides else None,
            portal_pairs=portal_pairs,
        )

    def make_rules(self, line_of_sight=None, wizard=None):
        """Reguly domyslne z podmieniona sekcja LOS lub parametrami wizarda."""

        data = json.loads(DEFAULT_RULES_PATH.read_text(encoding="utf-8"))
        if line_of_sight:
            data["line_of_sight"] = {**data["line_of_sight"], **line_of_sight}
        if wizard:
            data["monsters"]["wizard"] = {**data["monsters"]["wizard"], **wizard}
        path = Path(self.temp_directory.name) / f"rules{self.fixture_index}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_rules_and_personas_json_load(self):
        rules = load_rules()
        self.assertEqual("md2-methodological-reconstruction-v1", rules.data["ruleset_id"])
        self.assertEqual(10, rules.value("hero", "start_hp"))
        personas = load_personas()
        self.assertEqual(
            {"runner", "monster_killer", "treasure_collector", "completionist"},
            set(personas["personas"]),
        )
        self.assertEqual(5.0, personas["death_penalty"])

    def test_every_benchmark_map_loads_and_clone_is_independent(self):
        for path in sorted(MAP_DIR.glob("map??.txt")):
            with self.subTest(map=path.stem):
                env = MiniDungeon(path)
                clone = env.clone()
                action = clone.legal_actions()[0]
                clone.step(action)
                self.assertNotEqual(env.state_key(), clone.state_key())
                self.assertEqual(env.entrance, env.hero_position)

    def test_potion_treasure_and_exit(self):
        env = self.make_env("#######", "#EprX.#", "#######")
        env.hero_hp = 9
        env.step(Action.move("E"))
        self.assertEqual(10, env.hero_hp)
        self.assertEqual(1, env.metrics.potions_drunk)
        env.step(Action.move("E"))
        self.assertEqual(1, env.metrics.treasures_opened)
        env.step(Action.move("E"))
        self.assertTrue(env.done)
        self.assertEqual("exit", env.outcome)
        self.assertEqual(0.0, env.proximity_to_exit())

    def test_collision_damage_is_simultaneous(self):
        env = self.make_env("######", "#Eg.X#", "######")
        env.step(Action.move("E"))
        self.assertEqual(9, env.hero_hp)
        self.assertEqual((1, 2), env.hero_position)
        self.assertEqual(1, env.metrics.monsters_slain)
        self.assertFalse(env.npcs)

    def test_javelin_kills_visible_monster_and_is_recovered(self):
        env = self.make_env("#######", "#E.g.X#", "#######")
        throw = next(action for action in env.legal_actions() if action.kind == "throw")
        env.step(throw)
        self.assertFalse(env.javelin_held)
        self.assertEqual((1, 3), env.javelin_position)
        self.assertEqual(1, env.metrics.javelins_thrown)
        self.assertEqual(1, env.metrics.monsters_slain)
        env.step(Action.move("E"))
        env.step(Action.move("E"))
        self.assertTrue(env.javelin_held)
        self.assertIsNone(env.javelin_position)

    def test_javelin_may_target_monster_behind_another_character(self):
        env = self.make_env("########", "#E.g.oX#", "########")
        targets = [action.target_id for action in env.legal_actions() if action.kind == "throw"]
        self.assertEqual([0, 1], targets)

    def test_wall_blocks_orthogonal_line_of_sight(self):
        env = self.make_env("#######", "#E.#gX#", "#.....#", "#######")
        self.assertFalse(any(action.kind == "throw" for action in env.legal_actions()))
        npc = next(iter(env.npcs.values()))
        self.assertFalse(env.has_line_of_sight(env.hero_position, npc.position))

    def test_wizards_act_in_initial_row_major_order(self):
        env = self.make_env(
            "#########", "#w..E..w#", "#.......#", "#...X...#", "#########"
        )
        _, info = env.step(Action.move("E"))
        spells = [event for event in info["events"] if event["type"] == "wizard_spell"]
        self.assertEqual([0, 1], [event["actor_id"] for event in spells])
        self.assertEqual(8, env.hero_hp)

    def test_wizard_approaches_only_from_beyond_its_spell_range(self):
        """MCTS §IV: czar w LOS do 5 kafli, podejscie w LOS powyzej 5 kafli."""

        env = self.make_env("##########", "#E......w#", "#X.......#", "##########")
        env.step(Action.move("E"))  # dystans 6 > 5, wiec wizard podchodzi
        wizard = next(iter(env.npcs.values()))
        self.assertEqual((1, 7), wizard.position)
        self.assertEqual(10, env.hero_hp)

        env.step(Action.move("E"))  # dystans 4 <= 5, wiec rzuca czar i stoi
        self.assertEqual((1, 7), wizard.position)
        self.assertEqual(9, env.hero_hp)

    def test_wizard_without_line_of_sight_stays_unless_rules_say_otherwise(self):
        """Publikacje sa tu sprzeczne - patrz `wizard_without_los`
        w docs/rules/decisions.md. Domyslnie obowiazuje wersja z artykulu
        MCTS, w ktorej ruch wymaga LOS."""

        rows = ("########", "#E.#..w#", "#X.....#", "########")
        env = self.make_env(*rows)
        env.step(Action.move("E"))
        wizard = next(iter(env.npcs.values()))
        self.assertEqual((1, 6), wizard.position)
        self.assertFalse(env.has_line_of_sight(wizard.position, env.hero_position))
        self.assertEqual(
            "no_los",
            next(event for event in env.last_events if event["type"] == "npc_stay")["reason"],
        )

        chasing = self.make_env(*rows, wizard={"moves_without_los": True})
        chasing.step(Action.move("E"))
        self.assertEqual((2, 6), next(iter(chasing.npcs.values())).position)

    def test_goblin_walks_into_blob_and_both_die_in_collision(self):
        env = self.make_env("#########", "#gb..E.X#", "#########")
        env.step(Action.move("E"))
        self.assertFalse(env.npcs)
        self.assertEqual(0, env.metrics.monsters_slain)

    def test_goblin_chases_only_with_line_of_sight(self):
        env = self.make_env("########", "#g..E.X#", "#......#", "########")
        env.step(Action.move("E"))
        goblin = next(iter(env.npcs.values()))
        self.assertEqual((1, 2), goblin.position)

    def test_blobs_merge_and_keep_lower_initial_order(self):
        env = self.make_env("########", "#bb.E.X#", "#......#", "########")
        env.step(Action.move("W"))
        self.assertEqual(1, len(env.npcs))
        blob = next(iter(env.npcs.values()))
        self.assertEqual(0, blob.npc_id)
        self.assertEqual(2, blob.power)
        self.assertEqual((1, 2), blob.position)

    def test_blob_consumes_potion_without_healing(self):
        env = self.make_env("########", "#b.pE.X#", "#......#", "########")
        env.step(Action.move("S"))
        env.step(Action.move("W"))
        blob = next(iter(env.npcs.values()))
        self.assertEqual((1, 3), blob.position)
        self.assertNotIn((1, 3), env.objects)
        self.assertEqual(1, blob.power)

    def test_ogre_consumes_treasure_without_scoring_for_hero(self):
        env = self.make_env("########", "#o.rE.X#", "#......#", "########")
        env.step(Action.move("S"))
        env.step(Action.move("W"))
        ogre = next(iter(env.npcs.values()))
        self.assertEqual((1, 3), ogre.position)
        self.assertTrue(ogre.fancy)
        self.assertEqual(0, env.metrics.treasures_opened)

    def test_ogres_deal_simultaneous_damage_to_each_other(self):
        env = self.make_env("########", "#oo.E.X#", "########")
        env.step(Action.move("W"))
        self.assertFalse(env.npcs)
        self.assertEqual(0, env.metrics.monsters_slain)

    def test_occupied_portal_destination_blocks_teleport(self):
        env = self.make_env(
            "########", "#EP.gPX#", "########",
            portal_pairs=[((1, 2), (1, 5))],
        )
        next(iter(env.npcs.values())).position = (1, 5)
        env.step(Action.move("E"))
        self.assertEqual((1, 2), env.hero_position)
        self.assertEqual(0, env.metrics.teleports_used)

    def test_portal_teleports_in_same_turn_without_extra_step(self):
        env = self.make_env(
            "########", "#EP..PX#", "########",
            portal_pairs=[((1, 2), (1, 5))],
        )
        env.step(Action.move("E"))
        self.assertEqual((1, 5), env.hero_position)
        self.assertEqual(1, env.metrics.steps_taken)
        self.assertEqual(1, env.metrics.teleports_used)

    def test_trap_is_persistent(self):
        env = self.make_env("######", "#E^.X#", "######")
        env.step(Action.move("E"))
        env.step(Action.move("W"))
        env.step(Action.move("E"))
        self.assertEqual(8, env.hero_hp)
        self.assertEqual(2, env.metrics.traps_sprung)
        self.assertEqual("trap", env.objects[(1, 2)])

    def test_minitaur_is_stunned_for_three_npc_actions_and_passable(self):
        env = self.make_env("########", "#E.M..X#", "########")
        throw = next(action for action in env.legal_actions() if action.kind == "throw")
        env.step(throw)
        minitaur = next(iter(env.npcs.values()))
        self.assertEqual(2, minitaur.stunned_actions)
        env.step(Action.move("E"))
        self.assertEqual(1, minitaur.stunned_actions)
        env.step(Action.move("E"))
        self.assertEqual((1, 3), env.hero_position)
        self.assertEqual(0, minitaur.stunned_actions)
        self.assertEqual(1, env.metrics.minitaur_knockouts)

    def test_trap_knocks_out_minitaur(self):
        env = self.make_env("########", "#M^..E.#", "#.....X#", "########")
        env.step(Action.move("W"))
        minitaur = next(iter(env.npcs.values()))
        self.assertEqual((1, 2), minitaur.position)
        self.assertEqual(3, minitaur.stunned_actions)

    def test_persona_utilities_match_paper_formulas(self):
        metrics = {
            "steps": 10,
            "proximity_to_exit": -0.2,
            "monster_ratio": 0.5,
            "treasure_ratio": 0.25,
            "interactive_ratio": 0.75,
            "died": False,
        }
        self.assertAlmostEqual(-0.3, utility_from_metrics("runner", metrics))
        self.assertAlmostEqual(0.29, utility_from_metrics("monster_killer", metrics))
        self.assertAlmostEqual(0.115, utility_from_metrics("treasure_collector", metrics))
        self.assertAlmostEqual(0.465, utility_from_metrics("completionist", metrics))
        metrics["died"] = True
        self.assertAlmostEqual(-5.3, utility_from_metrics("runner", metrics))

    def test_map02_reproduces_md2_figure1_tile_and_move_counts(self):
        """105 tiles and 240 moves from MD2 Fig. 1. Both numbers are independent
        of the line of sight rules, so they validate the transcription of the
        figure into map02.txt - see `illegal_move` and `wait_action` in
        docs/rules/decisions.md."""

        env = MiniDungeon(MAP_DIR / "map02.txt")
        rows, cols = len(env.terrain), len(env.terrain[0])
        floor_tiles = [
            (r, c) for r in range(rows) for c in range(cols) if env.terrain[r][c] != "#"
        ]
        self.assertEqual(105, len(floor_tiles))

        moves = sum(
            1
            for tile in floor_tiles
            for delta in ((-1, 0), (0, 1), (1, 0), (0, -1))
            if (tile[0] + delta[0], tile[1] + delta[1]) in set(floor_tiles)
        )
        self.assertEqual(240, moves)

    def test_map02_javelin_target_count_stays_below_the_published_118(self):
        """MD2 Fig. 1 reports 118 javelin actions across the 105 tiles
        (branching 3.41 = (240+118)/105). No line of sight variant we tested
        reproduces 118: axis4 gives 70, the shipped axis8 95, an unrestricted
        raycast 143. This test pins our number so
        the gap stays visible instead of drifting silently - see
        `line_of_sight_geometry` in docs/rules/decisions.md."""

        env = MiniDungeon(MAP_DIR / "map02.txt")
        throws = sum(
            1
            for row in range(env.height)
            for column in range(env.width)
            for npc in env.npcs.values()
            if env.terrain[row][column] != "#"
            and env.has_line_of_sight((row, column), npc.position)
        )
        self.assertEqual(95, throws)

    def test_sight_does_not_squeeze_between_two_wall_corners_on_map02(self):
        """Regression for a real case spotted in the GUI: from (13, 1) the ray
        to the treasure at (10, 4) crosses the exact point where the corners of
        the walls (11, 2) and (12, 3) touch. Letting sight through that
        zero-width gap made the ogre walk sideways instead of at the hero."""

        env = MiniDungeon(MAP_DIR / "map02.txt")
        self.assertEqual("#", env.terrain[11][2])
        self.assertEqual("#", env.terrain[12][3])
        self.assertEqual("treasure", env.objects[(10, 4)])
        self.assertFalse(env.has_line_of_sight((13, 1), (10, 4)))

    def test_ogre_prefers_the_hero_once_the_leaking_treasure_is_gone(self):
        """Same two north moves, then a throw: the hero does not move, so ogre
        id 6 sees him at distance 3 and no treasure at all, and closes in."""

        env = MiniDungeon(MAP_DIR / "map02.txt")
        for _ in range(2):
            env.step(Action.move("N"))
        self.assertEqual((16, 1), env.hero_position)
        self.assertEqual((13, 1), env.npcs[6].position)

        throw = next(action for action in env.legal_actions() if action.kind == "throw")
        env.step(throw)
        self.assertEqual((16, 1), env.hero_position)  # rzut nie rusza bohatera
        self.assertEqual((14, 1), env.npcs[6].position)

    def test_map02_matches_md2_figure1_after_three_north_moves(self):
        """NPC state after the hero's first three N moves, i.e. the paper's
        after-three-turns panel. Two things in that panel are legible enough to
        test: the minitaur closes three tiles down column 1, and ogre id 6
        leaves (12, 2), eats the treasure at (13, 1) and turns fancy. The latter
        is impossible under axial LOS (from (12, 2) it can only see (12, 1) and
        (13, 2), neither of which the hero can reach in three moves), which is
        why the shipped geometry is axis8. Goblin id 9 catches LOS once the hero
        enters row 15 and dies stepping onto the trap lying between them."""

        env = MiniDungeon(MAP_DIR / "map02.txt")
        self.assertEqual((18, 1), env.hero_position)
        for _ in range(3):
            env.step(Action.move("N"))
        self.assertEqual((15, 1), env.hero_position)

        positions = {npc.npc_id: npc.position for npc in env.npcs.values()}
        self.assertNotIn(9, positions)  # goblin died on the trap at (15, 2)
        self.assertEqual((4, 1), positions[0])  # minitaur
        self.assertEqual((1, 3), positions[1])  # wizard, never had LOS
        self.assertEqual((1, 7), positions[2])  # blob, never got a target
        self.assertEqual((2, 4), positions[3])  # ogre, treasure behind a wall
        self.assertEqual((4, 7), positions[4])  # blob, walked onto the potion
        self.assertEqual((4, 5), positions[5])  # goblin, no LOS yet
        self.assertEqual((12, 4), positions[7])  # goblin, saw the hero diagonally
        self.assertEqual((13, 7), positions[8])  # wizard, never had LOS
        self.assertEqual((18, 6), positions[10])  # minitaur

        ogre = next(npc for npc in env.npcs.values() if npc.npc_id == 6)
        self.assertEqual((14, 1), ogre.position)  # (12,2) -> (13,2) -> (13,1) -> (14,1)
        self.assertTrue(ogre.fancy)
        self.assertNotIn((13, 1), env.objects)
        self.assertEqual(0, env.metrics.treasures_opened)  # the ogre ate it, not the hero

        self.assertNotIn((4, 7), env.objects)  # potion consumed by the blob
        self.assertEqual(0, env.metrics.potions_drunk)  # blob does not heal or count as hero drinking

    def test_axial_geometry_freezes_the_figure1_ogre(self):
        """Regression guard for the bug this replaced: with `axis4` the ogre of
        MD2 Fig. 1 cannot move at all in three turns, contradicting the panel."""

        env = MiniDungeon(MAP_DIR / "map02.txt", rules_path=self.make_rules({"geometry": "axis4"}))
        for _ in range(3):
            env.step(Action.move("N"))
        ogre = next(npc for npc in env.npcs.values() if npc.npc_id == 6)
        self.assertEqual((12, 2), ogre.position)
        self.assertFalse(ogre.fancy)
        self.assertIn((13, 1), env.objects)

    def test_target_seeker_needs_diagonal_geometry_to_see_a_diagonal_treasure(self):
        """The Fig. 1 situation in miniature: the treasure sits diagonally from
        the ogre, so only a diagonal geometry lets it start walking."""

        rows = ("######", "#.o..#", "#r..E#", "#....#", "#...X#", "######")
        for geometry, expected in (("axis4", (1, 2)), ("axis8", (2, 1)), ("raycast", (2, 1))):
            with self.subTest(geometry=geometry):
                env = self.make_env(*rows, line_of_sight={"geometry": geometry})
                env.step(Action.move("S"))  # hero leaves the ogre's row and column
                env.step(Action.move("W"))
                ogre = next(iter(env.npcs.values()))
                self.assertEqual(expected, ogre.position)
                self.assertEqual(geometry != "axis4", ogre.fancy)
                self.assertEqual(geometry == "axis4", (2, 1) in env.objects)

    def test_only_two_walls_at_a_corner_block_diagonal_sight(self):
        """A 45 degree ray from (1, 1) to (3, 3) crosses the corner of four
        tiles twice; its sides at the first crossing are (1, 2) and (2, 1).
        Sight passes while at least one of them is floor and stops once both
        are walls - the single rule left after `transparent` and `strict` were
        refuted by MD2 Fig. 1, see docs/rules/decisions.md."""

        for rows, visible in (
                (("#g.E#", "#...#"), True),   # both corner sides open
                (("#g#E#", "#...#"), True),   # one side walled, sight brushes past
                (("#g#E#", "##..#"), False),  # both sides walled, zero-width gap
        ):
            with self.subTest(rows=rows):
                env = self.make_env(
                    "#####", rows[0], rows[1], "#..X#", "#####",
                    line_of_sight={"geometry": "axis8"},
                )
                self.assertEqual(visible, env.has_line_of_sight((1, 1), (3, 3)))

    def test_corner_crossing_is_detected_outside_45_degrees(self):
        """A (3, 1) ray also hits an exact corner, between (3, 1) and (2, 2)
        after passing (2, 1) - it happens for every direction whose reduced form
        has two odd components. Missing this is what made an earlier
        sampling-based prototype miscount, hence the explicit case."""

        rows = ("#####", "#g..#", "#.#.#", "##..#", "#Er.#", "#..X#", "#####")
        env = self.make_env(*rows, line_of_sight={"geometry": "raycast"})
        self.assertEqual("#", env.terrain[2][2])  # one corner side
        self.assertEqual("#", env.terrain[3][1])  # the other corner side
        self.assertEqual(".", env.terrain[2][1])  # tile the ray really crosses
        self.assertEqual(".", env.terrain[3][2])  # tile the ray really crosses
        self.assertFalse(env.has_line_of_sight((1, 1), (4, 2)))
        # ta sama para pod axis8 jest niewidoczna juz z powodu geometrii
        axis8 = self.make_env(*rows, line_of_sight={"geometry": "axis8"})
        self.assertFalse(axis8.has_line_of_sight((1, 1), (4, 2)))

    def test_unknown_line_of_sight_rule_is_rejected(self):
        with self.assertRaises(ValueError):
            self.make_env("#####", "#E.X#", "#####", line_of_sight={"geometry": "bresenham"})


if __name__ == "__main__":
    unittest.main()
