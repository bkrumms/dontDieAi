"""Passive watcher for a live Don't Die run.

Usage:
    python scripts/watch_run.py <session_id> [poll_interval_seconds]

Polls both:
  - GET /api/character?sessionId=<session_id>      (player state)
  - GET /api/game?character_id=<character_id>      (movement / map state)

and merges them into a single flat dict for the Observer to diff.

Writes:
    data/runs/<session_id>/states.jsonl
    data/runs/<session_id>/events.md
    data/runs/<session_id>/map.json         (written once on first poll)
"""
import asyncio
import json
import sys
from pathlib import Path

# Windows cmd defaults to cp1252; force UTF-8 so event strings with unicode
# (arrows, em-dashes, etc.) print without UnicodeEncodeError.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dd_agent.dd_client import DDClient  # noqa: E402
from dd_agent.observer import Observer  # noqa: E402


def _merge(char: dict | None, game: dict | None) -> dict:
    """Flatten the two responses into the shape Observer expects."""
    merged: dict = {}
    c = char or {}
    merged.update({
        "health": c.get("health"),
        "max_health": c.get("max_health"),
        "gold": c.get("gold"),
        "points": c.get("points"),
        "time_crystal": c.get("time_crystal"),
        "dices": c.get("dices") or [],
        "boosts": c.get("boosts") or [],
        "trinkets": c.get("trinkets") or [],
        "characterId": c.get("characterId"),
        "lootMul": c.get("lootMul"),
        "lootPoints": c.get("lootPoints"),
        "nftType": c.get("nftType"),
        "characterName": c.get("characterName"),
        "usedBottleFairy": c.get("usedBottleFairy"),
    })

    g = game or {}
    last = (g.get("lastSession") or {}) if isinstance(g, dict) else {}
    progress = (last.get("progress") or {}) if isinstance(last, dict) else {}
    merged.update({
        "inState": progress.get("inState"),
        "activePath": progress.get("activePath"),
        "currentIndex": progress.get("currentIndex"),
        "rolledSteps": progress.get("rolledSteps"),
        "pendingChoice": progress.get("pendingChoice"),
        "checkpointPending": progress.get("checkpointPending"),
        "isFtue": progress.get("isFtue"),
        "chapter": last.get("chapter"),
        "nextRerollCost": g.get("nextRerollCost"),
        "upcoming_boss": g.get("upcoming_boss"),
        "isTournament": g.get("isTournament"),
    })
    return merged


async def watch(session_id: str, poll_interval: float = 1.5):
    out_dir = Path("data/runs") / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    states_path = out_dir / "states.jsonl"
    events_path = out_dir / "events.md"
    map_path = out_dir / "map.json"

    dd = DDClient()
    observer = Observer(session_id=session_id, states_path=states_path, events_path=events_path)

    print(f"Watching session {session_id}")
    print(f"  poll interval: {poll_interval}s")
    print(f"  log dir:       {out_dir}")
    print("Press Ctrl+C to stop.\n")

    character_id: str | None = None
    map_saved = False
    consecutive_errors = 0

    try:
        while not observer.is_terminal():
            try:
                char = await dd.get_character(session_id)
                if character_id is None and isinstance(char, dict):
                    character_id = char.get("characterId")

                game = None
                if character_id:
                    try:
                        game = await dd.get_game(character_id)
                    except Exception as e:
                        print(f"[game-poll warn] {e}")

                if game and not map_saved:
                    last = (game.get("lastSession") or {})
                    if isinstance(last, dict) and last.get("mapData"):
                        map_path.write_text(
                            json.dumps(last["mapData"], indent=2),
                            encoding="utf-8",
                        )
                        print(f"[map saved → {map_path}]")
                        map_saved = True

                merged = _merge(char, game)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                msg = str(e)
                hint = ""
                if "401" in msg or "403" in msg:
                    hint = "  (auth — check DD_AUTH_TOKEN in .env; raw token, no Bearer)"
                elif "429" in msg:
                    hint = "  (Cloudflare rate limit — raise poll_interval)"
                print(f"[poll error #{consecutive_errors}] {msg}{hint}")
                if consecutive_errors >= 5:
                    print("5 consecutive errors, giving up.")
                    break
                await asyncio.sleep(poll_interval * 2)
                continue

            events = observer.record(merged)
            for event in events:
                print(event)

            await asyncio.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[stopping — Ctrl+C]")
    finally:
        observer.close()
        await dd.close()
        print()
        print(f"Polls recorded: {observer.poll_count}")
        print(f"Events logged:  {observer.event_count}")
        print(f"Raw states:     {states_path}")
        print(f"Event timeline: {events_path}")
        if map_saved:
            print(f"Map snapshot:   {map_path}")


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/watch_run.py <session_id> [poll_interval_seconds]")
        sys.exit(1)
    session_id = sys.argv[1]
    poll_interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    asyncio.run(watch(session_id, poll_interval))


if __name__ == "__main__":
    main()
