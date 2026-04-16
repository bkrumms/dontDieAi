# Battle

Turn-based **auto-battler**. Your 4 dice are rolled and resolved in order, attacking baddies **left to right, front to back**. If baddies are alive at end of your turn, they take their turn. Loop until one side is dead.

## Controls

- **Re-arrange dice**: click a die symbol and drag. Allowed any time. (API: `POST /api/game/reorder-dice` or the pre-battle setup.)
- **Eat food** before/during a tough fight — one-time consumables that make you much stronger for a single battle. (`POST /api/game/battle/select-boost`.)

## Battle modifiers

There are **5 main modifiers** that can affect you or the baddies (the Notion page shows them in a "Battle modifiers" image). The known schema-level fields on abilities include:

- `damage`
- `block`
- `heal`
- `poison`
- `bleed`

Monsters and players both carry `statusEffects` arrays. (From OpenAPI.)

## Phases (from API)

1. `setup-scene` — `POST /api/game/battle/setup-scene`
2. `pre-fight` — `POST /api/game/battle/pre-fight`
3. `select-boost` (food) — `POST /api/game/battle/select-boost`
4. `start-scene` — `POST /api/game/battle/start-scene`
5. `resolve-turn` (loop) — `POST /api/game/battle/resolve-turn`
6. `rewind` (optional, uses Time Crystal) — `POST /api/game/battle/rewind`
7. `to-loot` — `POST /api/game/battle/to-loot`
8. Loot phase — see `campfire-shop-loot.md` in `api/`.

## End of turn
Response from `resolve-turn` includes: `state`, `visualClientState`, rewind data, `sequence` number, `outcome`, and `accumulated points`.
