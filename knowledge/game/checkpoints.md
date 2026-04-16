# Checkpoints & Chapters

## Structure
- **2 chapters**, **4 checkpoints** total across them.
- A **Campfire** is placed immediately before each mini-boss and boss.

## Tournament decision
- The key decision in Tournament mode is **which checkpoint to stop at**.
- **Continuing past a checkpoint risks death** — if you die after a checkpoint, you lose the prize.
- Player (or AI agent + player preference) decides to continue or unstake at each checkpoint.

## API
- `POST /api/game/checkpoint` — non-tournament. Body: `{ session_id, selection: "no" | "yes" | "die" | "win" }`.
- `POST /api/game/checkpoint/tournament` — tournament. Body: `{ session_id, selection: "continue" | "unstake" }`.
- `POST /api/game/forfeit` — give up the session.

## AI Mode nuance
Per the AI Provider Program doc, the player must be given the option to:
- **Auto-accept** continuing at checkpoints (if the agent deems it appropriate), OR
- **Manually decide** continue vs. unstake at each checkpoint.
See `ai-provider-program/player-experience.md`.
