"""Mine committed run data for dice setups that land near 50% winrate
against a target big-baddie, so we have calibrated test beds for
food-effect simulations.

Usage:
    python scripts/mine_sim_setups.py               # all enemies
    python scripts/mine_sim_setups.py wendibrrr     # single enemy

Walks every subdirectory under data/full_runs/, finds prefight JSONs
whose monster roster matches a known Ch1 big-baddie (or boss), loads
the player's dice + HP from that prefight, runs the sim N times, and
prints every setup whose winrate lands in [40%, 60%]. The setup with
the sample count closest to 50% is marked with a ★.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dd_agent.sim.battle import PlayerState, simulate_battle
from dd_agent.sim.enemies import (
    big_cheeze_onslaught, big_cheeze_shield, black_firant, blue_firant,
    detonox, firant_queen_solo, ganondwarf, gorgon_zola, pterrordactyl,
    wendibrrr, zomboid_horde,
)
from scripts.analyze_run import live_ability_to_side
from dd_agent.sim.sides import Die


# Target fights keyed by a short label. Each value is a (factory, matcher)
# tuple: factory returns a fresh enemy list, matcher detects this fight
# in a monster-name list.
def _names_contain(names, needed):
    lowered = [n.lower() for n in names]
    return all(any(n in l for l in lowered) for n in needed)


TARGETS = {
    # --- Chapter 1 ---
    "wendibrrr": (
        lambda: [wendibrrr()],
        lambda names: _names_contain(names, ["wendibrrr"]),
        1,
    ),
    "firant_queen_pack": (
        lambda: [black_firant(), black_firant(), firant_queen_solo(), blue_firant()],
        lambda names: _names_contain(names, ["firant queen"]),
        1,
    ),
    "gorgon_zola": (
        lambda: [gorgon_zola()],
        lambda names: _names_contain(names, ["gorgon"]),
        1,
    ),
    "ganondwarf": (
        lambda: [ganondwarf()],
        lambda names: _names_contain(names, ["ganondwarf"]),
        1,
    ),
    # --- Chapter 2 ---
    "pterrordactyl": (
        lambda: [pterrordactyl()],
        lambda names: _names_contain(names, ["pterrordactyl"]),
        2,
    ),
    "detonox": (
        lambda: [detonox()],
        lambda names: _names_contain(names, ["detonox"]),
        2,
    ),
    "big_cheeze_onslaught": (
        lambda: [big_cheeze_onslaught()],
        lambda names: _names_contain(names, ["big cheeze"])
                      and _names_contain(names, ["onslaught"]),
        2,
    ),
    "big_cheeze_shield": (
        lambda: [big_cheeze_shield()],
        lambda names: _names_contain(names, ["big cheeze"])
                      and _names_contain(names, ["shield"]),
        2,
    ),
    "zomboid_horde": (
        lambda: [zomboid_horde()],
        # Real roster is 5 sequential zomboids. Detect on any of them.
        lambda names: _names_contain(names, ["cryonic"])
                      or _names_contain(names, ["necrotic"])
                      or (_names_contain(names, ["infernal"]) and
                          _names_contain(names, ["crystal zomboid"])),
        2,
    ),
}

TRIALS = 50
BAND = (0.40, 0.60)
# Per-target override: some enemies don't yield calibrated setups in the
# 40-60% band because the bot either wrecks them easily or can't touch
# them. These still need a setup for food-effect testing, so we relax
# the band into whatever bucket has samples.
BAND_OVERRIDE = {
    "gorgon_zola": (0.20, 0.40),
}


def prefight_to_player(prefight_path: Path) -> tuple[PlayerState, list[str]] | None:
    try:
        data = json.loads(prefight_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    state = data.get("state") or {}
    player = state.get("player") or {}
    monsters = state.get("monsters") or []
    if not player.get("dice"):
        return None
    # Build sim dice from the prefight dice JSON.
    sim_dice = []
    for i, d in enumerate(player.get("dice") or []):
        sides = [live_ability_to_side(a) for a in (d.get("ability") or [])]
        if sides:
            sim_dice.append(Die(name=f"Die {i + 1}", sides=sides))
    if not sim_dice:
        return None
    hp = int(player.get("health") or 60)
    max_hp = int(player.get("maxHealth") or player.get("max_health") or 60)
    names = [m.get("name") or "" for m in monsters]
    ps = PlayerState(hp=hp, max_hp=max_hp, dice=sim_dice)
    return ps, names


def winrate(player: PlayerState, enemy_factory, trials: int = TRIALS,
             chapter: int = 1, seed: int = 42) -> tuple[float, float]:
    """Return (winrate, mean_hp_end_on_wins). The second value lets us
    evaluate food effects that preserve HP even when the fight is already
    winnable — fast kills = less damage taken."""
    rng = random.Random(seed)
    wins = 0
    hp_ends = []
    for t in range(trials):
        ps = PlayerState(
            hp=player.hp, max_hp=player.max_hp,
            dice=[Die(name=d.name, sides=list(d.sides)) for d in player.dice],
        )
        enemies = enemy_factory()
        trial_rng = random.Random(rng.random())
        result = simulate_battle(ps, enemies, trial_rng, chapter=chapter)
        if result.won:
            wins += 1
            hp_ends.append(result.player_hp_end)
    mean_hp = sum(hp_ends) / len(hp_ends) if hp_ends else 0
    return wins / trials, mean_hp


def dice_fingerprint(dice: list[Die]) -> str:
    parts = []
    for d in dice:
        sides = sorted(str(s)[:30] for s in d.sides)
        parts.append(f"{d.name}[{len(d.sides)}]:" + "|".join(s[:15] for s in sides[:6]))
    return "  ".join(parts)


def main():
    target_filter = sys.argv[1] if len(sys.argv) > 1 else None
    root = Path("C:/dev/dontDieAi/data/full_runs")
    if not root.exists():
        print(f"no full_runs dir at {root}")
        return 1

    per_target: dict[str, list] = {k: [] for k in TARGETS}

    run_dirs = sorted(root.iterdir())
    print(f"scanning {len(run_dirs)} run dirs...")
    for rdir in run_dirs:
        if not rdir.is_dir():
            continue
        for pf in sorted(rdir.glob("*_prefight.json")):
            loaded = prefight_to_player(pf)
            if loaded is None:
                continue
            player, names = loaded
            for tname, (factory, matcher, _ch) in TARGETS.items():
                if target_filter and target_filter != tname:
                    continue
                if matcher(names):
                    per_target[tname].append((rdir.name, pf.name, player))
                    break

    print()
    for tname, hits in per_target.items():
        if target_filter and target_filter != tname:
            continue
        if not hits:
            print(f"=== {tname}: no prefight samples found ===\n")
            continue
        factory, _, chapter = TARGETS[tname]
        print(f"=== {tname}: {len(hits)} candidate setups, running {TRIALS} trials each ===")
        scored = []
        for rdir, pf_name, player in hits:
            wr, hp_end = winrate(player, factory, chapter=chapter)
            scored.append((wr, hp_end, rdir, pf_name, player))
        band = BAND_OVERRIDE.get(tname, BAND)
        band_center = (band[0] + band[1]) / 2
        in_band = [s for s in scored if band[0] <= s[0] <= band[1]]
        in_band.sort(key=lambda s: abs(s[0] - band_center))
        if not in_band:
            bins = {"<20%": 0, "20-40%": 0, "40-60%": 0, "60-80%": 0, ">80%": 0}
            for wr, _, _, _, _ in scored:
                if wr < 0.2: bins["<20%"] += 1
                elif wr < 0.4: bins["20-40%"] += 1
                elif wr < 0.6: bins["40-60%"] += 1
                elif wr < 0.8: bins["60-80%"] += 1
                else: bins[">80%"] += 1
            print(f"  no setups in [{band[0]:.0%}, {band[1]:.0%}]. distribution: {bins}\n")
            continue
        for i, (wr, hp_end, rdir, pf_name, player) in enumerate(in_band[:5]):
            mark = "★" if i == 0 else " "
            print(f"  {mark} {wr:.0%}  hp_in={player.hp}/{player.max_hp}  "
                  f"hp_end_on_win={hp_end:.0f}  {rdir}/{pf_name}")
            print(f"       {dice_fingerprint(player.dice)[:150]}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
