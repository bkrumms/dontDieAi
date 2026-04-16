# Run 3 — Analysis

**Session**: `10792b8f-a38d-4b0a-b93e-38283588f40c`
**Date**: 2026-04-13
**Mode**: Practice
**Outcome**: **DIED at fork2[17] Volcano big-baddie.** One-shot from 21 HP → 0.
**Chapter**: 1
**Duration**: ~4 minutes of active play, 141 polls, 45 events

A short run but packed with firsts: first fork traversal, first "Never Tell Me The Odds" data, first pure-benefit +TC mystery, first confirmed burn-only campfire.

## Final stats

| Metric | Start | End |
|---|---:|---:|
| HP | 59 / 60 | **0 / 60** (dead) |
| Points | 1460 | 397 |
| Gold | 76 | 107 |
| TC | 5 | ? (died before final capture) |

## The "Never Tell Me The Odds" revelation

At fork2[15] we hit a mystery event and got this exact points sequence:

```
14:23:23  POINTS  4540 -> 1207  (-3333)
14:23:27  POINTS  1207 -> 207   (-1000)
14:23:28  POINTS  207 -> 107    (-100)
14:23:30  POINTS  107 -> 7      (-100)
```

**The losses (−3333, −1000, −100, −100) are exactly the pickType enum from `POST /api/game/mystery/never-tell-me-the-odds`.** This decisively identifies the event AND tells us:

1. **It supports multiple sequential bets** — the player bet four times in the same event session.
2. **Each bet is an independent gamble** from {100, 1000, 3333}.
3. **The bets are whatever-you-can-lose stakes**, not incremental wagers. You chose the stakes each time.
4. **It's the same event** that gave +10,000 points in run 2 mystery [11] — so the win distribution exists and can be big, but so can the loss.

This run was "go on tilt, lose 4,533 points in ~7 seconds" — the pattern is: lost the 3333, tried to recover with 1000, then got gun-shy and bet 100 twice, lost all four.

**Rules-engine decision tree for this event**:
- If ahead on points and stable HP: refuse entirely.
- If early in the run and scouting: bet 100 max, stop after one regardless of outcome.
- Never bet 3333 unless you're already terminal and the score is worth more than the risk.
- **Never chase losses.** A loss on bet N is NOT a reason to bet N+1.

## Pure-benefit mystery at main[5]: +4 TC

```
14:21:54  STATE   mystery -> map
14:21:56  TC      5 -> 9  (+4)
```

No HP change, no gold change, no points change. Just **+4 Time Crystals for free**. This is almost certainly `Limited Offer` with `pickType: "time-crystal"`, or a similar pure-gift event.

**Value**: +4 TC at 2 TC per rewind = **2 extra rewinds of insurance**. That's a game-shaping benefit for zero cost.

**Rules-engine rule**: always take +TC on a free mystery. No downside unless you're already at the 7-TC cap (the field isn't capped mid-run from what we've seen; only pre-run is capped at 7).

## The fork traversal (first ever)

Took fork2 (Volcano biome, 15 nodes) from main[5]:

```
main[5]  →  fork2[7]   campfire (burned Attack 4, no heal)
         →  fork2[9]   baddie (rolled past)
         →  fork2[10]  mystery (nothing visible gained)
         →  fork2[13]  baddie (-34 HP!)
         →  fork2[15]  mystery (Never Tell Me The Odds, lost 4533 pts)
         →  fork2[17]  big-baddie (DEATH, 21 -> 0)
```

### Fork node indexing
Fork node indices are **not local 0-indexed**. fork2's first node was at index 7, not index 0. They appear to be **offsets along a virtual extended path** — probably the main-path index where the fork branches off. Worth confirming with Nick but the rules engine can treat them as opaque IDs.

### Volcano fork tempo
- Volcano fork baddies hit **hard**: the baddie at fork2[13] did **34 damage** (55 → 21). That's the highest single-baddie damage we've seen so far.
- Three big-baddies in this fork. Died to the very first one at fork2[17].
- Only 3 campfires for 15 nodes. Less sustain than Ice Cave.

**Rules-engine note**: Volcano fork is a damage-race environment. Should only be taken with healing food ready, HP > 80%, and a plan for each big-baddie. A bleed-immune trinket (Ket Mask) would be valuable here given the biome's bleed density.

## Burn-only campfire confirmation

At fork2[7] campfire:
```
14:22:13  STATE  campfire -> map
14:22:13  MOVE   fork2[7] -> fork2[9]   (rolled 2 after exit)
14:22:13  DIE    die#1: -['Attack 4']
```

Die #1 lost an `Attack 4` (starter side) with **no side added and no heal logged**. This confirms:
1. Campfires can be used for pure burning (not just healing or upgrading).
2. The burn targets any side you pick, including a starter `Attack 4`.
3. Burning at a campfire costs nothing (no HP, no gold) — unlike Bub's which requires health/gold.

**Rules-engine rule reinforced**: **campfires are the cheapest burn source**. Always prioritize curse burns at campfires over other actions.

## New side pickup (CSV update)

| Side | Was in CSV as | Updated to |
|---|---|---|
| `(e) Attack 4. Heal equal to unblocked Damage` | `Attack 4. Heal equal to unblocked Damage` | Added `(e)` prefix |

Confirmed (+20) Toxic Swamp from tag data.

## Carry-over score mystery persists

| Run | Start points | End points |
|---|---:|---:|
| 1 | 0 | 14,880 |
| 2 | **1,480** | 33,570 |
| 3 | **1,460** | 397 (died) |

Run 3 started with **1,460 points** — essentially the same as run 2's start (1,480), despite run 2 ending at 33,570 and dying at boss. So the starting points are **not persistence of the prior run**. Something else is giving you ~1,460-1,480 points each run start. Candidates:
- Sticker Loot Points converted at start (but LootPoints was 0)
- A daily quest bonus
- A "starting score floor" tied to character / chapter progression
- Something from the Nova points system

**Open question for Nick**. Important because the rules engine needs to know whether this is free points (ignore) or score that counts for tournament payout (include in multiplier math).

## Flagged bug in observer

Run 3 showed a PointS event with a **large negative delta** (-3333 in one poll). The observer handled it correctly (logged as POINTS). But when the same tag fires multiple times in quick succession (4x within 7 seconds), the events render as four separate entries. **Potential improvement**: batch consecutive same-tag events within a short window into a single "POINTS storm" entry to make the timeline more readable.

## Run 3 state coverage

| Target | Achieved? |
|---|---|
| Visit an Obelisk | ❌ Still 0/5 |
| Visit a Fork | ✅ **Volcano fork (fork2) traversed** |
| Reach a (+30) upgrade offer | ❌ |
| A successful checkpoint decision | ❌ `checkpointPending` stayed 0 |
| Capture a `shopItems` payload | ❌ No shop visit |
| Survive the boss | ❌ Died in fork |

## Data collected across 3 runs so far

| Space type | Visits |
|---|---:|
| baddie | 20+ |
| big-baddie | 3 |
| boss-baddie | 1 (died) |
| mystery | ~12 |
| campfire | 6+ |
| loot-die | 1 |
| bub shop | 1 |
| **obelisk** | **0** |
| **forks** | **1 (Volcano)** — Ice Cave never visited |

## Priority data gaps for run 4

1. **Obelisk** — highest priority. 5 encountered, 0 visited.
2. **Ice Cave fork** — never visited.
3. **A full chapter-1 survival** — we need to see the checkpoint flow and what drops at the end.
4. **(+30) sides** — still zero observed.
5. **Mystery events not yet decoded**: Volcano Spirit, Yin Yang, Lava of Life, Health Points, Echo Dagger, Chronically Tired, Infinidieferno, Freezer Burn, Poison Veins, Too Temp To Pass, Double Down, Glitch Matrix.

## New rules-engine heuristics from this run

1. **Never chase a gambling loss.** Even at 100 stakes, the event has negative EV once you're tilted.
2. **Always burn starter `Attack 4` sides at campfires** once the die has a better Attack option. Starter attacks scoring +10 base points contribute less than a (+20) side per roll.
3. **Volcano fork requires >80% HP entry and bleed immunity**. Otherwise the damage race kills you before the loot pays off.
4. **Any mystery that gives +TC with no cost → take it unconditionally**. No analysis needed.
5. **Refuse Never Tell Me The Odds by default in tournament mode.** The variance isn't worth the USDC-at-stake risk.
