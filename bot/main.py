"""Discord bot — player interaction hub (mock).

Slash commands:
  /run      — start a mock agent run
  /status   — show the active run state
  /forfeit  — end the active run

The bot subscribes to the in-memory bus for narration + player prompts from
the agent loop. Prompts are rendered as messages with button components.
"""
import asyncio

import discord
from discord import app_commands

from dd_agent.bus import bus
from dd_agent.config import DISCORD_BOT_TOKEN, WEB_BASE_URL
from dd_agent.dd_client import DDClient
from dd_agent.loop import AgentRun


intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# user_id → active AgentRun (mock single-run-per-user)
active_runs: dict[int, AgentRun] = {}


class CheckpointView(discord.ui.View):
    def __init__(self, run: AgentRun):
        super().__init__(timeout=120)
        self.run = run

    @discord.ui.button(label="Continue", style=discord.ButtonStyle.success)
    async def _continue(self, interaction: discord.Interaction, _: discord.ui.Button):
        ok = self.run.supply_player_answer("continue")
        await interaction.response.send_message(
            "Continuing." if ok else "Too late — agent already moved on.",
            ephemeral=True,
        )
        self.stop()

    @discord.ui.button(label="Unstake", style=discord.ButtonStyle.danger)
    async def _unstake(self, interaction: discord.Interaction, _: discord.ui.Button):
        ok = self.run.supply_player_answer("unstake")
        await interaction.response.send_message(
            "Unstaking." if ok else "Too late — agent already moved on.",
            ephemeral=True,
        )
        self.stop()


@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot ready: {client.user}")


@tree.command(name="run", description="Start an AI agent run (mock).")
@app_commands.describe(
    character_id="Your NFT / character id",
    time_crystals="0-7 TCs to bring",
)
async def slash_run(
    interaction: discord.Interaction,
    character_id: str,
    time_crystals: int = 0,
):
    if interaction.user.id in active_runs:
        await interaction.response.send_message(
            "You already have a run in progress.", ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)

    dd = DDClient()
    # TODO: real start_tournament / start_session call — mock session id for now
    session_id = f"mock-{interaction.user.id}"
    run = AgentRun(session_id=session_id, character_id=character_id, client=dd)
    active_runs[interaction.user.id] = run

    thread = await interaction.channel.create_thread(
        name=f"run-{interaction.user.name}",
        type=discord.ChannelType.public_thread,
    )
    await thread.send(
        f"🎲 Agent starting run for `{character_id}` with {time_crystals} TC.\n"
        f"🔗 Live viewer: {WEB_BASE_URL}/viewer/{session_id}"
    )

    asyncio.create_task(_relay_narration(thread, session_id))
    asyncio.create_task(_relay_prompts(thread, session_id, run))
    asyncio.create_task(run.run())

    await interaction.followup.send(f"Run started. Follow in {thread.mention}.")


async def _relay_narration(thread: discord.Thread, session_id: str):
    q = bus.subscribe(f"run:{session_id}:narration")
    try:
        while True:
            msg = await q.get()
            await thread.send(str(msg))
    finally:
        bus.unsubscribe(f"run:{session_id}:narration", q)


async def _relay_prompts(thread: discord.Thread, session_id: str, run: AgentRun):
    q = bus.subscribe(f"run:{session_id}:prompt")
    try:
        while True:
            prompt = await q.get()
            text = f"**Decision needed:** {prompt.get('text', '')}"
            if prompt.get("kind") == "checkpoint":
                await thread.send(text, view=CheckpointView(run))
            else:
                await thread.send(text)
    finally:
        bus.unsubscribe(f"run:{session_id}:prompt", q)


@tree.command(name="status", description="Show your active run status.")
async def slash_status(interaction: discord.Interaction):
    run = active_runs.get(interaction.user.id)
    if not run:
        await interaction.response.send_message("No active run.", ephemeral=True)
        return
    try:
        state = await run.client.get_character(run.session_id)
    except Exception as e:
        await interaction.response.send_message(f"State fetch failed: {e}", ephemeral=True)
        return
    await interaction.response.send_message(
        f"Session `{run.session_id}`\n"
        f"State: `{(state or {}).get('inState')}`\n"
        f"HP: {(state or {}).get('health')}/{(state or {}).get('maxHealth')}",
        ephemeral=True,
    )


@tree.command(name="forfeit", description="Forfeit your active run.")
async def slash_forfeit(interaction: discord.Interaction):
    run = active_runs.pop(interaction.user.id, None)
    if not run:
        await interaction.response.send_message("No active run.", ephemeral=True)
        return
    try:
        await run.client.forfeit(run.session_id)
    finally:
        await run.client.close()
    await interaction.response.send_message("Forfeited.", ephemeral=True)


def main():
    if not DISCORD_BOT_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN not set")
    client.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
