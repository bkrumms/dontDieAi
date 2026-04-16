# Character & Session Reads

## `GET /api/character`
Retrieve player session data for an active run.
- Query: `sessionId` (required)
- Returns: full player state — `dice[]`, `health`, `maxHealth`, `boosts[]`, `trinkets[]`, `equipment`, `timeCrystal`, `points`, etc.

## `GET /api/characters`
User's NFT characters.
- Returns: array of character objects with NFT metadata, health, equipment.

## `GET /api/characters/solo`
Practice-mode character.
- Returns: solo character UUID (string).

## `GET /api/nft-characters`
Current-season tournament characters.
- Returns: season data with a `character[]` array.

## `GET /api/game`
Query the active (or most recent) session for a character.
- Query: `character_id` (required)
- Returns: last session state or `null`, `nextRerollCost`, upcoming boss indicators.
