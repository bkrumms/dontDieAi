"""DD session/character/game snapshot tool.

Usage:
  python scripts/dd_fetch.py session <session_id>
  python scripts/dd_fetch.py char    <session_id>
  python scripts/dd_fetch.py dice    <session_id>   # pretty-print dice layout
  python scripts/dd_fetch.py all     <session_id>   # fetch everything to data/sessions/<id>/

Always writes JSON under data/sessions/<session_id>/ so subsequent scripts
can read from disk without hitting the API again.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dd_agent.dd_client import DDClient  # noqa: E402
OUT_ROOT = REPO / "data" / "sessions"


def _outdir(session_id: str) -> Path:
    p = OUT_ROOT / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str))
    print(f"  wrote {path.relative_to(REPO)}")


async def fetch_session_debug(dd: DDClient, session_id: str) -> dict:
    return await dd._get("/api/game/session-debug", session_id=session_id)


async def fetch_character(dd: DDClient, session_id: str) -> dict:
    return await dd.get_character(session_id)


def print_dice(char: dict) -> None:
    if not isinstance(char, dict):
        print("(no character)")
        return
    print(f"HP {char.get('health')}/{char.get('max_health')}  "
          f"gold={char.get('gold')}  points={char.get('points')}  "
          f"tc={char.get('time_crystal')}")
    trinkets = char.get("trinkets") or []
    if trinkets:
        print("trinkets:", ", ".join(t.get("label", "?") for t in trinkets))
    boosts = char.get("boosts") or []
    if boosts:
        print("food:", ", ".join(b.get("label", "?") for b in boosts))
    print()
    for d in sorted(char.get("dices") or [], key=lambda x: x.get("order", 0)):
        abs_ = d.get("ability") or []
        print(f"Die order={d.get('order')}  ({len(abs_)} sides)")
        for a in abs_:
            tags = [t.get("label") for t in (a.get("tags") or []) if isinstance(t, dict)]
            tag_str = f"  [{','.join(tags)}]" if tags else ""
            print(f"  - {a.get('label')}{tag_str}")
        print()


async def cmd_session(session_id: str) -> None:
    dd = DDClient()
    debug = await fetch_session_debug(dd, session_id)
    _dump(_outdir(session_id) / "session_debug.json", debug)


async def cmd_char(session_id: str) -> None:
    dd = DDClient()
    char = await fetch_character(dd, session_id)
    _dump(_outdir(session_id) / "character.json", char)


async def cmd_dice(session_id: str) -> None:
    dd = DDClient()
    char = await fetch_character(dd, session_id)
    _dump(_outdir(session_id) / "character.json", char)
    print()
    print_dice(char)


async def cmd_all(session_id: str) -> None:
    dd = DDClient()
    debug = await fetch_session_debug(dd, session_id)
    _dump(_outdir(session_id) / "session_debug.json", debug)
    char = await fetch_character(dd, session_id)
    _dump(_outdir(session_id) / "character.json", char)
    print()
    print_dice(char)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["session", "char", "dice", "all"])
    ap.add_argument("session_id")
    args = ap.parse_args()

    fn = {
        "session": cmd_session,
        "char": cmd_char,
        "dice": cmd_dice,
        "all": cmd_all,
    }[args.cmd]
    asyncio.run(fn(args.session_id))


if __name__ == "__main__":
    main()
