import discord
from discord.ext import commands
import config
import sys
import asyncio
from utils import owner_only, mod_only, command_help, HelpInfo, create_embed

class Commands(commands.Cog):
    """Main commands for the bot."""
    
    def __init__(self, bot):
        self.bot = bot
    
    # Core system commands (owner only)
    @commands.command()
    @owner_only()
    @command_help("owner", "Shuts down the bot completely", "shutdown")
    async def shutdown(self, ctx):
        """Shut down the bot completely."""
        await ctx.send("Shutting down... Goodbye!")
        await self.bot.close()
        
    @commands.command()
    @owner_only()
    @command_help("owner", "Reloads all cogs to update code", "reboot")
    async def reboot(self, ctx):
        """Reload all cogs to implement code changes."""
        message = await ctx.send("Rebooting cogs...")
        
        # Unload all cogs
        for extension in list(self.bot.extensions):
            try:
                await self.bot.unload_extension(extension)
            except Exception as e:
                await message.edit(content=f"Error unloading {extension}: {e}")
                return
                
        # Load all cogs back
        for extension in list(self.bot.extensions):
            try:
                await self.bot.load_extension(extension)
            except Exception as e:
                await message.edit(content=f"Error loading {extension}: {e}")
                return
                
        await message.edit(content="All cogs have been reloaded successfully!")
        
    # Help commands
    @commands.command()
    @command_help("general", "Shows help information for commands", "help [command]")
    async def help(self, ctx, command_name=None):
        """Display help information for commands."""
        if command_name:
            # Show specific command help
            cmd_info, category = HelpInfo.get_command_by_name(command_name)
            if cmd_info:
                embed = create_embed(f"Help: {cmd_info['name']}")
                embed.add_field(name="Description", value=cmd_info["description"], inline=False)
                if cmd_info["usage"]:
                    embed.add_field(name="Usage", value=f"`{config.PREFIX}{cmd_info['usage']}`", inline=False)
                embed.add_field(name="Category", value=category.capitalize(), inline=False)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"Command '{command_name}' not found.")
        else:
            # Show all commands
            embed = create_embed("Bot Commands Help")
            
            commands_by_category = HelpInfo.get_all_commands()
            
            # Owner commands (only show to owner)
            if ctx.author.id == config.OWNER_ID and commands_by_category["owner"]:
                owner_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                       for cmd in commands_by_category["owner"]])
                embed.add_field(name="🔒 Owner Commands", value=owner_cmds or "None", inline=False)
            
            # Mod commands (only show to mods and owner)
            is_mod = any(role.id in config.MOD_ROLES for role in ctx.author.roles) if ctx.guild else False
            if (is_mod or ctx.author.id == config.OWNER_ID) and commands_by_category["mod"]:
                mod_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                     for cmd in commands_by_category["mod"]])
                embed.add_field(name="🛡️ Moderator Commands", value=mod_cmds or "None", inline=False)
            
            # General commands (show to everyone)
            if commands_by_category["general"]:
                general_cmds = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}" 
                                         for cmd in commands_by_category["general"]])
                embed.add_field(name="📝 General Commands", value=general_cmds or "None", inline=False)
            
            embed.set_footer(text=f"Use {config.PREFIX}help [command] for detailed info about a command.")
            await ctx.send(embed=embed)
    
    # Example commands
    @commands.command()
    @mod_only()
    @command_help("mod", "Example command for moderators", "mod_command")
    async def mod_command(self, ctx):
        """Example moderator command."""
        await ctx.send("This is a moderator-only command!")
    
    @commands.command()
    @command_help("general", "Ping the bot to check latency", "ping")
    async def ping(self, ctx):
        """Check the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency}ms")

async def setup(bot):
    await bot.add_cog(Commands(bot))
