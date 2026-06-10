# Don't Die Vault — Usage Guide for Claude

This vault is an analytical database built from autonomous game runs. Its purpose
is to inform pick decisions during runs, answer strategic questions, and surface
non-obvious patterns across thousands of games.

## What This Vault Is For

**Primary use:** When evaluating a side pick or build direction, consult this vault
before reasoning from first principles. The data here represents observed outcomes
across 1,700+ runs — it overrides intuition when sample sizes are sufficient (n≥20).

**Secondary use:** When a strategic question comes up in conversation, check
`learnings/open_questions.md` first. If the question is already tracked, use the
current hypothesis. If it's new, add it.

## How to Navigate a Pick Decision

1. **Check `sides/<side_name>.md`** for the side being offered — win rate, ch1 delta,
   known synergies and anti-synergies with other sides already on the die.

2. **Check `learnings/side_pairs.md`** for any pair involving this side + a side
   already on the same die. A -30% delta trap combo overrides a side that looks
   good in isolation.

3. **Check `learnings/cross_die_pairs.md`** for cross-die interactions — especially
   if the pick would create a freeze source/payoff split or an offense/defense
   balance across dice.

4. **Check `learnings/build_profiles.md`** to verify the build still has all four
   pillars: offense, defense, freeze, strength. A build missing a multiplier by
   Ganondwarf is -7.8% vs baseline. A build missing defense entirely is almost
   always a loss.

5. **Check `enemies/<upcoming_boss>.md`** for any immunity or dangerous-side-combo
   data specific to the fight ahead.

## What "Useful" Means Here

A vault note is useful when it changes a pick decision or answers a strategic
question that would otherwise be guessed at.

- A side note with n≥20 and a delta >+15% is decision-grade signal — follow it.
- A pair with n≥10 and delta >+20% is strong — weight it heavily.
- A pair with n<10 is suggestive only — note it but don't override scoring.
- Build profile data (n≥100) is the most reliable signal in the vault.

## What to Ignore

- Enemy notes with encounters <10 — too few samples.
- Side notes with runs <5 — noise.
- Any note marked `status: hypothesis` in open_questions.md — treat as a question
  to investigate, not a conclusion to act on.

## Active Open Questions

See `learnings/open_questions.md` for questions the vault hasn't fully answered yet.
These drive what future run batches should test.

## Contribution Tracking

Each side note and enemy note has a `use_count` frontmatter field. When a note
directly influenced a pick decision or answered a question, increment it. Over time
this shows which notes are load-bearing vs dead weight.
