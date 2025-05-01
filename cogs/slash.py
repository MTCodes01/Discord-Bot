import discord
from discord.ext import commands
from discord import app_commands
import config
import asyncio
from utils import owner_only, mod_only, create_embed, command_help

class SlashCommands(commands.GroupCog):
    """Slash commands for the bot."""
    
    def __init__(self, bot):
        self.bot = bot
        self.commands_cog = None
        super().__init__()
    
    async def cog_load(self):
        """Get reference to the Commands cog for command reuse."""
        await asyncio.sleep(1)  # Wait for all cogs to load
        self.commands_cog = self.bot.get_cog('Commands')
    
    # Help command
    @app_commands.command(name="help", description="Show help information for commands")
    @app_commands.describe(command_name="The command to get help for (optional)")
    async def help(self, interaction: discord.Interaction, command_name: str = None):
        """Display help information for commands."""
        await interaction.response.defer()
        
        if command_name:
            # Show specific command help
            from utils import HelpInfo
            cmd_info, category = HelpInfo.get_command_by_name(command_name)
            if cmd_info:
                embed = create_embed(f"Help: {cmd_info['name']}")
                embed.add_field(name="Description", value=cmd_info["description"], inline=False)
                if cmd_info["usage"]:
                    embed.add_field(name="Usage", value=f"`{config.PREFIX}{cmd_info['usage']}`", inline=False)
                embed.add_field(name="Category", value=category.capitalize(), inline=False)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"Command '{command_name}' not found.")
        else:
            # Show all commands based on permission level
            from utils import HelpInfo
            
            embed = create_embed("Bot Commands Help")
            commands_by_category = HelpInfo.get_all_commands()
            
            # Owner commands (only show to owner)
            if interaction.user.id == config.OWNER_ID and commands_by_category["owner"]:
                owner_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                      for cmd in commands_by_category["owner"]])
                embed.add_field(name="🔒 Owner Commands", value=owner_cmds or "None", inline=False)
            
            # Mod commands (only show to mods and owner)
            is_mod = (interaction.guild and 
                      any(role.id in config.MOD_ROLES for role in interaction.user.roles))
            if (is_mod or interaction.user.id == config.OWNER_ID) and commands_by_category["mod"]:
                mod_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                    for cmd in commands_by_category["mod"]])
                embed.add_field(name="🛡️ Moderator Commands", value=mod_cmds or "None", inline=False)
            
            # General commands (show to everyone)
            if commands_by_category["general"]:
                general_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                        for cmd in commands_by_category["general"]])
                embed.add_field(name="📝 General Commands", value=general_cmds or "None", inline=False)
            
            embed.set_footer(text=f"Use {config.PREFIX}help [command] for detailed info about a command.")
            await interaction.followup.send(embed=embed)
    
    # Core system commands
    @app_commands.command(name="shutdown", description="Shut down the bot completely (owner only)")
    async def shutdown(self, interaction: discord.Interaction):
        """Shut down the bot completely."""
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Only the bot owner can use this command!", ephemeral=True)
            
        await interaction.response.send_message("Shutting down... Goodbye!")
        await self.bot.close()
    
    @app_commands.command(name="reboot", description="Reload all cogs to update code (owner only)")
    async def reboot(self, interaction: discord.Interaction):
        """Reload all cogs to implement code changes."""
        if interaction.user.id != config.OWNER_ID:
            return await interaction.response.send_message("Only the bot owner can use this command!", ephemeral=True)
            
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
            # Re-sync slash commands
            try:
                await self.bot.tree.sync()
                await interaction.followup.send("All cogs have been reloaded and slash commands synced successfully!")
            except Exception as e:
                await interaction.followup.send(f"Cogs reloaded but failed to sync commands: {e}")
        
    # Example commands
    @app_commands.command(name="mod_command", description="Example command for moderators")
    async def mod_command(self, interaction: discord.Interaction):
        """Example moderator command."""
        # Check if user is a mod or the owner
        is_mod = interaction.user.id == config.OWNER_ID or (
            interaction.guild and any(role.id in config.MOD_ROLES for role in interaction.user.roles)
        )
        
        if not is_mod:
            return await interaction.response.send_message("Only moderators can use this command!", ephemeral=True)
            
        await interaction.response.send_message("This is a moderator-only command!")
    
    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Check the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! Latency: {latency}ms")

async def setup(bot):
    await bot.add_cog(SlashCommands(bot))