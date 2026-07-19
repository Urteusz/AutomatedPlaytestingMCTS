from pathlib import Path
import tempfile
import unittest

from src.minidungeons.domain import Action, MiniDungeon, load_personas, load_rules, utility_from_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAP_DIR = PROJECT_ROOT / "data" / "maps" / "md2" / "benchmark"


class RulesEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)

    def make_env(self, *rows, portal_pairs=None):
        path = Path(self.temp_directory.name) / "fixture.txt"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return MiniDungeon(path, portal_pairs=portal_pairs)

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


if __name__ == "__main__":
    unittest.main()
