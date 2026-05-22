"""Activity logging cog."""
import discord
from discord.ext import commands
from discord import app_commands
from database import Database

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Log messages from non-bot users."""
        if message.author.bot or not message.guild:
            return

        # Don't log bot commands (slash commands don't trigger message events)
        if message.content.startswith("/"):
            return

        self.db.add_user(message.author.id, message.guild.id)
        self.db.log_message(
            message.author.id,
            message.guild.id,
            message.channel.id,
            message.id,
            message.content
        )

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages."""
        if message.author.bot or not message.guild:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"**Author:** {message.author}\n**Content:** {message.content}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channel", value=message.channel.mention)
        embed.set_footer(text=f"User ID: {message.author.id}")

        print(f"[AUDIT] Message deleted by {message.author}: {message.content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages."""
        if before.author.bot or not before.guild:
            return

        if before.content == after.content:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"**Author:** {before.author}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Before", value=before.content or "No content", inline=False)
        embed.add_field(name="After", value=after.content or "No content", inline=False)
        embed.add_field(name="Channel", value=before.channel.mention)
        embed.set_footer(text=f"User ID: {before.author.id}")

        print(f"[AUDIT] Message edited by {before.author}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member updates (roles, nicknames, etc)."""
        if before.guild is None:
            return

        # Check for nickname change
        if before.nick != after.nick:
            print(f"[AUDIT] {after} nickname changed from '{before.nick}' to '{after.nick}'")

        # Check for role changes
        if before.roles != after.roles:
            added_roles = [role for role in after.roles if role not in before.roles]
            removed_roles = [role for role in before.roles if role not in after.roles]

            if added_roles:
                print(f"[AUDIT] {after} gained roles: {', '.join([r.name for r in added_roles])}")

            if removed_roles:
                print(f"[AUDIT] {after} lost roles: {', '.join([r.name for r in removed_roles])}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Log member leaving."""
        print(f"[AUDIT] {member} left the server")

    @app_commands.command(name="logs", description="View activity logs")
    @app_commands.describe(member="User to check")
    async def view_logs(self, interaction: discord.Interaction, member: discord.Member = None):
        """View message logs for a user."""
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
            return

        # Defer reply to avoid "The application did not respond" timeout
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            # already responded or deferred
            pass

        if member is None:
            member = interaction.user

        # Fetch recent message logs from the database
        logs = self.db.get_message_logs(member.id, interaction.guild.id, limit=10)

        embed = discord.Embed(
            title=f"📨 Activity Logs - {member}",
            color=discord.Color.blue()
        )

        if logs:
            for i, row in enumerate(logs, 1):
                channel_id = row[0]
                content = row[1] or "(no content)"
                timestamp = row[2]
                # Truncate content for embed
                short = content if len(content) <= 190 else content[:187] + "..."
                try:
                    channel = interaction.guild.get_channel(channel_id)
                    channel_name = channel.mention if channel else f"Channel ID {channel_id}"
                except:
                    channel_name = f"Channel ID {channel_id}"

                embed.add_field(
                    name=f"{i}. {channel_name}",
                    value=f"{short}\n*{timestamp}*",
                    inline=False
                )
        else:
            embed.description = "No message logs found for this user."

        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            # fall back to send_message if followup fails
            try:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"[ERROR] Failed to send logs response: {e}")

    @app_commands.command(name="logsetup", description="Setup a channel for audit logs (Admin only)")
    @app_commands.describe(channel="Channel to receive audit logs")
    async def log_setup(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Wrapper for backwards-compatible command. Calls internal implementation."""
        await self._do_log_setup(interaction, channel)

    async def _do_log_setup(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Set the guild log channel where audit messages will be sent."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator to use this command!", ephemeral=True)
            return

        # Defer immediately to avoid timeouts
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass

        if channel is None:
            channel = interaction.channel

        try:
            self.db.set_log_channel(interaction.guild.id, channel.id)

            embed = discord.Embed(
                title="✅ Log Channel Set",
                description=f"Audit log channel has been set to {channel.mention}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                info = discord.Embed(
                    title="📌 Audit Logging Enabled",
                    description="I'll post moderation and audit logs here.",
                    color=discord.Color.blue()
                )
                await channel.send(embed=info)
            except Exception as e:
                print(f"[ERROR] Failed to send test message to log channel: {e}")
        except Exception as e:
            print(f"[ERROR] Failed during log setup: {e}")
            try:
                await interaction.followup.send(f"❌ Failed to set log channel: {e}", ephemeral=True)
            except Exception:
                pass

    # Backwards-compatible alias for older command name
    @app_commands.command(name="setuplogs", description="(alias) Setup a channel for audit logs (Admin only)")
    @app_commands.describe(channel="Channel to receive audit logs")
    async def setuplogs(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await self._do_log_setup(interaction, channel)

async def setup(bot):
    await bot.add_cog(Logging(bot))
