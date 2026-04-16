"""Discord bot for live Don't Die run analysis.

Lets you talk to the bot from a Discord channel while playing a run.
Commands (prefix `!`):

  !help                       — list commands
  !watch <session_id>         — start polling a session (every 3s)
  !stop                       — stop polling the current session
  !status                     — print the current state of the watched session
  !dice                       — pretty-print the dice layout
  !map                        — print the map tiles around current position
  !trinkets                   — list trinkets and food
  !snapshot                   — one-shot fetch without starting the polling loop
  !setbase <url>              — override the DD API base URL (prod vs dev)
  !settoken <jwt>             — override the DD JWT for this session

Environment:
  DISCORD_BOT_TOKEN           — required, the bot token
  DD_API_BASE                 — initial DD API base (default dev)
  DD_AUTH_TOKEN               — initial DD JWT (default from .env)

Usage:
  python scripts/dd_discord_bot.py

The bot can run in the background; use Ctrl+C to stop.
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import discord
from discord.ext import commands, tasks

from dd_agent.dd_client import DDClient


BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DEFAULT_BASE = os.getenv("DD_API_BASE", "https://dd-api-dev.anomalygames.ai")
DEFAULT_TOKEN = os.getenv("DD_AUTH_TOKEN", "")

intents = discord.Intents.default()
intents.message_content = True  # needs to be enabled in the Discord dev portal too
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# Per-guild state so multiple channels don't collide.
class WatchState:
    def __init__(self):
        self.session_id: str | None = None
        self.base: str = DEFAULT_BASE
        self.token: str = DEFAULT_TOKEN
        self.channel: discord.abc.Messageable | None = None
        self.last_state: dict | None = None
        self.polling = False

    def client(self) -> DDClient:
        return DDClient(base=self.base, token=self.token)


state = WatchState()


def _fmt_dice(char: dict) -> str:
    if not isinstance(char, dict):
        return "(no character)"
    lines = [
        f"HP {char.get('health')}/{char.get('max_health')}  "
        f"gold={char.get('gold')}  pts={char.get('points')}  tc={char.get('time_crystal')}"
    ]
    for d in sorted(char.get("dices") or [], key=lambda x: x.get("order", 0) or 0):
        abs_ = d.get("ability") or []
        lines.append(f"**Die {d.get('order')}** ({len(abs_)} sides):")
        for a in abs_:
            tags = [t.get("label") for t in (a.get("tags") or []) if isinstance(t, dict)]
            tag_s = f" [{','.join(tags)}]" if tags else ""
            lines.append(f"  • {a.get('label')}{tag_s}")
    return "\n".join(lines)[:1900]  # Discord 2000 char cap


def _fmt_trinkets(char: dict) -> str:
    tr = [t.get("label") or t.get("type") for t in (char.get("trinkets") or []) if isinstance(t, dict)]
    boosts = [b.get("label") or b.get("type") for b in (char.get("boosts") or []) if isinstance(b, dict)]
    return f"**Trinkets ({len(tr)}):** {', '.join(tr) or '—'}\n**Food ({len(boosts)}):** {', '.join(boosts) or '—'}"


async def _fetch_state(ws: WatchState) -> dict | None:
    if not ws.session_id:
        return None
    dd = ws.client()
    try:
        char = await dd.get_character(ws.session_id)
    except Exception as e:
        await dd.close()
        raise e
    await dd.close()
    return char


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id {bot.user.id})")
    print("Invite URL: https://discord.com/oauth2/authorize?client_id={}&scope=bot&permissions=274877975552".format(bot.user.id))


@bot.command(name="help")
async def cmd_help(ctx):
    await ctx.send(
        "**Don't Die Bot**\n"
        "`!watch <session_id>` — start polling\n"
        "`!stop` — stop polling\n"
        "`!status` — current state\n"
        "`!dice` — dice layout\n"
        "`!trinkets` — trinkets + food\n"
        "`!snapshot` — one-shot fetch\n"
        "`!setbase <url>` — API base override (prod/dev)\n"
        "`!settoken <jwt>` — JWT override\n"
    )


@bot.command(name="watch")
async def cmd_watch(ctx, session_id: str):
    state.session_id = session_id
    state.channel = ctx.channel
    state.polling = True
    await ctx.send(f"👀 watching `{session_id}` on base `{state.base}`")
    if not poll_loop.is_running():
        poll_loop.start()


@bot.command(name="stop")
async def cmd_stop(ctx):
    state.polling = False
    await ctx.send("stopped polling")


@bot.command(name="setbase")
async def cmd_setbase(ctx, url: str):
    state.base = url
    await ctx.send(f"base set → `{url}`")


@bot.command(name="settoken")
async def cmd_settoken(ctx, *, jwt: str):
    state.token = jwt.strip()
    await ctx.send(f"JWT set (len={len(jwt)}). Make sure it matches the API base.")
    # Try to delete the user's message so the token isn't left in chat.
    try:
        await ctx.message.delete()
    except Exception:
        pass


@bot.command(name="status")
async def cmd_status(ctx):
    if not state.session_id:
        await ctx.send("no session. `!watch <session_id>` first.")
        return
    try:
        char = await _fetch_state(state)
    except Exception as e:
        await ctx.send(f"fetch failed: `{e}`")
        return
    if not isinstance(char, dict):
        await ctx.send("no character returned")
        return
    await ctx.send(
        f"HP {char.get('health')}/{char.get('max_health')}  "
        f"gold={char.get('gold')}  pts={char.get('points')}  tc={char.get('time_crystal')}"
    )


@bot.command(name="dice")
async def cmd_dice(ctx):
    if not state.session_id:
        await ctx.send("no session")
        return
    try:
        char = await _fetch_state(state)
    except Exception as e:
        await ctx.send(f"fetch failed: `{e}`")
        return
    await ctx.send(_fmt_dice(char))


@bot.command(name="trinkets")
async def cmd_trinkets(ctx):
    if not state.session_id:
        await ctx.send("no session")
        return
    try:
        char = await _fetch_state(state)
    except Exception as e:
        await ctx.send(f"fetch failed: `{e}`")
        return
    await ctx.send(_fmt_trinkets(char))


@bot.command(name="snapshot")
async def cmd_snapshot(ctx, session_id: str = None):
    if session_id:
        state.session_id = session_id
    if not state.session_id:
        await ctx.send("no session. `!snapshot <id>`")
        return
    try:
        char = await _fetch_state(state)
    except Exception as e:
        await ctx.send(f"fetch failed: `{e}`")
        return
    await ctx.send(_fmt_dice(char))
    await ctx.send(_fmt_trinkets(char))


@tasks.loop(seconds=3)
async def poll_loop():
    if not state.polling or not state.session_id or not state.channel:
        return
    try:
        char = await _fetch_state(state)
    except Exception:
        return
    if not isinstance(char, dict):
        return
    # Diff interesting fields and announce changes.
    def summary(c):
        return (
            c.get("health"), c.get("gold"), c.get("points"),
            c.get("time_crystal"),
            tuple(len(d.get("ability") or []) for d in (c.get("dices") or [])),
            len(c.get("trinkets") or []),
            len(c.get("boosts") or []),
        )
    if state.last_state is None:
        state.last_state = char
        return
    if summary(state.last_state) != summary(char):
        hp_old = state.last_state.get("health")
        hp_new = char.get("health")
        msg_parts = []
        if hp_old != hp_new:
            msg_parts.append(f"HP {hp_old}→{hp_new}")
        if state.last_state.get("points") != char.get("points"):
            msg_parts.append(f"pts→{char.get('points')}")
        if state.last_state.get("time_crystal") != char.get("time_crystal"):
            msg_parts.append(f"TC→{char.get('time_crystal')}")
        old_dice = tuple(len(d.get("ability") or []) for d in (state.last_state.get("dices") or []))
        new_dice = tuple(len(d.get("ability") or []) for d in (char.get("dices") or []))
        if old_dice != new_dice:
            deltas = [f"D{i+1} {o}→{n}" for i, (o, n) in enumerate(zip(old_dice, new_dice)) if o != n]
            msg_parts.append("sides: " + ", ".join(deltas))
        if msg_parts:
            try:
                await state.channel.send("· " + " | ".join(msg_parts))
            except Exception:
                pass
        state.last_state = char


def main():
    if not BOT_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN is empty. Add it to .env or set the env var.")
        sys.exit(1)
    bot.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
