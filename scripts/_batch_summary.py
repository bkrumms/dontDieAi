#!/usr/bin/env python3
"""Summarize the current May 31 training batch."""
import json
from collections import Counter
from pathlib import Path

RUNS_DIR = Path("data/full_runs")
PREFIXES = ("20260531", "20260601", "20260602")
INFRA = {"start_session_failed","state_fetch_failed","stuck","battle_error","active_session_exists","unknown"}

dirs = sorted(d for d in RUNS_DIR.iterdir() if any(d.name.startswith(p) for p in PREFIXES))
summaries = []
for d in dirs:
    s = d / "_summary.json"
    if s.exists():
        try:
            summaries.append((d.name, json.loads(s.read_text(encoding="utf-8"))))
        except Exception:
            pass

def classify(s):
    battles = s.get("battles") or []
    end_reason = s.get("end_reason", "unknown")
    bosses_beaten = []
    last_lost = None
    for b in battles:
        if b.get("result") == "lost" and last_lost is None:
            last_lost = b
        for m in (b.get("monsters") or []):
            for tag in (m.get("tags") or []):
                if "Boss Pool" in tag and b.get("result") == "won":
                    try:
                        bosses_beaten.append(int(tag.split("Pool")[1].strip()))
                    except Exception:
                        pass
    ch = max(bosses_beaten) if bosses_beaten else 0
    if last_lost:
        mons = last_lost.get("monsters") or []
        death = " + ".join(m.get("name","?") for m in mons) if mons else end_reason
    else:
        death = end_reason
    return ch, death

results = [(classify(s), name, s) for name, s in summaries]
total = len(results)
ch1 = sum(1 for (ch,_),_,_ in results if ch >= 1)
ch2 = sum(1 for (ch,_),_,_ in results if ch >= 2)
infra_n = sum(1 for (_,d),_,_ in results if d in INFRA)
gameplay = total - infra_n

print(f"=== BATCH PROGRESS: {len(dirs)} started, {total} complete ===")
print(f"")
print(f"Ch1 cleared:       {ch1}/{total} ({ch1/total*100:.1f}%)")
print(f"Ch2 cleared:       {ch2}/{total} ({ch2/total*100:.1f}%)")
print(f"Infra failures:    {infra_n}/{total} ({infra_n/total*100:.1f}%)")
if gameplay:
    print(f"Gameplay Ch1 rate: {ch1}/{gameplay} ({ch1/gameplay*100:.1f}%) excl. infra")
print()

print("=== TOP Ch1 DEATH CAUSES ===")
ch1_deaths = Counter(d for (ch,d),_,_ in results if ch==0 and d not in INFRA)
for cause, cnt in ch1_deaths.most_common(10):
    print(f"  {cnt:3d}x  {cause}")
print()

print("=== TOP Ch2 DEATH CAUSES ===")
ch2_deaths = Counter(d for (ch,d),_,_ in results if ch==1)
for cause, cnt in ch2_deaths.most_common(10):
    print(f"  {cnt:3d}x  {cause}")
print()

print("=== INFRA FAILURES (detail) ===")
for (ch,d), name, s in results:
    if d in INFRA:
        battles = len(s.get("battles") or [])
        stuck_info = s.get("stuck_info", {})
        if stuck_info:
            last_calls = stuck_info.get("recent_calls", [])
            blocking = next((c for c in reversed(last_calls) if c.get("status") != 200), None)
            detail = f"  blocking={blocking['label']} status={blocking['status']} body={str(blocking.get('body',''))[:80]}" if blocking else ""
            print(f"  {name}  reason={d}  state={stuck_info.get('stuck_state')}  pos={stuck_info.get('stuck_pos')}  hp={stuck_info.get('hp')}/{stuck_info.get('max_hp')}{detail}")
        else:
            print(f"  {name}  reason={d}  battles={battles}  (no stuck_info — pre-patch run)")

print()
battle_counts = [len(s.get("battles") or []) for _, s in summaries]
if battle_counts:
    print(f"=== BATTLE STATS ===")
    print(f"avg battles/run: {sum(battle_counts)/len(battle_counts):.1f}  min: {min(battle_counts)}  max: {max(battle_counts)}")
