# Run 4 — Analysis (THE BIG ONE)

**Session**: `12776905-ebfd-4232-a822-dfe597cef3e2`
**Date**: 2026-04-13
**Mode**: Practice
**Outcome**: DIED in Chapter 2 at main[22] baddie. HP 15 → 0.
**Chapter**: Reached Chapter 2 for the first time.
**Duration**: ~17 minutes, 586 polls, 242 events — longest run yet.
**Final score**: **56,374 points** (new PR).

This run was the data jackpot: **first Chapter-1 boss kill, first Obelisk visit, first Toxic Swamp fork, first (+30) side observed, first boss trinket captured.**

## Points carry-over mystery SOLVED

Run 4's INIT had `points=0` and `HP=60/60` (fresh state, watcher connected before any dice rolled). Runs 2 and 3 had `points=~1480` and `HP=59/60` at INIT — meaning the watcher connected a few seconds *after* the first fight had already begun, so what I thought was "carry-over" was **actually just the first few dice rolls of baddie [0] that I missed**.

**Conclusion**: no points carry-over exists. Each run starts at 0. The mystery was a watcher-timing artifact.

## Final stats

| Metric | Start | End |
|---|---:|---:|
| HP | 60 / 60 | **0 / 66** (dead; max HP had been boosted to 70 then clipped to 66) |
| Points | 0 | **56,374** |
| Gold | 60 | (died mid-fight, probably ~175) |
| TC | 5 | 1-3 (fluctuated) |
| Trinkets | 0 | **3** (Lizard Mask, Bottled Fairy, Scoring) |
| LOOT-MUL | 0 | **2** |
| LOOT-PTS | 0 | 11 |
| Chapter | 1 | **2** ✓ |

## Chapter-1 BOSS KILL (Ganondwarf) — the Ice Rice rule is confirmed

Pre-fight setup that worked:
- HP 30 (healed from 6 at campfire [38])
- 1 TC
- Food: **Ice Rice** ("Negate next 3 Debuffs") — used pre-fight
- Trinkets: Lizard Mask (Poison all 4 at battle start), Bottled Fairy (revive at 30% on death)

Result:
- **Survived.** Took damage but healed back; final post-fight HP: 70 (max HP went 60 → 70!)
- **+2890 points** in-fight
- **+2 TC, +87 gold**
- **+Pickle food**
- **+11 LP (LOOT-PTS 10 → 11)**
- **+Scoring trinket** — brand new boss-tier trinket
- **Chapter 1 → 2** after the fight

**Contrast with run 2** (died to Ganondwarf, one-shot 25 → 0):
- Run 2 used Brrrito Blockerito (Stack Block for 6 turns). Block got weakened by freeze + bleed-amplified incoming damage. One-shot death.
- Run 4 used Ice Rice. Ganondwarf's first 3 debuffs were negated — which means his freeze + bleed + whatever-else couldn't land. Block did its job. Survived.

**Rules engine rule CONFIRMED**: **vs. a boss with "All Modifiers" pattern → pre-fight Ice Rice is the single most important food choice**. Anything else is strictly worse. Call this **Rule #1: Ice Rice vs Ganondwarf** and similar All-Modifier bosses (Big Cheeza in chapter 2 has "Removes Debuffs and Reduces Damage" — Ice Rice is probably less good there, but worth testing).

## Obelisk visit at main[33] — first ever

The Obelisk is an **offering mechanic**: you sacrifice food items to the obelisk in exchange for large rewards.

Sequence:
```
14:37:26  STATE  rewindable -> obelisk
14:37:33  FOOD-  Ice Rice       ← sacrificed
14:37:54  FOOD-  Clutch Creme   ← sacrificed
14:38:03  FOOD-  Crit Chips     ← sacrificed
14:38:23  DAMAGE  7 -> 6  (-1)   ← slight HP cost
14:38:23  POINTS  16327 -> 26257 (+9930)  ← HUGE payout
14:38:25  TC      3 -> 5  (+2)
14:38:25  GOLD    139 -> 217 (+78)
14:38:25  TRINKET+  Bottled Fairy     ← rare-tier trinket
14:38:25  LOOT-MUL  1 -> 2             ← Loot Multiple doubled
14:38:25  LOOT-PTS  8 -> 10
```

**Observations:**
1. **Sacrificed 3 food items** (Ice Rice, Clutch Creme, Crit Chips).
2. **Gained +9930 points** — the single largest point gain outside of battle in the run.
3. **+2 TC, +78 gold, +trinket, +loot multiple/points, -1 HP**.
4. The obelisk's scale seems to be "3 food items in, massive rewards out".

**Caveat**: the player sacrificed `Ice Rice` to the obelisk, then later had to **buy another Ice Rice from Bub's** to bring into the boss fight. Giving up Ice Rice to an obelisk is risky unless you'll find another one before the boss. The player barely pulled it off.

**Rules-engine rules**:
- **Visit Obelisks when holding 3+ food items AND none are labeled "Ice Rice" or "Godmode Guac"** (reserved for boss).
- **Skip Obelisks when carrying fewer than 3 food items** (probably refuses to trade?).
- **Skip Obelisks in Chapter 1 if the next stop is Ganondwarf-adjacent AND you don't have Ice Rice in reserve**.

## The Toxic Swamp fork (fork1) traversal

Went main[8] → fork1[10] (mystery, Never Tell Me The Odds **lost 3533**) → rewind abuse back to fork1[10] (cost 4 TC total) → fork1[12] (Bub's visit — 186 gold spent, bought 2 sides and burned an Attack 4) → fork1[14] (campfire, burned Poison 3) → fork1[15] → fork1[17] (big-baddie, 32 dmg taken, +Godmode Guac + trinket slot) → fork1[18] → main[20].

**Fork1 had:**
- 11 nodes, all Toxic Swamp biome
- 2 big-baddies, 3 mysteries, 3 campfires, 2 baddies, 1 Bub
- Rich in sustain (3 campfires) — confirmed for my earlier "Ice Cave fork has 3 campfires for sustain" note, same applies to Toxic Swamp

The fork1 big-baddie at [17] did **32 damage** (53 → 21). For comparison Volcano fork's big-baddie in run 3 did a one-shot 21 → 0 kill. Toxic Swamp is milder but still punishing.

## Second "Never Tell Me The Odds" data point

At fork1[10] mystery:
```
14:30:58  POINTS  3600 -> 267  (-3333)
14:31:00  POINTS  267 -> 167   (-100)
14:31:01  POINTS  167 -> 67    (-100)
```

Same event as run 3: gambled, lost 3333 then tilted into two 100 losses. **−3533 total.** Third data point confirms the multi-bet pattern.

## Chapter 2 began at main[0] (post-boss)

After boss:
```
14:41:11  STATE  boss-baddie -> map
14:41:11  MOVE   main[39] -> main[0]
14:41:11  ROLL   rolled 0
14:41:11  CHAPTER  1 -> 2
```

Chapter 2 starts at main[0] with a special `rolled 0` event — the post-boss transition forces a reset. Interesting implementation detail.

**Chapter 2 baddies HIT MUCH HARDER:**

| Space | Damage taken | Points gained |
|---|---:|---:|
| main[1] baddie | −6 | +3460 |
| main[5] baddie | −1 | **+11,207** |
| main[7] baddie | **−41** | +3940 |
| main[10] baddie | +1 (heal) | +4470 |
| main[22] baddie | **DEATH** | +1060 |

Chapter 2 baddies are dealing ~40 damage in single fights. Note also: **main[5] gave 11,207 points** — the points engine was fully online (Scoring trinket ticking 7777 per battle end + multipliers stacking).

## New data captured

### New trinkets (3 captured; 1 new to knowledge base)

| Name | Type / Action | Trigger | Value | Notes |
|---|---|---|---|---|
| Lizard Mask | allMonstersStartWithPoison / applyPoison | onBattleStart | 4.00 | Already in CSV ✓ |
| Bottled Fairy | bottledFairy / health | onDeath | 30.00 | **Renamed from "Fairy in a Bottle"** — live name is Bottled Fairy |
| **Scoring** (new) | scoring / **score7777** | onBattleEnd | 1.00 | **Scores 7777 points at the end of every battle.** Boss-tier trinket. |

**Scoring is a monster trinket.** Dropped by Ganondwarf. At +7777 points per battle end, in a 20-battle run that's +155,540 points from this one trinket. Priority target in any boss-loot decision.

### New food: Crit Chips

`Crit Chips` appeared in the food drops. Not in our CSV, effect unknown (consumed at the obelisk without being activated on a fight). Adding as placeholder `Effect TBD`. Need to see it used in a battle to know what it does.

### New side observed: first Level 3 (+30)!

`(e) Block 40` — ID 14, tags `['FTUE', 'Ice Cave', 'Level 3']`, exhaust=True. This is our **first observed `Level 3` / `(+30)` side**. Confirms the tier system and validates the CSV entry.

### New tag combo: `Level 3 Boss`

`2x Poison` — tags `['Toxic Swamp', 'Level 3 Boss']` — dropped after the boss fight. This suggests **bosses drop special `Level 3 Boss`-tagged sides** that may be a subset of the +30 pool only obtainable from bosses. Worth investigating. Could explain why some +30 sides are never seen in normal upgrade offers.

### CSV corrections applied

| File | Change |
|---|---|
| sides.csv | `Attack 14, Gain 2 Strength` → `Attack 12, Gain 4 Strength` (value correction) |
| sides.csv | `Attack all 10` → `Attack All 10` (capitalization) |
| sides.csv | `Block 8 per Freeze or Bleed on you. Otherwise Block 10` → restored comma after `Otherwise,` |
| sides.csv | `Freeze all 3, Bleed 4, Poison 5` → `(e) Freeze all 3, Bleed 4, Poison 5` |
| sides.csv | `Block 40` → `(e) Block 40` |
| sides.csv | `Freeze self 2` → `Afflict yourself with 2 Freeze` (Curse label) |
| trinkets.csv | `Fairy in a Bottle` → `Bottled Fairy` |
| trinkets.csv | **Added Scoring (boss tier, +7777 per battle end)** |
| food.csv | **Added Crit Chips (effect TBD)** |

## Rewinds in run 4

6 rewinds total. All 2 TC each. Briefly observed `REROLL-COST` flip 2 → 3 → 2 during a Bub's visit at 14:38:44-14:38:47 — suggests the **reroll cost can temporarily spike at certain points** (entering Bub's?) but then reset. Flag for investigation.

## Max HP can go UP

After the boss fight, max HP went **60 → 70** (+10). So bosses can grant permanent max HP increases. Later at fork2[14] mystery (chapter 2), max HP clipped **70 → 66** (-4). So the "bad mystery" pattern (HP + max HP cost) persists in chapter 2.

## Boss drops full inventory

Ganondwarf dropped:
- +2 TC
- +87 gold
- +1 Pickle food
- +1 LOOT-PTS
- **+Scoring trinket** (boss-tier)
- **+10 max HP**
- **+31 heal** (post-fight restore)
- **+2x Poison side** (Level 3 Boss Toxic Swamp, added to die #3)

The boss is worth **dramatically more than any other event in the game** when you survive it. This validates the core rules-engine question: **how much HP/TC should you commit to surviving the boss?** Answer: **a lot, because the payout is huge.**

## Key rules-engine heuristics from run 4

1. **[CONFIRMED] Ice Rice vs All-Modifier bosses** — non-negotiable best food pick for Ganondwarf.
2. **Obelisks want 3 food sacrifices in exchange for ~10k points + TC + gold + trinket + LOOT-MUL**. Visit only with non-essential food surplus.
3. **"Never Tell Me The Odds" is tilt-trap** — refuse by default, or bet only 100 once and walk regardless of outcome.
4. **Any +TC mystery event → take it unconditionally.**
5. **Max HP can grow** (bosses) and shrink (cost mysteries). Don't treat HP cap as fixed.
6. **Boss loot is the single most valuable event in the game** by at least 5×. Any run planning must include surviving the boss as the central objective.
7. **Chapter 2 baddies deal ~40 damage in single fights.** Carry >50 HP into chapter 2 or you die fast (which is what happened in this run: died at chapter 2 main[22] with 15 HP).

## Still missing (priorities for run 5+)

1. **Ice Cave fork** — still never visited. Only biome never entered.
2. **Checkpoint decision flow** — `checkpointPending` stayed 0 the whole run. Does the game actually show a checkpoint screen in practice mode? Or only in tournament?
3. **Chapter-2 boss fight** (Big Cheeza, 700 HP).
4. **Multiple Obelisk visits** — 1 obelisk captured; need more to know if the reward scales with food sacrificed, and if skipping is an option.
5. **Full `shopItems` payload** — still inferred from state deltas, not direct.
6. **Most mystery events** still undecoded (Volcano Spirit, Yin Yang, Lava of Life, Health Points, Echo Dagger, Chronically Tired, Infinidieferno, Freezer Burn, Poison Veins, Double Down, Glitch Matrix, Too Temp To Pass).
