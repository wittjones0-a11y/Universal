"""Verification system cog."""
import asyncio
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot_helpers import slash_send
from config import UNVERIFIED_ROLE_ID, VERIFIED_ROLE_ID
from database import Database

logger = logging.getLogger(__name__)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.verification_codes = {}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.db.run(self.db.add_user, member.id, member.guild.id)

        try:
            unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
            if unverified_role:
                await member.add_roles(unverified_role, reason="New member — unverified")
        except discord.HTTPException as exc:
            logger.warning("Failed to assign unverified role: %s", exc)

        embed = discord.Embed(
            title="Welcome",
            description=f"Welcome {member.mention}! Use `/verify` to access the server.",
            color=discord.Color.green(),
        )
        try:
            await member.send(embed=embed)
        except discord.HTTPException:
            pass

    @app_commands.command(name="verify", description="Start verification process")
    @app_commands.guild_only()
    async def verify(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        verified = await self.db.run(self.db.is_verified, user.id, guild.id)
        if verified:
            await slash_send(interaction, content="You are already verified.", ephemeral=True)
            return

        channel_id = await self.db.run(self.db.get_verification_channel, guild.id)
        channel = guild.get_channel(channel_id) if channel_id else interaction.channel

        code = random.randint(1000, 9999)
        self.verification_codes[user.id] = code

        embed = discord.Embed(
            title="Verification",
            description=f"Post this code in {channel.mention}:",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Code", value=f"```{code}```", inline=False)
        embed.set_footer(text="You have 5 minutes. Case-sensitive — numbers only.")
        await slash_send(interaction, embed=embed, ephemeral=True)

        def check(msg: discord.Message) -> bool:
            return (
                msg.author.id == user.id
                and msg.guild
                and msg.guild.id == guild.id
                and msg.channel.id == channel.id
            )

        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)
        except asyncio.TimeoutError:
            self.verification_codes.pop(user.id, None)
            await interaction.followup.send(
                "Verification timed out. Run `/verify` again.", ephemeral=True
            )
            return

        if response.content.strip() != str(code):
            self.verification_codes.pop(user.id, None)
            await response.reply(
                "Incorrect code. Run `/verify` to try again.", delete_after=15
            )
            return

        await self.db.run(self.db.verify_user, user.id, guild.id)
        self.verification_codes.pop(user.id, None)

        member = guild.get_member(user.id) or await guild.fetch_member(user.id)
        try:
            unverified = guild.get_role(UNVERIFIED_ROLE_ID)
            verified_role = guild.get_role(VERIFIED_ROLE_ID)
            if unverified and unverified in member.roles:
                await member.remove_roles(unverified, reason="Verified")
            if verified_role:
                await member.add_roles(verified_role, reason="Verified")
        except discord.HTTPException as exc:
            logger.warning("Role update after verify failed: %s", exc)

        done = discord.Embed(
            title="Verification complete",
            description="You now have access to the server.",
            color=discord.Color.green(),
        )
        await response.reply(embed=done, delete_after=30)
        await interaction.followup.send("Verified successfully.", ephemeral=True)

    @app_commands.command(name="verified", description="Check if a user is verified")
    @app_commands.describe(member="User to check")
    @app_commands.guild_only()
    async def check_verified(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        is_verified = await self.db.run(
            self.db.is_verified, member.id, interaction.guild.id
        )
        status = "Verified" if is_verified else "Not verified"
        embed = discord.Embed(
            title=f"Verification — {member.display_name}",
            description=status,
            color=discord.Color.green() if is_verified else discord.Color.red(),
        )
        await slash_send(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="verificationsetup", description="Set the verification channel (Admin)")
    @app_commands.describe(channel="Channel where users post their code")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def verification_setup(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await self.db.run(
            self.db.set_verification_channel, interaction.guild.id, channel.id
        )
        embed = discord.Embed(
            title="Verification channel set",
            description=f"Members will verify in {channel.mention}.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="How it works",
            value="1. User runs `/verify`\n2. Bot shows a code\n3. User posts the code in this channel",
            inline=False,
        )
        await slash_send(interaction, embed=embed, ephemeral=True)

        info = discord.Embed(
            title="Verification channel",
            description="Use `/verify` here to get your access code.",
            color=discord.Color.blue(),
        )
        try:
            await channel.send(embed=info)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Verification(bot))
