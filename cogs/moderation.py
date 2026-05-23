"""Moderation commands cog."""
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta

from bot_helpers import slash_send
from database import Database

logger = logging.getLogger(__name__)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            self.db = Database()
        except Exception as e:
            logger.error("Database init failed: %s", e, exc_info=True)
            raise

    async def _get_bot_member(self, guild: discord.Guild) -> Optional[discord.Member]:
        me = guild.me
        if me is not None:
            return me
        try:
            return await guild.fetch_member(self.bot.user.id)
        except discord.HTTPException as e:
            logger.error("Could not fetch bot member in %s: %s", guild.id, e)
            return None

    async def _bot_can_moderate(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> Optional[str]:
        me = await self._get_bot_member(interaction.guild)
        if me is None:
            return "Bot member data unavailable — try again in a moment."

        if member.id == interaction.guild.owner_id:
            return "Cannot moderate the server owner."
        if member.top_role >= me.top_role:
            return "I cannot moderate this user — move my role above theirs in Server Settings → Roles."
        if (
            member.top_role >= interaction.user.top_role
            and interaction.user.id != interaction.guild.owner_id
        ):
            return "You cannot moderate a member with an equal or higher role than yours."
        return None

    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.describe(member="User to warn", reason="Reason for warning")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def warn_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        if member.bot:
            await slash_send(interaction, content="You cannot warn bots.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.moderate_members:
            await slash_send(
                interaction, content="You need **Moderate Members** permission.", ephemeral=True
            )
            return
        blocked = await self._bot_can_moderate(interaction, member)
        if blocked:
            await slash_send(interaction, content=blocked, ephemeral=True)
            return

        try:
            await self.db.run(self.db.add_user, member.id, interaction.guild.id)
            warning_count = await self.db.run(
                self.db.add_warning,
                member.id, interaction.guild.id, reason, interaction.user.id,
            )
            await self.db.run(
                self.db.log_moderation,
                member.id, interaction.guild.id, "warn", reason, interaction.user.id,
            )
        except Exception as e:
            logger.error("Warn DB error: %s", e, exc_info=True)
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title="User Warned",
            description=f"{member.mention} has been warned.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Warnings", value=f"{warning_count}/3")
        embed.set_footer(text=f"Warned by {interaction.user}")
        await slash_send(interaction, embed=embed)

        try:
            dm_embed = discord.Embed(
                title="Warning",
                description=f"You have been warned in {interaction.guild.name}",
                color=discord.Color.orange(),
            )
            dm_embed.add_field(name="Reason", value=reason)
            dm_embed.add_field(name="Total Warnings", value=f"{warning_count}/3")
            await member.send(embed=dm_embed)
        except discord.HTTPException:
            pass

        if warning_count >= 3:
            await self._apply_mute(
                interaction, member, "Auto-mute: 3 warnings", 3600, announce=True
            )

    @app_commands.command(name="mute", description="Mute a user")
    @app_commands.describe(
        member="User to mute",
        duration="Duration in seconds (default 300)",
        reason="Reason for mute",
    )
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def mute_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: int = 300,
        reason: str = "No reason provided",
    ):
        if member.bot:
            await slash_send(interaction, content="You cannot mute bots.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.moderate_members:
            await slash_send(
                interaction, content="You need **Moderate Members** permission.", ephemeral=True
            )
            return
        blocked = await self._bot_can_moderate(interaction, member)
        if blocked:
            await slash_send(interaction, content=blocked, ephemeral=True)
            return

        me = await self._get_bot_member(interaction.guild)
        if not me or not me.guild_permissions.moderate_members:
            await slash_send(
                interaction,
                content="I need **Moderate Members** permission to timeout users.",
                ephemeral=True,
            )
            return

        await self._apply_mute(interaction, member, reason, duration, announce=True)

    async def _apply_mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
        duration: int = 300,
        *,
        announce: bool = True,
    ):
        mute_until = datetime.utcnow() + timedelta(seconds=duration)
        try:
            await self.db.run(self.db.add_user, member.id, interaction.guild.id)
            await self.db.run(self.db.set_muted, member.id, interaction.guild.id, mute_until)
            await self.db.run(
                self.db.log_moderation,
                member.id, interaction.guild.id, "mute", reason, interaction.user.id,
            )
        except Exception as e:
            logger.error("Mute DB error: %s", e, exc_info=True)
            if announce:
                await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        try:
            await member.timeout(timedelta(seconds=duration), reason=reason)
        except discord.Forbidden:
            if announce:
                await slash_send(
                    interaction,
                    content="Could not mute — check my role position and **Moderate Members**.",
                    ephemeral=True,
                )
            return
        except discord.HTTPException as e:
            logger.error("Mute failed: %s", e)
            if announce:
                await slash_send(
                    interaction,
                    content=f"Could not mute: {e.text or 'Discord API error'}",
                    ephemeral=True,
                )
            return

        if not announce:
            return

        minutes = max(duration // 60, 1)
        embed = discord.Embed(
            title="User Muted",
            description=f"{member.mention} has been muted for {minutes} minute(s).",
            color=discord.Color.red(),
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Muted by {interaction.user}")
        await slash_send(interaction, embed=embed)

    @app_commands.command(name="unmute", description="Unmute a user")
    @app_commands.describe(member="User to unmute")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def unmute_user(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await slash_send(
                interaction, content="You need **Moderate Members** permission.", ephemeral=True
            )
            return
        blocked = await self._bot_can_moderate(interaction, member)
        if blocked:
            await slash_send(interaction, content=blocked, ephemeral=True)
            return

        try:
            await self.db.run(self.db.set_muted, member.id, interaction.guild.id)
            await self.db.run(
                self.db.log_moderation,
                member.id, interaction.guild.id, "unmute", moderator_id=interaction.user.id,
            )
        except Exception as e:
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        try:
            await member.timeout(None, reason="Unmuted")
        except discord.Forbidden:
            await slash_send(
                interaction,
                content="Could not unmute — check my role and **Moderate Members**.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await slash_send(
                interaction,
                content=f"Could not unmute: {e.text or 'Discord API error'}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="User Unmuted",
            description=f"{member.mention} has been unmuted.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Unmuted by {interaction.user}")
        await slash_send(interaction, embed=embed)

    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.describe(member="User to kick", reason="Reason for kick")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guild_only()
    async def kick_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        if member.bot:
            await slash_send(interaction, content="You cannot kick bots.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.kick_members:
            await slash_send(
                interaction, content="You need **Kick Members** permission.", ephemeral=True
            )
            return
        blocked = await self._bot_can_moderate(interaction, member)
        if blocked:
            await slash_send(interaction, content=blocked, ephemeral=True)
            return

        me = await self._get_bot_member(interaction.guild)
        if not me or not me.guild_permissions.kick_members:
            await slash_send(
                interaction, content="I need **Kick Members** permission.", ephemeral=True
            )
            return

        try:
            await self.db.run(
                self.db.log_moderation,
                member.id, interaction.guild.id, "kick", reason, interaction.user.id,
            )
        except Exception as e:
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        try:
            await member.send(
                f"You have been kicked from {interaction.guild.name}. Reason: {reason}"
            )
        except discord.HTTPException:
            pass

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            await slash_send(
                interaction,
                content="Could not kick — check my role position and **Kick Members**.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await slash_send(
                interaction,
                content=f"Could not kick: {e.text or 'Discord API error'}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="User Kicked",
            description=f"{member} has been kicked.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Kicked by {interaction.user}")
        await slash_send(interaction, embed=embed)

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(member="User to ban", reason="Reason for ban")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def ban_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
    ):
        if member.bot:
            await slash_send(interaction, content="You cannot ban bots.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.ban_members:
            await slash_send(
                interaction, content="You need **Ban Members** permission.", ephemeral=True
            )
            return
        blocked = await self._bot_can_moderate(interaction, member)
        if blocked:
            await slash_send(interaction, content=blocked, ephemeral=True)
            return

        me = await self._get_bot_member(interaction.guild)
        if not me or not me.guild_permissions.ban_members:
            await slash_send(
                interaction, content="I need **Ban Members** permission.", ephemeral=True
            )
            return

        try:
            await self.db.run(
                self.db.log_moderation,
                member.id, interaction.guild.id, "ban", reason, interaction.user.id,
            )
        except Exception as e:
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        try:
            await member.send(
                f"You have been banned from {interaction.guild.name}. Reason: {reason}"
            )
        except discord.HTTPException:
            pass

        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            await slash_send(
                interaction,
                content="Could not ban — check my role position and **Ban Members**.",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await slash_send(
                interaction,
                content=f"Could not ban: {e.text or 'Discord API error'}",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="User Banned",
            description=f"{member} has been banned.",
            color=discord.Color.dark_red(),
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Banned by {interaction.user}")
        await slash_send(interaction, embed=embed)

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="ID of user to unban")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guild_only()
    async def unban_user(self, interaction: discord.Interaction, user_id: str):
        if not interaction.user.guild_permissions.ban_members:
            await slash_send(
                interaction, content="You need **Ban Members** permission.", ephemeral=True
            )
            return

        me = await self._get_bot_member(interaction.guild)
        if not me or not me.guild_permissions.ban_members:
            await slash_send(
                interaction, content="I need **Ban Members** permission.", ephemeral=True
            )
            return

        try:
            user_id_int = int(user_id)
        except ValueError:
            await slash_send(
                interaction, content="Invalid user ID. Use numbers only.", ephemeral=True
            )
            return

        try:
            user = await self.bot.fetch_user(user_id_int)
            await interaction.guild.unban(user)
            await self.db.run(
                self.db.log_moderation,
                user_id_int, interaction.guild.id, "unban", moderator_id=interaction.user.id,
            )
            await slash_send(interaction, content=f"{user} has been unbanned.")
        except discord.NotFound:
            await slash_send(interaction, content="User not found in ban list.", ephemeral=True)
        except discord.Forbidden:
            await slash_send(
                interaction,
                content="Could not unban — I need **Ban Members** permission.",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            await slash_send(
                interaction,
                content=f"Could not unban: {e.text or 'Discord API error'}",
                ephemeral=True,
            )

    @app_commands.command(name="warnings", description="View warnings for a user")
    @app_commands.describe(member="User to check")
    @app_commands.guild_only()
    async def get_warnings(self, interaction: discord.Interaction, member: discord.Member):
        try:
            warning_count = await self.db.run(
                self.db.get_warnings, member.id, interaction.guild.id
            )
            logs = await self.db.run(
                self.db.get_user_logs, member.id, interaction.guild.id, 5
            )
        except Exception as e:
            logger.error("Warnings DB error: %s", e, exc_info=True)
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Warnings for {member}",
            description=f"Total warnings: {warning_count}/3",
            color=discord.Color.orange(),
        )
        if logs:
            log_text = ""
            for log in logs:
                action, reason, _timestamp = log
                log_text += f"**{action.upper()}** — {reason or 'No reason'}\n"
            embed.add_field(name="Recent Actions", value=log_text)
        else:
            embed.add_field(name="Recent Actions", value="No moderation history")

        await slash_send(interaction, embed=embed)

    @app_commands.command(name="modlog", description="View moderation log for a user")
    @app_commands.describe(member="User to check")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def modlog(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await slash_send(
                interaction, content="You need **Moderate Members** permission.", ephemeral=True
            )
            return

        try:
            logs = await self.db.run(
                self.db.get_user_logs, member.id, interaction.guild.id, 10
            )
        except Exception as e:
            logger.error("Modlog DB error: %s", e, exc_info=True)
            await slash_send(interaction, content=f"Database error: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Moderation Log — {member}",
            color=discord.Color.blue(),
        )
        if logs:
            for i, log in enumerate(logs, 1):
                action, reason, timestamp = log
                embed.add_field(
                    name=f"{i}. {action.upper()}",
                    value=f"**Reason:** {reason or 'None'}\n**Time:** {timestamp}",
                    inline=False,
                )
        else:
            embed.description = "No moderation history for this user."

        await slash_send(interaction, embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
