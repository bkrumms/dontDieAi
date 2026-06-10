#!/usr/bin/env python3
"""Generate an Obsidian vault from training run data.

Reads data/full_runs/*/  and writes knowledge/vault/:
  runs/YYYY-MM/run_<id>.md      — one note per run
  enemies/<name>.md             — aggregate stats + dangerous/good side combos
  sides/<name>.md               — pick rate, win rates, synergies
  learnings/side_pairs.md       — combos that significantly move win rate
  learnings/death_patterns.md   — what kills runs and why
  _index.md                     — dashboard

Usage:
  python scripts/generate_vault.py
  python scripts/generate_vault.py --min-samples 5   # lower bar for patterns
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RUNS_DIR = Path("data/full_runs")
VAULT = Path("knowledge/vault")

DIE_ROLES = {0: "utility", 1: "attack", 2: "mixed", 3: "defense"}

# ─── helpers ──────────────────────────────────────────────────────────────────

def safe_filename(s: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", s).strip().strip(".")


def pct(n, d):
    return f"{n/d*100:.1f}%" if d else "0%"


def load_initial_dice(run_dir: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Return ({die_id: [side_labels]}, starter_side_labels) from the first char step."""
    for path in sorted(run_dir.glob("*_it001_char*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = {}
            starters: set[str] = set()
            for die in (data.get("dices") or []):
                die_id = die.get("id") or die.get("uuid", "")
                sides = []
                for a in (die.get("ability") or []):
                    if not isinstance(a, dict):
                        continue
                    label = a.get("label", "?")
                    sides.append(label)
                    tags = [t.get("label", "") for t in (a.get("tags") or []) if isinstance(t, dict)]
                    if "Starter" in tags:
                        starters.add(label)
                result[die_id] = sides
            return result, starters
        except Exception:
            pass
    return {}, set()


def classify_run(summary: dict) -> tuple[int, str]:
    """(chapter_cleared, death_entity)"""
    battles = summary.get("battles") or []
    end_reason = summary.get("end_reason", "unknown")
    bosses_beaten = []
    last_lost = None
    for b in battles:
        if b.get("result") == "lost" and last_lost is None:
            last_lost = b
        for m in (b.get("monsters") or []):
            for tag in (m.get("tags") or []):
                if "Boss Pool" in tag and b.get("result") == "won":
                    try:
                        bosses_beaten.append(int(tag.split("Pool")[1].strip()))
                    except Exception:
                        pass
    chapter_cleared = max(bosses_beaten) if bosses_beaten else 0
    if last_lost:
        mons = last_lost.get("monsters") or []
        death_to = " + ".join(m.get("name", "?") for m in mons) if mons else end_reason
    else:
        death_to = end_reason
    return chapter_cleared, death_to


def reconstruct_die_state(
    initial: dict[str, list[str]], summary: dict
) -> dict[str, list[str]]:
    """Replay all picks onto initial die state. Returns {die_id: [sides]}."""
    state = {k: list(v) for k, v in initial.items()}
    for b in (summary.get("battles") or []):
        die_id = b.get("picked_die_id")
        label = b.get("picked_ability_label")
        if die_id and label:
            if die_id not in state:
                state[die_id] = []
            state[die_id].append(label)
    return state


# ─── run model ────────────────────────────────────────────────────────────────

class RunModel:
    def __init__(self, run_dir: Path, summary: dict):
        self.run_id = run_dir.name
        self.summary = summary
        self.battles = summary.get("battles") or []
        self.end_reason = summary.get("end_reason", "unknown")
        self.chapter_cleared, self.death_to = classify_run(summary)
        self.initial_dice, self.starter_sides = load_initial_dice(run_dir)
        self.final_dice = reconstruct_die_state(self.initial_dice, summary)
        # all sides ever on any die during the run
        self.all_sides_picked: list[str] = [
            b["picked_ability_label"] for b in self.battles
            if b.get("picked_ability_label")
        ]
        # sides on each die (final state)
        self.sides_per_die: list[list[str]] = list(self.final_dice.values())
        # flat unique sides
        self.unique_sides: set[str] = set()
        for sides in self.sides_per_die:
            self.unique_sides.update(sides)
        for sides in self.initial_dice.values():
            self.unique_sides.update(sides)

    @property
    def ch1_cleared(self):
        return self.chapter_cleared >= 1

    @property
    def ch2_cleared(self):
        return self.chapter_cleared >= 2

    def die_state_before_battle(self, battle_num: int) -> dict[str, list[str]]:
        """Reconstruct die state just before a given battle number."""
        state = {k: list(v) for k, v in self.initial_dice.items()}
        for b in self.battles:
            if b.get("num", 0) >= battle_num:
                break
            die_id = b.get("picked_die_id")
            label = b.get("picked_ability_label")
            if die_id and label:
                if die_id not in state:
                    state[die_id] = []
                state[die_id].append(label)
        return state


# ─── load all runs ─────────────────────────────────────────────────────────────

def load_runs(min_battles: int = 1) -> list[RunModel]:
    runs = []
    for d in RUNS_DIR.iterdir():
        s = d / "_summary.json"
        if not s.exists():
            continue
        try:
            summary = json.loads(s.read_text(encoding="utf-8"))
        except Exception:
            continue
        if len(summary.get("battles") or []) < min_battles:
            continue
        runs.append(RunModel(d, summary))
    return runs


# ─── statistics ───────────────────────────────────────────────────────────────

def compute_side_stats(runs: list[RunModel]) -> dict:
    """For each side: pick_count, ch1_win_rate, ch2_win_rate, die_roles."""
    stats: dict[str, dict] = {}
    for r in runs:
        for side in r.unique_sides:
            if side not in stats:
                stats[side] = {"picks": 0, "ch1_wins": 0, "ch2_wins": 0, "runs": 0}
            stats[side]["picks"] += 1
            stats[side]["runs"] += 1
            if r.ch1_cleared:
                stats[side]["ch1_wins"] += 1
            if r.ch2_cleared:
                stats[side]["ch2_wins"] += 1
    return stats


def compute_enemy_stats(runs: list[RunModel]) -> dict:
    """For each enemy: encounters, wins, hp_lost_avg, sides_at_fight."""
    stats: dict[str, dict] = defaultdict(lambda: {
        "encounters": 0, "wins": 0, "hp_lost": [], "sides_at_fight": Counter()
    })
    for r in runs:
        for b in r.battles:
            for m in (b.get("monsters") or []):
                name = m.get("name", "?")
                stats[name]["encounters"] += 1
                if b.get("result") == "won":
                    stats[name]["wins"] += 1
                hp_before = b.get("hp_before", None)
                hp_after = b.get("hp_at_end", None)
                if hp_before and hp_after:
                    stats[name]["hp_lost"].append(hp_before - hp_after)
                # sides active at this fight
                state = r.die_state_before_battle(b.get("num", 999))
                for sides in state.values():
                    for side in sides:
                        stats[name]["sides_at_fight"][side] += 1
    return stats


def _boss_battle_num(run: "RunModel", boss_name: str = "Ganondwarf") -> int | None:
    """Return the battle number of the first encounter with boss_name, or None."""
    for b in run.battles:
        for m in (b.get("monsters") or []):
            if m.get("name") == boss_name:
                return b.get("num")
    return None


def compute_side_pair_stats(runs: list[RunModel], min_samples: int = 25) -> list[dict]:
    """Find acquired-side pairs that affect Ganondwarf win rate.

    Analysis is anchored to the die state BEFORE the Ganondwarf fight (or before
    the killing battle for runs that never reached Ganondwarf). This avoids
    survivorship bias where successful runs naturally accumulate more sides.

    Starter sides are excluded from both slots.
    """
    # Determine which runs reached Ganondwarf and what happened
    anchor_states: list[tuple[dict[str, list[str]], bool, "RunModel"]] = []
    for r in runs:
        gano_num = _boss_battle_num(r, "Ganondwarf")
        if gano_num is not None:
            # Use die state just before Ganondwarf
            state = r.die_state_before_battle(gano_num)
            beat_gano = any(
                b.get("result") == "won" and
                any(m.get("name") == "Ganondwarf" for m in (b.get("monsters") or []))
                for b in r.battles
            )
            anchor_states.append((state, beat_gano, r))
        else:
            # Never reached Ganondwarf — find death battle and use state before it
            death_battle = next(
                (b.get("num") for b in r.battles if b.get("result") == "lost"), None
            )
            if death_battle is None:
                continue
            # Only include if died to a real enemy (not infra)
            if r.end_reason in ("start_session_failed", "state_fetch_failed",
                                 "stuck", "battle_error"):
                continue
            state = r.die_state_before_battle(death_battle)
            anchor_states.append((state, False, r))

    if not anchor_states:
        return []

    baseline_ch1 = sum(1 for _, beat, _ in anchor_states if beat) / len(anchor_states)

    pair_data: dict[tuple, dict] = defaultdict(lambda: {"runs": 0, "wins": 0})

    for state, beat_gano, r in anchor_states:
        seen_pairs: set[tuple] = set()
        for die_sides in state.values():
            acquired = sorted(set(s for s in die_sides if s not in r.starter_sides))
            for i in range(len(acquired)):
                for j in range(i + 1, len(acquired)):
                    pair = (acquired[i], acquired[j])
                    if pair not in seen_pairs:
                        seen_pairs.add(pair)
                        pair_data[pair]["runs"] += 1
                        if beat_gano:
                            pair_data[pair]["wins"] += 1

    results = []
    for (a, b), d in pair_data.items():
        n = d["runs"]
        if n < min_samples:
            continue
        win_rate = d["wins"] / n
        delta = win_rate - baseline_ch1
        if abs(delta) < 0.12:
            continue
        results.append({
            "side_a": a, "side_b": b,
            "runs": n, "ch1": d["wins"], "ch2": 0,
            "ch1_rate": win_rate, "ch2_rate": 0.0,
            "delta": delta,
        })

    return sorted(results, key=lambda x: abs(x["delta"]), reverse=True)


def _build_anchor_states(runs: list[RunModel]) -> list[tuple[dict[str, list[str]], bool, "RunModel"]]:
    """Shared helper: returns (die_state_at_anchor, beat_ganondwarf, run) for each run."""
    anchor_states = []
    for r in runs:
        gano_num = _boss_battle_num(r, "Ganondwarf")
        if gano_num is not None:
            state = r.die_state_before_battle(gano_num)
            beat_gano = any(
                b.get("result") == "won" and
                any(m.get("name") == "Ganondwarf" for m in (b.get("monsters") or []))
                for b in r.battles
            )
            anchor_states.append((state, beat_gano, r))
        else:
            if r.end_reason in ("start_session_failed", "state_fetch_failed",
                                 "stuck", "battle_error"):
                continue
            death_battle = next(
                (b.get("num") for b in r.battles if b.get("result") == "lost"), None
            )
            if death_battle is None:
                continue
            state = r.die_state_before_battle(death_battle)
            anchor_states.append((state, False, r))
    return anchor_states


def compute_cross_die_pair_stats(runs: list[RunModel], min_samples: int = 25) -> list[dict]:
    """Find pairs of acquired sides on DIFFERENT dice that affect Ganondwarf win rate.

    e.g. freeze source on die 1 + freeze payoff on die 2. Anchored to the same
    Ganondwarf/death-battle state as the intra-die analysis.
    """
    anchor_states = _build_anchor_states(runs)
    if not anchor_states:
        return []
    baseline = sum(1 for _, beat, _ in anchor_states if beat) / len(anchor_states)

    pair_data: dict[tuple, dict] = defaultdict(lambda: {"runs": 0, "wins": 0})

    for state, beat_gano, r in anchor_states:
        # Build per-die acquired side lists
        dice_acquired = []
        for die_sides in state.values():
            acquired = sorted(set(s for s in die_sides if s not in r.starter_sides))
            if acquired:
                dice_acquired.append(acquired)

        # Pairs across different dice only
        seen_pairs: set[tuple] = set()
        for di in range(len(dice_acquired)):
            for dj in range(di + 1, len(dice_acquired)):
                for sa in dice_acquired[di]:
                    for sb in dice_acquired[dj]:
                        pair = tuple(sorted([sa, sb]))
                        if pair not in seen_pairs:
                            seen_pairs.add(pair)
                            pair_data[pair]["runs"] += 1
                            if beat_gano:
                                pair_data[pair]["wins"] += 1

    results = []
    for (a, b), d in pair_data.items():
        n = d["runs"]
        if n < min_samples:
            continue
        win_rate = d["wins"] / n
        delta = win_rate - baseline
        if abs(delta) < 0.12:
            continue
        results.append({
            "side_a": a, "side_b": b,
            "runs": n, "wins": d["wins"],
            "win_rate": win_rate, "delta": delta,
        })

    return sorted(results, key=lambda x: abs(x["delta"]), reverse=True)


# ─── build coverage keywords ───────────────────────────────────────────────────
# These classify a side into a coverage bucket. A side can match multiple.

def _side_buckets(label: str) -> set[str]:
    l = label.lower()
    buckets = set()
    if any(k in l for k in ("attack", "damage", "bleed", "poison")):
        buckets.add("offense")
    if any(k in l for k in ("block", "armor", "negate damage")):
        buckets.add("defense")
    if any(k in l for k in ("heal", "heal equal", "heal 8", "heal 2", "heal 1")):
        buckets.add("heal")
    if "freeze" in l:
        buckets.add("freeze")
    if "strength" in l:
        buckets.add("strength")
    if "duplicate" in l or "2x" in l or "increase damage" in l:
        buckets.add("multiplier")
    return buckets


def compute_build_profile_stats(runs: list[RunModel]) -> list[dict]:
    """Measure win rate for each combination of coverage pillars present at Ganondwarf.

    Pillars: offense, defense, heal, freeze, strength, multiplier.
    For each pillar combo that appears in ≥10 runs, reports win rate vs baseline.
    """
    anchor_states = _build_anchor_states(runs)
    if not anchor_states:
        return []
    baseline = sum(1 for _, beat, _ in anchor_states if beat) / len(anchor_states)

    profile_data: dict[frozenset, dict] = defaultdict(lambda: {"runs": 0, "wins": 0})

    for state, beat_gano, _ in anchor_states:
        all_sides = [s for sides in state.values() for s in sides]
        present: set[str] = set()
        for side in all_sides:
            present |= _side_buckets(side)
        key = frozenset(present)
        profile_data[key]["runs"] += 1
        if beat_gano:
            profile_data[key]["wins"] += 1

    results = []
    for pillars, d in profile_data.items():
        n = d["runs"]
        if n < 10:
            continue
        win_rate = d["wins"] / n
        delta = win_rate - baseline
        results.append({
            "pillars": sorted(pillars),
            "runs": n, "wins": d["wins"],
            "win_rate": win_rate, "delta": delta,
        })

    return sorted(results, key=lambda x: -x["win_rate"])


def compute_death_pattern_stats(runs: list[RunModel]) -> dict:
    """For each death cause: count, and which sides were commonly present."""
    stats: dict[str, dict] = defaultdict(lambda: {"count": 0, "sides": Counter()})
    for r in runs:
        if r.ch1_cleared:
            continue
        if r.death_to in ("start_session_failed", "state_fetch_failed", "stuck",
                          "battle_error", "active_session_exists", "unknown"):
            continue
        stats[r.death_to]["count"] += 1
        for side in r.unique_sides:
            stats[r.death_to]["sides"][side] += 1
    return stats


# ─── vault writers ─────────────────────────────────────────────────────────────

def write_run_note(run: RunModel, vault: Path):
    month = run.run_id[:7] if len(run.run_id) >= 7 else "unknown"
    out = vault / "runs" / month / f"{run.run_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("---")
    lines.append(f"run_id: {run.run_id}")
    lines.append(f"end_reason: {run.end_reason}")
    lines.append(f"chapter_cleared: {run.chapter_cleared}")
    lines.append(f"death_to: \"{run.death_to}\"")
    lines.append(f"total_battles: {len(run.battles)}")
    lines.append("---")
    lines.append(f"# Run {run.run_id}")
    lines.append("")
    lines.append(f"**Outcome:** {'✅ Ch' + str(run.chapter_cleared) + ' clear' if run.ch1_cleared else '❌ Died in Ch1'}  ")
    lines.append(f"**Death:** [[{safe_filename(run.death_to)}]]  ")
    lines.append(f"**Battles fought:** {len(run.battles)}")
    lines.append("")

    # Die progression
    lines.append("## Die Progression")
    lines.append("")
    die_ids = list(run.initial_dice.keys()) if run.initial_dice else []
    die_id_to_idx = {did: i for i, did in enumerate(die_ids)}

    for die_id, starter_sides in run.initial_dice.items():
        die_idx = die_id_to_idx.get(die_id, "?")
        role = DIE_ROLES.get(die_idx, "unknown") if isinstance(die_idx, int) else "unknown"
        lines.append(f"### Die {die_idx} ({role})")
        lines.append("")
        lines.append("**Starters:** " + ", ".join(f"[[{safe_filename(s)}]]" for s in starter_sides))
        lines.append("")
        lines.append("| Battle | Side Added |")
        lines.append("|--------|-----------|")
        for b in run.battles:
            if b.get("picked_die_id") == die_id and b.get("picked_ability_label"):
                mons = " + ".join(m.get("name", "?") for m in (b.get("monsters") or []))
                label = b["picked_ability_label"]
                lines.append(f"| B{b.get('num','?')} vs {mons} | [[{safe_filename(label)}]] |")
        lines.append("")

    # Battles
    lines.append("## Battles")
    lines.append("")
    for b in run.battles:
        mons = (b.get("monsters") or [])
        mon_str = " + ".join(f"[[{m.get('name','?')}]]" for m in mons)
        result = "✅" if b.get("result") == "won" else "❌"
        hp = b.get("hp_at_end", "?")
        turns = b.get("turns", "?")
        lines.append(f"### {result} B{b.get('num','?')} — {mon_str}")
        lines.append(f"- HP after: **{hp}**  |  Turns: {turns}")
        if b.get("picked_ability_label"):
            lines.append(f"- Picked: [[{safe_filename(b['picked_ability_label'])}]]")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def _read_use_count(out: Path) -> int:
    """Preserve use_count from an existing note so rebuilds don't reset it."""
    if not out.exists():
        return 0
    for line in out.read_text(encoding="utf-8").splitlines():
        if line.startswith("use_count:"):
            try:
                return int(line.split(":")[1].strip())
            except ValueError:
                pass
    return 0


def log_contribution(note_path: Path) -> None:
    """Increment use_count in a vault note's frontmatter. Call when a note
    directly influenced a pick decision or answered a strategic question."""
    if not note_path.exists():
        return
    text = note_path.read_text(encoding="utf-8")
    import re
    def bump(m):
        return f"use_count: {int(m.group(1)) + 1}"
    new_text = re.sub(r"use_count:\s*(\d+)", bump, text)
    if new_text != text:
        note_path.write_text(new_text, encoding="utf-8")


def write_enemy_note(name: str, data: dict, vault: Path, baseline_ch1: float):
    out = vault / "enemies" / f"{safe_filename(name)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    enc = data["encounters"]
    wins = data["wins"]
    win_rate = wins / enc if enc else 0
    hp_lost_avg = sum(data["hp_lost"]) / len(data["hp_lost"]) if data["hp_lost"] else None
    use_count = _read_use_count(out)

    lines = []
    lines.append("---")
    lines.append(f"encounters: {enc}")
    lines.append(f"win_rate: {win_rate:.3f}")
    lines.append(f"use_count: {use_count}")
    lines.append("---")
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"**Encounters:** {enc}  |  **Win rate:** {pct(wins,enc)}  |  **Baseline:** {pct(int(baseline_ch1*enc),enc)}")
    if hp_lost_avg is not None:
        lines.append(f"**Avg HP lost per fight:** {hp_lost_avg:.1f}")
    lines.append("")

    # Sides most present at this fight
    side_counts = data["sides_at_fight"]
    if side_counts:
        lines.append("## Most Common Active Sides")
        lines.append("")
        lines.append("| Side | Times Active |")
        lines.append("|------|-------------|")
        for side, cnt in side_counts.most_common(15):
            lines.append(f"| [[{safe_filename(side)}]] | {cnt} |")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def write_side_note(side: str, data: dict, co_pairs: list[dict], vault: Path, baseline_ch1: float):
    out = vault / "sides" / f"{safe_filename(side)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    n = data["runs"]
    ch1_rate = data["ch1_wins"] / n if n else 0
    delta = ch1_rate - baseline_ch1
    use_count = _read_use_count(out)

    lines = []
    lines.append("---")
    lines.append(f"pick_count: {n}")
    lines.append(f"ch1_win_rate: {ch1_rate:.3f}")
    lines.append(f"ch1_delta: {delta:+.3f}")
    lines.append(f"use_count: {use_count}")
    lines.append("---")
    lines.append(f"# {side}")
    lines.append("")
    lines.append(f"**Picked in:** {n} runs  |  **Ch1 clear rate:** {pct(data['ch1_wins'],n)}  |  **vs baseline:** {delta:+.1%}")
    lines.append("")

    # Synergies/anti-synergies from pair data
    good_pairs = [p for p in co_pairs
                  if (p["side_a"] == side or p["side_b"] == side) and p["delta"] > 0]
    bad_pairs  = [p for p in co_pairs
                  if (p["side_a"] == side or p["side_b"] == side) and p["delta"] < 0]

    if good_pairs:
        lines.append("## Synergies")
        lines.append("")
        lines.append("| Partner Side | Runs | Ch1 Rate | Δ Baseline |")
        lines.append("|-------------|------|----------|-----------|")
        for p in sorted(good_pairs, key=lambda x: -x["delta"])[:10]:
            partner = p["side_b"] if p["side_a"] == side else p["side_a"]
            lines.append(f"| [[{safe_filename(partner)}]] | {p['runs']} | {pct(p['ch1'],p['runs'])} | {p['delta']:+.1%} |")
        lines.append("")

    if bad_pairs:
        lines.append("## Anti-synergies")
        lines.append("")
        lines.append("| Partner Side | Runs | Ch1 Rate | Δ Baseline |")
        lines.append("|-------------|------|----------|-----------|")
        for p in sorted(bad_pairs, key=lambda x: x["delta"])[:10]:
            partner = p["side_b"] if p["side_a"] == side else p["side_a"]
            lines.append(f"| [[{safe_filename(partner)}]] | {p['runs']} | {pct(p['ch1'],p['runs'])} | {p['delta']:+.1%} |")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def write_side_pairs_learning(pairs: list[dict], baseline_ch1: float, vault: Path):
    out = vault / "learnings" / "side_pairs.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Side Pair Learnings")
    lines.append("")
    lines.append(f"Auto-generated from {sum(p['runs'] for p in pairs[:1])} run sample.  ")
    lines.append(f"Baseline Ch1 clear rate: {baseline_ch1:.1%}")
    lines.append("")

    synergies = [p for p in pairs if p["delta"] > 0]
    antisynergies = [p for p in pairs if p["delta"] < 0]

    lines.append("## Powerful Combos (significantly above baseline)")
    lines.append("")
    lines.append("| Side A | Side B | Runs | Ch1 Rate | Δ Baseline |")
    lines.append("|--------|--------|------|----------|-----------|")
    for p in synergies[:30]:
        lines.append(
            f"| [[{safe_filename(p['side_a'])}]] | [[{safe_filename(p['side_b'])}]] "
            f"| {p['runs']} | {pct(p['ch1'],p['runs'])} | {p['delta']:+.1%} |"
        )
    lines.append("")

    lines.append("## Trap Combos (significantly below baseline)")
    lines.append("")
    lines.append("| Side A | Side B | Runs | Ch1 Rate | Δ Baseline |")
    lines.append("|--------|--------|------|----------|-----------|")
    for p in antisynergies[:30]:
        lines.append(
            f"| [[{safe_filename(p['side_a'])}]] | [[{safe_filename(p['side_b'])}]] "
            f"| {p['runs']} | {pct(p['ch1'],p['runs'])} | {p['delta']:+.1%} |"
        )

    out.write_text("\n".join(lines), encoding="utf-8")


def write_cross_die_pairs_learning(pairs: list[dict], baseline_ch1: float, vault: Path):
    out = vault / "learnings" / "cross_die_pairs.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    synergies = [p for p in pairs if p["delta"] > 0]
    antisynergies = [p for p in pairs if p["delta"] < 0]

    lines = []
    lines.append("# Cross-Die Pair Learnings")
    lines.append("")
    lines.append("Pairs of sides on **different dice** that move Ganondwarf win rate.  ")
    lines.append("Captures synergies that span roles — e.g. freeze source on die 1 + freeze payoff on die 2.")
    lines.append(f"  \nBaseline Ch1 clear rate: {baseline_ch1:.1%}")
    lines.append("")

    lines.append("## Cross-Die Synergies")
    lines.append("")
    lines.append("| Die A side | Die B side | Runs | Win Rate | Δ Baseline |")
    lines.append("|-----------|-----------|------|----------|-----------|")
    for p in synergies[:30]:
        lines.append(
            f"| [[{safe_filename(p['side_a'])}]] | [[{safe_filename(p['side_b'])}]] "
            f"| {p['runs']} | {pct(p['wins'],p['runs'])} | {p['delta']:+.1%} |"
        )
    lines.append("")

    lines.append("## Cross-Die Anti-synergies")
    lines.append("")
    lines.append("| Die A side | Die B side | Runs | Win Rate | Δ Baseline |")
    lines.append("|-----------|-----------|------|----------|-----------|")
    for p in antisynergies[:30]:
        lines.append(
            f"| [[{safe_filename(p['side_a'])}]] | [[{safe_filename(p['side_b'])}]] "
            f"| {p['runs']} | {pct(p['wins'],p['runs'])} | {p['delta']:+.1%} |"
        )

    out.write_text("\n".join(lines), encoding="utf-8")


def write_build_profiles_learning(profiles: list[dict], baseline_ch1: float, vault: Path):
    out = vault / "learnings" / "build_profiles.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Build Coverage Profiles")
    lines.append("")
    lines.append("Which combination of coverage pillars across all four dice wins at Ganondwarf.  ")
    lines.append("Pillars: **offense** (attack/poison/bleed), **defense** (block/armor), **heal**, **freeze**, **strength**, **multiplier** (2x/Dup/Perm+)")
    lines.append(f"  \nBaseline Ch1 clear rate: {baseline_ch1:.1%}")
    lines.append("")
    lines.append("| Pillars Present | Runs | Win Rate | Δ Baseline |")
    lines.append("|----------------|------|----------|-----------|")
    for p in profiles:
        pillars = ", ".join(p["pillars"]) if p["pillars"] else "(none)"
        delta_str = f"{p['delta']:+.1%}"
        lines.append(
            f"| {pillars} | {p['runs']} | {pct(p['wins'],p['runs'])} | {delta_str} |"
        )

    out.write_text("\n".join(lines), encoding="utf-8")


def write_death_patterns_learning(death_stats: dict, baseline_ch1: float, vault: Path):
    out = vault / "learnings" / "death_patterns.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# Death Pattern Learnings")
    lines.append("")
    lines.append("What kills Ch1 runs, and which sides were commonly present.")
    lines.append("")

    sorted_deaths = sorted(death_stats.items(), key=lambda x: -x[1]["count"])
    for enemy, data in sorted_deaths[:20]:
        cnt = data["count"]
        lines.append(f"## [[{safe_filename(enemy)}]] — {cnt} kills")
        lines.append("")
        top_sides = data["sides"].most_common(8)
        if top_sides:
            lines.append("**Sides most often present at death:**")
            for side, n in top_sides:
                lines.append(f"- [[{safe_filename(side)}]] ({n}x)")
        lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")


def write_index(runs: list[RunModel], vault: Path, baseline_ch1: float):
    out = vault / "_index.md"
    total = len(runs)
    ch1 = sum(1 for r in runs if r.ch1_cleared)
    ch2 = sum(1 for r in runs if r.ch2_cleared)
    infra_fails = sum(1 for r in runs if r.end_reason in
                      ("start_session_failed", "state_fetch_failed", "stuck", "battle_error"))

    lines = []
    lines.append("# Don't Die AI — Run Dashboard")
    lines.append("")
    lines.append(f"**Total runs:** {total}  |  **Ch1 clear:** {pct(ch1,total)}  |  **Ch2 clear:** {pct(ch2,total)}")
    lines.append(f"**Infra failures (not gameplay):** {infra_fails}")
    lines.append("")
    lines.append("## Navigation")
    lines.append("")
    lines.append("- [[learnings/side_pairs]] — same-die combos that move win rate")
    lines.append("- [[learnings/cross_die_pairs]] — cross-die synergies (offense+defense, freeze source+payoff)")
    lines.append("- [[learnings/build_profiles]] — which pillar combinations win (offense+defense+heal etc)")
    lines.append("- [[learnings/death_patterns]] — what kills runs")
    lines.append("- `enemies/` — per-enemy win rates and active-side breakdowns")
    lines.append("- `sides/` — per-side win rates, synergies, anti-synergies")
    lines.append("")

    top_killers = Counter(r.death_to for r in runs if not r.ch1_cleared
                          and r.death_to not in ("start_session_failed","state_fetch_failed",
                                                  "stuck","battle_error","active_session_exists","unknown"))
    lines.append("## Top Ch1 Killers")
    lines.append("")
    for name, cnt in top_killers.most_common(10):
        lines.append(f"- [[{safe_filename(name)}]] — {cnt} kills")

    out.write_text("\n".join(lines), encoding="utf-8")


# ─── main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-samples", type=int, default=25,
                    help="Minimum run count to include in pair analysis")
    ap.add_argument("--skip-run-notes", action="store_true",
                    help="Skip per-run note generation (fast mode)")
    args = ap.parse_args()

    print("Loading runs...")
    runs = load_runs(min_battles=1)
    print(f"  {len(runs)} runs with battles")

    baseline_ch1 = sum(1 for r in runs if r.ch1_cleared) / len(runs) if runs else 0
    print(f"  Baseline Ch1 clear rate: {baseline_ch1:.1%}")

    print("Computing side stats...")
    side_stats = compute_side_stats(runs)

    print("Computing enemy stats...")
    enemy_stats = compute_enemy_stats(runs)

    print("Computing side pair stats (same-die)...")
    pair_stats = compute_side_pair_stats(runs, min_samples=args.min_samples)
    print(f"  {len(pair_stats)} notable pairs found")

    print("Computing cross-die pair stats...")
    cross_pair_stats = compute_cross_die_pair_stats(runs, min_samples=args.min_samples)
    print(f"  {len(cross_pair_stats)} notable cross-die pairs found")

    print("Computing build coverage profiles...")
    profile_stats = compute_build_profile_stats(runs)
    print(f"  {len(profile_stats)} profiles found")

    print("Computing death patterns...")
    death_stats = compute_death_pattern_stats(runs)

    VAULT.mkdir(parents=True, exist_ok=True)

    print("Writing learnings...")
    write_side_pairs_learning(pair_stats, baseline_ch1, VAULT)
    write_cross_die_pairs_learning(cross_pair_stats, baseline_ch1, VAULT)
    write_build_profiles_learning(profile_stats, baseline_ch1, VAULT)
    write_death_patterns_learning(death_stats, baseline_ch1, VAULT)

    print("Writing enemy notes...")
    for name, data in enemy_stats.items():
        if data["encounters"] >= 3:
            write_enemy_note(name, data, VAULT, baseline_ch1)

    print("Writing side notes...")
    for side, data in side_stats.items():
        if data["runs"] >= 3:
            write_side_note(side, data, pair_stats, VAULT, baseline_ch1)

    if not args.skip_run_notes:
        print("Writing run notes...")
        for i, run in enumerate(runs):
            if i % 200 == 0:
                print(f"  {i}/{len(runs)}...")
            write_run_note(run, VAULT)

    print("Writing index...")
    write_index(runs, VAULT, baseline_ch1)

    print(f"\nDone. Vault at: {VAULT.resolve()}")
    print(f"  Run notes:   {len(list((VAULT/'runs').rglob('*.md'))) if (VAULT/'runs').exists() else 0}")
    print(f"  Enemy notes: {len(list((VAULT/'enemies').glob('*.md'))) if (VAULT/'enemies').exists() else 0}")
    print(f"  Side notes:  {len(list((VAULT/'sides').glob('*.md'))) if (VAULT/'sides').exists() else 0}")


if __name__ == "__main__":
    main()
