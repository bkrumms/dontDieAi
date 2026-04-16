# Sides (Dice Faces) — Full List

Source: [Don't Die Full Game Database Google Sheet](https://docs.google.com/spreadsheets/d/1kxLe6JPYK9Ku0SNvSRFePrDW53DYBc9jPq_ms9KEMkw/edit) — `Sides` tab.
Raw data: [`sides.csv`](sides.csv)

**Total sides documented: 75** (Notion FAQ says "60+ currently, up to 80+ at final design" — so ~5–15 more may be added).

## Columns

| Column | Meaning |
|---|---|
| `pool` | Which pool the side comes from. Pools appear to correspond to upgrade *tiers* offered after different battle difficulties. |
| `biome` | Biome gate — `None` means available in every biome. Otherwise `Ice Cave` / `Toxic Swamp` / `Volcano`. |
| `effect` | Human-readable effect text from the sheet. |
| `exhaust` | Whether the side **exhausts** (one-time use per battle). |

## Pools = points-per-roll

The `(+N)` label on a side is the **base points the player scores every time that side is rolled**, on top of any "Score N Points" effect the side's text adds. It is *not* a difficulty gate.

- A `(+30)` side rolled 5 times in a battle = **+150 points** from the base alone, before any effect fires.
- A die with four `(+30)` sides that rolls once per turn over an 8-turn battle = **+240 base points** from that die alone.

| Pool | Base points / roll | Count | Notes |
|---|---:|---:|---|
| Starter | +10 | 8 | Baseline dice faces — already scoring from turn 1. |
| (+10)   | +10 | 22 | Same per-roll value as Starter; pick for the effect, not the points. |
| (+20)   | +20 | 19 | Mid-value upgrade pool. |
| (+30)   | +30 | 16 | Top-value upgrade pool. |
| Echo Dagger | +30 | 1 | Scores like a top-tier upgrade on every roll, PLUS the "if fatal, attack again" effect. |
| Curse   | 0 or negative | 9 | Some curses actively subtract points (`Lose 50 Points`, `Lose 100 Points`). |

### Rules-engine implications

1. **A fresh 4-side Starter die always scores +40 per roll just for existing.** Across a run, that's a huge floor — starters are not "worthless".
2. **`(+10)` upgrades don't improve points-per-roll over Starters.** Their value is purely the *effect*. If the effect is weak, skip — you're just adding variance for no scoring upside.
3. **Upgrade EV is roughly checkpoint-inverse.** A `(+30)` picked at checkpoint 1 rolls far more times across the rest of the run than the same `(+30)` picked at checkpoint 4, so early-run upgrade value >> late-run.
4. **Burning should target the lowest base value first.** Once a die has any `(+20)` or `(+30)` sides, every Starter/`(+10)` side on it is a scoring drag. Burn those, not the top-tier ones.
5. **"Duplicate this Side" on Volcano `(+10)`** (`Attack 16, Duplicate this Side onto this Die`) turns one `(+10)` slot into two — +10 additional per-roll AND a second Attack-16. Very strong in early chapters.
6. **Echo Dagger is a top-tier scoring side** disguised as a utility — at `+30` per roll PLUS a finishing-blow effect, it's worth protecting via burn priority.
7. **Curses lose points two ways**: the side gives 0/negative, AND it displaces what could be a `(+30)` slot. Burn cost is almost always cheaper than tolerating the slot.
8. **Scoring-multiplier sides** (`Increase Points by 1x / 3x`) multiply the base per-roll points too — pair them with fully-upgraded dice for the biggest multiplier payoff.

## Biome distribution (non-`None` sides)

| Pool | Ice Cave | Toxic Swamp | Volcano |
|---|---:|---:|---:|
| (+10) | 5 | 5 | 3 |
| (+20) | 5 | 6 | 4 |
| (+30) | 2 | 4 | 4 |

Swamp is the broadest biome pool, Volcano the narrowest at the low tiers.

## Starter sides (baseline)

These 8 sides are what a fresh die carries — any upgrade is layered on top.

| Effect | Exhaust |
|---|---|
| Attack 4 | No |
| Attack all 4 | No |
| Attack 6, Bleed 2 | No |
| Gain 3 Strength | Yes |
| Poison 3 | No |
| Block 6 | No |
| Freeze all 3, Block 10 | Yes |
| Gain 3 Armor | Yes |

**Archetypes represented**: single-target attack, AoE attack, bleed, buff (strength), poison, block, CC+block, armor buff.

## (+10) sides

### None (always available)
| Effect | Exhaust |
|---|---|
| Attack 14, Gain 2 Strength | No |
| Attack all 10 | No |
| Block 3 anytime you Attack | Yes |
| Block 5 at the end of each turn | Yes |
| Block 8 per Baddie | No |
| Block 24 if you have no Block | No |
| Score 3 Points times Attack on this Die | No |
| Score 2 Points times the current Health of All Baddies | No |
| Score 100 Points any time you Block | Yes |

### Ice Cave
| Effect | Exhaust |
|---|---|
| Attack 12, Freeze 3 | No |
| Attack 10. If Baddie is Freezing, Attack +20 | No |
| Block 8, Gain 1 Armor | No |
| Block 8 per Freeze or Bleed on you. Otherwise, Block 10 | No |
| Block 3 times the current turn | No |

### Toxic Swamp
| Effect | Exhaust |
|---|---|
| Poison 8, Heal 1 | No |
| Poison 4, 2 times | No |
| Poison all 4 | No |
| Block 8, Poison 3 | No |
| Heal 2 at the end of each turn | Yes |

### Volcano
| Effect | Exhaust |
|---|---|
| Attack 2 per Attack Side on this Die | No |
| Attack 16, Duplicate this Side onto this Die | Yes |
| Block 8, Bleed 3 | No |

## (+20) sides

### None
| Effect | Exhaust |
|---|---|
| Attack 6, 2 times | No |
| Block 18. Score 50 Points | No |
| Score 100 Points per Trinket you have | Yes |
| Score 1 Point per the collective Points all your Dice are worth | Yes |

### Ice Cave
| Effect | Exhaust |
|---|---|
| Attack 16, Bleed 2, Freeze 2 | No |
| Block equal to your largest Attack value on this Die | No |
| Block 2. Permanently increase the Block gained on this Side by 4 | Yes |
| Stack Block for 3 turns | No |
| Gain 2 Armor at the end of each turn | No |

### Toxic Swamp
| Effect | Exhaust |
|---|---|
| Attack 4. Heal equal to unblocked Damage | Yes |
| Poison all 2, 3 times | Yes |
| Freeze all 3, Bleed 4, Poison 5 | Yes |
| All Baddies lose 15 Strength this turn | Yes |
| Remove all debuffs | No |
| Heal 8 after the battle | Yes |

### Volcano
| Effect | Exhaust |
|---|---|
| Exhaust an Attack 4 on each Die, do it's collective Attack | Yes |
| Attack 16. Permanently increase the Attack on this Side by +2 | Yes |
| Attack 28 | No |
| Gain 4 Strength at the end of each turn | No |

## (+30) sides

### None
| Effect | Exhaust |
|---|---|
| Increase Damage by 2x next turn | No |
| Increase Points by 1x | Yes |
| Increase Points by 3x. Every turn, decrease Points by 1x | Yes |
| Copy the next Die's effect | No |
| Re-roll your rightmost Die every turn | Yes |
| Increase the values on all other Dice by 1 | No |

### Ice Cave
| Effect | Exhaust |
|---|---|
| Block 40 | Yes |
| Negate Damage 2 times | Yes |

### Toxic Swamp
| Effect | Exhaust |
|---|---|
| Increase all values on this Die by 3 | Yes |
| 2x Poison | No |
| Poison All 1 whenever you Block | Yes |
| Cure Poison at the start of your turn | Yes |

### Volcano
| Effect | Exhaust |
|---|---|
| Attack all 32. Exhaust a Side on this Die | Yes |
| All Bleed 5, Re-roll this Die | Yes |
| Increase Damage by 1x. Anything rolled has 33% chance of Exhausting | Yes |
| 2x the values on 3 random Sides of this Die | Yes |

## Echo Dagger (special)

| Effect | Exhaust |
|---|---|
| Attack 22. If fatal, Attack again | No |

This side is what the **Echo Dagger** mystery event grants — see `knowledge/game/mystery-events.md` and `POST /api/game/mystery/echo-dagger`.

## Curse sides

Negative sides added to your dice by enemy effects or bad outcomes. All are in the `None` biome pool (apply anywhere).

| Effect | Exhaust |
|---|---|
| Lose 50 Points | No |
| Lose 100 Points | No |
| Lose 2 hp | No |
| Poison self 1 | No |
| Freeze self 2 | No |
| Bleed self 1 | No |
| Exhaust a random Side on this Die | Yes |
| Decrease all values by 1 on this Die | Yes |
| Duplicate this Side on this Die | No |

**"Duplicate this Side on this Die"** is particularly nasty — it compounds by making itself more likely to roll again. Strong signal that the rules engine should prioritize **burning curse sides** at any burn opportunity (campfire, Bub's, Freezer Burn, Infinidieferno).

## Keyword glossary

Status-effect definitions are now canonical — see [`../status-effects.md`](../status-effects.md) for the full reference. Short form:

| Keyword | Meaning |
|---|---|
| **Attack N** | Deal N damage to the current target. |
| **Attack all N** | Deal N damage to every baddie. (Gold outline in UI.) |
| **Attack +N** | Conditional bonus damage on top of a base. |
| **Block N** | Gain N block this turn. |
| **Block N at the end of each turn** | Passive end-of-turn block generator. |
| **Gain N Armor** | **Armor buffs future Block** — Block values on subsequent turns are stronger. Persistent. |
| **Gain N Strength** | **Strength buffs future Attacks** — Attack values on subsequent turns are stronger. Persistent. Likely flat +N to attack values (confirm). |
| **Poison N** | Apply N poison stacks. Baddie takes damage equal to poison at end of turn. Persistent. |
| **Poison all N** | AoE poison. |
| **Poison self N** | Curse side — applies poison to *you*. |
| **Bleed N** | Apply bleed. **Target takes 50% more damage while bleeding.** |
| **Freeze N** | Apply freeze. **Target's attacks and blocks are 25% weaker while frozen.** |
| **Freeze all N** | AoE freeze. |
| **Heal N** | Restore N HP. |
| **Score N Points** | Flat point gain. |
| **Increase Damage by Nx** | Damage multiplier for a window. |
| **Increase Points by Nx** | Points multiplier for a window. |
| **Exhaust** | One-time use per battle (Yes column). |
| **Re-roll this/the rightmost Die** | Reroll effect on the selected die. |
| **Copy the next Die's effect** | Mirror the next die's rolled face. |
| **Duplicate this Side onto this Die** | Adds another copy of the same side. Great on strong sides, disastrous on Curses. |
| **Negate Damage N times** | Hard ignore the next N incoming damage events. |
| **Permanently increase …** | Buff persists for the rest of the run once triggered. |

### Visual UI cues (from the dice-explainer image)

- **Red border** → La Volcano biome side.
- **Blue border** → Ice Cave biome side.
- **Green border** → Toxic Swamp biome side.
- **No colored border** → biome-neutral (None pool). Some of the most powerful sides have no border.
- **Gold outline on the main effect** → hits ALL baddies (AoE).
- **Black triangles on all 4 corners** → the side **exhausts** after one use.
- **Purple background/border** → **Curse**. The game explicitly tells players to burn these.

### Label prefixes (observed in live API data)

In-game side labels carry a one-letter prefix for certain behaviors:

| Prefix | Meaning | Example |
|---|---|---|
| `(e)` | **Exhausts after one use in a battle.** Shown on upgrade-tier sides whose exhaust behavior isn't obvious from text. | `(e) Attack 16. Permanently increase the Attack on this Side by 2` |
| `(p)` | **Persistent / passive.** The effect triggers every turn the side is alive on the die, not just when rolled. Still carries `exhaust: true` in the API — the effect ticks until exhausted by some trigger. | `(p) Gain 4 Strength at the end of each turn` |

**Note**: Starter-tier sides like `Gain 3 Strength` also exhaust (`exhaust: true`) but do **not** show an `(e)` prefix in their label. The prefix seems reserved for upgrade-tier sides. Confirm pattern with Nick.

### API tag system

Each side ability in the live API carries a `tags` array. Observed tag labels:

| Tag | Meaning |
|---|---|
| `Starter` | Baseline starter side. Matches our `Starter` pool. |
| `Level 1` | Matches our `(+10)` pool. |
| `Level 2` | Matches our `(+20)` pool. |
| `Level 3` | Matches our `(+30)` pool. *(inferred — not yet observed live)* |
| `Curse` | Curse pool. |
| `Ice Cave` / `Toxic Swamp` / `Volcano` | Biome affiliation. |
| `FTUE` | First-time user experience. Flags sides that can appear in the tutorial run. |

Sides typically carry multiple tags — e.g. `["FTUE", "Level 2", "Volcano"]` for a Volcano-biome (+20) side. The rules engine can match on `Level N` + biome tag combinations to determine the pool unambiguously.

### Data reliability

The CSV dump from the Notion-linked Google Sheet is **stale in places**. When a side label or exhaust flag disagrees with a live API observation, **trust the live observation** and update the CSV. Known corrections from run 1 (2026-04-13):

- `"Freeze all 3, Block 10"` → `"(e) Block 10, Freeze All 3"` (order + prefix)
- `"Attack 6, Bleed 2"` → `"Attack 6 Bleed 2"` (no comma)
- `"Attack all 4"` → `"Attack All 4"` (capitalization)
- `"Poison all 2, 3 times"` → `"(e) Poison all 3, 3 times"` (value: 2 → 3)
- `"Attack 16. Permanently increase the Attack on this Side by +2"` → `"(e) Attack 16. Permanently increase the Attack on this Side by 2"` (prefix + no `+`)
- `"Gain 2 Armor at the end of each turn"` → `"(p) Gain 2 Armor at the end of each turn"` + **exhaust No→Yes**
- `"Gain 4 Strength at the end of each turn"` → `"(p) Gain 4 Strength at the end of each turn"` + **exhaust No→Yes**
- `"Exhaust a random Side on this Die"` → `"(e) Exhaust a random other Side on this Dice"`

## Rules-engine starter heuristics (rough)

These are seed ideas to turn into concrete code later — not final rules.

1. **Never skip a burn on a Curse side.** Compound cost of leaving one is too high, especially "Duplicate this Side".
2. **Biome targeting by current need.** If HP ≤ 40% → Toxic Swamp for heals / debuff removal. If dice have no block → Ice Cave. If you're trying to break a damage check → Volcano.
3. **Archetype locking by chapter.** In chapter 1 favor raw damage and survival (Attack/Block); in chapter 2 the big multiplier sides (`Increase Damage by 2x next turn`, `Score 3 Points times Attack on this Die`) start paying off.
4. **Exhaust math.** An exhausting side with +20/+30 effect is worth it on the first 1–2 dice in the roll order (they fire first, so exhausted state next turn matters less). Less valuable on die #4.
5. **Consistency vs. power tradeoff.** Each added side decreases consistency. A rough threshold: don't grow a die past 6 sides unless the new side is at least +20 tier AND synergizes with another side already on that die.

## Unknowns / TODO

**Resolved** (from the Notion images):
- ✅ Block vs. Armor — Block is one-turn; Armor makes future Block stronger (persistent).
- ✅ Freeze mechanics — frozen target's Attack AND Block are 25% weaker. Not a turn-skip.
- ✅ Strength mechanics — makes future attacks stronger (persistent buff, additive).
- ✅ Poison mechanics — end-of-turn HP tick equal to current poison; persistent until cured.
- ✅ Curses are marked purple in the UI; "burn these off" is explicit in-game advice.

**Still open:**
- [x] ~~Confirm what `(+10)/(+20)/(+30)` represents~~ — base points the player scores every time the side is rolled. Confirmed by user.
- [x] ~~Starter / Echo Dagger base points~~ — Starters score +10 per roll; Echo Dagger scores +30 per roll. Confirmed by user.
- [ ] Confirm whether "Score 100 Points any time you Block" triggers per Block event, per side, or per turn.
- [ ] **Data discrepancy**: the "Database Feb" image shows Echo Dagger as "Attack 24" and the "No Biome" side as "Attack 12, Gain 4 Strength", but the current CSV has "Attack 22" and "Attack 14, Gain 2 Strength". CSV was pulled live today so it's likely newer — treat CSV as authoritative but confirm with Nick when values look wrong.
- [x] ~~Pull baddies, food, trinkets into `database/`~~ — see `baddies.md`, `food.md`, `trinkets.md`.
