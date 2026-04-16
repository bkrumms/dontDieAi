"""Thin async wrapper around the Don't Die dev API.

Auth scheme is TBD — the OpenAPI spec declares no securitySchemes. The client
accepts any combination of:
  - Bearer token  (DD_AUTH_TOKEN)
  - Raw Cookie    (DD_COOKIE)
  - Extra headers (DD_EXTRA_HEADERS, JSON dict in .env)

Use whichever the dev build requires. You can find the correct header(s) in
your browser's dev tools → Network tab while logged into the local build.
"""
import httpx

from .config import DD_API_BASE, DD_AUTH_TOKEN, DD_COOKIE, DD_EXTRA_HEADERS


class DDClient:
    def __init__(
        self,
        base: str = DD_API_BASE,
        token: str = DD_AUTH_TOKEN,
        cookie: str = DD_COOKIE,
        extra_headers: dict | None = None,
    ):
        headers: dict[str, str] = {}
        if token:
            # NOTE: the dev build expects the raw JWT, NOT "Bearer <token>".
            # Prefixing with "Bearer " triggers a middleware "Invalid request".
            headers["authorization"] = token
        if cookie:
            headers["Cookie"] = cookie
        headers.update(extra_headers or DD_EXTRA_HEADERS)
        self.http = httpx.AsyncClient(base_url=base, headers=headers, timeout=30.0)

    async def close(self):
        await self.http.aclose()

    async def _get(self, path: str, **params):
        r = await self.http.get(path, params=params)
        r.raise_for_status()
        body = r.json()
        return body.get("data", body) if isinstance(body, dict) else body

    async def _post(self, path: str, **body):
        r = await self.http.post(path, json=body)
        r.raise_for_status()
        data = r.json()
        return data.get("data", data) if isinstance(data, dict) else data

    # --- reads ---
    async def get_character(self, session_id: str):
        return await self._get("/api/character", sessionId=session_id)

    async def get_game(self, character_id: str):
        return await self._get("/api/game", character_id=character_id)

    async def get_inventory(self):
        return await self._get("/api/user/inventory")

    async def fetch_loot(self, session_id: str):
        return await self._get("/api/game/battle/fetch-loot", sessionId=session_id)

    # --- session lifecycle ---
    async def start_tournament(
        self,
        character_id: str,
        equipped: list,
        time_crystals: int,
        token_id: str,
        nft_name: str,
    ):
        return await self._post(
            "/api/game/start-tournament",
            character_id=character_id,
            equipped=equipped,
            time_crystals=time_crystals,
            token_id=token_id,
            nft_name=nft_name,
        )

    async def start_session(self, character_id: str, equipped: list, time_crystals: int):
        return await self._post(
            "/api/game/start-session",
            character_id=character_id,
            equipped=equipped,
            time_crystals=time_crystals,
        )

    async def forfeit(self, session_id: str):
        return await self._post("/api/game/forfeit", session_id=session_id)

    # --- map ---
    async def roll(self, session_id: str, choice=None):
        body = {"session_id": session_id}
        if choice is not None:
            body["choice"] = choice
        return await self._post("/api/game/roll", **body)

    async def proceed(self, session_id: str):
        return await self._post("/api/game/proceed", session_id=session_id)

    async def reroll_movement(self, session_id: str):
        return await self._post("/api/game/reroll", session_id=session_id)

    async def checkpoint_tournament(self, session_id: str, selection: str):
        return await self._post(
            "/api/game/checkpoint/tournament",
            session_id=session_id,
            selection=selection,
        )

    # --- battle ---
    async def battle_setup(self, session_id: str):
        return await self._post("/api/game/battle/setup-scene", session_id=session_id)

    async def battle_prefight(self, character_id: str, session_id: str):
        return await self._post(
            "/api/game/battle/pre-fight",
            character_id=character_id,
            session_id=session_id,
        )

    async def battle_start(self, session_id: str):
        return await self._post("/api/game/battle/start-scene", sessionId=session_id)

    async def battle_resolve(self, session_id: str):
        return await self._post("/api/game/battle/resolve-turn", sessionId=session_id)

    async def battle_rewind(self, session_id: str):
        return await self._post("/api/game/battle/rewind", sessionId=session_id)

    async def battle_to_loot(self, session_id: str):
        return await self._post("/api/game/battle/to-loot", sessionId=session_id)

    async def battle_loot(self, session_id: str, loot_type: str, **meta):
        return await self._post(
            "/api/game/battle/loot",
            sessionId=session_id,
            lootType=loot_type,
            **meta,
        )
