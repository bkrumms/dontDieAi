# AI Provider Program — Training Access & Dev Environment

## Free practice credits

- Don't Die supplies each provider with a **local/dev version of the game via API with no frontend** so providers can train rapidly and repeatedly.
- Practice mode is gated by **credits**. Providers get free credits airdropped.

## How to get credits

1. Create a new account at the **Local Build link** (dev environment).
2. Home page → top-left hamburger menu → **Referrals** → copy referral code.
3. Send the referral code to **Nick**.
4. Anomaly airdrops **20,000 Practice Credits** to start.

## Dev environment caveats

- This is a **dev environment** — every couple weeks it may get updated. **Some updates may adjust the API.**

## Usage limits (start conservative)

- **Use ≤ 1,000 credits per day** at the start. They don't yet know if there are costs on their end or if **CloudFlare will rate-limit (HTTP 429)**.
- If you see a 429 in the API response payload, send logs + screen capture to Anomaly. They can't configure Cloudflare but need the evidence.
- **Important integration note**: when running an agent through the API docs, the model must **analyze the payload return before issuing the next instruction** — that's where the 429 would appear.

## Cost policy

- Providers pay their own local costs (inference, compute).
- If Anomaly incurs costs because of provider training, they will request **USDC to cover it**. They'll be transparent about this. They describe it as "unexpected but might happen".

## Strong recommendation

- **Play the game a few times yourself** before training models. Concepts like "when to use Time Crystals" are not evident to a model from the API alone.

## Important Links (referenced in the doc)

- "Local Build for training" (the dev build URL — not pasted in the doc copy we have; request it from Nick).
- "API Docs" → `https://dd-api-dev.anomalygames.ai/api_docs`.
- Three "API Video Examples" listed at the bottom of the doc:
  1. Example to get user info
  2. Example to make a request to update user
  3. Example on what to give the agent for next instruction
