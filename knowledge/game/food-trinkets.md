# Food and Trinkets

## Food (boosts)

- **One-time consumables** that make you much stronger **for a single battle**.
- Used pre/during a tough fight.
- Accessible from the Backpack and during pre-fight.

## Trinkets

- **Permanent passive items** acquired during a run.
- **Very strong** — they can shape your run.
- **Trigger automatically during battle.**

## API
- Player state includes `trinkets[]` and `boosts[]`.
- Pre-fight food selection: `POST /api/game/battle/select-boost` — body `{ character_id, session_id, boost_id, targetUuid, targets[]? }`.
- Discard food: `POST /api/game/boost/discard` — `{ sessionId, boostId }`.
- Loot endpoint returns `boosts[]` and `trinkets[]` arrays: `POST /api/game/battle/loot`, and trinkets are also in loot-dice and shop outputs.
