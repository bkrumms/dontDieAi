# Don't Die — Knowledge Base

Queryable reference compiled from:

1. **API** — `https://dd-api-dev.anomalygames.ai/openapi.json` (OpenAPI 3.1 spec)
2. **Notion FAQ** — "Don't Die How to Play + FAQ" (public)
3. **AI Provider Program** — internal Google Doc ("Don't Die AI for Providers")
4. **Nick's Game Database** (2026-04-13 export) — authoritative: Dice Sides CSV + HTML exports covering baddie attack patterns, encounter loot, map design, mystery events, points, prizes/stickers, and trinkets/food. Raw TSVs preserved under `data/raw/nick_db/`.
5. **Live watch sessions** — 4 runs logged via `scripts/watch_run.py` with state diffs captured in `data/runs/`.

Per project rule: **live API observations > Nick's sheet > other sources** when they disagree.

## Layout

```
knowledge/
├── game/                        Gameplay mechanics, rules, numbers
│   ├── overview.md              One-paragraph summary + chapters
│   ├── status-effects.md        Strength/Armor/Freeze/Bleed/Poison mechanics
│   ├── dice-sides-upgrades.md   Dice/upgrade flow, side types, exhaust, prefixes
│   ├── map-movement-odds.md     Movement die (1,2,2,3,3,4) + rewind rules
│   ├── map-design.md            **NEW**: Map generation algorithm + encounter placement rules
│   ├── biomes.md                La Volcano / Ice Cave / Toxic Swamp archetypes
│   ├── battle.md                Turn order, modifiers, rearranging dice
│   ├── scoring.md               **REWRITTEN**: Complete point formulas (kill, HP, speed, damage)
│   ├── time-crystals.md         Rewind mechanics
│   ├── burns.md                 Removing sides; min 4 sides per die
│   ├── bub-shop.md              Pay with gold or health
│   ├── food-trinkets.md         Food/trinket overview (drops vs use)
│   ├── stickers-loot-multiple.md   How stickers drive USDC payouts
│   ├── checkpoints.md           4 checkpoints, tournament unstake flow
│   ├── backpack.md              UI inventory
│   ├── mystery-events.md        **REWRITTEN**: All 16 events with full decisions + pool structure
│   ├── encounter-loot.md        **NEW**: Drop tables, Bub's pricing, campfire options, trinket/food/TC odds
│   ├── prizes-stickers.md       **NEW**: Prize pool distribution + sticker rarity + Loot Multiple math
│   ├── boss-big-cheeze.md       **NEW**: Chapter 2 boss — all 7 modes
│   ├── watch-mode.md            How to use the passive run watcher
│   └── database/                Raw data from Nick's sheet + live observations
│       ├── sides.csv            81 sides (pool + biome + effect + exhaust)
│       ├── sides.md             Grouped reference + glossary + prefix notes
│       ├── baddies.csv          **NEW**: Full attack patterns (29 enemies incl. horde)
│       ├── baddies.md           **REWRITTEN**: Turn-by-turn patterns for every baddie
│       ├── food.csv             15 foods (11 common + 4 rare)
│       ├── food.md              Food archetypes + counter-picks
│       ├── trinkets.csv         21 trinkets (10 common + 4 rare + 7 boss)
│       └── trinkets.md          Trinket archetypes + stacking notes
├── api/                         OpenAPI reference
│   ├── overview.md
│   ├── session-character.md     /api/character reads
│   ├── session-lifecycle.md     start/stake/forfeit
│   ├── map.md                   roll/reroll/proceed
│   ├── battle.md                Battle scene + loot phase
│   ├── mystery-events.md        All /api/game/mystery/* endpoints
│   ├── campfire-shop-loot.md    Campfire, loot dice, Bub's
│   ├── inventory-wallet.md      User inventory + wallet linking
│   ├── quests-rewards-referral.md
│   └── schemas.md               Recurring object shapes
├── ai-provider-program/         Monetization and integration with Anomaly
│   ├── overview.md
│   ├── player-experience.md
│   ├── training-access.md
│   └── monetization.md
└── watch-mode.md                Watch-mode workflow (also copied in game/)
```

## Quick lookup

- **Odds of rolling a 2 or 3 on the map die?** → `game/map-movement-odds.md` (33.3% each, 66.7% combined)
- **What's the best food vs Ganondwarf?** → `game/database/food.md` — **Ice Rice** (confirmed in run 4 vs run 2 death)
- **What are the 7 Big Cheeze modes?** → `game/boss-big-cheeze.md`
- **How many points does a turn-1 win score in chapter 2?** → `game/scoring.md` (Speed Bonus 3000 + kill points 300-2000)
- **Which mystery events appear in chapter 1 spaces 10-20?** → `game/mystery-events.md` (ME Pool 2)
- **What's the TC drop rate after a chapter-2 big-baddie stop fight?** → `game/encounter-loot.md` (80% 2TC, 20% 3TC)
- **Max Loot Multiple?** → 10× at 68 total Loot Points (`game/prizes-stickers.md`)
- **Curse sides — how to identify?** → Purple borders + `Curse` tag. See `game/database/sides.md`
- **How do Level 3 side drops scale?** → Dynamic x-counter per chapter; `game/encounter-loot.md` has the full algorithm
- **What does Nick's database add?** → See `data/raw/nick_db/*.tsv` for raw exports

## Known data discrepancies (live vs Nick's sheet)

Per the **live > CSV** rule, when the live API shows a different label than Nick's sheet, use the live label. Observed discrepancies in sides.csv labels:

| Nick's sheet | Live API label |
|---|---|
| `Freeze all 3, Block 10` | `(e) Block 10, Freeze All 3` |
| `Attack 6, Bleed 2` | `Attack 6 Bleed 2` |
| `Poison all 2, 3 times` | `(e) Poison all 3, 3 times` (value changed!) |
| `Attack 16. Permanently increase the Attack on this Side by +2` | `(e) Attack 16. Permanently increase the Attack on this Side by 2` |
| `Gain 2 Armor at the end of each turn` (exhaust No) | `(p) Gain 2 Armor at the end of each turn` (exhaust Yes) |
| `Gain 4 Strength at the end of each turn` (exhaust No) | `(p) Gain 4 Strength at the end of each turn` (exhaust Yes) |
| `Score 100 Points any time you Block` | `(p) Score 100 Points any time you Block` |
| `Heal 2 at the end of each turn` | `(p) Heal 2 at the end of each turn` |
| `Freeze self 2` (Curse) | `Afflict yourself with 2 Freeze` |
| `Block 40` | `(e) Block 40` |

The rules engine should match sides by **API id** (numeric), not by label. Labels are for human reference only.
