"""Experiment: determine whether pick-dice returns die-specific ability
options, and whether it can be called multiple times without committing.

Usage:
    python scripts/probe_pick_dice.py <session_id>

Must be called when a session is in the loot phase with pick-dice as the
next required step. The script will:
  1. Call pick-dice with die 1 → record the 3 abilities returned
  2. Try to call pick-dice with die 2 → record response
  3. If both succeed, compare ability sets and print findings

DOES NOT call pick-ability, so the loot phase is left in an intermediate
state. You'll need to commit the loot manually afterward.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dd_agent.dd_client import DDClient


async def main():
    if len(sys.argv) < 2:
        print("usage: probe_pick_dice.py <session_id>")
        return
    session_id = sys.argv[1]
    dd = DDClient()

    char = await dd.get_character(session_id)
    dices = char.get("dices") or []
    if len(dices) < 2:
        print("need at least 2 dice")
        return

    for i, d in enumerate(dices[:4]):
        die_id = d.get("id")
        print(f"\n=== Calling pick-dice with die #{i+1} (id={die_id}) ===")
        try:
            r = await dd._post(
                "/api/game/battle/pick-dice",
                sessionId=session_id,
                diceMeta={"diceId": die_id, "phase": 1},
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        if isinstance(r, dict):
            ab = r.get("abilities") or []
            print(f"  abilities: {[a.get('label') for a in ab if isinstance(a, dict)]}")
        else:
            print(f"  unexpected response: {type(r).__name__}")

    await dd.close()


if __name__ == "__main__":
    asyncio.run(main())
