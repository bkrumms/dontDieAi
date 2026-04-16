"""Experiment: start a fresh run, play battle 1, and at the pick-ability
step try to commit an ability to a DIFFERENT die than the one pick-dice
was called with. Reports whether the cross-dice pick is accepted and
which die actually received the side.

Usage:
    python scripts/probe_cross_dice_pick.py

Runs through setup → pre-fight → resolve-turn(1) → fetch-loot → pick-general
→ pick-dice(die A) → pick-ability with diceMeta specifying die B. Then
fetches the character and reports which die grew by 1 side.

Forfeits the session at the end — this is a probe, not a run.
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
    try:
        char_id = await dd._get("/api/characters/solo")
        print(f"character_id: {char_id}")

        # Forfeit any leftover session
        try:
            g = await dd._get("/api/game", character_id=char_id)
            if isinstance(g, dict):
                last = g.get("lastSession") or {}
                in_state = (last.get("progress") or {}).get("inState")
                if in_state and in_state not in ("dead", "lost", "won", "ended", "forfeited", "lose", "win"):
                    sid = last.get("sessionId")
                    if sid:
                        print(f"forfeit leftover {sid}")
                        await dd.forfeit(sid)
        except Exception as e:
            print(f"precheck: {e}")

        # Start
        sess = await dd.start_session(character_id=char_id, equipped=[], time_crystals=0)
        session_id = sess.get("sessionId") if isinstance(sess, dict) else None
        if not session_id:
            print("no session_id")
            return
        print(f"session_id: {session_id}")

        # Battle 1 — setup → pre-fight → start-scene → resolve-turn
        await dd._post("/api/game/battle/setup-scene", session_id=session_id)
        await dd.battle_prefight(char_id, session_id)
        await dd.battle_start(session_id)
        # Resolve one turn (battle 1 is usually 1-turn win vs Baby Scarebug)
        r = await dd.battle_resolve(session_id)
        print(f"  resolve-turn ok")

        # to-loot → fetch-loot → pick-general
        await dd._post("/api/game/battle/to-loot", sessionId=session_id)
        loot = await dd.fetch_loot(session_id)
        required = loot.get("requiredSteps") if isinstance(loot, dict) else []
        print(f"required_steps: {required}")

        if "pick-general" in (required or []):
            await dd._post("/api/game/battle/loot",
                           sessionId=session_id, lootType="pick-general")

        # Get pre-pick dice state
        char_pre = await dd.get_character(session_id)
        dices = char_pre.get("dices") or []
        print("\nPRE-PICK dice:")
        for d in sorted(dices, key=lambda x: x.get("order", 0)):
            print(f"  D{d.get('order')} id={d.get('id')}: "
                  f"{len(d.get('ability') or [])} sides")

        if len(dices) < 4:
            print("not enough dice")
            await dd.forfeit(session_id)
            return

        ordered = sorted(dices, key=lambda x: x.get("order", 0))
        die_a = ordered[0]  # call pick-dice with die A (D1)
        die_b = ordered[1]  # try to commit to die B (D2)

        print(f"\nCalling pick-dice with die A = D{die_a.get('order')}")
        pick_resp = await dd._post(
            "/api/game/battle/pick-dice",
            sessionId=session_id,
            diceMeta={"diceId": die_a.get("id"), "phase": 1},
        )
        abilities = pick_resp.get("abilities") if isinstance(pick_resp, dict) else []
        print(f"  abilities returned: {len(abilities)}")
        for a in abilities:
            print(f"    - {a.get('label')}")

        if not abilities:
            print("no abilities returned")
            await dd.forfeit(session_id)
            return

        # ---- EXPERIMENT 2: call pick-dice AGAIN with die B, see if abilities match ----
        print(f"\nEXPERIMENT A: calling pick-dice AGAIN with die B (D{die_b.get('order')})")
        try:
            pick_b = await dd._post(
                "/api/game/battle/pick-dice",
                sessionId=session_id,
                diceMeta={"diceId": die_b.get("id"), "phase": 1},
            )
            if isinstance(pick_b, dict):
                ab_b = pick_b.get("abilities") or []
                labels_b = [a.get("label") for a in ab_b if isinstance(a, dict)]
                labels_a = [a.get("label") for a in abilities if isinstance(a, dict)]
                print(f"  die A abilities: {labels_a}")
                print(f"  die B abilities: {labels_b}")
                if labels_a == labels_b:
                    print("  => IDENTICAL (abilities are battle-determined, not die-dependent)")
                else:
                    print("  => DIFFERENT (abilities depend on which die you call pick-dice with)")
        except Exception as e:
            print(f"  pick-dice(B) failed: {e}")

        chosen = abilities[0]
        ability_id = chosen.get("uuid") or chosen.get("id")
        print(f"\nChosen ability: {chosen.get('label')} (id={ability_id})")

        # ---- EXPERIMENT 1: pick-ability with diceMeta specifying DIE B ----
        print(f"\nEXPERIMENT B: calling pick-ability with diceMeta = die B (D{die_b.get('order')})")
        try:
            r = await dd._post(
                "/api/game/battle/loot",
                sessionId=session_id,
                lootType="pick-ability",
                diceMeta={"abilityId": ability_id, "phase": 1, "diceId": die_b.get("id")},
            )
            print(f"  response: {type(r).__name__}")
            if isinstance(r, dict):
                print(f"  body sample: {json.dumps(r)[:200]}")
        except Exception as e:
            print(f"  ERROR: {e}")

        # Check which die grew
        char_post = await dd.get_character(session_id)
        dices_post = char_post.get("dices") or []
        print("\nPOST-PICK dice:")
        for d in sorted(dices_post, key=lambda x: x.get("order", 0)):
            print(f"  D{d.get('order')}: {len(d.get('ability') or [])} sides")

        print("\n=== RESULT ===")
        for before, after in zip(
            sorted(dices, key=lambda x: x.get("order", 0)),
            sorted(dices_post, key=lambda x: x.get("order", 0)),
        ):
            old = len(before.get("ability") or [])
            new = len(after.get("ability") or [])
            delta = new - old
            marker = ""
            if after.get("order") == die_a.get("order"):
                marker = " (pick-dice target)"
            if after.get("order") == die_b.get("order"):
                marker += " (experiment target)"
            print(f"  D{after.get('order')}: {old} -> {new} ({'+' if delta>=0 else ''}{delta}){marker}")

    finally:
        try:
            await dd.forfeit(session_id)
        except Exception:
            pass
        await dd.close()


if __name__ == "__main__":
    asyncio.run(main())
