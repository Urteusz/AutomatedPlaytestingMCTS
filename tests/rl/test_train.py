from __future__ import annotations

import json
import tempfile
import unittest
from functools import partial
from pathlib import Path

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3.common.vec_env import DummyVecEnv

from minidungeons.rl.env import MiniDungeonsEnv
from minidungeons.rl.train import (
    CURVE_FIELDS,
    CurveCallback,
    EgoCNN,
    InfoMasks,
    LightSubprocVecEnv,
    env_options,
    play,
)


class FeatureExtractorTests(unittest.TestCase):
    def test_features_have_the_declared_size(self) -> None:
        space = MiniDungeonsEnv("runner").observation_space
        extractor = EgoCNN(space, features_dim=64)
        batch = torch.zeros((3, *space.shape))
        self.assertEqual(tuple(extractor(batch).shape), (3, 64))


class InfoMasksTests(unittest.TestCase):
    def test_masks_match_the_environments_across_resets(self) -> None:
        factory = partial(MiniDungeonsEnv, "runner", maps=("map08",), max_steps=12, max_wait=2)
        wrapped = InfoMasks(DummyVecEnv([factory] * 3))
        wrapped.reset()
        rng = np.random.default_rng(0)
        for _ in range(40):
            masks = wrapped.env_method("action_masks")
            direct = wrapped.venv.env_method("action_masks")
            for mask, expected in zip(masks, direct, strict=True):
                np.testing.assert_array_equal(mask, expected)
            wrapped.step(np.array([rng.choice(np.flatnonzero(mask)) for mask in masks]))


class LightSubprocTests(unittest.TestCase):
    def test_matches_the_in_process_vector_env(self) -> None:
        factory = partial(MiniDungeonsEnv, "completionist", maps=("map08",), max_steps=15,
                          max_wait=2, shield=1)
        light = InfoMasks(LightSubprocVecEnv([factory] * 2))
        local = InfoMasks(DummyVecEnv([factory] * 2))
        try:
            light.seed(0)
            local.seed(0)
            np.testing.assert_array_equal(light.reset(), local.reset())
            rng = np.random.default_rng(1)
            for _ in range(30):
                masks = local.env_method("action_masks")
                for mask, expected in zip(light.env_method("action_masks"), masks, strict=True):
                    np.testing.assert_array_equal(mask, expected)
                actions = np.array([rng.choice(np.flatnonzero(mask)) for mask in masks])
                first, second = light.step(actions), local.step(actions)
                for left, right in zip(first[:3], second[:3], strict=True):
                    np.testing.assert_allclose(left, right, rtol=1e-6)
        finally:
            light.close()


class FirstLegalModel:
    """Polityka "pierwsza legalna akcja" z licznikiem zapisow - zamiast sieci."""

    def __init__(self) -> None:
        self.saved: list[str] = []
        self.logger = type("Logger", (), {"record": lambda *args: None})()

    def predict(self, observation, action_masks, deterministic):
        return int(np.flatnonzero(action_masks)[0]), None

    def save(self, path) -> None:
        self.saved.append(Path(path).name)


class BestCheckpointTests(unittest.TestCase):
    def test_model_is_the_best_checkpoint_on_training_maps(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            env = MiniDungeonsEnv("runner", maps=("map08",), max_steps=20)
            callback = CurveCallback(env, every=10, path=Path(folder) / "curve.csv")
            model = FirstLegalModel()
            callback.model = model
            callback.evaluate()
            self.assertEqual(model.saved, ["model_last", "model"])
            best = json.loads((Path(folder) / "best.json").read_text(encoding="utf-8"))
            callback.best = best["train_utility"] + 1.0
            callback.evaluate()
            self.assertEqual(model.saved[2:], ["model_last"])
            resumed = CurveCallback(env, every=10, path=Path(folder) / "curve.csv")
            self.assertEqual(resumed.best, best["train_utility"])


class ConfigTests(unittest.TestCase):
    def test_options_come_from_config_without_the_old_view_key(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            options = {"max_steps": 300, "pe_portals": "off", "win_bonus": 1.0, "max_wait": 4}
            (Path(folder) / "config.json").write_text(json.dumps({"view": "ego", **options}),
                                                      encoding="utf-8")
            self.assertEqual(env_options(Path(folder)), options)
            MiniDungeonsEnv("runner", **env_options(Path(folder)))


class PlayTests(unittest.TestCase):
    def test_untrained_policy_plays_a_legal_episode(self) -> None:
        env = MiniDungeonsEnv("treasure_collector", max_steps=30, max_wait=4, shield=1)
        model = MaskablePPO(
            "CnnPolicy", env, device="cpu", n_steps=32, batch_size=32,
            policy_kwargs=dict(features_extractor_class=EgoCNN, normalize_images=True),
        )
        row = play(model, env, "map05")
        self.assertEqual(row["map"], "map05")
        self.assertLessEqual(row["turns"], 30)
        self.assertLessEqual(set(row), set(CURVE_FIELDS))


if __name__ == "__main__":
    unittest.main()
