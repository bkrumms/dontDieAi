# Battle API

Ordered battle flow:

## 1. `POST /api/game/battle/setup-scene`
Initialize a battle. Body: `session_id`.
Returns: `battleId`, full state object with player/monsters/battle info.

## 2. `POST /api/game/battle/pre-fight`
Pre-fight phase. Body: `character_id`, `session_id`.
Returns: `state`, `visualClientState`.

## 3. `POST /api/game/battle/select-boost`
Pick a food/boost to apply pre-battle.
- Body: `character_id`, `session_id`, `boost_id`, `targetUuid`, `targets[]?`
- Returns: updated battle state.

## 4. `POST /api/game/battle/start-scene`
Commence battle. Body: `sessionId` (note camelCase).

## 5. `POST /api/game/battle/resolve-turn`  *(loop)*
Resolve a turn. Body: `sessionId`.
Returns: `state`, `visualClientState`, rewind data, `sequence` number, `outcome`, `accumulated points`.

## 6. `POST /api/game/battle/rewind`  *(optional, uses Time Crystal)*
Body: `sessionId`. Returns previous battle state. **Not allowed if dead.**

## 7. `POST /api/game/battle/to-loot`
Commit the battle to the loot phase. Body: `sessionId`.

## Loot phase

### `GET /api/game/battle/fetch-loot`
Query available loot. Query: `sessionId`.
Returns: `gold`, `timeCrystal`, `boosts[]`, `trinkets[]`, `abilityPhaseOne[]`.

### `POST /api/game/battle/pick-dice`
Pick a die to host a new Side during loot.
- Body: `sessionId`, `diceMeta: { phase, diceId }`
- Returns: array of abilities.

### `POST /api/game/battle/loot`
Handle the loot pick.
- Body: `sessionId`, `lootType` (enum), optional `diceMeta`, `boostMeta`, `burnMeta`, `trinketMeta`
- Returns: `bones`, `gold`, `timeCrystal`, `boosts[]`, `trinkets[]`, `abilityPhaseOne[]`, `stickers[]`.

### `POST /api/game/battle/obelisk-action`
Obelisk skip/interact.
- Body: `sessionId`, `action: "proceed" | "exit"`

## Checkpoints
- `POST /api/game/checkpoint` — non-tournament. `selection: "no" | "yes" | "die" | "win"`.
- `POST /api/game/checkpoint/tournament` — tournament. `selection: "continue" | "unstake"`.
