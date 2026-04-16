# Map Navigation

## `POST /api/game/roll`
Roll the movement die on the map. The movement die is irregular (faces `1,2,2,3,3,4`) — see `game/map-movement-odds.md`.
- Body:
  - `choice` *(optional)* — fork selection when stopped on a fork
  - `session_id`
- Returns: `nextRerollCost`, `pendingSteps`, `movementResult` with `path` and `index`.

## `POST /api/game/reroll`
Rewind on the map (costs Time Crystals).
- Body: `session_id`
- Returns: `rewindTarget` with `path` and `index`.

## `POST /api/game/proceed`
Commit to the event on the current space (battle, mystery, campfire, loot die, shop, etc.).
- Body: `session_id`
- Returns: `inState`, `activePath`, `currentIndex`, upcoming bosses.

## Movement state (recurring)
All movement responses contain fields: `activePath` (string), `currentIndex` (number), `rolledSteps` (nullable number), `pendingChoice`, `inState` (string), `justRejoinedFromFork` (nullable boolean).
