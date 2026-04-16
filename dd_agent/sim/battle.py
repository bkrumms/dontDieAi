"""Battle simulation engine (multi-enemy).

Pure function: given a player state and a list of enemies, returns a
BattleResult. Seeded RNG makes trials reproducible.

Conventions:
- Turn cycle = player phase then enemy phase.
- Single-target attacks hit the first living enemy in the list (front).
- AoE attacks (target="all") hit every living enemy.
- Player block resets at the start of each player phase.
- Each enemy tracks its own block, poison, bleed, freeze, strength, armor.
- Enemy block does NOT reset between turns (multi-turn block stacking).
- Poison ticks at the end of the owner's phase.
- Bleed: +50% incoming damage. Freeze: 25% weaker outgoing attack/block.
"""
from dataclasses import dataclass, field
import random

from .sides import Die
from .enemies import Enemy, EnemyAction, action_on_turn, roll_hp


TURN_LIMIT = 30


@dataclass
class PlayerState:
    hp: int
    max_hp: int
    dice: list
    strength: int = 0
    armor: int = 0
    poison: int = 0
    bleed_turns: int = 0
    freeze_turns: int = 0
    block: int = 0
    damage_mult: float = 1.0
    points_mult: float = 1.0
    negate_debuffs: int = 0
    curses_received: int = 0
    # Passive accumulators (recomputed each turn from dice with passive sides).
    passive_block_on_attack: int = 0    # "N block per attack rolled this turn"
    passive_heal_per_turn_total: int = 0
    passive_str_per_turn_total: int = 0
    passive_block_per_turn_total: int = 0
    # --- food-effect state (set by scripts/sim_food_effects.py) ---
    # Brrrito Blockerito: block carries over instead of resetting for N turns.
    block_stack_turns_remaining: int = 0
    # Pickle: at end of player phase, if block ≤ threshold, add amount.
    pickle_block_threshold: int = 0
    pickle_block_refill: int = 0
    # Clutch Creme: incoming damage ≤ this gets reduced to 1.
    clutch_creme_threshold: int = 0
    # Toxipop: on enemy death, transfer that enemy's poison to next alive enemy.
    toxipop_active: bool = False


@dataclass
class BattleResult:
    won: bool
    reason: str
    turns: int
    player_hp_end: int
    player_max_hp: int
    enemies_label: str
    enemies_hp_end: list
    damage_taken: int
    damage_dealt: int
    max_single_turn_damage: int
    points_from_rolls: int
    points_from_kill: int
    points_from_damage_bonus: int
    points_from_low_hp: int
    points_from_speed: int
    points_from_flat_bonuses: int
    total_points: int
    curses_received: int


# ---- scoring tables (chapter 1 baseline) ----
_LOW_HP_TIERS = [(1, 7500), (5, 5000), (14, 3000), (25, 1000)]
_SPEED_TABLE = {1: 1500, 2: 1000, 3: 800, 4: 600, 5: 400, 6: 300}
_DAMAGE_TIERS = [(20, 100), (40, 200), (70, 300), (100, 500), (200, 700), (300, 1000)]


def _low_hp_bonus(hp: int, max_hp: int, chapter: int) -> int:
    for threshold, pts in _LOW_HP_TIERS:
        if hp <= threshold:
            return pts * chapter
    if hp <= int(max_hp * 0.5):
        return 800 * chapter
    if hp <= int(max_hp * 0.8):
        return 500 * chapter
    return 0


def _speed_bonus(turns: int, chapter: int) -> int:
    return _SPEED_TABLE.get(turns, 200) * chapter


def _cum_damage_bonus(best_turn_damage: int) -> int:
    total = 0
    for threshold, pts in _DAMAGE_TIERS:
        if best_turn_damage >= threshold:
            total += pts
        else:
            break
    return total


def _absorb(incoming: int, block: int):
    absorbed = min(block, incoming)
    return incoming - absorbed, block - absorbed


def _bleed_amp(raw: int, bleed_turns: int) -> int:
    return int(raw * 1.5) if bleed_turns > 0 else raw


def _reset_enemy(enemy: Enemy, rng: random.Random):
    enemy.current_hp = roll_hp(enemy, rng)
    enemy.rolled_max_hp = enemy.current_hp
    enemy.strength = 0
    enemy.armor = 0
    enemy.block = 0
    enemy.poison = 0
    enemy.bleed_turns = 0
    enemy.freeze_turns = 0


def simulate_battle(
    player: PlayerState,
    enemies: list,
    rng: random.Random,
    chapter: int = 1,
    reset: bool = True,
) -> BattleResult:
    # reset runtime state. Callers that pre-reset (e.g. food-effect
    # simulator that needs to inject pre-battle damage on enemies AFTER
    # the reset) can pass reset=False to keep their modifications.
    if reset:
        for die in player.dice:
            die.reset()
        for enemy in enemies:
            _reset_enemy(enemy, rng)

    def alive():
        return [e for e in enemies if e.current_hp > 0]

    def front():
        for e in enemies:
            if e.current_hp > 0:
                return e
        return None

    damage_taken = 0
    damage_dealt = 0
    points_rolls = 0
    points_flat = 0
    max_turn_dmg = 0
    reason = "turn_limit"
    final_turn = 0

    for turn in range(1, TURN_LIMIT + 1):
        final_turn = turn

        # --------- PLAYER PHASE ---------
        # Brrrito Blockerito: block accumulates instead of resetting for
        # the first N turns. Otherwise the sim clears block every turn.
        if player.block_stack_turns_remaining > 0:
            player.block_stack_turns_remaining -= 1
        else:
            player.block = 0
        turn_dmg_dealt = 0

        # Recompute passive accumulators from non-exhausted passive sides.
        # These run for every die face with the passive effect.
        turn_passive_block_on_attack = 0
        turn_passive_heal = 0
        turn_passive_str = 0
        turn_passive_block = 0
        for d in player.dice:
            for i, s in enumerate(d.sides):
                if i in d.exhausted:
                    continue
                turn_passive_block_on_attack += s.attack_give_defend
                turn_passive_heal += s.passive_heal_per_turn
                turn_passive_str += s.passive_str_per_turn
                turn_passive_block += s.passive_block_per_turn
        player.passive_block_on_attack = turn_passive_block_on_attack

        # Turn-level strength debuff tracker — any enemy we debuff "this
        # turn" has its strength reduced at apply time and restored at the
        # end of the enemy phase.
        turn_str_debuffs = []  # list[(enemy, amount)]

        for die in player.dice:
            side, idx, already_exhausted = die.roll(rng)
            points_rolls += side.score_base
            if already_exhausted:
                continue

            # ---- outgoing attack ----
            base_damage = side.damage
            # multiply_largest_attack: e.g. 2× — applied when this side is
            # the largest attack on its own die. Approximation: doubles the
            # current side's damage if it is the max on this die.
            if side.multiply_largest_attack > 0:
                max_die_dmg = max((s.damage for s in die.sides), default=0)
                if base_damage == max_die_dmg and base_damage > 0:
                    base_damage = int(base_damage * side.multiply_largest_attack)
            if base_damage > 0:
                attack_value = base_damage + player.strength
                if player.freeze_turns > 0:
                    attack_value = int(attack_value * 0.75)
                attack_value = int(attack_value * player.damage_mult)
                targets = alive() if side.target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is None or target.current_hp <= 0:
                        continue
                    for _ in range(side.hits):
                        dmg = _bleed_amp(attack_value, target.bleed_turns)
                        dmg, target.block = _absorb(dmg, target.block)
                        target.current_hp -= dmg
                        damage_dealt += dmg
                        turn_dmg_dealt += dmg
                        if target.current_hp <= 0:
                            # Toxipop: transfer this enemy's poison to
                            # the next alive enemy.
                            if player.toxipop_active and target.poison > 0:
                                for other in enemies:
                                    if other is target: continue
                                    if other.current_hp > 0:
                                        other.poison += target.poison
                                        break
                                target.poison = 0
                            break
                # passive: N block per attack rolled
                if player.passive_block_on_attack > 0:
                    player.block += player.passive_block_on_attack

            # ---- self block ----
            block_value = side.block
            # Conditional: "Block 24 if you have no block" — fires only when
            # player.block is still 0 (i.e. no earlier die rolled block).
            if side.block_if_no_block > 0 and player.block == 0:
                block_value += side.block_if_no_block
            # Scale by enemy count
            if side.block_per_baddie > 0:
                block_value += side.block_per_baddie * len(alive())
            # Scale by self-debuffs
            if side.block_per_debuff_on_self > 0:
                debuff_count = (
                    (1 if player.freeze_turns > 0 else 0)
                    + (1 if player.bleed_turns > 0 else 0)
                    + (1 if player.poison > 0 else 0)
                )
                if debuff_count > 0:
                    block_value += side.block_per_debuff_on_self * debuff_count
                elif side.block > 0:
                    pass  # fallback block already counted above
            if block_value > 0:
                blk = block_value + player.armor
                if player.freeze_turns > 0:
                    blk = int(blk * 0.75)
                player.block += blk

            # ---- self heal ----
            if side.heal > 0:
                player.hp = min(player.max_hp, player.hp + side.heal)

            # ---- enemy debuffs (status) ----
            if side.poison_stacks > 0:
                targets = alive() if side.poison_target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is None:
                        continue
                    for _ in range(side.poison_hits):
                        target.poison += side.poison_stacks
            if side.bleed_duration > 0:
                targets = alive() if side.bleed_target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is not None:
                        target.bleed_turns = max(target.bleed_turns, side.bleed_duration)
            if side.freeze_duration > 0:
                targets = alive() if side.freeze_target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is not None:
                        target.freeze_turns = max(target.freeze_turns, side.freeze_duration)

            # ---- enemy strength debuff (this-turn or permanent) ----
            if side.strength_enemy > 0:
                targets = alive() if side.strength_enemy_target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is None:
                        continue
                    reduction = side.strength_enemy
                    # Don't push below -current-strength; record original.
                    applied = min(reduction, max(0, target.strength) + 100)
                    target.strength -= reduction
                    if side.strength_enemy_this_turn:
                        turn_str_debuffs.append((target, reduction))

            # ---- enemy armor debuff (permanent) ----
            if side.armor_enemy > 0:
                targets = alive() if side.armor_enemy_target == "all" else ([front()] if front() else [])
                for target in targets:
                    if target is not None:
                        target.armor = max(0, target.armor - side.armor_enemy)

            # ---- self buffs ----
            if side.strength_self > 0:
                player.strength += side.strength_self
            if side.armor_self > 0:
                player.armor += side.armor_self

            if side.score_flat_bonus > 0:
                points_flat += side.score_flat_bonus

            if side.exhaust:
                die.exhausted.add(idx)

            if not alive():
                break

        # End-of-player-phase passives that heal / add strength / add block.
        if turn_passive_heal > 0:
            player.hp = min(player.max_hp, player.hp + turn_passive_heal)
        if turn_passive_str > 0:
            player.strength += turn_passive_str
        if turn_passive_block > 0:
            player.block += turn_passive_block
        # Pickle: "Gain 6 Block if you have 9 or less Block at end of turn".
        if (player.pickle_block_refill > 0
                and player.block <= player.pickle_block_threshold):
            player.block += player.pickle_block_refill

        if turn_dmg_dealt > max_turn_dmg:
            max_turn_dmg = turn_dmg_dealt

        if not alive():
            reason = "enemy_dead"
            break

        # end of player phase: tick enemy debuffs
        for e in list(enemies):
            if e.current_hp <= 0:
                continue
            if e.poison > 0:
                e.current_hp -= e.poison
                damage_dealt += e.poison
            if e.bleed_turns > 0:
                e.bleed_turns -= 1
            if e.freeze_turns > 0:
                e.freeze_turns -= 1

        if not alive():
            reason = "enemy_dead"
            break

        # --------- ENEMY PHASE ---------
        for e in list(enemies):
            if e.current_hp <= 0:
                continue
            action = action_on_turn(e, turn, rng)

            if action.self_block > 0:
                e.block += action.self_block + e.armor
            if action.self_strength > 0:
                e.strength += action.self_strength
            if action.self_armor > 0:
                e.armor += action.self_armor
            if action.rehealth > 0:
                e.current_hp = min(e.rolled_max_hp, e.current_hp + action.rehealth)

            atk = action.damage
            if action.attack_equal_block:
                atk = e.block
            if atk > 0:
                raw = atk + e.strength
                if e.freeze_turns > 0:
                    raw = int(raw * 0.75)
                for _ in range(action.hits):
                    dmg = _bleed_amp(raw, player.bleed_turns)
                    dmg, player.block = _absorb(dmg, player.block)
                    # Clutch Creme: if incoming damage (post-block) is
                    # ≤ threshold AND > 0, reduce to 1. Does nothing for
                    # fully-blocked hits (dmg already 0).
                    if (player.clutch_creme_threshold > 0
                            and 0 < dmg <= player.clutch_creme_threshold):
                        dmg = 1
                    player.hp -= dmg
                    damage_taken += dmg
                    if player.hp <= 0:
                        break

            if action.applies_poison > 0:
                if player.negate_debuffs > 0:
                    player.negate_debuffs -= 1
                else:
                    player.poison += action.applies_poison
            if action.applies_bleed_duration > 0:
                if player.negate_debuffs > 0:
                    player.negate_debuffs -= 1
                else:
                    player.bleed_turns = max(player.bleed_turns, action.applies_bleed_duration)
            if action.applies_freeze_duration > 0:
                if player.negate_debuffs > 0:
                    player.negate_debuffs -= 1
                else:
                    player.freeze_turns = max(player.freeze_turns, action.applies_freeze_duration)
            if action.apply_curse_count > 0:
                player.curses_received += action.apply_curse_count
            if action.exhaust_random_side:
                pool = [(d, i) for d in player.dice for i in range(len(d.sides)) if i not in d.exhausted]
                if pool:
                    d, i = rng.choice(pool)
                    d.exhausted.add(i)

            if player.hp <= 0:
                break

        if player.hp <= 0:
            reason = "player_dead"
            break

        # Restore any "this turn only" enemy strength debuffs.
        for target, amount in turn_str_debuffs:
            target.strength += amount
        turn_str_debuffs = []

        # end of enemy phase: tick player debuffs
        if player.poison > 0:
            player.hp -= player.poison
            damage_taken += player.poison
            if player.hp <= 0:
                reason = "player_dead"
                break
        if player.bleed_turns > 0:
            player.bleed_turns -= 1
        if player.freeze_turns > 0:
            player.freeze_turns -= 1

    # ---- scoring ----
    if reason == "enemy_dead":
        kill_pts = sum(e.points for e in enemies) * chapter
        low_hp = _low_hp_bonus(max(1, player.hp), player.max_hp, chapter)
        speed = _speed_bonus(final_turn, chapter)
    else:
        kill_pts = 0
        low_hp = 0
        speed = 0

    dmg_bonus = _cum_damage_bonus(max_turn_dmg)
    total_pts = int(
        (points_rolls + kill_pts + low_hp + speed + dmg_bonus + points_flat)
        * player.points_mult
    )

    return BattleResult(
        won=(reason == "enemy_dead"),
        reason=reason,
        turns=final_turn,
        player_hp_end=max(0, player.hp),
        player_max_hp=player.max_hp,
        enemies_label=" + ".join(e.name for e in enemies),
        enemies_hp_end=[max(0, e.current_hp) for e in enemies],
        damage_taken=damage_taken,
        damage_dealt=damage_dealt,
        max_single_turn_damage=max_turn_dmg,
        points_from_rolls=points_rolls,
        points_from_kill=kill_pts,
        points_from_damage_bonus=dmg_bonus,
        points_from_low_hp=low_hp,
        points_from_speed=speed,
        points_from_flat_bonuses=points_flat,
        total_points=total_pts,
        curses_received=player.curses_received,
    )
