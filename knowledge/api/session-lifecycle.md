# Session Lifecycle

## `POST /api/game/start-session`
Start a new **adventure** (practice) session.
- Body:
  - `character_id`
  - `equipped[]`
  - `time_crystals` (max **7**)
- Returns: `sessionId`, `mapData`, `chapter`, `progress`, upcoming boss indicators.

## `POST /api/game/start-tournament`
Start a **tournament** session.
- Body:
  - `character_id`
  - `equipped[]`
  - `time_crystals` (max 7)
  - `token_id`
  - `nft_name`
- Returns: same shape as start-session.

## `POST /api/game/stake`
Stake a character on a tournament.
- Body: `session_id`
- Returns: success + data string.

## `POST /api/game/reorder-dice`
Pre-battle dice reorder.
- Body: `character_id`, `session_id`, `new_dice_order[]` of `{ id, order }`
- Returns: nullable state string.

## `POST /api/game/forfeit`
Abandon the run.
- Body: `session_id`
- Returns: boolean confirmation.
