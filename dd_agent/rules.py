"""Rules engine — the deterministic brain.

Every handler takes game state and returns a Decision describing the next
action the agent should take. Stubs here pick safe defaults so the loop runs;
real rules go in as we iterate.

Design notes:
- Rules are pure functions of state. No I/O.
- Decisions include a `rationale` so the narrator can turn them into player text.
- Decisions can set `needs_player=True` to force a prompt via the bot.
- Low `confidence` can later trigger LLM escalation.
"""
from dataclasses import dataclass, field


@dataclass
class Decision:
    action: str                     # e.g. "roll", "proceed", "battle_resolve"
    args: dict = field(default_factory=dict)
    rationale: str = ""
    confidence: float = 1.0
    needs_player: bool = False


def decide(state: dict) -> Decision:
    """Top-level dispatch based on the player's current in-game state."""
    in_state = (state or {}).get("inState") or "unknown"

    if in_state in ("map", "movement", "unknown"):
        return _decide_map(state)
    if in_state.startswith("battle"):
        return _decide_battle(state)
    if in_state == "mystery":
        return _decide_mystery(state)
    if in_state == "campfire":
        return _decide_campfire(state)
    if in_state in ("shop", "bub"):
        return _decide_shop(state)
    if in_state == "checkpoint":
        return _decide_checkpoint(state)
    if in_state == "loot":
        return _decide_loot(state)

    return Decision(
        action="proceed",
        rationale=f"unknown state '{in_state}', trying to proceed",
        confidence=0.2,
    )


# ---------- handler stubs ----------

def _decide_map(state: dict) -> Decision:
    # TODO: fork selection (biome preference), reroll logic (TC budget vs EV of
    # current space), skip-friendly spaces, avoid-boss until healed.
    return Decision(action="roll", rationale="rolling the map die")


def _decide_battle(state: dict) -> Decision:
    # TODO: reorder dice, pre-fight food pick vs threat level, rewind if we
    # lost the turn, commit to loot when battle is over.
    return Decision(action="battle_resolve", rationale="resolving turn")


def _decide_mystery(state: dict) -> Decision:
    # TODO: per-event EV tables. Many events are high-variance so confidence
    # stays low until we codify each one.
    return Decision(
        action="proceed",
        rationale="skipping mystery event (stub)",
        confidence=0.3,
    )


def _decide_campfire(state: dict) -> Decision:
    # TODO: heal vs burn vs upgrade based on HP, dice consistency, chapter.
    return Decision(
        action="campfire_exit",
        rationale="leaving campfire (stub)",
        confidence=0.3,
    )


def _decide_shop(state: dict) -> Decision:
    # TODO: gold vs health spending, burn-for-consistency, buy trinkets/food
    # that patch current weaknesses.
    return Decision(
        action="shop_exit",
        rationale="skipping shop (stub)",
        confidence=0.3,
    )


def _decide_checkpoint(state: dict) -> Decision:
    """Checkpoint is the highest-stakes decision — always prompt the player."""
    hp = (state or {}).get("health") or 0
    max_hp = (state or {}).get("maxHealth") or 1
    pct = hp / max_hp if max_hp else 0.0
    tc = (state or {}).get("timeCrystal") or 0

    if pct < 0.35 or tc == 0:
        return Decision(
            action="checkpoint",
            args={"selection": "unstake"},
            rationale=f"HP {hp}/{max_hp} ({pct:.0%}) + {tc} TC — too risky to push",
            needs_player=True,
            confidence=0.8,
        )
    return Decision(
        action="checkpoint",
        args={"selection": "continue"},
        rationale=f"HP {hp}/{max_hp} ({pct:.0%}) + {tc} TC — safe to continue",
        needs_player=True,
        confidence=0.7,
    )


def _decide_loot(state: dict) -> Decision:
    # TODO: side EV, burn targets, trinket priority.
    return Decision(
        action="battle_to_loot",
        rationale="committing to loot (stub)",
        confidence=0.3,
    )
