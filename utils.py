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
    
    def decorator(func):
        # Tag the function or command object so command_help can see it
        actual_func = getattr(func, "callback", func)
        actual_func.__requires_owner__ = True
        return commands.check(predicate)(func)
    return decorator

def mod_only():
    """Decorator that restricts command usage to server moderators or bot owner."""
    async def predicate(ctx):
        if ctx.author.id == config.OWNER_ID:
            return True
        if not ctx.guild:
            return False
        return any(role.id in config.MOD_ROLES for role in ctx.author.roles)
        
    def decorator(func):
        # Tag the function or command object so command_help can see it
        actual_func = getattr(func, "callback", func)
        actual_func.__requires_mod__ = True
        return commands.check(predicate)(func)
    return decorator

# Help formatting utilities
class HelpInfo:
    """Class to store and manage command help information."""
    _commands = {}
    
    @classmethod
    def add_command(cls, category, name, description, usage=None, examples=None, note=None, requires_mod=False, requires_owner=False):
        """Register a command's help information."""
        if category not in cls._commands:
            cls._commands[category] = []
        cls._commands[category].append({
            "name": name,
            "description": description,
            "usage": usage,
            "examples": examples or [],
            "note": note,
            "requires_mod": requires_mod,
            "requires_owner": requires_owner
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
    """Decorator to add help documentation to a command."""
    def decorator(func):
        # If this is a command object (like HybridCommand), get its callback
        actual_func = getattr(func, "callback", func)

        cmd_name = getattr(actual_func, "__name__", "unknown")
        
        # Check if the function was tagged by our permission decorators
        requires_mod = getattr(actual_func, "__requires_mod__", False)
        requires_owner = getattr(actual_func, "__requires_owner__", False)

        HelpInfo.add_command(
            category, cmd_name, description, usage, examples, note,
            requires_mod=requires_mod, requires_owner=requires_owner
        )

        # Store help info on the actual callable
        actual_func.help_info = {
            "category": category,
            "name": cmd_name,
            "description": description,
            "usage": usage,
            "examples": examples or [],
            "note": note,
            "requires_mod": requires_mod,
            "requires_owner": requires_owner
        }

        @functools.wraps(actual_func)
        async def wrapper(*args, **kwargs):
            return await actual_func(*args, **kwargs)

        # Return the original object if it's already a command, else the wrapper
        return func if hasattr(func, "callback") else wrapper

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
