"""Autonomous full-run player.

Starts a practice session and iterates through the map, resolving every
encounter with a simple "safe bot" policy. Logs every API request/response
to disk so we can later analyze battles, upgrade offers, and state transitions.

Policy:
  - Baddie / Big Baddie / Boss: setup -> prefight -> start -> resolve-turn loop
    -> to-loot -> fetch-loot -> try to claim (or skip) -> back to map
  - Map: roll -> proceed (no rewinds)
  - Mystery: exit (skip)
  - Campfire: rest (heal)
  - Bub's: exit (no purchases)
  - Loot Die: claim
  - Obelisk: exit (no sacrifice)
  - Checkpoint: unstake (end the run)
  - Everything else: try to proceed, or bail

Safety:
  - Refuses to start if another active session exists
  - Bails after SAME_STATE_LIMIT iterations stuck in the same state
  - Hard cap on total iterations and battle turn count
  - Always forfeits on exit (even on exception)

Usage:
    python scripts/play_full_run.py             # one run
    python scripts/play_full_run.py 3           # three runs in a row
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx

from dd_agent.dd_client import DDClient
from dd_agent.sim.upgrade_picker import (
    DIE_ROLES,
    choose_die_for_upgrade,
    has_curse,
    pick_best_side,
    pick_burn_target,
    pick_burn_target_preboss,
    score_side_for_die,
)


MAX_ITERATIONS = 300
BATTLE_TURN_LIMIT = 40
SAME_STATE_LIMIT = 3
CALL_DELAY = 1.0   # seconds between API calls (Cloudflare 429 kicks in ~500ms bursts)
_last_call_time = [0.0]


class RunLogger:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.step = 0
        self.summary = {"battles": [], "iterations": 0, "end_reason": None}

    def save(self, label: str, data):
        self.step += 1
        path = self.out_dir / f"{self.step:04d}_{label}.json"
        path.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        return path

    def log(self, msg: str):
        print(f"[{self.step:04d}] {msg}")

    def write_summary(self):
        path = self.out_dir / "_summary.json"
        path.write_text(
            json.dumps(self.summary, indent=2, default=str),
            encoding="utf-8",
        )


async def try_call(logger, label, coro, max_retries: int = 3):
    """Execute an async DD API coroutine with throttling + 429 backoff.

    429s are Cloudflare rate limits; they cascade into stuck sessions if
    we don't recover (forfeit fails → next run can't start). Retry with
    exponential backoff up to max_retries times.

    Note: because a coroutine can only be awaited ONCE, we can't re-run
    the same `coro` across retries. Instead this function accepts a
    plain coroutine for its signature but we only retry the FIRST call.
    For 429 retries we sleep and trust the caller's next call to pick up.
    Best-effort: sleep once on a 429 before returning None, which at
    least slows the cascade.
    """
    # Throttle: enforce minimum gap between calls
    import time
    now = time.monotonic()
    gap = now - _last_call_time[0]
    if gap < CALL_DELAY:
        await asyncio.sleep(CALL_DELAY - gap)
    _last_call_time[0] = time.monotonic()

    try:
        r = await coro
        logger.save(label, r)
        return r
    except httpx.HTTPStatusError as e:
        body = None
        try:
            body = e.response.text
        except Exception:
            pass
        msg = f"HTTP {e.response.status_code}: {body or ''}"
        logger.log(f"ERROR {label}: {msg[:400]}")
        logger.save(f"{label}_ERROR", {"status": e.response.status_code, "body": body})
        # Cloudflare 429: back off hard so subsequent calls can succeed.
        if e.response.status_code == 429:
            backoff = 15.0
            logger.log(f"  [429 backoff {backoff}s]")
            await asyncio.sleep(backoff)
            # Also push _last_call_time forward so the next call waits too.
            _last_call_time[0] = time.monotonic()
        return None
    except Exception as e:
        logger.log(f"ERROR {label}: {type(e).__name__}: {e}")
        logger.save(f"{label}_ERROR", {"error": f"{type(e).__name__}: {e}"})
        return None


def _get_state(resp):
    if not isinstance(resp, dict):
        return {}
    return resp.get("state") if isinstance(resp.get("state"), dict) else resp


def _extract_outcome(resp):
    """Try to pull a clear outcome hint from resolve-turn or similar responses."""
    if not isinstance(resp, dict):
        return None
    # direct field
    o = resp.get("outcome")
    if o:
        return o
    # nested in state
    state = resp.get("state")
    if isinstance(state, dict):
        o = state.get("outcome")
        if o:
            return o
    return None


def _extract_player_hp(resp):
    if not isinstance(resp, dict):
        return None
    for path in (
        ("state", "player", "health"),
        ("state", "player", "hp"),
        ("player", "health"),
        ("player", "hp"),
    ):
        cur = resp
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, (int, float)):
            return cur
    return None


def _extract_monsters(resp):
    if not isinstance(resp, dict):
        return []
    state = resp.get("state")
    src = state.get("monsters") if isinstance(state, dict) else resp.get("monsters")
    if isinstance(src, list):
        return [m for m in src if isinstance(m, dict)]
    return []


def _die_order_signals(die: dict) -> dict:
    """Extract the signals we need to decide where a die should sit.

    Resolve order matters because:
    - "Increase all values on all other Dice" only boosts dice that resolve
      AFTER the buff fires → buff die must be first.
    - Damage multipliers amplify later dice → multiplier die must precede
      the heavy attackers.
    - Debuff appliers (freeze / bleed / poison) must resolve BEFORE the
      dice that carry consumer sides ("Attack +X if Frozen", etc.).
    - "Copy the effect of the next Die" needs a next die → must not be last.
    """
    labels = []
    for ab in (die.get("ability") or []):
        if isinstance(ab, dict):
            labels.append((ab.get("label") or "").lower())

    def has(pred):
        return any(pred(l) for l in labels)

    def label_applies_debuff(l, kw):
        # "Attack 10. If monster is Freezing, Attack +20" is a consumer, not applier
        if "if" in l and kw in l:
            # Distinguish "Freeze 3" side from "if Freezing" side
            if "attack +" in l or "+attack" in l or "bonus" in l:
                return False
        return kw in l and "cure" not in l

    return {
        "global_buff": has(lambda l: (
            ("all other dice" in l or "all dice" in l or "other dice" in l)
            and ("increase" in l or "gain" in l or "+" in l)
        )),
        "damage_mult": has(lambda l: (
            "increase damage" in l or "2x damage" in l
            or "double damage" in l or "increase all damage" in l
        )),
        "freeze_applier": has(lambda l: label_applies_debuff(l, "freez")),
        "freeze_consumer": has(lambda l: "if" in l and "freez" in l),
        "bleed_applier": has(lambda l: label_applies_debuff(l, "bleed")),
        "bleed_consumer": has(lambda l: "if" in l and "bleed" in l),
        "poison_applier": has(lambda l: label_applies_debuff(l, "poison")),
        "poison_consumer": has(lambda l: "if" in l and "poison" in l),
        "copy_next": has(lambda l: "copy" in l and "next" in l and "die" in l),
        "block_if_no_block": has(lambda l: "if you have no block" in l),
    }


def _compute_optimal_order(dices: list) -> list:
    """Return the preferred permutation of dice as a list of die dicts.

    Scores each die with a "preferred position" value (lower = earlier),
    sorts, and then applies a final fixup so that copy-next-die is never
    last.
    """
    if not dices:
        return []
    ordered = sorted(dices, key=lambda d: d.get("order", 0) if isinstance(d, dict) else 0)
    n = len(ordered)
    sigs = [_die_order_signals(d) for d in ordered]

    any_freeze_consumer = any(s["freeze_consumer"] for s in sigs)
    any_bleed_consumer = any(s["bleed_consumer"] for s in sigs)
    any_poison_consumer = any(s["poison_consumer"] for s in sigs)

    # Are there any other dice with damage output? If so, bleed appliers
    # benefit from going first so subsequent attacks hit a bleeding target
    # for +50% damage (user rule 2026-04-14).
    def _has_damage_sides(die):
        for ab in (die.get("ability") or []):
            if not isinstance(ab, dict): continue
            dmg = ab.get("damage") or {}
            if isinstance(dmg, dict) and (dmg.get("value", 0) or 0) > 0:
                return True
        return False
    any_damage_on_other_die = lambda self_idx: any(
        _has_damage_sides(ordered[j]) for j in range(n) if j != self_idx
    )

    def rank(i):
        s = sigs[i]
        # Position score: smaller = earlier in the chain.
        # Global buff sources must fire first so later dice see the buff.
        if s["global_buff"]:
            r = 0
        # Damage multipliers precede heavy attackers.
        elif s["damage_mult"]:
            r = 10
        # Bleed applier when other dice have attacks — subsequent attacks
        # amplify on bleeding targets. This kicks in even without an
        # explicit "attack-if-bleeding" consumer.
        elif s["bleed_applier"] and any_damage_on_other_die(i):
            r = 15
        # Debuff appliers precede their consumers (only if a consumer exists).
        elif s["freeze_applier"] and any_freeze_consumer and not s["freeze_consumer"]:
            r = 20
        elif s["bleed_applier"] and any_bleed_consumer and not s["bleed_consumer"]:
            r = 22
        elif s["poison_applier"] and any_poison_consumer and not s["poison_consumer"]:
            r = 24
        # "Block N if you have no block" must be slot 1 — it's useless
        # after any other die has already rolled block.
        elif s["block_if_no_block"]:
            r = 5
        else:
            r = 50  # neutral

        # Consumers must land after appliers — push them just past applier
        # rank (but NOT to the tail: a pure attacker with no debuff interaction
        # can still come after them safely).
        if s["freeze_consumer"] or s["bleed_consumer"] or s["poison_consumer"]:
            r = max(r, 30)
        return r

    perm = sorted(range(n), key=rank)

    # Final fixup: copy-next-die must have a "next die", so if it lands
    # last, swap with the die just before it.
    if n >= 2 and sigs[perm[-1]]["copy_next"]:
        perm[-1], perm[-2] = perm[-2], perm[-1]

    return [ordered[i] for i in perm]


def _needs_reorder(dices: list) -> tuple:
    """Return (needs_reorder, new_order_payload) based on strategic signals.

    new_order_payload is the list of `{id, order}` dicts we send to
    `/api/game/reorder-dice`. Returns (False, None) when the current order
    already matches the desired one.
    """
    if not dices:
        return (False, None)
    ordered = sorted(dices, key=lambda d: d.get("order", 0) if isinstance(d, dict) else 0)
    optimal = _compute_optimal_order(dices)
    if not optimal:
        return (False, None)

    current_ids = [d.get("id") for d in ordered]
    optimal_ids = [d.get("id") for d in optimal]
    if current_ids == optimal_ids:
        return (False, None)

    new_order = [
        {"id": d.get("id"), "order": i + 1}
        for i, d in enumerate(optimal)
    ]
    return (True, new_order)


# Map live-API enemy names to sim enemy factories. Names come from the
# `name` field on the monster payload. Use conservative fallback matching.
_LIVE_TO_SIM_ENEMY = {
    "Ice Pufflet": "ice_pufflet",
    "Black Firant": "black_firant",
    "Blue Firant": "blue_firant",
    "Baby Scarebug": "baby_scarebug",
    "Frostmaul": "frostmaul",
    "Cobra Frier": "cobra_frier",
    "Kevin": "kevin",
    "Lil Zomboid": "lil_zomboid",
    "Rock Lobster": "rock_lobster",
    "Wendibrrr": "wendibrrr",
    "Firant Queen": "firant_queen",
    "Gorgon-zola": "gorgon_zola",
    "Ganondwarf": "ganondwarf",
}


async def _should_battle_rewind(
    dices, monsters, hp_before, max_hp, actual_hp_end, logger, battle_num
) -> tuple:
    """Decide whether to spend TC on a battle rewind.

    Returns (should_rewind: bool, sim_better_rate: float, median_sim_hp: int).

    Rewind rule (user spec 2026-04-14):
    - HP loss from this fight was >= 20
    - Sim N trials of the same fight with current dice
    - If >60% of sim trials end with a BETTER hp_end than the actual, rewind
    """
    hp_loss = hp_before - (actual_hp_end or 0)
    if hp_loss < 20:
        return (False, 0.0, actual_hp_end or 0)
    if not dices or not monsters:
        return (False, 0.0, actual_hp_end or 0)

    try:
        import random as _rnd
        from dd_agent.sim.battle import PlayerState, simulate_battle
        from dd_agent.sim.enemies import ENEMIES
        from scripts.analyze_run import live_dice_to_sim_dice
    except Exception as e:
        logger.log(f"    rewind sim import failed: {e}")
        return (False, 0.0, actual_hp_end or 0)

    # Build enemy factories from the monster list via name mapping.
    factories = []
    for m in monsters:
        name = (m.get("name") or "").strip()
        key = _LIVE_TO_SIM_ENEMY.get(name)
        if key and key in ENEMIES:
            factories.append(ENEMIES[key])
    if not factories:
        return (False, 0.0, actual_hp_end or 0)

    trials = 80
    better = 0
    hp_ends = []
    for i in range(trials):
        try:
            sim_dice = live_dice_to_sim_dice(dices)
            player = PlayerState(hp=hp_before, max_hp=max_hp, dice=sim_dice)
            enemies = [f() for f in factories]
            rng = _rnd.Random(1000 + i)
            r = simulate_battle(player, enemies, rng)
        except Exception:
            continue
        if not r.won:
            # Losing sim trials count as "not better" — can't rewind into a loss
            hp_ends.append(0)
            continue
        hp_ends.append(r.player_hp_end)
        if r.player_hp_end > (actual_hp_end or 0):
            better += 1
    if not hp_ends:
        return (False, 0.0, actual_hp_end or 0)
    hp_ends.sort()
    median = hp_ends[len(hp_ends) // 2]
    rate = better / len(hp_ends)
    return (rate > 0.60, rate, median)


# Obelisks are 2 sequential fights with HP carryover. Fight 1 monsters
# come from the setup-scene response; fight 2 monsters aren't revealed
# until fight 1 wins. Use the hardest observed composition per chapter
# as a pessimistic stress test for fight 2.
#
# Observed Ch1 obelisk fight 2 (from v21 run #5): Black Firant ×3 + Firant
# Queen — essentially the mini-boss pack. That's the hardest we've seen.
# Observed Ch2 obelisk compositions: Snowfang Pack ×3, Noxious + Haunt +
# Scarebug, Lavamander ×2 + Firants. We pick the hardest as the stress.
def _obelisk_fight2_stress(chapter):
    from dd_agent.sim.enemies import (
        black_firant, blue_firant, firant_queen_solo,
    )
    if chapter == 2:
        # Best Ch2 approximation — Snowfang Pack ×3 is the common hard
        # case. We don't have a real Snowfang sim enemy yet so fall back
        # to a Firant Queen pack which is a reasonable damage proxy.
        return [black_firant(), black_firant(), firant_queen_solo(), blue_firant()]
    return [black_firant(), black_firant(), firant_queen_solo(), blue_firant()]


async def _simulate_obelisk(dd, session_id, monsters, logger, battle_num,
                             chapter=1) -> float:
    """Joint-winrate sim of BOTH obelisk fights with HP carryover.

    Fight 1 monsters are known (the `monsters` arg). Fight 2 monsters
    are unknown until fight 1 wins, so we sim against a chapter-
    appropriate stress composition.

    Returns joint win probability ∈ [0, 1] — the share of trials where
    the dice cleared BOTH fights back-to-back. The caller's threshold
    (currently 0.5) applies to the joint rate, matching the real
    obelisk risk.

    On any failure (unknown enemy, import error, etc.) we return 1.0
    so the bot defaults to "proceed" rather than skipping everything.
    """
    try:
        import copy as _copy
        import random as _rnd
        from dd_agent.sim.battle import PlayerState, simulate_battle
        from dd_agent.sim.enemies import ENEMIES
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
        from scripts.analyze_run import live_dice_to_sim_dice  # type: ignore
    except Exception as e:
        logger.log(f"  sim import failed: {type(e).__name__}: {e}; defaulting to proceed")
        return 1.0

    char = await try_call(
        logger, f"b{battle_num:02d}_obelisk_char",
        dd.get_character(session_id),
    )
    if not isinstance(char, dict):
        return 1.0
    dices = char.get("dices") or []
    player_hp = int(char.get("health") or 60)
    player_max = int(char.get("max_health") or 60)

    factories = []
    for m in monsters:
        name = (m.get("name") or "").strip()
        key = _LIVE_TO_SIM_ENEMY.get(name)
        if key and key in ENEMIES:
            factories.append(ENEMIES[key])
    if not factories:
        logger.log("  obelisk sim: no enemies recognized, defaulting to proceed")
        return 1.0

    f1_wins = 0
    joint_wins = 0
    trials = 150
    f1_hp_ends = []
    for i in range(trials):
        sim_dice = live_dice_to_sim_dice(dices)
        player = PlayerState(hp=player_hp, max_hp=player_max, dice=sim_dice)
        enemies = [f() for f in factories]
        rng = _rnd.Random(i)
        try:
            r1 = simulate_battle(player, enemies, rng)
        except Exception:
            return 1.0
        if not r1.won:
            continue
        f1_wins += 1
        f1_hp_ends.append(r1.player_hp_end)

        # Carry dice + HP into fight 2 (stress composition)
        try:
            f2_enemies = _obelisk_fight2_stress(chapter)
            sim_dice2 = live_dice_to_sim_dice(dices)
            player2 = PlayerState(
                hp=r1.player_hp_end, max_hp=player_max, dice=sim_dice2,
            )
            r2 = simulate_battle(player2, f2_enemies, rng)
        except Exception:
            continue
        if r2.won:
            joint_wins += 1

    f1_rate = f1_wins / trials
    joint_rate = joint_wins / trials
    mean_f1_hp = (sum(f1_hp_ends) / len(f1_hp_ends)) if f1_hp_ends else 0
    logger.log(
        f"  obelisk sim: fight1={f1_rate:.2f} joint={joint_rate:.2f} "
        f"mean_hp_end_f1={mean_f1_hp:.0f}/{player_max}"
    )
    return joint_rate


# Biome preference (tiebreaker only — tile contents dominate).
BIOME_SCORE = {
    "Volcano": 5,
    "Ice Cave": 3,
    "Ice": 3,
    "Desert": 0,
    "Toxic Swamp": -10,
    "Swamp": -10,
}

# Map-movement die distribution. The physical die has faces [1, 2, 2, 3, 3, 4]
# so +2 and +3 rolls are twice as likely as +1 or +4. Reroll EV calcs must
# use these probabilities.
MOVE_DIE_SIDES = [1, 2, 2, 3, 3, 4]
MOVE_DIE_PROBS = {1: 1/6, 2: 2/6, 3: 2/6, 4: 1/6}


def _bub_score_from_gold(current_gold: int) -> float:
    """Scale bub tile value by the player's current gold. With <50g the
    bot can barely buy a single side; with 300+g the shop can deliver a
    rare trinket + food + TCs, which is run-defining. Per
    `feedback_bub_value_scales_with_gold`.
    """
    if current_gold < 50:
        return 15.0
    if current_gold < 150:
        return 25.0
    if current_gold < 300:
        return 35.0
    return 48.0  # rare-trinket-tier — approaches campfire value


def _score_single_tile(node: dict, dice_readiness: float, biome_sim_results: dict,
                        current_gold: int = 0, chapter: int = 1) -> float:
    """Score a single map tile using the same rules as _score_path_nodes but
    for one node at a time (no distance weighting — caller handles that).
    """
    if not isinstance(node, dict):
        return 0.0
    ttype = (node.get("type") or "").lower()
    b = node.get("biome")
    idx = node.get("index", 0) or 0
    biome_sim_results = biome_sim_results or {}

    if ttype in ("big-baddie", "boss-baddie"):
        sim_result = biome_sim_results.get(b, (0.0, 60, 0))
        win_rate, median_loss = sim_result[0], sim_result[1]
        if win_rate >= 0.5 and median_loss < 20:
            base = 12
        elif win_rate >= 0.5:
            base = -5
        else:
            base = -30
        if ttype == "boss-baddie":
            base -= 5
    elif ttype == "mystery" and dice_readiness <= 0.0:
        # Only penalize mysteries when every die is still at 4 sides
        # (pure starter state). Once any die has a non-starter upgrade,
        # burn-mysteries can succeed and mystery routing is fine.
        base = -5
    elif ttype == "bub":
        # Gold-scaled: a 300g+ bub is nearly as valuable as a campfire
        # because it can buy a rare trinket + food + TC, all of which
        # compound across remaining battles.
        base = _bub_score_from_gold(current_gold)
    elif ttype == "baddie" and chapter == 1 and idx <= 14:
        # Early Ch1 battles are the cheapest source of dice upgrades in
        # the entire run — weakest enemies, cheapest HP cost, and every
        # win drops an upgrade. Score them strongly positive so the
        # reroll/fork logic doesn't skip them. Per
        # `feedback_early_battles_are_upgrade_fuel`.
        base = 3  # offsets the default -2 and tips net positive
    else:
        base = TILE_SCORE.get(ttype, 0)

    if b:
        base += BIOME_SCORE.get(b, 0) * 0.3
    return float(base)


def _tile_at(nodes: list, target_idx: int) -> dict:
    """Find the node at `target_idx` on a list of path nodes."""
    for n in nodes:
        if isinstance(n, dict) and (n.get("index", -1) or -1) == target_idx:
            return n
    return {}


def _best_tile_score_across_paths(
    md: dict, active_path: str, base_idx: int, target_idx: int,
    dice_readiness: float, biome_sim_results: dict,
    current_gold: int = 0, chapter: int = 1,
) -> tuple:
    """For a target idx, check the active path + any fork whose branch
    point (atMainIndex) falls in (base_idx, target_idx]. Return the best
    score because the bot will pick the better option at the fork prompt.

    A fork's branch point is one index before its first node (fork1 first
    node idx == atMainIndex + 1).

    Returns (best_score, picked_label).
    """
    active_key = {
        "main": "mainPathNodes",
        "fork1": "fork1Nodes",
        "fork2": "fork2Nodes",
    }.get(active_path, "mainPathNodes")
    active_nodes = md.get(active_key) or []
    active_tile = _tile_at(active_nodes, target_idx)
    active_score = (
        _score_single_tile(
            active_tile, dice_readiness, biome_sim_results, current_gold, chapter,
        )
        if active_tile else -20
    )
    candidates = [(active_score, f"{active_path}:{(active_tile or {}).get('type','?')}")]

    # Only forks branching FROM main matter. If we're already on a fork,
    # a second branch is not a thing.
    if active_path == "main":
        for fork_key in ("fork1Nodes", "fork2Nodes"):
            fork_nodes = md.get(fork_key) or []
            if not fork_nodes or not isinstance(fork_nodes[0], dict):
                continue
            first_fork_idx = int(fork_nodes[0].get("index", 0) or 0)
            branch_point = first_fork_idx - 1  # atMainIndex
            # Fork fires when the roll crosses OUT of branch_point. We
            # haven't left base_idx yet, so the branch point is reachable
            # from [base_idx, target_idx).
            if branch_point < base_idx or branch_point >= target_idx:
                continue
            fork_tile = _tile_at(fork_nodes, target_idx)
            if not fork_tile:
                continue
            fork_score = _score_single_tile(
                fork_tile, dice_readiness, biome_sim_results, current_gold, chapter,
            )
            fork_id = fork_key.replace("Nodes", "")
            candidates.append((fork_score, f"{fork_id}:{fork_tile.get('type','?')}"))

    candidates.sort(reverse=True)
    return candidates[0]


async def _should_reroll_movement(
    dd, character_id, session_id, logger, iteration
) -> bool:
    """Decide whether to spend TC rerolling the current movement.

    Uses EV calc with the [1,2,2,3,3,4] die distribution. For each
    possible target tile, considers the best of (main tile, available
    fork tiles) because the bot will pick the better fork at any fork
    prompt encountered along the way.
    """
    try:
        game = await dd.get_game(character_id)
    except Exception:
        return False
    if not isinstance(game, dict):
        return False

    last = game.get("lastSession") or {}
    md = last.get("mapData") or {}
    progress = last.get("progress") or {}
    current_idx = int(progress.get("currentIndex", 0) or 0)
    rolled_steps = int(progress.get("rolledSteps") or 0)
    active_path = progress.get("activePath") or "main"
    chapter = int(last.get("chapter") or 1)
    # Server-side reroll cost: baseline 2 TC, escalates on repeated
    # rerolls from the same space. Read the authoritative value from
    # game.nextRerollCost (top-level on the /api/game response) instead
    # of assuming 1 TC.
    next_reroll_cost = int(game.get("nextRerollCost") or 2)

    base_idx = current_idx - rolled_steps if rolled_steps > 0 else current_idx

    try:
        char = await dd.get_character(session_id)
    except Exception:
        char = None
    if not isinstance(char, dict):
        return False
    tc = int(char.get("time_crystal") or 0)
    if tc < next_reroll_cost:
        return False
    dices = char.get("dices") or []
    dice_readiness = _avg_non_starter_sides(dices)
    hp = int(char.get("health") or 60)
    max_hp = int(char.get("max_health") or 60)
    current_gold = int(char.get("gold") or 0)

    # Collect biomes of big-baddies in reach across ALL paths, so we sim
    # each biome once and reuse.
    biomes_needed = set()
    for path_key in ("mainPathNodes", "fork1Nodes", "fork2Nodes"):
        for n in (md.get(path_key) or []):
            if not isinstance(n, dict):
                continue
            idx = n.get("index", 0) or 0
            if idx < base_idx or idx > base_idx + 4:
                continue
            if (n.get("type") or "").lower() in ("big-baddie", "boss-baddie"):
                biomes_needed.add(n.get("biome"))
    biome_sims = {}
    for biome in biomes_needed:
        biome_sims[biome] = await _sim_big_baddie_survival(dices, biome, hp, max_hp, trials=40)

    # Score the tile we'd commit to if we proceeded without rerolling.
    active_key = {
        "main": "mainPathNodes", "fork1": "fork1Nodes", "fork2": "fork2Nodes"
    }.get(active_path, "mainPathNodes")
    active_nodes = md.get(active_key) or []
    current_tile = _tile_at(active_nodes, current_idx)
    current_score = _score_single_tile(
        current_tile, dice_readiness, biome_sims, current_gold, chapter,
    )

    # EV(reroll) — each die face weighted by its probability. At each
    # target idx, pick the best score across main + any branching forks.
    ev = 0.0
    reachable = []
    for steps, prob in MOVE_DIE_PROBS.items():
        target_idx = base_idx + steps
        best_score, label = _best_tile_score_across_paths(
            md, active_path, base_idx, target_idx, dice_readiness, biome_sims,
            current_gold=current_gold, chapter=chapter,
        )
        ev += prob * best_score
        reachable.append((steps, prob, label, round(best_score, 1)))

    # User 2026-04-14: TC spends on map rerolls are HIGHER priority than
    # battle rewinds. Lower the cost penalty and be aggressive.
    reroll_cost_penalty = 2.0

    # Don't waste TC when the vast majority of outcomes land on the same
    # tile type. E.g. if 5/6 die faces land on big-baddie, rerolling is
    # an 83% chance of the same result for 2 TC.
    if current_score < 0 and reachable:
        same_type_prob = sum(
            prob for _, prob, _, tile_score in reachable
            if tile_score <= current_score + 5
        )
        if same_type_prob >= 0.75:
            logger.log(
                f"  reroll check: idx={current_idx} rolled={rolled_steps} "
                f"cur_score={current_score:.1f} ev(reroll)={ev:.1f} "
                f"tc={tc}/cost={next_reroll_cost} → reroll=False "
                f"(skip: {same_type_prob:.0%} of outcomes are equally bad)"
            )
            logger.log(f"    reachable: {reachable}")
            return False

    # Low-HP safety reroll: when HP is critical and we landed on a baddie,
    # prefer rerolling toward mystery/campfire/bub tiles at distance 2-3
    # (the 33% probability slots). Mysteries can't kill you and may give
    # free burns/buffs/healing. Only applies when build is already strong
    # (5+ upgrades) so we're not sacrificing upgrade opportunities.
    hp_pct_now = hp / max_hp if max_hp else 1.0
    total_upgrades = sum(
        1 for d in dices for ab in (d.get("ability") or [])
        if isinstance(ab, dict) and "Starter" not in
        [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
    ) if dices else 0
    current_is_baddie = "baddie" in (current_tile.get("type", "") if isinstance(current_tile, dict) else "")

    if (hp_pct_now < 0.40 and current_is_baddie and total_upgrades >= 5
            and tc >= next_reroll_cost):
        safe_tiles_at_2_3 = sum(
            1 for steps, prob, label, score in reachable
            if steps in (2, 3) and any(
                t in label for t in ("mystery", "campfire", "bub", "loot-die")
            )
        )
        if safe_tiles_at_2_3 >= 1:
            logger.log(
                f"  reroll check: idx={current_idx} rolled={rolled_steps} "
                f"cur_score={current_score:.1f} ev(reroll)={ev:.1f} "
                f"tc={tc}/cost={next_reroll_cost} → reroll=True "
                f"(low HP {hp_pct_now:.0%}, {safe_tiles_at_2_3}/2 safe tiles at distance 2-3)"
            )
            logger.log(f"    reachable: {reachable}")
            return True

    rolled_4 = (rolled_steps == 4)
    if rolled_4:
        # Rolling a 4 is blind-walking (UI/scorer only sees 4 tiles ahead).
        # Reroll unless current tile is clearly great (+20).
        should = (ev - reroll_cost_penalty > current_score) and (current_score < 20)
    else:
        # Default: reroll when current tile is meaningfully negative.
        should = (current_score < 3) and (ev - reroll_cost_penalty > current_score)
    logger.log(
        f"  reroll check: idx={current_idx} rolled={rolled_steps} "
        f"cur_score={current_score:.1f} ev(reroll)={ev:.1f} "
        f"tc={tc}/cost={next_reroll_cost} → reroll={should}"
    )
    logger.log(f"    reachable: {reachable}")
    return should


# Stress enemy per biome — the "hardest plausible big-baddie" for that
# biome. We sim the current dice against this enemy to decide whether a
# big-baddie on the path is an opportunity (loot + trinket) or a grave.
_BIOME_STRESS_ENEMY = {
    "Ice Cave":    "wendibrrr",
    "Ice":         "wendibrrr",
    "Volcano":     "gorgon_zola",
    "Toxic Swamp": "gorgon_zola",   # lean on poison baseline
    "Swamp":       "gorgon_zola",
    None:          "wendibrrr",     # unknown biome → stress with hardest
}


async def _sim_big_baddie_survival(dices, biome, player_hp, player_max,
                                     trials=60, enemy_key=None):
    """Return (win_rate, median_hp_loss, mean_hp_end) simming the current
    dice against the stress big-baddie. If `enemy_key` is provided, use
    it directly (authoritative from game-state `upcoming_boss`/
    `upcoming_bb_*`); otherwise fall back to biome-based
    `_BIOME_STRESS_ENEMY`.

    mean_hp_end includes losses (0 HP) so it reflects expected HP after
    the fight across all outcomes, not just wins.

    On any failure returns (0.0, player_max, 0) — caller treats that as
    "too risky".
    """
    if not dices:
        return (0.0, player_max, 0)
    try:
        import random as _rnd
        from dd_agent.sim.battle import PlayerState, simulate_battle
        from dd_agent.sim.enemies import ENEMIES
        import sys as _sys
        from pathlib import Path as _P
        _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))
        from scripts.analyze_run import live_dice_to_sim_dice  # type: ignore
    except Exception:
        return (0.0, player_max, 0)

    if enemy_key is None:
        enemy_key = _BIOME_STRESS_ENEMY.get(biome, "wendibrrr")
    if enemy_key not in ENEMIES:
        return (0.0, player_max, 0)

    wins = 0
    hp_losses = []
    all_hp_ends = []
    for i in range(trials):
        try:
            sim_dice = live_dice_to_sim_dice(dices)
            player = PlayerState(hp=player_hp, max_hp=player_max, dice=sim_dice)
            enemy = ENEMIES[enemy_key]()
            rng = _rnd.Random(i)
            result = simulate_battle(player, [enemy], rng)
        except Exception:
            return (0.0, player_max, 0)
        all_hp_ends.append(result.player_hp_end)
        if result.won:
            wins += 1
            hp_losses.append(player_hp - result.player_hp_end)
    win_rate = wins / trials if trials else 0.0
    if hp_losses:
        hp_losses.sort()
        median_loss = hp_losses[len(hp_losses) // 2]
    else:
        median_loss = player_max
    mean_hp_end = sum(all_hp_ends) / len(all_hp_ends) if all_hp_ends else 0
    return (win_rate, median_loss, mean_hp_end)

# Tile-type scores. Positive = want to land on it, negative = avoid.
# These dominate the fork decision because "what's actually on the path"
# matters more than which biome the path is in.
TILE_SCORE = {
    "campfire":  30,   # heals, burns — highest priority for stabilizing
    "bub":       25,   # shop — burn, food, trinkets
    "mystery":   5,    # mixed bag; unupgraded dice should avoid (handled below)
    "baddie":   -2,    # routine fight, mild tempo cost
    "big-baddie": -15, # big baddies are the killers — heavy penalty
    "boss-baddie": -25,
    "obelisk":   0,    # skippable via sim now, neutral
    "rewindable": 0,
    "checkpoint": 2,
}


def _avg_non_starter_sides(dices) -> float:
    if not dices:
        return 0.0
    counts = []
    for d in dices:
        if not isinstance(d, dict):
            continue
        ns = 0
        for ab in (d.get("ability") or []):
            tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
            if "Starter" not in tags:
                ns += 1
        counts.append(ns)
    return sum(counts) / len(counts) if counts else 0.0


def _score_path_nodes(nodes, start_idx, look_ahead, dice_readiness,
                      biome_sim_results=None) -> float:
    """Score the next `look_ahead` tiles on a path starting from start_idx.

    dice_readiness = average non-starter sides per die (0 = pure starter,
    2+ = well-upgraded). Used for mystery-tile avoidance.

    biome_sim_results = {biome: (win_rate, median_hp_loss)} from
    `_sim_big_baddie_survival`. When a tile is a big-baddie, we look up
    the biome's sim result to decide whether the fight is an opportunity
    (dice can clear it → +12 loot bonus) or a grave (→ heavy penalty).
    """
    if not nodes:
        return -999
    biome_sim_results = biome_sim_results or {}
    score = 0.0
    count = 0
    for n in nodes:
        if not isinstance(n, dict):
            continue
        idx = n.get("index", 0) or 0
        if idx < start_idx or idx > start_idx + look_ahead:
            continue
        ttype = (n.get("type") or "").lower()
        b = n.get("biome")

        if ttype in ("big-baddie", "boss-baddie"):
            # Sim-driven scoring: big baddies drop a trinket + food + a
            # powerful side. Worth taking IF the dice can clear them with
            # a median HP loss < 20 and >=50% win rate. Otherwise, heavy
            # penalty.
            win_rate, median_loss = biome_sim_results.get(b, (0.0, 60))
            if win_rate >= 0.5 and median_loss < 20:
                base = 12  # opportunity — loot is worth the HP trade
            elif win_rate >= 0.5:
                base = -5  # we CAN win, but it costs too much HP
            else:
                base = -30  # likely fatal, hard avoid
            if ttype == "boss-baddie":
                # Chapter boss is mandatory at the end — same scoring but
                # slightly stronger negative when unready.
                base -= 5
        elif ttype == "mystery" and dice_readiness <= 0.0:
            # Only penalize mysteries when EVERY die is still at 4
            # sides (pure starter). The server floor of 4 means burn
            # events reject any target. Once any die has an upgrade,
            # mystery routing is fine.
            base = -5
        else:
            base = TILE_SCORE.get(ttype, 0)

        # Biome tiebreaker — small weight compared to tile type.
        if b:
            base += BIOME_SCORE.get(b, 0) * 0.3

        # Distance weight — the NEXT tile (1 step away) matters much more
        # than tiles 6 steps away. A lethal big-baddie 1 step out cannot
        # be offset by a bub 4 steps later. Weight: 1/(distance+1).
        distance = max(0, idx - start_idx)
        weight = 1.0 / (distance + 1)
        score += base * weight
        count += 1
    if count == 0:
        return -50  # empty / unknown path, deprioritize but still consider
    return score


# Enemy immunity / counter table — downweights fork paths where the
# next big-baddie or boss neutralises the dice's primary damage vector.
# Keys are lowercase enemy names OR sim enemy keys; values are
# (damage_vector, multiplier) tuples. See feedback_pick_ability_enemy_immunity.
_ENEMY_IMMUNITY_PENALTIES = {
    # Ch1
    "wendibrrr":     [("freeze", 0.2)],             # Can't be Frozen
    # Ch2
    "pterrordactyl": [("debuff", 0.2), ("freeze", 0.4), ("bleed", 0.4), ("poison", 0.4)],  # 3 Negate Debuffs
    "gorgon-zola":   [("bleed", 0.3), ("freeze", 0.3)],  # transfers bleed/freeze back
    "gorgon_zola":   [("bleed", 0.3), ("freeze", 0.3)],  # sim-key alias
    "detonox":       [("chip", 0.2)],               # +3 Str on HP loss — chip damage feeds it
    # Big Cheeze modes
    "big cheeze shield mode":    [("block_stack", 0.3)],
    "big cheeze poison mode":    [("freeze", 0.3)],
    "big cheeze attack mode":    [("poison", 0.3)],
}


def _dice_primary_vector(dices) -> str:
    """Classify the dice loadout's dominant damage vector.

    Returns one of: "freeze", "bleed", "poison", "debuff", "chip",
    "block_stack", or "none". Uses a minimum-count threshold so a single
    stray side doesn't get tagged as a "build".
    """
    freeze_count = 0
    bleed_count = 0
    poison_count = 0
    debuff_count = 0
    chip_count = 0
    block_stack_count = 0
    if not isinstance(dices, list):
        return "none"
    for d in dices:
        if not isinstance(d, dict):
            continue
        for s in (d.get("ability") or []):
            if not isinstance(s, dict):
                continue
            if s.get("exhausted"):
                continue
            label = (s.get("label") or "").lower()
            freeze_dur = int((s.get("freeze") or {}).get("duration", 0) or 0)
            bleed_dur = int((s.get("bleed") or {}).get("duration", 0) or 0)
            poison_val = int((s.get("poison") or {}).get("value", 0) or 0)
            dmg = int((s.get("damage") or {}).get("value", 0) or 0)
            block_val = int((s.get("block") or {}).get("value", 0) or 0)
            strength = s.get("strength") or {}
            strength_target = strength.get("target")
            is_freeze = freeze_dur > 0 or "freeze" in label
            is_bleed = bleed_dur > 0 or "bleed" in label
            is_poison = poison_val > 0 or "poison" in label
            if is_freeze:
                freeze_count += 1
            if is_bleed:
                bleed_count += 1
            if is_poison:
                poison_count += 1
            if is_freeze or is_bleed or is_poison:
                debuff_count += 1
            elif strength_target and strength_target != "self":
                debuff_count += 1
            if dmg > 0 and dmg < 6:
                chip_count += 1
            if block_val > 0 and dmg == 0:
                block_stack_count += 1
    counts = {
        "freeze": freeze_count,
        "bleed": bleed_count,
        "poison": poison_count,
        "debuff": debuff_count,
        "chip": chip_count,
        "block_stack": block_stack_count,
    }
    best_vec = max(counts, key=lambda k: counts[k])
    if counts[best_vec] < 3:
        return "none"
    # Prefer the more specific tag over the umbrella "debuff" when they tie.
    if best_vec == "debuff":
        for specific in ("freeze", "bleed", "poison"):
            if counts[specific] == counts["debuff"] and counts[specific] >= 3:
                return specific
    return best_vec


def _immunity_multiplier(enemy_key_or_name: str, vector: str) -> float:
    """Look up the downweight multiplier for (enemy, vector). 1.0 = no penalty."""
    if not enemy_key_or_name or vector == "none":
        return 1.0
    entry = _ENEMY_IMMUNITY_PENALTIES.get(enemy_key_or_name.lower())
    if not entry:
        return 1.0
    for vec, mult in entry:
        if vec == vector:
            return mult
    return 1.0


def _next_bb_on_path(md, path_key: str, current_idx: int, chapter, upcoming_boss,
                     upcoming_bb_code) -> str:
    """Scan `path_key` nodes forward from current_idx and return the name
    (sim key or display name) of the first big-baddie or boss-baddie tile.
    Returns None if no such tile exists on the path ahead.
    """
    nodes = md.get(path_key) or []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        idx = int(n.get("index", 0) or 0)
        if idx <= current_idx:
            continue
        ttype = (n.get("type") or "").lower()
        if ttype == "boss-baddie":
            # Prefer the explicit boss name if we have one.
            name = (upcoming_boss or n.get("name") or "").strip()
            return name or None
        if ttype == "big-baddie":
            ch = chapter or 1
            by_chapter = _BB_CODE_TO_SIM.get(ch, _BB_CODE_TO_SIM[1])
            key = by_chapter.get((upcoming_bb_code or "").strip())
            if key:
                return key
            return (n.get("name") or "").strip() or None
    return None


async def _choose_fork_order(dd, character_id, session_id=None, logger=None) -> list:
    """Return a preferred ordering of path IDs to try at a fork choice prompt.

    Only paths actually reachable from the current junction are considered
    (main is always reachable; fork1/fork2 are reachable iff their branch
    point — first-fork-node idx - 1 — lies in [current_idx, current_idx + 4),
    i.e. within the move-die range).

    Per-path score = EV over the move die distribution [1,2,2,3,3,4] of
    `_score_single_tile` applied to the tile we'd land on on that path.
    """
    fallback_order = ["main", "fork1", "fork2"]
    try:
        game = await dd.get_game(character_id)
    except Exception:
        return fallback_order
    if not isinstance(game, dict):
        return fallback_order

    last = game.get("lastSession") or {}
    md = last.get("mapData") or {}
    progress = last.get("progress") or {}
    current_idx = int(progress.get("currentIndex", 0) or 0)

    # Pull dice + HP state — informs readiness and the big-baddie sims.
    dice_readiness = 0.0
    dices = []
    player_hp = 60
    player_max = 60
    current_gold = 0
    if session_id:
        try:
            char = await dd.get_character(session_id)
            if isinstance(char, dict):
                dices = char.get("dices") or []
                dice_readiness = _avg_non_starter_sides(dices)
                player_hp = int(char.get("health") or 60)
                player_max = int(char.get("max_health") or 60)
                current_gold = int(char.get("gold") or 0)
        except Exception:
            pass

    path_keys = {
        "main": "mainPathNodes",
        "fork1": "fork1Nodes",
        "fork2": "fork2Nodes",
    }

    # Figure out which fork paths are actually reachable from this junction.
    # A fork's branch point is (first fork node idx - 1). It fires when the
    # roll crosses it — reachable if branch_point in [current_idx, current_idx+3]
    # (since the max move die face is 4, so we step through indices up to +4).
    reachable = ["main"]  # main is always the default continuation
    for pid in ("fork1", "fork2"):
        nodes = md.get(path_keys[pid]) or []
        if not nodes or not isinstance(nodes[0], dict):
            continue
        first_fork_idx = int(nodes[0].get("index", 0) or 0)
        branch_point = first_fork_idx - 1
        if current_idx <= branch_point <= current_idx + 3:
            reachable.append(pid)

    # Pre-sim big-baddies across all landing tiles (1..4 steps) on reachable
    # paths so `_score_single_tile` has biome sim data to key off.
    biomes_needing_sim = set()
    for pid in reachable:
        nodes = md.get(path_keys[pid]) or []
        for steps in (1, 2, 3, 4):
            tile = _tile_at(nodes, current_idx + steps)
            if tile and (tile.get("type") or "").lower() in ("big-baddie", "boss-baddie"):
                biomes_needing_sim.add(tile.get("biome"))

    biome_sim_results = {}
    for biome in biomes_needing_sim:
        biome_sim_results[biome] = await _sim_big_baddie_survival(
            dices, biome, player_hp, player_max
        )

    # Pull chapter + upcoming boss/bb codes for the enemy-immunity downweight.
    chapter = last.get("chapter")
    upcoming_boss = game.get("upcoming_boss")
    vector = _dice_primary_vector(dices)

    # EV-weighted landing-tile score per reachable path.
    scored = []
    for pid in reachable:
        nodes = md.get(path_keys[pid]) or []
        if not nodes:
            continue
        ev = 0.0
        for steps, prob in MOVE_DIE_PROBS.items():
            tile = _tile_at(nodes, current_idx + steps)
            tile_score = (
                _score_single_tile(
                    tile, dice_readiness, biome_sim_results, current_gold,
                    chapter if isinstance(chapter, int) else 1,
                )
                if tile else -20.0
            )
            ev += prob * tile_score

        # NEW: immunity-vector downweight — if the next big-baddie/boss on
        # this path counters our primary damage vector, scale the score.
        upcoming_bb_code = game.get(f"upcoming_bb_{pid}")
        next_bb = _next_bb_on_path(
            md, path_keys[pid], current_idx, chapter, upcoming_boss, upcoming_bb_code,
        )
        if next_bb and vector != "none":
            mult = _immunity_multiplier(next_bb, vector)
            if mult < 1.0:
                if logger is not None:
                    logger.log(
                        f"    {pid}: downweight \u00d7{mult} (vs {next_bb}, dice={vector})"
                    )
                # Scale positive EV down; for non-positive EV an additive
                # penalty preserves the "worse is worse" direction (a negative
                # score multiplied by <1 would become LESS negative).
                if ev > 0:
                    ev *= mult
                else:
                    ev -= (1.0 - mult) * 20.0

        scored.append((ev, pid))

    if not scored:
        return fallback_order

    scored.sort(reverse=True)
    order = [pid for _, pid in scored]
    return order


async def maybe_reorder_dice(dd, logger, session_id, character_id, iteration):
    """Check current dice and reorder if needed."""
    char = await try_call(
        logger, f"it{iteration:03d}_char_pre_reorder",
        dd.get_character(session_id),
    )
    if not isinstance(char, dict):
        return
    dices = char.get("dices") or []
    needs, new_order = _needs_reorder(dices)
    if not needs:
        return
    logger.log(f"  reordering dice: {new_order}")
    await try_call(
        logger, f"it{iteration:03d}_reorder",
        dd._post(
            "/api/game/reorder-dice",
            character_id=character_id,
            session_id=session_id,
            new_dice_order=new_order,
        ),
    )


def _resolve_food_target(food_name: str, prefight: dict):
    """Return (targetUuid, targets_list) for a food activation.

    Different foods target different things:
      - Self-buffs (Ice Rice, Brrrito, Heat Meat, ...): targetUuid="player"
      - Boom Beans: enemy uuid — prefer an enemy in HP range (10, 40] so
        the 40 primary kills it and the 10 AoE cleans chaff; otherwise
        highest-HP enemy.
      - Crit Chips: a dice attack side uuid — pick the highest-damage
        non-exhausted attack side.
      - Scorch Sauce: up to 4 side uuids (max 2 per die). Pick the
        lowest-value non-exhausted sides on dice that have a clear
        higher-value winner (feedback_scorch_sauce_rule).
    """
    state = (prefight or {}).get("state") or {}
    monsters = [m for m in (state.get("monsters") or []) if isinstance(m, dict)]
    player = state.get("player") or {}
    dice = player.get("dice") or []

    if food_name == "Boom Beans":
        alive = [m for m in monsters if (m.get("health") or 0) > 0]
        if not alive:
            return None, None
        in_range = [m for m in alive if 10 < (m.get("health") or 0) <= 40]
        if in_range:
            target = max(in_range, key=lambda m: m.get("health") or 0)
        else:
            target = max(alive, key=lambda m: m.get("health") or 0)
        return target.get("uuid"), None

    # Crit Chips and Scorch Sauce both use targetUuid="dice" (literal
    # string) with targets = [{diceId, abilityId}, ...]. Crit Chips
    # takes exactly one entry and requires an Attack side; Scorch Sauce
    # takes up to 4 entries, max 2 per die, and exhausts those sides.
    if food_name == "Crit Chips":
        best = None
        best_val = -1
        for d in dice:
            die_id = d.get("id")
            for s in (d.get("ability") or []):
                if s.get("exhausted"): continue
                if s.get("sideType") != "Attack": continue
                val = ((s.get("damage") or {}).get("value")) or 0
                if val > best_val:
                    best_val = val
                    best = {"diceId": die_id, "abilityId": s.get("uuid")}
        if best is None:
            return None, None
        return "dice", [best]

    if food_name == "Scorch Sauce":
        targets = []
        for d in dice:
            die_id = d.get("id")
            sides = [s for s in (d.get("ability") or []) if not s.get("exhausted")]
            if len(sides) < 3:
                continue
            attacks = [s for s in sides if s.get("sideType") == "Attack"]
            if not attacks:
                continue
            top_val = max(((s.get("damage") or {}).get("value") or 0) for s in attacks)
            if top_val < 10:
                continue
            def _side_score(s):
                if s.get("sideType") != "Attack":
                    return 0
                return (s.get("damage") or {}).get("value") or 0
            fillers = sorted(sides, key=_side_score)
            picked_on_die = 0
            for s in fillers:
                if picked_on_die >= 2: break
                if _side_score(s) >= top_val: break
                targets.append({"diceId": die_id, "abilityId": s.get("uuid")})
                picked_on_die += 1
                if len(targets) >= 4:
                    break
            if len(targets) >= 4:
                break
        if not targets:
            return None, None
        return "dice", targets

    return "player", None


async def _activate_food(dd, logger, character_id, session_id, battle_num,
                          food_entry: dict, prefight: dict, tag: str = ""):
    """Send a single select-boost call with correctly-resolved target.

    Returns True if the call succeeded, False otherwise. Logs the attempt.
    """
    if not isinstance(food_entry, dict):
        return False
    fid = food_entry.get("id") or food_entry.get("uuid")
    fname = food_entry.get("type") or food_entry.get("name") or "?"
    if not fid:
        return False
    target_uuid, targets_list = _resolve_food_target(fname, prefight)
    if target_uuid is None and not targets_list:
        logger.log(f"    skip {fname}: no valid target")
        return False
    if targets_list:
        tgt_label = f"dice[{len(targets_list)}]"
    elif target_uuid:
        tgt_label = str(target_uuid)[:8]
    else:
        tgt_label = "?"
    logger.log(f"    activating {fname} → target={tgt_label}")
    body = dict(
        character_id=character_id,
        session_id=session_id,
        boost_id=fid,
    )
    if target_uuid is not None:
        body["targetUuid"] = target_uuid
    if targets_list:
        body["targets"] = targets_list
    result = await try_call(
        logger, f"b{battle_num:02d}_select_boost{tag}",
        dd._post("/api/game/battle/select-boost", **body),
    )
    return result is not None


async def play_battle(dd, logger, session_id, character_id, battle_num,
                       in_state="baddie", pos=None, chapter=None):
    """Play a single battle end-to-end.

    Special handling:
    - Obelisk: after setup-scene, the session is in 'obelisk-skipable' status.
      Must call /battle/obelisk-action with action='proceed' to enter the fight.
      After winning the first fight, must call /battle/setup-scene AGAIN to
      trigger the second fight (obelisk = 2 battles). Only after the second
      win do we go to /battle/to-loot.
    """
    logger.log(f"=== BATTLE #{battle_num} ({in_state}) ===")
    summary_entry = {"num": battle_num, "monsters": None, "result": None, "turns": 0, "hp_at_end": None}

    setup = await try_call(logger, f"b{battle_num:02d}_setup_scene",
                            dd.battle_setup(session_id))
    if not setup:
        summary_entry["result"] = "setup_error"
        logger.summary["battles"].append(summary_entry)
        return "error"

    # OBELISK: the setup puts the battle in 'obelisk-skipable' status.
    # Run a sim against the posted monsters; if simulated win rate < 50%
    # we skip the obelisk entirely instead of committing.
    is_obelisk = in_state == "obelisk"
    if is_obelisk:
        preview_monsters = _extract_monsters(setup)
        sim_win_rate = await _simulate_obelisk(
            dd, session_id, preview_monsters, logger, battle_num,
            chapter=chapter or 1,
        )
        summary_entry["sim_win_rate"] = sim_win_rate
        logger.log(f"  obelisk sim win rate: {sim_win_rate:.2f}")

        if sim_win_rate < 0.5:
            logger.log(f"  obelisk: skipping (sim {sim_win_rate:.2f} < 0.50)")
            skip_resp = await try_call(
                logger, f"b{battle_num:02d}_obelisk_exit",
                dd._post("/api/game/battle/obelisk-action",
                          sessionId=session_id, action="exit"),
            )
            summary_entry["result"] = "skipped"
            summary_entry["turns"] = 0
            logger.summary["battles"].append(summary_entry)
            return "skipped"

        logger.log("  obelisk: proceeding")
        obelisk_proceed = await try_call(
            logger, f"b{battle_num:02d}_obelisk_proceed",
            dd._post("/api/game/battle/obelisk-action",
                      sessionId=session_id, action="proceed")
        )
        if obelisk_proceed is None:
            logger.log("  obelisk-action proceed failed; aborting battle")
            summary_entry["result"] = "obelisk_proceed_error"
            logger.summary["battles"].append(summary_entry)
            return "error"

    monsters = _extract_monsters(setup)
    mon_summary = []
    for m in monsters:
        mon_summary.append({
            "name": m.get("name"),
            "hp": m.get("health"),
            "maxHp": m.get("maxHealth"),
            "tags": [t.get("label") for t in (m.get("tags") or []) if isinstance(t, dict)],
            "abilityCount": len(m.get("ability") or []),
            "abilityCycleFromIndex": m.get("abilityCycleFromIndex"),
        })
    summary_entry["monsters"] = mon_summary
    _display = " + ".join(f"{m['name']}({m['hp']})" for m in mon_summary)
    logger.log(f"  monsters: {_display}")

    # ---- pre-fight food selection ----
    # Correct order per knowledge/api/battle.md:
    #   1. setup-scene (done above)
    #   2. pre-fight
    #   3. select-boost  ← food activation MUST happen after pre-fight
    #   4. start-scene
    # Previously we called select-boost BEFORE pre-fight, which the server
    # rejected with "invalid fight prepare".
    prefight_char = await try_call(
        logger, f"b{battle_num:02d}_char_pre_food",
        dd.get_character(session_id),
    )
    food_list = []
    hp_before_battle = 60
    max_hp_before_battle = 60
    tc_before_battle = 0
    dices_before_battle = []
    if isinstance(prefight_char, dict):
        food_list = prefight_char.get("boosts") or []
        hp_before_battle = int(prefight_char.get("health") or 60)
        max_hp_before_battle = int(prefight_char.get("max_health") or 60)
        tc_before_battle = int(prefight_char.get("time_crystal") or 0)
        dices_before_battle = prefight_char.get("dices") or []

    food_id, food_name = _food_for_enemy(monsters, food_list)

    prefight = await try_call(logger, f"b{battle_num:02d}_prefight",
                               dd.battle_prefight(character_id, session_id))

    # Dump-all rule: ONLY the Ch2 chapter boss (Big Cheeze / Zomboid
    # Horde) gets every food in the backpack fired at once — it's the
    # final fight and there's no reason to hoard past it. Every other
    # fight (Ch1 boss, mini-bosses, big-baddies, regular baddies) uses
    # the matchup-specific single-food pick from _food_for_enemy, which
    # avoids activating foods with no positive effect (e.g. Scorch Sauce
    # dumped into a Ganondwarf fight where no dominant side exists).
    is_ch2_boss = in_state == "boss-baddie" and chapter == 2
    if is_ch2_boss and food_list:
        logger.log(f"  Ch2 boss: dumping ALL {len(food_list)} foods")
        for i, f in enumerate(food_list):
            await _activate_food(
                dd, logger, character_id, session_id, battle_num,
                f, prefight, tag=f"_all_{i}",
            )
    elif food_id:
        logger.log(f"  pre-fight food: activating {food_name}")
        food_entry = next(
            (f for f in food_list
             if isinstance(f, dict) and (f.get("id") or f.get("uuid")) == food_id),
            None,
        )
        if food_entry is not None:
            await _activate_food(
                dd, logger, character_id, session_id, battle_num,
                food_entry, prefight,
            )

    start = await try_call(logger, f"b{battle_num:02d}_start_scene",
                            dd.battle_start(session_id))

    # Pre-battle food (e.g. Brotein Bar MAX "Attack all 20") can kill
    # all enemies BEFORE start-scene. The server marks the battle as
    # 'win' immediately — calling resolve-turn would 400. Detect this
    # and skip straight to loot.
    pre_won = False
    if isinstance(start, dict):
        bp = ((start.get("state") or {}).get("battle") or {}).get("battlePhase")
        if bp == "win":
            logger.log(f"  pre-battle food killed all enemies (battlePhase=win)")
            pre_won = True
            last_hp = hp_before_battle
            summary_entry["result"] = "won"
            summary_entry["turns"] = 0
            summary_entry["hp_at_end"] = hp_before_battle

    last_hp = last_hp if pre_won else None
    rewind_attempts = 0
    MAX_REWINDS = 2
    turn_label_suffix = ""  # empty for first attempt, "_rwN" after rewinds

    if pre_won:
        won_battle = True
    else:
        won_battle = False

    while not pre_won:  # outer loop: allows rewind+replay (skip if pre-won)
        won_battle = False
        last_hp = None
        for turn_num in range(1, BATTLE_TURN_LIMIT + 1):
            res = await try_call(
                logger,
                f"b{battle_num:02d}_resolve{turn_label_suffix}_t{turn_num:02d}",
                dd.battle_resolve(session_id),
            )
            if res is None:
                summary_entry["result"] = "resolve_error"
                summary_entry["turns"] = turn_num - 1
                logger.summary["battles"].append(summary_entry)
                return "error"

            outcome = _extract_outcome(res)
            player_hp = _extract_player_hp(res)
            mons = _extract_monsters(res)
            alive = sum(1 for m in mons if m.get("health", 0) > 0)
            last_hp = player_hp

            logger.log(
                f"  t{turn_num}: outcome={outcome} playerHP={player_hp} alive={alive}"
            )

            if outcome in ("win", "won", "victory"):
                won_battle = True
                break
            if outcome in ("lose", "lost", "defeat", "dead"):
                summary_entry["result"] = "lost"
                summary_entry["turns"] = turn_num
                summary_entry["hp_at_end"] = 0
                logger.summary["battles"].append(summary_entry)
                return "lost"
            if alive == 0 and len(mons) > 0:
                won_battle = True
                break
            if player_hp is not None and player_hp <= 0:
                summary_entry["result"] = "lost"
                summary_entry["turns"] = turn_num
                summary_entry["hp_at_end"] = 0
                logger.summary["battles"].append(summary_entry)
                return "lost"
        else:
            logger.log(f"  battle reached turn limit {BATTLE_TURN_LIMIT}")
            summary_entry["result"] = "turn_limit"
            summary_entry["turns"] = BATTLE_TURN_LIMIT
            summary_entry["hp_at_end"] = last_hp
            logger.summary["battles"].append(summary_entry)
            return "turn_limit"

        # Battle was won — consider a TC-rewind if we took heavy damage
        # and the sim says a replay would likely end with more HP.
        if (
            won_battle
            and rewind_attempts < MAX_REWINDS
            # Battle rewind costs 2 TC baseline (knowledge/game/encounter-loot.md).
            # Escalates on chain-rewinds from the same space; assume +1 per
            # subsequent attempt as a safe lower bound.
            and tc_before_battle - (2 * (rewind_attempts + 1)) >= 0
            # Mid-obelisk rewinds are rejected by the server with
            # "invalid fight rewind" (rewinds aren't allowed between
            # the 2 fights of an obelisk). Skip the check entirely.
            and not is_obelisk
        ):
            should, rate, median = await _should_battle_rewind(
                dices_before_battle, monsters, hp_before_battle,
                max_hp_before_battle, last_hp, logger, battle_num,
            )
            logger.log(
                f"  rewind check: hp_end={last_hp} hp_before={hp_before_battle} "
                f"sim_better_rate={rate:.2f} sim_median={median} → rewind={should}"
            )
            if should:
                rewind_attempts += 1
                turn_label_suffix = f"_rw{rewind_attempts}"
                logger.log(f"  REWINDING battle (attempt {rewind_attempts})")
                rw = await try_call(
                    logger, f"b{battle_num:02d}_rewind{turn_label_suffix}",
                    dd._post("/api/game/battle/rewind", sessionId=session_id),
                )
                if rw is None:
                    logger.log("  rewind API failed; accepting original outcome")
                    break
                # After rewind the server puts the battle back into 'setup'
                # status — a bare /battle/start-scene is NOT enough to flip
                # to 'fighting' (verified: start-scene still returned
                # battlePhase=setup, isActive=False in v20 runs #8, #11).
                # Re-run the full pre-fight → start-scene sequence.
                pf_after_rw = await try_call(
                    logger, f"b{battle_num:02d}_rewind_prefight{turn_label_suffix}",
                    dd.battle_prefight(character_id, session_id),
                )
                if pf_after_rw is None:
                    logger.log("  pre-fight after rewind failed; bailing rewind loop")
                    break
                start_after_rw = await try_call(
                    logger, f"b{battle_num:02d}_rewind_start{turn_label_suffix}",
                    dd.battle_start(session_id),
                )
                if start_after_rw is None:
                    logger.log("  start-scene after rewind failed; bailing rewind loop")
                    break
                continue  # re-enter the while True loop
        break  # no rewind → exit outer loop

    # OBELISK: after the first fight wins, call setup-scene AGAIN for fight 2.
    if is_obelisk:
        logger.log("  obelisk: first fight won, setting up fight 2")
        setup2 = await try_call(
            logger, f"b{battle_num:02d}_obelisk_setup2",
            dd.battle_setup(session_id),
        )
        if setup2 is None:
            summary_entry["result"] = "obelisk_setup2_error"
            logger.summary["battles"].append(summary_entry)
            return "error"
        monsters2 = _extract_monsters(setup2)
        if monsters2:
            names2 = [f"{m.get('name')}({m.get('health')})" for m in monsters2]
            logger.log(f"  obelisk fight 2 monsters: {' + '.join(names2)}")

        await try_call(
            logger, f"b{battle_num:02d}_obelisk_prefight2",
            dd.battle_prefight(character_id, session_id),
        )
        await try_call(
            logger, f"b{battle_num:02d}_obelisk_start2",
            dd.battle_start(session_id),
        )

        for turn_num2 in range(1, BATTLE_TURN_LIMIT + 1):
            res2 = await try_call(
                logger, f"b{battle_num:02d}_obelisk_resolve2_t{turn_num2:02d}",
                dd.battle_resolve(session_id),
            )
            if res2 is None:
                summary_entry["result"] = "obelisk_resolve2_error"
                logger.summary["battles"].append(summary_entry)
                return "error"
            outcome2 = _extract_outcome(res2)
            player_hp2 = _extract_player_hp(res2)
            mons2 = _extract_monsters(res2)
            alive2 = sum(1 for m in mons2 if m.get("health", 0) > 0)
            logger.log(f"  obelisk t{turn_num2}: outcome={outcome2} hp={player_hp2} alive={alive2}")
            last_hp = player_hp2 if player_hp2 is not None else last_hp
            if outcome2 in ("win", "won", "victory"):
                break
            if outcome2 in ("lose", "lost", "defeat", "dead"):
                summary_entry["result"] = "lost"
                summary_entry["hp_at_end"] = 0
                logger.summary["battles"].append(summary_entry)
                return "lost"
            if alive2 == 0 and len(mons2) > 0:
                break
            if player_hp2 is not None and player_hp2 <= 0:
                summary_entry["result"] = "lost"
                summary_entry["hp_at_end"] = 0
                logger.summary["battles"].append(summary_entry)
                return "lost"

    # Won → loot phase
    if not pre_won:
        summary_entry["turns"] = turn_num
        summary_entry["hp_at_end"] = last_hp
    to_loot = await try_call(logger, f"b{battle_num:02d}_to_loot",
                              dd.battle_to_loot(session_id))
    loot_opts = await try_call(logger, f"b{battle_num:02d}_fetch_loot",
                                dd.fetch_loot(session_id))

    # Log the loot options shape for later analysis
    required_steps = []
    if isinstance(loot_opts, dict):
        summary_entry["loot_options_keys"] = list(loot_opts.keys())[:10]
        summary_entry["gold_offered"] = loot_opts.get("gold")
        summary_entry["boosts_offered"] = len(loot_opts.get("boosts") or [])
        summary_entry["trinkets_offered"] = len(loot_opts.get("trinkets") or [])
        summary_entry["burn_side"] = loot_opts.get("burnSide")
        phase_one = loot_opts.get("abilityPhaseOne")
        if isinstance(phase_one, dict):
            summary_entry["picked_dice"] = phase_one.get("pickedDice")
            abilities = phase_one.get("abilities") or []
            summary_entry["side_choices"] = [
                a.get("label") if isinstance(a, dict) else str(a)
                for a in (abilities if isinstance(abilities, list) else [])
            ][:5]
        required_steps = loot_opts.get("requiredSteps") or []

    logger.log(f"  loot required_steps: {required_steps}")

    # Append the battle entry BEFORE walking loot so walk_loot_steps
    # writes picked_die_index / picked_ability_label to THIS battle's
    # entry, not the previous one.
    summary_entry["result"] = "won"
    logger.summary["battles"].append(summary_entry)

    # Determine the battle's biome from monster tags — the loot pool is
    # biome-specific, so die selection should target the die whose role
    # matches the biome's pool (Ice Cave→defense, Volcano→offense,
    # Toxic Swamp→poison).
    battle_biome = None
    for m in monsters:
        if not isinstance(m, dict):
            continue
        for t in (m.get("tags") or []):
            label = t.get("label") if isinstance(t, dict) else None
            if label in ("Volcano", "Ice Cave", "Ice", "Toxic Swamp", "Swamp"):
                battle_biome = label
                break
        if battle_biome:
            break
    logger.log(f"  loot biome: {battle_biome or 'neutral'}")

    await walk_loot_steps(
        dd, logger, session_id, battle_num, required_steps, loot_opts,
        biome=battle_biome,
    )
    return "won"


async def walk_loot_steps(dd, logger, session_id, battle_num, required_steps, initial_opts, biome=None):
    """Walk the post-battle loot flow using the correct Zod schemas.

    Confirmed by user 2026-04-13:
      pick-dice: POST /api/game/battle/pick-dice
                 body {sessionId, diceMeta: {diceId, phase: 1}}
                 response includes the 3 ability options for the chosen die
      pick-ability: POST /api/game/battle/loot
                 body {sessionId, lootType: "pick-ability",
                       diceMeta: {abilityId, phase: 1}}
    """
    pick_abilities = []       # populated after pick-dice succeeds
    picked_die_id = None
    picked_die_index = None
    picked_ability_label = None
    general_opts = None       # pick-general response (source of trinket poolIds)

    for step in required_steps:
        logger.log(f"  loot step: {step}")

        if step == "pick-dice":
            char = await try_call(
                logger, f"b{battle_num:02d}_char_pre_pick_dice",
                dd.get_character(session_id),
            )
            dices = []
            if isinstance(char, dict):
                dices = char.get("dices") or []

            # Use die-selection heuristic — biome-aware so the offered
            # pool (Ice Cave → defensive, Volcano → offensive, Toxic
            # Swamp → poison) lands on the matching die role.
            die_idx = choose_die_for_upgrade(dices, biome=biome)
            picked_die_index = die_idx
            picked_die_id = None
            if dices and die_idx < len(dices):
                picked_die_id = dices[die_idx].get("id")

            role = DIE_ROLES.get(die_idx, "mixed")
            logger.log(f"    pick-dice die#{die_idx + 1} ({role}) id={picked_die_id} phase=1")

            pick_result = await try_call(
                logger, f"b{battle_num:02d}_loot_pick_dice",
                dd._post(
                    "/api/game/battle/pick-dice",
                    sessionId=session_id,
                    diceMeta={"diceId": picked_die_id, "phase": 1},
                ),
            )

            # Response shape: array of abilities (per OpenAPI).
            # The DDClient unwraps `data` already, so pick_result is either
            # a list directly or a dict we need to navigate.
            if isinstance(pick_result, list):
                pick_abilities = pick_result
            elif isinstance(pick_result, dict):
                for key in ("abilities", "data", "abilityPhaseOne"):
                    v = pick_result.get(key)
                    if isinstance(v, list):
                        pick_abilities = v
                        break
                    if isinstance(v, dict) and isinstance(v.get("abilities"), list):
                        pick_abilities = v["abilities"]
                        break

            labels = [
                a.get("label") if isinstance(a, dict) else str(a)
                for a in pick_abilities
            ]
            logger.log(f"    -> {len(pick_abilities)} options: {labels}")
            continue

        if step == "pick-ability":
            # Use the upgrade picker to rank the 3 offered sides for the die
            # we committed to in pick-dice. Pass current dice state for
            # context-aware combo scoring.
            ability_id = None
            die_idx_for_score = picked_die_index if picked_die_index is not None else 0

            # Fetch fresh character state for combo context
            ctx_char = await try_call(
                logger, f"b{battle_num:02d}_char_pre_pick_ability",
                dd.get_character(session_id),
            )
            ctx_dices = []
            ctx_target_die = None
            ctx_chapter = 1
            if isinstance(ctx_char, dict):
                ctx_dices = ctx_char.get("dices") or []
                if die_idx_for_score < len(ctx_dices):
                    ctx_target_die = ctx_dices[die_idx_for_score]
            # Need chapter for the Ch2 dilution skip rule
            try:
                _g = await dd.get_game(character_id)
                ctx_chapter = int(
                    ((_g or {}).get("lastSession") or {}).get("chapter") or 1
                )
            except Exception:
                ctx_chapter = 1

            if pick_abilities:
                best_idx, best_side, scored = pick_best_side(
                    die_idx_for_score,
                    pick_abilities,
                    target_die=ctx_target_die,
                    all_dice=ctx_dices,
                )

                # --- Duplicate-across-dice downweight ---
                # If the top-ranked side already exists by label on a
                # DIFFERENT die, multiply its score by 0.5 and re-rank.
                # One copy of "Attack 16, Duplicate this Side" is a combo;
                # a second is tolerable; a third is strictly dilutive
                # (v23 run #9 had this side on 3 dice).
                def _side_label_signature(ability):
                    if not isinstance(ability, dict):
                        return ""
                    return (ability.get("label") or "").strip().lower()

                existing_labels_other_dice = set()
                for di, d in enumerate(ctx_dices):
                    if di == die_idx_for_score or not isinstance(d, dict):
                        continue
                    for ab in (d.get("ability") or []):
                        sig = _side_label_signature(ab)
                        if sig:
                            existing_labels_other_dice.add(sig)

                adjusted = []
                for (orig_i, lbl, s, cat, tier, combos) in scored:
                    offered_sig = _side_label_signature(pick_abilities[orig_i])
                    if offered_sig and offered_sig in existing_labels_other_dice:
                        new_s = s * 0.5
                        combos = list(combos) + ["duplicate_across_dice_downweight"]
                        adjusted.append((orig_i, lbl, new_s, cat, tier, combos))
                    else:
                        adjusted.append((orig_i, lbl, s, cat, tier, combos))
                adjusted.sort(key=lambda x: x[2], reverse=True)
                scored = adjusted
                best_idx = scored[0][0] if scored else None
                best_side = pick_abilities[best_idx] if best_idx is not None else None

                # --- Ch2 dilution skip ---
                # In Ch2, skip the upgrade entirely if the best offered
                # side's score is below the average score of existing
                # non-exhausted sides on the target die. Taking a worse
                # side dilutes the die's roll quality. Per
                # `feedback_ch2_skip_weak_upgrades`.
                skip_upgrade = False
                if ctx_chapter == 2 and ctx_target_die and scored:
                    existing_sides = [
                        a for a in (ctx_target_die.get("ability") or [])
                        if isinstance(a, dict) and not a.get("exhausted", False)
                    ]
                    if existing_sides:
                        existing_scores = []
                        for es in existing_sides:
                            try:
                                sc, _ = score_side_for_die(
                                    die_idx_for_score, es,
                                    len(existing_sides),
                                    target_die=ctx_target_die,
                                    all_dice=ctx_dices,
                                )
                                existing_scores.append(sc)
                            except Exception:
                                pass
                        if existing_scores:
                            avg_existing = sum(existing_scores) / len(existing_scores)
                            best_offered_score = scored[0][2]
                            if best_offered_score < avg_existing:
                                skip_upgrade = True
                                logger.log(
                                    f"    Ch2 dilution skip: best offered "
                                    f"{best_offered_score:.1f} < die avg "
                                    f"{avg_existing:.1f} — skipping upgrade"
                                )

                # Log all scores for transparency
                for rank, (orig_i, lbl, s, cat, tier, combos) in enumerate(scored):
                    mark = " ← PICKED" if rank == 0 and not skip_upgrade else ""
                    combo_str = f"  combos={combos}" if combos else ""
                    logger.log(
                        f"    [{orig_i}] {lbl}  ({tier}/{cat})  score={s:.1f}{combo_str}{mark}"
                    )

                if skip_upgrade:
                    ability_id = None
                    picked_ability_label = "(skipped — dilutive)"
                elif best_side and isinstance(best_side, dict):
                    ability_id = best_side.get("uuid") or best_side.get("id")
                    picked_ability_label = best_side.get("label")
            logger.log(f"    pick-ability -> {picked_ability_label} ({ability_id})")

            if ability_id is not None:
                await try_call(
                    logger, f"b{battle_num:02d}_loot_pick_ability",
                    dd._post(
                        "/api/game/battle/loot",
                        sessionId=session_id,
                        lootType="pick-ability",
                        diceMeta={"abilityId": ability_id, "phase": 1},
                    ),
                )
            else:
                # Either no abilities available OR we chose to skip the
                # upgrade (Ch2 dilution). Either way, don't call pick-ability.
                if skip_upgrade:
                    logger.log(f"    skipped upgrade to preserve die quality")
                else:
                    logger.log(f"    no ability_id available; skipping")
            continue

        if step == "pick-boost":
            # pick-boost is required when inventory would overflow (>3 food).
            # Flow (user-confirmed, same shape as campfire food overflow):
            #   1. POST /api/game/boost/discard {sessionId, boostId: <old>}
            #   2. POST /api/game/battle/loot  {sessionId, lootType: "pick-boost",
            #                                    boostMeta: {boostId: <new>}}
            char = await try_call(
                logger, f"b{battle_num:02d}_char_for_boost",
                dd.get_character(session_id),
            )
            existing = []
            if isinstance(char, dict):
                existing = char.get("boosts") or []
            offered_boosts = []
            if isinstance(general_opts, dict):
                offered_boosts = general_opts.get("boosts") or []
            if offered_boosts and isinstance(offered_boosts[0], dict):
                # Pick the best incoming food, not just the first.
                best_incoming = max(
                    (b for b in offered_boosts if isinstance(b, dict)),
                    key=lambda b: _FOOD_VALUE.get(b.get("type") or "", 50),
                    default=None,
                )
                weakest = _pick_weakest_food(existing)
                if best_incoming is not None and weakest is not None:
                    new_id = best_incoming.get("id") or best_incoming.get("uuid")
                    new_type = best_incoming.get("type") or "?"
                    old_id = weakest.get("id") or weakest.get("uuid")
                    old_type = weakest.get("type") or "?"
                    # Only replace if the incoming food is strictly better.
                    new_score = _FOOD_VALUE.get(new_type, 50)
                    old_score = _FOOD_VALUE.get(old_type, 50)
                    if new_score > old_score:
                        logger.log(
                            f"    pick-boost: discard {old_type}({old_score}) "
                            f"→ keep {new_type}({new_score})"
                        )
                        await try_call(
                            logger, f"b{battle_num:02d}_boost_discard",
                            dd._post("/api/game/boost/discard",
                                      sessionId=session_id, boostId=old_id),
                        )
                        await try_call(
                            logger, f"b{battle_num:02d}_loot_pick_boost",
                            dd._post(
                                "/api/game/battle/loot",
                                sessionId=session_id,
                                lootType="pick-boost",
                                boostMeta={"boostId": new_id},
                            ),
                        )
                        continue
                    logger.log(
                        f"    pick-boost: incoming {new_type}({new_score}) not "
                        f"better than worst {old_type}({old_score}); skipping"
                    )
            # Fallback — bare lootType (declines the food). Lets the loot
            # loop advance without getting stuck on an undocumented branch.
            await try_call(
                logger, f"b{battle_num:02d}_loot_pick_boost_plain",
                dd._post(
                    "/api/game/battle/loot",
                    sessionId=session_id,
                    lootType="pick-boost",
                ),
            )
            continue

        if step == "pick-trinket":
            # Boss-only step. The pick-general response (stashed above)
            # contains the trinkets with their poolIds, e.g.
            #   [{"type": "deleteButton", "poolId": 28}, ...]
            # The server expects `trinketMeta: {poolId: <int>}`.
            offered_trinkets = []
            if isinstance(general_opts, dict):
                offered_trinkets = general_opts.get("trinkets") or []
            if offered_trinkets:
                type_to_label = {
                    "deleteButton": "Delete Button",
                    "gainStrengthWhenTurnStart": "Strength Up",
                    "greenade": "Greenade",
                    "scoring": "Scoring",
                    "quadforce": "Quadforce",
                    "birdMask": "Bird Mask",
                    "shibaMask": "Shiba Mask",
                    "idolOfImmunity": "Idol of Immunity",
                    "tinyTitan": "Tiny Titan",
                    "bottledFairy": "Bottled Fairy",
                    "adamantaeum": "Adamantaeum",
                    "jokerCard": "Joker Card",
                    "ketMask": "Ket Mask",
                    "kroniclesMask": "Kronicles Mask",
                }

                scored = []
                for t in offered_trinkets:
                    if not isinstance(t, dict):
                        continue
                    label = type_to_label.get(t.get("type"), t.get("type") or "?")
                    scored.append((t, TRINKET_SCORE.get(label, 25), label))
                scored.sort(key=lambda x: x[1], reverse=True)
                if not scored:
                    logger.log("    pick-trinket: no usable trinkets, skipping")
                    continue
                best_t, best_score, best_label = scored[0]
                pool_id = best_t.get("poolId")
                logger.log(
                    f"    pick-trinket: picking {best_label} "
                    f"(type={best_t.get('type')}, poolId={pool_id}, score={best_score})"
                )
                if pool_id is None:
                    logger.log("    pick-trinket: no poolId on best trinket, skipping")
                    continue
                await try_call(
                    logger, f"b{battle_num:02d}_loot_pick_trinket",
                    dd._post(
                        "/api/game/battle/loot",
                        sessionId=session_id,
                        lootType="pick-trinket",
                        trinketMeta={"poolId": pool_id},
                    ),
                )
                continue
            # No offered trinkets — skip the step
            logger.log("    pick-trinket: no offered trinkets in pick-general, skipping")
            continue

        # Generic steps: pick-general, exit
        r = await try_call(
            logger, f"b{battle_num:02d}_loot_{step}",
            dd._post("/api/game/battle/loot", sessionId=session_id, lootType=step),
        )
        # The pick-general response contains the full trinket offerings
        # with their poolIds — stash it for pick-trinket below.
        if step == "pick-general" and isinstance(r, dict):
            general_opts = r

    # stash what we picked in the logger summary so we can analyze it later
    if logger.summary["battles"]:
        logger.summary["battles"][-1]["picked_die_id"] = picked_die_id
        logger.summary["battles"][-1]["picked_die_index"] = picked_die_index
        logger.summary["battles"][-1]["picked_ability_label"] = picked_ability_label


# =====================================================================
# Run-goal strategy: every decision point routes through a strategy
# function chosen by RUN_GOAL. Each strategy is a pure function that
# returns (loot_type, reason). No `if RUN_GOAL == ...` scattered through
# the handlers.
# =====================================================================

RUN_GOAL = "stage2-clear"   # one of: "stage1-score", "stage2-clear"


def _campfire_stage2_clear(hp_pct, current_hp, max_hp, carrying_curse, has_burn_target):
    """Survival-first campfire strategy — reach stage 2.

    Priority:
      1. Curse → pick-burn (free removal).
      2. HP < 60% → pick-rest (heal priority).
      3. HP ≥ 60% AND burn target available → pick-burn (consolidate).
      4. HP ≥ 60% AND no burn target → choose-boost (stock food).

    Food pickups matter because the right food completely flips a fight
    (Ice Rice vs Ganondwarf, Boom Beans vs Firant Queen pack, etc.).
    Never pick-points / pick-mine — healing and food both beat them.
    """
    if carrying_curse:
        return "pick-burn", "carrying curse"
    if hp_pct < 0.60:
        return "pick-rest", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), healing"
    if has_burn_target:
        return "pick-burn", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), consolidating"
    return "choose-boost", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), stocking food"


def _campfire_stage1_score(hp_pct, current_hp, max_hp, carrying_curse, has_burn_target):
    """Score-farming campfire strategy — maximize stage-1 points.

    Happy to bank points when safe, and uses pick-burn only on curses.
      1. Curse → burn.
      2. HP < 60% → rest.
      3. HP ≥ 90% → pick-points (7000 points banked).
      4. Otherwise → rest.
    """
    if carrying_curse:
        return "pick-burn", "carrying curse"
    if hp_pct < 0.60:
        return "pick-rest", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), healing"
    if hp_pct >= 0.90:
        return "pick-points", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), banking"
    return "pick-rest", f"HP {current_hp}/{max_hp} ({hp_pct:.0%}), healing"


CAMPFIRE_STRATEGIES = {
    "stage2-clear": _campfire_stage2_clear,
    "stage1-score": _campfire_stage1_score,
}


# Map the game-state `upcoming_bb_*` code to a sim enemy key. Ch1
# biome mapping is known (per `BB_FIGHTS_CH1` in dd_agent/sim/enemies.py).
# Ch2 mapping is approximated based on observed compositions; adjust as
# more data arrives.
_BB_CODE_TO_SIM = {
    1: {
        "bb-ice":   "wendibrrr",
        "bb-vol":   "firant_queen",   # pack stand-in (solo proxy)
        "bb-swamp": "gorgon_zola",
    },
    2: {
        "bb-ice":   "pterrordactyl",
        "bb-vol":   "detonox",
        "bb-swamp": "detonox",        # no sim enemy for Deathbat/Lavamander; fall back
    },
}

# Map the game-state `upcoming_boss` name to a sim enemy key.
_BOSS_NAME_TO_SIM = {
    "Ganondwarf":     "ganondwarf",
    "Big Cheeze":     "big_cheeze_onslaught",  # conservative mid-difficulty mode
    "Zomboid Horde":  "zomboid_horde",
}


def _stress_enemy_for(upcoming_boss, upcoming_bb_code, chapter, node_type):
    """Pick the sim enemy key to use as the stress test for an upcoming
    big-baddie or boss fight. Reads the authoritative game-state fields
    (`upcoming_boss`, `upcoming_bb_<path>`) instead of guessing from biome.
    """
    if node_type == "boss-baddie":
        key = _BOSS_NAME_TO_SIM.get((upcoming_boss or "").strip())
        if key:
            return key
        return "ganondwarf" if (chapter or 1) == 1 else "big_cheeze_onslaught"
    # big-baddie
    ch = chapter or 1
    by_chapter = _BB_CODE_TO_SIM.get(ch, _BB_CODE_TO_SIM[1])
    key = by_chapter.get((upcoming_bb_code or "").strip())
    if key:
        return key
    return "wendibrrr" if ch == 1 else "pterrordactyl"


async def _nearest_bb_in_reach(dd, character_id, max_steps: int = 3):
    """Return the nearest big-baddie or boss-baddie node within
    `max_steps` steps on the active path, or None. Returns a dict with
    keys: type, biome, index, steps_away, chapter, upcoming_boss,
    upcoming_bb_code, stress_enemy_key.
    """
    try:
        game = await dd.get_game(character_id)
    except Exception:
        return None
    if not isinstance(game, dict):
        return None
    last = game.get("lastSession") or {}
    md = last.get("mapData") or {}
    progress = last.get("progress") or {}
    cur_idx = int(progress.get("currentIndex", 0) or 0)
    active_path = progress.get("activePath") or "main"
    chapter = last.get("chapter")
    upcoming_boss = game.get("upcoming_boss")
    upcoming_bb_code = game.get(f"upcoming_bb_{active_path}")
    key = {"main": "mainPathNodes", "fork1": "fork1Nodes", "fork2": "fork2Nodes"}.get(
        active_path, "mainPathNodes"
    )
    nodes = md.get(key) or []
    nearest = None
    for n in nodes:
        if not isinstance(n, dict):
            continue
        idx = n.get("index", 0) or 0
        if idx <= cur_idx or idx > cur_idx + max_steps:
            continue
        ttype = (n.get("type") or "").lower()
        if ttype not in ("big-baddie", "boss-baddie"):
            continue
        if nearest is None or idx < nearest["index"]:
            nearest = {
                "type": ttype,
                "biome": n.get("biome"),
                "index": idx,
                "steps_away": idx - cur_idx,
                "chapter": chapter,
                "upcoming_boss": upcoming_boss,
                "upcoming_bb_code": upcoming_bb_code,
            }
    if nearest:
        nearest["stress_enemy_key"] = _stress_enemy_for(
            upcoming_boss, upcoming_bb_code, chapter, nearest["type"],
        )
    return nearest


async def _next_bb_before_campfire(dd, character_id):
    """Scan the map for the next big-baddie/boss-baddie that appears
    before the next campfire. Returns the same dict shape as
    _nearest_bb_in_reach, or None if a campfire comes first (or no
    boss is ahead).
    """
    try:
        game = await dd.get_game(character_id)
    except Exception:
        return None
    if not isinstance(game, dict):
        return None
    last = game.get("lastSession") or {}
    md = last.get("mapData") or {}
    progress = last.get("progress") or {}
    cur_idx = int(progress.get("currentIndex", 0) or 0)
    active_path = progress.get("activePath") or "main"
    chapter = last.get("chapter")
    upcoming_boss = game.get("upcoming_boss")
    upcoming_bb_code = game.get(f"upcoming_bb_{active_path}")
    key = {"main": "mainPathNodes", "fork1": "fork1Nodes", "fork2": "fork2Nodes"}.get(
        active_path, "mainPathNodes"
    )
    nodes = sorted(
        [n for n in (md.get(key) or []) if isinstance(n, dict)],
        key=lambda n: n.get("index", 0) or 0,
    )
    # Skip past any campfire tiles that are adjacent to the current
    # position — the player is already at a campfire, so consecutive
    # campfire tiles don't count as "a campfire before the boss".
    past_campfire_cluster = False
    for n in nodes:
        idx = n.get("index", 0) or 0
        if idx <= cur_idx:
            continue
        ttype = (n.get("type") or "").lower()
        if ttype == "campfire" and not past_campfire_cluster:
            continue
        past_campfire_cluster = True
        if ttype == "campfire":
            return None
        if ttype in ("big-baddie", "boss-baddie"):
            result = {
                "type": ttype,
                "biome": n.get("biome"),
                "index": idx,
                "steps_away": idx - cur_idx,
                "chapter": chapter,
                "upcoming_boss": upcoming_boss,
                "upcoming_bb_code": upcoming_bb_code,
            }
            result["stress_enemy_key"] = _stress_enemy_for(
                upcoming_boss, upcoming_bb_code, chapter, ttype,
            )
            return result
    return None


def _dices_after_burn(dices, burn_die_id, burn_ability_id):
    """Return a deep-copy of `dices` with the burn target side removed."""
    import copy as _copy
    if not burn_die_id or not burn_ability_id:
        return None
    new_dices = _copy.deepcopy(dices)
    for d in new_dices:
        if not isinstance(d, dict):
            continue
        if d.get("id") == burn_die_id:
            d["ability"] = [
                a for a in (d.get("ability") or [])
                if a.get("uuid") != burn_ability_id
            ]
            break
    return new_dices


async def _sim_campfire_options(
    logger, dices, current_hp, max_hp, biome,
    burn_die_id, burn_ability_id, enemy_key=None,
):
    """Run the sim for baseline / rest / burn against the stress enemy
    (from the game-state `upcoming_boss`/`upcoming_bb_*` fields, passed
    as `enemy_key`). Return a list of (label, loot_type, winrate, hp_end)
    tuples sorted best-first.

    Food option is NOT yet simmed here — it needs setup.receivingBoosts
    and the food-application framework.
    """
    results = []

    base_wr, base_hp_loss, base_mean_hp = await _sim_big_baddie_survival(
        dices, biome, current_hp, max_hp, trials=40, enemy_key=enemy_key,
    )
    base_hp_end = int(base_mean_hp)
    results.append(("baseline", None, base_wr, base_hp_end))

    rest_hp = min(max_hp, current_hp + int(max_hp * 0.4))
    rest_wr, rest_hp_loss, rest_mean_hp = await _sim_big_baddie_survival(
        dices, biome, rest_hp, max_hp, trials=40, enemy_key=enemy_key,
    )
    rest_hp_end = int(rest_mean_hp)
    results.append(("rest", "pick-rest", rest_wr, rest_hp_end))

    burn_dices = _dices_after_burn(dices, burn_die_id, burn_ability_id)
    if burn_dices:
        burn_wr, burn_hp_loss, burn_mean_hp = await _sim_big_baddie_survival(
            burn_dices, biome, current_hp, max_hp, trials=40,
            enemy_key=enemy_key,
        )
        burn_hp_end = int(burn_mean_hp)
        results.append(("burn", "pick-burn", burn_wr, burn_hp_end))

    # Sort: primary by winrate, secondary by hp_end
    results.sort(key=lambda r: -(r[2] * 100 + r[3]))
    logger.log(
        "  campfire sim options: "
        + " | ".join(f"{r[0]}={r[2]:.0%}@{r[3]}" for r in results)
    )
    return results


async def _near_boss_tile(dd, character_id) -> bool:
    """True if the boss-baddie tile is within 3 steps of the current
    position on the active path. Used by campfire handler to decide
    whether to switch to pre-boss burn logic.
    """
    try:
        game = await dd.get_game(character_id)
    except Exception:
        return False
    if not isinstance(game, dict):
        return False
    last = game.get("lastSession") or {}
    md = last.get("mapData") or {}
    progress = last.get("progress") or {}
    cur_idx = int(progress.get("currentIndex", 0) or 0)
    active_path = progress.get("activePath") or "main"
    key = {"main": "mainPathNodes", "fork1": "fork1Nodes", "fork2": "fork2Nodes"}.get(active_path, "mainPathNodes")
    nodes = md.get(key) or []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        idx = n.get("index", 0) or 0
        if cur_idx <= idx <= cur_idx + 3:
            if (n.get("type") or "").lower() == "boss-baddie":
                return True
    return False


async def handle_campfire(dd, logger, session_id, character_id, iteration, char):
    """Campfire handler. Delegates the decision to the strategy selected
    by RUN_GOAL; this function only handles I/O (setup-scene, loot post,
    fallback chain).

    Loot options (reference):
      pick-rest   — heal 40% of max
      pick-burn   — burn a side (free, no HP cost) — needs diceMeta
      pick-food   — get 2 random food items
      pick-points — gain 7000 points
      pick-mine   — gain 5 Time Crystals
    """
    setup = await try_call(
        logger, f"it{iteration:03d}_campfire_setup",
        dd._post("/api/game/campfire/setup-scene",
                  character_id=character_id, session_id=session_id)
    )

    dices = []
    current_hp = 60
    max_hp = 60
    if isinstance(char, dict):
        dices = char.get("dices") or []
        current_hp = char.get("health", 60) or 60
        max_hp = char.get("max_health", 60) or 60

    hp_pct = current_hp / max_hp if max_hp else 1.0
    carrying_curse = has_curse(dices)

    # Pre-boss mode: if the upcoming tile (or the tile within 2-3 steps)
    # is a boss-baddie, use the pre-boss burn strategy — concentrate rolls
    # on strong sides by burning weakest starters.
    is_preboss = await _near_boss_tile(dd, character_id)
    if is_preboss:
        burn_die_id, burn_ability_id, burn_label, burn_die_idx = pick_burn_target_preboss(dices)
        if burn_ability_id:
            logger.log(f"  campfire: near boss, using pre-boss burn target")
    else:
        burn_die_id, burn_ability_id, burn_label, burn_die_idx = pick_burn_target(dices)
    has_burn_target = burn_ability_id is not None

    # When an unavoidable big-baddie is ≤3 steps away, skip the HP-percent
    # rules and run a simulation of each option (baseline/rest/burn) vs
    # the upcoming fight. Pick by score = winrate*100 + hp_end. This
    # catches the "88% HP → burn → walk into big-baddie → chain death"
    # failure mode from v21 run #4 where a 7 HP rest alone wouldn't
    # have saved the run but a sim could rank burn vs rest vs food.
    sim_override = None
    # Force burn at very high HP regardless of sim — a 40% rest is wasted
    # when HP is already near full, while burning compounds forever. Per
    # `feedback_dice_bloat_quality` rule #4.
    if not carrying_curse and has_burn_target and hp_pct >= 0.90:
        sim_override = (
            "pick-burn",
            f"HP {current_hp}/{max_hp} ({hp_pct:.0%}) — force burn at high HP",
        )
    elif not carrying_curse:
        near_bb = await _next_bb_before_campfire(dd, character_id)
        if near_bb:
            if near_bb["type"] == "boss-baddie":
                stress_label = near_bb["upcoming_boss"] or "?"
            else:
                stress_label = near_bb["upcoming_bb_code"] or "?"
            logger.log(
                f"  campfire: {near_bb['type']} at +{near_bb['steps_away']} "
                f"→ {stress_label} (stress={near_bb['stress_enemy_key']})"
            )
            options = await _sim_campfire_options(
                logger, dices, current_hp, max_hp, near_bb["biome"],
                burn_die_id, burn_ability_id,
                enemy_key=near_bb["stress_enemy_key"],
            )
            # Prefer burn when rest's winrate advantage is marginal AND
            # HP is healthy enough to absorb it. Below 50% HP, always
            # respect the sim's rest preference — survival trumps compounding.
            # Also check HP end: if rest leaves significantly more HP after
            # the fight, prefer rest (we need that HP for subsequent fights).
            # Exception: boss-baddie (Ganondwarf) gives a full heal after,
            # so HP end doesn't matter — only winrate.
            is_boss = near_bb["type"] == "boss-baddie"
            best = options[0]
            if best[0] == "rest" and hp_pct > 0.50 and best[2] >= 0.50:
                burn_opt = next((o for o in options if o[0] == "burn"), None)
                if burn_opt and best[2] - burn_opt[2] <= 0.10:
                    hp_end_gap = best[3] - burn_opt[3]
                    if (is_boss and burn_opt[2] >= 0.50) or hp_end_gap < 10:
                        logger.log(
                            f"    burn within 10% of rest "
                            f"({burn_opt[2]:.0%} vs {best[2]:.0%}, "
                            f"hp_end {burn_opt[3]} vs {best[3]}) "
                            f"— preferring burn (compounds)"
                        )
                        best = burn_opt
                    else:
                        logger.log(
                            f"    burn within 10% winrate of rest "
                            f"({burn_opt[2]:.0%} vs {best[2]:.0%}) but "
                            f"rest HP end {best[3]} >> burn HP end {burn_opt[3]} "
                            f"— keeping rest (need HP for later fights)"
                        )
            # When ALL options have sub-50% winrate, neither rest nor burn
            # will reliably save the run. Pick food instead — a lucky pull
            # (Godmode Guac, Brrrito, etc.) can completely flip the fight.
            if best[2] < 0.50:
                logger.log(
                    f"    all sim options below 50% (best={best[0]}@{best[2]:.0%}) "
                    f"— choosing food (hail mary)"
                )
                sim_override = ("choose-boost", f"sim hopeless ({best[0]}={best[2]:.0%}@{best[3]}), food hail mary")
            elif best[1] is None:  # baseline won — fall through to rest
                sim_override = ("pick-rest", f"sim baseline@{best[3]}, rest as safe default")
            else:
                sim_override = (best[1], f"sim {best[0]}={best[2]:.0%}@{best[3]}")

    if sim_override:
        loot_type, reason = sim_override
    else:
        strategy = CAMPFIRE_STRATEGIES.get(RUN_GOAL, _campfire_stage2_clear)
        loot_type, reason = strategy(
            hp_pct, current_hp, max_hp, carrying_curse, has_burn_target
        )

    logger.log(f"  campfire decision ({RUN_GOAL}): {loot_type} ({reason})")

    # For pick-burn we also need to specify the target side via diceMeta
    body = {"sessionId": session_id, "lootType": loot_type}
    if loot_type == "pick-burn":
        if burn_ability_id:
            body["diceMeta"] = {"diceId": burn_die_id, "abilityId": burn_ability_id}
            logger.log(f"    burn target: {burn_label} on die#{(burn_die_idx or 0) + 1}")
        else:
            logger.log(f"    no burn target found, falling back to rest")
            body["lootType"] = "pick-rest"
            loot_type = "pick-rest"

    if loot_type == "choose-boost":
        # Campfire food flow:
        #   1. POST campfire/loot with lootType=choose-boost
        #   2. If existing + incoming > MAX_FOODS, discard weakest current
        #      via /api/game/boost/discard, then POST campfire/loot again
        #      with lootType=pick-boost + boostMeta={boostId: <chosen>}.
        setup_recv = []
        if isinstance(setup, dict):
            setup_recv = setup.get("receivingBoosts") or []
        existing_foods = [b for b in (char.get("boosts") or []) if isinstance(b, dict)] \
            if isinstance(char, dict) else []
        MAX_FOODS = 3
        # Edge case: server returns receivingBoosts=[] when the backpack
        # is full (nothing to offer). choose-boost would 400 in that case.
        # Fall through to pick-rest instead.
        if not setup_recv:
            logger.log("    food flow: no incoming foods offered, switching to pick-rest")
            loot_type = "pick-rest"
            body = {"sessionId": session_id, "lootType": "pick-rest"}
            r = await try_call(
                logger, f"it{iteration:03d}_campfire_pick-rest",
                dd._post("/api/game/campfire/loot", **body)
            )
            if r is None:
                await try_call(
                    logger, f"it{iteration:03d}_campfire_exit",
                    dd._post("/api/game/campfire/exit", sessionId=session_id)
                )
            return
        total_after = len(existing_foods) + len(setup_recv)
        logger.log(
            f"    food flow: existing={len(existing_foods)} incoming={len(setup_recv)} "
            f"(max {MAX_FOODS})"
        )
        r = await try_call(
            logger, f"it{iteration:03d}_campfire_choose-boost",
            dd._post("/api/game/campfire/loot",
                      sessionId=session_id, lootType="choose-boost")
        )
        # choose-boost can return null on success (action consumed, no body).
        # If setup had receivingBoosts, proceed with pick-boost regardless —
        # if it truly failed, pick-boost will also fail and we exit cleanly.
        if total_after > MAX_FOODS:
            weakest = _pick_weakest_food(existing_foods)
            if weakest and isinstance(weakest, dict):
                weakest_id = weakest.get("id") or weakest.get("uuid")
                weakest_type = weakest.get("type") or "?"
                logger.log(f"    discarding {weakest_type} to make room")
                await try_call(
                    logger, f"it{iteration:03d}_boost_discard",
                    dd._post("/api/game/boost/discard",
                              sessionId=session_id, boostId=weakest_id)
                )
            # Pick the best incoming food (highest _FOOD_VALUE).
            best = None
            best_score = -1
            for b in setup_recv:
                if not isinstance(b, dict):
                    continue
                ftype = b.get("type") or ""
                score = _FOOD_VALUE.get(ftype, 50)
                if score > best_score:
                    best_score = score
                    best = b
            if best is not None:
                best_id = best.get("uuid") or best.get("id")
                best_type = best.get("type") or "?"
                logger.log(f"    pick-boost: keeping {best_type}")
                await try_call(
                    logger, f"it{iteration:03d}_campfire_pick-boost",
                    dd._post("/api/game/campfire/loot",
                              sessionId=session_id,
                              lootType="pick-boost",
                              boostMeta={"boostId": best_id})
                )
        else:
            # total_after <= MAX_FOODS: choose-boost already added both
            # incoming foods. No discard or pick-boost needed.
            logger.log(f"    no overflow — choose-boost added both foods")
        # choose-boost flow complete — exit campfire, don't fall through to rest
        await try_call(
            logger, f"it{iteration:03d}_campfire_exit",
            dd._post("/api/game/campfire/exit", sessionId=session_id)
        )
        return
    else:
        r = await try_call(
            logger, f"it{iteration:03d}_campfire_{loot_type}",
            dd._post("/api/game/campfire/loot", **body)
        )

    if r is None:
        # Fallback chain: if chosen option fails, try rest, then exit
        if loot_type != "pick-rest":
            await try_call(
                logger, f"it{iteration:03d}_campfire_fallback_rest",
                dd._post("/api/game/campfire/loot",
                          sessionId=session_id, lootType="pick-rest")
            )
        await try_call(
            logger, f"it{iteration:03d}_campfire_exit",
            dd._post("/api/game/campfire/exit", sessionId=session_id)
        )


async def handle_bub(dd, logger, session_id, character_id, iteration):
    """Visit Bub's shop. Strategy (user 2026-04-14):
      1. Always buy the burn if HP permits (ability removal is mandatory)
      2. Buy 1-2 sides if gold permits
      3. Buy trinkets if high-tier (Quadforce, Tiny Titan, etc.)
      4. Exit
    """
    setup = await try_call(
        logger, f"it{iteration:03d}_bub_setup",
        dd._post("/api/game/bub/setup-scene",
                  character_id=character_id,
                  session_id=session_id)
    )
    if not isinstance(setup, dict):
        await try_call(
            logger, f"it{iteration:03d}_bub_exit_early",
            dd._post("/api/game/bub/exit", sessionId=session_id)
        )
        return

    items = setup.get("shopItems") or []
    burns_done = setup.get("burns", 0)
    logger.log(f"  bub shop: {len(items)} items, burns_done={burns_done}")
    for it in items[:15]:
        if isinstance(it, dict):
            payload = it.get("payload") or {}
            label = payload.get("label") if isinstance(payload, dict) else str(payload)
            logger.log(
                f"    [{it.get('type')}] price={it.get('price')} "
                f"sale={it.get('isSale')}  {label}"
            )

    # Check player HP — only burn if we have >= 10 HP (6 burn cost + safety buffer)
    char = await try_call(
        logger, f"it{iteration:03d}_bub_char_check",
        dd.get_character(session_id)
    )
    current_hp = 60
    dices = []
    if isinstance(char, dict):
        current_hp = char.get("health", 60)
        dices = char.get("dices") or []

    burn_item = next((it for it in items if isinstance(it, dict) and it.get("type") == "burn"), None)
    burn_done = False

    if burn_item and current_hp >= 25:
        burn_id = burn_item.get("id")
        health_cost = burn_item.get("price", 6)

        # Smart burn target selection (curses first, then duplicates, etc.)
        target_die_id, target_ability_id, target_label, target_die_idx = pick_burn_target(dices)

        if target_ability_id:
            die_name = f"die#{target_die_idx + 1}" if target_die_idx is not None else "?"
            logger.log(
                f"  attempting burn: {target_label} on {die_name} "
                f"(health cost {health_cost}, current HP {current_hp})"
            )
            deal = await try_call(
                logger, f"it{iteration:03d}_bub_deal_burn",
                dd._post(
                    "/api/game/bub/deal",
                    session_id=session_id,
                    items=[{
                        "id": burn_id,
                        "gold": 0,
                        "health": health_cost,
                        "qty": 1,
                    }],
                )
            )
            if deal is not None:
                loot = await try_call(
                    logger, f"it{iteration:03d}_bub_loot_burn",
                    dd._post(
                        "/api/game/bub/loot",
                        sessionId=session_id,
                        id=burn_id,
                        diceId=target_die_id,
                        abilityId=target_ability_id,
                    )
                )
                if loot is not None:
                    burn_done = True
                    logger.log(f"  BURN successful")
        else:
            logger.log(f"  no Attack 4 on Die 1 to burn")
    elif burn_item:
        logger.log(f"  skipping burn: HP {current_hp} too low")

    # ---- Side purchases (up to 2, gold-gated) ----
    # Re-fetch char after the burn to get updated gold.
    char2 = await try_call(
        logger, f"it{iteration:03d}_bub_char_after_burn",
        dd.get_character(session_id),
    )
    gold = int(char2.get("gold", 0) or 0) if isinstance(char2, dict) else 0
    dices_after = char2.get("dices") or [] if isinstance(char2, dict) else dices
    side_items = [it for it in items if isinstance(it, dict) and it.get("type") == "side" and not it.get("boughtAt")]

    if side_items:
        logger.log(f"  bub sides available: {len(side_items)}, gold={gold}")

    # Score each offered side against each die and pick the top 2 whose
    # best placement beats a minimum score threshold.
    # Balance rule: if the build is defense-heavy and lacks offensive
    # upgrades, boost attack/poison side scores to restore kill speed.
    from dd_agent.sim.upgrade_picker import (
        score_side_for_die, classify_side, DIE_ROLES,
        _count_offensive_upgrades, _count_defensive_upgrades,
    )
    off_count = _count_offensive_upgrades(dices_after)
    def_count = _count_defensive_upgrades(dices_after)
    needs_offense = def_count > off_count and def_count >= 2

    side_scores = []
    for it in side_items:
        payload = it.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        # Score on best die
        best_score = -999
        best_die_idx = 0
        for di in range(min(4, len(dices_after))):
            target = dices_after[di] if di < len(dices_after) else None
            try:
                s, _ = score_side_for_die(di, payload, target_die=target, all_dice=dices_after)
            except Exception:
                s = 0
            if s > best_score:
                best_score = s
                best_die_idx = di
        if needs_offense and classify_side(payload) == "attack":
            best_score *= 2.0
        side_scores.append((best_score, it, best_die_idx))
    side_scores.sort(key=lambda x: -x[0])

    sides_bought = 0
    for score, item, die_idx in side_scores[:2]:
        if sides_bought >= 2:
            break
        price = int(item.get("price") or 999)
        if gold < price:
            logger.log(f"    skip side: gold {gold} < price {price}")
            continue
        if score < 20:
            logger.log(f"    skip side: low score ({score:.0f})")
            continue
        item_id = item.get("id")
        die_id = dices_after[die_idx].get("id") if die_idx < len(dices_after) else None
        label = (item.get("payload") or {}).get("label", "?")
        logger.log(f"  buying side: {label} → die#{die_idx+1} for {price}g (score={score:.0f})")
        deal = await try_call(
            logger, f"it{iteration:03d}_bub_deal_side_{sides_bought}",
            dd._post(
                "/api/game/bub/deal",
                session_id=session_id,
                items=[{"id": item_id, "gold": price, "health": 0, "qty": 1}],
            ),
        )
        if deal is not None:
            loot = await try_call(
                logger, f"it{iteration:03d}_bub_loot_side_{sides_bought}",
                dd._post(
                    "/api/game/bub/loot",
                    sessionId=session_id,
                    id=item_id,
                    diceId=die_id,
                ),
            )
            if loot is not None:
                sides_bought += 1
                gold -= price
                logger.log(f"    side purchased")

    # ---- Trinket purchases (high-tier only) ----
    trinket_items = [it for it in items if isinstance(it, dict) and it.get("type") == "trinket" and not it.get("boughtAt")]
    # Map trinket payload type → display label for scoring
    type_to_label = {
        "deleteButton": "Delete Button", "gainStrengthWhenTurnStart": "Strength Up",
        "greenade": "Greenade", "scoring": "Scoring", "quadforce": "Quadforce",
        "birdMask": "Bird Mask", "shibaMask": "Shiba Mask",
        "idolOfImmunity": "Idol of Immunity", "tinyTitan": "Tiny Titan",
        "bottledFairy": "Bottled Fairy", "adamantaeum": "Adamantaeum",
        "jokerCard": "Joker Card", "ketMask": "Ket Mask",
        "kroniclesMask": "Kronicles Mask", "immuneFromBleed": "Ket Mask",
        "snakeSkull": "Snake Skull", "sunstone": "Sunstone",
    }
    for it in trinket_items:
        payload = it.get("payload") or ""
        if isinstance(payload, dict):
            payload = payload.get("type") or ""
        label = type_to_label.get(payload, payload)
        score = TRINKET_SCORE.get(label, 25)
        price = int(it.get("price") or 999)
        # Only buy high-tier (≥80) or Tiny Titan / Quadforce specifically
        if score < 80:
            continue
        if gold < price:
            logger.log(f"    skip trinket {label}: gold {gold} < price {price}")
            continue
        item_id = it.get("id")
        logger.log(f"  buying trinket: {label} for {price}g (score={score})")
        deal = await try_call(
            logger, f"it{iteration:03d}_bub_deal_trinket",
            dd._post(
                "/api/game/bub/deal",
                session_id=session_id,
                items=[{"id": item_id, "gold": price, "health": 0, "qty": 1}],
            ),
        )
        if deal is not None:
            await try_call(
                logger, f"it{iteration:03d}_bub_loot_trinket",
                dd._post("/api/game/bub/loot", sessionId=session_id, id=item_id),
            )
            gold -= price

    # Exit
    await try_call(
        logger, f"it{iteration:03d}_bub_exit",
        dd._post("/api/game/bub/exit", sessionId=session_id)
    )


# Trinkets that are situational/biome-specific — OK to trade away.
JUNK_TRINKETS = {
    # Per user 2026-04-14 — fine to trade in the Trade Offer mystery,
    # the incoming mystery trinket is usually a net upgrade.
    "Pudgy Mask", "Lizard Mask", "Ket Mask", "Pet Hooligan Mask", "Snake Skull",
}

# Boss-trinket and rare trinket preference for pick-trinket step.
# Higher score = prefer picking.
TRINKET_SCORE = {
    # S+++++ — top of everything
    "Quadforce": 150,  # reroll-based combos, user's #1 trinket
    # Auto-buy at any HP cost (free passive value every turn)
    "Tiny Titan": 92,  # 16 dmg to last enemy every turn, compounds
    # Strong boss-tier
    "Scoring": 88,
    "Delete Button": 85,
    "Greenade": 85,
    "Bottled Fairy": 75,
    "Adamantaeum": 72,
    # Situational — good only for matching build
    "Bird Mask": 55,  # only valuable if attack-heavy; skip on poison/bleed
    "Joker Card": 65,
    # Bottom-tier boss drops per user 2026-04-13 — never worth a slot
    "Idol of Immunity": 20,
    "Shiba Mask": 20,  # useless on poison builds
    # Common — strong
    "Ket Mask": 60,  # Bleed immune — critical vs Detonox
    "Kronicles Mask": 58,  # Freeze immune
    "Snake Skull": 55,
    "Sunstone": 50,
    "Amulet of Yendor": 48,
    "Pet Hooligan Mask": 48,
    "Noggles": 45,
    "Turtle Shell": 40,
    # Common — situational
    "Pudgy Mask": 30,
    "Lizard Mask": 30,
}


def score_trinket(trinket_dict) -> int:
    """Return a preference score for a trinket payload."""
    if not isinstance(trinket_dict, dict):
        return 0
    label = trinket_dict.get("label") or trinket_dict.get("name") or ""
    return TRINKET_SCORE.get(label, 25)


# Food rules for pre-fight activation. Each rule: (enemy_match_fn, food_name_priority).
# Weak foods (replaced first when inventory overflows)
_FOOD_VALUE = {
    "Rage Shake": 30,
    "Pickle": 35,
    "Toxipop": 40,
    "Snackrifice": 45,
    "Heat Meat": 50,
    "Clutch Creme": 55,
    "Boom Beans": 60,
    "Brrrito Blockerito": 65,
    "Ice Rice": 70,
    "Brotein Bar MAX": 75,
    "Scorch Sauce": 50,
    "Godmode Guac": 90,  # rare
    "Ascendacandy": 92,  # rare
    "Crit Chips": 85,  # rare
    "Giga Juice": 88,  # rare
}


def _pick_weakest_food(food_list: list):
    if not food_list:
        return None
    worst = None
    worst_score = 999
    for f in food_list:
        if isinstance(f, dict):
            ftype = f.get("type") or f.get("name") or ""
            score = _FOOD_VALUE.get(ftype, 50)
            if score < worst_score:
                worst_score = score
                worst = f
    return worst


def _score_monster_threats(monsters: list) -> dict:
    """Introspect the monster list's ability patterns and return a threat
    profile (total damage, total poison/bleed/freeze applied, curse count,
    total enemy HP, etc.) that food selection can branch on.
    """
    profile = {
        "total_dmg": 0,
        "max_hit": 0,
        "total_poison": 0,
        "total_bleed": 0,
        "total_freeze": 0,
        "total_curse": 0,
        "total_hp": 0,
        "enemy_count": 0,
        "any_boss": False,
        "self_strength": 0,
        "self_block": 0,
    }
    if not isinstance(monsters, list):
        return profile
    for m in monsters:
        if not isinstance(m, dict):
            continue
        profile["enemy_count"] += 1
        profile["total_hp"] += int(m.get("maxHealth") or m.get("health") or 0)
        tags = [t.get("label") for t in (m.get("tags") or []) if isinstance(t, dict)]
        if "Boss" in tags or "Big Baddie" in tags:
            profile["any_boss"] = True
        for a in (m.get("ability") or []):
            if not isinstance(a, dict):
                continue
            dmg = (a.get("damage") or {}).get("value", 0) or 0
            hits = (a.get("damage") or {}).get("hits", 1) or 1
            per_turn_dmg = int(dmg) * int(hits)
            profile["total_dmg"] += per_turn_dmg
            if per_turn_dmg > profile["max_hit"]:
                profile["max_hit"] = per_turn_dmg
            profile["total_poison"] += int((a.get("poison") or {}).get("value", 0) or 0)
            profile["total_bleed"] += int((a.get("bleed") or {}).get("duration", 0) or 0)
            profile["total_freeze"] += int((a.get("freeze") or {}).get("duration", 0) or 0)
            profile["self_strength"] += int((a.get("strength") or {}).get("value", 0) or 0)
            profile["self_block"] += int((a.get("block") or {}).get("value", 0) or 0)
            label = (a.get("label") or "").lower()
            if "curse" in label:
                profile["total_curse"] += 1
    return profile


def _food_for_enemy(monsters: list, foods: list) -> tuple:
    """Return (food_id, food_name) to activate pre-fight, or (None, None).

    Priorities based on 100-trial sim results in feedback_food_sim_rankings:

    Tier S (always beat most alternatives): Godmode Guac, Brotein Bar MAX, Giga Juice
    Tier A: Boom Beans, Rage Shake, Heat Meat
    Tier B: Ice Rice (Ganondwarf/Gorgon-zola only), Pickle, Brrrito Blockerito
    Tier C: Crit Chips, Clutch Creme, Toxipop
    Tier D (skip): Scorch Sauce (net negative in sim), Snackrifice

    Matchup-specific hooks override the generic order when the current
    monsters have a specific counter (Ice Rice vs debuff openers, Pickle
    vs multi-hit bosses, Boom Beans vs 3+ enemy packs).
    """
    if not monsters or not foods:
        return (None, None)

    food_map = {}
    for f in foods:
        if isinstance(f, dict):
            ftype = f.get("type") or f.get("name")
            if ftype:
                food_map[ftype] = f

    def _pick(preferences: list):
        for name in preferences:
            if name in food_map:
                return (
                    food_map[name].get("id") or food_map[name].get("uuid"),
                    food_map[name].get("type"),
                )
        return (None, None)

    profile = _score_monster_threats(monsters)

    # Skip chaff fights — food is too valuable to burn on small baddies.
    dangerous = (
        profile["any_boss"]
        or profile["total_hp"] >= 60
        or profile["total_dmg"] >= 20
        or profile["total_poison"] >= 3
        or profile["total_bleed"] >= 3
        or profile["total_curse"] >= 1
    )
    if not dangerous:
        return (None, None)

    # Universal Tier-S list used as fallback in every matchup branch.
    S_TIER = ["Godmode Guac", "Brotein Bar MAX", "Giga Juice"]

    # Monster-name lookup for explicit counter-picks.
    names_lower = " ".join(
        (m.get("name") or "").lower() for m in monsters if isinstance(m, dict)
    )
    is_ganondwarf = "ganondwarf" in names_lower
    is_gorgon_zola = "gorgon" in names_lower
    is_pterrordactyl = "pterrordactyl" in names_lower
    is_detonox = "detonox" in names_lower
    is_firant_queen_pack = "firant queen" in names_lower

    # -------------------------------------------------------------
    # Explicit matchup picks (sim-backed, most specific first)
    # -------------------------------------------------------------

    # Ganondwarf: Ice Rice negates the T1 triple-debuff (+49% winrate).
    # Tied with Godmode Guac in sim; prefer Ice Rice when available.
    if is_ganondwarf:
        pick = _pick(["Ice Rice"] + S_TIER + ["Pickle", "Boom Beans", "Brrrito Blockerito"])
        if pick[0]:
            return pick

    # Gorgon-zola: Ice Rice eats the T1 Poison 3 opener (+64% winrate).
    if is_gorgon_zola:
        pick = _pick(["Ice Rice"] + S_TIER + ["Boom Beans", "Rage Shake", "Heat Meat"])
        if pick[0]:
            return pick

    # Pterrordactyl: Pickle's +6/turn block refill perfectly counters the
    # multi-hit bursts (+41% winrate, behind only Godmode Guac).
    if is_pterrordactyl:
        pick = _pick(S_TIER + ["Pickle", "Brrrito Blockerito", "Rage Shake", "Heat Meat"])
        if pick[0]:
            return pick

    # Detonox: bleed + Str ramp bypasses block walls entirely. Damage
    # foods only — fast kill beats the turn-7 self-destruct.
    if is_detonox:
        pick = _pick(S_TIER + ["Boom Beans", "Heat Meat", "Rage Shake", "Crit Chips"])
        if pick[0]:
            return pick

    # Firant Queen pack (space-25 mini-boss): Boom Beans targets the
    # back Blue Firant, kills it + AoE-splashes the chaff for a 1v1 vs
    # the Queen. Tied with Brotein Bar MAX at +44%.
    if is_firant_queen_pack:
        pick = _pick(["Brotein Bar MAX", "Boom Beans"] + S_TIER
                     + ["Rage Shake", "Pickle", "Heat Meat"])
        if pick[0]:
            return pick

    # -------------------------------------------------------------
    # Profile-based fallbacks for unrecognized enemies
    # -------------------------------------------------------------

    # Poison-heavy opener (unknown Gorgon-zola-like) → Ice Rice first.
    if profile["total_poison"] >= 3:
        pick = _pick(["Ice Rice"] + S_TIER + ["Boom Beans", "Rage Shake"])
        if pick[0]:
            return pick

    # Curse-heavy (Wendibrrr-like) → fast kill beats chained curses.
    if profile["total_curse"] >= 1:
        pick = _pick(S_TIER + ["Boom Beans", "Ice Rice", "Pickle", "Rage Shake"])
        if pick[0]:
            return pick

    # Multi-enemy pack (3+ enemies) → Boom Beans AoE splash is king.
    if profile["enemy_count"] >= 3:
        pick = _pick(["Brotein Bar MAX", "Boom Beans"] + S_TIER
                     + ["Rage Shake", "Heat Meat"])
        if pick[0]:
            return pick

    # Multi-hit boss (big max_hit from multi-hits like 8x2, 12x2) → Pickle
    # + Brrrito shine because they refill/stack through the repeated hits.
    if profile["any_boss"] and profile["max_hit"] >= 20:
        pick = _pick(S_TIER + ["Pickle", "Brrrito Blockerito", "Boom Beans",
                                "Rage Shake", "Heat Meat"])
        if pick[0]:
            return pick

    # Generic big-baddie / boss → damage-first, defensive as fallback.
    if profile["any_boss"] or profile["total_hp"] >= 80:
        pick = _pick(S_TIER + ["Boom Beans", "Rage Shake", "Heat Meat",
                                "Pickle", "Brrrito Blockerito"])
        if pick[0]:
            return pick

    # Generic fallback for anything still dangerous — lead with Tier S.
    pick = _pick(S_TIER + ["Boom Beans", "Rage Shake", "Heat Meat",
                            "Pickle", "Brrrito Blockerito", "Clutch Creme"])
    return pick


def compute_health_or_wealth(current_hp, max_hp, current_gold, current_points):
    """Return (gold_spend, points_spend) for the Health or Wealth event.

    Per Nick: 10 gold or 200 points per HP, up to 30 HP.
    Strategy: heal toward 90% of max HP, prefer gold over points.
    Keep a safety reserve of 30 gold and 3000 points.
    """
    target_hp = int(max_hp * 0.9)
    hp_needed = max(0, min(30, target_hp - current_hp))
    if hp_needed == 0:
        return (0, 0)

    gold_reserve = 30
    points_reserve = 3000

    gold_available = max(0, current_gold - gold_reserve)
    hp_from_gold = min(hp_needed, gold_available // 10)
    gold_spend = hp_from_gold * 10

    remaining = hp_needed - hp_from_gold
    points_spend = 0
    if remaining > 0:
        points_available = max(0, current_points - points_reserve)
        max_hp_from_points = points_available // 200
        hp_from_points = min(remaining, max_hp_from_points)
        points_spend = hp_from_points * 200

    return (gold_spend, points_spend)


async def handle_mystery(dd, logger, session_id, iteration, setup, character_id=None):
    """Dispatch mystery events using the user's standing decision rules.

    Default: take almost every event. Skip only Double Down and Poisoned Veins.
    See memory feedback_mystery_event_decisions.md for the full rule set.
    """
    from dd_agent.sim.upgrade_picker import pick_burn_target

    event = ""
    skippable = True
    if isinstance(setup, dict):
        event = setup.get("event", "")
        skippable = bool(setup.get("skippable", True))

    logger.log(f"  mystery event='{event}' skippable={skippable}")

    # ---- skippable events we SKIP ----
    if event in ("Double Down", "Poisoned Veins"):
        await try_call(
            logger, f"it{iteration:03d}_mystery_exit",
            dd._post("/api/game/mystery/exit", sessionId=session_id)
        )
        return

    # ---- Never Tell Me the Odds: two 3333-risk bets, then exit ----
    # Per user 2026-04-15: always worth two 3333 attempts (1/3 odds each,
    # for a 10,000-point prize). 1/100 and 1/10 tiers are never worth it.
    # With two attempts: 5/9 chance of winning at least once (~56%);
    # expected value is 0 by design but the MEDIAN outcome is positive.
    # Stop after a win (don't give it back).
    if event == "Never Tell Me the Odds":
        for attempt in (1, 2):
            r = await try_call(
                logger, f"it{iteration:03d}_mystery_ntmto_{attempt}",
                dd._post("/api/game/mystery/never-tell-me-the-odds",
                          sessionId=session_id, pickType="3333"),
            )
            # Response shape is unknown at implementation time — inspect
            # for common win indicators. If we see a win, stop.
            if isinstance(r, dict):
                won_this = False
                for k in ("won", "success", "isWin"):
                    if r.get(k) is True:
                        won_this = True; break
                last_action = (r.get("lastAction") or r.get("result") or "")
                if isinstance(last_action, str) and last_action.lower() in ("win", "won"):
                    won_this = True
                if won_this:
                    logger.log(f"  NTMTO: won on attempt {attempt}, stopping")
                    break
                logger.log(f"  NTMTO: attempt {attempt} lost, continuing")
            elif r is None:
                # Call failed — could mean already-resolved or server error.
                # Break to exit instead of retrying blindly.
                logger.log(f"  NTMTO: attempt {attempt} API failed, stopping")
                break
        await try_call(
            logger, f"it{iteration:03d}_mystery_ntmto_exit",
            dd._post("/api/game/mystery/exit", sessionId=session_id),
        )
        return

    # ---- non-skippable events use dedicated endpoint with smart picks ----
    if not skippable:
        # Need fresh character state for decision context
        char = await try_call(
            logger, f"it{iteration:03d}_char_for_nonskip",
            dd.get_character(session_id)
        )
        dices = []
        current_hp = 60
        max_hp = 60
        current_gold = 0
        current_points = 0
        if isinstance(char, dict):
            dices = char.get("dices") or []
            current_hp = char.get("health", 60) or 60
            max_hp = char.get("max_health", 60) or 60
            current_gold = char.get("gold", 0) or 0
            try:
                current_points = int(char.get("points", "0") or 0)
            except Exception:
                current_points = 0

        if event == "Freezer Burn":
            # Prefer burn, but if both burn attempts fail (server gates
            # "minimum 4 sides"), fall through to boost so we never get
            # stuck looping on this mystery. Also: if every die is still
            # at 4 sides (no upgrade we can burn off), go straight to
            # the boost option. Before asking for the boost, discard a
            # food if the backpack is already full — otherwise the boost
            # pickup 400s with "Max 3 boosts" and the run stucks (v23
            # run #3 died this way).
            async def _freezer_burn_take_boost(tag: str):
                existing_foods = [
                    b for b in (char.get("boosts") or [])
                    if isinstance(b, dict)
                ] if isinstance(char, dict) else []
                if len(existing_foods) >= 3:
                    weakest = _pick_weakest_food(existing_foods)
                    if weakest and isinstance(weakest, dict):
                        wid = weakest.get("id") or weakest.get("uuid")
                        wtype = weakest.get("type") or "?"
                        logger.log(
                            f"  Freezer Burn: backpack full, discarding {wtype}"
                        )
                        await try_call(
                            logger,
                            f"it{iteration:03d}_mystery_freezer_burn_discard",
                            dd._post("/api/game/boost/discard",
                                      sessionId=session_id, boostId=wid),
                        )
                return await try_call(
                    logger, f"it{iteration:03d}_mystery_freezer_burn_boost{tag}",
                    dd._post("/api/game/mystery/freezer-burn",
                              sessionId=session_id, pickType="boost"),
                )

            max_sides = max((len(d.get("ability") or []) for d in dices), default=0)
            if max_sides <= 4:
                logger.log(f"  Freezer Burn: all dice at 4 sides, taking boost")
                await _freezer_burn_take_boost("")
                return
            die_id, ability_id, label, _ = pick_burn_target(dices)
            burn_succeeded = False
            if ability_id:
                logger.log(f"  Freezer Burn: burning {label}")
                r = await try_call(
                    logger, f"it{iteration:03d}_mystery_freezer_burn_targeted",
                    dd._post("/api/game/mystery/freezer-burn",
                              sessionId=session_id, pickType="burn",
                              diceId=die_id, abilityId=ability_id)
                )
                if r is not None:
                    burn_succeeded = True
                else:
                    r2 = await try_call(
                        logger, f"it{iteration:03d}_mystery_freezer_burn_plain",
                        dd._post("/api/game/mystery/freezer-burn",
                                  sessionId=session_id, pickType="burn")
                    )
                    if r2 is not None:
                        burn_succeeded = True
            if not burn_succeeded:
                logger.log("  Freezer Burn: burn rejected/unavailable, taking boost")
                await _freezer_burn_take_boost("_fallback")
            return

        if event == "Health Points":
            # Options: 1=-5000pts/+30hp/+3TC, 2=-2000pts/+10hp/+2TC,
            #          3=-750pts/+5hp/+1TC, 4=+100pts (free)
            hp_pct = current_hp / max_hp if max_hp else 1.0
            pts = int(char.get("points", 0) or 0) if isinstance(char, dict) else 0
            if hp_pct < 0.3 and pts >= 5000:
                pick = "1"
                reason = f"HP {hp_pct:.0%} critical, pts={pts}"
            elif hp_pct < 0.6 and pts >= 2000:
                pick = "2"
                reason = f"HP {hp_pct:.0%} low, pts={pts}"
            elif hp_pct < 0.85 and pts >= 750:
                pick = "3"
                reason = f"HP {hp_pct:.0%} mid, pts={pts}"
            else:
                pick = "4"
                reason = f"HP {hp_pct:.0%}, pts={pts}, taking free 100pts"
            logger.log(f"  Health Points: picking option {pick} ({reason})")
            await try_call(
                logger, f"it{iteration:03d}_mystery_hp",
                dd._post("/api/game/mystery/health-points",
                          sessionId=session_id, pickType=pick)
            )
            return

        if event == "Trade Offer":
            # "Cannot trade" is the recurring stuck-cause — we don't know
            # which side of the trade the server wants (or whether the
            # field name is pickType or lootType). Brute-force the
            # variants and fall through to /mystery/exit if all fail so
            # we never loop on this event.
            trinkets = char.get("trinkets") or [] if isinstance(char, dict) else []
            has_junk = any(
                (t.get("label") or t.get("name") or "") in JUNK_TRINKETS
                for t in trinkets if isinstance(t, dict)
            )
            preferred = "trinket" if has_junk else "points"
            alternate = "points" if has_junk else "trinket"
            logger.log(f"  Trade Offer: preferred={preferred} (has_junk={has_junk})")

            attempts = [
                ("pickType", preferred),
                ("pickType", alternate),
                ("lootType", preferred),
                ("lootType", alternate),
            ]
            success = False
            for i, (field, value) in enumerate(attempts):
                body = {"sessionId": session_id, field: value}
                r = await try_call(
                    logger, f"it{iteration:03d}_mystery_trade_{i}",
                    dd._post("/api/game/mystery/trade-offer", **body)
                )
                if r is not None:
                    logger.log(f"    trade succeeded with {field}={value}")
                    success = True
                    break
            if not success:
                logger.log("  Trade Offer: all variants failed, calling /mystery/exit")
                await try_call(
                    logger, f"it{iteration:03d}_mystery_trade_exit",
                    dd._post("/api/game/mystery/exit", sessionId=session_id)
                )
            return

        if event == "Health or Wealth":
            gold_spend, points_spend = compute_health_or_wealth(
                current_hp, max_hp, current_gold, current_points
            )
            logger.log(
                f"  Health or Wealth: spending gold={gold_spend} points={points_spend} "
                f"(HP {current_hp}/{max_hp}, gold={current_gold}, points={current_points})"
            )
            await try_call(
                logger, f"it{iteration:03d}_mystery_hw",
                dd._post("/api/game/mystery/health-or-wealth",
                          sessionId=session_id, gold=gold_spend, points=points_spend)
            )
            return

        # Unknown non-skippable event
        logger.log(f"  [warn] unknown non-skippable '{event}'; trying exit")
        await try_call(
            logger, f"it{iteration:03d}_mystery_exit_blind",
            dd._post("/api/game/mystery/exit", sessionId=session_id)
        )
        return

    # ---- skippable events we TAKE via dedicated endpoint ----
    # Need fresh dice state for events that target a specific side
    char = None
    dices = []
    if character_id:
        char = await try_call(
            logger, f"it{iteration:03d}_char_for_mystery",
            dd.get_character(session_id)
        )
        if isinstance(char, dict):
            dices = char.get("dices") or []

    if event == "Limited Time Offer":
        # +TC if below 5, else +maxHP
        tc = char.get("time_crystal", 5) if isinstance(char, dict) else 5
        pick = "time-crystal" if tc < 5 else "health"
        logger.log(f"  LTO: picking {pick} (current TC={tc})")
        await try_call(
            logger, f"it{iteration:03d}_mystery_lto",
            dd._post("/api/game/mystery/limited-offer",
                      sessionId=session_id, pickType=pick)
        )
        return

    if event == "Too Tempting to Pass":
        # Priority order:
        #   1. If a bub shop is within 2-6 tiles ahead → pick-gold (+150g).
        #      Gold is always useful — shop buys are worth more than the
        #      curse cost.
        #   2. If RUN_GOAL is "stage1-score" AND we're still in early Ch1
        #      (pos <= 14) → pick-points (+10000). Only a high-score run
        #      benefits from the raw point haul; in a stage2-clear run
        #      the curse cost outweighs the points.
        #   3. Otherwise → pick-exit (skip). The curse cost isn't worth
        #      a reward we won't use.
        has_shop_ahead = False
        cur_idx = 0
        chapter = 1
        game_resp = await try_call(
            logger, f"it{iteration:03d}_ttp_game_fetch",
            dd.get_game(character_id) if character_id else dd.get_game("")
        )
        if isinstance(game_resp, dict):
            last = game_resp.get("lastSession") or {}
            progress = last.get("progress") or {}
            cur_idx = progress.get("currentIndex", 0) or 0
            chapter = last.get("chapter") or 1
            mapdata = last.get("mapData") or {}
            active_path = progress.get("activePath", "main") or "main"
            path_nodes = []
            if active_path == "main":
                path_nodes = mapdata.get("mainPathNodes") or []
            elif active_path == "fork1":
                path_nodes = mapdata.get("fork1Nodes") or []
            elif active_path == "fork2":
                path_nodes = mapdata.get("fork2Nodes") or []
            for node in path_nodes:
                if not isinstance(node, dict):
                    continue
                idx = node.get("index", 0)
                if cur_idx + 2 <= idx <= cur_idx + 6 and node.get("type") == "bub":
                    has_shop_ahead = True
                    break

        # Confirmed enum values from server error: pick-gold|pick-points|
        # pick-trinket|pick-sticker|pick-exit
        if has_shop_ahead:
            pick = "pick-gold"
            reason = "shop ahead, taking 150 gold"
        elif RUN_GOAL == "stage1-score" and chapter == 1 and cur_idx <= 14:
            pick = "pick-points"
            reason = f"stage1-score run at Ch1 main[{cur_idx}], taking 10000 points"
        else:
            pick = "pick-exit"
            reason = f"no shop + goal={RUN_GOAL}, skipping (curse cost > reward)"
        logger.log(f"  TTP: {reason}")

        r = await try_call(
            logger, f"it{iteration:03d}_mystery_ttp",
            dd._post("/api/game/mystery/too-temp-to-pass",
                      sessionId=session_id, lootType=pick)
        )
        if r is None and pick != "pick-exit":
            # Fallback to skip if the primary pick errored
            await try_call(
                logger, f"it{iteration:03d}_mystery_ttp_exit",
                dd._post("/api/game/mystery/too-temp-to-pass",
                          sessionId=session_id, lootType="pick-exit")
            )
        return

    if event == "Chronically Tired":
        # Exhaust 1 Block 6 on the mixed die (Die 3 starter) + 1 Block 6 on the
        # defense die (Die 4 starter). Find by composition, not by index.
        actions = _chronically_tired_targets(dices)
        if len(actions) < 2:
            logger.log(f"  Chronically Tired: not enough block targets ({len(actions)}), exiting")
            await try_call(
                logger, f"it{iteration:03d}_mystery_ct_exit",
                dd._post("/api/game/mystery/exit", sessionId=session_id)
            )
            return
        labels = [a.get("_label") for a in actions]
        logger.log(f"  Chronically Tired: exhausting {labels}")
        for a in actions:
            a.pop("_label", None)
        await try_call(
            logger, f"it{iteration:03d}_mystery_ct",
            dd._post("/api/game/mystery/chronically-tired",
                      sessionId=session_id, actions=actions)
        )
        return

    if event in ("Volcanic Spirits", "Volcanic Spirit"):
        # Burn a starter side via pick_burn_target
        die_id, ability_id, label, _ = pick_burn_target(dices)
        if not ability_id:
            logger.log("  Volcanic Spirits: no burn target; exiting")
            await try_call(
                logger, f"it{iteration:03d}_mystery_vs_exit",
                dd._post("/api/game/mystery/exit", sessionId=session_id)
            )
            return
        logger.log(f"  Volcanic Spirits: burning {label}")
        await try_call(
            logger, f"it{iteration:03d}_mystery_vs",
            dd._post("/api/game/mystery/vocalno",
                      sessionId=session_id, diceId=die_id, abilityId=ability_id)
        )
        return

    if event == "Lava of Life":
        # Burn any starter side for +5 HP (or curse for -1000 pts — avoid)
        die_id, ability_id, label, _ = pick_burn_target(dices)
        if not ability_id:
            logger.log("  Lava of Life: no burn target; exiting")
            await try_call(
                logger, f"it{iteration:03d}_mystery_lol_exit",
                dd._post("/api/game/mystery/exit", sessionId=session_id)
            )
            return
        logger.log(f"  Lava of Life: burning {label}")
        await try_call(
            logger, f"it{iteration:03d}_mystery_lol",
            dd._post("/api/game/mystery/lava-of-life",
                      sessionId=session_id, diceId=die_id, abilityId=ability_id)
        )
        return

    if event == "Echo Dagger":
        # Replace an Attack 4 on Die 1 (utility) or Die 3 (mixed). NOT Die 2.
        die_id, ability_id, label = _echo_dagger_target(dices)
        if not ability_id:
            logger.log("  Echo Dagger: no Attack 4 target on Die 1/3; exiting")
            await try_call(
                logger, f"it{iteration:03d}_mystery_ed_exit",
                dd._post("/api/game/mystery/exit", sessionId=session_id)
            )
            return
        logger.log(f"  Echo Dagger: replacing {label}")
        await try_call(
            logger, f"it{iteration:03d}_mystery_ed",
            dd._post("/api/game/mystery/echo-dagger",
                      sessionId=session_id, diceId=die_id, abilityId=ability_id)
        )
        return

    if event == "Yin Yang":
        # Duplicate a boss-tier (Level 3 Boss) side if we have one and can afford it
        die_id, ability_id, label = _yin_yang_target(dices)
        gold = 0
        if ability_id and character_id:
            char_check = await try_call(
                logger, f"it{iteration:03d}_mystery_yy_char",
                dd.get_character(session_id)
            )
            if isinstance(char_check, dict):
                gold = int(char_check.get("gold") or 0)
        if ability_id and gold >= 50:
            logger.log(f"  Yin Yang: duplicating {label} (gold={gold})")
            result = await try_call(
                logger, f"it{iteration:03d}_mystery_yy",
                dd._post("/api/game/mystery/yinyang",
                          sessionId=session_id, pickType="dupe",
                          diceId=die_id, abilityId=ability_id)
            )
            if result is None:
                logger.log(f"  Yin Yang: dupe failed, skipping")
                await try_call(
                    logger, f"it{iteration:03d}_mystery_yy_exit",
                    dd._post("/api/game/mystery/exit", sessionId=session_id)
                )
        else:
            reason = "no boss-tier side" if not ability_id else f"insufficient gold ({gold})"
            logger.log(f"  Yin Yang: {reason}; skipping")
            await try_call(
                logger, f"it{iteration:03d}_mystery_yy_exit",
                dd._post("/api/game/mystery/exit", sessionId=session_id)
            )
        return

    # Default fallback: exit (unknown event, no handler)
    logger.log(f"  [warn] no handler for skippable '{event}'; exiting")
    await try_call(
        logger, f"it{iteration:03d}_mystery_default_exit",
        dd._post("/api/game/mystery/exit", sessionId=session_id)
    )


def _chronically_tired_targets(dices):
    """Find 2 block sides to exhaust: prefer one on a mixed die (Die 3 starter)
    and one on a pure-defense die (Die 4 starter). Composition-based, not index.
    """
    if not dices:
        return []

    # Classify each die by composition
    def _is_block(ab):
        if not isinstance(ab, dict):
            return False
        return bool(ab.get("block")) or "block" in (ab.get("label") or "").lower()

    def _is_attack(ab):
        if not isinstance(ab, dict):
            return False
        return bool(ab.get("damage"))

    def _first_block(die):
        for ab in (die.get("ability") or []):
            if _is_block(ab) and isinstance(ab, dict):
                return ab
        return None

    # Sort dice by their order field so we walk them in player-facing order
    ordered = sorted(dices, key=lambda d: d.get("order", 0))

    # Find a "mixed" die (has both attack and block starter sides)
    mixed_die = None
    defense_die = None
    for d in ordered:
        abilities = d.get("ability") or []
        has_attack = any(_is_attack(a) for a in abilities)
        has_block = any(_is_block(a) for a in abilities)
        block_count = sum(1 for a in abilities if _is_block(a))
        if has_attack and has_block and mixed_die is None:
            mixed_die = d
        elif block_count >= 3 and defense_die is None:
            defense_die = d

    actions = []
    for die in (mixed_die, defense_die):
        if die is None:
            continue
        ab = _first_block(die)
        if ab:
            actions.append({
                "diceId": die.get("id"),
                "abilityId": ab.get("uuid"),
                "_label": f"{ab.get('label')} on die order {die.get('order')}",
            })
    return actions


def _echo_dagger_target(dices):
    """Find an Attack 4 on a die that is NOT the pure-attack die.

    Returns (die_id, ability_uuid, label_for_log) or (None, None, None).
    Prefers a die where the Attack 4 is a duplicate (safer to replace).
    """
    ordered = sorted(dices, key=lambda d: d.get("order", 0))
    # A "pure attack" die has ALL attack sides in its starter
    def _all_attack(die):
        abilities = die.get("ability") or []
        starter_abs = [a for a in abilities if isinstance(a, dict)]
        if not starter_abs:
            return False
        return all(bool(a.get("damage")) for a in starter_abs[:4])

    for die in ordered:
        if _all_attack(die):
            continue  # skip pure attack dies
        for ab in (die.get("ability") or []):
            if isinstance(ab, dict) and ab.get("label") == "Attack 4":
                return (
                    die.get("id"),
                    ab.get("uuid"),
                    f"Attack 4 on die order {die.get('order')}",
                )
    return (None, None, None)


def _yin_yang_target(dices):
    """Find a boss-tier (Level 3 Boss) side to duplicate."""
    for die in (dices or []):
        for ab in (die.get("ability") or []):
            if not isinstance(ab, dict):
                continue
            tags = [t.get("label") for t in (ab.get("tags") or []) if isinstance(t, dict)]
            if "Level 3 Boss" in tags:
                return (
                    die.get("id"),
                    ab.get("uuid"),
                    ab.get("label"),
                )
    return (None, None, None)


async def play_full_run(dd, character_id, out_dir):
    logger = RunLogger(out_dir)
    logger.log(f"starting full run, character_id={character_id}")

    existing = await try_call(logger, "precheck_game", dd.get_game(character_id))
    if isinstance(existing, dict):
        last = existing.get("lastSession") or {}
        progress = last.get("progress") or {}
        in_state = progress.get("inState")
        if in_state and in_state not in ("dead", "lost", "won", "ended", "forfeited", "lose", "win"):
            # Zombie session from a crashed previous run. Force-forfeit it
            # using the leftover session id before starting a fresh one.
            zombie_session_id = last.get("sessionId") or last.get("session_id")
            logger.log(
                f"[recover] active session (inState={in_state}) "
                f"session_id={zombie_session_id}; forfeiting"
            )
            if zombie_session_id:
                # Retry forfeit up to 4 times with escalating backoff so
                # Cloudflare 429s don't leave a zombie.
                for attempt in range(4):
                    r = await try_call(
                        logger, f"precheck_forfeit_{attempt}",
                        dd.forfeit(zombie_session_id),
                    )
                    if r is not None:
                        break
                    await asyncio.sleep(10 * (attempt + 1))
            # Re-check state after forfeit.
            existing2 = await try_call(
                logger, "precheck_game_after_forfeit",
                dd.get_game(character_id),
            )
            if isinstance(existing2, dict):
                last2 = existing2.get("lastSession") or {}
                in_state2 = (last2.get("progress") or {}).get("inState")
                if in_state2 and in_state2 not in (
                    "dead", "lost", "won", "ended", "forfeited", "lose", "win"
                ):
                    logger.log(
                        f"[abort] forfeit failed, still active (inState={in_state2})"
                    )
                    logger.summary["end_reason"] = "active_session_exists"
                    logger.write_summary()
                    return

    session = await try_call(logger, "start_session",
                              dd.start_session(character_id=character_id,
                                                equipped=[], time_crystals=0))
    if not session:
        logger.summary["end_reason"] = "start_session_failed"
        logger.write_summary()
        return

    session_id = None
    if isinstance(session, dict):
        session_id = session.get("sessionId") or session.get("session_id")
    if not session_id:
        logger.log("no session_id returned from start-session")
        logger.summary["end_reason"] = "no_session_id"
        logger.write_summary()
        return

    logger.log(f"session_id={session_id}")
    logger.summary["session_id"] = session_id
    battle_num = 0
    last_state = None
    same_state_count = 0
    end_reason = "iteration_cap"
    # Track whether we've already rerolled the current movement. Resets
    # each time we /proceed (commit to a tile). One reroll per movement
    # max — TC is too scarce to burn on multiple rerolls of the same
    # movement roll.
    already_rerolled_this_move = False

    try:
        for iteration in range(1, MAX_ITERATIONS + 1):
            logger.summary["iterations"] = iteration

            game = await try_call(logger, f"it{iteration:03d}_game",
                                   dd.get_game(character_id))
            char = await try_call(logger, f"it{iteration:03d}_char",
                                   dd.get_character(session_id))

            if not game or not char:
                end_reason = "state_fetch_failed"
                break

            if isinstance(char, dict) and char.get("health", 1) <= 0:
                logger.log("player HP <= 0")
                end_reason = "dead"
                break

            progress = (game.get("lastSession") or {}).get("progress") or {} \
                if isinstance(game, dict) else {}
            in_state = progress.get("inState")
            current_idx = progress.get("currentIndex")
            hp = char.get("health") if isinstance(char, dict) else None
            max_hp = char.get("max_health") if isinstance(char, dict) else None
            pts = char.get("points") if isinstance(char, dict) else None

            logger.log(
                f"[it{iteration}] state={in_state} pos=main[{current_idx}] "
                f"hp={hp}/{max_hp} pts={pts}"
            )

            if in_state in ("dead", "lost", "won", "ended", "forfeited", "lose", "win"):
                end_reason = f"terminal_{in_state}"
                break

            # Checkpoint pending takes priority over every other state —
            # the server blocks all other actions until we answer.
            checkpoint_pending = progress.get("checkpointPending") or 0
            if checkpoint_pending > 0:
                logger.log(f"  checkpoint pending={checkpoint_pending}; selecting 'yes' (continue)")
                await try_call(
                    logger, f"it{iteration:03d}_checkpoint_yes",
                    dd._post(
                        "/api/game/checkpoint",
                        session_id=session_id,
                        selection="yes",
                    )
                )
                continue

            # stuck detector
            state_tuple = (in_state, current_idx)
            if state_tuple == last_state:
                same_state_count += 1
            else:
                same_state_count = 0
            last_state = state_tuple
            if same_state_count >= SAME_STATE_LIMIT:
                logger.log(f"stuck on {state_tuple} for {SAME_STATE_LIMIT}; bailing")
                end_reason = "stuck"
                break

            if in_state in ("baddie", "big-baddie", "boss-baddie", "obelisk"):
                # Reorder dice if needed (e.g. Copy next die stuck on last position).
                # Only reorder in map-adjacent states; not valid during battle.
                # We check just before entering the battle.
                await maybe_reorder_dice(dd, logger, session_id, character_id, iteration)

                battle_num += 1
                last_session = (game.get("lastSession") or {}) if isinstance(game, dict) else {}
                current_chapter = last_session.get("chapter")
                result = await play_battle(
                    dd, logger, session_id, character_id, battle_num,
                    in_state=in_state, pos=current_idx,
                    chapter=current_chapter,
                )
                logger.log(f"  battle result: {result}")
                if result in ("lost", "error"):
                    end_reason = f"battle_{result}"
                    break
            elif in_state == "mystery":
                # Must setup first. Response tells us event name + skippable.
                setup = await try_call(
                    logger, f"it{iteration:03d}_mystery_setup",
                    dd._post("/api/game/mystery/setup-scene",
                              character_id=character_id,
                              session_id=session_id)
                )
                if setup is not None:
                    await handle_mystery(
                        dd, logger, session_id, iteration, setup,
                        character_id=character_id,
                    )
            elif in_state == "campfire":
                await handle_campfire(
                    dd, logger, session_id, character_id, iteration, char
                )
            elif in_state == "bub":
                await handle_bub(dd, logger, session_id, character_id, iteration)
            elif in_state == "loot-die":
                setup = await try_call(
                    logger, f"it{iteration:03d}_loot_die_setup",
                    dd._post("/api/game/loot-dice/setup-scene",
                              character_id=character_id,
                              session_id=session_id)
                )
                await try_call(logger, f"it{iteration:03d}_loot_die_claim",
                                dd._post("/api/game/loot-dice/loot",
                                          sessionId=session_id))
            # (obelisk state handled above, routed through play_battle)
            elif in_state == "map":
                # Always try a plain roll first. If the server tells us a
                # fork choice is required, pick the best fork by biome
                # (Volcano > Ice Cave > anything else > Toxic Swamp).
                r = await try_call(logger, f"it{iteration:03d}_roll",
                                    dd.roll(session_id))
                if r is None:
                    fork_order = await _choose_fork_order(dd, character_id, session_id, logger=logger)
                    logger.log(f"  fork choice order: {fork_order}")
                    for choice in fork_order:
                        r = await try_call(
                            logger, f"it{iteration:03d}_roll_{choice}",
                            dd.roll(session_id, choice=choice),
                        )
                        if r is not None:
                            break
                # Do NOT call proceed in the same iteration — the next
                # state-poll tells us where we landed (rewindable, or already
                # in a non-rewindable event, or fork-pending).
            elif in_state == "rewindable":
                # Consider spending TC to reroll the movement — but only
                # ONCE per movement. After a reroll we'll end up here
                # again and must commit.
                should_reroll = False
                if not already_rerolled_this_move:
                    try:
                        should_reroll = await _should_reroll_movement(
                            dd, character_id, session_id, logger, iteration
                        )
                    except Exception as e:
                        logger.log(f"  reroll decision failed: {type(e).__name__}: {e}")
                if should_reroll:
                    logger.log("  rerolling movement (TC spend, 1/movement)")
                    r = await try_call(
                        logger, f"it{iteration:03d}_reroll",
                        dd.reroll_movement(session_id),
                    )
                    if r is not None:
                        already_rerolled_this_move = True
                    else:
                        # Reroll failed — fall through to proceed.
                        await try_call(
                            logger, f"it{iteration:03d}_proceed_after_failed_reroll",
                            dd.proceed(session_id),
                        )
                        already_rerolled_this_move = False
                else:
                    await try_call(logger, f"it{iteration:03d}_proceed",
                                    dd.proceed(session_id))
                    # Committed to a tile — future rolls may reroll again.
                    already_rerolled_this_move = False
            elif in_state == "checkpoint":
                await try_call(logger, f"it{iteration:03d}_checkpoint_unstake",
                                dd.checkpoint_tournament(session_id, "unstake"))
                end_reason = "checkpoint_unstake"
                break
            else:
                logger.log(f"unknown state: {in_state}; trying proceed")
                r = await try_call(logger, f"it{iteration:03d}_proceed_unknown",
                                    dd.proceed(session_id))
                if r is None:
                    # If even proceed fails, increment stuck counter
                    pass
    finally:
        logger.log("cleanup: forfeit")
        # Retry forfeit on 429 so cloudflare cooldown doesn't leave a
        # zombie session. Critical for batch runs.
        for attempt in range(4):
            r = await try_call(logger, f"final_forfeit_{attempt}", dd.forfeit(session_id))
            if r is not None:
                break
            await asyncio.sleep(10 * (attempt + 1))
        logger.summary["end_reason"] = end_reason
        logger.summary["total_battles"] = battle_num
        logger.write_summary()

        # Final report
        print("\n=== RUN SUMMARY ===")
        print(f"  session_id:    {session_id}")
        print(f"  end reason:    {end_reason}")
        print(f"  iterations:    {logger.summary['iterations']}")
        print(f"  total battles: {battle_num}")
        for b in logger.summary["battles"]:
            _mons = b.get("monsters") or []
            mon = " + ".join(f"{m.get('name')}({m.get('hp')})" for m in _mons)
            result = b.get("result")
            turns = b.get("turns")
            hp_end = b.get("hp_at_end")
            num = b.get("num")
            print(f"    #{num} [{result}] t={turns} hp_end={hp_end}  {mon}")


async def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run the Don't Die bot end-to-end.")
    ap.add_argument("n_runs", type=int, nargs="?", default=1,
                    help="Number of runs to play (serial).")
    ap.add_argument("--character-id", dest="character_id", default=None,
                    help="Override the character UUID (default: /api/characters/solo).")
    args = ap.parse_args()

    dd = DDClient()
    try:
        character_id = args.character_id
        if not character_id:
            chars = await dd._get("/api/characters/solo")
            character_id = chars if isinstance(chars, str) else (chars or {}).get("id")
        if not character_id:
            print("could not determine character_id")
            return
        print(f"character_id: {character_id}")

        for i in range(1, args.n_runs + 1):
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("data/full_runs") / f"{stamp}_r{i}"
            print(f"\n>>> run #{i} logging to {out_dir}")
            await play_full_run(dd, character_id, out_dir)
            if i < args.n_runs:
                await asyncio.sleep(15)  # cool-off between runs (Cloudflare 429)
    finally:
        await dd.close()


if __name__ == "__main__":
    asyncio.run(main())
