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

from bot_helpers import defer_command, slash_send

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


def _tree_command_names(guild: discord.Object = None) -> list[str]:
    return sorted(cmd.name for cmd in bot.tree.get_commands(guild=guild))


async def sync_slash_commands():
    """Register slash commands with Discord."""
    if os.getenv("SYNC_COMMANDS", "true").lower() not in ("1", "true", "yes"):
        logger.info("SYNC_COMMANDS disabled — skipping command sync")
        return

    local_commands = _tree_command_names()
    logger.info("Local command tree has %s command(s): %s", len(local_commands), local_commands)

    expected = {
        "help", "ping", "warn", "mute", "unmute", "kick", "ban", "unban", "warnings", "modlog",
        "role_add", "verify", "verified", "verificationsetup", "logs", "logsetup", "botstatus",
    }
    missing = expected - set(local_commands)
    if missing:
        logger.error("Missing commands in tree: %s", sorted(missing))

    from config import DISCORD_GUILD_ID as guild_id_cfg
    guild_id = os.getenv("DISCORD_GUILD_ID") or guild_id_cfg
    try:
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            commands = list(bot.tree.get_commands())
            bot.tree.clear_commands(guild=None)
            cleared_global = await bot.tree.sync()
            logger.info(
                "Cleared %s global command(s) to prevent duplicates",
                len(cleared_global),
            )
            bot.tree.clear_commands(guild=guild)
            cleared_guild = await bot.tree.sync(guild=guild)
            logger.info(
                "Cleared %s guild command(s) from %s to remove cached duplicates",
                len(cleared_guild),
                guild_id,
            )
            for command in commands:
                bot.tree.add_command(command)
            bot.tree.copy_global_to(guild=guild)
            guild_synced = await bot.tree.sync(guild=guild)
            logger.info(
                "Synced %s guild command(s) to %s: %s",
                len(guild_synced),
                guild_id,
                sorted(cmd.name for cmd in guild_synced),
            )
        else:
            synced = await bot.tree.sync()
            logger.info(
                "Synced %s global command(s): %s",
                len(synced),
                sorted(cmd.name for cmd in synced),
            )
    except discord.HTTPException as e:
        logger.error("Failed to sync commands (HTTP %s): %s", e.status, e.text, exc_info=True)
        raise
    except Exception as e:
        logger.error("Failed to sync commands: %s", e, exc_info=True)
        raise


async def load_cogs():
    """Load all cogs from the cogs directory."""
    cogs_dir = BASE_DIR / "cogs"
    if not cogs_dir.is_dir():
        raise RuntimeError(f"Cogs directory not found: {cogs_dir}")

    failed = []
    for path in sorted(cogs_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        extension = f"cogs.{path.stem}"
        try:
            await bot.load_extension(extension)
            logger.info("Loaded cog: %s", path.name)
        except Exception as e:
            logger.error("Failed to load cog %s: %s", path.name, e, exc_info=True)
            failed.append(path.name)

    if failed:
        raise RuntimeError(f"Failed to load cogs: {', '.join(failed)}")

    expected = {
        "help", "ping", "warn", "mute", "unmute", "kick", "ban", "unban",
        "warnings", "modlog", "role_add", "verify", "verified", "verificationsetup",
        "logs", "logsetup", "botstatus",
    }
    registered = set(_tree_command_names())
    missing = expected - registered
    if missing:
        raise RuntimeError(f"Commands failed to register: {sorted(missing)}")
    logger.info("All %s commands registered", len(expected))


@bot.tree.interaction_check
async def defer_all_slash_commands(interaction: discord.Interaction) -> bool:
    """Acknowledge every slash command within 3 seconds before handler code runs."""
    if interaction.type != discord.InteractionType.application_command:
        return True
    return await defer_command(interaction)


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        name = interaction.data.get("name", "?") if interaction.data else "?"
        logger.info(
            "Interaction /%s from %s in guild %s",
            name,
            interaction.user,
            interaction.guild_id,
        )


@bot.event
async def setup_hook():
    """Load extensions before connecting to Discord."""
    await load_cogs()


_commands_synced = False


@bot.event
async def on_ready():
    """Called when bot is ready."""
    global _commands_synced
    logger.info("Bot is ready! Logged in as %s", bot.user)
    logger.info("Connected to %s guild(s)", len(bot.guilds))

    if not _commands_synced:
        try:
            await sync_slash_commands()
            _commands_synced = True
        except Exception as e:
            logger.error("Command sync failed on ready: %s", e, exc_info=True)

    from config import DISCORD_GUILD_ID as guild_id_cfg
    guild_id = os.getenv("DISCORD_GUILD_ID") or guild_id_cfg
    if guild_id:
        target = int(guild_id)
        in_guild = bot.get_guild(target)
        if in_guild:
            me = in_guild.me
            perms = me.guild_permissions if me else None
            logger.info(
                "Guild sync target %s (%s) — bot perms: kick=%s ban=%s timeout=%s",
                in_guild.name,
                target,
                perms.kick_members if perms else "?",
                perms.ban_members if perms else "?",
                perms.moderate_members if perms else "?",
            )
        else:
            logger.error(
                "DISCORD_GUILD_ID=%s but the bot is NOT in that server. "
                "Fix the variable or invite the bot. Your servers: %s",
                target,
                [(g.name, g.id) for g in bot.guilds],
            )

    for guild in bot.guilds:
        me = guild.me
        if not me:
            continue
        if me.guild_permissions.moderate_members:
            logger.info("OK %s — can moderate", guild.name)
        else:
            logger.warning(
                "NO MOD PERMS in %s — enable Moderate/Kick/Ban on bot role",
                guild.name,
            )

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
        await slash_send(interaction, content=message, ephemeral=True)
    except discord.HTTPException:
        pass


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when bot joins a new guild."""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")

    if guild.system_channel:
        embed = discord.Embed(
            title="🤖 Universal Bot",
            description=f"Thank you for inviting me to **{guild.name}**! I'm here to help moderate your server.",
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="🛡️ Features",
            value="• Moderation (warn, mute, kick, ban)\n• Roblox verification system\n• Activity logging\n• Role management",
            inline=False,
        )
        embed.add_field(
            name="🚀 Get Started",
            value="Use `/help` to see all commands\nUse `/verificationsetup` to configure verification",
            inline=False,
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text=f"Bot ID: {bot.user.id}")
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
            title="🚫 Permission Denied",
            description="You don't have the required permissions to use this command.",
            color=discord.Color.from_rgb(237, 66, 69),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Contact a server administrator if you need access")
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="⚠️ Missing Argument",
            description=f"Missing required argument: `{error.param.name}`",
            color=discord.Color.from_rgb(255, 183, 77),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=f"Use {ctx.prefix}help {ctx.command} for usage info")
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="⚠️ Invalid Argument",
            description=str(error),
            color=discord.Color.from_rgb(255, 183, 77),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="Check your input and try again")
        await ctx.send(embed=embed)
    else:
        logger.error(f"Command error: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An unexpected error occurred while processing your command.",
            color=discord.Color.from_rgb(237, 66, 69),
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text="The error has been logged for review")
        await ctx.send(embed=embed)


@bot.tree.command(name="ping", description="Test if the bot responds to slash commands")
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)

    # Determine status color based on latency
    if latency_ms < 100:
        status_color = discord.Color.from_rgb(87, 242, 135)  # Green
        status_text = "🟢 Excellent"
    elif latency_ms < 200:
        status_color = discord.Color.from_rgb(255, 183, 77)  # Yellow
        status_text = "🟡 Good"
    else:
        status_color = discord.Color.from_rgb(237, 66, 69)  # Red
        status_text = "🔴 High"

    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"The bot is online and responding.",
        color=status_color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="📡 Latency", value=f"`{latency_ms}ms`", inline=True)
    embed.add_field(name="📊 Status", value=status_text, inline=True)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text=f"{bot.user.name} v1.0")
    await slash_send(interaction, embed=embed, ephemeral=True)


@bot.tree.command(name="botstatus", description="Show bot diagnostics (admin)")
@app_commands.default_permissions(administrator=True)
async def botstatus(interaction: discord.Interaction):
    """Help debug Railway / permission / command issues."""
    if not interaction.guild:
        await slash_send(interaction, content="Use this in a server.", ephemeral=True)
        return

    guild = interaction.guild
    me = guild.me
    perms = me.guild_permissions if me else None
    from config import DISCORD_GUILD_ID as configured_guild

    lines = [
        f"**Server:** {guild.name}",
        f"**Server ID:** `{guild.id}`",
        f"**DISCORD_GUILD_ID:** `{configured_guild}`",
        f"**Bot role:** {me.top_role.name if me else 'unknown'} (position {me.top_role.position if me else '?'})",
    ]
    if perms:
        lines.append(
            "**Bot permissions:** "
            f"Timeout={perms.moderate_members} "
            f"Kick={perms.kick_members} "
            f"Ban={perms.ban_members}"
        )
    if str(guild.id) != str(configured_guild) and configured_guild != "(not set)":
        lines.append(
            "⚠️ **DISCORD_GUILD_ID does not match this server.** "
            "Set it to the Server ID above in Railway Variables, then redeploy."
        )

    tree_names = _tree_command_names()
    mod_cmds = [c for c in tree_names if c in ("warn", "mute", "kick", "ban", "unmute", "unban", "warnings", "modlog")]
    lines.append(f"**Moderation commands loaded:** {len(mod_cmds)}/8 — {', '.join(f'`/{c}`' for c in mod_cmds)}")

    embed = discord.Embed(
        title="🤖 Bot Diagnostics",
        description="\n".join(lines),
        color=discord.Color.from_rgb(88, 101, 242),
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="After changing Railway variables, redeploy and wait ~30s")
    await slash_send(interaction, embed=embed, ephemeral=True)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Show help information."""
    embed = discord.Embed(
        title="📚 Universal Bot Commands",
        description=f"**{len(bot.tree.get_commands())} commands available**\nUse `/` to see command options with autocompletion.",
        color=discord.Color.from_rgb(88, 101, 242),
        timestamp=datetime.utcnow(),
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(
        name="🛡️ Moderation",
        value="`/warn` — Warn a member\n"
        "`/mute` — Timeout a member\n"
        "`/unmute` — Remove a timeout\n"
        "`/kick` — Kick a member\n"
        "`/ban` — Ban a member\n"
        "`/unban` — Unban by user ID\n"
        "`/warnings` — View warning count\n"
        "`/modlog` — View moderation history\n"
        "`/role_add` — Add a role to a member",
        inline=True,
    )

    embed.add_field(
        name="✅ Verification",
        value="`/verify` — Start Roblox verification\n"
        "`/verified` — Check verification status\n"
        "`/verificationsetup` — Set verification channel",
        inline=True,
    )

    embed.add_field(
        name="📜 Logging",
        value="`/logs` — View message activity\n"
        "`/logsetup` — Set audit log channel",
        inline=True,
    )

    embed.add_field(
        name="⚙️ Utilities",
        value="`/ping` — Check bot latency\n"
        "`/botstatus` — View bot diagnostics\n"
        "`/help` — Show this help message",
        inline=True,
    )

    embed.add_field(
        name="📖 Quick Tips",
        value="• Most moderation commands require `Moderate Members` permission\n"
        "• Verification links Discord accounts to Roblox usernames\n"
        "• Use `/botstatus` to check bot diagnostics",
        inline=False,
    )

    embed.set_footer(text=f"{bot.user.name} • Type / to start using commands", icon_url=bot.user.display_avatar.url)

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
