# Inventory, Stickers, Wallet

## Inventory
- `GET /api/user/inventory` — stickers, loot dice, tournament entries.
- `GET /api/stickers` — full sticker pool (rarity, type, timestamps).
- `GET /api/game/stickers?session_id=` — session-specific stickers.
- `POST /api/game/stickers` — sync character stickers. Body: `session_id`, `stickersRequest[]` **(max 5 items)**.

## Wallet
- `GET /api/wallet` — user wallet addresses `[{type, address}]`.
- `POST /api/wallet` — link wallet. Body: `walletId`, `chain`, `signature`, `message`.
- `DELETE /api/wallet` — unlink AVAX wallet. Returns deletion boolean.
