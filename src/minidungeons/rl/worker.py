"""Proces srodowiska bez torcha - protokol `SubprocVecEnv._worker` z SB3.

Worker SB3 importuje pakiet `stable_baselines3`, a z nim torch z bibliotekami CUDA
(~1,4 GB zarezerwowanej pamieci na proces); ten modul importuje tylko srodowisko.
"""

from __future__ import annotations

from collections.abc import Callable
from multiprocessing.connection import Connection

import gymnasium as gym


def serve(remote: Connection, parent_remote: Connection, factory: Callable[[], gym.Env]) -> None:
    parent_remote.close()
    env = factory()
    while True:
        try:
            command, data = remote.recv()
        except (EOFError, KeyboardInterrupt):
            break
        if command == "step":
            observation, reward, terminated, truncated, info = env.step(data)
            done = terminated or truncated
            info["TimeLimit.truncated"] = truncated and not terminated
            reset_info = {}
            if done:
                info["terminal_observation"] = observation
                observation, reset_info = env.reset()
            remote.send((observation, reward, done, info, reset_info))
        elif command == "reset":
            options = {"options": data[1]} if data[1] else {}
            remote.send(env.reset(seed=data[0], **options))
        elif command == "get_spaces":
            remote.send((env.observation_space, env.action_space))
        elif command == "env_method":
            remote.send(getattr(env, data[0])(*data[1], **data[2]))
        elif command == "get_attr":
            remote.send(getattr(env, data))
        elif command == "has_attr":
            remote.send(hasattr(env, data))
        elif command == "set_attr":
            setattr(env, data[0], data[1])
            remote.send(None)
        elif command == "is_wrapped":
            remote.send(False)
        elif command == "render":
            remote.send(env.render())
        elif command == "close":
            env.close()
            remote.close()
            break
        else:
            raise NotImplementedError(f"`{command}` nie jest obslugiwane w workerze")
