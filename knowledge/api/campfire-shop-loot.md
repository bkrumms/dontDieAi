# Campfire, Loot Dice, and Bub's Shop

## Campfire
- `POST /api/game/campfire/setup-scene` — init. Body: `character_id`, `session_id`. Returns `status`, `receivingBoosts[]`.
- `POST /api/game/campfire/loot` — select loot. Body: `sessionId`, `lootType`, optional `diceMeta`, `boostMeta`. Returns movement data.
- `POST /api/game/campfire/exit` — leave. Returns movement data.

## Loot Dice
- `POST /api/game/loot-dice/setup-scene` — init. Body: `character_id`, `session_id`. Returns `gold`, `trinkets[]`, `sticker`.
- `POST /api/game/loot-dice/loot` — claim. Body: `sessionId`. Returns movement data.

## Bub's Shop
- `POST /api/game/bub/setup-scene` — init. Returns `shopItems[]` of `{id, type, payload, cost}`.
- `POST /api/game/bub/deal` — purchase. Body: `session_id`, `items[]: {id, gold, health, qty}`.
- `POST /api/game/bub/loot` — claim a purchased item (e.g. host a new Side). Body: `sessionId`, `id`, `diceId`, `abilityId?`.
- `POST /api/game/bub/exit` — leave shop. Returns movement data.

## Boosts
- `POST /api/game/boost/discard` — drop a food item. Body: `sessionId`, `boostId`.
