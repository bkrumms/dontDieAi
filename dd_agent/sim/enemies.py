"""Chapter 1 enemy attack patterns.

Patterns follow Nick's `Baddie Attack Patterns` sheet (2026-04-13 export).
Each enemy has a fixed pattern prefix and (optionally) a repeat loop plus
a weighted rand pool for turns flagged as random.

API:
  action_on_turn(enemy, turn, rng) -> EnemyAction
"""
from dataclasses import dataclass, field
import random


@dataclass
class EnemyAction:
    label: str = ""
    # Effects targeting the player
    damage: int = 0
    hits: int = 1
    applies_poison: int = 0
    applies_bleed_duration: int = 0
    applies_freeze_duration: int = 0
    apply_curse_count: int = 0
    exhaust_random_side: bool = False
    # Self effects
    self_block: int = 0
    self_strength: int = 0
    self_armor: int = 0
    rehealth: int = 0
    attack_equal_block: bool = False  # Frostmaul T3


@dataclass
class Enemy:
    name: str
    hp_base: int
    hp_variance: int
    points: int
    pattern: list                   # list[Optional[EnemyAction]]; None = rand slot
    repeat_from: int = 0            # 0-indexed turn to loop from once pattern is exhausted
    rand_pool: list = field(default_factory=list)  # list[(weight, EnemyAction)]
    stacks_block_forever: bool = False
    # runtime — reset before each battle by simulate_battle
    current_hp: int = 0
    rolled_max_hp: int = 0
    strength: int = 0
    armor: int = 0
    block: int = 0
    poison: int = 0
    bleed_turns: int = 0
    freeze_turns: int = 0


def roll_hp(enemy: Enemy, rng: random.Random) -> int:
    v = enemy.hp_variance
    return max(1, enemy.hp_base + rng.randint(-v, v))


def _weighted_pick(pool, rng):
    total = sum(w for w, _ in pool)
    r = rng.random() * total
    cum = 0.0
    for w, action in pool:
        cum += w
        if r <= cum:
            return action
    return pool[-1][1]


def action_on_turn(enemy: Enemy, turn: int, rng: random.Random) -> EnemyAction:
    """Return the EnemyAction for 1-indexed turn N."""
    idx = turn - 1
    pattern = enemy.pattern
    if idx < len(pattern):
        slot = pattern[idx]
    else:
        loop_length = len(pattern) - enemy.repeat_from
        if loop_length <= 0:
            return EnemyAction(label="idle")
        position = (idx - len(pattern)) % loop_length
        slot = pattern[enemy.repeat_from + position]

    if slot is not None:
        return slot
    if enemy.rand_pool:
        return _weighted_pick(enemy.rand_pool, rng)
    return EnemyAction(label="idle")


# --------------------------------------------------------------------
# Chapter 1 common baddies
# --------------------------------------------------------------------
def ice_pufflet() -> Enemy:
    return Enemy(
        name="Ice Pufflet",
        hp_base=32, hp_variance=2, points=100,
        pattern=[
            EnemyAction(label="Freeze 2", applies_freeze_duration=2),
            EnemyAction(label="8", damage=8),
            None,  # T3+ rand
        ],
        repeat_from=2,
        rand_pool=[
            (0.40, EnemyAction(label="8 + Freeze 2", damage=8, applies_freeze_duration=2)),
            (0.30, EnemyAction(label="+3 Strength",  self_strength=3)),
            (0.30, EnemyAction(label="12",           damage=12)),
        ],
    )


def black_firant() -> Enemy:
    return Enemy(
        name="Black Firant",
        hp_base=9, hp_variance=2, points=100,
        pattern=[
            EnemyAction(label="6 + Bleed 1",  damage=6, applies_bleed_duration=1),
            EnemyAction(label="10",           damage=10),
            EnemyAction(label="14 + Bleed 2", damage=14, applies_bleed_duration=2),
            EnemyAction(label="+8 Strength",  self_strength=8),
        ],
        repeat_from=0,  # T5+ loops 1-4
    )


def blue_firant() -> Enemy:
    return Enemy(
        name="Blue Firant",
        hp_base=24, hp_variance=2, points=100,
        pattern=[
            EnemyAction(label="6 + Block 6",     damage=6, self_block=6),
            EnemyAction(label="Exhaust 1 Side",  exhaust_random_side=True),
            None, None,  # T3-4 rand
        ],
        repeat_from=2,
        rand_pool=[
            (0.55, EnemyAction(label="9 + Block 9",    damage=9, self_block=9)),
            (0.15, EnemyAction(label="Exhaust 1 Side", exhaust_random_side=True)),
            (0.30, EnemyAction(label="+6 Str +3 Arm",  self_strength=6, self_armor=3)),
        ],
    )


def baby_scarebug() -> Enemy:
    return Enemy(
        name="Baby Scarebug",
        hp_base=22, hp_variance=2, points=100,
        pattern=[
            EnemyAction(label="Poison 1", applies_poison=1),
            EnemyAction(label="Poison 1", applies_poison=1),
            EnemyAction(label="Poison 2", applies_poison=2),
            EnemyAction(label="Poison 3", applies_poison=3),
            EnemyAction(label="Poison 4", applies_poison=4),
        ],
        repeat_from=4,  # T6+ = Poison 4 forever
    )


def frostmaul() -> Enemy:
    return Enemy(
        name="Frostmaul",
        hp_base=36, hp_variance=2, points=200,
        pattern=[
            EnemyAction(label="Block 20",        self_block=20),
            EnemyAction(label="Block 8",         self_block=8),
            EnemyAction(label="Attack = Block",  attack_equal_block=True),
            None,  # T4+ rand
        ],
        repeat_from=0,
        rand_pool=[
            (0.70, EnemyAction(label="12 + Freeze 3", damage=12, applies_freeze_duration=3)),
            (0.30, EnemyAction(label="12 + Block 12", damage=12, self_block=12)),
        ],
        stacks_block_forever=True,
    )


def cobra_frier() -> Enemy:
    return Enemy(
        name="Cobra Frier",
        hp_base=36, hp_variance=2, points=200,
        pattern=[
            None,  # T1 rand
            None,  # T2 rand
            EnemyAction(label="+4 Strength", self_strength=4),
        ],
        repeat_from=0,
        rand_pool=[
            (0.50, EnemyAction(label="8 + Bleed 2", damage=8, applies_bleed_duration=2)),
            (0.50, EnemyAction(label="14",          damage=14)),
        ],
    )


def kevin() -> Enemy:
    return Enemy(
        name="Kevin",
        hp_base=44, hp_variance=2, points=200,
        pattern=[
            EnemyAction(label="Rehealth 14",         rehealth=14),
            EnemyAction(label="16",                  damage=16),
            EnemyAction(label="12 + Rehealth 10",    damage=12, rehealth=10),
            EnemyAction(label="Block 30",            self_block=30),
        ],
        repeat_from=0,
    )


def lil_zomboid() -> Enemy:
    return Enemy(
        name="Lil Zomboid",
        hp_base=40, hp_variance=2, points=200,
        pattern=[
            None,  # T1 rand
            EnemyAction(label="Poison 1", applies_poison=1),
            EnemyAction(label="8", damage=8),
            None,  # T4 rand
        ],
        repeat_from=0,
        rand_pool=[
            (0.50, EnemyAction(label="Freeze 2 + Bleed 2",
                               applies_freeze_duration=2, applies_bleed_duration=2)),
            (0.50, EnemyAction(label="8", damage=8)),
        ],
    )


def rock_lobster() -> Enemy:
    return Enemy(
        name="Rock Lobster",
        hp_base=38, hp_variance=2, points=200,
        pattern=[
            EnemyAction(label="16",              damage=16),
            EnemyAction(label="Block 20",        self_block=20),
            EnemyAction(label="Block 15",        self_block=15),
            EnemyAction(label="10 + Block 10",   damage=10, self_block=10),
            EnemyAction(label="+5 Str +5 Arm",   self_strength=5, self_armor=5),
        ],
        repeat_from=0,
        stacks_block_forever=True,
    )


# --------------------------------------------------------------------
# Chapter 1 Big Baddies (simplified single-target)
# --------------------------------------------------------------------
def wendibrrr() -> Enemy:
    return Enemy(
        name="Wendibrrr",
        hp_base=96, hp_variance=2, points=500,
        pattern=[
            EnemyAction(label="Add Curse",             apply_curse_count=1),
            EnemyAction(label="Block 20 + Freeze 7",   self_block=20,
                        applies_freeze_duration=7),
            EnemyAction(label="16 + Block 6",          damage=16, self_block=6),
            EnemyAction(label="20",                    damage=20),
            EnemyAction(label="Add Curse",             apply_curse_count=1),
            EnemyAction(label="+10 Strength",          self_strength=10),
        ],
        repeat_from=2,  # T7+ loops 3-6
    )


def firant_queen_solo() -> Enemy:
    # Simplified as a solo fight; the real encounter also spawns 3 Firants.
    return Enemy(
        name="Firant Queen (solo, simplified)",
        hp_base=68, hp_variance=2, points=500,
        pattern=[
            EnemyAction(label="8",            damage=8),
            EnemyAction(label="12",           damage=12),
            EnemyAction(label="Rehealth 12",  rehealth=12),
            EnemyAction(label="8",            damage=8),
            EnemyAction(label="12",           damage=12),
            EnemyAction(label="+6 Strength",  self_strength=6),
        ],
        repeat_from=3,  # T7+ loops 4-6
    )


def ganondwarf() -> Enemy:
    """Chapter 1 final boss. 160 HP.

    T1: Freeze 4 + Bleed 3 + Poison 2 (triple debuff — this is why Ice Rice wins)
    T2: 14 damage
    T3: 8 damage, 2 times (16 total)
    T4: 12 damage, 2 times (24 total)
    T5: Block 20 + 8 Strength
    T6+: repeat 2-5
    """
    return Enemy(
        name="Ganondwarf",
        hp_base=160, hp_variance=2, points=1000,
        pattern=[
            EnemyAction(
                label="Freeze 4 + Bleed 3 + Poison 2",
                applies_freeze_duration=4,
                applies_bleed_duration=3,
                applies_poison=2,
            ),
            EnemyAction(label="14", damage=14),
            EnemyAction(label="8 x2", damage=8, hits=2),
            EnemyAction(label="12 x2", damage=12, hits=2),
            EnemyAction(label="Block 20 + 8 Str", self_block=20, self_strength=8),
        ],
        repeat_from=1,  # T6+ loops 2-5
    )


def gorgon_zola() -> Enemy:
    return Enemy(
        name="Gorgon-zola",
        hp_base=80, hp_variance=2, points=500,
        pattern=[
            EnemyAction(label="Poison 3",          applies_poison=3),
            EnemyAction(label="Block 24",          self_block=24),
            EnemyAction(label="18",                damage=18),
            EnemyAction(label="Poison 3",          applies_poison=3),
            EnemyAction(label="+6 Str +6 Arm",     self_strength=6, self_armor=6),
            EnemyAction(label="Block 24",          self_block=24),
            EnemyAction(label="Poison 3",          applies_poison=3),
            EnemyAction(label="18",                damage=18),
        ],
        repeat_from=4,  # T9+ loops 5-8
    )


# --------------------------------------------------------------------
# Chapter 2 big-baddies and bosses
#
# Simplifications vs real game (because the sim doesn't model these yet):
# - Pterrordactyl's "Steal all player armor" is approximated as fixed 10 dmg.
# - Pterrordactyl's "Starts with 3 Negate Debuffs" is NOT modeled — debuff
#   strategies will over-perform in sim vs reality.
# - Detonox's "HP-loss → +3 Strength" passive is approximated by applying
#   +2 self_strength on each action turn (slightly lower because it
#   wouldn't trigger on whiff turns).
# - Detonox's "Explode after turn 7" is modeled as 100 direct damage on T7.
# - Big Cheeze: we implement the Onslaught mode (Ice Cave + Toxic tied),
#   which is the mode the memory already calls out as Ice Rice-critical.
#   Turn-5 "Melt all Block + Remove all Debuffs" is NOT modeled — food
#   effects that survive the reset will over-perform.
# --------------------------------------------------------------------
def pterrordactyl() -> Enemy:
    """Chapter 2 big-baddie. 280 HP. Heavy block + burst damage.

    T1: 24 | T2: Block 40 | T3: 10 (armor steal approx) | T4: 30 + Block 5 |
    T5: idle (negate refresh) | T6: 30 + Block 10 | T7: 10 (armor steal) |
    T8: 24 + Block 5 | T9: 40 + Block 10 | T10+: repeat 7-9.
    """
    return Enemy(
        name="Pterrordactyl",
        hp_base=280, hp_variance=2, points=800,
        pattern=[
            EnemyAction(label="24",                     damage=24),
            EnemyAction(label="Block 40",               self_block=40),
            EnemyAction(label="Steal Armor (~10)",      damage=10),
            EnemyAction(label="30 + Block 5",           damage=30, self_block=5),
            EnemyAction(label="Negate Debuffs (idle)"),
            EnemyAction(label="30 + Block 10",          damage=30, self_block=10),
            EnemyAction(label="Steal Armor (~10)",      damage=10),
            EnemyAction(label="24 + Block 5",           damage=24, self_block=5),
            EnemyAction(label="40 + Block 10",          damage=40, self_block=10),
        ],
        repeat_from=6,  # T10+ loops 7-9
    )


def detonox() -> Enemy:
    """Chapter 2 big-baddie. 240 HP. Bleed-stack opener, self-destructs T7.

    T1: Bleed 3 | T2: Bleed 2 | T3: Bleed 1 | T4: 12 | T5: 12 + Bleed 3 |
    T6: 1 x3 | T7: 100 damage (EXPLODE — self-destructs, ending battle).
    """
    return Enemy(
        name="Detonox",
        hp_base=240, hp_variance=2, points=800,
        pattern=[
            EnemyAction(label="Bleed 3",     applies_bleed_duration=3),
            EnemyAction(label="Bleed 2",     applies_bleed_duration=2),
            EnemyAction(label="Bleed 1",     applies_bleed_duration=1),
            EnemyAction(label="12",          damage=12),
            EnemyAction(label="12 + Bleed 3", damage=12, applies_bleed_duration=3),
            EnemyAction(label="1 x3",        damage=1, hits=3),
            EnemyAction(label="EXPLODE 100", damage=100),
        ],
        repeat_from=6,  # T8+ idle (shouldn't get here — explodes T7)
    )


def big_cheeze_shield() -> Enemy:
    """Chapter 2 boss — Shield Mode (700 HP).

    Triggered when player has Volcano majority in L3 biome tags. This
    was the mode observed in v14 run #26. Counter is burst damage (the
    block/armor stacks make sustained damage painful).

    T1: Cheezy Glitch (idle)
    T2: Armor 15 + passive Block 5/turn (approximated as self_block 15)
    T3: Block 20 + Poison 7
    T4: 40 dmg + Armor 10
    T5: idle (Melt reset, NOT MODELED)
    T6: idle (Exhaust all, NOT MODELED)
    T7+: rand pool
    """
    return Enemy(
        name="Big Cheeze (Shield)",
        hp_base=700, hp_variance=2, points=2000,
        pattern=[
            EnemyAction(label="Cheezy Glitch (idle)"),
            EnemyAction(label="Armor 15 + Block 5/turn",
                        self_armor=15, self_block=15),
            EnemyAction(label="Block 20 + Poison 7",
                        self_block=20, applies_poison=7),
            EnemyAction(label="40 + Armor 10", damage=40, self_armor=10),
            EnemyAction(label="Reset (idle, NOT MODELED)"),
            EnemyAction(label="Exhaust (idle, NOT MODELED)"),
            None,  # T7+ rand
        ],
        repeat_from=6,
        rand_pool=[
            (35, EnemyAction(label="Block 15 + Poison 7",
                             self_block=15, applies_poison=7)),
            (35, EnemyAction(label="12 x4", damage=12, hits=4)),
            (30, EnemyAction(label="Exhaust 1 side",
                             exhaust_random_side=True)),
        ],
    )


def zomboid_horde() -> Enemy:
    """Chapter 2 boss — Zomboid Horde (simplified aggregate).

    The real fight is a 5-monster sequential gauntlet:
    Lil Zomboid(40) → Crystal Zomboid(42) → Infernal Zomboid(116) →
    Necrotic Zomboid(154) → Cryonic Zomboid(190) = 542 total HP.

    The sim doesn't model multi-stage battles, so this is approximated
    as a single super-enemy with pooled HP and a damage pattern that
    mixes the worst behaviors of each: Infernal's +4 Str/turn (modeled
    as self_strength 2/turn amortized), Cryonic's block stacking,
    Necrotic's heal + poison. Useful ONLY for food differentiation —
    do not use for strategy tuning outside of that.
    """
    return Enemy(
        name="Zomboid Horde (aggregate)",
        hp_base=542, hp_variance=2, points=2000,
        pattern=[
            EnemyAction(label="Poison 2 x2",    applies_poison=4),
            EnemyAction(label="14",             damage=14),
            EnemyAction(label="Heal 12",        rehealth=12),
            EnemyAction(label="Bleed 3 + Poison 2",
                        applies_bleed_duration=3, applies_poison=2),
            EnemyAction(label="Block 12 + 6 Str",
                        self_block=12, self_strength=6),
            EnemyAction(label="12 + Block 12",  damage=12, self_block=12),
            EnemyAction(label="Block 12 + Freeze 5",
                        self_block=12, applies_freeze_duration=5),
            None,  # T8+ rand
        ],
        repeat_from=7,
        rand_pool=[
            (40, EnemyAction(label="6 + Block 4", damage=6, self_block=4)),
            (30, EnemyAction(label="Strength 18", self_strength=18)),
            (30, EnemyAction(label="8 x2",        damage=8, hits=2)),
        ],
    )


def big_cheeze_onslaught() -> Enemy:
    """Chapter 2 boss — Onslaught Mode (700 HP).

    Triggered when player has Ice Cave + Toxic tied in L3 biome majority.
    Memory calls out Ice Rice as the counter (T2's triple-source debuff).

    T1: Cheezy Glitch (idle)
    T2: 20 + Poison 5 + Bleed 2
    T3: 12 x3 (36 total)
    T4: Poison 3 + 3 Strength
    T5: "Melt all block + remove debuffs" — NOT MODELED (idle)
    T6: Add Bleed Curses (NOT MODELED — idle)
    T7+: rand pool
    """
    return Enemy(
        name="Big Cheeze (Onslaught)",
        hp_base=700, hp_variance=2, points=2000,
        pattern=[
            EnemyAction(label="Cheezy Glitch (idle)"),
            EnemyAction(
                label="20 + Poison 5 + Bleed 2",
                damage=20, applies_poison=5, applies_bleed_duration=2,
            ),
            EnemyAction(label="12 x3", damage=12, hits=3),
            EnemyAction(label="Poison 3 + 3 Str", applies_poison=3, self_strength=3),
            EnemyAction(label="Reset (idle, NOT MODELED)"),
            EnemyAction(label="Curse (idle, NOT MODELED)"),
            None,  # T7+ rand
        ],
        repeat_from=6,
        rand_pool=[
            (40, EnemyAction(label="8 x4",            damage=8, hits=4)),
            (40, EnemyAction(label="Poison 5 + 5 Str",
                             applies_poison=5, self_strength=5)),
            (20, EnemyAction(label="Block 50",        self_block=50)),
        ],
    )


def deathbat() -> Enemy:
    """Chapter 2 big-baddie (Toxic Swamp obelisk). 144 HP. Summoner.

    T1: Summon Battys (not modeled — sim treats as idle)
    T2: 6 damage
    T3: Strength 6
    T4: Summon (idle)
    T5: 6 damage
    T6: 34 damage + Heal 70
    T7: Summon (idle)
    T8: Strength 10
    T9: 6 damage
    T10+: repeat 8-9

    NOTE: summon mechanic not modeled — real Deathbat fills empty slots
    with Battys (22 HP each, attack 4-6/turn). This makes the sim
    optimistic; the actual fight is harder due to Batty chip damage.
    """
    return Enemy(
        name="Deathbat",
        hp_base=144, hp_variance=2, points=800,
        pattern=[
            EnemyAction(label="Summon"),             # T1: idle (summon not modeled)
            EnemyAction(label="6", damage=6),        # T2
            EnemyAction(label="Str 6", self_strength=6),  # T3
            EnemyAction(label="Summon"),             # T4: idle
            EnemyAction(label="6", damage=6),        # T5
            EnemyAction(label="34 + Heal 70", damage=34, rehealth=70),  # T6
            EnemyAction(label="Summon"),             # T7: idle
            EnemyAction(label="Str 10", self_strength=10),  # T8
            EnemyAction(label="6", damage=6),        # T9
        ],
        repeat_from=7,  # T10+ loops 8-9
    )


ENEMIES = {
    "ice_pufflet":   ice_pufflet,
    "black_firant":  black_firant,
    "blue_firant":   blue_firant,
    "baby_scarebug": baby_scarebug,
    "frostmaul":     frostmaul,
    "cobra_frier":   cobra_frier,
    "kevin":         kevin,
    "lil_zomboid":   lil_zomboid,
    "rock_lobster":  rock_lobster,
    "wendibrrr":     wendibrrr,
    "firant_queen":  firant_queen_solo,
    "gorgon_zola":   gorgon_zola,
    "ganondwarf":    ganondwarf,
    "pterrordactyl": pterrordactyl,
    "detonox":       detonox,
    "deathbat":      deathbat,
    "big_cheeze_onslaught": big_cheeze_onslaught,
    "big_cheeze_shield":    big_cheeze_shield,
    "zomboid_horde":        zomboid_horde,
}


# =====================================================================
# Chapter 1 fight compositions (from Nick's Baddie Attack Patterns sheet,
# "Chapter 1 Battle List" tab, rows 47-89 of the TSV export).
#
# Fight pools by space range:
#   B Fights 1 = spaces 1-5
#   B Fights 2 = spaces 6-13
#   B Fights 3 = spaces 14-23
#   B Fights 4 = spaces 24-39 (with 25 = Big Baddie stop fight, 39 = Boss)
#
# Within each pool fights are tagged by biome: Neutral, Ice Cave, Volcano,
# Toxic Swamp. The game picks a fight based on current biome then neutral
# fallback (see knowledge/game/database/baddies.md "battle selection algorithm").
# =====================================================================

# Pool 1 — spaces 1-5 (Neutral only; no biome fights in this pool per sheet)
FIGHTS_POOL_1 = {
    "p1_neutral_black_firant_x2":  lambda: [black_firant(), black_firant()],
    "p1_neutral_ice_pufflet":      lambda: [ice_pufflet()],
    "p1_neutral_baby_scarebug":    lambda: [baby_scarebug()],
}

# Pool 2 — spaces 6-13
FIGHTS_POOL_2 = {
    "p2_ice_pufflet_x2":           lambda: [ice_pufflet(), ice_pufflet()],
    "p2_frostmaul":                lambda: [frostmaul()],
    "p2_black_firant_cobra_frier": lambda: [black_firant(), cobra_frier()],
    "p2_cobra_frier_random_firant": lambda: [cobra_frier(), black_firant()],  # TODO rand
    "p2_baby_scarebug_lil_zomboid": lambda: [baby_scarebug(), lil_zomboid()],
    "p2_kevin":                    lambda: [kevin()],
    "p2_rock_lobster_black_firant": lambda: [rock_lobster(), black_firant()],
    "p2_lil_zomboid_x2":           lambda: [lil_zomboid(), lil_zomboid()],
}

# Pool 3 — spaces 14-23
FIGHTS_POOL_3 = {
    "p3_frostmaul_ice_pufflet":    lambda: [frostmaul(), ice_pufflet()],
    "p3_ice_pufflet_rock_lobster": lambda: [ice_pufflet(), rock_lobster()],
    "p3_black_firant_x3_random":   lambda: [black_firant(), black_firant(), black_firant()],
    "p3_blue_firant_x3":           lambda: [blue_firant(), blue_firant(), blue_firant()],
    "p3_baby_scarebug_x2":         lambda: [baby_scarebug(), baby_scarebug()],
    "p3_lil_zomboid_kevin":        lambda: [lil_zomboid(), kevin()],
    "p3_rock_lobster_black_firant": lambda: [rock_lobster(), black_firant()],
    "p3_lil_zomboid_x2":           lambda: [lil_zomboid(), lil_zomboid()],
}

# Pool 4 — spaces 24-39 (regular fights; 25 and 39 are stop fights below)
FIGHTS_POOL_4 = {
    "p4_frostmaul_x2_lil_zomboid":      lambda: [frostmaul(), frostmaul(), lil_zomboid()],
    "p4_frostmaul_rock_lobster":        lambda: [frostmaul(), rock_lobster()],
    "p4_cobra_frier_blue_firant":       lambda: [cobra_frier(), blue_firant()],
    "p4_black_firant_blue_firant_cobra": lambda: [black_firant(), blue_firant(), cobra_frier()],
    "p4_kevin_baby_scarebug":           lambda: [kevin(), baby_scarebug()],
    "p4_baby_scarebug_x3":              lambda: [baby_scarebug(), baby_scarebug(), baby_scarebug()],
}

# Chapter 1 Big Baddie stop fights (space 25)
BB_FIGHTS_CH1 = {
    "bb_ice_wendibrrr":   lambda: [wendibrrr()],
    "bb_volcano_firant_queen": lambda: [black_firant(), black_firant(), firant_queen_solo(), blue_firant()],
    "bb_toxic_gorgon_zola": lambda: [gorgon_zola()],
}


FIGHTS_CH1_ALL = {}
for d in (FIGHTS_POOL_1, FIGHTS_POOL_2, FIGHTS_POOL_3, FIGHTS_POOL_4, BB_FIGHTS_CH1):
    FIGHTS_CH1_ALL.update(d)
