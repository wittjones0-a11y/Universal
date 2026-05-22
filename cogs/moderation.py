"""Moderation commands cog."""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from database import Database

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="warn", description="Warn a user")
    @app_commands.describe(member="User to warn", reason="Reason for warning")
    async def warn_user(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Warn a user."""
        if member.bot:
            await interaction.response.send_message("❌ You cannot warn bots!", ephemeral=True)
            return

        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        self.db.add_user(member.id, interaction.guild.id)
        warning_count = self.db.add_warning(member.id, interaction.guild.id, reason, interaction.user.id)
        self.db.log_moderation(member.id, interaction.guild.id, "warn", reason, interaction.user.id)

        embed = discord.Embed(
            title="⚠️ User Warned",
            description=f"{member.mention} has been warned.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reason", value=reason)
        embed.add_field(name="Warnings", value=f"{warning_count}/3")
        embed.set_footer(text=f"Warned by {interaction.user}")
        await interaction.response.send_message(embed=embed)

        try:
            dm_embed = discord.Embed(
                title="⚠️ Warning",
                description=f"You have been warned in {interaction.guild.name}",
                color=discord.Color.orange()
            )
            dm_embed.add_field(name="Reason", value=reason)
            dm_embed.add_field(name="Total Warnings", value=f"{warning_count}/3")
            await member.send(embed=dm_embed)
        except:
            pass

        if warning_count >= 3:
            await self._mute_user(interaction, member, "Auto-mute: 3 warnings", 3600, silent=True)

    @app_commands.command(name="mute", description="Mute a user")
    @app_commands.describe(member="User to mute", duration="Duration in seconds (default 300)", reason="Reason for mute")
    async def mute_user(self, interaction: discord.Interaction, member: discord.Member, duration: int = 300, reason: str = "No reason provided"):
        """Mute a user for specified seconds."""
        if member.bot:
            await interaction.response.send_message("❌ You cannot mute bots!", ephemeral=True)
            return

        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        await self._mute_user(interaction, member, reason, duration)

    async def _mute_user(self, interaction: discord.Interaction, member: discord.Member, reason: str, duration: int = 300, silent: bool = False):
        """Internal mute function."""
        mute_until = datetime.utcnow() + timedelta(seconds=duration)
        self.db.set_muted(member.id, interaction.guild.id, mute_until)
        self.db.log_moderation(member.id, interaction.guild.id, "mute", reason, interaction.user.id)

        try:
            await member.timeout(timedelta(seconds=duration), reason=reason)
        except:
            pass

        minutes = duration // 60
        embed = discord.Embed(
            title="🔇 User Muted",
            description=f"{member.mention} has been muted for {minutes} minutes.",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Muted by {interaction.user}")
        
        if not silent:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a user")
    @app_commands.describe(member="User to unmute")
    async def unmute_user(self, interaction: discord.Interaction, member: discord.Member):
        """Unmute a user."""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        self.db.set_muted(member.id, interaction.guild.id)
        self.db.log_moderation(member.id, interaction.guild.id, "unmute", moderator_id=interaction.user.id)

        try:
            await member.timeout(None, reason="Unmuted")
        except:
            pass

        embed = discord.Embed(
            title="🔊 User Unmuted",
            description=f"{member.mention} has been unmuted.",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Unmuted by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.describe(member="User to kick", reason="Reason for kick")
    async def kick_user(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Kick a user from the server."""
        if member.bot:
            await interaction.response.send_message("❌ You cannot kick bots!", ephemeral=True)
            return

        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        self.db.log_moderation(member.id, interaction.guild.id, "kick", reason, interaction.user.id)

        try:
            await member.send(f"You have been kicked from {interaction.guild.name}. Reason: {reason}")
        except:
            pass

        await interaction.guild.kick(member, reason=reason)

        embed = discord.Embed(
            title="👢 User Kicked",
            description=f"{member} has been kicked.",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Kicked by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(member="User to ban", reason="Reason for ban")
    async def ban_user(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """Ban a user from the server."""
        if member.bot:
            await interaction.response.send_message("❌ You cannot ban bots!", ephemeral=True)
            return

        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        self.db.log_moderation(member.id, interaction.guild.id, "ban", reason, interaction.user.id)

        try:
            await member.send(f"You have been banned from {interaction.guild.name}. Reason: {reason}")
        except:
            pass

        await interaction.guild.ban(member, reason=reason)

        embed = discord.Embed(
            title="🔨 User Banned",
            description=f"{member} has been banned.",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Reason", value=reason)
        embed.set_footer(text=f"Banned by {interaction.user}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="ID of user to unban")
    async def unban_user(self, interaction: discord.Interaction, user_id: int):
        """Unban a user by ID."""
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user)
            self.db.log_moderation(user_id, interaction.guild.id, "unban", moderator_id=interaction.user.id)
            await interaction.response.send_message(f"✅ {user} has been unbanned.")
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found!", ephemeral=True)

    @app_commands.command(name="warnings", description="View warnings for a user")
    @app_commands.describe(member="User to check (default: yourself)")
    async def get_warnings(self, interaction: discord.Interaction, member: discord.Member = None):
        """Get warning count for a user."""
        if member is None:
            member = interaction.user

        warning_count = self.db.get_warnings(member.id, interaction.guild.id)
        logs = self.db.get_user_logs(member.id, interaction.guild.id, 5)

        embed = discord.Embed(
            title=f"📋 Warnings for {member}",
            description=f"Total warnings: {warning_count}/3",
            color=discord.Color.orange()
        )

        if logs:
            log_text = ""
            for log in logs:
                action, reason, timestamp = log
                log_text += f"**{action.upper()}** - {reason}\n"
            embed.add_field(name="Recent Actions", value=log_text or "None")
        else:
            embed.add_field(name="Recent Actions", value="No moderation history")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="modlog", description="View moderation log for a user")
    @app_commands.describe(member="User to check")
    async def modlog(self, interaction: discord.Interaction, member: discord.Member):
        """View moderation log for a user."""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        logs = self.db.get_user_logs(member.id, interaction.guild.id, 10)

        embed = discord.Embed(
            title=f"📜 Moderation Log - {member}",
            color=discord.Color.blue()
        )

        if logs:
            for i, log in enumerate(logs, 1):
                action, reason, timestamp = log
                embed.add_field(
                    name=f"{i}. {action.upper()}",
                    value=f"**Reason:** {reason}\n**Time:** {timestamp}",
                    inline=False
                )
        else:
            embed.description = "No moderation history for this user."

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
