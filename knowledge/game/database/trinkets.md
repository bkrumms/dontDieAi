# Trinkets

Trinkets = **permanent passive items** acquired during a run. They trigger automatically in battle and persist through the entire run. See also `game/food-trinkets.md` for the gameplay overview.

Source: "Feb Food + Trinkets" image. Raw data: [`trinkets.csv`](trinkets.csv)

## Common

| Name | Effect |
|---|---|
| Ket Mask | Bleed immune |
| Pudgy Mask | Freeze all 3 at the start of battle |
| Lizard Mask | Poison all 4 at the start of battle |
| Amulet of Yendor | Every time you Heal, Heal 1 more |
| Sunstone | Increase Damage by 1x for turn 1 |
| Kronicles Mask | Freeze immune |
| Snake Skull | Any time you deal Poison, deal 2 more |
| Noggles | Heal 5 after battle |
| Turtle Shell | If there are 3 or more Baddies, your first Attack hits All |
| Pet Hooligan Mask | Big Baddies start with 20% less health. (not active for Obelisks) |

## Rare

| Name | Effect |
|---|---|
| Fairy in a Bottle | If you die, instantly revive to 30% Health, then lose this Trinket |
| Joker Card | Increase Points by 1x on odd turns only |

## Boss

Dropped by boss fights. Strongest tier.

| Name | Effect |
|---|---|
| Bird Mask | Gain 2 Strength at the start of each turn |
| Shiba Mask | Exhaust 1 Curse at the start of each turn |
| Idol of Immunity | The first time you would die each battle, retain 1 Health and survive |
| Quadforce | Your first 4 turns, re-roll a random die |

## Archetypes and rules-engine hints

| Archetype | Trinkets |
|---|---|
| **Immunity** | Ket Mask (Bleed), Kronicles Mask (Freeze). Immediately obviates the corresponding enemy strategy — grab these without hesitation. |
| **Pre-battle tempo** | Pudgy Mask, Lizard Mask, Sunstone. Free value on turn 1. |
| **Heal scaling** | Amulet of Yendor (adds to heals), Noggles (post-battle top-up). Stack both if you find them. |
| **Poison scaling** | Snake Skull (+2 per poison). Auto-pick in a Toxic Swamp run. |
| **Survival / revive** | Fairy in a Bottle (rare), Idol of Immunity (boss). Both are death-skip mechanics. Idol is strictly better — it retriggers per battle. |
| **Points farming** | Joker Card (odd turns). Strong in long fights where you control the turn count. |
| **Curse cleansing** | Shiba Mask (boss) — auto-burns one Curse per battle. Removes the "I need to stop at a campfire to burn" pressure. **Huge for runs that picked up Wendlbrrr or Haunt curses.** |
| **Strength stacker** | Bird Mask (boss) — +2 Strength every turn. Compounds forever. |
| **Die-roll insurance** | Quadforce (boss) — re-rolls a random die for 4 turns. Smooths bad variance in the opening of tough fights. |
| **Big-baddie tax** | Pet Hooligan Mask — 20% off Big Baddies is meaningful against 240/280 HP Ch2 Bigs (saves ~48/56 HP of damage). |

### Stacking callouts

- **Amulet of Yendor + Noggles + any heal side** = "infinite" healing at the end of each battle. Good in Toxic Swamp runs where you're burning HP to cure poison.
- **Snake Skull + Toxic Swamp poison sides** → each poison application gets +2. With "Poison all 4" that's effectively "Poison all 6" per cast, and with a 2x Poison (+30) side it compounds further.
- **Bird Mask + Rage Shake food + Ch1 Starter "Gain 3 Strength" side** = aggressive Strength stack that scales infinitely in long fights.

### Trinket-priority note

Boss trinkets are strictly best → grab them every time. Rare > Common. Within common, immunity > pre-battle tempo > heal > points > combat math.

## Unknowns

- [ ] Do trinkets that trigger "at the start of battle" also trigger on Obelisk fights? (Pet Hooligan Mask explicitly says no for Obelisks — is that an exception or the rule?)
- [ ] Is "Heal 5 after battle" (Noggles) multiplied by Amulet of Yendor? (Probably yes, but confirm.)
- [ ] Does Shiba Mask's auto-exhaust also count for sides that are already exhausted (i.e. is it wasted)?
- [ ] Max stackable trinkets per run?
