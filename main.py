import discord
from discord import app_commands
from discord.ext import commands
import config
import os
import logging
import asyncio
import aiohttp
import re

# Custom logger handler for per-server logs
class GuildFileHandler(logging.Handler):
    def __init__(self, log_dir="logs"):
        super().__init__()
        self.log_dir = log_dir
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

    def emit(self, record):
        try:
            msg = self.format(record)
            if "[Guild: " in record.getMessage():
                match = re.search(r"\[Guild:\s*([^\]]+)\]", record.getMessage())
                if match:
                    guild_name = match.group(1)
                    # Create a safe filename
                    safe_name = "".join(c for c in guild_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    if not safe_name:
                        safe_name = "unknown_guild"
                    
                    filepath = os.path.join(self.log_dir, f"{safe_name}.log")
                    with open(filepath, "a", encoding="utf-8") as f:
                        f.write(msg + "\n")
        except Exception:
            self.handleError(record)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"), 
        logging.StreamHandler(),
        GuildFileHandler("logs")
    ]
)
logger = logging.getLogger("bot")

# Bot initialization
intents = discord.Intents.default()
intents.message_content = True  # To read message content for automod
intents.guilds = True           # For guild events
intents.members = True          # For member join/leave events
intents.presences = True        # For member status
intents.messages = True         # For message events
intents.guild_messages = True   # For message logging
intents.guild_reactions = True  # For reaction events
intents.guild_typing = True     # For typing events
intents.emojis_and_stickers = True  # For server backup
intents.voice_states = True     # For voice activity tracking
intents.bans = True             # For ban logging
intents = discord.Intents.all()

# Disable the default help command
bot: commands.Bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)
bot.logger = logger  # Add logger to bot for access in cogs

async def setup_hook():
    logger.info("Running setup_hook...")
    bot.session = aiohttp.ClientSession()

    # Load cogs
    try:
        await load_extensions()
        logger.info("All extensions loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load extensions: {e}")

bot.setup_hook = setup_hook

# Bot events
@bot.event
async def on_ready():
    logger.info(f"Bot is ready! Logged in as {bot.user}")

    # Sync application commands (slash commands)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} application commands")
    except Exception as e:
        logger.error(f"Failed to sync application commands: {e}")
    
    # Set bot status to online with custom activity
    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name=config.BOT_STATUS)
        )
        logger.info(f"Bot status set to: {config.BOT_STATUS}")
    except Exception as e:
        logger.error(f"Failed to set presence: {e}")

@bot.event
async def on_command_completion(ctx):
    if ctx.guild:
        logger.info(f"[Guild: {ctx.guild.name}] Command '{ctx.command.name}' executed by {ctx.author} in #{ctx.channel.name}")
    else:
        logger.info(f"[Guild: DMs] Command '{ctx.command.name}' executed by {ctx.author}")

@bot.event
async def on_app_command_completion(interaction: discord.Interaction, command: discord.app_commands.Command | discord.app_commands.ContextMenu):
    guild_name = interaction.guild.name if interaction.guild else "DMs"
    channel_name = interaction.channel.name if hasattr(interaction.channel, 'name') else "DMs"
    logger.info(f"[Guild: {guild_name}] Slash command '{command.name}' executed by {interaction.user} in #{channel_name}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")

# Slash command error handler
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        logger.error(f"Slash command not found: {error}")
        if interaction.response.is_done():
            await interaction.followup.send("Slash command not found.", ephemeral=True)
        else:
            await interaction.response.send_message("Slash command not found.", ephemeral=True)
    else:
        logger.error(f"App command error: {error}")
        if interaction.response.is_done():
            await interaction.followup.send("An error occurred.", ephemeral=True)
        else:
            await interaction.response.send_message("An error occurred.", ephemeral=True)

# Extension loading
async def load_extensions():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                logger.info(f"Loaded extension: {filename}")
            except Exception as e:
                logger.error(f"Failed to load extension {filename}: {e}")

# Run the bot
def run_bot():
    bot.run(config.TOKEN, log_handler=None)

if __name__ == "__main__":
    run_bot()