"""Verification system cog."""
import asyncio
import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

from bot_helpers import slash_send
from config import UNVERIFIED_ROLE_ID, VERIFIED_ROLE_ID
from database import Database

logger = logging.getLogger(__name__)


class RobloxUsernameModal(Modal, title='🎮 Roblox Verification'):
    roblox_username = TextInput(label='Roblox Username', placeholder='Enter your Roblox username', required=True, max_length=50, min_length=3)

    def __init__(self, verification_cog):
        super().__init__()
        self.verification_cog = verification_cog

    async def on_submit(self, interaction: discord.Interaction):
        roblox_username = self.roblox_username.value.strip()
        await self.verification_cog.start_verification_with_roblox(interaction, roblox_username)


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.verification_codes = {}
        self.pending_roblox_usernames = {}

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
            title="👋 Welcome to the Server!",
            description=f"Hey {member.mention}! We're excited to have you here.\n\nTo get started and unlock all channels, please complete the verification process by using the `/verify` command.",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(
            name="📝 Quick Start",
            value="1. Use `/verify` in any channel\n2. Enter your Roblox username\n3. Post the verification code in the designated channel",
            inline=False
        )
        embed.set_footer(text="Need help? Contact a staff member.")
        try:
            await member.send(embed=embed)
        except discord.HTTPException:
            pass

    async def start_verification_with_roblox(self, interaction: discord.Interaction, roblox_username: str):
        guild = interaction.guild
        user = interaction.user

        channel_id = await self.db.run(self.db.get_verification_channel, guild.id)
        channel = guild.get_channel(channel_id) if channel_id else interaction.channel

        code = random.randint(1000, 9999)
        self.verification_codes[user.id] = code
        self.pending_roblox_usernames[user.id] = roblox_username

        embed = discord.Embed(
            title="🔐 Your Verification Code",
            description=f"Please post the code below in {channel.mention} to complete your verification.",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(
            name="🎯 Your Code",
            value=f"```\n{code}\n```",
            inline=False
        )
        embed.add_field(
            name="📋 Roblox Username",
            value=f"```\n{roblox_username}\n```",
            inline=False
        )
        embed.add_field(
            name="⏰ Time Limit",
            value="You have 5 minutes to complete verification.",
            inline=False
        )
        embed.set_footer(text="Make sure to enter the code exactly as shown - numbers only!")
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
            self.pending_roblox_usernames.pop(user.id, None)
            embed = discord.Embed(
                title="⏰ Verification Timed Out",
                description="The verification process has timed out. Please run `/verify` again to start a new verification.",
                color=discord.Color.from_rgb(237, 66, 69),
            )
            embed.set_footer(text="You have 5 minutes to complete verification")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if response.content.strip() != str(code):
            self.verification_codes.pop(user.id, None)
            self.pending_roblox_usernames.pop(user.id, None)
            embed = discord.Embed(
                title="❌ Incorrect Code",
                description="The code you entered was incorrect. Please run `/verify` to try again with a new code.",
                color=discord.Color.from_rgb(237, 66, 69),
            )
            embed.set_footer(text="Make sure to enter the code exactly as shown")
            await response.reply(embed=embed, delete_after=15)
            return

        await self.db.run(self.db.verify_user, user.id, guild.id)
        self.verification_codes.pop(user.id, None)
        roblox_name = self.pending_roblox_usernames.pop(user.id, None)

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

        new_nickname = f"{member.name} ({roblox_name})"
        try:
            await member.edit(nick=new_nickname, reason="Verified - added Roblox username")
        except discord.HTTPException as exc:
            logger.warning("Failed to update nickname after verify: %s", exc)

        done = discord.Embed(
            title="✅ Verification Complete!",
            description=f"Congratulations {member.mention}! You now have full access to the server.",
            color=discord.Color.from_rgb(87, 242, 135),
        )
        done.add_field(
            name="🎮 Roblox Username",
            value=roblox_name,
            inline=True
        )
        done.add_field(
            name="🏷️ New Nickname",
            value=new_nickname,
            inline=True
        )
        done.add_field(
            name="🎉 Next Steps",
            value="Check out the channels and introduce yourself!",
            inline=False
        )
        done.set_footer(text="Welcome to the community!")
        await response.reply(embed=done, delete_after=30)
        embed = discord.Embed(
            title="✅ Verification Successful",
            description="You have been successfully verified and your nickname has been updated!",
            color=discord.Color.from_rgb(87, 242, 135),
        )
        embed.add_field(
            name="🏷️ Your New Nickname",
            value=new_nickname,
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="verify", description="Start verification process")
    @app_commands.guild_only()
    async def verify(self, interaction: discord.Interaction):
        guild = interaction.guild
        user = interaction.user

        verified = await self.db.run(self.db.is_verified, user.id, guild.id)
        if verified:
            embed = discord.Embed(
                title="✅ Already Verified",
                description="You have already completed the verification process and have full access to the server!",
                color=discord.Color.from_rgb(87, 242, 135),
            )
            await slash_send(interaction, embed=embed, ephemeral=True)
            return

        await interaction.response.send_modal(RobloxUsernameModal(self))

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
            title=f"{'✅' if is_verified else '❌'} Verification Status — {member.display_name}",
            description=f"**Status:** {status}\n\n**User ID:** `{member.id}`\n**Joined:** {member.joined_at.strftime('%B %d, %Y') if member.joined_at else 'N/A'}",
            color=discord.Color.from_rgb(87, 242, 135) if is_verified else discord.Color.from_rgb(237, 66, 69),
        )
        if is_verified:
            embed.add_field(
                name="🎮 Roblox Account",
                value=f"Linked to Roblox username",
                inline=False
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
            title="⚙️ Verification Channel Configured",
            description=f"The verification system has been set up successfully!\n\nMembers will now verify in {channel.mention}.",
            color=discord.Color.from_rgb(87, 242, 135),
        )
        embed.add_field(
            name="📋 How It Works",
            value="1. User runs `/verify` command\n2. Bot asks for their Roblox username\n3. Bot generates a unique verification code\n4. User posts the code in this channel\n5. Bot verifies and renames them to `Discord (Roblox)`",
            inline=False
        )
        embed.add_field(
            name="🔧 Settings",
            value=f"Channel: {channel.mention}\nServer: {interaction.guild.name}",
            inline=False
        )
        embed.set_footer(text="Verification system is now active!")
        await slash_send(interaction, embed=embed, ephemeral=True)

        info = discord.Embed(
            title="🔐 Verification Channel",
            description="This is the designated verification channel. Please use `/verify` in any server channel to start the verification process, then post your code here.",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        info.add_field(
            name="📝 Instructions",
            value="1. Run `/verify` anywhere in the server\n2. Enter your Roblox username when prompted\n3. Copy the verification code you receive\n4. Paste the code in this channel to complete verification",
            inline=False
        )
        info.set_footer(text="Staff members monitor this channel for verification codes")
        try:
            await channel.send(embed=info)
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Verification(bot))
