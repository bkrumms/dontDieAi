#!/usr/bin/env python3
"""Analyze run outcomes from data/full_runs/ summaries."""
import json
from collections import Counter, defaultdict
from pathlib import Path

RUNS_DIR = Path("data/full_runs")

summaries = []
for d in RUNS_DIR.iterdir():
    s = d / "_summary.json"
    if s.exists():
        try:
            summaries.append(json.loads(s.read_text(encoding="utf-8")))
        except Exception:
            pass

print(f"Summaries loaded: {len(summaries)}\n")

def classify_run(s):
    """Return (chapter_cleared, death_monster_or_reason)."""
    battles = s.get("battles") or []
    end_reason = s.get("end_reason", "unknown")

    # Find the killing blow
    last_lost = None
    for b in battles:
        if b.get("result") == "lost":
            last_lost = b
            break  # first loss = death

    # Determine highest chapter reached by looking at monster tags
    chapters_seen = set()
    bosses_beaten = []
    for b in battles:
        for m in (b.get("monsters") or []):
            tags = m.get("tags") or []
            for t in tags:
                if "Boss Pool" in t:
                    ch = int(t.split("Pool")[1].strip())
                    if b.get("result") == "won":
                        bosses_beaten.append(ch)
                elif t.startswith("B Pool") or t.startswith("BB Pool"):
                    try:
                        ch = int(t.split("Pool")[1].strip())
                        chapters_seen.add(ch)
                    except Exception:
                        pass

    chapter_cleared = max(bosses_beaten) if bosses_beaten else 0

    # Death monster
    if last_lost:
        mons = last_lost.get("monsters") or []
        if mons:
            death_to = " + ".join(m.get("name", "?") for m in mons)
            # Tag for context
            tags = mons[0].get("tags") or []
            pool_tag = next((t for t in tags if "Pool" in t), "")
            if pool_tag:
                death_to += f" [{pool_tag}]"
        else:
            death_to = "unknown battle"
    else:
        death_to = end_reason

    return chapter_cleared, death_to

results = [classify_run(s) for s in summaries]

# Overall win rate (cleared ch1 or more)
clears = sum(1 for ch, _ in results if ch >= 1)
ch2_clears = sum(1 for ch, _ in results if ch >= 2)
total = len(results)

print(f"=== OVERALL ===")
print(f"Total runs:       {total}")
print(f"Ch1 cleared:      {clears} ({clears/total*100:.1f}%)")
print(f"Ch2 cleared:      {ch2_clears} ({ch2_clears/total*100:.1f}%)")
print(f"Died before Ch1:  {total - clears} ({(total-clears)/total*100:.1f}%)")
print()

# Chapter breakdown
chapter_counts = Counter(ch for ch, _ in results)
print("=== CHAPTER CLEARED BREAKDOWN ===")
for ch in sorted(chapter_counts):
    label = f"Ch{ch} cleared" if ch > 0 else "Died in Ch1"
    print(f"  {label}: {chapter_counts[ch]} ({chapter_counts[ch]/total*100:.1f}%)")
print()

# Death causes — grouped
print("=== TOP DEATH CAUSES (all runs that died) ===")
deaths = Counter(death for ch, death in results if ch == 0)
for cause, cnt in deaths.most_common(20):
    print(f"  {cnt:4d}x  {cause}")
print()

print("=== DEATH CAUSES (runs that cleared ch1 but died in ch2) ===")
ch2_deaths = Counter(death for ch, death in results if ch == 1)
for cause, cnt in ch2_deaths.most_common(20):
    print(f"  {cnt:4d}x  {cause}")
