"""Combo detection for side upgrades.

This module encodes the "combination" strategy principle: in Don't Die, one
die side rarely makes a run — runs are built from 2-4 sides that amplify each
other. Each combo rule checks whether a proposed side would form or extend a
known combo, given the current state of the target die and all other dice.

Combos return a multiplier that's applied to the base score of the side.

Each rule is a dataclass with:
  name:        short identifier for logging
  description: human-readable explanation
  bonus:       multiplier applied when the combo matches
  check:       function(target_die, offered_side, all_dice, target_die_index) -> bool

The upgrade_picker.score_side_for_die() calls compute_synergy_bonus() to get
a combined multiplier and the list of matched combo names. Per-combo bonuses
stack multiplicatively.

Starting with ~10 core combos — this framework is designed to expand as we
discover more interactions in real runs.
"""
from dataclasses import dataclass
from typing import Callable


# --------------------------------------------------------------------
# Low-level side introspection helpers
# --------------------------------------------------------------------

def _label(side) -> str:
    return (side.get("label") or "").lower() if isinstance(side, dict) else ""


def _tags(side) -> list:
    if not isinstance(side, dict):
        return []
    return [t.get("label") for t in (side.get("tags") or []) if isinstance(t, dict) and t.get("label")]


def _abilities(die) -> list:
    if not isinstance(die, dict):
        return []
    return [a for a in (die.get("ability") or []) if isinstance(a, dict)]


def is_attack(side) -> bool:
    if not isinstance(side, dict):
        return False
    if side.get("damage"):
        return True
    label = _label(side)
    return "attack" in label and "on this side" not in label.split("attack")[0]


def is_poison(side) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("poison")) or "poison" in _label(side) and "cure" not in _label(side)


def is_bleed_applier(side) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("bleed")) or "bleed" in _label(side)


def is_freeze_applier(side) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("freeze")) or "freeze" in _label(side)


def is_block(side) -> bool:
    if not isinstance(side, dict):
        return False
    label = _label(side)
    return bool(side.get("block")) or ("block" in label and "per baddie" not in label and "gain" not in label)


def is_scoring(side) -> bool:
    if not isinstance(side, dict):
        return False
    label = _label(side)
    return "score" in label or "point" in label


def is_damage_multiplier(side) -> bool:
    if not isinstance(side, dict):
        return False
    return "increase damage" in _label(side)


def is_points_multiplier(side) -> bool:
    if not isinstance(side, dict):
        return False
    return "increase points" in _label(side)


def is_exhaust(side) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("exhaust"))


def is_cure_poison(side) -> bool:
    return "cure poison" in _label(side)


def is_heal(side) -> bool:
    if not isinstance(side, dict):
        return False
    return bool(side.get("heal")) or "heal" in _label(side)


def is_debuff_remover(side) -> bool:
    label = _label(side)
    return (
        "remove all debuffs" in label
        or "remove leftmost debuff" in label
        or "cure poison" in label
        or "exhaust all curses" in label
    )


def is_negate_damage(side) -> bool:
    return "negate damage" in _label(side)


def is_remove_all_debuffs(side) -> bool:
    return "remove all debuffs" in _label(side)


def has_debuff_remover(die) -> bool:
    return any(is_debuff_remover(a) for a in _abilities(die))


def is_copy_next_die(side) -> bool:
    label = _label(side)
    return "copy" in label and "next die" in label


def is_pool_tier_boss(side) -> bool:
    return "Level 3 Boss" in _tags(side)


def is_values_plus_3(side) -> bool:
    label = _label(side)
    return "all values on this die" in label and "+3" in label


def count_heal_sides(die) -> int:
    return sum(1 for a in _abilities(die) if is_heal(a))


def is_strength_gainer(side) -> bool:
    """A side that gives the player Strength (flat +N to future attacks)."""
    if not isinstance(side, dict):
        return False
    strength = side.get("strength") or {}
    if isinstance(strength, dict):
        val = strength.get("value", 0) or 0
        target = strength.get("target") or ""
        if val > 0 and target == "self":
            return True
    # Text fallback for sides whose strength is in specialEffect
    label = _label(side)
    return ("gain" in label and "strength" in label) or "+strength" in label


def get_hits(side) -> int:
    """Get the number of damage hits for multi-hit attacks. Default 1."""
    if not isinstance(side, dict):
        return 1
    dmg = side.get("damage") or {}
    if isinstance(dmg, dict):
        return int(dmg.get("hits", 1) or 1)
    # Text fallback: "Attack N, 2 times", "Attack N, 3 times"
    label = _label(side)
    import re
    m = re.search(r"(\d+)\s+times", label)
    if m:
        return int(m.group(1))
    return 1


def is_multihit_attack(side) -> bool:
    return is_attack(side) and get_hits(side) > 1


def player_has_strength_gainer(all_dice) -> bool:
    return any(is_strength_gainer(a) for d in all_dice for a in _abilities(d))


def player_has_multihit_attack(all_dice) -> bool:
    return any(is_multihit_attack(a) for d in all_dice for a in _abilities(d))


def max_attack_damage(die) -> int:
    m = 0
    for ab in _abilities(die):
        dmg = ab.get("damage")
        if isinstance(dmg, dict):
            v = dmg.get("value", 0) or 0
            if v > m:
                m = v
    return m


def count_attack_sides(die) -> int:
    return sum(1 for a in _abilities(die) if is_attack(a))


def _count_block_sides_on_other_dice(all_dice, self_idx) -> int:
    """Count sides with block on all dice except self_idx."""
    count = 0
    for i, die in enumerate(all_dice or []):
        if i == self_idx:
            continue
        for ab in _abilities(die):
            label = (ab.get("label") or "").lower()
            if "block" in label:
                count += 1
    return count


def count_poison_sides(die) -> int:
    return sum(1 for a in _abilities(die) if is_poison(a))


def count_scoring_sides(die) -> int:
    return sum(1 for a in _abilities(die) if is_scoring(a))


def count_exhaust_sides(die) -> int:
    return sum(1 for a in _abilities(die) if is_exhaust(a))


def player_has_freeze_applier(all_dice) -> bool:
    return any(is_freeze_applier(a) for d in all_dice for a in _abilities(d))


def player_has_bleed_applier(all_dice) -> bool:
    return any(is_bleed_applier(a) for d in all_dice for a in _abilities(d))


# --------------------------------------------------------------------
# Combo rule definitions
# --------------------------------------------------------------------

@dataclass
class ComboRule:
    name: str
    bonus: float
    description: str
    check: Callable


# Rules are evaluated in order. All matching rules apply (multiplicative).

COMBO_RULES = [
    # ============================================================
    # SURVIVAL COMBOS (top priority — dead runs score nothing)
    # ============================================================
    ComboRule(
        name="debuff_removal_valuable_late",
        bonus=1.8,
        description="Debuff removal / negate is critical for surviving Ganondwarf's T1 "
                    "triple-debuff and chapter 2 bosses — BUT only once dice are upgraded "
                    "enough that the die slot isn't needed for base damage/block. Gate on "
                    "readiness ≥ 2.",
        check=lambda target_die, side, all_dice, idx: (
            is_debuff_remover(side)
            and _avg_non_starter_sides_across(all_dice) >= 2.0
        ),
    ),
    ComboRule(
        name="negate_damage_always_valuable",
        bonus=1.8,
        description="Negate Damage N times — hard damage cap, huge for boss fights",
        check=lambda target_die, side, all_dice, idx: is_negate_damage(side),
    ),
    ComboRule(
        name="heal_on_no_heal_die",
        bonus=1.6,
        description="First heal side on a die that has no healing yet",
        check=lambda target_die, side, all_dice, idx: (
            is_heal(side) and count_heal_sides(target_die) == 0
        ),
    ),
    ComboRule(
        name="heal_stack",
        bonus=1.3,
        description="Additional heal on an already-healing die (sustain build)",
        check=lambda target_die, side, all_dice, idx: (
            is_heal(side) and count_heal_sides(target_die) >= 1
        ),
    ),
    ComboRule(
        name="kill_speed_high_attack",
        bonus=1.5,
        description="High base attack (≥12) on Die 2 or Die 3 — fewer turns means less damage taken",
        check=lambda target_die, side, all_dice, idx: (
            idx in (1, 2)
            and is_attack(side)
            and (side.get("damage") or {}).get("value", 0) >= 12
        ),
    ),
    ComboRule(
        name="multihit_with_strength",
        bonus=1.7,
        description="Multi-hit attack ('Attack N, M times') when player has any strength-gaining side — each hit is amplified",
        check=lambda target_die, side, all_dice, idx: (
            is_multihit_attack(side)
            and player_has_strength_gainer(all_dice)
        ),
    ),
    ComboRule(
        name="strength_with_multihit",
        bonus=1.6,
        description="Strength-gaining side when player has a multi-hit attack — the Strength amplifies every hit",
        check=lambda target_die, side, all_dice, idx: (
            is_strength_gainer(side)
            and player_has_multihit_attack(all_dice)
        ),
    ),
    ComboRule(
        name="multihit_on_attack_die",
        bonus=1.4,
        description="Multi-hit attack on Die 2 (pure attack die) — stacks with the existing attacks + strength scaling",
        check=lambda target_die, side, all_dice, idx: (
            idx == 1 and is_multihit_attack(side)
        ),
    ),

    # ============================================================
    # EXISTING ROLE COMBOS — kept but retuned
    # ============================================================
    ComboRule(
        name="poison_stack",
        bonus=1.5,
        description="Adding poison to a die that already has 2+ poison sides",
        check=lambda target_die, side, all_dice, idx: (
            is_poison(side) and count_poison_sides(target_die) >= 2
        ),
    ),
    ComboRule(
        name="freeze_attack_combo",
        bonus=1.9,
        description="'Attack X. If Baddie is Freezing, Attack +Y' when player has any freeze applier",
        check=lambda target_die, side, all_dice, idx: (
            "freezing" in _label(side) and player_has_freeze_applier(all_dice)
        ),
    ),
    ComboRule(
        name="bleed_amp_combo",
        bonus=1.3,
        description="Strong attack on a die that already applies bleed (or any die has bleed)",
        check=lambda target_die, side, all_dice, idx: (
            is_attack(side) and not is_bleed_applier(side)
            and player_has_bleed_applier(all_dice)
            and (side.get("damage") or {}).get("value", 0) >= 10
        ),
    ),
    ComboRule(
        name="damage_mult_on_strong_attacks",
        bonus=1.6,
        description="Damage multiplier side when the target die already has Attack 10+",
        check=lambda target_die, side, all_dice, idx: (
            is_damage_multiplier(side) and max_attack_damage(target_die) >= 10
        ),
    ),
    ComboRule(
        name="attack_density_scaling",
        bonus=1.7,
        description="'Attack N per Attack Side' on a die with 3+ attack sides already",
        check=lambda target_die, side, all_dice, idx: (
            "per attack side" in _label(side) and count_attack_sides(target_die) >= 3
        ),
    ),
    ComboRule(
        name="self_duplicator_on_attack_die",
        bonus=1.5,
        description="'Duplicate this Side onto this Die' on Die 2 (attack die)",
        check=lambda target_die, side, all_dice, idx: (
            "duplicate this side" in _label(side) and idx == 1
        ),
    ),
    ComboRule(
        name="exhaust_payoff_die_1",
        bonus=1.2,
        description="Strong non-exhaust side on Die 1 with 2+ existing exhaust sides",
        check=lambda target_die, side, all_dice, idx: (
            idx == 0
            and not is_exhaust(side)
            and count_exhaust_sides(target_die) >= 2
        ),
    ),

    # ============================================================
    # SCORING COMBOS (SHARPLY DE-EMPHASIZED)
    # Only apply once the survival floor is locked — gated by
    # having both a heal side AND an attack ≥12 anywhere in the
    # player's dice pool. Otherwise the picker ignores them.
    # ============================================================
    ComboRule(
        name="points_mult_conditional",
        bonus=1.4,
        description="Points multiplier — only valuable once survival floor is met",
        check=lambda target_die, side, all_dice, idx: (
            is_points_multiplier(side)
            and count_scoring_sides(target_die) >= 1
            and _survival_floor_met(all_dice)
        ),
    ),

    # ============================================================
    # ANTI-COMBOS (penalties)
    # ============================================================
    ComboRule(
        name="damage_mult_anti_synergy",
        bonus=0.3,
        description="PENALTY: damage multiplier with max attack < 10 — wasted tempo",
        check=lambda target_die, side, all_dice, idx: (
            is_damage_multiplier(side) and max_attack_damage(target_die) < 10
        ),
    ),
    ComboRule(
        name="remove_all_debuffs_bait",
        bonus=0.2,
        description="PENALTY: 'Remove all debuffs' is bait — single-use exhaust that dilutes the die's role",
        check=lambda target_die, side, all_dice, idx: is_remove_all_debuffs(side),
    ),
    ComboRule(
        name="cure_poison_bait",
        bonus=0.25,
        description="PENALTY: 'Cure Poison' is bait unless no heal/damage-mult is available — user confirmed 2x Damage beats it",
        check=lambda target_die, side, all_dice, idx: is_cure_poison(side),
    ),
    ComboRule(
        name="debuff_remover_saturation",
        bonus=0.3,
        description="PENALTY: adding a debuff remover to a die that already has one (no stacking benefit)",
        check=lambda target_die, side, all_dice, idx: (
            (is_cure_poison(side) or is_remove_all_debuffs(side))
            and has_debuff_remover(target_die)
        ),
    ),
    ComboRule(
        name="copy_next_die_on_last",
        bonus=0.2,
        description="PENALTY: 'Copy next die' on Die 4 — there is no next die, so the side is dead weight",
        check=lambda target_die, side, all_dice, idx: (
            is_copy_next_die(side) and idx == 3
        ),
    ),
    ComboRule(
        name="boss_side_on_die_1",
        bonus=1.8,
        description="Boss-tier L3 side on Die 1 — compounds with Strength/Armor/Values+3 buffs",
        check=lambda target_die, side, all_dice, idx: (
            is_pool_tier_boss(side) and idx == 0
        ),
    ),
    ComboRule(
        name="boss_side_on_die_1_with_values3",
        bonus=2.2,
        description="Boss-tier L3 side on a Die 1 that already has the L3 'Give all values +3' side",
        check=lambda target_die, side, all_dice, idx: (
            is_pool_tier_boss(side) and idx == 0
            and any(is_values_plus_3(a) for a in _abilities(target_die))
        ),
    ),
    ComboRule(
        name="exhaust_basic_attacks_on_die_1",
        bonus=1.6,
        description="'Exhaust one Basic Attack on each die' works best on Die 1 (consolidated pool)",
        check=lambda target_die, side, all_dice, idx: (
            "exhaust" in _label(side) and "basic attack" in _label(side)
            and idx == 0
        ),
    ),
    ComboRule(
        name="cure_poison_on_poison_die",
        bonus=0.2,
        description="PENALTY: Cure Poison on a die with poison sides (self-sabotage)",
        check=lambda target_die, side, all_dice, idx: (
            is_cure_poison(side) and count_poison_sides(target_die) >= 1
        ),
    ),
    ComboRule(
        name="block_per_baddie_on_attack_die",
        bonus=0.4,
        description="PENALTY: 'Block per Baddie' on Die 2 (attack die) — off-role",
        check=lambda target_die, side, all_dice, idx: (
            "per baddie" in _label(side) and "block" in _label(side) and idx == 1
        ),
    ),
    ComboRule(
        name="scoring_below_survival_floor",
        bonus=0.05,
        description="PENALTY: any scoring side before the survival floor is met — near-zero",
        check=lambda target_die, side, all_dice, idx: (
            is_scoring(side) and not _survival_floor_met(all_dice)
        ),
    ),
    # ============================================================
    # BAIT SIDE PENALTIES
    # ============================================================
    ComboRule(
        name="block_stacks_bait_early",
        bonus=0.2,
        description="PENALTY: 'Block stacks for N turns' is bait early game — needs "
                    "multiple turns of block-rolling to compound, which early dice can't "
                    "guarantee. Conditional block (per-Freeze, per-Baddie) is far better.",
        check=lambda target_die, side, all_dice, idx: (
            "block stacks" in _label(side) and not _survival_floor_met(all_dice)
        ),
    ),
    ComboRule(
        name="block_equal_to_largest_attack_bait",
        bonus=0.15,
        description="PENALTY: 'Block equal to largest Attack value on this Die' is nearly "
                    "always worse than a flat block side — bounded by the die's attacks "
                    "and competes with actual block sides.",
        check=lambda target_die, side, all_dice, idx: (
            "block equal to largest attack" in _label(side)
        ),
    ),
    ComboRule(
        name="attack_equal_to_block_situational",
        bonus=0.2,
        description="PENALTY: 'Attack equal to Block' is too situational — only good "
                    "when most other dice provide block. Without heavy block from other "
                    "dice this side outputs near-zero damage.",
        check=lambda target_die, side, all_dice, idx: (
            "attack equal to block" in _label(side)
            and _count_block_sides_on_other_dice(all_dice, idx) < 6
        ),
    ),
    # ============================================================
    # BIOME × DIE ROUTING (per user 2026-04-13)
    # Ice Cave → defensive / freeze → starter Die 3 / Die 4 (idx 2/3)
    # Volcano  → offensive / exhaust-buffs → starter Die 1 / 2 / 3 (idx 0/1/2)
    # Toxic Swamp → generally bait
    # ============================================================
    ComboRule(
        name="ice_cave_on_defensive_die",
        bonus=1.3,
        description="Ice Cave side on Die 3 or Die 4 — matches the defensive role of that slot",
        check=lambda target_die, side, all_dice, idx: (
            "Ice Cave" in _tags(side) and idx in (2, 3)
        ),
    ),
    ComboRule(
        name="ice_cave_off_role",
        bonus=0.85,
        description="PENALTY: Ice Cave side on Die 1/2 — the offensive slots prefer Volcano",
        check=lambda target_die, side, all_dice, idx: (
            "Ice Cave" in _tags(side) and idx in (0, 1)
        ),
    ),
    ComboRule(
        name="volcano_on_offensive_die",
        bonus=1.3,
        description="Volcano side on Die 1/2/3 — matches the offensive exhaust-buff slot",
        check=lambda target_die, side, all_dice, idx: (
            "Volcano" in _tags(side) and idx in (0, 1, 2)
        ),
    ),
    ComboRule(
        name="volcano_off_role",
        bonus=0.85,
        description="PENALTY: Volcano side on Die 4 — defense slot doesn't want offensive burn sides",
        check=lambda target_die, side, all_dice, idx: (
            "Volcano" in _tags(side) and idx == 3
        ),
    ),
    ComboRule(
        name="toxic_swamp_poison_only",
        bonus=0.7,
        description="PENALTY: Toxic Swamp side when the build isn't committing to poison",
        check=lambda target_die, side, all_dice, idx: (
            "Toxic Swamp" in _tags(side)
            and sum(count_poison_sides(d) for d in all_dice) < 2
        ),
    ),
    # ============================================================
    # SPECIFIC SIDES — user-flagged pick-quality tweaks (2026-04-14)
    # ============================================================
    ComboRule(
        name="block_24_conditional_on_first_die",
        bonus=2.0,
        description="'Block 24 if you have no block' — HUGE value when the target die "
                    "is at position 1 (idx 0). The condition only holds when no earlier "
                    "die has already rolled block this turn, so placing it on a die "
                    "other than slot 1 is much weaker.",
        check=lambda target_die, side, all_dice, idx: (
            "block 24" in _label(side) and "no block" in _label(side) and idx == 0
        ),
    ),
    ComboRule(
        name="block_24_conditional_not_first_die",
        bonus=0.6,
        description="PENALTY: 'Block 24 if you have no block' on a die at idx >=1. "
                    "Any earlier die that rolls block will make this side fail the "
                    "condition — the upside is real but unreliable.",
        check=lambda target_die, side, all_dice, idx: (
            "block 24" in _label(side) and "no block" in _label(side) and idx >= 1
        ),
    ),
    ComboRule(
        name="block_24_conditional_duplicate",
        bonus=0.15,
        description="PENALTY: another die already carries 'Block 24 if you have no block'. "
                    "Only one copy can fire usefully per turn (because the first one satisfies "
                    "its own 'no block' condition), so the second copy is dead weight.",
        check=lambda target_die, side, all_dice, idx: (
            "block 24" in _label(side) and "no block" in _label(side)
            and any(
                ("block 24" in (_label(a) or "") and "no block" in (_label(a) or ""))
                for d in all_dice for a in _abilities(d)
            )
        ),
    ),
    ComboRule(
        name="block_equal_to_largest_attack_on_weak_die",
        bonus=0.35,
        description="PENALTY: 'Block equal to largest Attack value on this Die' when "
                    "the target die has no attack ≥10 — output is bounded by the die's "
                    "weakest attacks, making this nearly worthless.",
        check=lambda target_die, side, all_dice, idx: (
            "block equal to largest attack" in _label(side)
            and max_attack_damage(target_die) < 10
        ),
    ),
    ComboRule(
        name="aoe_poison_for_multi_enemy_fights",
        bonus=1.8,
        description="'Poison all' sides are high-value in general — they apply poison to "
                    "every enemy, which scales linearly with enemy count and trivializes "
                    "multi-enemy fights (e.g. Firant Queen 4-pack).",
        check=lambda target_die, side, all_dice, idx: (
            "poison all" in _label(side)
        ),
    ),
    ComboRule(
        name="aoe_bleed_freeze_applier",
        bonus=1.5,
        description="'Freeze all', 'Bleed all' or AOE debuff appliers scale with enemy "
                    "count and buy turns against multi-enemy fights.",
        check=lambda target_die, side, all_dice, idx: (
            ("freeze all" in _label(side) or "bleed all" in _label(side))
            and "attack" not in _label(side).split("all")[0][-10:]
        ),
    ),
    ComboRule(
        name="attack_per_side_is_bait",
        bonus=0.2,
        description="PENALTY: 'Attack 2 per Attack Side on this Die' is bait. On a 6-sided "
                    "die with 4 attack sides it only hits for 8 damage. We want FEWER sides "
                    "with HIGHER per-side value so powerful sides roll more often. Only "
                    "worth picking on a die that already has 'Duplicate this Side' (which "
                    "forces the bait side to keep re-rolling).",
        check=lambda target_die, side, all_dice, idx: (
            "attack" in _label(side) and "per attack side" in _label(side)
            and not any(
                "duplicate this side" in (_label(a) or "")
                for a in _abilities(target_die)
            )
        ),
    ),
    ComboRule(
        name="attack_per_side_with_duplicate_combo",
        bonus=1.6,
        description="'Attack N per Attack Side' when the die already has 'Duplicate this "
                    "Side' — the duplicate keeps the scaling side alive and turns it into a "
                    "compounding damage engine. Only context where this side is worth picking.",
        check=lambda target_die, side, all_dice, idx: (
            "attack" in _label(side) and "per attack side" in _label(side)
            and any(
                "duplicate this side" in (_label(a) or "")
                for a in _abilities(target_die)
            )
        ),
    ),
    ComboRule(
        name="passive_heal_per_turn_early",
        bonus=0.3,
        description="PENALTY: '(p) Heal N at the end of each turn' is too slow in early "
                    "game. Passive heals trickle over many turns while we take burst damage "
                    "from ch1 big-baddies. Only worth picking once dice are upgraded enough "
                    "to survive past turn 4.",
        check=lambda target_die, side, all_dice, idx: (
            "heal" in _label(side) and "end of each turn" in _label(side)
            and _avg_non_starter_sides_across(all_dice) < 2.0
        ),
    ),
    ComboRule(
        name="passive_heal_end_of_battle_good",
        bonus=1.5,
        description="'(p) Heal N at the end of the battle' is strong whenever block/attacks "
                    "are already solid — it compounds across every remaining battle. User "
                    "confirmed: end-of-battle heal ≠ end-of-turn heal. Not bait.",
        check=lambda target_die, side, all_dice, idx: (
            "heal" in _label(side) and "end of the battle" in _label(side)
        ),
    ),
    # ---- passive-per-turn bait (early game) ----
    ComboRule(
        name="passive_armor_per_turn_early",
        bonus=0.3,
        description="PENALTY: '(p) Gain N Armor at the end of each turn' trickles the same "
                    "way as heal-per-turn. Too slow for early ch1 burst damage. Only worth "
                    "picking once dice have a survival floor (readiness ≥ 2).",
        check=lambda target_die, side, all_dice, idx: (
            "armor" in _label(side) and "end of each turn" in _label(side)
            and _avg_non_starter_sides_across(all_dice) < 2.0
        ),
    ),
    ComboRule(
        name="passive_str_per_turn_early",
        bonus=0.4,
        description="PENALTY: '(p) Gain N Strength at the end of each turn' is slow. "
                    "A flat Attack 16 clears the same damage in one turn while this takes "
                    "3-4 turns to reach equivalent scaling.",
        check=lambda target_die, side, all_dice, idx: (
            "strength" in _label(side) and "end of each turn" in _label(side)
            and _avg_non_starter_sides_across(all_dice) < 2.0
        ),
    ),
    # ---- early-game priority: strong direct attacks > passive utility ----
    ComboRule(
        name="early_game_direct_damage_bonus",
        bonus=1.5,
        description="Early game (readiness < 2), a high-damage direct attack (≥12) is the "
                    "single best pick. Boost it above debuff removers and passives. "
                    "'Strong attacks and defenses' is the user's rule-of-thumb.",
        check=lambda target_die, side, all_dice, idx: (
            _avg_non_starter_sides_across(all_dice) < 2.0
            and (side.get("damage") or {}).get("value", 0) >= 12
        ),
    ),
    ComboRule(
        name="early_game_strong_poison_bonus",
        bonus=1.4,
        description="Early game, strong poison sides (≥4 stacks, or multi-hit) are a "
                    "legitimate damage option alongside direct attacks. User rule: 'attack "
                    "options also include strong poison options'.",
        check=lambda target_die, side, all_dice, idx: (
            _avg_non_starter_sides_across(all_dice) < 2.0
            and (
                ((side.get("poison") or {}).get("value", 0) >= 4)
                or (((side.get("poison") or {}).get("value", 0) >= 2)
                    and ((side.get("poison") or {}).get("hits", 1) >= 2))
            )
        ),
    ),
    ComboRule(
        name="early_game_direct_block_bonus",
        bonus=1.4,
        description="Early game, a direct block side (≥8 block) is better than conditional "
                    "blocks or passive armor ramps.",
        check=lambda target_die, side, all_dice, idx: (
            _avg_non_starter_sides_across(all_dice) < 2.0
            and (side.get("block") or {}).get("value", 0) >= 8
            and "at the end" not in _label(side)
        ),
    ),
    ComboRule(
        name="debuff_removal_gate_on_readiness",
        bonus=0.5,
        description="PENALTY: Debuff removal sides (Block 4 remove debuff, Exhaust curses) "
                    "are too weak to pick early game. The survival value of a strong Attack "
                    "or Block beats the situational cleanup. User: 'Block 4 can be useful "
                    "late game but early game you need strong block and attack options'.",
        check=lambda target_die, side, all_dice, idx: (
            is_debuff_remover(side)
            and _avg_non_starter_sides_across(all_dice) < 2.0
        ),
    ),
    ComboRule(
        name="duplicate_this_side_is_strong",
        bonus=1.6,
        description="'Attack N, Duplicate this Side onto this Die' is strong as a standalone "
                    "pick because the duplicate replaces a random side with another copy of "
                    "the attack, so the die rolls the strong attack more often. Effective "
                    "floor-raising regardless of what else is on the die.",
        check=lambda target_die, side, all_dice, idx: (
            "duplicate this side" in _label(side)
        ),
    ),
]


def _avg_non_starter_sides_across(all_dice) -> float:
    """Average non-starter sides per die across the pool. Low = early game."""
    if not all_dice:
        return 0.0
    counts = []
    for d in all_dice:
        if not isinstance(d, dict):
            continue
        ns = 0
        for a in _abilities(d):
            tags = [t.get("label") for t in (a.get("tags") or []) if isinstance(t, dict)]
            if "Starter" not in tags:
                ns += 1
        counts.append(ns)
    return sum(counts) / len(counts) if counts else 0.0


def _survival_floor_met(all_dice) -> bool:
    """True if the player's dice pool has the minimum survival floor.

    Current definition: at least one Attack side with value ≥12 anywhere,
    AND at least one heal side anywhere.

    Until this is true, the scorer aggressively deprioritizes scoring and
    prefers heal/defense/high-attack upgrades.
    """
    if not all_dice:
        return False
    has_strong_attack = False
    has_heal = False
    for die in all_dice:
        for ab in _abilities(die):
            dmg = ab.get("damage") or {}
            if isinstance(dmg, dict) and dmg.get("value", 0) >= 12:
                has_strong_attack = True
            if is_heal(ab):
                has_heal = True
            if has_strong_attack and has_heal:
                return True
    return False


def compute_synergy_bonus(target_die, offered_side, all_dice, target_die_index=None) -> tuple:
    """Evaluate all combo rules against this target/offer/state.

    Returns (multiplier, [matched_rule_names]).
    """
    mult = 1.0
    matched = []
    for rule in COMBO_RULES:
        try:
            if rule.check(target_die, offered_side, all_dice, target_die_index):
                mult *= rule.bonus
                matched.append(rule.name)
        except Exception:
            pass
    return mult, matched
