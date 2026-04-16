"""Counterfactual analyzer for a completed run.

For each upgrade decision in the run, takes the 3 offered sides and runs
the battle simulator against a stress-test enemy (Ganondwarf by default)
with each option applied to the pre-decision dice state. Ranks the options
by simulated win rate and flags any case where a rejected option had a
higher win rate than the one actually taken.

Usage:
    python scripts/analyze_run.py <run_dir>
    python scripts/analyze_run.py data/full_runs/20260413_195055_r4
    python scripts/analyze_run.py latest    # analyze the most recent run
"""
import copy
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from dd_agent.sim.battle import PlayerState, simulate_battle
from dd_agent.sim.enemies import ENEMIES
from dd_agent.sim.sides import Die, Side


SIM_TRIALS = 500  # per option


# --------------------------------------------------------------------
# Live API → simulator conversion
# --------------------------------------------------------------------
def _tags(ability):
    return [t.get("label") for t in (ability.get("tags") or []) if isinstance(t, dict)]


def _score_base_for_side(ability) -> int:
    tags = _tags(ability)
    if "Level 3 Boss" in tags:
        return 100
    if "Level 3" in tags:
        return 30
    if "Level 2" in tags:
        return 20
    return 10  # L1 / Starter / default


def live_ability_to_side(ability: dict) -> Side:
    """Lossy conversion from a live API ability payload to a sim Side.

    Parses the structured damage/block/etc fields AND the specialEffect
    payload so sim accuracy covers passive blocks, enemy debuffs,
    conditional blocks, and per-turn heals.
    """
    if not isinstance(ability, dict):
        return Side(label="?")

    def _nested(key):
        v = ability.get(key)
        return v if isinstance(v, dict) else {}

    damage = _nested("damage")
    block = _nested("block")
    heal = _nested("heal")
    poison = _nested("poison")
    bleed = _nested("bleed")
    freeze = _nested("freeze")
    strength = _nested("strength")
    armor = _nested("armor")
    special = _nested("specialEffect")
    se_type = (special.get("type") or "") if isinstance(special, dict) else ""
    se_config = special.get("config") or {} if isinstance(special, dict) else {}
    se_value = int(se_config.get("value", 0) or 0) if isinstance(se_config, dict) else 0
    se_target = se_config.get("target") if isinstance(se_config, dict) else "single"

    # Player strength/armor direction: target="self" means buff self,
    # otherwise it's a debuff to enemies (rare but exists on some sides).
    strength_self = 0
    strength_enemy_val = 0
    strength_enemy_tgt = "single"
    if strength.get("target") == "self":
        strength_self = int(strength.get("value", 0) or 0)
    elif strength and int(strength.get("value", 0) or 0) > 0:
        strength_enemy_val = int(strength.get("value", 0) or 0)
        strength_enemy_tgt = strength.get("target") or "single"

    armor_self = 0
    armor_enemy_val = 0
    armor_enemy_tgt = "single"
    if armor.get("target") == "self":
        armor_self = int(armor.get("value", 0) or 0)
    elif armor and int(armor.get("value", 0) or 0) > 0:
        armor_enemy_val = int(armor.get("value", 0) or 0)
        armor_enemy_tgt = armor.get("target") or "single"

    # specialEffect parsing — one case per known type.
    block_if_no_block = 0
    block_per_baddie_val = 0
    block_per_debuff = 0
    attack_give_defend_val = 0
    passive_heal = 0
    passive_str = 0
    passive_block = 0
    multiply_largest = 0.0

    label_lower = (ability.get("label") or "").lower()

    if se_type == "attackGiveDefend":
        attack_give_defend_val = se_value
    elif se_type == "gainHealthWhenTurnEnd":
        passive_heal = se_value
    elif se_type == "gainStrengthWhenTurnEnd":
        passive_str = se_value
    elif se_type == "blockWhenHasFreezeOrBleed":
        # "Block 8 per Freeze or Bleed on you. Otherwise, Block 10"
        block_per_debuff = se_value
    elif se_type == "multiplyLargestAttackOnThisDie":
        multiply_largest = float(se_value or 2)
    elif se_type == "decreaseBaddieStrenthThisTurn":
        strength_enemy_val = se_value
        # The config sometimes says target=single even when the label is
        # "all Baddie". Trust the label when it says "all".
        if "all baddie" in label_lower or "all enemies" in label_lower:
            strength_enemy_tgt = "all"
        else:
            strength_enemy_tgt = se_target or "single"
    elif se_type == "decreaseBaddieArmor" or (
        "decrease" in label_lower and "armor" in label_lower
    ):
        armor_enemy_val = se_value or armor_enemy_val

    # Label-based fallbacks for sides whose effect is label-only.
    if "block 24" in label_lower and "no block" in label_lower:
        block_if_no_block = 24
    if "block" in label_lower and "per baddie" in label_lower:
        # "Block 8 per Baddie" etc.
        import re
        m = re.search(r"block\s+(\d+)\s+per\s+baddie", label_lower)
        if m:
            block_per_baddie_val = int(m.group(1))

    return Side(
        label=ability.get("label", "?"),
        damage=int(damage.get("value", 0) or 0),
        hits=int(damage.get("hits", 1) or 1),
        target=damage.get("target", "single") or "single",
        block=int(block.get("value", 0) or 0),
        heal=int(heal.get("value", 0) or 0),
        poison_stacks=int(poison.get("value", 0) or 0),
        poison_hits=int(poison.get("hits", 1) or 1),
        poison_target=poison.get("target", "single") or "single",
        bleed_duration=int(bleed.get("duration", 0) or 0),
        freeze_duration=int(freeze.get("duration", 0) or 0),
        freeze_target=freeze.get("target", "single") or "single",
        strength_self=strength_self,
        armor_self=armor_self,
        strength_enemy=strength_enemy_val,
        strength_enemy_target=strength_enemy_tgt,
        strength_enemy_this_turn=(se_type == "decreaseBaddieStrenthThisTurn"),
        armor_enemy=armor_enemy_val,
        armor_enemy_target=armor_enemy_tgt,
        block_if_no_block=block_if_no_block,
        block_per_baddie=block_per_baddie_val,
        block_per_debuff_on_self=block_per_debuff,
        attack_give_defend=attack_give_defend_val,
        passive_heal_per_turn=passive_heal,
        passive_str_per_turn=passive_str,
        passive_block_per_turn=passive_block,
        multiply_largest_attack=multiply_largest,
        exhaust=bool(ability.get("exhaust", False)),
        score_base=_score_base_for_side(ability),
    )


def live_dice_to_sim_dice(live_dices: list) -> list:
    """Convert a live /api/character `dices` list to a list of sim Die objects."""
    sim_dice = []
    for i, d in enumerate(live_dices):
        abilities = d.get("ability") or []
        sides = [live_ability_to_side(a) for a in abilities]
        sim_dice.append(Die(name=f"Die {i + 1}", sides=sides))
    return sim_dice


def apply_hypothetical_pick(
    pre_dice: list,
    target_die_index: int,
    ability: dict,
) -> list:
    """Return a deep-copied dice list with `ability` appended to the target die."""
    new_dice = copy.deepcopy(pre_dice)
    if 0 <= target_die_index < len(new_dice):
        abilities = new_dice[target_die_index].get("ability") or []
        abilities = list(abilities)
        abilities.append(copy.deepcopy(ability))
        new_dice[target_die_index]["ability"] = abilities
    return new_dice


# --------------------------------------------------------------------
# Per-decision counterfactual sim
# --------------------------------------------------------------------
def simulate_vs_boss(
    hypothetical_dice: list,
    enemy_factory,
    trials: int = SIM_TRIALS,
    player_hp: int = 60,
    player_max_hp: int = 60,
) -> dict:
    """Run N sim trials against a single-enemy stress test; return aggregate metrics."""
    wins = 0
    hp_ends = []
    for i in range(trials):
        sim_dice = live_dice_to_sim_dice(hypothetical_dice)
        player = PlayerState(hp=player_hp, max_hp=player_max_hp, dice=sim_dice)
        enemy = enemy_factory()
        rng = random.Random(i)
        result = simulate_battle(player, [enemy], rng)
        if result.won:
            wins += 1
        hp_ends.append(result.player_hp_end)

    return {
        "trials": trials,
        "p_win": wins / trials,
        "mean_hp_end": sum(hp_ends) / len(hp_ends),
    }


# --------------------------------------------------------------------
# Run parsing
# --------------------------------------------------------------------
def load_run(run_dir: Path) -> dict:
    """Load a run's summary + per-battle data for analysis.

    Returns a dict with `summary` and `battles` (a list of dicts containing
    `num`, `pre_dice`, `target_die_index`, `offered`, `picked_label`, etc.).
    """
    summary_path = run_dir / "_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"no _summary.json in {run_dir}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    battles = []
    # For each battle entry in the summary, find the corresponding
    # pre_pick_dice + pick_dice response on disk.
    for entry in summary.get("battles", []):
        num = entry.get("num")
        if num is None:
            continue
        num_str = f"b{int(num):02d}"
        pre_pick_files = list(run_dir.glob(f"*{num_str}_char_pre_pick_dice.json"))
        pick_dice_files = list(run_dir.glob(f"*{num_str}_loot_pick_dice.json"))
        if not pre_pick_files or not pick_dice_files:
            continue
        pre_char = json.loads(pre_pick_files[0].read_text(encoding="utf-8"))
        pick_resp = json.loads(pick_dice_files[0].read_text(encoding="utf-8"))
        pre_dice = pre_char.get("dices") or []
        offered = pick_resp.get("abilities") or []
        picked_label = entry.get("picked_ability_label")

        # Determine which die was picked: fall back to summary if present,
        # otherwise infer from the position that has one fewer side than
        # its counterpart (not reliable — prefer the summary).
        target_die_index = entry.get("picked_die_index")
        if target_die_index is None:
            target_die_index = 0  # best-effort fallback

        battles.append({
            "num": num,
            "monsters": entry.get("monsters"),
            "result": entry.get("result"),
            "hp_at_end": entry.get("hp_at_end"),
            "pre_dice": pre_dice,
            "offered": offered,
            "picked_label": picked_label,
            "target_die_index": target_die_index,
        })

    return {"summary": summary, "battles": battles}


# --------------------------------------------------------------------
# Analysis pipeline
# --------------------------------------------------------------------
def analyze(run_dir: Path, stress_enemy: str = "ganondwarf") -> None:
    run = load_run(run_dir)
    summary = run["summary"]
    battles = run["battles"]

    print(f"\n=== Counterfactual analysis: {run_dir.name} ===")
    print(f"  session_id:  {summary.get('session_id')}")
    print(f"  end_reason:  {summary.get('end_reason')}")
    print(f"  iterations:  {summary.get('iterations')}")
    print(f"  battles:     {summary.get('total_battles')}")
    print(f"  stress test: {stress_enemy} ({SIM_TRIALS} trials per option)")
    print()

    factory = ENEMIES.get(stress_enemy)
    if factory is None:
        print(f"unknown enemy: {stress_enemy}")
        return

    regrets = []  # list of (battle_num, improvement, rejected_label, picked_label)

    for b in battles:
        if not b["offered"]:
            continue
        print(f"--- battle #{b['num']} ({b.get('monsters')}) ---")
        print(f"    target die:  #{b['target_die_index'] + 1}")
        print(f"    taken:       {b['picked_label']}")

        picked_stats = None
        all_results = []
        for opt in b["offered"]:
            hyp_dice = apply_hypothetical_pick(
                b["pre_dice"], b["target_die_index"], opt
            )
            stats = simulate_vs_boss(hyp_dice, factory)
            label = opt.get("label", "?")
            all_results.append((label, stats, opt is b["offered"][0]))
            tag = " ← TAKEN" if label == b["picked_label"] else ""
            print(
                f"    [{label}] "
                f"P(win)={stats['p_win']*100:5.1f}%  "
                f"mean_hp={stats['mean_hp_end']:5.1f}"
                f"{tag}"
            )
            if label == b["picked_label"]:
                picked_stats = stats

        # Check for regret: any rejected option with meaningfully better win rate
        if picked_stats is not None:
            for label, stats, _ in all_results:
                if label == b["picked_label"]:
                    continue
                delta = stats["p_win"] - picked_stats["p_win"]
                if delta >= 0.05:  # 5pp improvement threshold
                    regrets.append((b["num"], delta, label, b["picked_label"]))
        print()

    # Summary of regrets
    if regrets:
        regrets.sort(key=lambda r: r[1], reverse=True)
        print("=== Top regrets (rejected picks that would have improved survival) ===")
        for num, delta, rejected, picked in regrets[:10]:
            print(f"  battle {num}: +{delta*100:4.1f}pp  {rejected!r}  vs  {picked!r}")
    else:
        print("=== No regrets found (picked option won in every decision) ===")


def resolve_run_dir(arg: str) -> Path:
    base = Path("data/full_runs")
    if arg == "latest":
        runs = sorted(
            [d for d in base.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
        )
        if not runs:
            raise FileNotFoundError("no runs in data/full_runs")
        return runs[-1]
    candidate = Path(arg)
    if candidate.exists():
        return candidate
    # Try as relative to data/full_runs
    fallback = base / arg
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"run dir not found: {arg}")


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/analyze_run.py <run_dir|latest> [stress_enemy]")
        print(f"  available enemies: {', '.join(sorted(ENEMIES))}")
        sys.exit(1)
    run_dir = resolve_run_dir(sys.argv[1])
    stress = sys.argv[2] if len(sys.argv) > 2 else "ganondwarf"
    analyze(run_dir, stress_enemy=stress)


if __name__ == "__main__":
    main()
