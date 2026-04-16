# Map Design — Generation Rules

**Source**: Nick's `Map Design.html` (2026-04-13 database export). This is the exact map generation spec.

## Core facts

- **Movement die**: `1, 2, 2, 3, 3, 4` (EV = 2.5)
- **Chapter length**: **always 39 spaces** on the main path. Non-negotiable.
- **Stop fights**:
  - **Big Baddie at space 25** (first checkpoint / mini-boss)
  - **Boss Baddie at space 39** (second checkpoint / boss)
- **Campfires at 24 and 38** are **guaranteed** — placed right before each stop fight.
- **Chapter 3 exists** (mentioned in Obelisk rules). We have not seen chapter 3 content yet.

## Path structure

Each chapter has:
- A **main path** of 39 spaces (0–39, where 0 = start, 1–39 = encounters).
- Optionally **1 or 2 forked paths**, 6–15 spaces each.
- Total spaces including forks: up to ~60 on a 2-fork map.

Path flow within a chapter: always 25 main-path spaces to the first stop fight, then 14 more to the boss at 39.

## Encounter types and their rarity

| Encounter | Rarity | Multi-space sets? |
|---|---|---|
| Baddie | Common | No (single space) |
| Big Baddie | Medium | **Yes** (2-3 in a row) |
| Campfire | Medium | **Yes** |
| Mystery Event | Common | No |
| Loot Die | Rare | No |
| Obelisk | Medium | **Yes** |
| Bub's Barter | Medium | **Yes** |

## Guaranteed encounters

- **Campfire right before every Stop Fight** (at 24 and 38).
- **Big Baddie stop fight** in chapter 1 and 2.
- **Obelisk stop fight** in chapter 3.
- **Boss Baddies** at the end of every chapter and at checkpoint battles.

## Example path (Chapter 1, from Nick's spec)

Main (39 spaces) with a Forked Path (11 spaces merging back in):

```
 0: Start
 1: Baddie
 2: Baddie
 3: Mystery Event
 4: Mystery Event
 5: Baddie
 6: Mystery Event
 7: Loot Die
 8: Bub's Barter       / Fork: Campfire
 9: Baddie             / Fork: Campfire
10: Baddie             / Fork: Big Baddie
11: Campfire           / Fork: Bub's Barter
12: Campfire           / Fork: Bub's Barter
13: Big Baddie         / Fork: Baddie
14: Big Baddie         / Fork: Baddie
15: Mystery Event      / Fork: Mystery Event
16: Baddie             / Fork: Mystery Event   ← fork re-merges here (16-23)
17: Mystery Event      / Fork: Baddie
18: Baddie
19: Obelisk
20: Mystery Event
21: Bub's Barter
22: Baddie
23: Mystery Event
24: Campfire           ← MUST STOP
25: Big Baddie         ← STOP FIGHT
26: Mystery Event
27: Mystery Event
28: Baddie
29: Baddie
30: Mystery Event
31: Baddie
32: Obelisk
33: Obelisk
34: Campfire
35: Bub's Barter
36: Loot Die
37: Baddie
38: Campfire           ← MUST STOP
39: Boss Baddie        ← STOP FIGHT, CHECKPOINT
```

### Example totals breakdown

| Type | Main count | Fork count | Total | % of total |
|---|---:|---:|---:|---:|
| Baddie | 12 | 3 | 15 | 30% |
| Big Baddie | 3 | 1 | 4 | 8% |
| Boss Baddie | 1 | 1 | 2 | 4% |
| Campfire | 5 | 2 | 7 | 14% |
| Mystery Event | 10 | 2 | 12 | 24% |
| Loot Die | 2 | 0 | 2 | 4% |
| Obelisk | 3 | 0 | 3 | 6% |
| Bub's Barter | 3 | 2 | 5 | 10% |

**Imp the Simp**: 0 (unused placeholder, probably cut).

## Map generation algorithm

Nick's exact generation order. The rules engine can simulate this to generate maps.

### Step 1: Fixed anchors
- Set campfires at **24** and **38**.
- Set space **25** to Big Baddie (chapter 1/2) or Obelisk (chapter 3).
- Set space **39** to Boss Baddie.

### Step 2: Fork count + biomes
- Roll for **1 to 2 forks**.
- Pick 2–3 biomes randomly from the 3 available (Ice Cave, Toxic Swamp, Volcano).

### Step 3: Fork length + starting positions
- Length: **6 to 15 spaces** per fork.
- **Fork re-merge must occur in spaces 16–23.**
- Extend paths appropriately and create forks.
- Check: no entry points with 2 forks on the same space. If so, shift 1 fork by 1 space.

### Step 4: Campfires (additional to the guaranteed ones)
- **Must be placed in spaces 7–18.**
- At least **4 non-campfire spaces between campfire sets.**
- Frequency: **60% → 1 set / 30% → 2 sets / 10% → 3 sets**
- Set sizes:
  - If 1 campfire set: 0% size-1, 35% size-2, 65% size-3
  - If 2 campfire sets: sizes always (1, 1, 0)
  - If 3 campfire sets: sizes always (2, 1, 0)
- **If a campfire exists on main but the player will miss it via the fork**, place an equivalent campfire set on the fork.
- Finally, place **1 random campfire somewhere in spaces 34–37**.

### Step 5: Obelisks (additional)
- Set a **2-space Obelisk set at 32+33** (guaranteed for chapter 1+ runs).
- Then roll for additional obelisks based on chapter:
  - Ch 1: 90% 0 additional / 10% 1 additional
  - Ch 2: 50% 0 / 50% 1
  - Ch 3: 25% 0 / 75% 1
- Additional set sizes:
  - Ch 1: 80% size-1 / 20% size-2
  - Ch 2: 30% size-1 / 35% size-2 / 35% size-3
  - Ch 3: 0% size-1 / 50% size-2 / 50% size-3
- **Must be placed in spaces 15–21** for additional obelisks.
- Main path or fork at equal odds.

### Step 6: Big Baddies (additional to stop fight)
- Frequency by chapter:
  - Ch 1: 40% 1 set / 60% 2 sets / 0% 3 sets
  - Ch 2: 20% 1 / 70% 2 / 10% 3
  - Ch 3: 20% 1 / 60% 2 / 20% 3
- Set sizes:
  - If 1 Big Baddie set: 10% size-1 / 30% size-2 / 60% size-3
  - If 2 Big Baddie sets: 50/50 between size-1 and size-2
  - If 3 Big Baddie sets: sizes (2, 1, 1)
- **Must be placed in spaces 7–21.**
- At least **4 non-BigBaddie/non-Obelisk spaces between BB sets.**
- Main or fork at equal odds.
- **Max 1 Big Baddie set per fork.**

### Step 7: Loot Dice
- Frequency:
  - Ch 1: 40% 0 / 60% 1
  - Ch 2: 45% 0 / 55% 1
  - Ch 3: 50% 0 / 50% 1
  - *Special rule*: if no Loot Die placed before the first stop fight in ch1/2, one is **guaranteed in chapter 3**.
- Sets are always size-1 if 3 Big Baddie sets exist, else 50/50 size-1/size-2.
- **Must be placed in spaces 3–23.**
- If on main and missable via fork, place an equivalent on the fork.
- Finally, **place 1 additional Loot Die** on a random unoccupied space in 34-37.

### Step 8: Bub's Barter
- **Forked path first**:
  - 65% 0 Bub's / 35% 1 Bub's on the fork
  - Fork set sizes: 50% size-1 / 50% size-2
- **Main path**:
  - Ch 1+2: 70% 1 Bub's / 30% 2 Bub's
  - Ch 3: always 1
- Main set sizes:
  - If 1 Bub's: 40% size-1 / 50% size-2 / 10% size-3
  - If 2 Bub's: sizes always (2, 0, 0)
- **Must be placed in spaces 7–23.**
- **At least 6 spaces between Bub's.**
- Finally, **place 1 more Bub's** on a random unoccupied space in 34-37.

### Step 9: Baddie + Step 10: Mystery Event (fill remaining)
- Place 1 Baddie on an unoccupied space in 34-37.
- Of remaining main-path and fork spaces, **at least 55% filled with Baddies**, rest with Mystery Events.

## Key rules-engine takeaways

1. **Spaces 24 and 38 are always safe campfires.** Plan around them for healing + burn opportunities.
2. **Spaces 34-37 always contain one of each: extra campfire, extra loot die, extra Bub's, and one Baddie.** This is the "late-chapter cluster" and is always rich in options.
3. **Obelisks at 32-33 are guaranteed** in every map (base set). Plan TC/food surplus by space 30 to take them.
4. **Fork entry points are spaces 7–15** (rough range, since forks re-merge in 16-23 with length 6-15).
5. **Chapter 3** is a design target but hasn't been implemented in live builds yet (or hasn't been accessible to us). Nick's rules explicitly include it.
6. **Chapter 3 removes Big Baddie stop fights** and puts Obelisks as the stop fight at space 25.
7. **55% of filler spaces are Baddies**, so a typical chapter has ~12-15 random baddie fights. The rules engine should plan for damage across that many encounters.
8. **Chapter generation is seed-based but NOT deterministic from player state** — each run rolls a fresh map. Can't predict the next map from the current one.
