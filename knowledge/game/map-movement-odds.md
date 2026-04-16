# Map Movement & Dice Odds

## The movement die

Map movement uses an **irregular 6-sided die** with faces:

```
1, 2, 2, 3, 3, 4
```

## Probabilities (per roll)

| Face | Count | Probability | Fraction |
|-----:|:-----:|:-----------:|:--------:|
| 1    | 1     | 16.67%      | 1/6      |
| 2    | 2     | 33.33%      | 2/6 = 1/3 |
| 3    | 2     | 33.33%      | 2/6 = 1/3 |
| 4    | 1     | 16.67%      | 1/6      |

**Expected value:** `(1+2+2+3+3+4) / 6 = 15/6 = 2.5` steps per roll.

Rolling a **2 or 3** combined: **66.67%** (4/6). Rolling a **1 or 4** combined: **33.33%**.

## Forced stops

- Spaces with a **purple glow** always stop you regardless of what you roll.
- These are **mini-boss** and **boss** spaces, plus the **Campfire** placed immediately before each of them.

## Map generation

- Maps are **randomly generated** with specific odds per space type.
- Some maps are harder than others — skill is recognizing patterns and surviving any layout.
- Forks lead to one of 3 biomes (see `biomes.md`).

## Rewinding movement

Time Crystals can rewind map movement to re-roll. The die is still irregular, so 2s and 3s remain most common. See `time-crystals.md`.

## API mapping

- `POST /api/game/roll` — roll the movement die. Body: `{ choice?, session_id }` → returns `pendingSteps`, `movementResult`.
- `POST /api/game/reroll` — rewind movement. Returns `rewindTarget`.
- `POST /api/game/proceed` — commit to the event on the current space.
