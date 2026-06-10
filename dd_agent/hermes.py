"""Hermes shadow observer.

Runs fire-and-forget alongside the rule-based engine. Every pick-side decision
is sent to a Hermes-compatible LLM (Ollama / Together AI / any OpenAI-compat
endpoint) which logs its own prediction. Those logs become fine-tuning data.

Set HERMES_ENABLED=true in .env to activate. The game loop is never blocked —
all API calls run in a background daemon thread via a bounded queue.
"""
from __future__ import annotations

import json
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .config import HERMES_BASE_URL, HERMES_ENABLED, HERMES_MODEL

_SHADOW_LOG = Path("data/hermes_shadow.jsonl")
_KNOWLEDGE_DIR = Path("knowledge/game")

# Only the most decision-relevant files — keep the system prompt from ballooning.
_KEY_KNOWLEDGE_FILES = [
    "overview.md",
    "dice-sides-upgrades.md",
    "battle.md",
    "status-effects.md",
    "winning_side_placements.md",
]

_DIE_ROLE_DESC = {
    0: "utility — Strength/Armor buffs, heals, conditional attacks, exhaust payoff",
    1: "attack — pure kill speed: Attack, Poison, Bleed, multi-hit",
    2: "mixed — gap filler: takes whatever the build currently lacks most",
    3: "defense — survival anchor: Block/Armor only; non-exhaust attacks are run-killers",
}

_q: queue.Queue = queue.Queue(maxsize=200)
_started = False
_start_lock = threading.Lock()
_log_lock = threading.Lock()
_system_prompt_cache: str | None = None


def _load_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is not None:
        return _system_prompt_cache

    parts = [
        "You are a strategic advisor for the Don't Die roguelike tournament game.\n"
        "Your role: given a game state and offered upgrade sides, predict the best pick.\n\n"
        "DICE ROLES (0-based index):\n",
    ]
    for idx, desc in _DIE_ROLE_DESC.items():
        parts.append(f"  Die {idx}: {desc}\n")

    parts.append("\nGAME KNOWLEDGE (excerpts):\n")
    for fname in _KEY_KNOWLEDGE_FILES:
        fpath = _KNOWLEDGE_DIR / fname
        if fpath.exists():
            try:
                content = fpath.read_text(encoding="utf-8")
                if len(content) > 1800:
                    content = content[:1800] + "\n...(truncated)"
                parts.append(f"\n--- {fname} ---\n{content}\n")
            except Exception:
                pass

    parts.append(
        "\nRESPOND in JSON only — no other text:\n"
        '{"pick_index": <0-based index into offered list>, "rationale": "<≤30 word reason>"}\n'
    )
    _system_prompt_cache = "".join(parts)
    return _system_prompt_cache


def _build_pick_prompt(
    die_index: int,
    offered_sides: list[dict],
    game_state: dict | None,
    rule_scored: list | None,
) -> str:
    role_desc = _DIE_ROLE_DESC.get(die_index, "mixed")
    lines = [f"TARGET DIE: {die_index}  role: {role_desc}\n\nOFFERED SIDES:"]

    for i, side in enumerate(offered_sides):
        label = side.get("label", "?")
        tags = [t.get("label") for t in (side.get("tags") or []) if isinstance(t, dict)]
        tier = next(
            (t for t in tags if t in ("Starter", "Level 1", "Level 2", "Level 3", "Level 3 Boss", "Curse")),
            "?",
        )
        exhaust_marker = "(exhaust) " if side.get("isExhaust") or "(e)" in label else ""
        lines.append(f"  [{i}] {exhaust_marker}{label}  tier={tier}")

    if game_state:
        hp = game_state.get("health", "?")
        max_hp = game_state.get("max_health", "?")
        gold = game_state.get("gold", "?")
        chapter = game_state.get("chapter", "?")
        boss = game_state.get("upcoming_boss", "?")
        lines.append(f"\nGAME STATE: HP={hp}/{max_hp}  gold={gold}  chapter={chapter}  upcoming_boss={boss}")

        dices = game_state.get("dices") or []
        if dices and die_index < len(dices):
            current_sides = [
                a.get("label", "?")
                for a in (dices[die_index].get("ability") or [])
                if isinstance(a, dict)
            ]
            lines.append(f"CURRENT SIDES ON TARGET DIE: {current_sides}")

    if rule_scored:
        lines.append("\nRULE ENGINE SCORES (top 5, for reference):")
        for orig_i, lbl, s, cat, tier, combos in rule_scored[:5]:
            lines.append(f"  [{orig_i}] {lbl}  score={s:.1f}  cat={cat}")

    lines.append("\nChoose the best pick. JSON only.")
    return "\n".join(lines)


def _call_hermes(prompt: str, system: str) -> dict | None:
    payload = {
        "model": HERMES_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 200,
    }
    try:
        resp = httpx.post(
            f"{HERMES_BASE_URL}/chat/completions",
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # strip markdown fences if model adds them
        if content.startswith("```"):
            parts = content.split("```")
            content = parts[1].lstrip("json").strip() if len(parts) > 1 else content
        return json.loads(content)
    except Exception:
        return None


def _append_log(entry: dict) -> None:
    _SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry) + "\n"
    with _log_lock:
        with _SHADOW_LOG.open("a", encoding="utf-8") as f:
            f.write(line)


def _worker() -> None:
    system = _load_system_prompt()
    while True:
        try:
            item = _q.get(timeout=5)
            if item is None:
                break
            die_index, offered_sides, game_state, rule_scored, rule_best_label = item
            prompt = _build_pick_prompt(die_index, offered_sides, game_state, rule_scored)
            result = _call_hermes(prompt, system)

            hermes_idx = result.get("pick_index") if result else None
            hermes_label = (
                offered_sides[hermes_idx].get("label", "?")
                if hermes_idx is not None and hermes_idx < len(offered_sides)
                else "?"
            )
            agrees = hermes_label.strip().lower() == (rule_best_label or "").strip().lower()

            _append_log({
                "ts": datetime.now(timezone.utc).isoformat(),
                "die_index": die_index,
                "offered": [s.get("label", "?") for s in offered_sides],
                "rule_pick": rule_best_label,
                "hermes_pick": hermes_label,
                "hermes_pick_index": hermes_idx,
                "hermes_rationale": (result or {}).get("rationale", ""),
                "agrees": agrees,
                "outcome": None,  # filled in post-run by scripts/annotate_hermes_outcomes.py
                "game_state_snapshot": {
                    "hp": (game_state or {}).get("health"),
                    "chapter": (game_state or {}).get("chapter"),
                    "upcoming_boss": (game_state or {}).get("upcoming_boss"),
                },
            })
        except queue.Empty:
            continue
        except Exception:
            pass


def _ensure_started() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        t = threading.Thread(target=_worker, daemon=True, name="hermes-shadow")
        t.start()
        _started = True


def shadow_pick(
    die_index: int,
    offered_sides: list[dict],
    rule_scored: list | None = None,
    rule_best_side: dict | None = None,
    game_state: dict | None = None,
) -> None:
    """Enqueue a shadow pick observation. Never blocks — drops silently if queue full or disabled."""
    if not HERMES_ENABLED:
        return
    _ensure_started()
    rule_best_label = (rule_best_side or {}).get("label", "") if rule_best_side else ""
    try:
        _q.put_nowait((die_index, offered_sides, game_state, rule_scored, rule_best_label))
    except queue.Full:
        pass
