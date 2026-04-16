# Burning Sides

Burning removes a Side from one of your dice. **Critical for improving consistency** (fewer sides = less variance on each roll).

## Rules

- **Dice must have a minimum of 4 sides.** You cannot burn below 4.
- Burning is a commitment — you can't un-burn a Side.

## Where you can burn

- **Campfires** (see the campfire event).
- **Bub's Barter** — the shop. **Burns always cost health** at Bub's, never gold.
- **Some Mystery Events** (e.g. Freezer Burn, Infinidieferno offer burn as an option).

## API
- Campfire loot: `POST /api/game/campfire/loot` with `lootType` that includes burn options.
- Bub's: `POST /api/game/bub/deal` — health is automatically included in the total if you're short on gold, or always for burn line-items.
- Mystery events with burns: `freezer-burn`, `infinidieferno` (see `api/mystery-events.md`).
