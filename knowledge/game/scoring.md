# Scoring — Complete Reference

**Source**: Nick's `Points.html` (2026-04-13 database export). This is the authoritative scoring formula for the game.

## 1. Per-roll base points

Every time a die is rolled, you score points based on the **pool tier** of the side that landed face-up:

| Pool | Points per roll |
|---|---:|
| Starter | **10** |
| Level 1 `(+10)` | **10** |
| Level 2 `(+20)` | **20** |
| Level 3 `(+30)` | **30** |
| **Level 3 earned from a Boss** | **100** ⚠ |

**Key finding**: Level 3 sides dropped from **boss fights** score **100 per roll** — 3.3× more than regular Level 3s. The `Level 3 Boss` tag flag in the API matters enormously. A boss-dropped Level 3 side rolled 10 times in a single battle = **+1000 base points** before any effect fires.

Curse sides: 0 base points, some explicitly subtract (`Lose 50 Points`, `Lose 100 Points`).

Various Score-N-Points effect sides exist (e.g. `Score 100 Points any time you Block`, `Block 18. Score 50 Points`). These stack **on top of** the per-roll base.

## 2. Kill rewards

Flat points for killing each baddie type:

| Baddie type | Ch 1 | Ch 2 |
|---|---:|---:|
| Baddie | 100 | 300 |
| Big Baddie | 500 | 800 |
| Boss | 1,000 | ~2,000 |

Chapter-2 kills are worth 2-3× chapter-1 kills.

## 3. High Damage Bonus — per-turn damage thresholds

Earned when you deal the specified damage in a single turn (cumulative if you cross multiple thresholds):

| Damage dealt in one turn | Bonus at threshold | Cumulative if you hit all prior |
|---:|---:|---:|
| 20 | 100 | 100 |
| 40 | 200 | 300 |
| 70 | 300 | 600 |
| 100 | 500 | 1,100 |
| 200 | 700 | 1,800 |
| 300 | 1,000 | 2,800 |

A 300+ damage turn awards **+2,800 points** cumulatively. This is why burst-turn builds with Damage multipliers are so valuable.

## 4. Low HP Bonus — win the battle at low HP

Earned after winning a battle. Score is based on HP at **end of battle, BEFORE any end-of-battle rehealths** (Noggles, Snackrifice, etc. don't count toward the bonus HP).

| HP at battle end | Points (× chapter) |
|---|---:|
| 1 | **7,500 × ch** |
| 2–5 | 5,000 × ch |
| 6–14 | 3,000 × ch |
| 15–25 | 1,000 × ch |
| 25 – 50% of max | 800 × ch |
| 50% – 80% of max | 500 × ch |

**In chapter 2, winning at 1 HP = 15,000 points.** This is a huge risk/reward incentive to intentionally low-HP the end of fights.

## 5. Speed Bonus — end battle on turn N

| Turn battle ends | Points (× chapter) |
|---:|---:|
| 1 | **1,500 × ch** |
| 2 | 1,000 × ch |
| 3 | 800 × ch |
| 4 | 600 × ch |
| 5 | 400 × ch |
| 6 | 300 × ch |
| 7+ | 200 × ch |

Turn-1 win in chapter 2 = +3,000 points. Pairs with `Scoring` trinket.

## 6. Campfires

One of the 5 campfire options is **Score: gain 7,000 points flat**. Only applies when the player picks the Score option. Campfires have 5 options (see `campfire` below in `knowledge/game/encounter-loot.md`).

## 7. Trinket & Food scoring effects

| Item | Tier | Effect |
|---|---|---|
| `Scoring` trinket | Boss | **If you win within 3 turns, score 7,777 points** — stacks with Speed Bonus |
| `Joker Card` trinket | Rare | `+1x` Points multiplier on **odd turns** only |
| `Ascendacandy` food | Rare | `+2x` Points multiplier (for a battle) |
| `Brotein Bar MAX` food | Common | +500 Points flat, +30 Gold, +8 HP, Attack all 20, +2 Strength |

**Joker Card effective value**: `1.5x` Points in a balanced battle (half the turns are odd). On short fights ending turn 1 or turn 3, value is higher.

**Ascendacandy effective value**: `3x` Points for the battle. Strictly stronger than Joker Card in a single fight; worth saving for a long big-baddie or boss fight.

## 8. Points multiplier stacking rules

The game has both a **damageMultiplier** and **pointsMultiplier** in player state. Multipliers **multiply the accumulated points per turn** — meaning the +N base points per roll get multiplied too.

Confirmed sources of `+Nx` points multipliers:
- Side: `Increase Points by 1x` (+30 None)
- Side: `Increase Points by 3x. Every turn decrease Points by 1x` (+30 None, decay)
- Trinket: Joker Card (odd turns only)
- Food: Ascendacandy (full battle)
- Mystery: `Double Down` (2x multiplier in next battle)

**Peak stacking**: Ascendacandy + `Increase Points by 1x` side + Joker Card on an odd turn = base × 3x × 2x × 2x = **12x** on an odd turn in the boosted battle. Pair with a high-damage turn and this is where runs go ballistic.

## 9. Rules-engine scoring priorities

1. **Boss-dropped Level 3 sides are the single most valuable upgrade** — +100/roll base vs +30 normal L3. Always take them.
2. **Campfire Score option is worth 7,000 points** — compare against heal/burn/food/TC value contextually. In late-chapter clean runs with no curses, Score is strictly dominant if you're at >80% HP.
3. **Low HP bonus is designed to reward risk** — intentionally finishing a fight at 1 HP is worth 7,500 × chapter. Hard rule: **if you can finish a fight at 1 HP and survive the next fight, do it**.
4. **Speed Bonus × Scoring trinket × 1x multiplier** is the explicit burst build — stacking these and winning turn-1 gives 1500 + 7777 + any base points ×2.
5. **In chapter 2, everything scores 2–3× chapter 1** — the player should be racing to chapter 2 once they have a stable build. Don't spend time farming chapter 1.
