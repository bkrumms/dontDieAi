# Food (Boosts)

Food = **one-time consumables** applied pre-battle or mid-battle via `POST /api/game/battle/select-boost`. They only last the current battle unless the effect says otherwise.

Source: "Feb Food + Trinkets" image. Raw data: [`food.csv`](food.csv)

## Common

| Name | Effect |
|---|---|
| Rage Shake | When damaged, gain 3 Strength |
| Ice Rice | Negate the next 3 Debuffs |
| Clutch Creme | If you take 7 or less damage, reduce it to 1 |
| Pickle | Gain 6 Block if you have 6 or less Block at the end of each turn |
| Heat Meat | Increase Damage by 1x for your first 2 turns |
| Brrrito Blockerito | Stack Block for your first 6 turns |
| Snackrifice | Lose 6 Health. If you have 50% Health or less at end of battle, Heal 22 |
| Toxipop | On Baddie death, transfer Poison to next Baddie |
| Boom Beans | Damage any Baddie 40. Damage all others 10. |
| Brotein Bar MAX | Attack all 20, Heal 8, Gain 2 Strength, Score 500 Points |

## Rare

| Name | Effect |
|---|---|
| Godmode Guac | Increase Damage by 1x. On the next turn 4, increase Damage by another 1x |
| Giga Juice | Increase all values on all Dice by 2 |

## Archetypes and rules-engine hints

| Archetype | Foods | Good against |
|---|---|---|
| **Burst opener** | Heat Meat, Godmode Guac, Giga Juice | Time-bomb baddies (Detonox, Deathbat, Big Cheeza) — front-load damage before their deadline. |
| **Survival / heal** | Snackrifice, Clutch Creme, Brrrito Blockerito | Long fights, high-attack baddies, or when you're under 50% HP going in. |
| **Direct damage** | Boom Beans, Protein Bar MAX | Low-HP Big Baddies where a 40 hit + 20 AoE tips the fight. Protein Bar MAX is the single-highest-swing consumable in the common pool. |
| **Debuff play** | Toxipop, Ice Rice | Poison-centric runs (Toxipop chains kills), or vs curse-applying baddies (Ice Rice eats 3 debuffs). |
| **Counter-punch** | Rage Shake, Pickle | Rage Shake is strong when you expect to be hit; stacks with other strength gains. Pickle is passive block padding — good vs consistent chip. |

### Specific situational picks

- **vs. Detonox** (240 HP, explodes turn 7): Godmode Guac + Heat Meat = 4x damage window, enough to race him.
- **vs. Big Cheeza** (700 HP, 1x cap on turn 5): Everything burst on turns 1–4. Protein Bar MAX + Giga Juice if you have them.
- **vs. Gorgon-zola** (reflects Freeze and Bleed): avoid foods that apply those modifiers; Boom Beans and Protein Bar MAX are clean damage.
- **vs. Ice Glitch (Frigid Interloper)**: Ice Rice to absorb the random-die freeze.
- **Low HP entering a fight**: Snackrifice is a trap if you can't survive 6 HP more; Clutch Creme or Brrrito Blockerito instead.

## Unknowns

- [ ] Do food effects that mention "at the end of each turn" (Pickle, Brrrito Blockerito) persist for the whole battle or only the specified window?
- [ ] Does "Stack Block for your first 6 turns" mean block carries over rather than resetting? (Block normally resets at turn end.)
- [ ] "On Baddie death, transfer Poison to next Baddie" — does stack size persist exactly, or decrement?
