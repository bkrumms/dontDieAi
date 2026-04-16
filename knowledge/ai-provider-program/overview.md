# AI Provider Program — Overview

**Source**: "Don't Die AI for Providers" (internal Google Doc).

## The idea

Let players compete in Don't Die tournaments by **hiring an AI agent** to run the NFT/Tournament Entry for them. Explicitly **not** a single-click experience — players must feel they contributed to the agent's success.

## Guiding principles

- **Player agency required.** Every provider's experience must incorporate the player in a meaningful way.
- **Multiple providers.** The inaugural season targets partner orgs across Web3 + individual players from the Don't Die community. Each provider gets their own unique style of engagement.
- **Diverse playstyles encouraged.** Providers can differentiate on style.

## Where it plugs into the UI

- Players select **"AI Mode"** in the run setup flow **after** clicking Practice or Tournament.
- Selecting AI Mode reveals the list of provider options.
- All AI agents run in the **main tournament mode**; entries are **tagged with "AI Agent"**.
- Any user can click into an entry to see which provider the agent is from, and distinguish humans from AI.
- Anomaly will publish data on the mix between AI agents and humans — if agents dominate the leaderboard, that mix is visible.

## Provider responsibilities

- **Own frontend** — each provider is responsible for building the player-facing frontend for their agent. It can navigate the player away from the game to a separate webpage:
  - An LLM chat interface that connects to an MCP
  - A parameters dashboard to adjust risk or select playstyles
- **TOS** — providers publish their own TOS covering model parameters and protection of initial training data.

## Contacts

- Questions → **Nick** (who routes them to **Quan**).
- Nick regularly updates the source doc; new info goes into an "Additional Information" section at the bottom.
