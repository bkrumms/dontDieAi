# Big Cheeze — Chapter 2 Boss (7 Modes)

**Source**: Nick's `Baddie Attack Patterns.html` rows 33-40.

Big Cheeze is the Chapter 2 boss. 700 HP, 2000 points for kill. On **turn 1**, Big Cheeze applies the **"Cheezy Glitch"** modifier which transforms him into one of 7 modes based on **the player's starting-dice Level 3 biome tags**.

## Mode selection

On turn 1, Big Cheeze counts the player's **Level-3 biome-tagged sides** (across all starting dice). Level 3 sides WITHOUT a biome tag (e.g. the `None` pool +30 sides) are **not counted**.

| Player's L3 biome majority | Big Cheeze mode | Color |
|---|---|---|
| Toxic Swamp | **Attack Mode** | red |
| Volcano | **Shield Mode** | light blue |
| Ice Cave | **Poison Mode** | green |
| Toxic + Volcano tied | **Melee Mode** | purple |
| Volcano + Ice Cave tied | **Outlast Mode** | turquoise |
| Ice Cave + Toxic tied | **Onslaught Mode** | orange |
| All 3 tied | **Mix (Balanced) Mode** | white |

**Key**: Big Cheeze always counters your dominant biome. If you went deep on Volcano sides, he switches to Shield mode. If you went Ice Cave heavy, he switches to Poison mode. Toxic Swamp heavy → Attack mode.

## All 7 attack patterns

Each mode is 700 HP, 2000 points. Turn 5 is always a **"reset phase"** that wipes your block and debuffs — plan accordingly.

### Attack Mode (red) — vs Toxic majority
"Molds itself into your starting dice's biome weakness"
- **T1**: Apply Cheezy Glitch
- **T2**: 20 dmg, 2 times (40 total)
- **T3**: 30 dmg + Block 10
- **T4**: 40 dmg + Block 10
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Gain 6 Negate Debuffs
- **T7+**: rand (repeat 7)
- **Rand pool**: 35% `25 dmg, 2 times` / 50% `50 dmg + Block 10` / 15% `+10 Strength, +10 Armor`

### Shield Mode (light blue) — vs Volcano majority
- **T1**: Apply Cheezy Glitch
- **T2**: Armor 15 + gain 5 Block at end of every turn
- **T3**: Block 20 + Poison 7
- **T4**: 40 dmg + Armor 10
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Exhaust 1 side on every die, set Damage Multiplier to 1x
- **T7+**: rand (repeat 7)
- **Rand pool**: 35% `Block 15 + Poison 7` / 35% `12 dmg, 4 times` / 30% `Exhaust one random die side`

### Poison Mode (green) — vs Ice Cave majority
- **T1**: Apply Cheezy Glitch
- **T2**: Poison 1, 5 times (5 total stacks)
- **T3**: Poison 5
- **T4**: Block 25 + Poison 3
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Exhaust any side containing "block"
- **T7+**: rand (repeat 7)
- **Rand pool**: 45% `Poison 6` / 35% `Block 20 + Poison 3` / 20% `30 dmg`

### Melee Mode (purple) — vs Toxic/Volcano tied
- **T1**: Apply Cheezy Glitch
- **T2**: 20 dmg + Block 20
- **T3**: +5 Strength, +5 Armor
- **T4**: 18 dmg, 2 times + Block 24
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Add 2 Exhaustion Curses to random dice
- **T7+**: rand (repeat 7)
- **Rand pool**: 35% `40 dmg + Block 30` / 45% `24 dmg + Poison 5` / 20% `Block 50 + Remove Debuffs`

### Outlast Mode (turquoise) — vs Volcano/Ice Cave tied
- **T1**: Apply Cheezy Glitch
- **T2**: Poison 5
- **T3**: gain 4 Armor at end of every turn + gain 4 Block at end of every turn
- **T4**: Freeze 5 + Poison 5
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Add 2 Poison Curses to random dice
- **T7+**: rand (repeat 7)
- **Rand pool**: 50% `Poison 2, 4 times` / 35% `Block 30 + Stack block 3 turns` / 15% `Exhaust 2 sides on random dice`

### Onslaught Mode (orange) — vs Ice Cave/Toxic tied
- **T1**: Apply Cheezy Glitch
- **T2**: 20 dmg + Poison 5 + Bleed 2
- **T3**: 12 dmg, 3 times
- **T4**: Poison 3 + 3 Strength
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Add 2 Bleed Curses to random dice
- **T7+**: rand (repeat 7)
- **Rand pool**: 40% `8 dmg, 4 times` / 40% `Poison 5 + 5 Strength` / 20% `Block 50 + Remove Debuffs`

### Mix / Balanced Mode (white) — vs all 3 tied
- **T1**: Apply Cheezy Glitch
- **T2**: 20 dmg + Block 20 + Poison 5
- **T3**: 35 dmg + Block 10 + Freeze 3
- **T4**: 7 dmg, 4 times
- **T5**: **Melt all Block + Remove all Debuffs**
- **T6**: Add Duplicator Curse to random die
- **T7+**: rand (repeat 7)
- **Rand pool**: 30% `Poison 2, 4 times` / 30% `Block 50 + Remove Debuffs` / 40% `40 dmg`

## Common patterns across all modes

1. **Turn 1**: Apply Cheezy Glitch (mode selection — no damage).
2. **Turn 5**: Always the "reset phase" — `Melt all Block + Remove all Debuffs`. Your defense setup is nuked.
3. **Turn 6**: Always a nasty unique mechanic (curses, exhausts, multiplier resets).
4. **Turn 7+**: Random rolls.

**The rules engine should plan to win by turn 4 or survive the turn-5 reset with enough HP to grind down the rest of the fight.** Turn-6 effects like "Exhaust 1 side on every die" or "Set Damage Multiplier to 1x" can cripple a burst build late.

## Rules engine implications

1. **Pre-fight biome check**: count Level 3 biome tags on starting dice → predict Big Cheeze mode → select counter-strategy food/trinkets.
2. **Best counter per mode**:
   - **Attack Mode**: bleed-immune trinket (Ket Mask) + healing food. High raw damage coming.
   - **Shield Mode**: burst damage (not sustained — the armor stacks). Ignore the poison.
   - **Poison Mode**: cure poison sides or Ice Rice for debuff negation. Also Lizard Mask is useless here (he's already poisoning you, not the other way around).
   - **Melee Mode**: Bleed Immune + Bleed-resist build. Fast kill preferred.
   - **Outlast Mode**: heavy burst before T3, otherwise the Armor/Block stacking kills you.
   - **Onslaught Mode**: Ice Rice pre-fight to negate the turn-2 triple debuff.
   - **Mix Mode**: balance. Nothing is specifically countered. Raw Power is best.
3. **Dice composition strategy**: if you want to force a specific Big Cheeze mode, you can intentionally stock Level 3 sides of one biome type. This is a powerful predictive tool — **build toward a mode you have the food/trinkets to counter**.
4. **Anti-tilt rule**: `Scoring` trinket (7,777 for 3-turn win) is **not viable** against Big Cheeze because he can't be killed by turn 3 (he doesn't even attack until turn 2 in most modes, and 700 HP in 3 turns = 233 dmg/turn burst which is borderline impossible).
