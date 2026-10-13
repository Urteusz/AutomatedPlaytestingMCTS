"""Trening MaskablePPO jednej persony na 6 mapach treningowych.

Co `--eval-every` krokow polityka (argmax, deterministyczna jak gra) gra raz kazda
z 11 map; wynik idzie do `curve.csv` i TensorBoardu - to krzywa uczenia i
sample efficiency. Opcje srodowiska ida do `config.json` obok modelu, wiec ocena
odtwarza dokladnie to srodowisko, na ktorym model sie uczyl. `model.zip` to punkt
kontrolny z najwyzsza srednia utility na mapach treningowych (jak wybor runu GP po
mapach treningowych), `model_last.zip` - stan po ostatnim kroku; `--resume` go dotrenowuje.

    python -m minidungeons.rl.train --persona runner --timesteps 5000000 --out data/results/ppo_ego
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

import torch
from gymnasium import spaces
from sb3_contrib import MaskablePPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.vec_env import SubprocVecEnv, VecEnvWrapper, VecNormalize
from torch import nn

from minidungeons.domain.gp_fitness import TRAINING_MAP_NAMES
from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.infrastructure.paths import RESULTS_DIR
from minidungeons.rl.env import RADIUS, MiniDungeonsEnv
from minidungeons.rl.worker import serve

ALL_MAPS = tuple(f"map{index:02d}" for index in range(1, 12))
CURVE_FIELDS = ("timesteps", "seconds", "map", "win", "died", "utility", "turns",
                "monster_ratio", "potion_ratio", "treasure_ratio")


class EgoCNN(BaseFeaturesExtractor):
    """Widok wokol bohatera: konwolucje z krokiem 2 (39 -> 5) widza cala mape, a surowe
    pola 7x7 wokol bohatera daja precyzje tam, gdzie decyduje sie ruch."""

    LOCAL = 3

    def __init__(self, observation_space: spaces.Box, features_dim: int = 256) -> None:
        super().__init__(observation_space, features_dim)
        channels = observation_space.shape[0]
        self.net = nn.Sequential(
            nn.Conv2d(channels, 32, 3, padding=1), nn.ReLU(),
            nn.Conv2d(32, 64, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=2, padding=1), nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=2, padding=1), nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            size = self.net(torch.zeros(1, *observation_space.shape)).shape[1]
        size += channels * (2 * self.LOCAL + 1) ** 2
        self.head = nn.Sequential(nn.Linear(size, features_dim), nn.ReLU())

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        near = slice(RADIUS - self.LOCAL, RADIUS + self.LOCAL + 1)
        local = observations[:, :, near, near].flatten(1)
        return self.head(torch.cat((self.net(observations), local), dim=1))


class LightSubprocVecEnv(SubprocVecEnv):
    """`SubprocVecEnv` z workerem z `rl/worker.py`. `spawn` importuje w dziecku modul
    glowny (ten plik, a z nim torch), wiec na czas startu procesow jest on ukryty."""

    def __init__(self, env_fns: list[Callable[[], MiniDungeonsEnv]]) -> None:
        self.waiting, self.closed = False, False
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # bufory na watek: ~0,4 GB na proces
        ctx = mp.get_context("spawn")
        self.remotes, self.work_remotes = zip(*[ctx.Pipe() for _ in env_fns], strict=True)
        self.processes = []
        main = sys.modules["__main__"]
        hidden = {name: main.__dict__.pop(name) for name in ("__spec__", "__file__")
                  if name in main.__dict__}
        main.__spec__ = None
        try:
            for work_remote, remote, env_fn in zip(self.work_remotes, self.remotes, env_fns,
                                                   strict=True):
                process = ctx.Process(target=serve, args=(work_remote, remote, env_fn),
                                      daemon=True)
                process.start()
                self.processes.append(process)
                work_remote.close()
        finally:
            main.__dict__.update(hidden)
        self.remotes[0].send(("get_spaces", None))
        observation_space, action_space = self.remotes[0].recv()
        super(SubprocVecEnv, self).__init__(len(env_fns), observation_space, action_space)


class InfoMasks(VecEnvWrapper):
    """Maski przychodza z procesow w `info` razem z obserwacja; bez tego MaskablePPO
    pyta o nie kazdy proces osobnym rundtripem przy kazdym kroku."""

    def reset(self):
        observations = self.venv.reset()
        self.masks = [info["action_mask"] for info in self.venv.reset_infos]
        return observations

    def step_wait(self):
        observations, rewards, dones, infos = self.venv.step_wait()
        resets = self.venv.reset_infos
        self.masks = [(reset if done else info)["action_mask"]
                      for info, reset, done in zip(infos, resets, dones, strict=True)]
        return observations, rewards, dones, infos

    def env_method(self, method_name, *args, indices=None, **kwargs):
        if method_name == "action_masks" and indices is None:
            return self.masks
        return self.venv.env_method(method_name, *args, indices=indices, **kwargs)


def env_options(model_dir: Path) -> dict:
    """Opcje srodowiska, na ktorym uczyl sie model z `model_dir`."""

    options = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    options.pop("view", None)  # klucz z czasow, gdy byl tez widok calej planszy
    return options


def play(model: MaskablePPO, env: MiniDungeonsEnv, map_name: str) -> dict:
    observation, info = env.reset(options={"map": map_name})
    done = False
    while not done:
        action, _ = model.predict(observation, action_masks=env.action_masks(), deterministic=True)
        observation, _, terminated, truncated, info = env.step(int(action))
        done = terminated or truncated
    metrics = info["metrics"]
    return {
        "map": map_name, "win": int(info["win"]), "died": int(info["died"]),
        "utility": env.utility(), "turns": info["turns"],
        "monster_ratio": metrics["monster_ratio"], "potion_ratio": metrics["potion_ratio"],
        "treasure_ratio": metrics["treasure_ratio"],
    }


class CurveCallback(BaseCallback):
    def __init__(self, env: MiniDungeonsEnv, every: int, path: Path) -> None:
        super().__init__()
        self.env, self.every, self.path = env, every, path
        self.next_eval = 0
        self.started = time.perf_counter()
        self.best_path = path.parent / "best.json"
        self.best = (json.loads(self.best_path.read_text(encoding="utf-8"))["train_utility"]
                     if self.best_path.exists() else float("-inf"))

    def _on_step(self) -> bool:
        if self.num_timesteps >= self.next_eval:
            self.next_eval = self.num_timesteps + self.every
            self.evaluate()
        return True

    def evaluate(self) -> None:
        rows = [play(self.model, self.env, name) for name in ALL_MAPS]
        elapsed = round(time.perf_counter() - self.started, 1)
        new_file = not self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CURVE_FIELDS)
            if new_file:
                writer.writeheader()
            for row in rows:
                writer.writerow({"timesteps": self.num_timesteps, "seconds": elapsed, **row})
        train = [row for row in rows if row["map"] in self.env.map_names]
        score = sum(row["utility"] for row in train) / len(train)
        self.model.save(self.path.parent / "model_last")
        if score >= self.best:
            self.best = score
            self.model.save(self.path.parent / "model")
            self.best_path.write_text(json.dumps(
                {"timesteps": self.num_timesteps, "train_utility": score}), encoding="utf-8")
        for label, subset in (("train", train), ("all", rows)):
            for key in ("win", "utility", "died"):
                self.logger.record(f"eval_{label}/{key}", sum(r[key] for r in subset) / len(subset))


def _max_wait(value: str) -> int | None:
    return None if value == "off" else int(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--persona", choices=PERSONA_NAMES, required=True)
    parser.add_argument("--timesteps", type=int, default=5_000_000)
    parser.add_argument("--envs", type=int, default=12)
    parser.add_argument("--eval-every", type=int, default=100_000)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--pe-portals", choices=("on", "off"), default="on")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--win-bonus", type=float, default=1.0)
    parser.add_argument("--augment", action=argparse.BooleanOptionalAction, default=True,
                        help="losowe symetrie map treningowych")
    parser.add_argument("--ent-coef", type=float, default=0.02)
    parser.add_argument("--norm-reward", action=argparse.BooleanOptionalAction, default=True,
                        help="VecNormalize nagrody: kara -5 za smierc dominuje skale zwrotu")
    parser.add_argument("--max-wait", type=_max_wait, default=4,
                        help="limit czekania tam i z powrotem; 'off' wylacza maske petli")
    parser.add_argument("--shield", type=int, default=0,
                        help="glebokosc tarczy przed smiercia (0 = wylaczona)")
    parser.add_argument("--generated", type=float, default=0.0,
                        help="udzial map z rl/mapgen.py w treningu (0-1)")
    parser.add_argument("--maps", nargs="+", default=list(TRAINING_MAP_NAMES),
                        help="mapy treningowe; domyslnie 6 map fitnessu GP")
    parser.add_argument("--resume", action="store_true",
                        help="dotrenuj model_last.zip (albo model.zip starszych runow)")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "ppo")
    args = parser.parse_args()

    out = args.out / args.persona
    out.mkdir(parents=True, exist_ok=True)
    options = dict(max_steps=args.max_steps, pe_portals=args.pe_portals,
                   win_bonus=args.win_bonus, max_wait=args.max_wait, shield=args.shield,
                   generated=args.generated)
    (out / "config.json").write_text(json.dumps(options, indent=2), encoding="utf-8")
    (out / "maps.json").write_text(json.dumps(args.maps), encoding="utf-8")

    vec_env = InfoMasks(LightSubprocVecEnv(
        [partial(MiniDungeonsEnv, args.persona, tuple(args.maps), augment=args.augment, **options)]
        * args.envs))
    if args.norm_reward:
        vec_env = VecNormalize(vec_env, norm_obs=False, norm_reward=True, gamma=0.995)
    previous = next((path for path in (out / "model_last.zip", out / "model.zip")
                     if path.exists()), None) if args.resume else None
    if previous is not None:
        model = MaskablePPO.load(previous, env=vec_env, device=args.device,
                                 tensorboard_log=str(out / "tb"))
    else:
        model = MaskablePPO(
            "CnnPolicy", vec_env, seed=args.seed, device=args.device, verbose=0,
            n_steps=512, batch_size=1024, n_epochs=4, gamma=0.995, ent_coef=args.ent_coef,
            policy_kwargs=dict(features_extractor_class=EgoCNN,
                               normalize_images=True),
            tensorboard_log=str(out / "tb"),
        )
    callback = CurveCallback(MiniDungeonsEnv(args.persona, tuple(args.maps), **options),
                             args.eval_every, out / "curve.csv")
    model.learn(args.timesteps, callback=callback, reset_num_timesteps=previous is None)
    callback.evaluate()
    vec_env.close()


if __name__ == "__main__":
    main()
