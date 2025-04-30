import discord
from discord.ext import commands
from discord import app_commands
import config
import asyncio
from utils import owner_only, mod_only, create_embed

class SlashCommands(commands.Cog):
    """Slash commands for the bot."""
    
    def __init__(self, bot):
        self.bot = bot
        self.commands_cog = None
        
        # Register the slash commands with the bot's command tree
        self._add_commands_to_tree()
    
    def _add_commands_to_tree(self):
        """Manually register all commands with the bot's app_commands tree."""
        self.bot.tree.add_command(self.slash_shutdown)
        self.bot.tree.add_command(self.slash_reboot)
        self.bot.tree.add_command(self.slash_help)
        self.bot.tree.add_command(self.slash_mod_command)
        self.bot.tree.add_command(self.slash_ping)
    
    async def cog_load(self):
        """Get reference to the Commands cog for command reuse."""
        await asyncio.sleep(1)  # Wait for all cogs to load
        self.commands_cog = self.bot.get_cog('Commands')
    
    # Check decorators for application commands
    def is_owner():
        """Check if the user is the bot owner."""
        async def predicate(interaction: discord.Interaction) -> bool:
            if interaction.user.id != config.OWNER_ID:
                await interaction.response.send_message("Only the bot owner can use this command!", ephemeral=True)
                return False
            return True
        return app_commands.check(predicate)
    
    def is_mod():
        """Check if the user is a moderator or the bot owner."""
        async def predicate(interaction: discord.Interaction) -> bool:
            if interaction.user.id == config.OWNER_ID:
                return True
            if not interaction.guild:
                await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
                return False
            if not any(role.id in config.MOD_ROLES for role in interaction.user.roles):
                await interaction.response.send_message("Only moderators can use this command!", ephemeral=True)
                return False
            return True
        return app_commands.check(predicate)
    
    # Core system commands
    @app_commands.command(name="shutdown", description="Shut down the bot (owner only)")
    @is_owner()
    async def slash_shutdown(self, interaction: discord.Interaction):
        """Shut down the bot completely."""
        await interaction.response.send_message("Shutting down... Goodbye!")
        await self.bot.close()
    
    @app_commands.command(name="reboot", description="Reload all cogs to update code (owner only)")
    @is_owner()
    async def slash_reboot(self, interaction: discord.Interaction):
        """Reload all cogs to implement code changes."""
        await interaction.response.defer()
        
        # Unload all cogs
        failed = False
        for extension in list(self.bot.extensions):
            try:
                await self.bot.unload_extension(extension)
            except Exception as e:
                await interaction.followup.send(f"Error unloading {extension}: {e}")
                failed = True
                break
        
        if not failed:
            # Load all cogs back
            for extension in list(self.bot.extensions):
                try:
                    await self.bot.load_extension(extension)
                except Exception as e:
                    await interaction.followup.send(f"Error loading {extension}: {e}")
                    failed = True
                    break
        
        if not failed:
            await interaction.followup.send("All cogs have been reloaded successfully!")
    
    # Help command
    @app_commands.command(name="help", description="Show help information for commands")
    @app_commands.describe(command_name="The command to get help for (optional)")
    async def slash_help(self, interaction: discord.Interaction, command_name: str = None):
        """Display help information for commands."""
        # Defer the response as the help command can take time to generate
        await interaction.response.defer()
        
        # Create a mock context for the regular help command
        class MockContext:
            def __init__(self, author, guild, send_func):
                self.author = author
                self.guild = guild
                self.send = send_func
        
        async def send_func(content=None, embed=None):
            await interaction.followup.send(content=content, embed=embed)
        
        mock_ctx = MockContext(
            author=interaction.user,
            guild=interaction.guild,
            send_func=send_func
        )
        
        # Use the regular help command logic
        if self.commands_cog:
            await self.commands_cog.help(mock_ctx, command_name)
        else:
            await interaction.followup.send("Help system is currently unavailable.")
    
    # Example commands (reusing the cog commands)
    @app_commands.command(name="mod_command", description="Example command for moderators")
    @is_mod()
    async def slash_mod_command(self, interaction: discord.Interaction):
        """Example moderator command."""
        await interaction.response.send_message("This is a moderator-only command!")
    
    @app_commands.command(name="ping", description="Check the bot's latency")
    async def slash_ping(self, interaction: discord.Interaction):
        """Check the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency}ms")

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))