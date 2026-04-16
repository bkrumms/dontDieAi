# Stickers & Loot Multiple

Stickers are **cosmetics** in Don't Die — swap outfits at any time in the Backpack. But in **Tournament mode** they are economically critical because they boost your **Loot Multiple**, which determines your USDC payout if you win.

## Earning stickers

- **In-run drops**: after Big Baddie, Obelisk, and Boss battles.
- **Loot Dice** drop stickers.
- **Some Mystery Events** award stickers.
- **Shop**: buy with **Bones** (premium currency).
- **Packs**: buy sticker packs.
- **Community rewards**: Discord / similar.
- **Practice mode**: stickers earned in Practice can be worn in any run.

## Tournament rules

- You may bring **up to 3 stickers** into a new Tournament Run. This is your best chance to boost your Multiple early.
- At the start of a Tournament run you automatically receive **a Sticker of your run tier**.
- **Higher tier NFTs have higher odds of more rare stickers** — this compensates for higher per-run risk. Therefore it's **easier to reach 10x as a $100 run than as a $1 run**.

## Sticker rarity → Loot Points

| Sticker Rarity | Loot Points |
| -------------- | ----------- |
| Common         | 1           |
| Rare           | 2           |
| Legendary      | 5           |
| Mythic         | 11          |

## Loot Multiple → Loot Points to advance

| Loot Multiple range | Loot Points needed to increase Multiple |
| ------------------- | --------------------------------------- |
| 1x and 2x           | 5                                       |
| 3x thru 5x          | 6                                       |
| 6x thru 10x         | 8                                       |

- **Max Loot Multiple: 10x.**
- Total Loot Points to go from 1x → 10x: `5 (1→2) + 5 (2→3) + 6 (3→4) + 6 (4→5) + 6 (5→6) + 8 (6→7) + 8 (7→8) + 8 (8→9) + 8 (9→10) = 60 Loot Points`.

## API
- `GET /api/stickers` — full sticker pool (rarity, type).
- `GET /api/game/stickers?session_id=` — session stickers.
- `POST /api/game/stickers` — sync character stickers. Body: `{ session_id, stickersRequest[] }` **(max 5 items)**.
- `GET /api/user/inventory` — stickers, loot dice, tournament entries.
