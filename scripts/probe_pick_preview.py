"""Test whether pick-dice can be called without a diceId to preview
abilities before committing to a die.

Several variants to test:
  1. pick-dice with diceMeta={} (no diceId)
  2. pick-dice with diceMeta={phase: 1}
  3. pick-dice with diceMeta={diceId: None, phase: 1}
  4. pick-dice with no diceMeta at all
  5. (baseline) pick-dice with diceMeta={diceId: X, phase: 1}
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dd_agent.dd_client import DDClient


async def main():
    dd = DDClient()
    session_id = None
    try:
        char_id = await dd._get("/api/characters/solo")
        try:
            g = await dd._get("/api/game", character_id=char_id)
            if isinstance(g, dict):
                last = g.get("lastSession") or {}
                sid = last.get("sessionId")
                in_state = (last.get("progress") or {}).get("inState")
                if sid and in_state and in_state not in ("dead", "lost", "won", "ended", "forfeited", "lose", "win"):
                    await dd.forfeit(sid)
        except Exception:
            pass
        sess = await dd.start_session(character_id=char_id, equipped=[], time_crystals=0)
        session_id = sess.get("sessionId")
        print(f"session: {session_id}")

        # Play battle 1 to loot phase
        await dd._post("/api/game/battle/setup-scene", session_id=session_id)
        await dd.battle_prefight(char_id, session_id)
        await dd.battle_start(session_id)
        await dd.battle_resolve(session_id)
        await dd._post("/api/game/battle/to-loot", sessionId=session_id)
        await dd.fetch_loot(session_id)
        await dd._post("/api/game/battle/loot",
                       sessionId=session_id, lootType="pick-general")

        # Get dice for later
        char = await dd.get_character(session_id)
        dices = sorted(char.get("dices") or [], key=lambda d: d.get("order", 0))
        die1_id = dices[0].get("id")
        die2_id = dices[1].get("id")

        variants = [
            ("v1 diceMeta={}", {}),
            ("v2 diceMeta={phase:1}", {"phase": 1}),
            ("v3 diceMeta={diceId:None, phase:1}", {"diceId": None, "phase": 1}),
            ("v4 no diceMeta (omit)", None),
        ]

        print("\n=== Probing preview variants (should NOT commit a die) ===\n")
        for label, meta in variants:
            print(f"--- {label} ---")
            body = {"sessionId": session_id}
            if meta is not None:
                body["diceMeta"] = meta
            try:
                r = await dd._post("/api/game/battle/pick-dice", **body)
                if isinstance(r, dict):
                    ab = r.get("abilities") or []
                    print(f"  SUCCESS — {len(ab)} abilities returned")
                    for a in ab:
                        print(f"    - {a.get('label')}")
                else:
                    print(f"  unexpected: {r}")
            except Exception as e:
                msg = str(e)[:200]
                print(f"  ERROR: {msg}")
            print()

        # After any preview attempts, commit to D1 for real
        print("--- baseline: commit pick-dice with die 1 id ---")
        r = await dd._post(
            "/api/game/battle/pick-dice",
            sessionId=session_id,
            diceMeta={"diceId": die1_id, "phase": 1},
        )
        if isinstance(r, dict):
            ab = r.get("abilities") or []
            print(f"  committed, {len(ab)} abilities:")
            for a in ab:
                print(f"    - {a.get('label')}")
    finally:
        if session_id:
            try:
                await dd.forfeit(session_id)
            except Exception:
                pass
        await dd.close()


if __name__ == "__main__":
    asyncio.run(main())
