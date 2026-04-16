"""Combined entrypoint: runs the Discord bot + FastAPI web viewer in one process.

The in-memory bus only connects publishers and subscribers within the same
process, so for the mock we run both the bot and the web server together.
When you move to Redis pub/sub you can split them.
"""
import asyncio

import uvicorn

from bot.main import client as discord_client
from dd_agent.config import DISCORD_BOT_TOKEN
from web.main import app as web_app


async def run_web():
    config = uvicorn.Config(web_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    if not DISCORD_BOT_TOKEN:
        print("[warn] DISCORD_BOT_TOKEN not set — bot will not start")
        return
    await discord_client.start(DISCORD_BOT_TOKEN)


async def main():
    await asyncio.gather(run_web(), run_bot())


if __name__ == "__main__":
    asyncio.run(main())
