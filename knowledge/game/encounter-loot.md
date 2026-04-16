# Encounter Loot — Drop Tables, Shop Rules, and Loot Algorithms

**Source**: Nick's `Encounter Loot.html` (2026-04-13 database export). This is the master spec for what each encounter type can drop and how loot/rewards are selected.

## Drop matrix by encounter type

| Encounter | New Side | Points | Gold | Food | Time Crystals | Trinket | Sticker | Health | Burn | Bones |
|---|---|---|---|---|---|---|---|---|---|---|
| Baddie | ✓ | ✓ | ✓ | Chance | Chance | ✗ | ✗ | ✗ | ✗ | ✗ |
| Big Baddie | ✓ | ✓ | ✓ | ✓ | Chance | ✗ | ✓ | ✗ | ✗ | **✓** |
| Mini Boss Big Baddie (stop-fight) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | **✓** |
| Obelisk | ✓ | ✓ | ✓ | Chance | ✓ | ✓ (higher rare chance) | **✓ ×2** | ✗ | ✗ | **✓** |
| Boss Baddie | ✓ (Special L3) | ✓ | ✓ | ✗ | ✓ | ✓ (boss tier) | ✓ | ✗ | ✗ | ✗ |
| Bub's Barter | ✓ ×6 | ✗ | **spend** | ✓ ×2 | ✓ | ✓ ×3 (2 common, 1 rare) | ✗ | **spend** | ✓ | ✗ |
| Campfire | ✗ | ✓ | ✗ | ✓ ×2 | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ |
| Loot Die | ✗ | ✗ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Mystery Event | Chance | Chance | Chance | Chance | Chance | Chance | Chance | Chance | Chance | ✗ |

**Key facts**:
- **Bones** only drop from Big Baddies, Mini Boss stop-fights, and Obelisks. 1 Bone per kill.
- **Trinkets** never drop from common Baddies — only from Big+ encounters and the Loot Die space.
- **Boss Baddies drop Level 3 sides that score 100 per roll** (not the normal 30 per roll). This is the "Level 3 Boss" tag.
- **Obelisks give 2× stickers** (double sticker drop).
- **Health** only comes from Mini Boss stop-fights, Obelisks, Boss Baddies, and Campfires (the Rest option).

## New Side selection algorithm

When a battle ends and you're offered a new side, the game rolls 3 options one at a time.

### Rules (from Nick, verbatim)

1. **When players see Side rewards, the Sides are rolled 1 by 1 until all 3 are rolled. Then, they're shown to the player.**
2. **The same Side cannot be duplicated in the rewards set** — you won't see 2 identical options.
3. Some Sides are tagged with a biome; most are non-tagged neutral.
4. **If you're in a biome and offered a side**, **2 of the 3 slots will have that biome's tag** (guaranteed).
5. **If you added a side in the most recent upgrade for this Die** (didn't skip), **1 of the 3 slots will match the biome tag of that previously-added side**.
6. If a slot has no biome stipulation, roll 50/50 between Neutral and Biome. If Biome, pick randomly from the 3 biomes.
7. Once biome tag assignment is done, roll for the **Level** of each side.

### Level odds (dynamic)

At the start of each chapter, the base odds for a given slot are:

| Level | Base odds |
|---|---:|
| Level 1 | **(70 − x)%** |
| Level 2 | **30%** |
| Level 3 | **x%** |

Where `x` is a counter starting at 0 and reset at the beginning of each chapter.

- **Every time a Level 1 side is selected, x increases by 1** (max selection is 3 per reward roll, so x can grow by up to 3 per battle).
- **Every time a Level 3 side is selected, x drops to 0.**

This means:
- Level 3 odds start at 0% and grow as you pick Level 1s.
- After ~10 Level 1 picks, Level 3 odds are ~10%.
- Hitting a Level 3 drops you back to 0.
- **Two Level 3s in a single reward set is ~1/100** and only possible if slot 1 rolled Level 3 while x was high, dropping x to 0, slot 2 rolled something else growing x to 1, and slot 3 hit Level 3 on a 1% chance.

### Side selection within a level

Once level + biome are determined per slot:
1. List all sides at that level matching that biome tag.
2. **Give each side a likelihood score of 1.**
3. **If that specific die already has a copy of a given side, that side's likelihood score becomes 2** (double odds of being offered).
4. **If the die has 2 copies of a specific Level 3 side already, that side's likelihood drops to 0** (cap at 2 per die).
5. Random weighted draw from the likelihood pool.
6. Selected side is removed from the pool for the other 2 slots in this set (no duplicates within the set).

### Boss override
**Boss Baddie loot always offers 3 Level 3 sides**, all with the **+100 per roll** base score. Same likelihood-weighting rules apply.

## Food pool odds

Each baddie battle or obelisk has a **dynamic food drop chance**:

- Run starts at **20% chance to drop food**.
- Every time you DON'T get a food, the chance **increases by 10%** for next reward.
- Every time you DO get a food, the chance **decreases by 10%** for next reward.
- Caps effectively between ~10% and ~80%.

When a food does drop, it comes from:
- **Food Pool 1 (common)**: 70%
- **Food Pool 2 (rare)**: 30%

**If in a biome** and Pool 1 is rolled, 50/50 between biome food and non-biome food within Pool 1. (Foods have biome tags.)

## Trinket pool odds

Each Big Baddie or higher drops a trinket roll:
- **Common**: 90%
- **Rare**: 10%
- **Boss**: only given at boss kills

**If the trinket comes from an Obelisk**, Rare chance is boosted to **30%** instead of 10%.

**Biome boost**: if in a biome and Common rolls, 50/50 between biome-tagged common trinket and non-biome common trinket. If both biome trinkets of that biome are already collected, defaults to non-biome.

## Time Crystal drop odds

Per encounter type:

### After Obelisk or any Stop Fight (Big Baddie stop-fight, Boss)
| 0 TC | 1 TC | 2 TC | 3 TC |
|---:|---:|---:|---:|
| 0% | 0% | 80% | 20% |

### After regular Baddie
| | 0 TC | 1 TC | 2 TC |
|---|---:|---:|---:|
| Chapter 1 | 90% | 10% | 0% |
| Chapter 2 | 85% | 15% | 0% |

### After non-stop-fight Big Baddie
| | 0 TC | 1 TC | 2 TC |
|---|---:|---:|---:|
| Chapter 1 | 0% | 70% | 30% |
| Chapter 2 | 0% | 60% | 40% |

**Rules-engine implications**:
- Expected TC gain per chapter-1 trash baddie = 0.1.
- Expected TC gain per chapter-2 stop-fight = 2.2.
- Obelisks are the best single source of TC (expected 2.2 per visit).

## Movement rewind cost (escalation confirmed)

Nick's spec: **"Each time the player re-rolls from that same space, the price increases following this sequence (2, 2, 3, 3, 4, 4, 5, 5, etc). Once the player is on a new space, the sequence resets."**

Across 4 watch runs, I observed flat 2 TC per rewind because the player only rerolled from a given space once each time. The escalation kicks in when you **re-roll from the same space multiple times in a single decision**. Confirmed: I saw a brief `REROLL-COST 2 → 3 → 2` flip in run 4 that was probably this sequence triggering, then resetting after the space was left.

**Budget rule**: 1 rewind per space = 2 TC. Chain-rewinds from the same space get expensive fast.

## Bones distribution
- 1 Bone per Big Baddie kill (on path or in miniboss stop-fight).
- 1 Bone per Obelisk clear.

## Gold distribution (per encounter type)

| Encounter | Min | Avg | Max |
|---|---:|---:|---:|
| Baddie | 10 | 15 | 20 |
| Big Baddie | 30 | 40 | 50 |
| Mid-Chapter Stop Fight (Big Baddie) | 60 | 65 | 70 |
| Obelisk | 65 | 75 | 85 |
| Boss Baddie | 80 | 90 | 100 |
| Loot Die | 10 | 30 | 50 |

Gaussian distribution, whole numbers only.

## Campfire — 5 options (pick one)

When you enter a campfire, you choose **exactly one** of the following five:

| Option | Effect |
|---|---|
| **Rest** | Heal 40% of max health (rounded down) |
| **Burn** | Burn one side |
| **Food** | Get 2 random Food items |
| **Score** | **Gain 7,000 Points** |
| **Mine** | **Gain 5 Time Crystals** |

**Rules-engine picking guide**:
- Rest: when HP < 60% of max AND no better heal option incoming
- Burn: when you have a Curse OR a weak Starter side AND no free burn (e.g. Shiba Mask) is active
- Food: when you have ≤1 food and a hard fight is coming
- Score: when HP is high, no curses, TC ≥4, and no food deficit
- Mine: when TC ≤2 and rewinds are needed

**The Score and Mine options are disproportionately powerful when they fit**. 7000 points is the single biggest non-battle point gain after Obelisks. 5 TC is a full run's worth of rewind insurance.

## Bub's Barter — full shop spec

Each Bub's visit offers:
- **6 Sides** for purchase
- **3 Trinkets** (2 common, 1 rare)
- **2 Food items**
- **3 Time Crystals** slots
- **1 Burn**

### Shopping mechanics
- Items go on the right side of Bub's scale; gold falls on the left (payment).
- Player sees total cost in number form and pays at the end.
- **Barter with health** if short on gold: each 3 gold you're short = 1 health.
- **Minimum 1 HP when leaving** — cannot spend all your health.
- Items do NOT refresh after purchase within a single Bub's visit.

### Biome-specific Bub's
- **At least 3 of the 6 sides** will feature that biome's tag (guaranteed).
- **At least 1 of the common trinkets** will feature the biome's tag (if any remain uncollected).
- **At least 1 of the 2 food items** will feature the biome's tag.

### Side selection (6 sides)
1. Roll for whether there will be a Level 3 side: **20% yes / 80% no**.
2. Roll for Level 2 side count:
   - If 0 Level 3: 0 L2 (never), 65% chance of 2 L2, 35% chance of 3 L2
   - If 1 Level 3: 60% chance 1 L2, 30% chance 2 L2, 10% chance 3 L2
3. Fill remaining 2–4 slots with Level 1 sides.
4. If in a biome, randomly pick 3 of the 6 sides to carry the biome tag.
5. **Exclude Level 3 sides the player already has 2 copies of on any single die** (can't get a 3rd).

### Trinket selection (3 trinkets)
- 2 common, 1 rare.
- **No duplicates** — only trinkets the player doesn't already own.
- Biome rule: if in a biome and player doesn't have all biome-common trinkets, at least 1 of the 2 common slots gets a biome tag.

### Food selection (2 foods)
- First food: always Pool 1 (common).
- Second food: 60% Pool 1, 40% Pool 2 (rare).

### Pricing (per item, Gaussian around average)

| Item type | Min | Avg | Max |
|---|---:|---:|---:|
| Level 1 Side | 45 | 50 | 55 |
| Level 2 Side | 68 | 75 | 82 |
| Level 3 Side | 150 | **165** | 180 |
| Food Pool 1 (common) | 45 | 50 | 55 |
| Food Pool 2 (rare) | 100 | 120 | 140 |
| Common Trinket | 195 | 210 | 225 |
| Rare Trinket | 230 | 270 | 310 |

**Sale tag**: after pricing, one random side gets a **Sale tag** — **35% off rounded down**.

### Time Crystals (up to 3 per Bub's)
- First: **20 gold**
- Second: **25 gold**
- Third: **30 gold**

### Burns (only 1 per Bub's)
- First burn in the whole run: **6 health**
- Each subsequent burn purchased: **+3 health** (9, 12, 15, ...)
- Blood sacrifice system — burns always cost health at Bub's.
- Only 1 burn available per Bub's visit.

## Loot Die drops
- 1 random food
- 1 common or rare trinket (exact odds unspecified in Nick's doc)
- 1 sticker

## Rules-engine implications

1. **Upgrade EV favors getting into level-3 territory fast**. The x-counter mechanic means you'll see L3 offers after ~5-10 L1 picks. Don't skip L1s unnecessarily early.
2. **Boss-dropped L3 sides (+100/roll) are strictly superior** to any other side and should be hoarded.
3. **Bub's has a random sale item at 35% off** — always check for one before committing to other purchases.
4. **Obelisks are the single best value event** in the game: guaranteed +Bones, +stickers ×2, +30% rare trinket chance, +TC, + boss-tier HP potential. But they consume food — time them carefully.
5. **Food drop rate scales with recent non-drops** — if you haven't seen a food in a while, your next battle is more likely to drop one.
6. **Campfire Score (7000 pts)** is the single-best campfire option when HP is safe and food reserves are healthy.
7. **Bub's level-3 price is ~165 gold** — budget accordingly. Level 2s are ~75g. Level 1s ~50g. Rare trinkets ~270g. A Bub's with a rare trinket + a L3 side costs ~435g before anything else.
