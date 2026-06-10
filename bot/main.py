"""Discord bot — production entry point.

Slash commands:
  /register      (DM only) bind your DD JWT + character to your Discord ID
  /run           start an autonomous run
  /status        show your active run state
  /stop-bot      detach the bot from your run (DD session stays alive)
  /forfeit-run   confirm + forfeit your active run on DD's side
  /help          list commands

The bot NEVER auto-forfeits. If the agent gets stuck, the user's run is
left alive on DD's side; the user takes over manually or /forfeit-run.
See feedback_no_auto_forfeit.md.
"""
from __future__ import annotations

import asyncio
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import discord
from discord import app_commands

from dd_agent import recovery, store
from dd_agent.config import DD_API_BASE, DISCORD_BOT_TOKEN
from dd_agent.dd_client import DDClient
from dd_agent.runner import RunStuck, play_full_run


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# run_id → asyncio.Task driving it (in-process only; lost on restart)
running_tasks: dict[int, asyncio.Task] = {}

# Concurrency cap — keep DD API + Cloudflare happy.
MAX_CONCURRENT_RUNS = 5
_run_semaphore = asyncio.Semaphore(MAX_CONCURRENT_RUNS)

# Match runner.USER_PROMPT_TIMEOUT — slightly less so the View times out
# before the runner gives up (avoids a stale orphan future).
PROMPT_TIMEOUT_SECONDS = 120


WELCOME_GUIDE = (
    "**How the bot works**\n\n"
    "**Starting runs**\n"
    "• `/run interactivity:N` — fresh practice run; bot creates the session\n"
    "• `/attach session_id:<uuid> interactivity:N` — attach to a tournament/NFT run "
    "you started in DD's game UI\n"
    "• `/resume` — pick a stuck run and have the bot re-attach to its DD session\n\n"
    "**Managing runs**\n"
    "• `/status` — show your active run's HP, gold, points, etc.\n"
    "• `/stop-bot` — detach the bot. **DD session stays alive** for you to play manually.\n"
    "• `/forfeit-run` — confirm + actually forfeit on DD's side (modal asks for run number).\n\n"
    "**Interactivity levels** (the `interactivity` arg on `/run` and `/attach`):\n"
    "• `0` — Fully autonomous; bot makes every decision\n"
    "• `1` — Asks at checkpoints (mid-chapter + tournament stay/continue)\n"
    "• `2` — `1` + asks at die upgrades (which die, which side; bot's pick is highlighted)\n"
    "• `3` — `2` + asks at mystery events, campfires, Bub's shop\n"
    "• `4` — `3` + asks at map rerolls\n\n"
    "**The no-auto-forfeit rule (important for tournament NFTs)**\n"
    "If a run gets stuck — timeout on a prompt, repeated API errors, etc. — the bot will "
    "**never auto-forfeit your DD session**. The run on DD's side stays alive. You can:\n"
    "• Click **Restart** on the stuck message → bot re-attaches and resumes\n"
    "• Use `/resume` later to pick from any stuck runs you have\n"
    "• Take over manually in the DD game UI\n"
    "• Use `/forfeit-run` to end it permanently (with confirmation)\n\n"
    "**Prompt timeouts**\n"
    "When the bot asks you something interactively (level 1+), you have **2 minutes** to "
    "click. If you don't, the run goes stuck — no auto-pick. Better to be safe than to "
    "make a tournament decision for you.\n\n"
    "Type `/help` anytime to revisit this guide."
)


class PromptView(discord.ui.View):
    """One button per option. Clicking sets the future. Buttons disable
    after first click (or timeout) so the user can't double-answer."""

    def __init__(self, options: list[dict], future: asyncio.Future, allowed_user_id: int):
        super().__init__(timeout=PROMPT_TIMEOUT_SECONDS)
        self.future = future
        self.allowed_user_id = allowed_user_id
        for opt in options:
            self.add_item(_PromptButton(opt["value"], opt["label"], self))

    async def on_timeout(self):
        if not self.future.done():
            self.future.set_result(None)
        for child in self.children:
            child.disabled = True


class _PromptButton(discord.ui.Button):
    def __init__(self, value: str, label: str, view: PromptView):
        super().__init__(style=discord.ButtonStyle.primary, label=label[:80])
        self._value = value
        self._owner_view = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner_view.allowed_user_id:
            await interaction.response.send_message(
                "❌ This prompt is for the run owner only.", ephemeral=True,
            )
            return
        if self._owner_view.future.done():
            await interaction.response.send_message("Already answered.", ephemeral=True)
            return
        self._owner_view.future.set_result(self._value)
        for child in self._owner_view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self._owner_view)


def _format_prompt(prompt: dict) -> str:
    text = prompt.get("text", "Decision needed.")
    ctx = prompt.get("context") or {}
    ctx_bits = []
    if "hp" in ctx:
        ctx_bits.append(f"HP {ctx.get('hp')}/{ctx.get('max_hp')}")
    if "points" in ctx:
        ctx_bits.append(f"pts {ctx.get('points')}")
    if "position" in ctx:
        ctx_bits.append(f"pos {ctx.get('position')}")
    if ctx_bits:
        text += "\n" + " · ".join(ctx_bits)
    return text


# ---------------------------------------------------------------- helpers

def _client_for(user: dict) -> DDClient:
    return DDClient(base=user["dd_api_base"], token=user["jwt"])


def _stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _format_ago(ts: int | None) -> str:
    if not ts:
        return "?"
    delta = max(0, int(time.time()) - int(ts))
    if delta < 60:
        return f"{delta}s ago"
    if delta < 3600:
        return f"{delta // 60}m ago"
    if delta < 86400:
        return f"{delta // 3600}h ago"
    return f"{delta // 86400}d ago"


async def _validate_jwt(api_base: str, jwt: str, character_id: str) -> tuple[bool, str]:
    dd = DDClient(base=api_base, token=jwt)
    try:
        game = await dd.get_game(character_id)
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        await dd.close()


# ---------------------------------------------------------------- /register

@tree.command(name="register", description="Bind your DD JWT + character to your Discord account (DM only).")
@app_commands.describe(
    character_id="Your DD character UUID",
    jwt="Your DD JWT (raw, no 'Bearer' prefix). Send via DM only.",
)
async def slash_register(
    interaction: discord.Interaction,
    character_id: str,
    jwt: str,
):
    if interaction.guild is not None:
        await interaction.response.send_message(
            "❌ `/register` only works in DMs — your JWT is sensitive. "
            "DM the bot directly and re-run there.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    base = DD_API_BASE.rstrip("/")
    ok, detail = await _validate_jwt(base, jwt, character_id)
    if not ok:
        await interaction.followup.send(
            f"❌ JWT validation failed: `{detail}`. Nothing was saved.",
            ephemeral=True,
        )
        return

    store.users_upsert(
        discord_id=str(interaction.user.id),
        character_id=character_id,
        jwt=jwt,
        dd_api_base=base,
    )
    await interaction.followup.send(
        f"✅ **Registered.** Character `{character_id}`.\n\n"
        + WELCOME_GUIDE,
        ephemeral=True,
    )


# ---------------------------------------------------------------- /run

@tree.command(name="run", description="Start an autonomous run with your registered character.")
@app_commands.describe(
    interactivity=(
        "How involved you want to be: "
        "0=fully autonomous, 1=ask at checkpoints, 2=+ die upgrades, "
        "3=+ mystery/campfire/Bub's, 4=+ map rerolls, 5=companion (you drive)"
    ),
)
async def slash_run(
    interaction: discord.Interaction,
    interactivity: app_commands.Range[int, 0, 5] = 0,
):
    discord_id = str(interaction.user.id)
    user = store.users_get(discord_id)
    if not user:
        await interaction.response.send_message(
            "❌ Not registered. DM the bot `/register` first.",
            ephemeral=True,
        )
        return

    active = store.runs_active_for_user(discord_id)
    if active:
        await interaction.response.send_message(
            f"❌ You already have an active run (#{active['id']}, status `{active['status']}`). "
            "Use `/status` to inspect, `/stop-bot` to detach, or `/forfeit-run` to end it.",
            ephemeral=True,
        )
        return

    if interaction.channel is None or not hasattr(interaction.channel, "create_thread"):
        await interaction.response.send_message(
            "❌ `/run` needs to be used in a channel where I can create a thread.",
            ephemeral=True,
        )
        return

    if interactivity == 5:
        await interaction.response.send_message(
            "⚠️ Companion mode (level 5) isn't built yet — coming in a future update. "
            "Pick 0-4 for now.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)

    thread = await interaction.channel.create_thread(
        name=f"run-{interaction.user.name}-{int(time.time())}",
        type=discord.ChannelType.public_thread,
    )

    run_id = store.runs_create(discord_id, thread_id=str(thread.id),
                                interactivity=interactivity)
    task = asyncio.create_task(_drive_run(
        run_id, user, thread,
        interactivity=interactivity,
        owner_user_id=interaction.user.id,
    ))
    running_tasks[run_id] = task

    await interaction.followup.send(
        f"🎲 Run #{run_id} started in {thread.mention} (interactivity={interactivity}).",
    )


async def _drive_run(
    run_id: int,
    user: dict,
    thread: discord.Thread,
    *,
    interactivity: int = 0,
    owner_user_id: int | None = None,
    existing_session_id: str | None = None,
) -> None:
    """Top-level coroutine for one run. Owns the DDClient and the
    play_full_run lifecycle. Posts events back to the user's thread.

    If existing_session_id is set we're resuming a previously-stuck run
    on the SAME DD session — caller is responsible for verifying the
    session is alive first.
    """
    out_dir = Path("data/full_runs") / f"{_stamp()}_bot_r{run_id}"
    dd = _client_for(user)
    if existing_session_id:
        await thread.send(
            f"🔁 **Restarting run #{run_id}** on existing session "
            f"`{existing_session_id}`. Interactivity: **{interactivity}**."
        )
    else:
        await thread.send(
            f"🟢 Agent acquiring slot (max {MAX_CONCURRENT_RUNS} concurrent). "
            f"Interactivity level: **{interactivity}**."
        )

    async with _run_semaphore:
        if not existing_session_id:
            await thread.send("🟢 Slot acquired. Starting run.")

        async def event_cb(event: dict):
            # Persist the DD session id as soon as we have one so /forfeit-run
            # and the Restart button can find it later (even if the run
            # subsequently goes stuck before play_full_run returns).
            if event.get("kind") == "session_started" and event.get("session_id"):
                try:
                    store.runs_set_session(run_id, event["session_id"])
                except Exception:
                    pass
            store.runs_touch(run_id)
            await _emit_to_thread(thread, event, run_id)

        async def prompt_cb(prompt: dict) -> str | None:
            store.runs_touch(run_id)
            return await _ask_in_thread(thread, prompt, owner_user_id or 0)

        try:
            summary = await play_full_run(
                dd,
                user["character_id"],
                out_dir,
                forfeit_on_exit=False,
                event_cb=event_cb,
                interactivity=interactivity,
                prompt_cb=prompt_cb,
                existing_session_id=existing_session_id,
            )
            store.runs_set_status(
                run_id,
                "finished",
                end_reason=(summary or {}).get("end_reason", "unknown"),
                summary_path=str(out_dir / "_summary.json"),
            )
            await _post_summary(thread, run_id, summary)

        except RunStuck as e:
            store.runs_set_status(
                run_id,
                "stuck",
                end_reason=e.end_reason,
                summary_path=str(out_dir / "_summary.json"),
                notes=f"DD session left alive: {e.session_id or '(none)'}",
            )
            await _post_stuck(thread, run_id, e, user, owner_user_id, interactivity)

        except Exception as e:
            tb = traceback.format_exc()
            store.runs_set_status(
                run_id,
                "errored",
                end_reason=f"exception:{type(e).__name__}",
                notes=tb[-500:],
            )
            await thread.send(
                f"⚠️ Run #{run_id} crashed inside the agent. "
                f"Your DD session was NOT touched — take over manually if it's still alive.\n"
                f"```\n{type(e).__name__}: {str(e)[:300]}\n```"
            )

        finally:
            await dd.close()
            running_tasks.pop(run_id, None)


async def _ask_in_thread(thread: discord.Thread, prompt: dict, owner_user_id: int) -> str | None:
    """Post a prompt with buttons, await the user's choice, return the
    chosen value. Returns None on PROMPT_TIMEOUT_SECONDS timeout (run
    will go stuck — no auto-pick, no auto-forfeit).
    """
    options = prompt.get("options") or []
    if not options:
        return None
    future: asyncio.Future = asyncio.get_event_loop().create_future()
    view = PromptView(options, future, owner_user_id)
    text = _format_prompt(prompt) + (
        f"\n_(Reply within {PROMPT_TIMEOUT_SECONDS}s or the run will go stuck.)_"
    )
    try:
        await thread.send(text, view=view)
    except Exception:
        return None
    try:
        return await asyncio.wait_for(future, timeout=PROMPT_TIMEOUT_SECONDS + 5)
    except asyncio.TimeoutError:
        return None


async def _emit_to_thread(thread: discord.Thread, event: dict, run_id: int) -> None:
    kind = event.get("kind")
    try:
        if kind == "session_started":
            await thread.send(f"▶️ Session `{event.get('session_id')}` started.")
        elif kind == "battle_won":
            mons = ", ".join(m.get("name", "?") for m in (event.get("monsters") or []))
            await thread.send(
                f"⚔️ B{event.get('battle_num')} **won** in {event.get('turns')} turn(s) "
                f"— HP {event.get('hp_at_end')} — {mons}"
            )
        elif kind == "battle_lost":
            mons = ", ".join(m.get("name", "?") for m in (event.get("monsters") or []))
            await thread.send(
                f"💀 B{event.get('battle_num')} **LOST** to {mons}"
            )
        elif kind == "battle_error":
            await thread.send(f"⚠️ B{event.get('battle_num')} errored.")
        elif kind == "run_ended":
            pass  # full summary follows separately
    except Exception:
        pass  # never let a Discord error kill the agent loop


async def _post_summary(thread: discord.Thread, run_id: int, summary: dict | None) -> None:
    s = summary or {}
    end = s.get("end_reason", "unknown")
    battles = s.get("battles") or []
    won = sum(1 for b in battles if b.get("result") == "won")
    lost = sum(1 for b in battles if b.get("result") == "lost")
    await thread.send(
        f"🏁 **Run #{run_id} finished** — `{end}`\n"
        f"Battles: {won}W / {lost}L (total {len(battles)})\n"
        f"Session: `{s.get('session_id') or 'n/a'}`"
    )


async def _post_stuck(
    thread: discord.Thread,
    run_id: int,
    stuck: RunStuck,
    user: dict,
    owner_user_id: int | None,
    interactivity: int,
) -> None:
    # Restart only makes sense when we have our own DD session to attach
    # to. active_session_exists/start_session_failed/no_session_id leave
    # us with nothing to restart.
    can_restart = bool(stuck.session_id) and stuck.end_reason not in (
        "active_session_exists", "start_session_failed", "no_session_id",
    )
    view = StuckView(run_id, user, owner_user_id, interactivity,
                     stuck.session_id, can_restart=can_restart)
    restart_hint = (
        "\nClick **Restart** to resume the bot on this same session."
        if can_restart else
        "\n_(Restart isn't available — there's no DD session attached to this run.)_"
    )
    await thread.send(
        f"🛑 **Run #{run_id} is stuck** (`{stuck.end_reason}`).\n"
        f"Your DD session is **still alive** — I won't touch it. "
        f"Take over in the game, or use the buttons below.\n"
        f"Session: `{stuck.session_id or 'n/a'}`"
        + restart_hint,
        view=view,
    )


class StuckView(discord.ui.View):
    def __init__(self, run_id: int, user: dict, owner_user_id: int | None,
                 interactivity: int, dd_session_id: str | None,
                 *, can_restart: bool):
        super().__init__(timeout=None)
        self.run_id = run_id
        self.user = user
        self.owner_user_id = owner_user_id
        self.interactivity = interactivity
        self.dd_session_id = dd_session_id
        if can_restart:
            self.add_item(_RestartButton(self))
        self.add_item(_StopBotButton(self))
        self.add_item(_ForfeitHintButton(self))


class _RestartButton(discord.ui.Button):
    def __init__(self, view: StuckView):
        super().__init__(style=discord.ButtonStyle.success, label="Restart (resume session)")
        self._view = view

    async def callback(self, interaction: discord.Interaction):
        v = self._view
        if v.owner_user_id and interaction.user.id != v.owner_user_id:
            await interaction.response.send_message(
                "❌ Only the run owner can restart.", ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate the DD session is still alive before spending compute
        # spinning up a new task.
        dd = _client_for(v.user)
        try:
            game = await dd.get_game(v.user["character_id"])
            last = (game or {}).get("lastSession") or {}
            in_state = (last.get("progress") or {}).get("inState")
            live_session = last.get("sessionId") or last.get("session_id")
            if not live_session or live_session != v.dd_session_id:
                await interaction.followup.send(
                    f"❌ DD no longer reports your session as live "
                    f"(saw `{live_session}`, expected `{v.dd_session_id}`). "
                    "Restart isn't possible — start a fresh `/run`.",
                    ephemeral=True,
                )
                return
            if in_state in ("dead", "lost", "won", "ended", "forfeited"):
                await interaction.followup.send(
                    f"❌ Session is in terminal state `{in_state}`. Nothing to resume.",
                    ephemeral=True,
                )
                return
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ Couldn't verify session state: `{type(e).__name__}: {str(e)[:200]}`. "
                "Restart aborted.",
                ephemeral=True,
            )
            return
        finally:
            await dd.close()

        thread = interaction.channel if isinstance(interaction.channel, discord.Thread) else None
        if thread is None:
            await interaction.followup.send(
                "❌ Couldn't resolve the thread for restart.", ephemeral=True,
            )
            return

        # Spawn the new run row + task.
        new_run_id = store.runs_create_resume(
            discord_id=str(v.owner_user_id) if v.owner_user_id else v.user.get("discord_id", ""),
            thread_id=str(thread.id),
            dd_session_id=v.dd_session_id,
            interactivity=v.interactivity,
            parent_run_id=v.run_id,
        )
        task = asyncio.create_task(_drive_run(
            new_run_id, v.user, thread,
            interactivity=v.interactivity,
            owner_user_id=v.owner_user_id,
            existing_session_id=v.dd_session_id,
        ))
        running_tasks[new_run_id] = task

        # Disable this view's buttons so user can't double-click.
        for child in v.children:
            child.disabled = True
        try:
            await interaction.message.edit(view=v)
        except Exception:
            pass

        await interaction.followup.send(
            f"🔁 Restarting as run #{new_run_id} on session `{v.dd_session_id}`.",
            ephemeral=True,
        )


class _StopBotButton(discord.ui.Button):
    def __init__(self, view: StuckView):
        super().__init__(style=discord.ButtonStyle.secondary, label="Stop bot (keep run alive)")
        self._view = view

    async def callback(self, interaction: discord.Interaction):
        await _do_stop_bot(interaction, self._view.run_id, via_button=True)


class _ForfeitHintButton(discord.ui.Button):
    def __init__(self, view: StuckView):
        super().__init__(style=discord.ButtonStyle.danger, label="Forfeit run")
        self._view = view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"To forfeit, type `/forfeit-run` and confirm. "
            f"This will end run #{self._view.run_id} on DD's side permanently.",
            ephemeral=True,
        )


# ---------------------------------------------------------------- /status

@tree.command(name="status", description="Show your active run status.")
async def slash_status(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    user = store.users_get(discord_id)
    if not user:
        await interaction.response.send_message("❌ Not registered.", ephemeral=True)
        return

    run = store.runs_active_for_user(discord_id)
    if not run:
        recent = store.runs_recent_for_user(discord_id, limit=3)
        if not recent:
            await interaction.response.send_message("No runs yet. `/run` to start.", ephemeral=True)
            return
        lines = [f"No active run. Recent:"]
        for r in recent:
            lines.append(f"  #{r['id']} `{r['status']}` — {r.get('end_reason') or '—'}")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    dd_session_id = run.get("dd_session_id")
    msg = [
        f"**Run #{run['id']}** — `{run['status']}`",
        f"Session: `{dd_session_id or 'pending'}`",
    ]
    if dd_session_id:
        dd = _client_for(user)
        try:
            char = await dd.get_character(dd_session_id)
            if isinstance(char, dict):
                msg.append(
                    f"HP {char.get('health')}/{char.get('max_health')} · "
                    f"gold {char.get('gold')} · pts {char.get('points')} · "
                    f"tc {char.get('time_crystal')}"
                )
        except Exception as e:
            msg.append(f"_(state fetch failed: {type(e).__name__})_")
        finally:
            await dd.close()
    await interaction.followup.send("\n".join(msg), ephemeral=True)


# ---------------------------------------------------------------- /stop-bot

@tree.command(name="stop-bot", description="Detach the bot from your run. The DD session stays alive.")
async def slash_stop_bot(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    run = store.runs_active_for_user(discord_id)
    if not run:
        await interaction.response.send_message("No active run to stop.", ephemeral=True)
        return
    await _do_stop_bot(interaction, run["id"], via_button=False)


async def _do_stop_bot(interaction: discord.Interaction, run_id: int, *, via_button: bool):
    task = running_tasks.pop(run_id, None)
    if task and not task.done():
        task.cancel()
    run = store.runs_get(run_id)
    store.runs_set_status(
        run_id,
        "stuck",
        end_reason="user_stop",
        notes="user invoked /stop-bot — DD session left untouched",
    )
    msg = (
        f"🛑 Detached from run #{run_id}. Your DD session "
        f"(`{(run or {}).get('dd_session_id') or 'unknown'}`) is **still alive** — "
        "take over in the game UI, or `/forfeit-run` here to end it."
    )
    if via_button:
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ---------------------------------------------------------------- /forfeit-run

class ForfeitConfirmModal(discord.ui.Modal, title="Confirm forfeit"):
    confirmation = discord.ui.TextInput(
        label="Type the run number to confirm",
        placeholder="e.g. 42",
        min_length=1,
        max_length=10,
    )

    def __init__(self, run_id: int, user: dict):
        super().__init__()
        self.run_id = run_id
        self.user = user

    async def on_submit(self, interaction: discord.Interaction):
        if (self.confirmation.value or "").strip() != str(self.run_id):
            await interaction.response.send_message(
                f"❌ Confirmation mismatch (expected `{self.run_id}`). Forfeit aborted.",
                ephemeral=True,
            )
            return

        run = store.runs_get(self.run_id)
        if not run or run["status"] not in ("queued", "running", "stuck", "errored"):
            await interaction.response.send_message(
                f"❌ Run #{self.run_id} is in status `{(run or {}).get('status')}` — nothing to forfeit.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Cancel the live task if any.
        task = running_tasks.pop(self.run_id, None)
        if task and not task.done():
            task.cancel()

        session_id = run.get("dd_session_id")
        if not session_id:
            store.runs_set_status(self.run_id, "finished", end_reason="user_forfeit_no_session")
            await interaction.followup.send(
                f"Run #{self.run_id} had no DD session. Marked finished.",
                ephemeral=True,
            )
            return

        dd = _client_for(self.user)
        try:
            await dd.forfeit(session_id)
            store.runs_set_status(
                self.run_id, "finished", end_reason="user_forfeit",
                notes="user forfeited via /forfeit-run",
            )
            await interaction.followup.send(
                f"✅ Run #{self.run_id} forfeited on DD's side.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"⚠️ DD forfeit call failed: `{type(e).__name__}: {str(e)[:200]}`. "
                f"The run record is unchanged. You may need to forfeit in-game.",
                ephemeral=True,
            )
        finally:
            await dd.close()


@tree.command(name="forfeit-run", description="Forfeit your active run (requires confirmation).")
async def slash_forfeit_run(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    user = store.users_get(discord_id)
    if not user:
        await interaction.response.send_message("❌ Not registered.", ephemeral=True)
        return
    run = store.runs_active_for_user(discord_id)
    if not run:
        recent = store.runs_recent_for_user(discord_id, limit=1)
        if recent and recent[0]["status"] in ("stuck", "errored"):
            run = recent[0]
        else:
            await interaction.response.send_message(
                "No active or stuck run to forfeit.", ephemeral=True,
            )
            return
    await interaction.response.send_modal(ForfeitConfirmModal(run["id"], user))


# ---------------------------------------------------------------- /attach

@tree.command(
    name="attach",
    description="Attach the bot to an in-progress DD session (e.g. tournament NFT run started in-game).",
)
@app_commands.describe(
    session_id="The DD session UUID for the run already in progress.",
    interactivity=(
        "How involved you want to be: 0=fully autonomous, 1=ask at checkpoints, "
        "2=+ die upgrades, 3=+ mystery/campfire/Bub's, 4=+ map rerolls"
    ),
)
async def slash_attach(
    interaction: discord.Interaction,
    session_id: str,
    interactivity: app_commands.Range[int, 0, 4] = 0,
):
    discord_id = str(interaction.user.id)
    user = store.users_get(discord_id)
    if not user:
        await interaction.response.send_message(
            "❌ Not registered. DM the bot `/register` first.",
            ephemeral=True,
        )
        return

    if interaction.channel is None or not hasattr(interaction.channel, "create_thread"):
        await interaction.response.send_message(
            "❌ `/attach` needs to be used in a channel where I can create a thread.",
            ephemeral=True,
        )
        return

    session_id = (session_id or "").strip()
    if not session_id:
        await interaction.response.send_message(
            "❌ session_id is required.", ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)

    # Validate the session is alive AND belongs to this user's character.
    dd = _client_for(user)
    try:
        game = await dd.get_game(user["character_id"])
        last = (game or {}).get("lastSession") or {}
        live = last.get("sessionId") or last.get("session_id")
        in_state = (last.get("progress") or {}).get("inState")
        if live != session_id:
            await interaction.followup.send(
                f"❌ DD doesn't report `{session_id}` as your character's live session "
                f"(saw `{live}`). Check the session ID, or start the run in-game first.",
            )
            return
        if in_state in ("dead", "lost", "won", "ended", "forfeited"):
            await interaction.followup.send(
                f"❌ Session is in terminal state `{in_state}`. Nothing to attach to.",
            )
            return
    except Exception as e:
        await interaction.followup.send(
            f"⚠️ Couldn't verify session: `{type(e).__name__}: {str(e)[:200]}`. Attach aborted.",
        )
        return
    finally:
        await dd.close()

    thread = await interaction.channel.create_thread(
        name=f"attach-{interaction.user.name}-{int(time.time())}",
        type=discord.ChannelType.public_thread,
    )

    run_id = store.runs_create_resume(
        discord_id=discord_id,
        thread_id=str(thread.id),
        dd_session_id=session_id,
        interactivity=interactivity,
        parent_run_id=None,
        note=f"attached via /attach by user (interactivity={interactivity})",
    )
    task = asyncio.create_task(_drive_run(
        run_id, user, thread,
        interactivity=interactivity,
        owner_user_id=interaction.user.id,
        existing_session_id=session_id,
    ))
    running_tasks[run_id] = task

    await interaction.followup.send(
        f"🔗 Attached to session `{session_id}` as run #{run_id} in {thread.mention} "
        f"(interactivity={interactivity}).",
    )


# ---------------------------------------------------------------- /resume

@tree.command(name="resume", description="Resume a previously stuck run on its existing DD session.")
async def slash_resume(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)
    user = store.users_get(discord_id)
    if not user:
        await interaction.response.send_message("❌ Not registered.", ephemeral=True)
        return

    resumable = store.runs_resumable(discord_id)
    if not resumable:
        await interaction.response.send_message(
            "No resumable runs. A run is resumable when the bot saved its DD session ID "
            "and the run went stuck (timeout, error, or you `/stop-bot`'d it).",
            ephemeral=True,
        )
        return

    options = []
    for r in resumable[:25]:
        sid = r.get("dd_session_id") or ""
        sid_short = sid[:8]
        ago = _format_ago(r.get("last_event_at"))
        end_reason = (r.get("end_reason") or "?")[:40]
        label = f"Run #{r['id']} · {ago} · …{sid_short}"[:100]
        desc = f"interactivity {r.get('interactivity') or 0} · stuck: {end_reason}"[:100]
        options.append(discord.SelectOption(label=label, description=desc, value=str(r['id'])))

    view = ResumeView(user, interaction.user.id, options)
    await interaction.response.send_message(
        f"Pick one of your **{len(resumable)}** stuck run(s) to resume "
        f"(showing latest per session). The bot will validate the DD session is still alive before re-attaching.",
        view=view,
        ephemeral=True,
    )


class ResumeView(discord.ui.View):
    def __init__(self, user: dict, owner_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=120)
        self.user = user
        self.owner_id = owner_id
        self.add_item(_ResumeSelect(self, options))


class _ResumeSelect(discord.ui.Select):
    def __init__(self, view: ResumeView, options: list[discord.SelectOption]):
        super().__init__(placeholder="Pick a run to resume", options=options,
                         min_values=1, max_values=1)
        self._owner_view = view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._owner_view.owner_id:
            await interaction.response.send_message("❌ Not your menu.", ephemeral=True)
            return
        run_id = int(self.values[0])
        await _do_resume(interaction, run_id, self._owner_view.user, self._owner_view.owner_id)


async def _do_resume(interaction: discord.Interaction, run_id: int,
                     user: dict, owner_user_id: int):
    run = store.runs_get(run_id)
    if not run or run.get("status") != "stuck" or not run.get("dd_session_id"):
        await interaction.response.send_message(
            f"Run #{run_id} is no longer resumable (status changed).",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    dd_session_id = run["dd_session_id"]
    interactivity = int(run.get("interactivity") or 0)

    # Validate the DD session is still live before we spin up a task.
    dd = _client_for(user)
    try:
        game = await dd.get_game(user["character_id"])
        last = (game or {}).get("lastSession") or {}
        live = last.get("sessionId") or last.get("session_id")
        in_state = (last.get("progress") or {}).get("inState")
        if live != dd_session_id:
            await interaction.followup.send(
                f"❌ DD reports a different live session "
                f"(`{live}` vs expected `{dd_session_id}`). "
                "Your saved session may have expired or been forfeited externally.",
                ephemeral=True,
            )
            return
        if in_state in ("dead", "lost", "won", "ended", "forfeited"):
            await interaction.followup.send(
                f"❌ Session is in terminal state `{in_state}`. Nothing to resume.",
                ephemeral=True,
            )
            return
    except Exception as e:
        await interaction.followup.send(
            f"⚠️ Couldn't verify session: `{type(e).__name__}: {str(e)[:200]}`. Resume aborted.",
            ephemeral=True,
        )
        return
    finally:
        await dd.close()

    # Reuse the original thread when possible; fall back to a new one in the
    # current channel.
    thread: discord.Thread | None = None
    if run.get("thread_id"):
        try:
            ch = await client.fetch_channel(int(run["thread_id"]))
            if isinstance(ch, discord.Thread) and not ch.archived:
                thread = ch
        except Exception:
            thread = None
    if thread is None:
        if interaction.channel and hasattr(interaction.channel, "create_thread"):
            thread = await interaction.channel.create_thread(
                name=f"resume-r{run_id}-{int(time.time())}",
                type=discord.ChannelType.public_thread,
            )
        else:
            await interaction.followup.send(
                "❌ Original thread is gone and I can't create a new one here. "
                "Try `/resume` from a regular channel.",
                ephemeral=True,
            )
            return

    new_run_id = store.runs_create_resume(
        discord_id=str(owner_user_id),
        thread_id=str(thread.id),
        dd_session_id=dd_session_id,
        interactivity=interactivity,
        parent_run_id=run_id,
    )
    task = asyncio.create_task(_drive_run(
        new_run_id, user, thread,
        interactivity=interactivity,
        owner_user_id=owner_user_id,
        existing_session_id=dd_session_id,
    ))
    running_tasks[new_run_id] = task

    await interaction.followup.send(
        f"🔁 Resuming run #{run_id} as new run #{new_run_id} on session "
        f"`{dd_session_id}` in {thread.mention}.",
        ephemeral=True,
    )


# ---------------------------------------------------------------- /help

@tree.command(name="help", description="List bot commands.")
async def slash_help(interaction: discord.Interaction):
    await interaction.response.send_message(WELCOME_GUIDE, ephemeral=True)


# ---------------------------------------------------------------- lifecycle

@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready: {client.user}")
    n = await recovery.recover_orphan_runs(client)
    if n:
        print(f"[recovery] reclassified {n} orphan run(s) as stuck")


def main():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
