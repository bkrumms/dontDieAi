"""Dice and sides data model.

A Side is a face of a die carrying damage / block / heal / status-effect
application / scoring info. A Die is a list of sides (typically 4-6).

The canonical starter dice composition is exposed here. It was confirmed
from live API data in run 1 and re-confirmed by the user on 2026-04-13:

  Die 1: Gain 3 Armor, Gain 3 Strength, Attack 4, Poison 3
  Die 2: Attack 4, Attack 4, Attack All 4, Attack 6 Bleed 2
  Die 3: Attack 4, Attack 4, Block 6, Block 6
  Die 4: Block 6, Block 6, Block 6, (e) Block 10 Freeze All 3
"""
from dataclasses import dataclass, field
import random


@dataclass
class Side:
    label: str
    # Offensive
    damage: int = 0
    hits: int = 1
    target: str = "single"  # "single" | "all"
    # Defensive
    block: int = 0
    heal: int = 0
    # Debuffs applied to enemy
    poison_stacks: int = 0
    poison_hits: int = 1
    poison_target: str = "single"
    bleed_duration: int = 0
    bleed_target: str = "single"
    freeze_duration: int = 0
    freeze_target: str = "single"
    # Stat debuffs applied to enemy (user-asked 2026-04-14)
    strength_enemy: int = 0        # reduce enemy.strength by N (this turn)
    strength_enemy_target: str = "single"
    strength_enemy_this_turn: bool = False  # True = revert at end of enemy phase
    armor_enemy: int = 0           # reduce enemy.armor by N (permanent)
    armor_enemy_target: str = "single"
    # Self buffs
    strength_self: int = 0
    armor_self: int = 0
    # Conditional / passive effects (specialEffect types)
    block_if_no_block: int = 0          # "Block 24 if you have no block"
    block_per_baddie: int = 0           # "Block 8 per Baddie"
    block_per_debuff_on_self: int = 0   # "Block 8 per Freeze or Bleed on you"
    attack_give_defend: int = 0         # passive: N block per attack rolled this turn
    passive_heal_per_turn: int = 0      # (p) Heal N at the end of each turn
    passive_str_per_turn: int = 0       # (p) Gain N Strength at end of turn
    passive_block_per_turn: int = 0     # (p) Block N at end of turn
    multiply_largest_attack: float = 0.0  # (e) 2× the largest attack — computed at fire time
    # Scoring
    score_base: int = 10          # per-roll base: Starter/L1=10, L2=20, L3=30, L3Boss=100
    score_flat_bonus: int = 0     # "Score N Points" secondary effect
    # Meta
    exhaust: bool = False
    is_curse: bool = False


@dataclass
class Die:
    sides: list
    name: str = ""
    exhausted: set = field(default_factory=set)  # indices already fired this battle

    def roll(self, rng: random.Random):
        idx = rng.randrange(len(self.sides))
        side = self.sides[idx]
        already_exhausted = idx in self.exhausted
        return side, idx, already_exhausted

    def reset(self):
        self.exhausted.clear()


# --------------------------------------------------------------------
# Starter side definitions
# --------------------------------------------------------------------
def _starter_sides() -> dict:
    return {
        "str3": Side(label="Gain 3 Strength", strength_self=3, exhaust=True),
        "arm3": Side(label="Gain 3 Armor",    armor_self=3,    exhaust=True),
        "a4":   Side(label="Attack 4",        damage=4),
        "p3":   Side(label="Poison 3",        poison_stacks=3),
        "aa4":  Side(label="Attack All 4",    damage=4, target="all"),
        "a6b":  Side(label="Attack 6 Bleed 2", damage=6, bleed_duration=2),
        "b6":   Side(label="Block 6",         block=6),
        "sf":   Side(
            label="(e) Block 10, Freeze All 3",
            block=10, freeze_duration=3, freeze_target="all", exhaust=True,
        ),
    }


def make_starter_dice() -> list:
    """Return a fresh list of 4 Die objects with canonical starter sides."""
    s = _starter_sides()
    return [
        Die(name="Die 1", sides=[s["arm3"], s["str3"], s["a4"],  s["p3"]]),
        Die(name="Die 2", sides=[s["a4"],   s["a4"],   s["aa4"], s["a6b"]]),
        Die(name="Die 3", sides=[s["a4"],   s["a4"],   s["b6"],  s["b6"]]),
        Die(name="Die 4", sides=[s["b6"],   s["b6"],   s["b6"],  s["sf"]]),
    ]
