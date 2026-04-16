"""API-driven run player.

Starts a practice session on the DD dev build, captures the first battle's
setup-scene response (which contains real monster data with HP, abilities,
and patterns), logs everything to disk, then forfeits the session cleanly.

This is how we build up a library of real fight compositions to compare
against the simulator and patch any pattern discrepancies.

Usage:
    python scripts/play_run.py            # one capture
    python scripts/play_run.py 3          # capture 3 runs

SAFETY:
- Refuses to run if an active session already exists on the practice
  character (to avoid stealing a human run).
- Always forfeits after capture to minimize credit spend.
- Logs every raw request/response to data/battles/<session_id>/.
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

from dd_agent.dd_client import DDClient


def _save(out_dir: Path, name: str, payload):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


async def _try(label, coro):
    try:
        r = await coro
        return {"ok": True, "data": r}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def capture_one_run(dd: DDClient, character_id: str, run_num: int) -> dict:
    """Start a session, capture first battle, forfeit. Returns summary."""
    print(f"\n--- run #{run_num} ---")
    summary = {"run_num": run_num, "character_id": character_id}

    # Step 1: check for active session
    existing = await _try("pre-check", dd.get_game(character_id))
    if existing["ok"] and isinstance(existing["data"], dict):
        last = existing["data"].get("lastSession") or {}
        progress = last.get("progress") or {}
        in_state = progress.get("inState")
        if in_state and in_state not in ("dead", "ended", "forfeited", "won", "lost", "lose"):
            print(f"  [abort] active session detected (inState={in_state}); refusing to start a new run")
            summary["aborted"] = "active_session_exists"
            summary["active_session_id"] = last.get("sessionId")
            return summary
    print("  pre-check ok, no active session")

    # Step 2: start new practice session
    start = await _try(
        "start-session",
        dd.start_session(character_id=character_id, equipped=[], time_crystals=0),
    )
    if not start["ok"]:
        print(f"  [error] start-session failed: {start['error']}")
        summary["error"] = start["error"]
        return summary

    session_data = start["data"]
    session_id = (
        session_data.get("sessionId")
        or session_data.get("session_id")
        or (session_data.get("data") or {}).get("sessionId")
    )
    if not session_id:
        print(f"  [error] no session id in start response: {session_data}")
        summary["error"] = "no_session_id"
        return summary

    out_dir = Path("data/battles") / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    _save(out_dir, "01_start_session", session_data)
    summary["session_id"] = session_id
    print(f"  session {session_id}")
    print(f"  logging to {out_dir}")

    # Step 3: fetch initial character + game state
    char = await _try("character", dd.get_character(session_id))
    if char["ok"]:
        _save(out_dir, "02_character", char["data"])
    game = await _try("game", dd.get_game(character_id))
    if game["ok"]:
        _save(out_dir, "03_game", game["data"])
        # Extract progress state for logging
        last = (game["data"] or {}).get("lastSession") or {}
        progress = last.get("progress") or {}
        print(f"  initial inState={progress.get('inState')} path={progress.get('activePath')}[{progress.get('currentIndex')}]")

    # Step 4: attempt battle setup-scene
    print("  attempting battle/setup-scene")
    setup = await _try(
        "setup-scene",
        dd.battle_setup(session_id),
    )
    if setup["ok"]:
        _save(out_dir, "04_battle_setup_scene", setup["data"])
        data = setup["data"]
        # Real monster objects live at state.monsters (full dicts).
        # Top-level `monsters` is only a list of name strings.
        monsters_full = []
        if isinstance(data, dict):
            state = data.get("state") or {}
            if isinstance(state, dict):
                m = state.get("monsters") or state.get("baddies") or []
                if isinstance(m, list):
                    monsters_full = [x for x in m if isinstance(x, dict)]

        if monsters_full:
            summary["monsters"] = []
            for m in monsters_full:
                tags = [t.get("label") for t in (m.get("tags") or []) if isinstance(t, dict)]
                entry = {
                    "name": m.get("name"),
                    "hp": m.get("health"),
                    "maxHp": m.get("maxHealth"),
                    "tags": tags,
                    "ability_count": len(m.get("ability") or []),
                    "abilityCycleFromIndex": m.get("abilityCycleFromIndex"),
                }
                summary["monsters"].append(entry)
            names = [f"{e['name']}({e['hp']})" for e in summary["monsters"]]
            print(f"  CAPTURED: {' + '.join(names)}")
        else:
            names_only = data.get("monsters") if isinstance(data, dict) else None
            print(f"  [note] no full monster dicts found; top-level monsters = {names_only}")
            summary["monsters"] = names_only
    else:
        print(f"  [error] setup-scene failed: {setup['error']}")
        summary["setup_scene_error"] = setup["error"]

    # Step 5: try pre-fight (optional, to see more state)
    prefight = await _try(
        "pre-fight",
        dd.battle_prefight(character_id, session_id),
    )
    if prefight["ok"]:
        _save(out_dir, "05_battle_prefight", prefight["data"])

    # Step 6: forfeit (cleanup)
    print("  forfeiting session")
    forfeit = await _try("forfeit", dd.forfeit(session_id))
    if forfeit["ok"]:
        _save(out_dir, "99_forfeit", forfeit["data"])
    else:
        print(f"  [warn] forfeit failed: {forfeit['error']}")
        summary["forfeit_error"] = forfeit["error"]

    return summary


async def main():
    n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    dd = DDClient()
    all_summaries = []
    try:
        # Get the practice character id
        chars_resp = await _try("characters/solo", dd._get("/api/characters/solo"))
        if chars_resp["ok"]:
            print(f"characters/solo: {chars_resp['data']}")

        # /api/characters/solo may return just a UUID or a wrapped object
        raw = chars_resp["data"]
        if isinstance(raw, str):
            character_id = raw
        elif isinstance(raw, dict):
            character_id = (
                raw.get("characterId")
                or raw.get("id")
                or raw.get("uuid")
                or raw.get("character_id")
            )
        else:
            character_id = None

        if not character_id:
            # Fall back to /api/characters and pick the first
            chars_list = await _try("characters", dd._get("/api/characters"))
            if chars_list["ok"] and chars_list["data"]:
                d = chars_list["data"]
                if isinstance(d, list) and d:
                    character_id = d[0].get("id") or d[0].get("characterId") or d[0].get("uuid")
                elif isinstance(d, dict):
                    # maybe a {characters: [...]} wrapper
                    lst = d.get("characters") or d.get("data") or []
                    if lst:
                        character_id = lst[0].get("id") or lst[0].get("characterId")

        if not character_id:
            print("[fatal] could not determine character_id; inspect raw responses above")
            return

        print(f"character_id: {character_id}")

        # Run captures
        for i in range(1, n_runs + 1):
            summary = await capture_one_run(dd, character_id, i)
            all_summaries.append(summary)
            # Small gap between runs to avoid Cloudflare rate limit
            if i < n_runs:
                await asyncio.sleep(3)
    finally:
        await dd.close()

    # Summary
    print("\n=== SUMMARY ===")
    for s in all_summaries:
        print(json.dumps(s, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
