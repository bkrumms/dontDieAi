"""Summarize a batch run log (e.g. data/test_50runs_v14.log).

Usage: python scripts/summarize_batch.py <log_path>

Prints one line per run: index, end reason, stage reached (ch/pos),
points, last battle type, and what killed them.
"""
import re
import sys
from pathlib import Path


RUN_START = re.compile(r">>> run #(\d+) logging")
POS_PTS = re.compile(r"pos=(\w+)\[(\d+)\] hp=(\d+)/\d+ pts=(\d+)")
BATTLE_HDR = re.compile(r"=== BATTLE #(\d+) \((.+?)\) ===")
MONSTERS = re.compile(r"monsters: (.+)$")
SUMMARY_START = "=== RUN SUMMARY ==="
END_REASON = re.compile(r"end reason:\s+(\w+)")
TOTAL_BATTLES = re.compile(r"total battles: (\d+)")
BATTLE_LINE = re.compile(r"#(\d+) \[(\w+)\] t=(\d+) hp_end=(\S+)\s+(.+)$")


def chapter_from_pos(path: str, idx: int) -> str:
    # Main path tile counts differ per chapter, but pos resets on checkpoint.
    # Simple heuristic: ch1 stage1 ~0-12, stage2 ~13-25, ch2 restarts index.
    return f"{path}[{idx}]"


def parse(log_path: Path):
    runs = []
    current = None
    last_battle_type = None
    last_monsters = None
    last_pos = None
    last_pts = None
    in_summary = False
    summary_battles = []

    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RUN_START.search(line)
        if m:
            if current is not None:
                runs.append(finalize(current, last_pos, last_pts, last_battle_type,
                                     last_monsters, summary_battles))
            current = {"run": int(m.group(1)), "end_reason": "incomplete"}
            last_battle_type = last_monsters = last_pos = last_pts = None
            summary_battles = []
            in_summary = False
            continue
        if current is None:
            continue

        m = POS_PTS.search(line)
        if m:
            last_pos = (m.group(1), int(m.group(2)))
            last_pts = int(m.group(4))

        m = BATTLE_HDR.search(line)
        if m:
            last_battle_type = m.group(2)
            last_monsters = None

        m = MONSTERS.search(line)
        if m and last_battle_type and last_monsters is None:
            last_monsters = m.group(1).strip()

        if SUMMARY_START in line:
            in_summary = True
            continue

        if in_summary:
            m = END_REASON.search(line)
            if m:
                current["end_reason"] = m.group(1)
            m = BATTLE_LINE.search(line)
            if m:
                summary_battles.append({
                    "idx": int(m.group(1)),
                    "result": m.group(2),
                    "monsters": m.group(5).strip(),
                })

    if current is not None:
        runs.append(finalize(current, last_pos, last_pts, last_battle_type,
                             last_monsters, summary_battles))
    return runs


def finalize(run, pos, pts, btype, monsters, sbattles):
    # Prefer summary's last battle for the "died to" field.
    died_to = None
    last_btype = btype
    if sbattles:
        last = sbattles[-1]
        if last["result"] != "won":
            died_to = last["monsters"]
    if died_to is None and run["end_reason"] != "terminal_win" and monsters:
        died_to = monsters
    run["pos"] = f"{pos[0]}[{pos[1]}]" if pos else "?"
    run["pts"] = pts or 0
    run["battles"] = len(sbattles) if sbattles else "?"
    run["last_battle"] = last_btype or "?"
    run["died_to"] = died_to or ("—" if run["end_reason"] == "terminal_win" else "?")
    return run


def main():
    if len(sys.argv) < 2:
        print("usage: summarize_batch.py <log_path>")
        sys.exit(1)
    runs = parse(Path(sys.argv[1]))
    print(f"{'#':>3} {'end':<14} {'pos':<12} {'pts':>6} {'btls':>4}  {'lastB':<12} died_to")
    print("-" * 100)
    by_reason = {}
    for r in runs:
        by_reason[r["end_reason"]] = by_reason.get(r["end_reason"], 0) + 1
        print(f"{r['run']:>3} {r['end_reason']:<14} {r['pos']:<12} "
              f"{r['pts']:>6} {str(r['battles']):>4}  {r['last_battle']:<12} {r['died_to']}")
    print("-" * 100)
    print(f"total runs: {len(runs)}")
    for k, v in sorted(by_reason.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
