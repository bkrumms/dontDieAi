# Mystery Events — Complete Reference

**Source**: Nick's `Mystery Events.html` (2026-04-13 database export), cross-referenced with live watch-session observations.

## Pool structure

Mystery events are grouped into **6 pools** based on chapter + space range. When the player hits a mystery space, the game picks an event from the matching pool.

| Chapter | Pool | Space range |
|---|---|---|
| 1 | ME Pool 1 | Spaces 1–9 |
| 1 | ME Pool 2 | Spaces 10–20 |
| 1 | ME Pool 3 | Spaces 21–39 |
| 2 | ME Pool 4 | Spaces 1–9 |
| 2 | ME Pool 5 | Spaces 10–20 |
| 2 | ME Pool 6 | Spaces 21–39 |

Some events appear in multiple pools (early AND late); others are chapter-specific.

## Full event catalog

### Limited Time Offer
**Pools**: Ch1 P1, Ch2 P4
**Decision**: Choose one: **Gain 8 max HP** OR **Gain 4 Time Crystals**.
**API**: `POST /api/game/mystery/limited-offer` with `pickType: "health" | "time-crystal"`
**Observed live**: +4 TC picked in run 3 at main[5]. Zero cost, zero downside.
**Rule**: When max HP is low (<60), pick health. When TC is low (<3), pick time-crystal. Almost never refuse.

### Too Tempting to Pass
**Pools**: Ch1 P1, Ch2 P4
**Decision**: Pick one (**Trinket / Sticker of run tier / 150 Gold / 10,000 Points**) AND accept **a random Curse** on a random die.
**API**: `POST /api/game/mystery/too-temp-to-pass`
**Rule**: The 10,000 points or a trinket pick is usually +EV, but only if you have a burn opportunity (campfire, Bub's, or Shiba Mask) coming soon. Never take in tournament late-chapter without burn access.

### Volcanic Spirits
**Pools**: Ch1 P1, Ch2 P5
**Decision**: Burn a Side. **Lose 8 HP and 4 max HP**.
**Description**: "Mystical spirits dance in the volcano, inviting you to join them."
**API**: `POST /api/game/mystery/vocalno` (yes, the path is misspelled in the API)
**Observed live**: Run 1 space 3 — this is the brutal mystery I couldn't identify. Confirmed: −8 HP + −4 max HP + free burn.
**Rule**: Only accept if you have a Curse to burn. Losing 4 max HP permanently is expensive.

### Chronically Tired
**Pools**: Ch1 P1
**Decision**: **Add Exhaust to two Sides.**
**API**: `POST /api/game/mystery/chronically-tired` with `actions: [{diceId, abilityId}]`
**Rule**: Usually bad — turns two sides into one-time-use. Only accept if you're exhausting sides you'd want to burn anyway.

### Health Points
**Pools**: Ch1 P2
**Decision**: Choose one:
- **−5,000 pts, +30 HP, +3 TC**
- **−2,000 pts, +10 HP, +2 TC**
- **−750 pts, +5 HP, +1 TC**
- **+100 pts** (no cost)
**API**: `POST /api/game/mystery/health-points` with `pickType: "1"|"2"|"3"|"4"`
**Rule**: Pick tier based on current HP deficit. The −750/+5/+1 tier is usually best value per point.

### Freezer Burn
**Pools**: Ch1 P2, Ch2 P4
**Decision**: Choose one: **Get a Brrrito Blockerito** OR **Burn a Side**.
**API**: `POST /api/game/mystery/freezer-burn` with `pickType: "boost"|"burn"`
**Rule**: Always take the burn if you have a Curse or a Starter Attack 4 to get rid of. Otherwise take the food.

### Never Tell Me the Odds
**Pools**: Ch1 P2, Ch2 P5
**Decision**: **10,000 points prize.** Pick odds:
- **1/100 odds** → risk 100 points
- **1/10 odds** → risk 1,000 points
- **1/3 odds** → risk 3,333 points

**Design note (per Nick)**: *"Ser, the possibility of successfully winning this game is EV neutral, playing is unnecessary."* This event is **explicitly EV-neutral by design**.
- 1/100 × 10000 − 100 = 0
- 1/10 × 10000 − 1000 = 0
- 1/3 × 10000 − 3333 ≈ 0
**API**: `POST /api/game/mystery/never-tell-me-the-odds` with `pickType: "100"|"1000"|"3333"`
**Observed live**:
  - Run 2: won +10,000 points on one bet at main[11].
  - Run 3: bet 4 times in a row at fork2[15], lost all (−3333, −1000, −100, −100). Total −4,533.
  - Run 4: bet at fork1[10], lost (−3333, −100, −100). Total −3,533.
**Rule**: Refuse by default. EV=0 but variance adds risk. In tournament mode, always skip — the downside threatens survival. In practice runs, can bet 100 once for scouting and then walk.

### Lava of Life
**Pools**: Ch1 P3
**Decision**: Select a Side to burn. Outcome depends on side tier:
- **Curse** → −1000 pts (no HP change)
- **Starter / Level 1** → +5 HP
- **Level 2** → +25 HP
- **Level 3** → +10 max HP AND +35 HP
**API**: `POST /api/game/mystery/lava-of-life`
**Rule**: Top-tier event — burn a Level 3 side for +10 max HP + +35 HP is amazing if you have a junk Level 3 you don't need. Never burn a curse here (it costs points).

### Echo Dagger
**Pools**: Ch1 P3
**Decision**: Replace any Attack Side with the **Echo Dagger** side: `Attack 24. If fatal, Attack again.`
**API**: `POST /api/game/mystery/echo-dagger`
**Rule**: Echo Dagger is high-tier (+30 per roll, base). Replace a weak Starter Attack 4. Never replace a Level 2 or Level 3 Attack side.

### Trade Offer
**Pools**: Ch1 P3, Ch2 P4
**Decision**: **Pass for −1,000 pts** OR **trade a random non-boss trinket for another random non-boss trinket** (player sees what they're giving up but not what they get).
**API**: `POST /api/game/mystery/trade-offer` with `pickType: "points"|"trinket"`
**Rule**: Trade only if you have a junk common trinket you wouldn't miss. Pass always beats trade if your current trinkets are all strong.

### Double Down
**Pools**: Ch1 P3, Ch2 P6
**Decision**: **Lose 10 HP. Start next battle with 2x Points Multiplier.**
**API**: `POST /api/game/mystery/double-down`
**Rule**: Take it if the next fight is a big-baddie or obelisk fight (long battle = more multiplier payoff) and you're >50% HP. Skip if near death.

### Infinidieferno
**Pools**: Ch2 P4
**Decision**: Randomly burn 1 Side at a time until you choose to stop. Time Crystals can rewind — but the TC rewind cost escalates by +1 each burn. **Dice have a D4 minimum** (can burn down to 4 sides per die).
**API**: `POST /api/game/mystery/infinidieferno` with `action: "burn"|"rewind"`
**Rule**: High-variance. Take if you have multiple Curses you want gone AND 4+ TC in reserve. The random burn can nuke a +30 side, so TC insurance is mandatory.

### Yin Yang
**Pools**: Ch2 P5
**Decision**: **Spend 130 Gold to Duplicate or Swap a Side.**
**API**: `POST /api/game/mystery/yinyang` with `pickType: "swap"|"dupe"`
**Rule**: Duplicate a +30 side on a die that only has one great side (doubles your +30/roll payout). Swap to move a side between dice (e.g., consolidate all Attack on one die). 130 gold is cheap for this.

### Poisoned Veins
**Pools**: Ch2 P5
**Decision**: **Get a Poison Curse** AND **get the Snake Skull trinket**. If you already have Snake Skull, get Lizard Mask. If you have both, get a random Common Trinket.
**API**: `POST /api/game/mystery/poison-veins`
**Rule**: Great for poison builds — Snake Skull + Lizard Mask stacked is a huge boost. Bad if you don't have any poison sides.

### Health or Wealth
**Pools**: Ch2 P6
**Decision**: Two sliders (Points + Gold). Buy up to **30 HP** at **10 gold or 200 points per HP**.
**API**: `POST /api/game/mystery/health-or-wealth` with `gold`, `points`
**Rule**: Cheap HP insurance. In chapter 2 pool 6 you're close to the boss — usually worth 200-400 points for 2-4 HP if you're below 70% max.

### Glitch in the Matrix
**Pools**: Ch2 P6
**Decision**: "Increase 0nevalue by 1" — the button text is literally `Increase 0nevalue by 1` (cryptic on purpose).
**API**: `POST /api/game/mystery/glitch-matrix` with `pick` (number), `diceId`, `abilityId`
**Rule**: Unclear exact effect from Nick's description — appears to increment one numeric value on a side by 1. Good for incrementally boosting a +30 side's damage/block/etc. Observe in a watch session to decode.

## Event distribution by space

If you're on a mystery space in chapter 1:
- **Spaces 1–9** (Pool 1): Limited Time Offer, Too Tempting to Pass, Volcanic Spirits, Chronically Tired
- **Spaces 10–20** (Pool 2): Health Points, Freezer Burn, Never Tell Me The Odds
- **Spaces 21–39** (Pool 3): Lava of Life, Echo Dagger, Trade Offer, Double Down

If you're on a mystery space in chapter 2:
- **Spaces 1–9** (Pool 4): Limited Time Offer, Too Tempting to Pass, Freezer Burn, Trade Offer, Infinidieferno
- **Spaces 10–20** (Pool 5): Volcanic Spirits, Never Tell Me The Odds, Yin Yang, Poisoned Veins
- **Spaces 21–39** (Pool 6): Double Down, Health or Wealth, Glitch in the Matrix

**Rules-engine implication**: Given a mystery at space X in chapter Y, the agent can **enumerate the possible events in that pool** and pre-compute the optimal choice for each, rather than reacting to whatever shows up.

## API scene control

- `POST /api/game/mystery/setup-scene` — init. Returns `event`, `status`, `actionCount`, `lastAction`.
- `POST /api/game/mystery/exit` — skip entirely.
