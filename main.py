"""Discord Moderation Bot - Main Entry Point"""
import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
import logging

# Load environment variables
load_dotenv()

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

@bot.event
async def on_ready():
    """Called when bot is ready."""
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    logger.info(f"✅ Bot is ready! Logged in as {bot.user}")
    logger.info(f"📊 Connected to {len(bot.guilds)} guild(s)")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the server | /help"
        )
    )

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when bot joins a new guild."""
    logger.info(f"✅ Joined new guild: {guild.name} (ID: {guild.id})")
    
    # Try to send a welcome message
    if guild.system_channel:
        embed = discord.Embed(
            title="🤖 Universal Moderation Bot",
            description="Thank you for inviting me! I'm here to help moderate your server.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Features",
            value="• Moderation (warn, mute, kick, ban)\n• Verification system\n• Activity logging\n• Audit logs",
            inline=False
        )
        embed.add_field(
            name="Get Started",
            value="Type `/help` to see available commands.",
            inline=False
        )
        try:
            await guild.system_channel.send(embed=embed)
        except:
            pass

@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Called when bot leaves a guild."""
    logger.info(f"❌ Left guild: {guild.name} (ID: {guild.id})")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You don't have permission to use this command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Missing required argument: {error.param.name}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ Bad Argument",
            description=str(error),
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        logger.error(f"Command error: {error}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while processing your command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    """Show help information."""
    embed = discord.Embed(
        title="🤖 Universal Moderation Bot - Commands",
        description="All available slash commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Moderation Commands",
        value="/warn - Warn a user\n"
              "/mute - Mute a user\n"
              "/unmute - Unmute a user\n"
              "/kick - Kick a user\n"
              "/ban - Ban a user\n"
              "/unban - Unban a user\n"
              "/warnings - View user warnings\n"
              "/modlog - View moderation history",
        inline=False
    )
    
    embed.add_field(
        name="✅ Verification Commands",
        value="/verify - Start verification process\n"
              "/verified - Check verification status\n"
              "/verificationsetup - Setup verification channel (Admin)",
        inline=False
    )
    
    embed.add_field(
        name="📊 Logging Commands",
        value="/logs - View activity logs",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def load_cogs():
    """Load all cogs from the cogs directory."""
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"✅ Loaded cog: {filename}")
            except Exception as e:
                logger.error(f"❌ Failed to load cog {filename}: {e}")

async def main():
    """Start the bot."""
    async with bot:
        # Load cogs
        await load_cogs()

        # Get token
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logger.error("❌ DISCORD_TOKEN not found in .env file!")
            return

        # Start bot
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
