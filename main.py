import discord
from discord.ext import commands
import config
import os
import logging
import asyncio

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger("bot")

# Bot initialization
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True  # For member status updates
# Enable all intents for complete access
intents = discord.Intents.all()

# Disable the default help command
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents, help_command=None)

# Bot events
@bot.event
async def on_ready():
    logger.info(f"Bot is ready! Logged in as {bot.user}")
    
    # Load cogs
    try:
        await load_extensions()
        logger.info("All extensions loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load extensions: {e}")

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
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
    else:
        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")

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