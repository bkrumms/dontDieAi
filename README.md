# Don't Die — AI Agent Provider (Mock)

Scaffold for an AI-agent participant in Anomaly Games' Don't Die AI Provider
Program. Three components:

| Component     | File                | Role                                      |
| ------------- | ------------------- | ----------------------------------------- |
| Discord bot   | `bot/main.py`       | Player interaction hub: slash commands, checkpoint prompts, run thread |
| Web viewer    | `web/main.py`       | Live state viewer over WebSocket         |
| Agent service | `dd_agent/loop.py`  | Per-run loop: rules engine + narrator + DD API |

Knowledge base for rules, API, and program terms lives in `knowledge/`.

## Architecture at a glance

```
  Player ──▶ Discord bot ──▶ AgentRun ──▶ DD API
               ▲  │             │
               │  └──prompts────┤
               │                ▼
               └── narration ─ in-mem bus ──▶ Web viewer (WebSocket)
```

- **Rules engine** (`dd_agent/rules.py`) — deterministic brain. Stubs now; real
  rules to be built out in a dedicated pass. Each handler returns a `Decision`.
- **Narrator** (`dd_agent/narrator.py`) — thin wrapper around Claude Haiku 4.5
  (cheap model). Turns rationale into punchy player-facing text. No decisions.
- **Bus** (`dd_agent/bus.py`) — in-memory pub/sub for the mock. Swap for
  `redis.asyncio` when you need multi-process.
- **DD client** (`dd_agent/dd_client.py`) — httpx wrapper over the OpenAPI.
  Auth header is a placeholder until the dev-build auth scheme is confirmed.

## Setup

```bash
cd C:\dev\dontDieAi
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# fill in DISCORD_BOT_TOKEN, ANTHROPIC_API_KEY, DD_AUTH_TOKEN
```

## Run

Combined (bot + web in one process; required for the in-memory bus):

```bash
python main.py
```

Standalone agent loop (no Discord, just runs the loop):

```bash
python scripts/run_agent.py <session_id> <character_id>
```

Web viewer only: `http://localhost:8000/viewer/<session_id>`

## What's a mock vs. real

| Piece                         | State   |
| ----------------------------- | ------- |
| Agent loop structure          | real    |
| DD API client (reads, battle, map, checkpoint, forfeit) | real-ish (auth TBD) |
| Rules engine handlers         | **stubs** — return safe defaults |
| Narrator (Haiku)              | real; falls back to echo if no key |
| Discord bot commands          | real shape, but `/run` uses a mock `session_id` — wire to `start_tournament` next |
| Web viewer                    | real WebSocket, minimal HTML |
| Wallet linking                | not built |
| Mystery / campfire / shop endpoints | not yet wired into the loop |
| Pub/sub                       | in-memory only (single process) |

## Next steps

1. Confirm DD dev-build auth scheme and fix `DDClient` headers.
2. Replace the mock `/run` session start with real `start_tournament()`.
3. Flesh out each rules-engine handler — one module per decision type.
4. Wire the remaining endpoint groups (mystery / campfire / shop / loot-dice).
5. Swap in-memory bus for Redis so bot / web / agent can run as separate services.
6. Build the pre-run wizard (modal UI for sticker/TC selection).
