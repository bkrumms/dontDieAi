"""Standalone agent-loop runner for testing without Discord.

Usage:
    python scripts/run_agent.py <session_id> <character_id>
"""
import asyncio
import sys

from dd_agent.dd_client import DDClient
from dd_agent.loop import AgentRun


async def main():
    if len(sys.argv) < 3:
        print("usage: run_agent.py <session_id> <character_id>")
        return
    sid, cid = sys.argv[1], sys.argv[2]
    dd = DDClient()
    try:
        run = AgentRun(session_id=sid, character_id=cid, client=dd)
        await run.run()
    finally:
        await dd.close()


if __name__ == "__main__":
    asyncio.run(main())
