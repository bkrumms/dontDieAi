"""Run the reorder algorithm against a saved session and print the decision.

Usage:
  python scripts/test_reorder.py <session_id>

Expects data/sessions/<session_id>/character.json to exist — run
`python scripts/dd_fetch.py char <session_id>` first if it doesn't.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.play_full_run import (  # noqa: E402
    _die_order_signals,
    _compute_optimal_order,
    _needs_reorder,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session_id")
    args = ap.parse_args()

    char_path = REPO / "data" / "sessions" / args.session_id / "character.json"
    if not char_path.exists():
        print(f"ERROR: {char_path} not found. Run dd_fetch.py char first.")
        sys.exit(1)

    char = json.loads(char_path.read_text())
    dices = char.get("dices") or []
    if not dices:
        print("no dice in character")
        return

    print("=== Current order ===")
    for d in sorted(dices, key=lambda x: x.get("order", 0)):
        sigs = _die_order_signals(d)
        active = [k for k, v in sigs.items() if v]
        labels = [a.get("label") for a in (d.get("ability") or [])]
        print(f"  order={d.get('order')}  signals={active}")
        for l in labels[:6]:
            print(f"    - {l}")
        if len(labels) > 6:
            print(f"    ... (+{len(labels)-6} more)")

    print()
    print("=== Optimal order ===")
    opt = _compute_optimal_order(dices)
    for i, d in enumerate(opt):
        print(f"  pos {i+1}: was order={d.get('order')}")

    needs, new_order = _needs_reorder(dices)
    print()
    print(f"needs_reorder: {needs}")
    if needs:
        print("payload:", json.dumps(new_order, indent=2))


if __name__ == "__main__":
    main()
