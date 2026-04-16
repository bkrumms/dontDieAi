# Mystery Events API

All under `/api/game/mystery/*`. Also see `game/mystery-events.md` for gameplay notes.

## Scene control
- `POST /api/game/mystery/setup-scene` — init. Body: `character_id`, `session_id`. Returns `event`, `status`, `actionCount`, `lastAction`.
- `POST /api/game/mystery/exit` — skip. Body: `sessionId`.

## Per-event endpoints

| Event | Method & Path | Body |
|---|---|---|
| Volcano Spirit | `POST /api/game/mystery/vocalno` | `sessionId`, `diceId`, `abilityId` |
| Yin Yang | `POST /api/game/mystery/yinyang` | `pickType: "swap"\|"dupe"`, `sessionId`, optional dice/ability |
| Lava of Life | `POST /api/game/mystery/lava-of-life` | `sessionId`, `diceId`, `abilityId` |
| Health Points | `POST /api/game/mystery/health-points` | `sessionId`, `pickType: "1"\|"2"\|"3"\|"4"` |
| Limited Offer | `POST /api/game/mystery/limited-offer` | `sessionId`, `pickType: "health"\|"time-crystal"` |
| Echo Dagger | `POST /api/game/mystery/echo-dagger` | `sessionId`, `diceId`, `abilityId` |
| Chronically Tired | `POST /api/game/mystery/chronically-tired` | `sessionId`, `actions[]: {diceId, abilityId}` |
| Infinidieferno | `GET \| POST /api/game/mystery/infinidieferno` | POST `{sessionId, action: "burn"\|"rewind"}` |
| Freezer Burn | `POST /api/game/mystery/freezer-burn` | `sessionId`, `pickType: "boost"\|"burn"`, optional dice/ability |
| Trade Offer | `GET \| POST /api/game/mystery/trade-offer` | POST `{sessionId, pickType: "points"\|"trinket"}` |
| Poison Veins | `GET \| POST /api/game/mystery/poison-veins` | POST `{sessionId}` |
| Too Temp To Pass | `GET \| POST /api/game/mystery/too-temp-to-pass` | POST `{sessionId, lootType, boostMeta?}` |
| Health or Wealth | `POST /api/game/mystery/health-or-wealth` | `sessionId`, `gold`, `points` |
| Never Tell Me The Odds | `POST /api/game/mystery/never-tell-me-the-odds` | `sessionId`, `pickType: "100"\|"1000"\|"3333"` |
| Double Down | `POST /api/game/mystery/double-down` | `sessionId` |
| Glitch Matrix | `POST /api/game/mystery/glitch-matrix` | `sessionId`, `pick` (number), `diceId`, `abilityId` |

Note the typo `vocalno` (not `volcano`) in the actual path — that's the spec as-is.
