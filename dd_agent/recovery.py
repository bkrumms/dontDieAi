"""Bot startup recovery.

When the bot restarts, any run rows still marked `running` are orphans —
the asyncio task that was driving them is gone. Per
feedback_no_auto_forfeit.md the bot must NEVER auto-forfeit. Instead we
mark them `stuck` and try to notify the user's thread.
"""
from __future__ import annotations

from typing import Optional

import discord

from . import store


async def recover_orphan_runs(client: discord.Client) -> int:
    """Find non-terminal runs from before this bot startup and mark
    them stuck. Posts a heads-up to each user's thread when possible.

    Returns: number of runs reclassified.
    """
    orphans = store.runs_by_status(["queued", "running"])
    if not orphans:
        return 0

    for r in orphans:
        store.runs_set_status(
            r["id"],
            "stuck",
            end_reason="bot_restart",
            notes="bot was restarted while this run was active; DD session left untouched",
        )
        await _notify_thread(client, r)
    return len(orphans)


async def _notify_thread(client: discord.Client, run: dict) -> None:
    thread_id = run.get("thread_id")
    if not thread_id:
        return
    try:
        thread = await _resolve_thread(client, int(thread_id))
    except Exception:
        return
    if thread is None:
        return

    # Try to attach a Restart button if we have everything we need.
    view = None
    msg_extra = ""
    dd_session_id = run.get("dd_session_id")
    if dd_session_id:
        try:
            from bot.main import StuckView
            user = store.users_get(run["discord_id"])
            if user:
                view = StuckView(
                    run_id=run["id"],
                    user=user,
                    owner_user_id=int(run["discord_id"]),
                    interactivity=int(run.get("interactivity") or 0),
                    dd_session_id=dd_session_id,
                    can_restart=True,
                )
                msg_extra = "\nClick **Restart** to resume the bot on this same session."
        except Exception:
            view = None

    msg = (
        "**Bot restarted while this run was in progress.** "
        "I won't touch your DD session — it should still be alive on DD's side. "
        "Take over manually in the game UI, or `/forfeit-run` here if you want to end it. "
        f"\nSession: `{dd_session_id or '(unknown)'}`"
        + msg_extra
    )
    try:
        if view is not None:
            await thread.send(msg, view=view)
        else:
            await thread.send(msg)
    except Exception:
        pass


async def _resolve_thread(client: discord.Client, thread_id: int) -> Optional[discord.Thread]:
    ch = client.get_channel(thread_id)
    if isinstance(ch, discord.Thread):
        return ch
    try:
        ch = await client.fetch_channel(thread_id)
    except Exception:
        return None
    return ch if isinstance(ch, discord.Thread) else None
