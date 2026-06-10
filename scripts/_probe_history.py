import asyncio, sys, json
sys.path.insert(0, ".")
from dd_agent.dd_client import DDClient

async def main():
    dd = DDClient()
    try:
        r = await dd._get("/api/game/run-history")
        practice = r.get("practice", []) if isinstance(r, dict) else []
        print(f"Total sessions returned: {len(practice)}")
        print(f"Keys on each entry: {list(practice[0].keys()) if practice else 'none'}")
        print()

        # Quick summary
        from collections import Counter
        outcomes = Counter(s.get("outcome") for s in practice)
        chapters = Counter(s.get("chapter") for s in practice)
        print("Outcomes:", dict(outcomes))
        print("Chapters reached:", dict(sorted(chapters.items())))
        print()
        print("Most recent 3:")
        for s in practice[:3]:
            print(f"  {s['created_at']}  outcome={s['outcome']}  ch={s['chapter']}  pts={s['points']}  idx={s['index']}")
        print("Oldest 3:")
        for s in practice[-3:]:
            print(f"  {s['created_at']}  outcome={s['outcome']}  ch={s['chapter']}  pts={s['points']}  idx={s['index']}")
    finally:
        await dd.close()

asyncio.run(main())
