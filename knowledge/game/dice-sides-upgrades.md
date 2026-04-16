# Dice, Sides, and Upgrades

## Dice

- The player has **4 dice** in battle.
- Dice are rolled and resolved **in order** (left to right).
- Dice can be **re-arranged** at any time: click a die symbol and drag. (API: `POST /api/game/reorder-dice`.)

## Upgrading dice (after every battle)

1. Select which die to add a new Side to.
2. You are shown **3 Side options** — pick one to add.
3. You can **skip** the upgrade if none of the options are good.
4. **You cannot change which die you're upgrading once selected.** Commit wisely.
5. Each upgrade decreases the **consistency** of that die (more sides = more variance).

## Side catalog

- **75** sides currently documented (see `database/sides.csv`). Notion FAQ says "60+ currently, 80+ at final design".
- At least **2 of the 3** sides shown after a battle match the current biome.
- Sides without a colored border exist in every biome.
- Each side belongs to a **pool**: `Starter`, `(+10)`, `(+20)`, `(+30)`, `Echo Dagger`, `Curse`.
- The pool determines **base points scored per roll**: Starter and `(+10)` = +10, `(+20)` = +20, `(+30)` and Echo Dagger = +30, Curse = 0 or negative. A fresh 4-side Starter die already scores +40 per roll. See `database/sides.md` for EV implications.

## Side anatomy

- **Main effect** — listed in the center.
- **Gold outline** — the main effect hits **all baddies** (AoE).
- **Secondary effect** — shown in the corner if present.
- **Colored borders** (green/blue/red) — biome-themed sides. Border is cosmetic/thematic, **not a strength indicator**. Some of the most powerful Sides have no colored border.
- **Exhaust** — sides with 4 black triangles are **one-time use per battle**. Check the exhausted state via the blue fire icon (bottom-left during battle).

## API mapping

- Side type enum: `"Attack" | "Tactic" | "Power"` (from OpenAPI `Ability.sideType`).
- Abilities carry fields: `damage`, `block`, `heal`, `poison`, `bleed`, `exhaust`, `exhausted`, `specialEffect`, `tags`.
