# Overnight DD bot test log

Format per batch:
`[timestamp] batch=N wins=W/10 avg_battles=X ch2=Y notable:...`

Started: 2026-04-13 overnight session.
[2026-04-14 02:46 UTC] batch=v5 wins=0/10 ch2=3/10 avg_b=7.6 early=3 stuck=3 notable: Freezer Burn burn-side rejected 'min 4 sides' → added boost fallback to unstick loop
[2026-04-14 sim-gap] sim/battle.py doesn't apply player→enemy Strength debuffs — '-15 Str all enemies' had no effect in b03 sim. Same gap likely for armor debuffs, poison-transfer, etc.
