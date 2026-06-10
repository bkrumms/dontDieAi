#!/usr/bin/env python3
"""Generate Hermes fine-tuning training data.

Sources:
  1. Hardcoded rules Q&A from key strategic knowledge
  2. Decision examples synthesized via upgrade_picker scoring
  3. Real run states from data/runs/*/states.jsonl

Outputs:
  data/hermes_training/rules.jsonl     — game mechanics Q&A
  data/hermes_training/decisions.jsonl — pick-side decision examples

Format: one JSON per line, {"messages": [...]} in ChatML style for SFT.

Usage:
  python scripts/generate_hermes_training.py
  python scripts/generate_hermes_training.py --runs-only   # only parse run logs
  python scripts/generate_hermes_training.py --decisions-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dd_agent.sim.upgrade_picker import (
    DIE_ROLES,
    _base_points,
    _pool_tier,
    _role_fit,
    classify_side,
    score_side_for_die,
)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge" / "game"
RUNS_DIR = Path(__file__).parent.parent / "data" / "runs"
OUT_DIR = Path(__file__).parent.parent / "data" / "hermes_training"

RULES_SYSTEM = (
    "You are an expert strategist for the Don't Die roguelike tournament game. "
    "Answer questions about game mechanics and strategy accurately and concisely."
)

DECISION_SYSTEM = (
    "You are a Don't Die pick advisor. Given a game state and offered upgrade sides, "
    "choose the best side for the target die. "
    "Respond ONLY in JSON: {\"pick_index\": <int>, \"rationale\": \"<≤30 word reason>\"}."
)

DIE_ROLE_DESC = {
    "utility": "Die 0 — compounding: Strength/Armor buffs, heals, exhaust payoff. Survival-first.",
    "attack": "Die 1 — pure kill speed: Attack, Poison, Bleed, multi-hit. Defense is near-useless here.",
    "mixed": "Die 2 — gap filler: takes whatever attack/defense the build currently lacks.",
    "defense": "Die 3 — survival anchor: Block/Armor only. Non-exhaust attack sides dilute blocking and are run-killers.",
}


# ---------------------------------------------------------------------------
# Rules Q&A pairs — key strategic knowledge encoded as instruction examples
# ---------------------------------------------------------------------------

RULES_QA: list[tuple[str, str]] = [
    # Die roles
    (
        "What is Die 0's role in Don't Die and what sides should it receive?",
        "Die 0 is the utility/compounding die. It should receive Strength buffs, Armor buffs, heals, "
        "conditional attacks, and exhaust-payoff sides. It benefits most from the exhaust mechanic "
        "because exhausting its starter sides leaves only upgraded sides rolling, compounding value every turn.",
    ),
    (
        "What is Die 1's role in Don't Die?",
        "Die 1 is the pure kill-speed die. It should only receive Attack, Poison, Bleed, and multi-hit "
        "sides. Defense sides score near-zero here (0.15x multiplier) and are a waste of a pick slot. "
        "Kill speed is a form of defense — dead enemies can't deal damage.",
    ),
    (
        "What is Die 3's role and what sides are dangerous on it?",
        "Die 3 is the pure defense die. It should only receive Block and Armor sides. "
        "Non-exhaust attack sides are run-killers: they eat the die's roll budget, reducing how often "
        "it blocks. Exhaust attack sides are acceptable — they fire once then the die returns to blocking. "
        "Block 12/turn is the gold standard pick for Die 3.",
    ),
    # Exhaust mechanic
    (
        "How does the exhaust mechanic work and why does it help Die 0?",
        "When an exhausted side fires, it's removed from the die for the rest of that battle. "
        "On Die 0, Gain 3 Strength and Gain 3 Armor are both exhaust starters. Once they fire, "
        "only the upgraded non-exhaust sides remain in the rotation. This means upgrades roll "
        "roughly twice as often compared to a die with no exhausts, making Die 0 the highest-priority "
        "die to upgrade first.",
    ),
    (
        "What does 'Exhaust all Basic Attack on each die' do and why is it strong?",
        "It permanently exhausts every basic Attack 4 starter across all dice at the start of battle. "
        "This removes filler sides and boosts every die's consistency — upgraded sides roll more often. "
        "It's especially valuable on the defense die, which gets back to blocking faster. "
        "Score this side at 1.0x (not the usual 0.15x attack-on-defense penalty) because its effect "
        "is defensive/supportive, not offensive.",
    ),
    # Tier scoring
    (
        "How are side tiers scored in Don't Die?",
        "Tiers assign base points before the role-fit multiplier:\n"
        "  Starter / Level 1 = 10 pts\n"
        "  Level 2           = 20 pts\n"
        "  Level 3           = 30 pts\n"
        "  Level 3 Boss      = 100 pts (gets an additional 1.5× bump → effective 150)\n"
        "  Curse             = hard veto (−1000, never pick)\n"
        "These are multiplied by the role-fit multiplier to get the final score.",
    ),
    # Role-fit multipliers
    (
        "What are the role-fit multipliers for Die 3 (defense)?",
        "Die 3 role-fit multipliers:\n"
        "  defense  → 2.2×\n"
        "  heal     → 1.9×  (directly supports survival)\n"
        "  utility  → 0.5×\n"
        "  attack   → 0.15× (heavily penalized; non-exhaust attacks dilute blocking)\n"
        "  scoring  → 0.3×  (de-prioritized; scoring only matters after survival floor is locked)\n"
        "  curse    → −10× (hard veto)",
    ),
    (
        "What are the role-fit multipliers for Die 1 (attack)?",
        "Die 1 role-fit multipliers:\n"
        "  attack   → 2.2×\n"
        "  heal     → 0.6×\n"
        "  utility  → 0.5×\n"
        "  defense  → 0.15×\n"
        "  scoring  → 0.4×\n"
        "  curse    → −10×",
    ),
    # Survival-first
    (
        "What does 'survival-first' mean in Don't Die strategy?",
        "Scoring sides are worthless on a dead run. Prioritize in this order:\n"
        "  1. Debuff removal (poison/bleed/freeze stacks kill runs)\n"
        "  2. Block and Armor (need ≥4 sustained block sides by end of Ch1)\n"
        "  3. Kill speed (dead enemies can't attack)\n"
        "  4. Heals\n"
        "  5. Scoring sides (only after the survival floor is locked)\n"
        "Scoring multipliers are 0.3–0.5× across all die roles to enforce this.",
    ),
    # Biome routing
    (
        "How does biome affect which die to upgrade?",
        "The biome of a fight determines the loot pool, so routing the pick to the die whose "
        "role matches the biome means offered sides are more likely to synergize:\n"
        "  Volcano (offensive pool)  → upgrade Die 0 → Die 1 → Die 2 → Die 3 last\n"
        "  Ice Cave (defensive pool) → upgrade Die 3 → Die 2 → Die 0 → Die 1 last\n"
        "  Toxic Swamp (poison pool) → upgrade Die 0 → Die 2 → Die 3 → Die 1 last\n"
        "If defensive upgrades outnumber offensive upgrades by ≥2, bias toward offensive dice "
        "regardless of biome to avoid all-block builds that can't kill.",
    ),
    # Campfire
    (
        "What should you do at a campfire?",
        "At campfires only pick rest (heal HP) or burn (remove a bad side). Never take "
        "points, food, or mine at a campfire — these waste the slot. Reaching Stage 2 is the "
        "top priority, and staying alive long enough to get there requires both HP and a clean die.",
    ),
    # Block stacks
    (
        "Is 'Block stacks for 3 turns' a good pick?",
        "No — 'Block stacks for 3 turns' is bait early game. It only pays off if enemies attack "
        "every single turn AND you don't take a hit that wipes the stack. Prefer conditional block "
        "sides like 'Block per Freeze' or 'Block per Bleed' which fire reliably when you have a "
        "freeze or bleed applier. Unconditional Block 12 is usually better than stacking block.",
    ),
    # Combo: strength + multi-hit
    (
        "Why do Strength and multi-hit attack sides combo well?",
        "Multi-hit attacks (e.g., 'Attack N, M times') apply Strength on each individual hit. "
        "So Gain 3 Strength + Attack 4 twice = (4+3)×2 = 14 damage vs 8 without Strength. "
        "The more hits, the more Strength amplifies. Strength and multi-hit are complements, "
        "not competitors — if you have one, the other becomes a higher-priority pick.",
    ),
    # Duplicate sides
    (
        "What does 'Duplicate this Side' do and should you burn copies?",
        "'Duplicate this Side' spawns copies of adjacent sides that vanish at end of battle — "
        "they are temporary. Never burn duplicate copies; the pick itself is strong because it "
        "effectively increases the roll frequency of the duplicated side during the fight.",
    ),
    # Curse handling
    (
        "What should you always do when a Curse side is offered?",
        "Never pick a Curse side. Curses are hard-vetoed with a −1000 score regardless of tier. "
        "They permanently debuff the die and have no upside. If all three offered sides are Curses "
        "(extremely rare), skip the upgrade entirely.",
    ),
    # Ch2 upgrades
    (
        "When should you skip an upgrade in Chapter 2?",
        "In Ch2, skip the upgrade if the best offered side's score is below the current average "
        "score of existing non-exhausted sides on the target die. Adding a weaker side dilutes "
        "the die's roll quality — every side gets equal roll probability, so a below-average side "
        "drags down the die's expected output per turn.",
    ),
    # Overcrowded dice
    (
        "What happens when a die has 6 or more sides?",
        "Sides on a 6+ side die get a 0.7× score penalty to reflect consistency loss — each "
        "individual side rolls less often. Prefer burning a starter side before adding a 7th+ "
        "unless the incoming side is exceptionally strong (L3Boss tier).",
    ),
    # Food strategy
    (
        "What is the food strategy for chapter bosses and space-25 mini-bosses?",
        "Dump all food on these mandatory fights — space-25 mini-boss and space-39 chapter boss. "
        "Food only fires at the start of a fight, so hoarding it past a forced encounter wastes it. "
        "Universal foods (Godmode Guac, Brotein Bar MAX, Giga Juice) can be used any fight. "
        "Defensive foods (Ice Rice, Brrrito) are reserved for bosses since they counter specific attacks.",
    ),
    # Time Crystals
    (
        "What are Time Crystals (TC) used for and what is the priority order?",
        "TC priority: map rerolls > burns at Bub's > battle rewinds (don't hoard).\n"
        "Map reroll: costs nextRerollCost (starts at 2, escalates each use). Reroll when EV of "
        "reachable tiles exceeds current tile score + reroll cost.\n"
        "Battle rewind: baseline 2 TC, escalates. Only rewind if HP loss ≥20 AND sim says >60% "
        "of replays beat actual outcome. Cap 2 rewinds per battle.",
    ),
    # Obelisk
    (
        "Should you always fight an obelisk?",
        "No. Obelisks are 2 sequential fights with HP carryover. Simulate BOTH fights against "
        "your current dice before deciding. Skip when simulated win rate across both fights is "
        "below 50%. Mid-obelisk rewinds are rejected by the server, so there's no safety net.",
    ),
    # Die identity
    (
        "How should you classify which die is which when reordering?",
        "Classify dice by their starter faces, not by order index. The utility die has Gain 3 "
        "Strength (exhaust) and Gain 3 Armor (exhaust) starters. The defense die has three Block 6 "
        "starters. The attack die has four attack starters. Use /reorder-dice proactively: "
        "buff-source dice should roll first, freeze appliers before freeze consumers.",
    ),
    # Tiny Titan trinket
    (
        "Is Tiny Titan worth buying at any gold cost?",
        "Yes. Tiny Titan deals 16 damage per turn passively and compounds because higher damage "
        "means enemies die faster, reducing total incoming damage. It's an auto-buy at any cost "
        "and is ranked alongside boss-tier trinkets.",
    ),
]


def _make_rules_example(question: str, answer: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": RULES_SYSTEM},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


# ---------------------------------------------------------------------------
# Synthetic decision examples using the scoring engine
# ---------------------------------------------------------------------------

# Realistic side objects covering common scenarios
_SYNTHETIC_SIDES: list[dict] = [
    {"label": "Block 12", "block": {"value": 12}, "sideType": "Tactic", "tags": [{"label": "Level 3"}], "exhaust": False},
    {"label": "Attack 14, Gain 5 Strength", "damage": {"hits": 1, "value": 14}, "strength": {"value": 5}, "sideType": "Attack", "tags": [{"label": "Level 3"}], "exhaust": False},
    {"label": "Attack 28", "damage": {"hits": 1, "value": 28}, "sideType": "Attack", "tags": [{"label": "Level 3"}], "exhaust": False},
    {"label": "(e) Attack 20, Increase Damage 2×", "damage": {"hits": 1, "value": 20}, "sideType": "Attack", "tags": [{"label": "Level 3"}], "exhaust": True, "isExhaust": True},
    {"label": "Attack 16, Duplicate this Side", "damage": {"hits": 1, "value": 16}, "sideType": "Attack", "tags": [{"label": "Level 3"}], "exhaust": False},
    {"label": "Block 6", "block": {"value": 6}, "sideType": "Tactic", "tags": [{"label": "Starter"}], "exhaust": False},
    {"label": "Attack 4", "damage": {"hits": 1, "value": 4}, "sideType": "Attack", "tags": [{"label": "Starter"}], "exhaust": False},
    {"label": "Poison 8", "poison": {"hits": 1, "value": 8}, "sideType": "Attack", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Heal 12", "heal": {"value": 12}, "sideType": "Power", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Gain 5 Strength", "strength": {"value": 5}, "sideType": "Power", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Gain 6 Armor", "armor": {"value": 6}, "sideType": "Power", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Bleed 3 Attack", "bleed": {"value": 3}, "damage": {"hits": 1, "value": 8}, "sideType": "Attack", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Score 200 Points", "sideType": "Bonus", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Cursed Weakness", "sideType": "Attack", "tags": [{"label": "Curse"}], "exhaust": False},
    {"label": "(e) Block 10, Freeze All 3", "block": {"value": 10}, "freeze": {"value": 0.75}, "sideType": "Tactic", "tags": [{"label": "Starter"}], "exhaust": True, "isExhaust": True},
    {"label": "Attack 8, Poison 4", "damage": {"hits": 1, "value": 8}, "poison": {"hits": 1, "value": 4}, "sideType": "Attack", "tags": [{"label": "Level 2"}], "exhaust": False},
    {"label": "Block 8 per Freeze or Bleed on you", "block": {"value": 8}, "sideType": "Tactic", "tags": [{"label": "Level 3"}], "exhaust": False},
    {"label": "Permanently +2 to all dice", "sideType": "Power", "tags": [{"label": "Level 3 Boss"}], "exhaust": False},
]

# Scenario definitions: (die_index, [side_indices into _SYNTHETIC_SIDES], correct_pick_idx_in_offered)
_SCENARIOS: list[tuple[int, list[int], int]] = [
    # Defense die: Block 12 vs Attack 14+Str vs Poison 8
    (3, [0, 1, 7], 0),
    # Defense die: Block 12 vs Heal 12 vs Score 200
    (3, [0, 8, 12], 0),
    # Defense die: Exhaust attack vs non-exhaust attack vs Block 6
    (3, [14, 7, 5], 2),  # Block 6 beats both; exhaust attack beats non-exhaust attack
    # Attack die: Attack 14+Str vs Block 6 vs Heal 12
    (1, [1, 5, 8], 0),
    # Attack die: Attack 28 vs Score 200 vs Gain 6 Armor
    (1, [2, 12, 10], 0),
    # Attack die: Attack 16 Duplicate vs Bleed 3 vs Gain 5 Strength
    (1, [4, 11, 9], 0),
    # Utility die: Gain 5 Strength vs Score 200 vs Curse
    (0, [9, 12, 13], 0),
    # Utility die: Heal 12 vs Attack 28 vs Block 12
    (0, [8, 2, 0], 0),
    # Mixed die: Attack 28 vs Block 12 vs Score 200
    (2, [2, 0, 12], 0),
    # Never pick a curse regardless of die
    (0, [13, 5, 7], 2),  # Curse, Block 6, Poison 8 → pick Poison 8
    (1, [13, 0, 8], 1),  # Curse, Block 12, Heal 12 → pick Block 12... but Die 1 prefers attack. Block 12 at 0.15x vs Heal at 0.6x → Heal wins
    # L3Boss is almost always correct
    (0, [17, 9, 8], 0),  # Permanently+2 (L3Boss) vs Str5 (L2) vs Heal 12 (L2)
    (3, [17, 0, 5], 0),  # Permanently+2 (L3Boss) vs Block 12 (L3) vs Block 6 (Starter)
]


def _describe_offered(offered: list[dict]) -> str:
    lines = []
    for i, s in enumerate(offered):
        label = s.get("label", "?")
        tags = [t.get("label") for t in (s.get("tags") or []) if isinstance(t, dict)]
        tier = next((t for t in tags if t in ("Starter", "Level 1", "Level 2", "Level 3", "Level 3 Boss", "Curse")), "?")
        ex = "(exhaust) " if s.get("isExhaust") else ""
        lines.append(f"  [{i}] {ex}{label}  tier={tier}")
    return "\n".join(lines)


def _make_decision_example(die_index: int, offered: list[dict]) -> dict | None:
    role = DIE_ROLES.get(die_index, "mixed")

    scored = []
    for i, side in enumerate(offered):
        s, combos = score_side_for_die(die_index, side)
        label = side.get("label", "?")
        cat = classify_side(side)
        tier = _pool_tier(side)
        scored.append((i, label, s, cat, tier, combos))
    scored.sort(key=lambda x: x[2], reverse=True)

    if not scored:
        return None

    best_i, best_label, best_score, best_cat, best_tier, _ = scored[0]

    # Build rationale from scoring
    runner_up = scored[1] if len(scored) > 1 else None
    if runner_up:
        ri, rlabel, rs, rcat, rtier, _ = runner_up
        gap = best_score - rs
        rationale = (
            f"{best_label} scores {best_score:.0f} ({best_tier}/{best_cat}) on {role} die, "
            f"vs {rlabel} at {rs:.0f} ({rtier}/{rcat}). "
            f"Gap of {gap:.0f} pts — {best_label} wins."
        )
    else:
        rationale = f"{best_label} scores {best_score:.0f} ({best_tier}/{best_cat}) on {role} die."

    role_desc = DIE_ROLE_DESC.get(role, role)
    prompt = (
        f"TARGET DIE: {die_index}  role: {role_desc}\n\n"
        f"OFFERED SIDES:\n{_describe_offered(offered)}\n\n"
        "Which side should be picked? Respond in JSON only."
    )
    answer = json.dumps({"pick_index": best_i, "rationale": rationale})

    return {
        "messages": [
            {"role": "system", "content": DECISION_SYSTEM},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]
    }


def generate_decision_examples() -> list[dict]:
    examples = []
    for die_index, side_indices, _ in _SCENARIOS:
        offered = [_SYNTHETIC_SIDES[i] for i in side_indices]
        ex = _make_decision_example(die_index, offered)
        if ex:
            examples.append(ex)
    # Also generate one example per die role with every possible tier combination
    tier_sides = {
        "defense_l3": _SYNTHETIC_SIDES[0],   # Block 12 L3
        "attack_l3":  _SYNTHETIC_SIDES[1],   # Attack 14+Str L3
        "heal_l2":    _SYNTHETIC_SIDES[8],   # Heal 12 L2
        "curse":      _SYNTHETIC_SIDES[13],  # Curse
        "scoring_l2": _SYNTHETIC_SIDES[12],  # Score 200
    }
    for die_index in range(4):
        offered = [tier_sides["defense_l3"], tier_sides["attack_l3"], tier_sides["curse"]]
        ex = _make_decision_example(die_index, offered)
        if ex:
            examples.append(ex)
    return examples


# ---------------------------------------------------------------------------
# Real-run state parsing — pull game states from recorded runs
# ---------------------------------------------------------------------------

def _summarize_dice(dices: list) -> str:
    parts = []
    for i, d in enumerate(dices or []):
        if not isinstance(d, dict):
            continue
        sides = [a.get("label", "?") for a in (d.get("ability") or []) if isinstance(a, dict)]
        parts.append(f"  Die {i}: {sides}")
    return "\n".join(parts)


def generate_run_state_examples() -> list[dict]:
    """Generate context-aware examples from real run state snapshots."""
    examples = []
    if not RUNS_DIR.exists():
        return examples

    for run_dir in RUNS_DIR.iterdir():
        states_file = run_dir / "states.jsonl"
        if not states_file.exists():
            continue
        try:
            states = []
            with states_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        states.append(json.loads(line))

            # Find state snapshots at decision points (inState == "loot" or similar)
            for snap in states:
                state = snap.get("state") or {}
                in_state = state.get("inState", "")
                if in_state not in ("loot", "pick"):
                    continue

                dices = state.get("dices") or []
                if not dices:
                    continue

                hp = state.get("health", "?")
                max_hp = state.get("max_health", "?")
                chapter = state.get("chapter", "?")
                boss = state.get("upcoming_boss", "?")
                gold = state.get("gold", "?")

                dice_summary = _summarize_dice(dices)
                prompt = (
                    f"GAME STATE SNAPSHOT:\n"
                    f"  HP={hp}/{max_hp}  gold={gold}  chapter={chapter}  upcoming_boss={boss}\n"
                    f"CURRENT DICE:\n{dice_summary}\n\n"
                    "Given this state, what die should be upgraded next and why? "
                    "Answer in plain text (this is a knowledge-building example, not a pick decision)."
                )

                # Determine best die to upgrade from dices
                try:
                    from dd_agent.sim.upgrade_picker import choose_die_for_upgrade
                    best_die_idx = choose_die_for_upgrade(dices, biome=None)
                    best_die_role = DIE_ROLES.get(best_die_idx, "mixed")
                    answer = (
                        f"Upgrade Die {best_die_idx} (role: {best_die_role}). "
                        f"This die has the fewest non-starter upgrades among the priority order "
                        f"for the current biome, making it the highest-leverage upgrade target."
                    )
                    examples.append({
                        "messages": [
                            {"role": "system", "content": RULES_SYSTEM},
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": answer},
                        ]
                    })
                except Exception:
                    pass

                if len(examples) >= 100:
                    return examples
        except Exception:
            continue
    return examples


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    print(f"  wrote {len(records)} examples -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-only", action="store_true")
    parser.add_argument("--decisions-only", action="store_true")
    args = parser.parse_args()

    if not args.decisions_only and not args.runs_only:
        print("Generating rules Q&A pairs...")
        rules = [_make_rules_example(q, a) for q, a in RULES_QA]
        write_jsonl(OUT_DIR / "rules.jsonl", rules)

    if not args.runs_only:
        print("Generating synthetic decision examples...")
        decisions = generate_decision_examples()
        write_jsonl(OUT_DIR / "decisions.jsonl", decisions)

    if not args.decisions_only:
        print("Parsing real run states...")
        run_examples = generate_run_state_examples()
        if run_examples:
            write_jsonl(OUT_DIR / "run_states.jsonl", run_examples)
        else:
            print("  no loot-state snapshots found in run logs")

    print(f"\nDone. Training data at {OUT_DIR}/")
    total = sum(
        len(list((OUT_DIR / f).open())) if (OUT_DIR / f).exists() else 0
        for f in ("rules.jsonl", "decisions.jsonl", "run_states.jsonl")
    )
    print(f"Total examples: ~{total}")


if __name__ == "__main__":
    main()
