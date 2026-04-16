# Quests, Reward Pass, Referral

## Quests
- `GET /api/quests` — array of quests with `id`, `title`, `description`, `type`, `reward_type`, `reward`, `userQuest` status, `claimable`, `isOnCooldown`, `nextResetAt`.
- `POST /api/quests` — submit completion. Body: `category: "daily" | "credits"`. Returns: submitted count, credits earned, `bp_points`.

## Reward Pass
- `GET /api/reward-pass` — `userBattlePass` object with `currentXp`, `currentStep`.

## Referral
- `POST /api/telegram-referral` — `username`, `telegram_user_id`, `referral_user_id`.
- `GET /api/referral-count` — `novalink_user_id`, `referral_count`.
- `GET /api/referral-balance` — `available_usd`, `minted_usd`, `total_earned_usd`, `updated_at`.
- `POST /api/referral-claim` — claim as NFTs. Body: `tier: "standard"`. Returns `claimId`, `tier`, `nft_count`, `mint_amount_usd`, `nftsByTier`.

## Metadata
- `GET /api/version` — version info.
- `GET /api/changelog?ref=` — changelog content (string or number env ref).
