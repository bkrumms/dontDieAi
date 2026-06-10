#!/usr/bin/env python3
import json, sys
from pathlib import Path
from collections import Counter

lines = Path("data/hermes_shadow.jsonl").read_text(encoding="utf-8").strip().splitlines()
entries = [json.loads(l) for l in lines if l.strip()]

agrees = sum(1 for e in entries if e.get("agrees"))
total = len(entries)
agree_rate = agrees / total * 100 if total else 0

hermes_picks = Counter(e.get("hermes_pick", "?") for e in entries)
rule_picks = Counter(e.get("rule_pick", "?") for e in entries)
disagrees = [e for e in entries if not e.get("agrees") and e.get("hermes_pick") not in ("?", None, "")]

print(f"Total decisions logged: {total}")
print(f"Hermes agrees with rule engine: {agrees}/{total} ({agree_rate:.1f}%)")
print()
print("Top Hermes picks:")
for label, cnt in hermes_picks.most_common(10):
    print(f"  {cnt:4d}x  {label}")
print()
print("Top rule engine picks:")
for label, cnt in rule_picks.most_common(10):
    print(f"  {cnt:4d}x  {label}")
print()
print(f"Disagreements: {len(disagrees)}")
print("Sample disagreements (hermes vs rule):")
for e in disagrees[:10]:
    offered = e.get("offered", [])
    rule = e.get("rule_pick", "")
    hermes = e.get("hermes_pick", "")
    rationale = e.get("hermes_rationale", "")[:90]
    print(f"  offered: {offered}")
    print(f"    rule={rule!r}  hermes={hermes!r}")
    print(f"    rationale: {rationale}")
    print()
