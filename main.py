"""Discord Moderation Bot - Main Entry Point"""
import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# Resolve project root before any relative imports/paths (fixes Railway cwd issues)
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)


def start_health_server():
    """Keep Railway happy by listening on PORT (prevents restart loops)."""
    port = int(os.getenv("PORT", "8080"))

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format, *args):
            return

    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server listening on 0.0.0.0:{port}")


async def sync_slash_commands():
    """Register slash commands with Discord."""
    guild_id = os.getenv("DISCORD_GUILD_ID")
    try:
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} guild command(s) to guild {guild_id}")
        else:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} global command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}", exc_info=True)
        raise


async def load_cogs():
    """Load all cogs from the cogs directory."""
    cogs_dir = BASE_DIR / "cogs"
    if not cogs_dir.is_dir():
        logger.error(f"Cogs directory not found: {cogs_dir}")
        return

    for path in sorted(cogs_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        extension = f"cogs.{path.stem}"
        try:
            await bot.load_extension(extension)
            logger.info(f"Loaded cog: {path.name}")
        except Exception as e:
            logger.error(f"Failed to load cog {path.name}: {e}", exc_info=True)


@bot.event
async def setup_hook():
    """Load extensions and sync commands before connecting to Discord."""
    await load_cogs()
    await sync_slash_commands()


@bot.event
async def on_ready():
    """Called when bot is ready."""
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the server | /help",
        )
    )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Log slash command failures so Railway logs show the real issue."""
    logger.error("Slash command error: %s", error, exc_info=error)

    if isinstance(error, app_commands.CommandInvokeError) and error.original:
        error = error.original

    message = "An error occurred while running this command."
    if isinstance(error, app_commands.CommandOnCooldown):
        message = f"Command on cooldown. Try again in {error.retry_after:.0f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        message = "You do not have permission to use this command."
    elif isinstance(error, discord.Forbidden):
        message = "I lack permission for that action. Check my role and permissions."
    elif isinstance(error, discord.HTTPException):
        message = f"Discord error: {error.text or 'request failed'}"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when bot joins a new guild."""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    if guild.system_channel:
        embed = discord.Embed(
            title="Universal Moderation Bot",
            description="Thank you for inviting me! I'm here to help moderate your server.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Features",
            value="Moderation, verification, activity logging, and audit logs",
            inline=False,
        )
        embed.add_field(
            name="Get Started",
            value="Type `/help` to see available commands.",
            inline=False,
        )
        try:
            await guild.system_channel.send(embed=embed)
        except discord.HTTPException:
            pass


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Called when bot leaves a guild."""
    logger.info(f"Left guild: {guild.name} (ID: {guild.id})")


@bot.event
async def on_command_error(ctx, error):
    """Handle prefix command errors (slash commands use on_app_command_error)."""
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="Permission Denied",
            description="You don't have permission to use this command.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="Missing Argument",
            description=f"Missing required argument: {error.param.name}",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="Bad Argument",
            description=str(error),
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
    else:
        logger.error(f"Command error: {error}")
        embed = discord.Embed(
            title="Error",
            description="An error occurred while processing your command.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Show help information."""
    embed = discord.Embed(
        title="Universal Moderation Bot - Commands",
        description="All available slash commands:",
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="Moderation Commands",
        value="/warn - Warn a user\n"
        "/mute - Mute a user\n"
        "/unmute - Unmute a user\n"
        "/kick - Kick a user\n"
        "/ban - Ban a user\n"
        "/unban - Unban a user\n"
        "/warnings - View user warnings\n"
        "/modlog - View moderation history",
        inline=False,
    )

    embed.add_field(
        name="Verification Commands",
        value="/verify - Start verification process\n"
        "/verified - Check verification status\n"
        "/verificationsetup - Setup verification channel (Admin)",
        inline=False,
    )

    embed.add_field(
        name="Logging Commands",
        value="/logs - View activity logs\n/logsetup - Set audit log channel (Admin)",
        inline=False,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def main():
    """Start the bot."""
    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "your_token_here":
        logger.error("DISCORD_TOKEN is missing. Set it in Railway Variables or a local .env file.")
        sys.exit(1)

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    start_health_server()
    asyncio.run(main())
