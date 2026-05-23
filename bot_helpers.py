"""Shared helpers for slash command interactions."""
import logging
from typing import Optional

import discord

logger = logging.getLogger(__name__)

# Commands that show a public (non-ephemeral) reply
PUBLIC_COMMANDS = frozenset({"warn", "mute", "unmute", "kick", "ban", "unban", "warnings"})


async def defer_command(interaction: discord.Interaction) -> bool:
    """Acknowledge the interaction within Discord's 3-second window."""
    if interaction.response.is_done():
        return True
    cmd = interaction.command
    ephemeral = True
    if cmd and cmd.name in PUBLIC_COMMANDS:
        ephemeral = False
    try:
        await interaction.response.defer(ephemeral=ephemeral, thinking=True)
        return True
    except discord.HTTPException as exc:
        logger.error("Defer failed for /%s: %s", cmd.name if cmd else "?", exc)
        return False


async def slash_send(
    interaction: discord.Interaction,
    *,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    ephemeral: bool = False,
) -> None:
    """Send a slash command reply (works after defer or without)."""
    kwargs = {}
    if content is not None:
        kwargs["content"] = content
    if embed is not None:
        kwargs["embed"] = embed
    if ephemeral:
        kwargs["ephemeral"] = True

    if interaction.response.is_done():
        await interaction.followup.send(**kwargs)
    else:
        await interaction.response.send_message(**kwargs)
