# Run 1 — Analysis

**Session**: `d0c9597f-4c50-40ff-b649-aea719a290e2`
**Date**: 2026-04-13
**Mode**: Practice / FTUE (tutorial flag `isFtue: true` on the progress object)
**Outcome**: Voluntarily concluded / session terminated after winning big-baddie at space 25. Did NOT reach the boss (Ganondwarf at space 39).
**Chapter**: 1
**Duration**: ~10 minutes of active play, 346 polls, 113 logged events

## Final stats

| Metric | Start | End | Δ |
|---|---:|---:|---:|
| HP | 60 / 60 | 27 / 56 | −33 / −4 max |
| Points | 0 | **14,880** | +14,880 |
| Gold | 60 | 380 | +320 |
| Time Crystals | 5 | 2 | −3 (net) |
| Trinkets | 0 | **1** (Lizard Mask) | +1 |
| Boosts | 0 | **1** (Toxipop) | +1 |

## Battle log

| # | Space | Type | HP before→after | Δ HP | Δ Points | Δ Gold | Notes |
|--:|--:|---|--:|--:|--:|--:|---|
| 1 | 0 | baddie | 60 → 60 | 0 | +1240 | +14 | Clean kill, FTUE opener |
| 2 | 4 | baddie | 52 → 51 | −1 | +1310 | +15 | Dropped food `Heat Meat` |
| 3 | 6 | baddie | 51 → 40 | −11 | +1430 | +14 | |
| 4 | 14 | baddie | 50 → 25 | −25 | +2150 | +14 | Worst trash fight — half HP gone |
| 5 | 17 | baddie | 25 → 22 | −3 | +2540 | +11 | |
| 6 | 20 | **big-baddie** | 22 → 6 | −16 | **+5430** | +36 | Pre-fight `Heat Meat` consumed. Got `Brotein Bar MAX` loot. +1 TC. |
| 7 | 25 | **big-baddie** | 28 → 27 | −1 | +2780 | +66 | Pre-fight `Brotein Bar MAX` consumed. Dropped **Lizard Mask** trinket + upgrade side. +2 TC. |

**Baddie HP damage average**: ~6.8 HP per fight (excluding the clean kill and the 25-dmg outlier).
**Big-baddie damage average**: 8.5 HP per fight, but wildly variable based on pre-fight food.

### Observation: pre-fight food matters enormously
Big-baddie at [20] without food-buff = 16 HP lost + 5430 pts.
Big-baddie at [25] with `Brotein Bar MAX` pre-fight = 1 HP lost + 2780 pts.

Brotein Bar MAX is `Attack all 20, Heal 8, Gain 2 Strength, Score 500 Points` — that explains the clean fight. The points comparison is backwards-misleading though: big-baddie [20] gave more points because the **fight was longer**, which means more die rolls, which means more base (+N) points accumulated. Protecting HP with food isn't free — it trades fight length for points.

**Rules-engine note**: "save food for big fights" is correct for **survival**, but an aggressive build might want to eat food in slower/safer fights to extend them and farm more per-roll points.

## Mystery events encountered

| Space | Cost | Benefit | Interpretation |
|--:|---|---|---|
| 2 | 0 | 0 visible | Skipped or null outcome |
| 3 | **−8 HP, −4 max HP, −1 side burned** (Poison 3) | None visible | Almost certainly a bad mystery outcome, or a "sacrifice a side" event that wasn't worth it |
| 5 | 0 | 0 visible | Skipped |
| 8 | 0 | +150 gold, **+1 Curse side** (`Exhaust a random other Side`) | Gold-for-risk trade. The curse was applied to die #2. |
| 12 | **−2000 points** | +2 TC, +10 HP | Classic `Trade Offer`-style trade: resources ↔ points |
| 15 | 0 | 0 visible | Skipped |
| (others) | — | — | Not reached |

**The Curse got through.** Die #2 now carries `"(e) Exhaust a random other Side on this Dice"` — a burn opportunity (campfire at [10] or Bub's at [36]) should have been used. The campfire at [10] was visited but the burn apparently targeted a different side. Flag for rules engine: **curse burn priority > all other burns**.

## Movement and rewinds

3 confirmed movement rewinds:

| Event | From → Rolled → Rewound → Re-rolled | TC cost |
|---|---|---:|
| Space 9 | [8] → rolled to [9] → rewound to [8] | −2 |
| Space 11 | [8] → rolled to [11] → rewound to [10] | −2 |
| Space 17 | [17] → rolled to [21] (big-baddie) → rewound to [17] → re-rolled to [20] (also big-baddie) | −2 |
| Space 23 | [21] → rolled to [23] → rewound to [24] (campfire before big-baddie [25]) | −2 |

**All 4 rewinds cost 2 TC.** `nextRerollCost` held at 2 across the run — **does not escalate on repeated use within a single run** (at least not in the first 4 uses on a tutorial run). This contradicts the Notion's implication that rewinds get more expensive; either that's a lie or escalation kicks in later.

**Smart rewind at [21]**: rolled into big-baddie [21], rewound, re-rolled, hit big-baddie [20] instead. Same enemy class but different ID/ability set. Worth investigating whether big-baddies have different difficulties and if the user intuited which was "easier".

**Smart rewind at [23]**: rolled into a regular baddie at [23], rewound, skipped it entirely to land on campfire [24] (which was critical — healed 6→28 before the big-baddie at [25]). This is the move that saved the run.

## Dice upgrades picked up

Over the run, these sides were added to the dice (confirmed from the state diffs):

| Space | Die | New side | Pool |
|--:|---|---|---|
| 0 | #1 | `Poison 8, Heal 1` | (+10) Toxic Swamp |
| 4 | #4 | `(p) Gain 2 Armor at the end of each turn` | (+20) Ice Cave |
| 6 | #4 | `(p) Gain 4 Strength at the end of each turn` | (+20) Volcano |
| 14 | #3 | `Block 18. Score 50 Points` | (+20) None |
| 17 | #4 | `(e) Poison all 3, 3 times` | (+20) Toxic Swamp |
| 20 | #1 | `(p) Gain 4 Strength at the end of each turn` | (+20) Volcano |
| 25 | #1 | `(e) Attack 16. Permanently increase the Attack on this Side by 2` | (+20) Volcano |

**Patterns**: Every upgrade picked was a `Level 2` (+20) tier side. Post-space-0 toxic swamp upgrade was the only (+10) pick. No (+30) sides offered yet (maybe they appear only in chapter 2, or after specific fights). Most upgrades went to die #4 and die #1.

**Interesting**: Die #1 got **two copies** of `Gain 4 Strength at end of each turn`. With `(p)` passive effect, that's potentially **+8 Strength per turn** stacked on die #1. Huge scaling for late-chapter fights.

## Dice reorder events

Detected 1 manual reorder (die #3 ↔ die #4 swap at 13:44:59). The observer currently logs this as two separate DIE events (added/removed on each position) — should be collapsed to a single REORDER event in a future pass.

## Data schema discoveries

### Side ability schema (live API)

```json
{
  "id": 74,
  "uuid": "...",
  "asset": "...svg",
  "label": "(e) Attack 16. Permanently increase the Attack on this Side by 2",
  "sideType": "Attack",
  "exhaust": true,
  "exhausted": false,
  "tags": [{"label": "FTUE", "tagId": 35}, {"label": "Level 2", "tagId": ...}, {"label": "Volcano", "tagId": ...}],
  "damage": {"hits": 1, "value": 16, "target": "single"},
  // plus optional: block, heal, poison, bleed, freeze, strength, armor
}
```

**Tag system**: `Level 1` / `Level 2` / `Level 3` tags correspond exactly to our `(+10)` / `(+20)` / `(+30)` pool labels. The rules engine should match pool by tag.

**Label prefixes** discovered:
- `(e)` → the side exhausts (for upgrade-tier sides; starter sides with `exhaust: true` don't show the prefix)
- `(p)` → passive / per-turn effect (like "end of each turn" sides)

### Status effect mechanics (confirmed from side payloads)

- **Bleed**: `{"value": 1.5, "target": "single", "duration": 2}` — literal **1.5× damage multiplier** for 2 turns. Confirms "take 50% more damage".
- **Freeze**: `{"value": 0.75, "target": "all", "duration": 3}` — literal **0.75× multiplier** on attack/block. Confirms "25% weaker".
- **Strength** / **Armor**: `{"value": 3, "target": "self", "duration": -1}` — **duration: -1 = permanent** for the rest of the run.
- **Poison**: `{"hits": 1, "value": 3, "target": "single", "duration": -1}` — persistent, ticks at end of turn.

### Food schema

```json
{
  "id": "954a7102-95ca-4435-8e51-59021354ff7f",
  "session_id": "...",
  "type": "Heat Meat",
  "created_at": "2026-04-13T13:44:17.000Z"
}
```

Food is identified by `type` (NOT `name`). The id is a per-instance UUID. Food items observed in run 1: `Heat Meat`, `Brotein Bar MAX`, `Toxipop`.

**Correction to food.csv**: "Protein Bar MAX" → "Brotein Bar MAX" (confirmed from API).

### Trinket schema

```json
{
  "id": "30592c1a-0cb4-4187-8c9b-87b264e891e9",
  "isUsed": 0,
  "label": "Lizard Mask",
  "action": "applyPoison",
  "condition": null,
  "target": "all",
  "trigger": "onBattleStart",
  "type": "allMonstersStartWithPoison",
  "value": "4.00"
}
```

**Huge discovery**: trinkets come back **fully machine-readable**. Fields map directly onto effect logic:
- `action` — what happens (`applyPoison`, `grantStrength`, etc.)
- `trigger` — when it fires (`onBattleStart`, `onTurnEnd`, etc.)
- `target` — who it hits (`all`, `self`, `single`)
- `value` — the magnitude (string-encoded float)
- `type` — rule-identifier for the specific trinket mechanic

The rules engine can consume trinkets directly without having to parse the English description. Same is likely true for sides and food.

## Bugs / issues flagged

1. **✅ Fixed**: observer didn't treat `"win"` as a terminal state. Added `win`, `lose`, `lost` to `TERMINAL_STATES`.
2. **✅ Fixed**: observer resolved food names to UUIDs because it tried `name`/`label`/`id`. Added `type` to the fallback chain.
3. **⚠ Known issue**: observer logs dice reorders as two separate DIE events (added/removed). Should detect "same labels, different positions" and emit a single REORDER event.
4. **⚠ Known issue**: some DIE events show empty additions/removals (e.g. at campfire [10], mystery [15]). This is probably the observer comparing ability labels but missing an in-place mutation (like `exhausted: true` flipping). Worth looking into.
5. **⚠ Open**: mystery event at space 3 was brutally expensive (−8 HP, −4 max HP, −1 side) with no visible reward. Either I'm missing what it gave us (maybe a non-state-mutating reward like XP?) or it's a trap event. Probably one of `Poison Veins`, `Chronically Tired`, or similar.

## Questions for Nick

1. Does `nextRerollCost` ever escalate within a run? We saw 4 rewinds at flat 2 TC.
2. Is the space-3 mystery supposed to have no visible reward, or did we miss something?
3. Do `(+30)` sides only appear in chapter 2, or after specific fights?
4. What determines whether a side label gets the `(e)` prefix? Some exhausting sides have it, starters don't.
5. When a "win" state is reached on a non-boss fight, is that a checkpoint screen, and why did the session dissolve after it?

## Next-run targets

Things I didn't get enough data on, prioritized:

1. **Full battle state** — can't back out individual monster attack numbers without watching battle-scene API responses. May need to poll a different endpoint during `inState = "baddie"`.
2. **(+30) side behavior** — need a run that reaches big-baddie or boss loot for these.
3. **A checkpoint decision** — none reached on run 1. Critical for rules engine.
4. **The Volcano biome stretch** (spaces 26-31 on this map) — never visited.
5. **Bub's shop** at space 36 — never visited.
6. **Obelisks** at 32-33 — never visited.
7. **Loot dice** at 13 and 34 — never visited.
8. **Checkpoint flag behavior** — `checkpointPending` stayed at 0 the whole run.
