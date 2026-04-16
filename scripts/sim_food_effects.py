"""Simulate every food against each calibrated boss/big-baddie setup,
measure winrate delta + HP preservation delta vs a no-food baseline.

Usage:
    python scripts/sim_food_effects.py                  # all 6 enemies
    python scripts/sim_food_effects.py wendibrrr        # one enemy

Setups are the ★ picks from scripts/mine_sim_setups.py. Each food's
effect is approximated in-code (see _apply_food). Each (enemy, food)
cell runs TRIALS battles; baseline row is "— no food —".

The rank is by `score = 100*winrate_delta + hp_preservation_delta`,
treating a 1% winrate gain as worth 1 HP of preservation. That's a
user-tunable weight — update `_score_result()` if you want another mix.
"""
from __future__ import annotations

import copy
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dd_agent.sim.battle import PlayerState, simulate_battle
from dd_agent.sim.enemies import (
    big_cheeze_onslaught, black_firant, blue_firant, detonox,
    firant_queen_solo, ganondwarf, gorgon_zola, pterrordactyl, wendibrrr,
)
from dd_agent.sim.sides import Die, Side
from scripts.analyze_run import live_ability_to_side


TRIALS = 100
FULL_RUNS = Path("C:/dev/dontDieAi/data/full_runs")


# Each entry: (label, chapter, enemy_factory, prefight_path)
SETUPS = [
    ("wendibrrr", 1, lambda: [wendibrrr()],
     "20260415_041517_r7/0250_b07_prefight.json"),
    ("firant_queen_pack", 1,
     lambda: [black_firant(), black_firant(), firant_queen_solo(), blue_firant()],
     "20260415_141707_r2/0202_b06_prefight.json"),
    ("gorgon_zola", 1, lambda: [gorgon_zola()],
     "20260415_042416_r8/0217_b06_prefight.json"),
    ("ganondwarf", 1, lambda: [ganondwarf()],
     "20260415_052404_r17/0335_b09_prefight.json"),
    ("pterrordactyl", 2, lambda: [pterrordactyl()],
     "20260415_063056_r29/0442_b12_prefight.json"),
    ("detonox", 2, lambda: [detonox()],
     "20260415_063056_r29/0395_b11_prefight.json"),
]


FOODS = [
    "— no food —",
    "Brotein Bar MAX",
    "Ice Rice",
    "Brrrito Blockerito",
    "Boom Beans",
    "Heat Meat",
    "Godmode Guac",
    "Giga Juice",
    "Pickle",
    "Clutch Creme",
    "Rage Shake",
    "Snackrifice",
    "Scorch Sauce",
    "Crit Chips",
    "Toxipop",
]


def _load_player(prefight_path: Path) -> PlayerState:
    data = json.loads(prefight_path.read_text(encoding="utf-8"))
    state = data["state"]
    player = state["player"]
    sim_dice = []
    for i, d in enumerate(player.get("dice") or []):
        sides = [live_ability_to_side(a) for a in (d.get("ability") or [])]
        if sides:
            sim_dice.append(Die(name=f"Die {i+1}", sides=sides))
    hp = int(player.get("health") or 60)
    max_hp = int(player.get("maxHealth") or player.get("max_health") or 60)
    return PlayerState(hp=hp, max_hp=max_hp, dice=sim_dice)


def _clone_player(p: PlayerState) -> PlayerState:
    # Deep-copy dice (simulate_battle mutates Die.exhausted + Side fields
    # via Giga Juice etc.) plus a fresh numeric state.
    new_dice = []
    for die in p.dice:
        new_sides = [copy.copy(s) for s in die.sides]
        new_dice.append(Die(name=die.name, sides=new_sides))
    # Start each trial with only the base stats copied. Food-effect flags
    # get set fresh by _apply_food on the cloned player.
    return PlayerState(
        hp=p.hp, max_hp=p.max_hp, dice=new_dice,
        strength=p.strength, armor=p.armor,
        damage_mult=p.damage_mult, points_mult=p.points_mult,
        negate_debuffs=p.negate_debuffs,
    )


def _apply_food(food: str, player: PlayerState, enemies: list) -> None:
    """Mutate player / enemies in place to apply the food's effect.

    Approximations are documented inline. Foods marked NOT MODELED will
    produce no effect and show up identical to the no-food baseline.
    """
    if food == "— no food —":
        return

    if food == "Ice Rice":
        # "Negate the next 3 Debuffs" — direct sim support.
        player.negate_debuffs += 3
        return

    if food == "Brrrito Blockerito":
        # "Stack Block for the first 6 turns" — block carries through
        # player-phase resets for N turns (sim directly supports this
        # via PlayerState.block_stack_turns_remaining).
        player.block_stack_turns_remaining = 6
        return

    if food == "Heat Meat":
        # "+1x Damage for your first 2 turns" — sim has damage_mult.
        # Approximate as +0.4 damage_mult over the whole fight (two turns
        # of +1.0 averaged into a ~5-turn battle = ~+0.4).
        player.damage_mult += 0.4
        return

    if food == "Godmode Guac":
        # "+1x Damage, +1x Damage at the start of turn 4" — full-fight
        # buff plus late ramp. Approximate as +1.3 damage_mult.
        player.damage_mult += 1.3
        return

    if food == "Giga Juice":
        # "+2 to all values on all dice" — attack damage + block + poison
        # + heal base values get +2 each.
        for die in player.dice:
            for s in die.sides:
                if s.damage: s.damage += 2
                if s.block: s.block += 2
                if s.heal: s.heal += 2
                if s.poison_stacks: s.poison_stacks += 2
        return

    if food == "Brotein Bar MAX":
        # "Attack all 20, Heal 8, Gain 2 Strength, +500 Points"
        player.strength += 2
        player.hp = min(player.max_hp, player.hp + 8)
        for e in enemies:
            if e.current_hp > 0:
                e.current_hp = max(0, e.current_hp - 20)
        return

    if food == "Boom Beans":
        # "40 to chosen, 10 to all others" — target enemy in HP (10,40]
        # so primary kills + splash cleans chaff; else highest HP.
        alive = [e for e in enemies if e.current_hp > 0]
        if not alive:
            return
        in_range = [e for e in alive if 10 < e.current_hp <= 40]
        target = max(in_range, key=lambda e: e.current_hp) if in_range \
                 else max(alive, key=lambda e: e.current_hp)
        for e in alive:
            dmg = 40 if e is target else 10
            e.current_hp = max(0, e.current_hp - dmg)
        return

    if food == "Pickle":
        # "Gain 6 Block if you have 9 or less Block at end of each turn"
        player.pickle_block_threshold = 9
        player.pickle_block_refill = 6
        return

    if food == "Rage Shake":
        # "When damaged, gain 3 Strength" — approximate flat +3 Str.
        player.strength += 3
        return

    if food == "Clutch Creme":
        # "If you take 7 or less damage, reduce it to 1" — sim supports
        # this via clutch_creme_threshold (post-block, pre-hp reduction).
        player.clutch_creme_threshold = 7
        return

    if food == "Snackrifice":
        # "Lose 6 HP; if you finish ≤50% HP, heal 22" — the heal part is
        # end-of-battle and depends on outcome. Model only the cost.
        player.hp = max(1, player.hp - 6)
        return

    if food == "Toxipop":
        # "After any Baddie dies, transfer Poison to next Baddie" —
        # sim supports via toxipop_active flag. Useful only in multi-
        # enemy fights where the player's dice apply poison (e.g.
        # Firant Queen pack with any poison side).
        player.toxipop_active = True
        return

    if food == "Scorch Sauce":
        # "Exhaust up to 4 Sides before battle, max 2 per die" — pre-mark
        # weakest attack side indices as exhausted on each die (max 2/die,
        # 4 total). Only applies if the die has a dominant attack ≥10.
        total_exhausted = 0
        for die in player.dice:
            attacks = [(i, s) for i, s in enumerate(die.sides)
                       if s.damage > 0]
            if not attacks:
                continue
            top_val = max(s.damage for _, s in attacks)
            if top_val < 10:
                continue
            fillers = sorted(attacks, key=lambda p: p[1].damage)
            per_die = 0
            for idx, s in fillers:
                if per_die >= 2 or total_exhausted >= 4:
                    break
                if s.damage >= top_val:
                    break
                die.exhausted.add(idx)
                per_die += 1
                total_exhausted += 1
            if total_exhausted >= 4:
                break
        return

    if food == "Crit Chips":
        # "3x the value of any Attack" — triple the highest-damage non-
        # exhausted attack side on any die.
        best_die = None
        best_idx = None
        best_val = 0
        for die in player.dice:
            for i, s in enumerate(die.sides):
                if i in die.exhausted: continue
                if s.damage > best_val:
                    best_val = s.damage
                    best_die = die
                    best_idx = i
        if best_die is not None and best_idx is not None:
            best_die.sides[best_idx].damage = best_val * 3
        return


def _reset_enemies_to_full(enemies: list, rng: random.Random) -> None:
    from dd_agent.sim.enemies import roll_hp
    for e in enemies:
        e.rolled_max_hp = roll_hp(e, rng)
        e.current_hp = e.rolled_max_hp
        e.strength = 0
        e.armor = 0
        e.block = 0
        e.poison = 0
        e.bleed_turns = 0
        e.freeze_turns = 0


def run_trials(base_player: PlayerState, enemy_factory, food: str,
                trials: int, chapter: int, seed: int) -> tuple[int, float, float]:
    """Return (wins, mean_hp_end_on_win, mean_hp_end_all)."""
    rng = random.Random(seed)
    wins = 0
    hp_wins = []
    hp_all = []
    for _ in range(trials):
        player = _clone_player(base_player)
        enemies = enemy_factory()
        trial_rng = random.Random(rng.random())
        # Pre-reset dice + enemies here so the food can mutate post-reset
        # state (otherwise simulate_battle would wipe Boom Beans damage).
        for die in player.dice:
            die.reset()
        _reset_enemies_to_full(enemies, trial_rng)
        _apply_food(food, player, enemies)
        result = simulate_battle(
            player, enemies, trial_rng, chapter=chapter, reset=False,
        )
        hp_all.append(max(0, result.player_hp_end))
        if result.won:
            wins += 1
            hp_wins.append(result.player_hp_end)
    mean_hp_win = sum(hp_wins) / len(hp_wins) if hp_wins else 0
    mean_hp_all = sum(hp_all) / len(hp_all) if hp_all else 0
    return wins, mean_hp_win, mean_hp_all


def main():
    target_filter = sys.argv[1] if len(sys.argv) > 1 else None

    for label, chapter, enemy_factory, setup_path in SETUPS:
        if target_filter and target_filter != label:
            continue
        pf_full = FULL_RUNS / setup_path
        if not pf_full.exists():
            print(f"\n=== {label}: setup not found at {setup_path} ===")
            continue
        base_player = _load_player(pf_full)

        print(f"\n=== {label} ({TRIALS} trials/food, chapter {chapter}) ===")
        print(f"    setup: {setup_path}")
        print(f"    player: HP {base_player.hp}/{base_player.max_hp}, "
              f"{len(base_player.dice)} dice, "
              f"{sum(len(d.sides) for d in base_player.dice)} total sides")

        # Run baseline first, then each food. Use a fixed seed stream so
        # every food faces the same sequence of rolls (reduces variance).
        baseline = None
        rows = []
        for food in FOODS:
            wins, hp_win, hp_all = run_trials(
                base_player, enemy_factory, food,
                trials=TRIALS, chapter=chapter, seed=1337,
            )
            wr = wins / TRIALS
            if baseline is None:
                baseline = (wr, hp_win, hp_all)
            rows.append((food, wr, hp_win, hp_all))

        base_wr, base_hp_win, base_hp_all = baseline

        def score(row):
            _, wr, hp_win, hp_all = row
            # Winrate gains are the headline. HP preservation on wins
            # is the tiebreaker (fast kills = less damage taken).
            wr_delta = wr - base_wr
            hp_delta = hp_all - base_hp_all
            return 100 * wr_delta + hp_delta

        # Sort so baseline stays first, then foods ranked by score.
        def sort_key(row):
            if row[0] == "— no food —":
                return (-9999, 0)
            return (-score(row), -row[1])

        rows_sorted = sorted(rows, key=sort_key)

        header = f"    {'food':<22} {'wr':>5} {'Δwr':>6} {'hp_end_win':>11} {'hp_end_all':>11} {'score':>7}"
        print(header)
        print("    " + "-" * (len(header) - 4))
        for food, wr, hp_win, hp_all in rows_sorted:
            d_wr = wr - base_wr
            d_all = hp_all - base_hp_all
            sc = score((food, wr, hp_win, hp_all))
            mark = "  " if food == "— no food —" else ("↑ " if sc > 0 else "↓ " if sc < 0 else "= ")
            print(f"    {mark}{food:<20} {wr:>4.0%} {d_wr:>+5.0%} "
                  f"{hp_win:>9.1f}    {hp_all:>9.1f} {sc:>+7.1f}")


if __name__ == "__main__":
    main()
