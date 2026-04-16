# Status Effects (Battle Modifiers)

Canonical reference. Source: in-game "Battle Modifiers" image + dice-explainer image.

Five modifiers exist. Two are **buffs** (applied to self), three are **debuffs** (applied to a target, typically a baddie — but Curse sides can apply them to you).

## Strength — buff

> **Future attacks stronger**

- Applies to the **owner** of the status (you or a baddie).
- Persistent — stays on the character for multiple turns unless cleared.
- Additive/scalar — grows each time you gain more. The exact formula (flat +N vs. %N) is not pinned down; multiple sides explicitly write "Gain 3 Strength" which suggests **+3 to future attack values**, flat.
- Baddies can gain Strength too (e.g. `Snowfang Pack`, `Deathbat`, `Haunt`, `Detonox`).

**Rules-engine hint:** Strength compounds — preventing a baddie from stacking it (kill fast, or use "Baddies lose N Strength this turn" sides like the +20 Toxic Swamp one) is often higher value than raw damage.

## Armor — buff

> **Future block stronger**

- Persistent, parallel to Strength but for Block.
- "Gain N Armor" likely adds +N to all future Block amounts on the owner.
- Baddies with Armor: `Frigid Interloper` (Perma Block), `Cryonic Zomboid`, `Pterrordactyl` (steals Armor).

**Rules-engine hint:** stacking Armor is strong for late-battle survival but does nothing the first turn. Treat "Gain N Armor at end of each turn" as a 3+ turn investment.

## Freeze — debuff

> **Attack 25% weaker**
> **Block 25% weaker**

- Affects both offensive and defensive output of the owner by 25%.
- The sides database uses "Freeze 3" / "Freeze all 3" as verbs, which probably means **3 stacks** — one stack decays per turn? Not confirmed; could also be a duration. Flag for Nick.
- Multiple baddies apply Freeze to you (`Ice Pufflet`, `Wendlbrrr`, `Frigid Interloper`).
- Immunity exists via the `Kronicles Mask` trinket. `Wendlbrrr` cannot be frozen.

**Rules-engine hint:** Freeze on a baddie is a 25% damage mitigation AND a 25% damage amplification (since their blocks also weaken). Stack it before the baddie's big turn.

## Bleed — debuff

> **Take 50% more damage**

- Owner takes 50% more incoming damage while Bleed is active.
- **Enormous multiplier.** If you can land Bleed on a Big Baddie before your burst turn, it's roughly a 1.5x multiplier on that burst.
- Multiple Ice Cave and Volcano sides combine Attack + Bleed (`Attack 6, Bleed 2`, `Attack 16, Bleed 2, Freeze 2`, `Block 8, Bleed 3`).
- Immunity exists via the `Ket Mask` trinket. `Gorgon-zola` reflects Bleed.

**Rules-engine hint:** Bleed-before-burst is one of the highest-EV combos in the game. When a die rolls a Bleed side early in the turn order and a high-damage side late, keep it — the ordering is already optimal.

## Poison — debuff

> **Persistent. Lose HP equal to poison at turn end.**

- End-of-turn tick: damage equal to current Poison stacks.
- Persists. Decay rate not specified in the image — could be "poison stays fixed until cured" or "decrements by 1 each tick". The Toxic Swamp +30 side "Cure Poison at the start of your turn" and the mystery event `Poison Veins` imply poison is sticky and must be actively removed or it kills you.
- Baddies with Poison: `Baby Scarebug` (Increasing Poison), `Gorgon-zola` (High Poison), `Noxious Interloper`, `Necrotic Zomboid`, `Batty`.
- Immunity pattern: `Lizard Mask` (Poison all 4 at start of battle), `Toxipop` food (transfer on kill).

**Rules-engine hint:** in Toxic Swamp, poison is the death clock — if you can't cure it you need to end the battle faster than it ticks you out. Use `Cure Poison at start of turn` or `Remove all debuffs` as priority sides.

## Curses (purple sides)

Not a status effect, but relevant here: **Curse sides are marked purple** in the UI. The dice-explainer image explicitly says **"Purple dice are Curses. Try to burn these off."** This confirms:

- Curse sides are visually identifiable as purple.
- They're enemy-applied (or bad-mystery-event-applied) and should be burned at the first opportunity.
- See the Curse entries in `database/sides.md` for the full list (9 curses).

**Rules-engine hint (hard rule):** never skip a burn opportunity when any die carries a Curse side. "Duplicate this Side on this Die" is the worst — it compounds itself.
