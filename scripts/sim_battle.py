"""CLI for running a battle simulation.

Usage:
    python scripts/sim_battle.py <name> [trials] [hp]
    python scripts/sim_battle.py all_ch1 10000 60

<name> can be:
  - A single enemy name (e.g. ice_pufflet) — runs solo
  - A fight composition name (e.g. p1_neutral_black_firant_x2)
  - "all" — every single-enemy
  - "all_ch1" — every chapter 1 fight composition
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dd_agent.sim.enemies import ENEMIES, FIGHTS_CH1_ALL
from dd_agent.sim.monte_carlo import run_trials, starter_player


def simulate_one(label: str, factory, trials: int, hp: int):
    metrics = run_trials(
        lambda: starter_player(hp=hp, max_hp=60),
        factory,
        trials=trials,
    )
    print(f"\n=== {label} (HP={hp}/60, {trials} trials) ===")
    print(metrics.pretty())


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/sim_battle.py <name|all|all_ch1> [trials] [hp]")
        print(f"enemies: {', '.join(sorted(ENEMIES))}")
        print(f"fights: {', '.join(sorted(FIGHTS_CH1_ALL))}")
        sys.exit(1)

    name = sys.argv[1]
    trials = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    hp = int(sys.argv[3]) if len(sys.argv) > 3 else 60

    if name == "all":
        for n in sorted(ENEMIES):
            factory = lambda n=n: [ENEMIES[n]()]
            simulate_one(n, factory, trials, hp)
    elif name == "all_ch1":
        for n in sorted(FIGHTS_CH1_ALL):
            simulate_one(n, FIGHTS_CH1_ALL[n], trials, hp)
    elif name in FIGHTS_CH1_ALL:
        simulate_one(name, FIGHTS_CH1_ALL[name], trials, hp)
    elif name in ENEMIES:
        simulate_one(name, lambda: [ENEMIES[name]()], trials, hp)
    else:
        print(f"unknown name: {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()
