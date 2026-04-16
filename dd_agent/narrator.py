"""Cheap-LLM narrator.

The rules engine already made the decision. The narrator's only job is to turn
(action, rationale, state) into punchy player-facing text, and optionally
answer the player's questions in chat.

Defaults to Claude Haiku 4.5 (cheap + prompt-caching). Falls back to echoing
the rationale if ANTHROPIC_API_KEY is not set.
"""
from anthropic import Anthropic

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL


_client: Anthropic | None = None

_SYSTEM = """You are the in-run voice of a Don't Die AI agent.

You do NOT make game decisions — the rules engine already decided. Your job:
- Narrate the decision in 1-2 short punchy sentences.
- Confident, slightly cocky tone. Player should feel the agent knows what it's doing.
- Under 40 words unless the player asks for detail.
- Never invent mechanics. If you don't know, say "rules engine call".
"""


def _get_client() -> Anthropic | None:
    global _client
    if _client is None and ANTHROPIC_API_KEY:
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def narrate(action: str, rationale: str, state_summary: str) -> str:
    client = _get_client()
    if client is None:
        return f"[{action}] {rationale}"

    try:
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=120,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": (
                    f"Action: {action}\n"
                    f"Rationale: {rationale}\n"
                    f"State: {state_summary}\n\n"
                    "Narrate this for the player."
                ),
            }],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts).strip() or f"[{action}] {rationale}"
    except Exception as e:
        return f"[{action}] {rationale}  (narrator error: {e})"
