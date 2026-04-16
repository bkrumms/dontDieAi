"""Score a list of offered sides with the picker and print the ranking.

Usage:
  # Score offered sides stored in a run dir (from a failed pick-ability step)
  python scripts/score_sides.py run <run_dir> <battle_num>

  # Score a die's current abilities (as if each were being re-offered)
  python scripts/score_sides.py die <session_id> <die_order>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dd_agent.sim.upgrade_picker import pick_best_side  # noqa: E402


def _load_offered_from_run(run_dir: Path, battle_num: int):
    """Pull the offered sides for battle N from its pick_dice JSON."""
    pattern = f"*b{battle_num:02d}_loot_pick_dice*.json"
    matches = sorted(run_dir.glob(pattern))
    if not matches:
        print(f"no pick_dice JSON for battle {battle_num} in {run_dir}")
        sys.exit(1)
    resp = json.loads(matches[-1].read_text())
    offered = resp.get("abilities") or resp.get("options") or []
    die_id = resp.get("diceId") or resp.get("dice_id")
    return offered, die_id


def _load_char(session_id: str) -> dict:
    path = REPO / "data" / "sessions" / session_id / "character.json"
    if not path.exists():
        print(f"ERROR: {path} not found. Run dd_fetch.py char first.")
        sys.exit(1)
    return json.loads(path.read_text())


def _die_index_by_order(dices, order):
    ordered = sorted(dices, key=lambda d: d.get("order", 0))
    for i, d in enumerate(ordered):
        if d.get("order") == order:
            return i, d
    return None, None


def _print_ranking(scored, header):
    print(header)
    for row in scored:
        idx, label, score, category, tier, combos = row
        combo_str = f"  combos={combos}" if combos else ""
        print(f"  [{idx}] {label}  ({tier}/{category})  score={score:.1f}{combo_str}")


def cmd_run(run_dir: str, battle_num: int):
    rd = Path(run_dir).resolve()
    offered, die_id = _load_offered_from_run(rd, battle_num)
    print(f"Battle {battle_num}: {len(offered)} sides offered, dieId={die_id}")
    for di in range(4):
        _, _, scored = pick_best_side(di, offered)
        _print_ranking(scored, f"\n--- As if on die index {di} ---")


def cmd_die(session_id: str, die_order: int):
    char = _load_char(session_id)
    dices = char.get("dices") or []
    di, die = _die_index_by_order(dices, die_order)
    if die is None:
        print(f"no die with order={die_order}")
        sys.exit(1)
    sides = die.get("ability") or []
    print(f"Die order={die_order} idx={di}  sides={len(sides)}")
    _, _, scored = pick_best_side(di, sides, current_die_side_count=len(sides),
                                  target_die=die, all_dice=dices)
    _print_ranking(scored, "\n--- Current die sides ---")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("run_dir")
    p_run.add_argument("battle_num", type=int)
    p_die = sub.add_parser("die")
    p_die.add_argument("session_id")
    p_die.add_argument("die_order", type=int)
    args = ap.parse_args()

    if args.cmd == "run":
        cmd_run(args.run_dir, args.battle_num)
    else:
        cmd_die(args.session_id, args.die_order)


if __name__ == "__main__":
    main()
