import json
import unittest

from src.minidungeons.application import GameService
from src.minidungeons.errors import GameNotFoundError, InvalidGameActionError, MapNotFoundError


class GameServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GameService()

    def test_catalog_exposes_all_maps_and_non_standard_map05_size(self) -> None:
        maps = self.service.list_maps()
        self.assertEqual(11, len(maps))
        map05 = next(item for item in maps if item["id"] == "map05")
        self.assertEqual((14, 11), (map05["rows"], map05["columns"]))

    def test_game_snapshot_is_json_serializable_and_has_backend_contract(self) -> None:
        snapshot = self.service.create_game("map01")
        json.dumps(snapshot)
        self.assertEqual("map01", snapshot["map"]["id"])
        self.assertIsInstance(snapshot["state"]["hero_position"], list)
        self.assertEqual(2, len(snapshot["state"]["hero_position"]))
        self.assertEqual(4, len(snapshot["persona_utilities"]))
        self.assertTrue(snapshot["legal_actions"])
        self.assertIn("board", snapshot)

    def test_legal_action_changes_state_and_returns_transition(self) -> None:
        snapshot = self.service.create_game("map01")
        action = snapshot["legal_actions"][0]
        result = self.service.apply_action(
            snapshot["session_id"],
            kind=action["kind"],
            direction=action["direction"],
            target_id=action["target_id"],
        )
        self.assertEqual(1, result["state"]["metrics"]["turns"])
        self.assertIn("last_transition", result)

    def test_reset_and_delete_game(self) -> None:
        snapshot = self.service.create_game("map02")
        session_id = snapshot["session_id"]
        self.service.reset_game(session_id)
        self.service.delete_game(session_id)
        with self.assertRaises(GameNotFoundError):
            self.service.get_game(session_id)

    def test_expected_errors_are_typed(self) -> None:
        with self.assertRaises(MapNotFoundError):
            self.service.create_game("map99")
        snapshot = self.service.create_game("map01")
        with self.assertRaises(InvalidGameActionError):
            self.service.apply_action(snapshot["session_id"], kind="wait")

    def test_unmanaged_environment_is_ready_for_mcts_cloning(self) -> None:
        environment = self.service.create_environment("map03")
        clone = environment.clone()
        clone.step(clone.legal_actions()[0])
        self.assertNotEqual(environment.state_key(), clone.state_key())


if __name__ == "__main__":
    unittest.main()
