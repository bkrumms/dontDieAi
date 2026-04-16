# Don't Die — Agent Integration Notes

**Source**: Supplemental notes provided by the Don't Die team on 2026-04-13. Captures sequencing rules and gate conditions that are not obvious from the OpenAPI schema alone.

This document is the authoritative reference for agent-API interaction patterns. When our code disagrees with this doc, update the code.

## Section index

1. Checkpoint Handshake (Impending Doom)
2. /api/game/roll 400 error inspection
3. Battle rewind flow (3-step sequence)
4. Obelisk action (proceed vs exit)
5. Battle state flow (state machine)
6. Mystery events (skippable detection)
7. Loot flow (requiredSteps + terminal step)
8. Battle state source of truth (HP/dice/trinkets/boosts)
9. "boost" = "food" terminology
10. Session debug snapshot
11. Session inState state machine
12. Tournament mode (NFT sessions)

## Critical rules the bot MUST follow

### Checkpoint handshake

- **Only triggers at player level 7+** (Impending Doom unlock) for free sessions, at space 25 and 39.
- **NFT/tournament sessions**: always triggered at 25 and 39.
- **Wrong endpoint**: returns `Invalid selection`.
  - Free → `POST /api/game/checkpoint` with `selection: "no"|"yes"|"die"|"win"`
  - NFT → `POST /api/game/checkpoint/tournament` with `selection: "continue"|"unstake"`
- Each loot-exit response includes `pendingCheckpoint: bool` — always present, always reliable.
- Calling `/roll` or `/proceed` while pending returns 400 with the exact fix message.

### Roll 400 error prefixes — fix mapping

| Message prefix | Fix |
|---|---|
| `Cannot roll: session in state '<state>'` | Finish the current event until `inState === "map"` |
| `Cannot roll: checkpoint pending` | Call `/checkpoint` (free) or `/checkpoint/tournament` (NFT) |
| `Cannot roll: fork choice required` | Resend `/roll` with `{ choice: "<path-id>" }` from prior `pendingChoice` |
| `Cannot roll: no pending choice` | Resend `/roll` WITHOUT the `choice` field |
| `Invalid:` | Auth/session mismatch — do not retry |

### Battle rewind flow (3-step sequence)

Rewind is NOT a single call:

```
POST /api/game/battle/rewind        → resets to setup; returns nextStep: "start-scene"
POST /api/game/battle/start-scene   → re-initializes the scene
POST /api/game/battle/resolve-turn  → resumes turn loop
```

Skipping start-scene returns:
> "Cannot resolve turn: battle session_status is 'setup' — expected 'fighting'. If after /battle/rewind, call /battle/start-scene before resolve-turn."

Preconditions:
- Only allowed when `battleState.session_status === "win"` (post-win, pre-loot-exit)
- Costs time crystals, escalating with `rewind_count` per space
- Refunds any boosts used in the fight

### Obelisk is TWO battles, not one

**Critical fix**: when `inState === "obelisk"`, after calling `/battle/obelisk-action {action: "proceed"}` and winning the first fight, you **must call `/battle/setup-scene` AGAIN** to trigger the second fight (new monsters, new `sequence: 2`). Then pre-fight → start-scene → resolve-turn. Only AFTER the **second** win call `/battle/to-loot`.

Session `inState` stays `"obelisk"` throughout both fights. Only the `/battle/loot { lootType: "exit" }` terminal call transitions back to `map`.

If you skip the re-setup call, your /battle/to-loot fails because the session is in obelisk-skipable state for the second fight, not win.

### Mystery events — skippable dispatch

After `/mystery/setup-scene`, check `data.skippable`:

- **Skippable** → call `/mystery/exit` to skip (if that's the chosen strategy)
- **Non-skippable** → call the dedicated endpoint:
  - Freezer Burn → `/mystery/freezer-burn`
  - Health Points → `/mystery/health-points`
  - Trade Offer → `/mystery/trade-offer`
  - Health or Wealth → `/mystery/health-or-wealth`

Calling `/mystery/exit` on a non-skippable returns:
> `Non skippable event '<name>' — call its dedicated exit endpoint instead ...`

Skippable events that still have valuable options (take instead of exit):
- **Limited Time Offer** → `/mystery/limited-offer` with `pickType: "health"|"time-crystal"`
- **Too Tempting to Pass** → `/mystery/too-temp-to-pass` with pickType (trinket/sticker/gold/points) + random curse
- **Volcanic Spirits** → `/mystery/vocalno` (API typo) — burn a side, −8 HP, −4 max HP
- **Chronically Tired** → `/mystery/chronically-tired` with `actions: [{diceId, abilityId}, ...]`
- **Echo Dagger** → `/mystery/echo-dagger` — replaces an Attack side
- **Lava of Life** → `/mystery/lava-of-life` — burns a side for HP scaled by tier
- **Yin Yang** → `/mystery/yinyang` with `pickType: "swap"|"dupe"` + 130 gold cost
- **Double Down** → skip (too risky in stage 1)
- **Poisoned Veins** → skip per user strategy

### Loot flow — requiredSteps contract

`GET /api/game/battle/fetch-loot` returns `requiredSteps` (array of step names). Follow them IN ORDER:

| Step | When |
|---|---|
| `pick-general` | Always first. Auto-claims gold/crystal/bones/stickers/full-HP + single trinket (obelisk or index 25 only) + boosts if room |
| `pick-boost` | Only when `userBoosts + offers > 3` (inventory overflow) |
| `pick-trinket` | **Boss nodes only** — boss offers 2 trinkets, pick one |
| `pick-dice` | Always — TWO-CALL substep (see below) |
| `pick-ability` | Always — commits the side chosen from the pick-dice preview |
| `pick-burn` | Only if `burnSide > 0` (trinket triggered burn-on-loot) |
| `exit` / `nextChapter` / `proceed` | Terminal — selection rule below |

**Dice upgrade is TWO calls**:
1. `POST /battle/pick-dice` with `{sessionId, diceMeta: {diceId, phase: 1}}` → server returns 3 candidate sides in `data.abilities[]`
2. `POST /battle/loot` with `{sessionId, lootType: "pick-ability", diceMeta: {abilityId, phase: 1}}` — abilityId is a UUID from step 1

**Terminal step selection**:

```
boss node + chapter 1  →  "nextChapter"   (CH1 → CH2 transition; new mapData inline)
boss node + chapter 2  →  "proceed"       (final game win)
otherwise              →  "exit"          (back on map, next call is /roll)
```

**Critical**: calling `lootType: "exit"` on a chapter 1 boss win may not trigger the chapter transition. Use `"nextChapter"`.

### Battle state source of truth

| Context | Read from |
|---|---|
| Map (between battles) | `GET /api/character` (player.health, player.dices, player.trinkets, player.boosts) |
| In battle (any phase) | `battle response.state.player.*` — from pre-fight / start-scene / resolve-turn / rewind |

Mid-battle state is cloned into `battle.player_state` and lives there until loot exits. Reading `/api/character` mid-battle gives PRE-BATTLE values — wrong for "do I have HP to continue", "is this trinket used", etc.

### "boost" = "food" permanently

The API uses `boost` in all field names, endpoint paths, and DB columns. UI calls these "food". Treat `boost` as the permanent API contract. Never expect a rename.

### Session debug snapshot

`GET /api/game/session-debug?session_id=<uuid>` — read-only. Returns the full session state machine (inState, battle.sessionStatus, pendingCheckpoint, pendingChoice, activeEvent, etc.).

Perfect for **crash recovery**: after a bot restart, call session-debug to learn where the session is stuck and dispatch the next call accordingly.

## Session inState values

| inState | Meaning | Valid next calls |
|---|---|---|
| `map` | On map, no pending action | `/roll` (or `/checkpoint` if pendingCheckpoint) |
| `rewindable` | Roll committed, can reroll or proceed | `/proceed`, `/reroll`, or `/roll` with choice if pendingChoice |
| `baddie` | Regular battle | Battle flow |
| `big-baddie` | Mini-boss | Battle flow |
| `boss-baddie` | Chapter boss | Battle flow; terminal is `nextChapter` or `proceed` |
| `obelisk` | Obelisk — 2-fight sequence | `/battle/setup-scene` → `/battle/obelisk-action` |
| `mystery` | Mystery event | `/mystery/setup-scene` → event endpoint |
| `campfire` | Campfire | `/campfire/setup-scene` → `/campfire/loot` → `/campfire/exit` |
| `bub` | Shop | `/bub/setup-scene` → `/bub/deal` → `/bub/loot` → `/bub/exit` |
| `loot-die` | Loot Die | `/loot-dice/setup-scene` → `/loot-dice/loot` |
| `win` | Game won (CH2 boss defeated) | `/forfeit` to close |
| `lost` | Game lost | `/forfeit` to close |

## Tournament mode (NFT sessions)

Different endpoint pairs for start, checkpoint, stake flows. Key differences:

- Start: `/api/game/start-tournament` (with `equipped[]`, `token_id`, `nft_name`)
- Stake: separate `/api/game/stake` call after start + after each checkpoint
- Checkpoint: `/api/game/checkpoint/tournament` with `selection: "continue"|"unstake"`
- Pre-conditions on `/stake`: `inState: "map"`, `checkpoint_pending !== 1`, `current_index === 0 || 25`, `staked === 0`

Full happy-path tournament sequence in the doc.
