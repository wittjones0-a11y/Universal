"""Activity logging cog."""
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot_helpers import slash_send
from database import Database

logger = logging.getLogger(__name__)


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith("/"):
            return

        try:
            await self.db.run(self.db.add_user, message.author.id, message.guild.id)
            await self.db.run(
                self.db.log_message,
                message.author.id,
                message.guild.id,
                message.channel.id,
                message.id,
                message.content,
            )
        except Exception as exc:
            logger.warning("Message log failed: %s", exc)

    @app_commands.command(name="logs", description="View activity logs for a user")
    @app_commands.describe(member="User to check")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def view_logs(self, interaction: discord.Interaction, member: discord.Member):
        logs = await self.db.run(
            self.db.get_message_logs, member.id, interaction.guild.id, 10
        )

        embed = discord.Embed(
            title=f"Activity logs — {member.display_name}",
            color=discord.Color.blue(),
        )

        if logs:
            for i, row in enumerate(logs, 1):
                channel_id, content, timestamp = row
                short = (content or "(no content)")[:190]
                channel = interaction.guild.get_channel(channel_id)
                ch_label = channel.mention if channel else f"<#{channel_id}>"
                embed.add_field(
                    name=f"{i}. {ch_label}",
                    value=f"{short}\n*{timestamp}*",
                    inline=False,
                )
        else:
            embed.description = "No message logs for this user."

        await slash_send(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="logsetup", description="Set the audit log channel (Admin)")
    @app_commands.describe(channel="Channel for audit logs (defaults to current channel)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def log_setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        await self._do_log_setup(interaction, channel)

    async def _do_log_setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel],
    ):
        target = channel or interaction.channel
        try:
            await self.db.run(
                self.db.set_log_channel, interaction.guild.id, target.id
            )
            embed = discord.Embed(
                title="✅ Log Channel Configured",
                description=f"Audit logs will now be sent to {target.mention}.",
                color=discord.Color.from_rgb(87, 242, 135),
            )
            embed.add_field(
                name="📋 Logged Activity",
                value="Messages, moderation actions, warnings, mutes, kicks, bans, and unbans.",
                inline=False,
            )
            embed.set_footer(text="Logging system is active")
            await slash_send(interaction, embed=embed, ephemeral=True)
            await target.send(
                embed=discord.Embed(
                    title="📜 Audit Log Channel",
                    description="This channel is now configured to receive server audit logs.",
                    color=discord.Color.from_rgb(88, 101, 242),
                )
            )
        except Exception as exc:
            logger.error("logsetup failed: %s", exc, exc_info=True)
            await slash_send(
                interaction, content=f"Failed to set log channel: {exc}", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Logging(bot))
