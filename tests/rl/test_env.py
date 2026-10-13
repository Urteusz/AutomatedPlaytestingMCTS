from __future__ import annotations

import random
import unittest

import numpy as np

# `rl/env.py` importuje `minidungeons.*`; porownania z konwencja MCTS musza isc
# przez te sama kopie modulu, bo `gp_fitness` podmienia atrybuty klasy silnika.
from minidungeons.domain import gp_fitness
from minidungeons.domain.engine import Action, MiniDungeon
from minidungeons.domain.personas import PERSONA_NAMES, utility
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR
from minidungeons.rl.env import (
    CHANNELS,
    EGO,
    RADIUS,
    SYMMETRIES,
    MiniDungeonsEnv,
    _load_level,
)

ALL_MAPS = tuple(f"map{index:02d}" for index in range(1, 12))


def random_walk(env: MiniDungeonsEnv, seed: int, length: int) -> list:
    """Losowa gra po legalnych akcjach; zwraca odegrane akcje silnika."""

    rng = random.Random(seed)
    played = []
    for _ in range(length):
        legal = np.flatnonzero(env.action_masks())
        if legal.size == 0:
            break
        action = int(rng.choice(list(legal)))
        played.append(env.decode(action))
        _, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break
    return played


def shortest_exit_path(env: MiniDungeonsEnv) -> list[int]:
    """BFS po ruchach od startu do wyjscia (map08 ma wyjscie 8 krokow od wejscia)."""

    from collections import deque

    env.reset()
    start = env.env.clone()
    queue = deque([(start, [])])
    seen = {start.state_key()}
    while queue:
        state, path = queue.popleft()
        for action in state.legal_actions():
            if action.kind != "move":
                continue
            child = state.clone()
            child.step(action)
            if child.metrics.reached_exit:
                return [*path, env.encode(action)]
            key = child.state_key()
            if not child.done and key not in seen and len(path) < 12:
                seen.add(key)
                queue.append((child, [*path, env.encode(action)]))
    raise AssertionError("brak sciezki do wyjscia")


class ObservationTests(unittest.TestCase):
    def test_ego_view_is_centred_on_the_hero(self) -> None:
        env = MiniDungeonsEnv("runner", maps=ALL_MAPS)
        proximity, wall = env.channel["proximity"], env.channel["wall"]
        for name in ALL_MAPS:
            observation, info = env.reset(options={"map": name})
            self.assertEqual(info["map"], name)
            self.assertEqual(observation.shape, (len(CHANNELS), EGO, EGO))
            self.assertTrue(env.observation_space.contains(observation), name)
            random_walk(env, seed=5, length=15)
            if env.env.done:
                continue
            observation = env._observation()
            row, column = env.env.hero_position
            for d_row, d_column in ((-1, 0), (0, 1), (1, 0), (0, -1)):
                cell = (row + d_row, column + d_column)
                seen = (RADIUS + d_row, RADIUS + d_column)
                blocked = env.env.terrain[cell[0]][cell[1]] == "#"
                self.assertEqual(observation[(wall, *seen)], 255 if blocked else 0, name)
                if not blocked:
                    expected = int(env._proximity(cell, env._level(name)[2]) * 255)
                    self.assertEqual(observation[(proximity, *seen)], expected, name)

    def test_outside_the_map_is_wall_in_the_ego_view(self) -> None:
        env = MiniDungeonsEnv("runner", maps=("map05",))
        observation, _ = env.reset()
        row, column = env.env.hero_position
        self.assertTrue((observation[env.channel["wall"], :RADIUS - row] == 255).all())
        self.assertTrue((observation[env.channel["wall"], :, :RADIUS - column] == 255).all())

    def test_seeded_reset_picks_the_same_map(self) -> None:
        first = [MiniDungeonsEnv("runner").reset(seed=seed)[1]["map"] for seed in range(8)]
        second = [MiniDungeonsEnv("runner").reset(seed=seed)[1]["map"] for seed in range(8)]
        self.assertEqual(first, second)


class ActionTests(unittest.TestCase):
    def test_mask_matches_legal_actions_and_round_trips(self) -> None:
        env = MiniDungeonsEnv("monster_killer", maps=ALL_MAPS)
        for index, name in enumerate(ALL_MAPS):
            env.reset(options={"map": name})
            rng = random.Random(index)
            for _ in range(60):
                legal = env.env.legal_actions()
                if not legal or env.env.done:
                    break
                mask = env.action_masks()
                self.assertEqual(mask.shape, (env.action_space.n,))
                self.assertEqual(int(mask.sum()), len(legal), name)
                for action in legal:
                    self.assertEqual(env.decode(env.encode(action)), action)
                env.step(env.encode(rng.choice(legal)))

    def test_mask_travels_in_info(self) -> None:
        env = MiniDungeonsEnv("completionist", maps=("map02",), max_wait=4)
        _, info = env.reset()
        rng = random.Random(2)
        for _ in range(100):
            np.testing.assert_array_equal(info["action_mask"], env.action_masks())
            action = int(rng.choice(list(np.flatnonzero(info["action_mask"]))))
            _, _, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                self.assertIn("metrics", info)
                break

    def test_masked_out_action_is_rejected(self) -> None:
        env = MiniDungeonsEnv("runner")
        env.reset(options={"map": "map01"})
        illegal = int(np.flatnonzero(~env.action_masks())[0])
        with self.assertRaises(ValueError):
            env.step(illegal)


class RewardTests(unittest.TestCase):
    def tearDown(self) -> None:
        gp_fitness._configure_conventions("binary", "combined")
        gp_fitness._configure_pe_portals("on")

    def test_rewards_sum_to_the_utility_gain(self) -> None:
        env = MiniDungeonsEnv("completionist", maps=("map02",), max_steps=10_000)
        env.reset()
        start = env.utility()
        total = 0.0
        rng = random.Random(3)
        for _ in range(200):
            legal = np.flatnonzero(env.action_masks())
            if legal.size == 0:
                break
            _, reward, terminated, truncated, _ = env.step(int(rng.choice(list(legal))))
            total += reward
            if terminated or truncated:
                break
        self.assertAlmostEqual(total, env.utility() - start, places=9)

    def test_win_bonus_is_paid_once_on_reaching_the_exit(self) -> None:
        plain = MiniDungeonsEnv("runner", maps=("map08",))
        bonus = MiniDungeonsEnv("runner", maps=("map08",), win_bonus=2.5)
        path = shortest_exit_path(plain)
        plain.reset()
        bonus.reset()
        gains = []
        for action in path:
            _, r_plain, *_ = plain.step(action)
            _, r_bonus, terminated, *_ = bonus.step(action)
            gains.append(r_bonus - r_plain)
        self.assertTrue(terminated and bonus.env.metrics.reached_exit)
        self.assertEqual(gains[:-1], [0.0] * (len(gains) - 1))
        self.assertAlmostEqual(gains[-1], 2.5)

    def test_utility_matches_the_mcts_convention(self) -> None:
        """Nagroda PPO musi byc ta sama funkcja, ktora MCTS propaguje w drzewie."""

        for pe_portals in ("on", "off"):
            for persona in PERSONA_NAMES:
                env = MiniDungeonsEnv(persona, maps=("map01",), pe_portals=pe_portals)
                env.reset()
                played = random_walk(env, seed=7, length=80)

                gp_fitness._configure_conventions("normalized", "mean3")
                gp_fitness._configure_pe_portals(pe_portals)
                reference = MiniDungeon(MD2_BENCHMARK_DIR / "map01.txt")
                for action in played:
                    reference.step(action)
                self.assertAlmostEqual(
                    env.utility(), utility(persona, reference), places=12,
                    msg=f"{persona} pe_portals={pe_portals}",
                )

    def test_portals_change_the_proximity_channel(self) -> None:
        on_env = MiniDungeonsEnv("runner", maps=("map01",), pe_portals="on")
        off_env = MiniDungeonsEnv("runner", maps=("map01",), pe_portals="off")
        proximity = on_env.channel["proximity"]
        on, off = on_env.reset()[0][proximity], off_env.reset()[0][proximity]
        self.assertFalse(np.array_equal(on, off))


class AugmentTests(unittest.TestCase):
    def test_flips_mirror_the_static_board(self) -> None:
        # statyczna plansza z marginesem RADIUS; obiekty nanosi dopiero obserwacja
        env = MiniDungeonsEnv("runner", maps=ALL_MAPS)
        env.reset(options={"map": "map01"})
        height, width = env.env.height, env.env.width
        inner = (slice(None), slice(RADIUS, RADIUS + height), slice(RADIUS, RADIUS + width))
        plain = env._level("map01")[1][inner]
        for flip, axes in (("v", (1,)), ("h", (2,)), ("vh", (1, 2))):
            flipped = env._level(f"map01:{flip}")[1][inner]
            for channel in ("wall", "proximity"):
                index = env.channel[channel]
                np.testing.assert_array_equal(
                    flipped[index], np.flip(plain, axes)[index], err_msg=flip
                )

    def test_transposed_map_keeps_walls_portals_and_exit_distances(self) -> None:
        for name in ("map01", "map05", "map09"):
            plain = _load_level(name)
            for symmetry in SYMMETRIES[1:]:
                level = _load_level(f"{name}:{symmetry}")
                plain_d = gp_fitness.exit_distances(plain, "on")
                level_d = gp_fitness.exit_distances(level, "on")
                self.assertEqual(sorted(plain_d.values()), sorted(level_d.values()),
                                 f"{name}:{symmetry}")
                self.assertEqual(len(plain.portal_links), len(level.portal_links))

    def test_unknown_symmetry_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _load_level("map01:x")

    def test_flipped_maps_play_legally(self) -> None:
        env = MiniDungeonsEnv("completionist", maps=("map02", "map05"), augment=True)
        seen = set()
        for seed in range(40):
            _, info = env.reset(seed=seed)
            seen.add(info["map"])
            random_walk(env, seed=seed, length=40)
        self.assertGreater(len(seen), 8)
        self.assertTrue(any(":t" in name for name in seen))


class LoopMaskTests(unittest.TestCase):
    def test_waiting_back_and_forth_is_capped(self) -> None:
        # minotaur idzie co ture, wiec powrot jest nowym stanem - czekanie, ale ograniczone
        env = MiniDungeonsEnv("runner", maps=("map08",), max_wait=2)
        env.reset()
        east, west = (env.encode(Action.move(d)) for d in "EW")
        for action in (east, west, east):
            self.assertTrue(env.action_masks()[action])
            env.step(action)
        self.assertFalse(env.action_masks()[west])
        self.assertTrue(env.action_masks()[east])

    def test_repeated_state_is_masked(self) -> None:
        # petla rzut w ogluszonego minotaura -> podniesienie oszczepu -> krok
        env = MiniDungeonsEnv("runner", maps=("map01",), max_wait=4)
        env.reset()
        moves = {d: Action.move(d) for d in "NESW"}
        script = [Action.throw(1), *[moves["E"]] * 4, Action.throw(0), moves["W"], moves["E"],
                  moves["W"], moves["W"], moves["E"], Action.throw(0), moves["W"], moves["E"]]
        for action in script:
            env.step(env.encode(action))
        throw = env.encode(Action.throw(0))
        self.assertIn(Action.throw(0), env.env.legal_actions())
        self.assertFalse(env.action_masks()[throw])

    def test_mask_is_never_empty_and_stays_legal(self) -> None:
        for name in ALL_MAPS:
            env = MiniDungeonsEnv("completionist", maps=(name,), max_wait=0)
            env.reset(seed=1)
            rng = random.Random(name)
            for _ in range(150):
                mask = env.action_masks()
                legal = {env.encode(action) for action in env.env.legal_actions()}
                self.assertTrue(mask.any())
                self.assertLessEqual(set(np.flatnonzero(mask)), legal)
                action = int(rng.choice(list(np.flatnonzero(mask))))
                _, _, terminated, truncated, _ = env.step(action)
                if terminated or truncated:
                    break

    def test_cached_child_states_match_a_fresh_step(self) -> None:
        masked = MiniDungeonsEnv("completionist", maps=("map03",), max_wait=4)
        plain = MiniDungeonsEnv("completionist", maps=("map03",))
        masked.reset()
        plain.reset()
        rng = random.Random(9)
        for _ in range(120):
            action = int(rng.choice(list(np.flatnonzero(masked.action_masks()))))
            first = masked.step(action)
            second = plain.step(action)
            self.assertEqual(masked.env.state_key(), plain.env.state_key())
            self.assertEqual(first[1], second[1])
            np.testing.assert_array_equal(first[0], second[0])
            if first[2] or first[3]:
                break

    def test_mask_is_off_by_default(self) -> None:
        env = MiniDungeonsEnv("runner", maps=("map08",))
        env.reset()
        east, west = (env.encode(Action.move(d)) for d in "EW")
        for _ in range(6):
            env.step(east)
            self.assertTrue(env.action_masks()[west])
            env.step(west)


class ShieldTests(unittest.TestCase):
    def test_shield_masks_only_deadly_actions(self) -> None:
        from minidungeons.rl.env import _survives

        for name in ALL_MAPS:
            env = MiniDungeonsEnv("monster_killer", maps=(name,), shield=2)
            plain = MiniDungeonsEnv("monster_killer", maps=(name,))
            env.reset(seed=3)
            plain.reset(seed=3)
            rng = random.Random(name)
            for _ in range(200):
                legal = np.flatnonzero(plain.action_masks())
                safe = [index for index in legal if _survives(env._child(int(index)), 1)]
                expected = set(safe) if safe else set(legal)
                self.assertEqual(set(np.flatnonzero(env.action_masks())), expected)
                action = int(rng.choice(sorted(expected)))
                first = env.step(action)
                plain.step(action)
                if first[2] or first[3]:
                    break

    def test_shield_is_off_by_default(self) -> None:
        env = MiniDungeonsEnv("runner", maps=("map04",))
        self.assertEqual(env.shield, 0)
        with self.assertRaises(ValueError):
            MiniDungeonsEnv("runner", shield=-1)


class EpisodeTests(unittest.TestCase):
    def test_episode_is_truncated_at_max_steps(self) -> None:
        env = MiniDungeonsEnv("runner", maps=("map03",), max_steps=5)
        env.reset()
        flags = []
        for _ in range(5):
            legal = np.flatnonzero(env.action_masks())
            _, _, terminated, truncated, info = env.step(int(legal[0]))
            flags.append((terminated, truncated))
            if terminated:
                break
        if not flags[-1][0]:
            self.assertEqual(flags[-1], (False, True))
            self.assertEqual(info["turns"], 5)
            self.assertTrue(all(not truncated for _, truncated in flags[:-1]))

    def test_invalid_arguments_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MiniDungeonsEnv("berserker")
        with self.assertRaises(ValueError):
            MiniDungeonsEnv("runner", max_steps=0)
        with self.assertRaises(ValueError):
            MiniDungeonsEnv("runner", pe_portals="maybe")
        with self.assertRaises(ValueError):
            MiniDungeonsEnv("runner", ic_mode="sum")


if __name__ == "__main__":
    unittest.main()
