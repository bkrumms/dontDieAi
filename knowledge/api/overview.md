# API Overview

- **Spec**: OpenAPI 3.1.0, version 1.0.0
- **Base URL (dev)**: `https://dd-api-dev.anomalygames.ai`
- **Spec JSON**: `https://dd-api-dev.anomalygames.ai/openapi.json`
- **Swagger UI**: `https://dd-api-dev.anomalygames.ai/api_docs`

## Auth
No explicit `securitySchemes` are declared in `components.securitySchemes`. Authentication likely comes from platform session cookies or headers set externally (verify by experimenting against the dev build).

## Conventions
- Every response body is `{ success: boolean, data: <payload> }`.
- Errors: `400 System Error`, `404 Not Found`.
- Session identifier is passed as `session_id` (snake_case) in most POST bodies, and as `sessionId` (camelCase) in a subset of endpoints — **do not assume consistency; copy the exact casing from the spec per endpoint**.
- Character identifier is `character_id`.

## Endpoint groups (see per-group files)
- `session-character.md` — character and session reads
- `session-lifecycle.md` — start/stake/forfeit
- `map.md` — roll, reroll, proceed
- `battle.md` — battle scene lifecycle + loot pickup
- `mystery-events.md` — all mystery/event endpoints
- `campfire-shop-loot.md` — campfire, loot dice, Bub's shop
- `inventory-wallet.md` — inventory, stickers, wallet linking
- `quests-rewards-referral.md` — quests, reward pass, referral program
- `schemas.md` — recurring object shapes
