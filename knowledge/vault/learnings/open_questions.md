# Open Questions

Questions the vault has raised but not yet fully answered. Each question drives
future run analysis. When a question accumulates enough data to answer, move it
to the Answered section and update the relevant side/enemy/learning notes.

**Minimum sample size to answer a question: 25 runs** with the relevant build
composition. Below 25 is suggestive only and should stay as hypothesis status.

Format:
- **Question** — what we want to know
- **Why it matters** — what decision it changes
- **Current data** — what the vault already shows
- **What would answer it** — what to look for in future runs
- **Status** — hypothesis / investigating / answered

---

## Active Questions

---

### Q1: Is multiplier the single biggest lever across all four dice?

**Why it matters:** If having any multiplier (Attack 16 Dup, Perm+2, 2x damage)
anywhere in the build is worth +10% regardless of where it lands, we should treat
multiplier acquisition as the highest-priority pick for whichever die offers it first.

**Current data:** Build profiles show:
- offense + defense + freeze + strength + multiplier = 69.5% (484 runs)
- offense + defense + freeze + strength (no multiplier) = 58.5% (407 runs)
- Delta: +11.0% for having one multiplier anywhere

Per-die multiplier placement (1,622 anchor runs):
- Die 0 (utility): n=396, win=66.7%, delta=**+0.5%** ← essentially neutral
- Die 1 (attack):  n=454, win=69.6%, delta=**+3.5%**
- Die 2 (mixed):   n=378, win=68.8%, delta=**+2.6%**
- Die 3 (defense): n=252, win=69.0%, delta=**+2.9%**

**Conclusion:** Multiplier on the utility die is nearly worthless (+0.5%). On attack,
mixed, or defense die it adds +2.6–3.5%. **Do not prioritise multiplier on the utility
die over a strong utility-role side — put it on any other die first.**

**What remains open:** Why is utility die neutral? Likely because the utility die
rolls exhaustible sides (Strength, Armor) that compound regardless — a multiplier
there doesn't amplify the core output. Further investigation needed.

**Status:** partially answered — placement matters, utility die is the worst slot

---

### Q2: Does the Perm Block +4 + Freeze 3 trap combo happen because both land on the defense die?

**Why it matters:** This is the biggest trap combo in the data (-30.8% on 14 runs).
If it's because both crowd the defense die with non-block output, the lesson is
"don't put Freeze 3 on the defense die." If it's a cross-die anti-synergy, the
lesson is broader.

**Current data:** `side_pairs.md` shows (e) Block +4 + Attack 12 Freeze 3 = 35.7%.
The pair analysis is same-die only, so we know they ended up on the same die.
The defense die taking a Freeze 3 side instead of pure block means one roll in
four is wasted offense that doesn't help defense either.

**What would answer it:** Check run notes where both sides are present. Which die
index did each land on? Does the combo hurt less when Freeze 3 is on the attack die?

**Related:** [[sides/(e) Block 2_ Permanently increase the Block gained on this Side by 4]]
[[sides/Attack 12, Freeze 3]]

**Status:** hypothesis — likely a defense die contamination problem

---

### Q3: Is poison density or freeze+attack the stronger Ch2 kill strategy?

**Why it matters:** By Ch2 the bot often has one or the other, rarely both. Knowing
which path clears more Ch2 content would let us prioritize differently in Ch1.

**Current data:** 
- `cross_die_pairs.md` shows (e) Freeze all 3/Bleed 4/Poison 5 + Attack 28 = 90.3% Ch1 (31 runs) 
- Poison all 4 + Poison 8 Heal 1 = 92.9% Ch1 (14 runs)
- Both are strong in Ch1 but Ch2 data is thin (only 66 Ch2 clears total)

**What would answer it:** Run a dedicated batch of 200 runs with HERMES_ENABLED
tracking which archetype (poison-heavy vs freeze-attack) reaches Ch2 and clears it.
Need to tag run archetypes at the Ch1 boss fight, not just track individual sides.

**Status:** investigating — insufficient Ch2 sample

---

### Q4: How much does having a heal source matter vs just having more block?

**Why it matters:** Heal and block are both survival options. The build profiles
show having heal adds +1.1% over no-heal (with multiplier). That's surprisingly
small. But is heal more valuable in specific fight compositions (e.g., multi-hit)?

**Current data (updated 2026-05-31):**
Heal 8 EOB specifically broken down by offense context (1,622 anchor runs):
- Heal 8 EOB **with** strong offense (Atk28/Dup/Poison4/(e)Freeze): n=174, win=70.1%, delta=**+4.0%**
- Heal 8 EOB **without** strong offense: n=89, win=55.1%, delta=**-11.1%**

Cross-die anti-synergy: Heal 8 EOB + Block 8 Gain Armor = 49.0% on 51 runs (-17.1%)

**Conclusion:** Heal 8 EOB is strongly context-dependent. With strong offense backing
it, it's a mild positive. Without it, it's a significant trap (-11.1%). The likely
mechanism: when a run lacks kill speed, heal just delays the inevitable. Only pick
Heal 8 EOB if you already have a strong offensive anchor elsewhere in the build.

**What remains open:** Does this hold for other heal sources (Heal 2 EOT, Poison 8
Heal 1)? Those might behave differently since they're passive and don't consume a
high-value slot.

**Related:** [[enemies/Pterrordactyl]] [[enemies/Snowfang Pack + Snowfang Pack + Snowfang Pack_B Pool 4_]]

**Status:** partially answered — Heal 8 EOB is context-dependent; other heal types still open

---

### Q5: Is Attack equal to Block a trap side or build-dependent?

**Why it matters:** Memory flags this as suspicious (penalised equal to block
without heavy block). But `cross_die_pairs.md` shows Attack equal to Block +
Freeze Attack +20 = 84.6% on 26 runs (+18.5%).

**Current data (updated 2026-05-31):**
Attack equal to Block by block count on the same die at Ganondwarf:
- Same die has **≥2 block sides**: n=82, win=65.9%, delta=**-0.3%** ← neutral even with block floor
- Same die has **<2 block sides**: n=32, win=56.2%, delta=**-9.9%** ← significant trap

**Conclusion:** Attack equal to Block needs at least 2 other block sides on the same
die just to be neutral. With a low block floor it's a -10% trap. The cross-die
synergy with Freeze Attack +20 is likely driven by the freeze context, not the combo
itself. **This side is a trap unless the defense die already has strong block density.**

**Related:** [[sides/Attack equal to Block]] [[sides/Block 3 times the current turn]]

**Status:** answered — trap without block floor (≥2 block sides on same die required for neutral)

---

### Q6: What is the minimum viable defense die to beat Ganondwarf?

**Why it matters:** The defense die is the most consequential single die for survival.
Knowing the floor (e.g., must have Block 12 EOT OR Block 8 Gain Armor + one other
block side) would give a clear upgrade target.

**Current data:** `cross_die_pairs.md` shows Block 12 EOT paired with almost
anything offensive = 90-100% win rate. But Block 12 EOT is a late/rare pick.
What does a "good enough" defense die look like without it?

**What would answer it:** Cluster defense die compositions at Ganondwarf fight into
tiers (total expected block per turn) and measure win rate per tier.

**Status:** investigating — needs die-level block scoring analysis

---

### Q7: Can a high heal + poison build be competitive?

**Current data (updated 2026-05-31):**
Defined as ≥2 poison/bleed sides AND ≥1 heal side across all dice at Ganondwarf:
- **n=731 qualifying runs**, win=68.8%, delta=**+2.6%** vs 66.2% anchor baseline

**Conclusion:** The archetype is essentially average (+2.6% is within noise at this
sample size). Heal+poison is not a distinct winning path — the poison sides are doing
the work and the heal is a passenger. The cross-die pair showing (e) Poison all 2/3
+ Heal 8 EOB = 86.5% is driven by the poison density, not the heal. See Q4 for why
Heal 8 EOB specifically is context-dependent.

→ **Moving to Answered.**

**Related:** [[sides/Poison 8, Heal 1]] [[sides/Poison all 4]]

**Status:** answered — not a distinct archetype; poison density drives wins, heal is neutral

---

## Answered Questions

---

### A2: Is Attack equal to Block a trap or build-dependent?

**Answer:** Trap without a block floor. Needs ≥2 block sides on the same die just
to be neutral (-0.3%). With <2 block sides it's -9.9%. Only viable on a
block-dense defense die that doesn't need the slot for pure block anyway.

**Evidence:** 82 runs (high floor) vs 32 runs (low floor), 2026-05-31 analysis.
[[sides/Attack equal to Block]]

**Answered:** 2026-05-31

---

### A3: Can a high heal + poison build be competitive?

**Answer:** No — it's an average build, not a distinct archetype. 731 qualifying
runs show only +2.6% vs baseline. Poison density drives wins; the heal is a
passenger. Don't prioritise heal sides to "enable" a poison build.

**Evidence:** 731 anchor runs with ≥2 poison/bleed + ≥1 heal, 2026-05-31.

**Answered:** 2026-05-31

---

### A1: Does having freeze anywhere in the build matter?

**Answer:** Yes — every single run profile in the build_profiles data includes freeze.
There are no significant-sample runs without it. Freeze is effectively mandatory
by Ch1 boss.

**Evidence:** [[learnings/build_profiles]] — all 4 profiles include freeze pillar.

**Answered:** 2026-05-30
