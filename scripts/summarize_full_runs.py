"""Summarize a batch of play_full_run.py outputs.

Each run dir under data/full_runs/ contains a `_summary.json` when the
run completed (written by play_full_run.py at end). Runs that crashed
mid-execution have no summary file and are reported as partial.

Usage:
    python scripts/summarize_full_runs.py                       # all dirs
    python scripts/summarize_full_runs.py --since 20260423_20   # prefix filter
    python scripts/summarize_full_runs.py --dir data/full_runs  # alt root
    python scripts/summarize_full_runs.py --verbose             # per-run lines
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def load_summary(run_dir: Path):
    f = run_dir / "_summary.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_parse_error": str(e)}


def last_battle_info(summary: dict):
    battles = summary.get("battles") or []
    if not battles:
        return None
    last = battles[-1]
    mons = last.get("monsters") or []
    names = ",".join(m.get("name", "?") for m in mons) if mons else "(no-monsters)"
    return {
        "num": last.get("num"),
        "result": last.get("result"),
        "monsters": names,
        "hp_end": last.get("hp_at_end"),
    }


def run_stats(summary: dict):
    battles = summary.get("battles") or []
    won = sum(1 for b in battles if b.get("result") == "won")
    lost = sum(1 for b in battles if b.get("result") == "lost")
    skipped = sum(1 for b in battles if b.get("result") == "skipped")
    return {"won": won, "lost": lost, "skipped": skipped, "total": len(battles)}


def has_tag(battle: dict, needle: str) -> bool:
    for m in battle.get("monsters") or []:
        for t in m.get("tags") or []:
            if needle in t:
                return True
    return False


def classify_death(summary: dict) -> str:
    """Return one of: ch1, ch1_boss, ch2, ch2_boss, ch1_post_skip, n/a.
    A run is "in Ch2" once it has won a Boss Pool 1 fight.
    """
    battles = summary.get("battles") or []
    if not battles:
        return "n/a"
    last = battles[-1]
    if last.get("result") != "lost":
        return "n/a"
    cleared_ch1_boss = any(
        b.get("result") == "won" and has_tag(b, "Boss Pool 1")
        for b in battles
    )
    if has_tag(last, "Boss Pool 1"):
        return "ch1_boss"
    if has_tag(last, "Boss Pool 2"):
        return "ch2_boss"
    return "ch2" if cleared_ch1_boss else "ch1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/full_runs", help="root dir of run folders")
    ap.add_argument("--since", default=None, help="only include dirs whose name starts with this prefix")
    ap.add_argument("--verbose", action="store_true", help="print one line per run")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"no such dir: {root}")
        return

    dirs = sorted(d for d in root.iterdir() if d.is_dir())
    if args.since:
        dirs = [d for d in dirs if d.name >= args.since]

    reasons = Counter()
    total_battles_won = 0
    total_battles_lost = 0
    total_battles_skipped = 0
    partial = 0
    wins = 0  # terminal_win + checkpoint_stake (made it all the way)
    killed_by = Counter()
    death_chapter = Counter()

    rows = []
    for d in dirs:
        s = load_summary(d)
        if s is None:
            partial += 1
            rows.append((d.name, "PARTIAL", "-", "-", "-", "-"))
            continue
        if "_parse_error" in s:
            rows.append((d.name, "PARSE_ERR", "-", "-", "-", s["_parse_error"][:30]))
            continue
        reason = s.get("end_reason", "?")
        reasons[reason] += 1
        st = run_stats(s)
        total_battles_won += st["won"]
        total_battles_lost += st["lost"]
        total_battles_skipped += st["skipped"]
        if reason in ("terminal_win", "checkpoint_stake", "checkpoint_unstake"):
            wins += 1
        last = last_battle_info(s)
        last_desc = "-"
        if last:
            last_desc = f"B{last['num']} {last['result']} {last['monsters'][:40]}"
            if reason == "battle_lost":
                killed_by[last["monsters"]] += 1
                death_chapter[classify_death(s)] += 1
        rows.append((d.name, reason, st["total"], st["won"], st["lost"], last_desc))

    if args.verbose:
        print(f"{'dir':40} {'end':<18} {'B':>3} {'W':>3} {'L':>3}  last")
        print("-" * 110)
        for r in rows:
            print(f"{r[0]:40} {str(r[1]):<18} {str(r[2]):>3} {str(r[3]):>3} {str(r[4]):>3}  {r[5]}")
        print()

    print(f"runs scanned:   {len(dirs)}")
    print(f"summary files:  {len(dirs) - partial}")
    print(f"partial (crash): {partial}")
    print()
    print(f"terminal wins / checkpoints: {wins}")
    print("end reasons:")
    for k, v in reasons.most_common():
        pct = 100.0 * v / max(1, len(dirs) - partial)
        print(f"  {k:<22} {v:>4}  ({pct:5.1f}%)")
    print()
    print(f"battles: won={total_battles_won}  lost={total_battles_lost}  skipped={total_battles_skipped}")
    if death_chapter:
        print()
        print("death by chapter:")
        order = ["ch1", "ch1_boss", "ch2", "ch2_boss"]
        for k in order:
            v = death_chapter.get(k, 0)
            if v:
                print(f"  {k:<10} {v:>4}")
    if killed_by:
        print()
        print("top killers (battle_lost final enemy comp):")
        for k, v in killed_by.most_common(10):
            print(f"  {v:>3}x  {k}")


if __name__ == "__main__":
    main()
