"""Verification system cog."""
import discord
from discord.ext import commands
from discord import app_commands
import random
from database import Database
from config import UNVERIFIED_ROLE_ID, VERIFIED_ROLE_ID

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        self.verification_codes = {}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle new member join."""
        self.db.add_user(member.id, member.guild.id)

        # Assign Unverified role
        try:
            unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
            if unverified_role:
                await member.add_roles(unverified_role)
        except Exception as e:
            print(f"[ERROR] Failed to assign Unverified role: {e}")

        embed = discord.Embed(
            title="👋 Welcome to the Server!",
            description=f"Welcome {member.mention}! To access the server, you must verify yourself.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="How to Verify",
            value="Use `/verify` to begin verification.",
            inline=False
        )

        try:
            welcome_msg = await member.send(embed=embed)
            await welcome_msg.add_reaction("✅")
        except:
            pass

    @app_commands.command(name="verify", description="Start verification process")
    async def verify(self, interaction: discord.Interaction):
        """Start verification process."""
        if self.db.is_verified(interaction.user.id, interaction.guild.id):
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        # Generate verification code
        code = random.randint(1000, 9999)
        self.verification_codes[interaction.user.id] = code

        embed = discord.Embed(
            title="🔐 Verification",
            description="Please reply in the verification channel with the code shown below:",
            color=discord.Color.blue()
        )
        embed.add_field(name="Code", value=f"```{code}```", inline=False)
        embed.set_footer(text="You have 5 minutes to complete verification.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Wait for response
        def check(msg):
            return msg.author == interaction.user and msg.guild == interaction.guild

        try:
            response = await self.bot.wait_for("message", check=check, timeout=300)
            if response.content == str(code):
                self.db.verify_user(interaction.user.id, interaction.guild.id)
                self.verification_codes.pop(interaction.user.id, None)

                # Remove Unverified role and add Verified role
                try:
                    unverified_role = interaction.guild.get_role(UNVERIFIED_ROLE_ID)
                    verified_role = interaction.guild.get_role(VERIFIED_ROLE_ID)
                    
                    member = interaction.guild.get_member(interaction.user.id)
                    if member:
                        if unverified_role:
                            await member.remove_roles(unverified_role)
                        if verified_role:
                            await member.add_roles(verified_role)
                except Exception as e:
                    print(f"[ERROR] Failed to update roles: {e}")

                embed = discord.Embed(
                    title="✅ Verification Complete",
                    description="You have been successfully verified! You now have access to all channels.",
                    color=discord.Color.green()
                )
                await response.reply(embed=embed, delete_after=10)
            else:
                await response.reply("❌ Incorrect code. Please try again with `/verify`", delete_after=10)
                self.verification_codes.pop(interaction.user.id, None)
        except:
            await interaction.followup.send("❌ Verification timed out. Use `/verify` to try again.", ephemeral=True)
            self.verification_codes.pop(interaction.user.id, None)

    @app_commands.command(name="verified", description="Check if a user is verified")
    @app_commands.describe(member="User to check (default: yourself)")
    async def check_verified(self, interaction: discord.Interaction, member: discord.Member = None):
        """Check if a user is verified."""
        if member is None:
            member = interaction.user

        is_verified = self.db.is_verified(member.id, interaction.guild.id)
        status = "✅ Verified" if is_verified else "❌ Not Verified"

        embed = discord.Embed(
            title=f"Verification Status - {member}",
            description=status,
            color=discord.Color.green() if is_verified else discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="verificationsetup", description="Setup verification channel (Admin only)")
    @app_commands.describe(channel="Channel where users verify")
    async def verification_setup(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Setup verification channel."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command!", ephemeral=True)
            return

        if channel is None:
            channel = interaction.channel

        self.db.set_verification_channel(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="✅ Verification Setup",
            description=f"Verification channel has been set to {channel.mention}",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Instructions",
            value="Users will now verify in that channel when they use `/verify`",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

        # Send a verification info message to the channel
        info_embed = discord.Embed(
            title="🔐 Verification Channel",
            description="This is the verification channel. Use `/verify` to verify yourself!",
            color=discord.Color.blue()
        )
        info_embed.add_field(
            name="Steps",
            value="1. Type `/verify`\n2. Copy the code from the message\n3. Paste the code here\n4. You're verified! ✅",
            inline=False
        )
        try:
            await channel.send(embed=info_embed)
        except:
            pass

async def setup(bot):
    await bot.add_cog(Verification(bot))
