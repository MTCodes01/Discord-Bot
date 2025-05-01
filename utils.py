import discord
from discord.ext import commands
import config
import functools
import inspect

# Command permission decorators
def owner_only():
    """Decorator that restricts command usage to the bot owner only."""
    async def predicate(ctx):
        return ctx.author.id == config.OWNER_ID
    return commands.check(predicate)

def mod_only():
    """Decorator that restricts command usage to server moderators or bot owner."""
    async def predicate(ctx):
        if ctx.author.id == config.OWNER_ID:
            return True
        if not ctx.guild:
            return False
        return any(role.id in config.MOD_ROLES for role in ctx.author.roles)
    return commands.check(predicate)

# Help formatting utilities
class HelpInfo:
    """Class to store and manage command help information."""
    _commands = {
        "owner": [],
        "mod": [],
        "general": []
    }
    
    @classmethod
    def add_command(cls, category, name, description, usage=None, examples=None, note=None):
        """Register a command's help information."""
        cls._commands[category].append({
            "name": name,
            "description": description,
            "usage": usage,
            "examples": examples or [],
            "note": note
        })
    
    @classmethod
    def get_all_commands(cls):
        """Get all registered commands organized by category."""
        return cls._commands
    
    @classmethod
    def get_command_by_name(cls, name):
        """Find a command by its name."""
        for category, cmds in cls._commands.items():
            for cmd in cmds:
                if cmd["name"] == name:
                    return cmd, category
        return None, None

def command_help(category, description, usage=None, examples=None, note=None):
    """Decorator to add help documentation to a command.
    
    Args:
        category: The command category ("general", "mod", "owner")
        description: Description of what the command does
        usage: How to use the command (format and parameters)
        examples: List of example usages of the command
        note: Additional notes or warnings about the command
    """
    def decorator(func):
        cmd_name = func.__name__
        HelpInfo.add_command(category, cmd_name, description, usage, examples, note)
        
        # Store help info directly on the function for slash commands
        func.help_info = {
            "category": category,
            "name": cmd_name,
            "description": description,
            "usage": usage,
            "examples": examples or [],
            "note": note
        }
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Helper functions for creating embeds
def create_embed(title, description=None, color=config.EMBED_COLOR):
    """Create a consistent Discord embed with the bot's styling."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    return embed
