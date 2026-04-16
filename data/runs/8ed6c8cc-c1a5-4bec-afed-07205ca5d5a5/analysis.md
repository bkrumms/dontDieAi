# Run 2 — Analysis

**Session**: `8ed6c8cc-c1a5-4bec-afed-07205ca5d5a5`
**Date**: 2026-04-13
**Mode**: Practice (post-FTUE — new sides no longer carry the `FTUE` tag)
**Outcome**: **DIED to boss** (Ganondwarf at space 39). One-shot, 25 → 0 HP.
**Chapter**: 1
**Duration**: ~10 minutes, 333 polls, 137 logged events

## Final stats

| Metric | Start | End | Δ |
|---|---:|---:|---:|
| HP | 59 / 60 | 0 / 60 | DEAD |
| Points | 1480 | **33,570** | +32,090 |
| Gold | 74 | 89 | +15 (after spending 173 at Bub's) |
| TC | 5 | 1 | −4 net |
| Trinkets | 0 | 2 (Kronicles Mask, Sunstone) | +2 |
| Sides added | 0 | 9+ (incl. 2 from Bub's) | +9 |

**Carry-over from run 1 confirmed**: started with 1480 points (not 0) and 74 gold. Practice runs persist score and gold to the next run on the same character — useful intel for the rules engine ("there's no penalty for dying in practice, just a soft economy reset").

## Battle log

| # | Space | Type | HP δ | Δ Points | Δ Gold | Loot / Notes |
|--:|--:|---|--:|--:|--:|---|
| 1 | 0 | baddie (FTUE start) | — | (start state) | — | Already mid-fight at INIT |
| 2 | 2 | baddie | −6 | +1570 | +14 | Got side `(e) Exhaust one 'Basic Attack' on each die` |
| 3 | 14 | baddie | −3 | +1410 | +12 | Got side `(p) Score 100 Points any time you Block` |
| 4 | 17 | baddie | −4 | +2030 | +16 | Dropped food **Heat Meat** |
| 5 | 19 | baddie | 0 | +1340 | +14 | **Clean kill** |
| 6 | 22 | baddie | 0 | +2120 | +14 | **Clean kill**. Dropped food **Brrrito Blockerito** |
| 7 | 25 | **big-baddie** | −23 | +3030 | +62 | Trinket **Sunstone** + food **Boom Beans** + **+2 TC** |
| 8 | 29 | baddie | 0 | +2870 | +13 | **Clean kill** (Boom Beans active) |
| 9 | 31 | baddie | **−29** | **+9280** | +14 | Brutal trash fight, but huge points (Heat Meat consumed mid-fight) |
| 10 | 39 | **boss-baddie (Ganondwarf)** | **−25 → DEAD** | +440 | 0 | One-shot. Brrrito Blockerito did not save us. |

**Boss damage**: Ganondwarf inflicted **25 damage in a single turn** through Brrrito Blockerito (which gives "Stack Block for first 6 turns"). That means his attack either bypassed block, was AoE freezing block (25% block weakness), or applied bleed to amplify — or all three ("All Modifiers. High Damage." per `baddies.md`). **+440 points on death** suggests partial-turn play before death.

**The +9280-point baddie at [31]**: 8.7× the base trash fight. Probably the points-multiplier sides we'd been stacking finally fired. This is the moment the run exploded — but it left us at 1 HP needing a heal before the boss.

## Mystery events

| Space | Cost | Benefit | Inferred event |
|--:|---|---|---|
| 11 | 0 | **+10,000 points** | Probably `Never Tell Me The Odds` — gambled, won big. Single biggest mystery payoff observed. |
| 13 | −2000 points | +7 HP, +2 TC | `Trade Offer` / `Health or Wealth`-style. Same pattern as run 1's space-12 mystery. |

**Run 1 vs Run 2** for the same trade-style event: confirmed pattern. Resources ↔ points trade is consistent.

## New space types visited (run 2)

### Loot Die at [6]
- Costs nothing to enter
- Returned **+29 gold**, **trinket Kronicles Mask**, **+1 Loot Points**
- No food, no TC, no sides
- State transition: `rewindable` → `loot-die` → `map`

### Bub's Shop at [35]
Sequence (over ~14 seconds):
1. State: `rewindable` → `bub`
2. Gold: **262 → 89** (spent 173 gold)
3. Die #2: empty diff event (likely a **burn**)
4. Die #2: gained `Attack 6, 2 times` (Level 2 None side)
5. Die #1: gained `(p) Heal 2 at the end of each turn` (Level 1 Toxic Swamp side)
6. State: `bub` → `map`

**Pricing inference**: 173 gold for 2 sides + 1 burn. If burns cost ~30g, that's ~70g per side. Or one side was 100, the other 73 (varies by tier?). We need to capture an actual `shopItems` payload to nail this down.

### Forks (NOT visited but observed)
At 14:03:55 the die rolled **into `fork2[9]`** from `main[7]`. Then the user rewound back to `main[7]` (cost 2 TC). So **forks are reachable via map roll** and the user can rewind out of them. The map JSON shows `fork1Nodes` (15 nodes) and `fork2Nodes` (14 nodes) on this run — biome content not yet observed.

### Spaces still not visited
- Obelisk (3 of them in this run — 20, 32, 33 — none visited)
- Fork content (rolled into one but rewound)

## Movement rewinds — 4 total, all 2 TC

| Move | Path | Cost |
|---|---|---:|
| [4] → rewind [2] | wanted earlier baddie | −2 |
| `main[7]` → rolled `fork2[9]` → rewound `main[7]` | refused fork | −2 |
| [13] → [15] → [13] → [14] | precision targeting baddie [14] | −2 |
| [29] → [25] → [29] | re-rolled, got the same baddie back | −2 |

**Pattern locked**: `nextRerollCost` stayed at **2 TC** for all 4 rewinds across this run, just like run 1. **Across both runs (8 rewinds total), the cost has never escalated.** Either escalation kicks in higher, only happens in tournament mode, or Notion was wrong. **Rules-engine implication**: budget rewinds at flat 2 TC.

## Dice manipulation

- **Manual reorder** detected at 14:06:00 (die #3 ↔ die #4 swap pre-fight). Same as run 1. Observer still logs as two events; future fix.
- **Bub's burn** at 14:11:22 — the die #2 "empty change" event likely represents a burn that the diff didn't categorize. Need to compare die length pre/post to detect burns explicitly.

## New sides observed in run 2

| Pool | Biome | Effect | Notes |
|---|---|---|---|
| (+10) | Toxic Swamp | `Poison 4, 2 times` | Already in CSV ✓ |
| (+10) | Volcano | `Block 8, Bleed 3` | Already in CSV ✓ |
| (+10) | Toxic Swamp | `Poison all 4` | Already in CSV ✓ |
| (+10) | None | `(p) Score 100 Points any time you Block` | **CSV updated**: added `(p)` prefix |
| (+10) | Toxic Swamp | `(p) Heal 2 at the end of each turn` | **CSV updated**: added `(p)` prefix |
| (+20) | Volcano | `(e) Exhaust one 'Basic Attack' on each die` | **NEW — added to CSV** |
| (+20) | Volcano | `Multiple Largest Attack On This Die` | **NEW — added to CSV** |
| (+20) | None | `Attack 6, 2 times` | Already in CSV ✓ |
| (+20) | None | `Score 1 Point per the collective Points your Dice are worth` | Already in CSV ✓ |

**CSV total now: 77 sides** (was 75). Notion target: 80+.

### Structured `specialEffect` types observed

The API exposes side mechanics in machine-readable form via `specialEffect.type`. So far observed:

| `specialEffect.type` | Side example |
|---|---|
| `exhaustBasicAttacks` | `(e) Exhaust one 'Basic Attack' on each die` |
| `gainHealthWhenTurnEnd` | `(p) Heal 2 at the end of each turn` |
| `gainPointsOnGainBlock` | `(p) Score 100 Points any time you Block` |
| `gainPoints` | `Block 18. Score 50 Points` (the secondary effect) |
| `multiplyLargestAttackOnThisDie` | `Multiple Largest Attack On This Die` |
| `gainPointPerCollectivePointsFromAllDie` | `Score 1 Point per the collective Points your Dice are worth` |

**Implication for the rules engine**: side effects are matchable by `specialEffect.type` enum, not by parsing English. The rules engine should index sides by this field once we have the full set.

## Trinkets observed

| Name | From | Confirmed in CSV |
|---|---|---|
| Kronicles Mask | Loot Die [6] | ✓ Common, "Freeze immune" |
| Sunstone | Big-baddie [25] loot | ✓ Common, "Increase Damage by 1x for turn 1" |

## Food observed

| Name | From | Used | Confirmed in CSV |
|---|---|---|---|
| Heat Meat | Baddie [17] drop | Mid-fight at baddie [31] | ✓ |
| Brrrito Blockerito | Baddie [22] drop | Pre-boss [39] | ✓ |
| Boom Beans | Big-baddie [25] loot | Pre-baddie [29] | ✓ |

## Tag system finding

Run 1 sides all carried the `FTUE` tag (tutorial run). Run 2's NEW sides lack the `FTUE` tag entirely:
- Run 2 new side `(e) Exhaust one 'Basic Attack' on each die`: tags `['Volcano', 'Level 2']` — no FTUE.
- Run 2 new side `Multiple Largest Attack On This Die`: tags `['Level 2', 'Volcano']` — no FTUE.

**However**, the starter sides (`Attack 4`, `Block 6`, etc.) STILL carry the `FTUE` tag in run 2. So FTUE tags are baked into specific *side instances* at character creation, not refreshed per run.

This means the rules engine can detect "is this a tutorial-pool side" by tag matching, and over time the player's dice become a mix of FTUE-tagged starters and post-FTUE upgrades.

## Things I want from run 3+

1. **Visit an Obelisk** — 0 visits across 2 runs. We need ability data for these.
2. **Visit a Fork** — rolled into one once but rewound out. Need to see the biome content.
3. **Reach a (+30) upgrade offer** — none observed. Maybe locked behind big-baddie loot in chapter 2, or maybe behind the boss?
4. **A successful checkpoint decision** — `checkpointPending` stayed at 0 both runs. Is checkpoint pending a flag that flips at specific spaces? Or is it never set in chapter 1?
5. **Capture a `shopItems` payload** — I only see the resulting state after Bub's purchase, not the shop contents. To get this I'd need to also poll a battle/shop GET endpoint, OR watch the user click in shop and infer from the state delta. Worth a probe.
6. **Survive Ganondwarf** — for boss-loot data and the chapter transition.
7. **Capture mystery event payload structure** — confirming WHICH event gave the +10000 points at [11].

## Boss death post-mortem

You went into Ganondwarf with:
- **25 HP** (just healed at campfire [38])
- **1 TC** (couldn't rewind a bad battle)
- **Brrrito Blockerito** food: "Stack Block for your first 6 turns"
- 0 trinkets active for the boss specifically (Kronicles Mask = freeze immune is great vs ice baddies, less useful here)

Ganondwarf hit for 25 in a single turn. Brrrito gives stacked block but Ganondwarf has "All Modifiers" — likely applied **freeze** (your block becomes 75% effective) and/or **bleed** (all incoming damage gets 1.5×). With those, even a hefty block wall crumbles fast.

**Rules engine takeaway**:
- Going into a boss with **<50% HP and 1 TC is a death sentence**. The rule should be: **never push to a boss with <50% max HP and <2 TC unless the score gain is worth dying**.
- For Ganondwarf specifically: **freeze immunity (Kronicles Mask) does nothing** — he applies bleed/strength/etc. Plan a different food: `Ice Rice` (Negate next 3 Debuffs) is actually the perfect answer to his "All Modifiers" pattern.
- **Rule**: "vs. boss with All Modifiers → prioritize Ice Rice food if available."
