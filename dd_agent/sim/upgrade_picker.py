"""Upgrade-picker module.

Given a die index and a list of offered sides (from the pick-dice response),
score each side for that die's role and return the best pick.

The scoring logic encodes the user's strategic rules:
  Die 1 (utility) — anything non-curse; exhaust-synergy bonus
  Die 2 (attack)  — only Attack/Poison; defense = negative
  Die 3 (mixed)   — scoring preferred
  Die 4 (defense) — only Block/Armor; attack = negative

All live-API side dicts carry fields like:
  damage, block, heal, poison, bleed, freeze, strength, armor, specialEffect,
  tags (list of {label, tagId}), exhaust, sideType, label

We rank by:
  1. hard vetoes (curses, role-mismatch) → very negative
  2. per-roll base points (Starter/L1=10, L2=20, L3=30, L3Boss=100)
  3. role-fit multiplier
  4. tiebreakers (exhaust bonus on Die 1, biome matching, etc.)
"""
from __future__ import annotations


# Die index (0-based) → role
DIE_ROLES = {
    0: "utility",  # Die 1 — Armor + Strength + Attack + Poison
    1: "attack",   # Die 2 — pure attacks
    2: "mixed",    # Die 3 — attacks + blocks, flexible
    3: "defense",  # Die 4 — all block + snowflake
}


def _tags(side: dict) -> list:
    raw = side.get("tags") or []
    return [t.get("label") for t in raw if isinstance(t, dict) and t.get("label")]


def _pool_tier(side: dict) -> str:
    """Return 'Starter' | 'L1' | 'L2' | 'L3' | 'L3Boss' | 'Curse' | 'EchoDagger' | 'Unknown'."""
    tags = _tags(side)
    if "Curse" in tags:
        return "Curse"
    if "Level 3 Boss" in tags:
        return "L3Boss"
    if "Level 3" in tags:
        return "L3"
    if "Level 2" in tags:
        return "L2"
    if "Level 1" in tags:
        return "L1"
    if "Starter" in tags:
        return "Starter"
    if side.get("label", "").startswith("Echo") or "Echo Dagger" in tags:
        return "EchoDagger"
    return "Unknown"


def _base_points(tier: str) -> int:
    return {
        "Starter": 10, "L1": 10, "L2": 20, "L3": 30,
        "L3Boss": 100, "EchoDagger": 30, "Curse": 0, "Unknown": 10,
    }.get(tier, 10)


def classify_side(side: dict) -> str:
    """Classify a side's primary category: attack/defense/utility/scoring/curse/heal.

    Priority order (most reliable signals first):
      1. Curse tag → curse
      2. Label keywords (robust against specialEffect-wrapped fields)
      3. specialEffect.type keywords
      4. Direct field presence
    """
    tags = _tags(side)
    if "Curse" in tags:
        return "curse"

    label = (side.get("label") or "").lower()
    side_type = (side.get("sideType") or "").lower()
    special = side.get("specialEffect") or {}
    se_type = (special.get("type") or "").lower() if isinstance(special, dict) else ""

    # 1. Scoring — label or specialEffect mentions points/score
    if "score" in label or "point" in label:
        return "scoring"
    if "point" in se_type or "gainpoint" in se_type:
        return "scoring"

    # 2. Label-based detection (covers conditional/special-effect sides)
    if "unblocked" in label and ("heal" in label or "attack" in label):
        return "heal"
    if "block" in label or "armor" in label or "attack equal to block" in label:
        # "Block 8, Poison 3" / "Block 8, Bleed 3" are primarily offensive
        # (poison/bleed ticks do the real work). But "Block 8 per Freeze or
        # Bleed on you" is a conditional block side — the "bleed" refers to
        # a debuff ON THE PLAYER, not applied to enemies.
        if ("poison" in label or "bleed" in label) and "per" not in label and "on you" not in label:
            return "attack"
        return "defense"
    if "attack" in label or "damage" in label:
        return "attack"
    if "poison" in label or "bleed" in label:
        return "attack"
    if "freeze" in label:
        # Applying freeze to an enemy is offensive support
        return "attack"
    if "heal" in label:
        return "heal"
    if "strength" in label:
        return "utility"

    # 3. specialEffect-based detection
    if "block" in se_type or "armor" in se_type:
        return "defense"
    if "damage" in se_type or "attack" in se_type:
        return "attack"
    if "heal" in se_type or "health" in se_type:
        return "heal"
    if "strength" in se_type:
        return "utility"

    # 4. Direct field fallback
    if side.get("damage") or side.get("poison") or side.get("bleed") or side_type == "attack":
        return "attack"
    if side.get("block") or side.get("armor"):
        return "defense"
    if side.get("heal"):
        return "heal"

    return "utility"


def _role_fit(role: str, category: str) -> float:
    """Return a multiplier for how well `category` fits the `role`.

    Survival-first tuning (2026-04-13):
    - Heal, defense, and kill-speed attacks are prioritized.
    - Scoring is de-prioritized across all dice. It only matters once the
      base survival floor is locked in, which happens implicitly via combo
      rules that detect when the build can safely pivot to scoring.
    """
    if category == "curse":
        return -10.0  # hard veto

    if role == "attack":
        # Die 2 — pure attack. Kill speed IS defense (dead enemies can't hit).
        if category == "attack":
            return 2.2
        if category == "heal":
            return 0.6
        if category == "defense":
            return 0.15
        if category == "scoring":
            return 0.4  # de-prioritized
        return 0.5

    if role == "defense":
        # Die 4 — pure defense. Absorb damage.
        if category == "defense":
            return 2.2
        if category == "heal":
            return 1.9  # heals directly support survival
        if category == "attack":
            return 0.15
        if category == "scoring":
            return 0.3  # de-prioritized
        return 0.5

    if role == "utility":
        # Die 1 — heals, buffs, debuff removal, kill-speed attacks
        if category == "heal":
            return 2.0
        if category == "defense":
            return 1.4
        if category == "attack":
            return 1.5  # kill speed matters
        if category == "utility":
            return 1.5  # strength/armor stacking
        if category == "scoring":
            return 0.5  # de-prioritized
        return 1.0

    if role == "mixed":
        # Die 3 — survival-flexible. Was scoring-heavy, now defense/heal first.
        if category == "heal":
            return 2.0
        if category == "defense":
            return 1.7
        if category == "attack":
            return 1.5
        if category == "scoring":
            return 0.5  # was 1.8, reduced to match survival-first principle
        return 1.0

    return 1.0


def score_side_for_die(
    die_index: int,
    side: dict,
    current_die_side_count: int = 4,
    target_die: dict = None,
    all_dice: list = None,
) -> tuple:
    """Return (score, matched_combos) for placing `side` on die at `die_index`.

    If target_die and all_dice are provided, combo synergies are applied on
    top of the base role-fit score.
    """
    from .synergies import compute_synergy_bonus

    tier = _pool_tier(side)
    category = classify_side(side)
    role = DIE_ROLES.get(die_index, "mixed")

    base = _base_points(tier)
    fit = _role_fit(role, category)

    score = base * fit

    # Curse = hard veto regardless of tier
    if category == "curse":
        return -1000.0, ["CURSE"]

    # Penalize over-crowded dice (consistency loss)
    if current_die_side_count >= 6:
        score *= 0.7

    # Boss-tier L3 is so good it deserves an extra bump
    if tier == "L3Boss":
        score *= 1.5

    # Apply combo synergies (context-aware)
    matched = []
    if target_die is not None and all_dice is not None:
        mult, matched = compute_synergy_bonus(target_die, side, all_dice, die_index)
        score *= mult

    return score, matched


def pick_best_side(
    die_index: int,
    offered_sides: list,
    current_die_side_count: int = 4,
    target_die: dict = None,
    all_dice: list = None,
):
    """Return (best_index, best_side, scored_list).

    scored_list is a list of (index, label, score, category, tier, combos)
    tuples for logging/debugging. `combos` is the list of matched combo rule
    names that contributed to the score.
    """
    scored = []
    for i, side in enumerate(offered_sides):
        s, combos = score_side_for_die(
            die_index, side, current_die_side_count,
            target_die=target_die, all_dice=all_dice,
        )
        scored.append((
            i,
            side.get("label", "?"),
            s,
            classify_side(side),
            _pool_tier(side),
            combos,
        ))

    if not scored:
        return None, None, scored

    scored.sort(key=lambda x: x[2], reverse=True)
    best = scored[0]
    best_side = offered_sides[best[0]]
    return best[0], best_side, scored


def _non_starter_count(die) -> int:
    """Count the number of non-starter (upgrade) sides on a die.

    A side is "starter" if its tags include 'Starter'. This is the true
    upgrade count — burning starter sides never changes it, so the die
    rotation stays stable when we burn starters at Bub's / Volcanic
    Spirits / Chronically Tired / Lava of Life etc.
    """
    if not isinstance(die, dict):
        return 0
    count = 0
    for ab in (die.get("ability") or []):
        if not isinstance(ab, dict):
            continue
        tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
        if "Starter" not in tags:
            count += 1
    return count


# Die-rotation priority by biome. The biome of the fight determines which
# pool the offered sides are drawn from, so routing the pick to the die
# whose role matches the biome means the offered sides are more likely
# to synergize.
#
# Ordering is [first-priority, second, third, fourth] by 0-indexed die.
# Die 0 = compounding, Die 1 = kill-speed, Die 2 = mixed, Die 3 = defense.
#
# Neutral (no biome): default rotation, spread picks across all dice.
# Volcano: offensive sides → target D1 (compounding, exhaust payoff), D2 (kill-speed), D3 (mixed).
# Ice Cave: defensive/freeze sides → target D3 (defense), D4-as-alternate, D1 (compounding).
#   Wait: D4 is idx 3, D3 is idx 2. The defensive die has the Block 6 starters — that's idx 3.
# Toxic Swamp: poison sides → target D1 (compounding, has poison starter), D3 (mixed).
_BIOME_PRIORITY = {
    None:          [0, 3, 1, 2],  # neutral — existing default
    "":            [0, 3, 1, 2],
    "Volcano":     [0, 1, 2, 3],  # offensive pool → compounding → kill-speed → mixed → defense last
    "Ice Cave":    [3, 2, 0, 1],  # defensive/freeze pool → defense → mixed → compounding → attack last
    "Ice":         [3, 2, 0, 1],
    "Toxic Swamp": [0, 2, 3, 1],  # poison pool → compounding (has Poison 3 starter) → mixed → defense → attack last
    "Swamp":       [0, 2, 3, 1],
}


def _count_offensive_upgrades(dice: list) -> int:
    """Count non-starter sides classified as attack/poison across all dice."""
    count = 0
    for die in (dice or []):
        if not isinstance(die, dict):
            continue
        for ab in (die.get("ability") or []):
            if not isinstance(ab, dict):
                continue
            tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
            if "Starter" in tags:
                continue
            cat = classify_side(ab)
            if cat == "attack":
                count += 1
    return count


def _count_defensive_upgrades(dice: list) -> int:
    """Count non-starter sides classified as defense across all dice."""
    count = 0
    for die in (dice or []):
        if not isinstance(die, dict):
            continue
        for ab in (die.get("ability") or []):
            if not isinstance(ab, dict):
                continue
            tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
            if "Starter" in tags:
                continue
            cat = classify_side(ab)
            if cat == "defense":
                count += 1
    return count


def choose_die_for_upgrade(dice: list, biome: str = None) -> int:
    """Choose which die to upgrade given the current dice state and the
    biome of the fight we just won.

    The biome matters because the loot pool is biome-specific: Ice Cave
    gives defensive sides, Volcano gives offensive, Toxic Swamp gives
    poison. Route the pick to the die whose role matches the pool so the
    offered sides synergize with where they land.

    Balance rule: if defensive upgrades outnumber offensive upgrades,
    bias toward offensive dice (attack/utility) regardless of biome to
    prevent all-block builds that lack kill speed.

    Returns the 0-indexed die to pick. Uses lowest NON-STARTER count
    within the biome-specific priority order as a tiebreak.
    """
    if not dice:
        return 0

    ordered = sorted(dice, key=lambda d: d.get("order", 0) if isinstance(d, dict) else 0)

    off_count = _count_offensive_upgrades(ordered)
    def_count = _count_defensive_upgrades(ordered)

    if def_count > off_count and def_count >= 2:
        priority = [0, 1, 2, 3]
    else:
        priority = _BIOME_PRIORITY.get(biome, _BIOME_PRIORITY[None])

    best_order = None
    best_count = 999
    for p in priority:
        if p < len(ordered):
            count = _non_starter_count(ordered[p])
            if count < best_count:
                best_count = count
                best_order = p
    return best_order if best_order is not None else 0


def pick_burn_target(dice: list) -> tuple:
    """Pick the best die side to burn.

    Returns (die_id, ability_uuid, label, die_index) or (None, None, None, None).

    Priority (confirmed with user 2026-04-13):
      1. Any Curse side (always burn curses first, regardless of die)
      2. **Die 3 Block 6** (shape Die 3 toward attack — matches Chronically
         Tired guidance)
      3. **Die 4 Block 6** (reduce Die 4 Block 6 duplicates — Die 4 has
         three Block 6 starters, burning one drops it to 2 + snowflake)
      4. Die 1 Attack 4 (buffs/utility die benefits from removing the
         weakest starter attack)
      5. Die 1 Poison 3 (if Die 1 has upgraded with a different attack)
      6. Die 3 Attack 4 (late fallback — only if no block)
      7. Die 2 Attack 4 (burn duplicate attacks if Die 2 has upgrades)
      8. Absolute fallback: any Attack 4

    Only burns sides on upgraded dice (ability count > 4) to avoid
    destroying starter balance on untouched dice. Exception: curses
    get burned regardless of die count.
    """
    if not dice:
        return (None, None, None, None)

    ordered = sorted(dice, key=lambda d: d.get("order", 0) if isinstance(d, dict) else 0)

    def _tags_of(ab):
        return [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]

    # 1. Curse sweep — burn any curse regardless of where it lives
    for i, die in enumerate(ordered):
        for ab in (die.get("ability") or []):
            if isinstance(ab, dict) and "Curse" in _tags_of(ab):
                return (die.get("id"), ab.get("uuid"), ab.get("label"), i)

    # Structural burns — only on upgraded dice
    def _first_match(die_idx, label_list):
        if die_idx >= len(ordered):
            return None
        die = ordered[die_idx]
        if len(die.get("ability") or []) <= 4:
            return None
        for ab in (die.get("ability") or []):
            if isinstance(ab, dict) and ab.get("label") in label_list:
                return (die.get("id"), ab.get("uuid"), ab.get("label"), die_idx)
        return None

    # 2. Die 3 Block 6 (idx 2) — specialize toward attack
    m = _first_match(2, ["Block 6"])
    if m:
        return m

    # 3. Die 4 Block 6 (idx 3) — reduce duplicates
    m = _first_match(3, ["Block 6"])
    if m:
        return m

    # 4. Die 1 weak starters (idx 0)
    m = _first_match(0, ["Attack 4", "Poison 3"])
    if m:
        return m

    # 5. Die 3 Attack 4 fallback
    m = _first_match(2, ["Attack 4"])
    if m:
        return m

    # 6. Die 2 Attack 4 duplicates (idx 1)
    m = _first_match(1, ["Attack 4"])
    if m:
        return m

    # Absolute fallback: any Attack 4 anywhere — but STILL require the
    # die to have >4 sides, because the server rejects burns that would
    # drop a die below 4 sides.
    for i, die in enumerate(ordered):
        if len(die.get("ability") or []) <= 4:
            continue
        for ab in (die.get("ability") or []):
            if isinstance(ab, dict) and ab.get("label") == "Attack 4":
                return (die.get("id"), ab.get("uuid"), "Attack 4", i)

    return (None, None, None, None)


def pick_burn_target_preboss(dice: list) -> tuple:
    """Pre-boss burn target — concentrate rolls on strong sides.

    Returns (die_id, ability_uuid, label, die_index) or (None, None, None, None).

    Rule (user 2026-04-14): before a boss fight, for each die that has ≥2
    non-starter upgrades, burn the WEAKEST remaining starter. Goal is to
    make the die roll its strong sides more often.

    Priority order:
      1. Any curse (always)
      2. Die with ≥2 upgrades → burn weakest starter (Attack 4 > Poison 3 > Block 6)
      3. Die with 1 upgrade → burn weakest starter
      4. Fallback to generic pick_burn_target
    """
    if not dice:
        return (None, None, None, None)
    ordered = sorted(dice, key=lambda d: d.get("order", 0) if isinstance(d, dict) else 0)

    def _tags_of(ab):
        return [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]

    # 1. Curse sweep
    for i, die in enumerate(ordered):
        for ab in (die.get("ability") or []):
            if isinstance(ab, dict) and "Curse" in _tags_of(ab):
                return (die.get("id"), ab.get("uuid"), ab.get("label"), i)

    # Weakness priority for burn — lower is weaker (burn first).
    burn_priority = {
        "Attack 4": 0, "Poison 3": 1, "Block 6": 2, "Attack 6 Bleed 2": 3,
        "Attack All 4": 4,
    }

    def _weakest_starter(die):
        """Return (ab, rank) of weakest starter side on a die, or None."""
        candidates = []
        for ab in (die.get("ability") or []):
            if not isinstance(ab, dict): continue
            tags = _tags_of(ab)
            if "Starter" not in tags: continue
            label = ab.get("label") or ""
            rank = burn_priority.get(label, 10)
            candidates.append((rank, ab))
        if not candidates: return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    # 2. Dice with most upgrades first — those benefit most from consolidation
    def _upgrade_count(die):
        return sum(
            1 for ab in (die.get("ability") or [])
            if isinstance(ab, dict) and "Starter" not in _tags_of(ab)
        )

    candidates = []
    for i, die in enumerate(ordered):
        if len(die.get("ability") or []) <= 4:
            continue  # server rejects burn if it drops below 4
        upgrades = _upgrade_count(die)
        if upgrades < 1:
            continue
        weakest = _weakest_starter(die)
        if weakest is None:
            continue
        # Prefer dice with more upgrades (higher consolidation payoff)
        candidates.append((-upgrades, i, die, weakest))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        _, i, die, weakest = candidates[0]
        return (die.get("id"), weakest.get("uuid"), weakest.get("label"), i)

    # 3. Fallback to the generic rule if pre-boss rule finds nothing
    return pick_burn_target(dice)


def has_curse(dice: list) -> bool:
    """Quick check: does the player currently carry any Curse side?"""
    for die in dice:
        for ab in (die.get("ability") or []):
            tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
            if "Curse" in tags:
                return True
    return False
