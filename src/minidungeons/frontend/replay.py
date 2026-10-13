"""Odtwarzacz partii agentow (UCB1, evolved, PPO) ze sladow `*_paths.jsonl`.

Silnik jest deterministyczny, wiec zapisane akcje odtwarzaja partie co do tury.
Kilka `--results` naraz pozwala przelaczac agentow na tej samej mapie i probie.

    python -m minidungeons.frontend.replay --results data/results/ucb1_bfs.csv \
        data/results/ours_bfs_fix.csv data/results/rl_eval/ppo_gen_argmax_runner.csv --map map08
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pygame

from minidungeons.domain import Action, MiniDungeon
from minidungeons.domain.personas import PERSONA_NAMES
from minidungeons.frontend import game_loop as board
from minidungeons.frontend.heatmap import load_outcomes
from minidungeons.infrastructure.paths import MD2_BENCHMARK_DIR
from minidungeons.infrastructure.traces import load_traces, trace_path_for

HUD_HEIGHT = 96
# pierwszy pasujacy prefiks nazwy pliku wygrywa, wiec dluzsze prefiksy ida wczesniej
LABELS = (("ucb1", "UCB1 (baseline)"), ("ours", "MCTS evolved"),
          ("ppo_gen_lb", "PPO generator, bonus 0,25"), ("ppo_gen", "PPO generator"),
          ("ppo_ego11_lb", "PPO 11 map, bonus 0,25"), ("ppo_ego11", "PPO 11 map"),
          ("ppo_ego", "PPO 6 map"), ("ppo", "PPO"))
HELP = "Spacja pauza  <- -> krok  Tab agent  P persona  M mapa  N proba  +/- tempo  Esc"


def parse_action(token: str) -> Action:
    kind, _, value = token.partition(":")
    return Action.move(value) if kind == "move" else Action.throw(int(value))


class Agent:
    def __init__(self, results: Path) -> None:
        self.name = next((label for prefix, label in LABELS if results.stem.startswith(prefix)),
                         results.stem)
        self.outcomes = load_outcomes(results)
        self.traces = {(t["persona"], t["map"], int(t["trial"])): t
                       for t in load_traces(trace_path_for(results))}


class Replay:
    def __init__(self, agents: list[Agent], persona: str, map_name: str, trial: int) -> None:
        self.agents, self.agent = agents, 0
        self.persona, self.map_name, self.trial = persona, map_name, trial
        self.env: MiniDungeon | None = None
        self.actions: list[Action] = []
        self.cursor = 0
        self.load()

    @property
    def key(self) -> tuple[str, str, int]:
        return self.persona, self.map_name, self.trial

    def maps(self) -> list[str]:
        return sorted({key[1] for key in self.agents[self.agent].traces})

    def load(self) -> None:
        trace = self.agents[self.agent].traces.get(self.key)
        if self.env is None or self.env.map_path.stem != self.map_name:
            self.env = MiniDungeon(MD2_BENCHMARK_DIR / f"{self.map_name}.txt")
        self.actions = [parse_action(a) for a in trace["actions"]] if trace else []
        self.seek(0)

    def seek(self, cursor: int) -> None:
        self.env.reset()
        self.cursor = max(0, min(cursor, len(self.actions)))
        for action in self.actions[:self.cursor]:
            self.env.step(action)

    def advance(self) -> None:
        if self.cursor < len(self.actions) and not self.env.done:
            self.env.step(self.actions[self.cursor])
            self.cursor += 1

    def cycle(self, attribute: str, options: list, step: int = 1) -> None:
        current = getattr(self, attribute)
        setattr(self, attribute, options[(options.index(current) + step) % len(options)])
        self.load()


def hud_render(screen, replay: Replay, speed: float, paused: bool) -> None:
    env = replay.env
    top = board.block_max_size * env.height + 6
    agent = replay.agents[replay.agent]
    outcome = agent.outcomes.get(replay.key)
    result = {True: "wygrana", False: "przegrana", None: "brak sladu"}[
        outcome if replay.actions else None]
    lines = [
        (f"[{replay.agent + 1}/{len(replay.agents)}] {agent.name}   {replay.persona}   "
         f"{replay.map_name}   proba {replay.trial}", 24, board.COLOR_TEXT),
        (f"tura {replay.cursor}/{len(replay.actions)}   HP {env.hero_hp}   wynik: {result}   "
         f"{speed:g} ruch/s{'   PAUZA' if paused else ''}", 20, board.COLOR_TEXT),
        (HELP, 18, board.COLOR_TEXT_DIM),
    ]
    for index, (text, size, color) in enumerate(lines):
        screen.blit(board.font(size).render(text, True, color), (10, top + index * 26))


def run(replay: Replay, speed: float) -> None:
    clock = pygame.time.Clock()
    paused, elapsed = False, 0.0
    size = None
    while True:
        env = replay.env
        wanted = (max(board.block_max_size * env.width, 760),
                  board.block_max_size * env.height + HUD_HEIGHT)
        if wanted != size:
            size = wanted
            screen = pygame.display.set_mode(size)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type != pygame.KEYDOWN:
                continue
            key = event.key
            if key in (pygame.K_ESCAPE, pygame.K_q):
                return
            if key == pygame.K_SPACE:
                paused = not paused
            elif key == pygame.K_RIGHT:
                replay.advance()
            elif key == pygame.K_LEFT:
                replay.seek(replay.cursor - 1)
            elif key == pygame.K_r:
                replay.seek(0)
            elif key == pygame.K_TAB:
                replay.cycle("agent", list(range(len(replay.agents))))
            elif key == pygame.K_p:
                replay.cycle("persona", list(PERSONA_NAMES))
            elif key == pygame.K_m:
                replay.cycle("map_name", replay.maps())
            elif key == pygame.K_n:
                replay.trial = (replay.trial + 1) % 50
                replay.load()
            elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                speed = min(speed * 2, 64)
            elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                speed = max(speed / 2, 0.5)

        elapsed += clock.tick(60) / 1000
        if not paused and elapsed >= 1 / speed:
            elapsed = 0.0
            replay.advance()

        screen.fill(board.COLOR_OUTLINE)
        board.background_render(screen, env)
        board.object_layer_render(screen, env)
        board.javelin_render(screen, env)
        board.npc_layer_render(screen, env)
        board.player_render(screen, env)
        hud_render(screen, replay, speed, paused)
        if env.done:
            board.banner_render(screen, env)
        pygame.display.flip()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", nargs="+", type=Path, required=True)
    parser.add_argument("--persona", choices=PERSONA_NAMES, default="runner")
    parser.add_argument("--map", default="map08")
    parser.add_argument("--trial", type=int, default=0)
    parser.add_argument("--speed", type=float, default=6.0, help="ruchy na sekunde")
    parser.add_argument("--tile-size", type=int, default=None)
    args = parser.parse_args(argv)
    if args.tile_size:
        board.set_block_size(args.tile_size)
    agents = [Agent(path) for path in args.results]
    pygame.init()
    pygame.display.set_caption("MiniDungeons 2 - odtwarzacz partii")
    try:
        run(Replay(agents, args.persona, args.map, args.trial), args.speed)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
