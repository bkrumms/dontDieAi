# Time Crystals

A **limited** resource used to rewind time and change outcomes.

## Uses

### Rewind a full battle
- Replays the whole battle with different luck.
- **Cannot rewind if you're dead.** (So plan the rewind before the death-blow resolves — or burn TC proactively.)

### Rewind movement
- Use on the map to get a different movement roll (target or avoid a particular space).
- The movement die is irregular: faces `1, 2, 2, 3, 3, 4`. 2s and 3s remain most common even after rewinding. See `map-movement-odds.md`.

## Acquiring
- Max **7 time crystals** can be brought into a session (`time_crystals` field on `POST /api/game/start-session` is capped at 7).
- Obtainable in loot, mystery events, etc.

## Pre-run
- Player adds Time Crystals **before** starting a run (pre-run choice, see AI Provider doc — player keeps control of this even in AI Mode).

## API
- `POST /api/game/start-session` body: `{ character_id, equipped[], time_crystals (max 7) }`.
- Battle rewind: `POST /api/game/battle/rewind`.
- Movement rewind: `POST /api/game/reroll` (returns `rewindTarget`).
- Player state includes `timeCrystal` count.
