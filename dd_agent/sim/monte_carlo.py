"""Monte Carlo runner for battle simulation (multi-enemy aware)."""
from dataclasses import dataclass
import random
import statistics

from .battle import simulate_battle, PlayerState
from .sides import make_starter_dice


@dataclass
class Metrics:
    trials: int
    p_win: float
    mean_turns: float
    mean_hp_end: float
    p05_hp_end: int
    p50_hp_end: int
    p95_hp_end: int
    worst_hp_end: int
    mean_damage_taken: float
    max_damage_taken: int
    mean_damage_dealt: float
    mean_points: float
    p05_points: int
    p50_points: int
    p95_points: int
    mean_curses: float

    def pretty(self) -> str:
        return (
            f"  trials           = {self.trials}\n"
            f"  P(win)           = {self.p_win*100:5.1f}%\n"
            f"  turns            mean={self.mean_turns:5.1f}\n"
            f"  HP end           mean={self.mean_hp_end:5.1f}   "
            f"p5/50/95={self.p05_hp_end}/{self.p50_hp_end}/{self.p95_hp_end}   "
            f"worst={self.worst_hp_end}\n"
            f"  dmg taken        mean={self.mean_damage_taken:5.1f}   max={self.max_damage_taken}\n"
            f"  dmg dealt        mean={self.mean_damage_dealt:5.1f}\n"
            f"  points           mean={self.mean_points:6.0f}   "
            f"p5/50/95={self.p05_points}/{self.p50_points}/{self.p95_points}\n"
            f"  curses received  mean={self.mean_curses:4.2f}\n"
        )


def _pct(values, p):
    sv = sorted(values)
    idx = int(len(sv) * p / 100)
    return sv[min(idx, len(sv) - 1)]


def run_trials(
    make_player,
    enemies_factory,  # callable returning list[Enemy]
    trials: int = 10000,
    seed_base: int = 0,
    chapter: int = 1,
) -> Metrics:
    results = []
    for i in range(trials):
        player = make_player()
        enemies = enemies_factory()
        if not isinstance(enemies, list):
            enemies = [enemies]
        rng = random.Random(seed_base + i)
        res = simulate_battle(player, enemies, rng, chapter=chapter)
        results.append(res)

    hp_ends = [r.player_hp_end for r in results]
    turns = [r.turns for r in results]
    dmg_taken = [r.damage_taken for r in results]
    dmg_dealt = [r.damage_dealt for r in results]
    points = [r.total_points for r in results]
    curses = [r.curses_received for r in results]

    return Metrics(
        trials=trials,
        p_win=sum(1 for r in results if r.won) / trials,
        mean_turns=statistics.mean(turns),
        mean_hp_end=statistics.mean(hp_ends),
        p05_hp_end=_pct(hp_ends, 5),
        p50_hp_end=_pct(hp_ends, 50),
        p95_hp_end=_pct(hp_ends, 95),
        worst_hp_end=min(hp_ends),
        mean_damage_taken=statistics.mean(dmg_taken),
        max_damage_taken=max(dmg_taken),
        mean_damage_dealt=statistics.mean(dmg_dealt),
        mean_points=statistics.mean(points),
        p05_points=_pct(points, 5),
        p50_points=_pct(points, 50),
        p95_points=_pct(points, 95),
        mean_curses=statistics.mean(curses),
    )


def starter_player(hp: int = 60, max_hp: int = 60) -> PlayerState:
    return PlayerState(hp=hp, max_hp=max_hp, dice=make_starter_dice())
