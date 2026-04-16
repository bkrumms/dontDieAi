# Bub's Barter (Shop)

"This devilish merchant will always make a sale. Don't have enough gold? Pay with blood!"

## Rules

- Click wares to add them to the scales; click **Deal** to pay.
- **Gold is used automatically.** If you're short on gold, the total calculated **also includes health**.
- **Burns always cost health** (never gold).

## API
- `POST /api/game/bub/setup-scene` — initialize shop. Returns `shopItems[]` with `id`, `type`, `payload`, `cost`.
- `POST /api/game/bub/deal` — submit purchase. Body: `{ session_id, items: [{id, gold, health, qty}] }`.
- `POST /api/game/bub/loot` — claim an item post-deal. Body: `{ sessionId, id, diceId, abilityId? }`.
- `POST /api/game/bub/exit` — leave the shop.
