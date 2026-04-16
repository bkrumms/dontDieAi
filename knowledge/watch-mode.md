# Watch Mode — Data Collection Workflow

A passive observer for live runs. You play the game normally; a Python script
polls `GET /api/character` in the background and logs every state change to
disk so we can review enemy attack patterns, score rates, mystery-event
outcomes, and upgrade decisions together afterwards.

**The watcher never calls POST endpoints.** It cannot mutate or interfere with
your run. It is safe to run alongside live play.

## One-time setup

1. Install deps: `pip install -r requirements.txt`
2. Copy `.env.example` → `.env`.
3. **Find the dev-build auth header**: open the Local Build in your browser,
   log in, open DevTools → Network tab, click any request to
   `dd-api-dev.anomalygames.ai`, and look at Request Headers. Copy whichever
   of these apply into `.env`:
   - `Authorization: Bearer <token>` → paste token into `DD_AUTH_TOKEN`
   - `Cookie: <long string>` → paste into `DD_COOKIE`
   - Any custom `x-*` headers → paste as JSON into `DD_EXTRA_HEADERS`,
     e.g. `DD_EXTRA_HEADERS={"x-csrf-token":"abc123"}`

## Running a watch session

1. **Start a run in the actual game client.** Watch mode can't start a run;
   you're the one playing.
2. In the game's Settings panel during the run, **copy the Session ID**.
   (Notion FAQ says it's in Settings for bug reports.)
3. In a terminal:
   ```bash
   python scripts/watch_run.py <session_id>
   ```
4. Play the game. The watcher prints a live event feed and writes two files:
   - `data/runs/<session_id>/states.jsonl` — every poll's raw state (for
     later analysis)
   - `data/runs/<session_id>/events.md` — human-readable timeline of changes
5. Stop with `Ctrl+C` (or it will stop automatically on death/forfeit/win).

## Event types the watcher detects

| Tag | Trigger |
|---|---|
| `INIT` | First poll — snapshots the starting state |
| `STATE` | `inState` transition (map → battle → loot → map, etc.) |
| `DAMAGE` / `HEAL` | Player HP delta |
| `TC` | Time Crystal delta (spent on rewind, or gained from loot) |
| `POINTS` | Points delta (per roll, per effect, per bonus) |
| `MOVE` | `activePath` or `currentIndex` change |
| `STATUS` | Player status-effect list change |
| `DIE` | Dice ability list change — upgrade, burn, or curse applied |
| `TRINKET+/-` | Trinket added/removed |
| `FOOD+/-` | Food added/removed |
| `PT-MULT` / `DMG-MULT` | Multiplier changed |
| `TERMINAL` | Run ended (dead / won / forfeited) |

## What we'll learn from a watch session

- **Enemy attack patterns** — by diffing player HP per turn during a battle,
  we can back-out each baddie's damage output.
- **Base points vs effect points** — we'll see per-roll point gains and can
  verify the `(+10/+20/+30)` rule end-to-end.
- **Mystery event outcomes** — which choice leads to what state change.
- **Upgrade offers** — we'll see which dice get new sides and when.
- **TC pacing** — how often rewinds happen and what they cost.

## What watch mode can't see (yet)

- **Direct monster state** during battle — `GET /api/character` is player-
  centric. Monster HP/ability data typically comes through POST-only battle
  endpoints. We'll have to infer monster behavior from player-side deltas
  until we find a GET endpoint that exposes the battle scene.
- **Exact ability cycle indices** on baddies — `abilityCycleFromIndex` is in
  the schema but may not be on the character endpoint.

## Troubleshooting

- **401 / 403**: auth header is wrong or expired. Re-copy from DevTools.
- **429**: Cloudflare rate limit. Increase `poll_interval`:
  `python scripts/watch_run.py <session_id> 3.0`
- **Script runs but no events**: check that the session_id is from an
  **active** run (not an old one), and that the game hasn't already ended.

## After a session

Tell me the `session_id` and I'll read the files in `data/runs/<session_id>/`
and turn what we learned into rules-engine knowledge + updates to the
`knowledge/game/database/` files.
