# Tournament Prizes & Stickers

**Source**: Nick's `Prizes+Stickers.html` (2026-04-13 database export).

## Prize pool structure

### Example economy (for reference)
- **10,000 NFTs sold** at average **$3** each = **$30,000 topline**
- **80% → Prize Pool** = $24,000
- **20% → Operations** = $6,000

### Pool distribution (% of prize pool)

| Pool # | Pool Name | % of Prize Pool | Winners |
|---|---|---:|---|
| 1 | **2nd Boss Checkpoint** | **50%** | 50% Leaderboard, 50% Random Draw |
| 2 | **2nd Mini Boss Checkpoint** | 25% | 50% LB, 50% Random |
| 3 | **1st Boss Checkpoint** | 15% | 50% LB, 50% Random |
| 4 | **1st Mini Boss Checkpoint** | 10% | 50% LB, 50% Random |

**Total**: 100%

**Key insight**: going deeper = exponentially bigger prize pools. The **2nd boss pool (50%)** is 5× the 1st mini-boss pool (10%). **Pushing past checkpoints is where the real money lives.**

### Distribution mechanics
- Leaderboards paid first, in score order, until 50% of the pool is distributed.
- Remaining 50% goes to random draw among eligible NFTs (weighted by score — higher score = higher odds).
- Each NFT can win only **1 prize**.
- If a final leaderboard winner pushes the % over the cap, overflow comes from the **next pool** (not the current one).

### NFT tiers
- **Standard**: $1
- **Premium**: $10
- **Degen**: $100

Winnings are `base payout × Loot Multiple`. Example: a Legendary $100 Degen run with 6× Loot Multiple that places in the 2nd boss pool by random draw wins `$100 × 6 = $600`.

## Stickers and Loot Multiple

Stickers are cosmetics that carry **Loot Points** — the currency that determines your **Loot Multiple**, which in turn determines your USDC payout.

### Sticker rarity → Loot Points

| Rarity | Loot Points |
|---|---:|
| Common | 1 |
| Rare | 2 |
| Legendary | 5 |
| Mythic | 11 |

### Loot Multiple → Loot Points needed (per step)

| Loot Multiple | LP per step | Cumulative LP from 0 |
|---:|---:|---:|
| 1× | 5 | 5 |
| 2× | 5 | 10 |
| 3× | 6 | 16 |
| 4× | 6 | 22 |
| 5× | 6 | 28 |
| 6× | 8 | 36 |
| 7× | 8 | 44 |
| 8× | 8 | 52 |
| 9× | 8 | 60 |
| 10× | 8 | **68** |

**Max Loot Multiple is 10×**, reached at 68 total Loot Points.

### Run mechanics
- **Bring up to 3 stickers** into a new run (pre-run choice).
- **1 complimentary starter sticker** equal to run's tier (Standard → Common, Premium → Rare, Degen → Legendary).
- **Sticker drop odds** depend on NFT tier (higher tier = better odds for rare stickers, compensating for higher per-run risk):

| Rarity | Standard odds | Premium odds | Degen odds |
|---|---:|---:|---:|
| Common | 60% | 38% | 35% |
| Rare | 24% | 38% | 36% |
| Legendary | 12% | 18% | 22% |
| Mythic | 4% | 6% | 7% |

**A $100 Degen run has 65% chance of non-common stickers per drop vs 40% for Standard.** Higher tiers pay off with better Loot Multiple climbs.

### Complete Sticker Sets
Completing a full set in a single run earns **bonus Loot Points**:

| Set | Pieces | Bonus LP |
|---|---|---:|
| Gold | Gold Helmet, Gold Armor, Gold Sword, Timeless Stopwatch, Crystal Badge | **15** |
| Avax | Centurion Helmet, Avax Armor, Ava-Axe, Lucky Dice, Avax Sash | **10** |
| Toxic | Gas Mask, Toxic Armor, Toxic Trident, Potion of Death | 7 |
| Frozen | Frigid Hood, Frozen Armor, Icesickle, Glint's Shield | 7 |
| Flaming | Firant Crown, Flaming Armor, Flamace, Molotov Cocktail | 7 |
| No Set | Bucket Hat, InVest, Echo Dagger, Moggers | 0 |

The **Gold set is the most valuable complete set** (+15 bonus LP on top of component values = Crystal Badge 11 + Gold Armor 5 + Timeless Stopwatch 2 + Gold Helmet 2 + Gold Sword 2 + 15 bonus = **37 LP from one set**, enough to go from 0 to 6× Loot Multiple.

### Sticker list (by rarity)

**Common (1 LP each)**: Avax Armor, Lucky Dice, Toxic Armor, Potion of Death, Frozen Armor, Frigid Hood, Flaming Armor, Flamace, Bucket Hat, InVest, Moggers

**Rare (2 LP each)**: Gold Helmet, Gold Sword, Timeless Stopwatch, Ava-Axe, Gas Mask, Icesickle, Molotov Cocktail, **Echo Dagger** (only obtainable via the Echo Dagger mystery event)

**Legendary (5 LP each)**: Gold Armor, Centurion Helmet, Glint's Shield, Toxic Trident, Firant Crown

**Mythic (11 LP each)**: Crystal Badge, Avax Sash

## Rules-engine implications

1. **Max run payout = base price × 10**. A $100 Degen run at max multiple is $1000 payout potential.
2. **Stack sticker drops pre-run**: bring 3 legendary stickers (15 LP) into a run to start at 2×→3× multiple territory.
3. **Pool incentive gradient**: surviving to 2nd boss is worth 5× more than surviving to 1st mini-boss. Always push the furthest checkpoint you can survive.
4. **Echo Dagger sticker** is only obtainable via the Echo Dagger mystery event, not random drops. Mystery event value is higher than random loot for this specific reward.
5. **Set completion in a single run** gives a bonus — the Gold set specifically (with a Mythic Crystal Badge) is enormously valuable if you can find all 5 pieces.
6. **In tournament mode**: play tier-appropriate. A Standard ($1) run aggressive-risking to 2nd boss has lower expected payout than a Degen ($100) run cautious-banking at 1st mini-boss, because the Degen base price × the legendary sticker odds shift.
