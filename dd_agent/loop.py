"""The agent loop. One coroutine per active run.

Cycle:
    1. Fetch state from DD API
    2. Publish state to web viewer
    3. Rules engine picks a decision
    4. If decision.needs_player → prompt via bus, await answer
    5. Narrator turns it into player text → publish to bot
    6. Apply the decision (POST to DD API)
    7. Sleep briefly, loop
"""
import asyncio
import json

from .bus import bus
from .dd_client import DDClient
from .narrator import narrate
from .rules import Decision, decide


TERMINAL_STATES = {"dead", "ended", "forfeited", "won"}


class AgentRun:
    def __init__(self, session_id: str, character_id: str, client: DDClient):
        self.session_id = session_id
        self.character_id = character_id
        self.client = client
        self._player_answer: asyncio.Future | None = None

    # --- player prompt plumbing ---

    def supply_player_answer(self, answer: str) -> bool:
        if self._player_answer and not self._player_answer.done():
            self._player_answer.set_result(answer)
            return True
        return False

    async def _await_player(self, prompt_payload: dict, timeout: float = 120.0):
        loop = asyncio.get_event_loop()
        self._player_answer = loop.create_future()
        await bus.publish(f"run:{self.session_id}:prompt", prompt_payload)
        try:
            return await asyncio.wait_for(self._player_answer, timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # --- main loop ---

    async def run(self):
        while True:
            try:
                state = await self.client.get_character(self.session_id)
            except Exception as e:
                await bus.publish(
                    f"run:{self.session_id}:narration",
                    f"[state fetch failed: {e}]",
                )
                break

            await bus.publish(f"run:{self.session_id}:state", state)

            in_state = (state or {}).get("inState")
            if in_state in TERMINAL_STATES:
                await bus.publish(
                    f"run:{self.session_id}:narration",
                    f"Run ended in state `{in_state}`.",
                )
                break

            decision: Decision = decide(state)

            if decision.needs_player:
                answer = await self._await_player({
                    "kind": "checkpoint" if decision.action == "checkpoint" else "generic",
                    "text": decision.rationale,
                    "default": decision.args.get("selection"),
                })
                if answer in ("continue", "unstake"):
                    decision.args["selection"] = answer

            narration = narrate(decision.action, decision.rationale, _summarize(state))
            await bus.publish(f"run:{self.session_id}:narration", narration)

            await self._apply(decision)
            await asyncio.sleep(0.5)

    async def _apply(self, d: Decision):
        method = {
            "roll": "roll",
            "proceed": "proceed",
            "reroll_movement": "reroll_movement",
            "checkpoint": "checkpoint_tournament",
            "battle_setup": "battle_setup",
            "battle_prefight": "battle_prefight",
            "battle_start": "battle_start",
            "battle_resolve": "battle_resolve",
            "battle_rewind": "battle_rewind",
            "battle_to_loot": "battle_to_loot",
            "battle_loot": "battle_loot",
            "forfeit": "forfeit",
            # TODO: wire campfire / shop / mystery / loot-dice
            "campfire_exit": None,
            "shop_exit": None,
        }.get(d.action)

        if method is None:
            await bus.publish(
                f"run:{self.session_id}:narration",
                f"[stub action '{d.action}' not wired yet]",
            )
            return

        fn = getattr(self.client, method)
        try:
            if d.action == "checkpoint":
                await fn(self.session_id, d.args.get("selection", "unstake"))
            elif d.action == "battle_prefight":
                await fn(self.character_id, self.session_id, **d.args)
            else:
                await fn(self.session_id, **d.args)
        except Exception as e:
            await bus.publish(
                f"run:{self.session_id}:narration",
                f"[error applying {d.action}: {e}]",
            )


def _summarize(state: dict) -> str:
    if not state:
        return "{}"
    keys = ("health", "maxHealth", "timeCrystal", "points", "inState", "activePath", "currentIndex")
    return json.dumps({k: state.get(k) for k in keys}, default=str)
