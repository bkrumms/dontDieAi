# Baddies — Full Reference (with Attack Patterns)

**Source**: Nick's `Baddie Attack Patterns.html` + `Encounter Loot.html` (2026-04-13 database export). This replaces the earlier reference which was derived from screenshot descriptions.

## How to read attack patterns

- **Health** is ±2 variance around the listed value (equal odds range).
- Each baddie has a scripted sequence of attacks (T1, T2, T3...).
- Some baddies have **random slots** — on certain turns they roll from a weighted list. Listed as `rand` with the Rand pool weights.
- `(repeat X-Y)` means after turn N, cycle through turns X-Y again.
- `N, M times` means the attack hits M separate times for N damage each.
- Attack modifiers (Bleed, Poison, Freeze, Strength, Block, Armor, Heal) follow standard rules — see `knowledge/game/status-effects.md`.

## Chapter 1 — Common Baddies

### Ice Pufflet — 32 HP, 100 pts
- **T1**: Freeze 2
- **T2**: 8 damage
- **T3+**: rand (repeat)
- **Rand pool**: 40% `8 dmg + Freeze 2` / 30% `+3 Strength` / 30% `12 dmg`

### Black Firant — 9 HP, 100 pts
Lowest HP in the game. Goes down fast.
- **T1**: 6 dmg + Bleed 1
- **T2**: 10 dmg
- **T3**: 14 dmg + Bleed 2
- **T4**: +8 Strength
- **T5+**: repeat 1-4

### Blue Firant — 24 HP, 100 pts
Exhausts your dice — dangerous early.
- **T1**: 6 dmg + Block 6 (self)
- **T2**: **Exhaust 1 Side randomly**
- **T3+**: rand (repeat)
- **Rand pool**: 55% `9 dmg + Block 9` / 15% `Exhaust 1 Side` / 30% `6 Strength + 3 Armor`

### Baby Scarebug — 22 HP, 100 pts
Linear poison ramp.
- **T1**: Poison 1
- **T2**: Poison 1
- **T3**: Poison 2
- **T4**: Poison 3
- **T5+**: Poison 4 (locks at 4)

### Frostmaul — 36 HP, 200 pts
**Special**: Stacks Block forever.
- **T1**: Block 20
- **T2**: Block 8
- **T3**: `Attack = Block` (hits for whatever block it currently has)
- **T4-5**: rand (repeat 1-4)
- **Rand pool**: 70% `12 dmg + Freeze 3` / 30% `12 dmg + Block 12`

### Cobra Frier — 36 HP, 200 pts
- **T1-2**: rand
- **T3**: +4 Strength
- **T4+**: repeat 1-3
- **Rand pool**: 50% `8 dmg + Bleed 2` / 50% `14 dmg`

### Kevin — 44 HP, 200 pts
Rehealth boss for a trash baddie.
- **T1**: Rehealth all 14
- **T2**: 16 dmg
- **T3**: 12 dmg + Rehealth all 10
- **T4**: Block 30
- **T5+**: repeat 1-4

### Lil Zomboid — 40 HP, 200 pts
- **T1**: rand
- **T2**: Poison 1
- **T3**: 8 dmg
- **T4**: rand
- **T5+**: repeat 1-4
- **Rand pool**: 50% `Freeze 2 + Bleed 2` / 50% `8 dmg`

### Rock Lobster — 38 HP, 200 pts
**Special**: Stacks Block forever.
- **T1**: 16 dmg
- **T2**: Block 20
- **T3**: Block 15
- **T4**: 10 dmg + Block 10
- **T5**: 5 Strength + 5 Armor
- **T6+**: repeat 1-5

## Chapter 1 — Big Baddies

### Wendibrrr — 96 HP, 500 pts
**Special**: Can't be Frozen. Curses you twice.
- **T1**: Add random Curse to random die
- **T2**: Block 20 + Freeze 7
- **T3**: 16 dmg + Block 6
- **T4**: 20 dmg
- **T5**: Add random Curse
- **T6**: +10 Strength
- **T7+**: repeat 3-6

### Firant Queen — 68 HP, 500 pts
Grinding damage with rehealth.
- **T1**: 8 / **T2**: 12 / **T3**: Rehealth all 12 / **T4**: 8 / **T5**: 12 / **T6**: +6 Strength / **T7+**: repeat 4-6

### Gorgon-zola — 80 HP, 500 pts
**Special**: When afflicted with Bleed or Freeze, also afflict Hero (reflection).
- **T1**: Poison 3
- **T2**: Block 24
- **T3**: 18 dmg
- **T4**: Poison 3
- **T5**: +6 Strength + 6 Armor
- **T6**: Block 24
- **T7**: Poison 3
- **T8**: 18 dmg
- **T9+**: repeat 5-8

## Chapter 1 — Boss

### Ganondwarf — 160 HP, 1000 pts
"All Modifiers. High Damage." — explains it well.
- **T1**: **Freeze 4 + Bleed 3 + Poison 2** ← this is why Ice Rice (negate 3 debuffs) wins
- **T2**: 14 dmg
- **T3**: 8 dmg, 2 times (16 total)
- **T4**: 12 dmg, 2 times (24 total)
- **T5**: Block 20 + 8 Strength
- **T6+**: repeat 2-5

**Confirmed winning strategy (run 4)**: Pre-fight Ice Rice negates the turn-1 triple debuff stack, neutralizing his damage spike. Without Ice Rice (run 2), freeze weakens block and bleed amplifies damage, resulting in a turn-1 one-shot.

## Chapter 2 — Common Baddies

### Haunt — 52 HP, 300 pts
**Special**: Gains Negate Damage (hard blocks your attacks).
- **T1**: Gain 4 Negate Damage
- **T2**: Add random Curse to random die
- **T3**: 7 dmg, 2 times + 2 Strength
- **T4+**: rand (repeat)
- **Rand pool**: 50% `7 dmg, 2 times + 2 Strength` / 30% `Gain 2 Negate Damage` / 20% `Add random Curse`

### Crystal Zomboid — 42 HP, 300 pts
**Special**: Eats 2 Time Crystals on turn 4. Kill before turn 4 or lose TCs.
- **T1-3**: rand (low damage)
- **T4**: **Eat 2 Time Crystals**
- **T5**: Strength 20 (!)
- **T6+**: rand
- **Rand pool**: 25% `4 dmg` / 40% `6 dmg` / 25% `8 dmg` / 10% `Strength 10`

### Frigid Interloper — 56 HP, 300 pts
**Special**: Starts with 20 Block. Stacks Block. Ice Glitch modifier freezes a random die at start of every turn (that die can't roll that turn).
- **T1**: Apply Ice Glitch modifier
- **T2**: 18 + Freeze 2 / **T3**: Block 20 / **T4**: 18 + Block 10 / **T5**: Block 10 + Freeze 2 / **T6**: 20 / **T7**: 30 / **T8**: 40 / **T9**: 50 / **T10+**: repeat 9 (scales forever)

### Lavamander — 116 HP, 300 pts (highest-HP common)
**Special**: Melts Block (removes all block to 0).
- **T1**: 2 dmg, 5 times (10 total)
- **T2**: Melt all player Block
- **T3**: +3 Strength
- **T4**: 2 dmg, 5 times
- **T5**: Melt all player Block
- **T6**: +5 Strength
- **T7**: 2 dmg, 5 times
- **T8+**: repeat 6-7 (scaling strength indefinitely)

### Jellire — 42 HP, 300 pts
Loop of one attack forever.
- **T1+**: 6 dmg + 4 Strength (repeat)

### Batty — 22 HP, 300 pts (low HP, brutal sustain)
**Special**: Heals 6 with every attack.
- **T1+**: rand (repeat)
- **Rand pool**: 40% `8 dmg + Heal 6` / 30% `6 dmg + Poison 2 + Heal 6` / 30% `6 dmg + Bleed 2 + Heal 6`

### Snowfang Pack — 72 HP, **400 pts**
**Special**: `Strength All Snowfang Pack` (entire pack gains strength collectively).
- **T1+**: rand (repeat)
- **Rand pool**: 30% `14 dmg` / 35% `4 dmg, 2 times` / 25% `Strength All Pack +2` / 10% `Strength All Pack +3`

### Jellame — 164 HP, 400 pts (high HP for a common)
**Special**: Summoner. Exhausts random sides.
- **T1**: 16 dmg
- **T2**: Exhaust random Side
- **T3**: 20 dmg
- **T4**: Summon (fill empty slots with Jellires)
- **T5**: Exhaust random Side
- **T6**: 30 dmg
- **T7**: Exhaust random Side
- **T8**: Summon
- **T9**: 60 dmg
- **T10+**: repeat 9

### Noxious Interloper — 88 HP, 400 pts
**Special**: Cures Poison (Toxic Glitch modifier — cures all poison at end of every turn).
- **T1**: Apply Toxic Glitch modifier
- **T2**: Block 18 + Poison 6
- **T3**: 14 dmg + Block 12
- **T4**: 10 dmg + Poison 3
- **T5+**: repeat 3-4

## Chapter 2 — Big Baddies

### Pterrordactyl — 280 HP, 800 pts (highest HP in the game outside bosses)
**Special**: Starts with 3 Negate Debuffs (Ice Rice effect). Gains Negate Debuffs. Removes Debuffs. Steals Armor.
- **T1**: 24 dmg
- **T2**: Block 40
- **T3**: Steal all player armor
- **T4**: 30 dmg + Block 5× current turn
- **T5**: Remove debuffs + Add 3 Negate Debuffs
- **T6**: 30 dmg + Block 10
- **T7**: Steal all player armor
- **T8**: 24 dmg + Block 5× current turn
- **T9**: 40 dmg + Block 10
- **T10+**: repeat 7-9

**Rules**: Don't bother with Freeze/Bleed/Poison — he negates all debuffs. Pure raw damage + Strength stacking.

### Detonox — 240 HP, 800 pts
**Special**: Gains 3 Strength every time it loses HP (Rage Shake effect). **Explodes on turn 7** for 100 damage and ends the battle.
- **T1**: Bleed 3 / **T2**: Bleed 2 / **T3**: Bleed 1 / **T4**: 12 / **T5**: 12 + Bleed 3 / **T6**: 1 dmg, 3 times / **T7**: **100 damage self-destruct**

**Rules**: **Must kill by turn 6.** Rage Shake on every hit means big burst damage BUILDS his strength — use sustained medium hits or a single 240+ burst turn. Avoid Scorch Sauce / multi-hit builds against him.

### Deathbat — 144 HP, 800 pts
**Special**: Summoner. Heals 70 on turn 6 after a big hit.
- **T1**: Summon Battys
- **T2**: 6 dmg / **T3**: +6 Strength / **T4**: Summon / **T5**: 6 dmg
- **T6**: **34 dmg + Heal 70**
- **T7**: Summon / **T8**: +10 Strength / **T9**: 6 dmg / **T10+**: repeat 8-9

**Rules**: Kill by turn 5 or be ready to deal >70 dmg on turn 6 to out-damage the heal.

## Chapter 2 — Bosses

### Big Cheeze — 700 HP, 2000 pts — has 7 modes
See [`boss-big-cheeze.md`](boss-big-cheeze.md) for all 7 attack patterns. Big Cheeze **molds to counter the player**: turn 1 applies the "Cheezy Glitch" modifier that changes his form based on the player's starting-dice Level 3 biome tags:
- Volcano majority → Shield mode
- Ice Cave majority → Poison mode
- Toxic Swamp majority → Attack mode
- Tied biomes → mixed modes (Melee, Outlast, Onslaught, Balanced)
- Level 3 sides without biome tags are **not considered** in the majority calculation.

This means **your pre-fight dice composition determines the boss pattern you face**. Rules-engine note: tracking Level 3 biome tags on the player's dice and predicting which Big Cheeze mode will trigger is a priority feature.

### Zomboid Horde — 2000 pts total
A chapter 2 boss fight consisting of a **sequential party** (5 zomboids fought one-at-a-time):
1. **Lil Zomboid** (40 HP) — same as ch1
2. **Crystal Zomboid** (42 HP) — eats TCs
3. **Infernal Zomboid** (116 HP, 600 pts) — gains +4 Strength at turn end, exhausts one random side every turn
4. **Necrotic Zomboid** (154 HP, 600 pts) — heals 8 at turn end, poison heavy
5. **Cryonic Zomboid** (190 HP, 600 pts) — gains +4 Armor at turn end, Block + Freeze combo

Total horde HP: ~542 across 5 fights. Individual kills score 200+600+600+600+600 = 2600 kill points on top of the boss bonus.

## Battle selection algorithm

Baddie spawns follow **battle pools** by space range:

| Chapter 1 | Space range |
|---|---|
| B Fights 1 | Spaces 1–5 |
| B Fights 2 | Spaces 6–13 |
| B Fights 3 | Spaces 14–23 |
| B Fights 4 | Spaces 24–39 |

Within each pool, fights are filtered by the current biome:
1. If in a biome, try biome-specific fight first.
2. If no biome fight remaining (or no biome), pull from Neutral fights.
3. If all biome+neutral exhausted, reset the pool and pick again.
4. **Fights don't repeat within a pool** until a reset.

Same structure applies to chapter 2 (pools 1-4 by space range).

Big Baddies have their own pools (Wendibrrr for Ice Cave ch1, Black Firant×2 + Firant Queen + Blue Firant for Volcano ch1, Gorgon-zola for Toxic Swamp ch1, etc.). See `data/raw/nick_db/Baddie_Attack_Patterns.tsv` rows 47-89 for the full fight tables.

Obelisk fights have their own baddie pools (chapter 1 obelisk fights are a mini-pool; chapter 2 has 2 obelisk fights back-to-back). See the same TSV for details.

## HP variance rule

Per Nick: "Health (equal odds range, **+/−2**)" — every baddie's HP roll is its listed value ±2 with uniform distribution. So Ice Pufflet can spawn with 30/31/32/33/34 HP each at 20% odds. The rules engine should use the listed value as the expected HP and add ±2 as the range when calculating kill turns.
