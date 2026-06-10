"""Thin async wrapper around the Don't Die dev API.

Uses curl_cffi with Chrome TLS impersonation to bypass Cloudflare's bot
detection. CF allows requests from origin https://dd-internal.dontdie.gg,
so all calls include origin/referer headers pointing to the game frontend.

Auth: DD_AUTH_TOKEN (raw JWT, no "Bearer" prefix). No cookie needed.
"""
from __future__ import annotations

import asyncio
import json
import urllib.parse

import httpx
from curl_cffi.requests import AsyncSession

from .config import DD_API_BASE, DD_AUTH_TOKEN, DD_EXTRA_HEADERS

_BASE_HEADERS = {
    "origin": "https://dd-internal.dontdie.gg",
    "referer": "https://dd-internal.dontdie.gg/",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
}


class DDClient:
    def __init__(
        self,
        base: str = DD_API_BASE,
        token: str = DD_AUTH_TOKEN,
        extra_headers: dict | None = None,
    ):
        self._base = base.rstrip("/")
        self._headers: dict[str, str] = {**_BASE_HEADERS}
        if token:
            self._headers["authorization"] = token
        if extra_headers or DD_EXTRA_HEADERS:
            # Accept any explicit overrides, but never let them clobber origin/referer.
            safe = {k: v for k, v in (extra_headers or DD_EXTRA_HEADERS).items()
                    if k.lower() not in ("origin", "referer")}
            self._headers.update(safe)
        self._session: AsyncSession | None = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> AsyncSession:
        if self._session is not None:
            return self._session
        async with self._lock:
            if self._session is None:
                self._session = AsyncSession(impersonate="chrome")
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    def _check_status(self, status: int, url: str, body: bytes) -> None:
        if status >= 400:
            raise httpx.HTTPStatusError(
                f"Client error '{status}' for url '{url}'",
                request=httpx.Request("GET", url),
                response=httpx.Response(status, content=body),
            )

    async def _fetch(self, method: str, url: str, extra_headers: dict | None = None,
                     body: str | None = None) -> tuple[int, bytes]:
        session = await self._ensure_session()
        headers = {**self._headers, **(extra_headers or {})}
        resp = await session.request(method, url, headers=headers,
                                     data=body, timeout=30)
        return resp.status_code, resp.content

    async def _get(self, path: str, **params):
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = self._base + path + (f"?{qs}" if qs else "")
        status, raw = await self._fetch("GET", url)
        self._check_status(status, url, raw)
        data = json.loads(raw)
        return data.get("data", data) if isinstance(data, dict) else data

    async def _post(self, path: str, **body):
        url = self._base + path
        status, raw = await self._fetch(
            "POST", url,
            extra_headers={"content-type": "application/json"},
            body=json.dumps(body),
        )
        self._check_status(status, url, raw)
        data = json.loads(raw)
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
