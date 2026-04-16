"""Trivial in-memory pub/sub for a single-process mock.

Topics used by the mock:
  run:{session_id}:state      → web viewer    (full state dict)
  run:{session_id}:narration  → discord bot   (string)
  run:{session_id}:prompt     → discord bot   (dict: {kind, text, ...})

Swap for `redis.asyncio` when we need multi-process deployment.
"""
import asyncio
from collections import defaultdict


class Bus:
    def __init__(self):
        self._subs: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[topic].append(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue):
        if q in self._subs.get(topic, []):
            self._subs[topic].remove(q)

    async def publish(self, topic: str, payload):
        for q in list(self._subs.get(topic, [])):
            await q.put(payload)


bus = Bus()
