import discord
from discord.ext import commands
from discord import app_commands
import config
import sys
import asyncio
import os
import logging
from utils import owner_only, mod_only, command_help, HelpInfo, create_embed

class HelpView(discord.ui.View):
    """Interactive help menu with pagination and category filtering"""
    
    def __init__(self, ctx, commands_by_category, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.commands_by_category = commands_by_category
        self.current_page = 0
        self.current_category = "all"  # Default to show all categories
        self.items_per_page = 10
        
        # Setup the category select dropdown
        self.category_select = self.create_category_select()
        self.add_item(self.category_select)
        
        # Setup the navigation buttons
        self.previous_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Previous",
            emoji="◀️",
            disabled=True
        )
        self.previous_button.callback = self.on_previous
        self.add_item(self.previous_button)
        
        self.next_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Next",
            emoji="▶️",
            disabled=self.get_total_pages() <= 1
        )
        self.next_button.callback = self.on_next
        self.add_item(self.next_button)
        
    def create_category_select(self):
        """Create the category selection dropdown"""
        # Create options based on available categories
        options = [discord.SelectOption(label="All Commands", value="all", emoji="📋", default=True)]
        
        # Add owner commands if user is owner
        if self.ctx.author.id == config.OWNER_ID and self.commands_by_category["owner"]:
            options.append(discord.SelectOption(label="Owner Commands", value="owner", emoji="🔒"))
            
        # Add mod commands if user is mod or owner
        is_mod = any(role.id in config.MOD_ROLES for role in self.ctx.author.roles) if self.ctx.guild else False
        if (is_mod or self.ctx.author.id == config.OWNER_ID) and self.commands_by_category["mod"]:
            options.append(discord.SelectOption(label="Moderator Commands", value="mod", emoji="🛡️"))
            
        # Add general commands option
        if self.commands_by_category["general"]:
            options.append(discord.SelectOption(label="General Commands", value="general", emoji="📝"))
            
        # Create the select menu
        select = discord.ui.Select(
            placeholder="Select command category",
            options=options
        )
        select.callback = self.on_category_select
        return select
        
    async def on_category_select(self, interaction):
        """Handle category selection"""
        self.current_category = interaction.data["values"][0]
        self.current_page = 0  # Reset to first page when changing category
        
        # Update button states
        await self.update_view(interaction)
    
    async def on_previous(self, interaction):
        """Handle previous page button"""
        self.current_page -= 1
        await self.update_view(interaction)
    
    async def on_next(self, interaction):
        """Handle next page button"""
        self.current_page += 1
        await self.update_view(interaction)
    
    async def update_view(self, interaction):
        """Update the view and embed"""
        # Update button states
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.get_total_pages() - 1)
        
        # Update the message
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    def get_total_pages(self):
        """Calculate the total number of pages for the current category"""
        commands_list = self.get_visible_commands()
        return max(1, (len(commands_list) + self.items_per_page - 1) // self.items_per_page)
    
    def get_visible_commands(self):
        """Get list of commands visible to the user based on selected category"""
        if self.current_category == "all":
            # Combine all accessible categories
            visible_commands = []
            
            # Add owner commands if user is owner
            if self.ctx.author.id == config.OWNER_ID:
                visible_commands.extend(self.commands_by_category.get("owner", []))
                
            # Add mod commands if user is mod or owner
            is_mod = any(role.id in config.MOD_ROLES for role in self.ctx.author.roles) if self.ctx.guild else False
            if is_mod or self.ctx.author.id == config.OWNER_ID:
                visible_commands.extend(self.commands_by_category.get("mod", []))
                
            # Add general commands (accessible to everyone)
            visible_commands.extend(self.commands_by_category.get("general", []))
            
            return visible_commands
        else:
            # Return only the selected category if the user has permission to view it
            category = self.current_category
            
            if category == "owner" and self.ctx.author.id != config.OWNER_ID:
                return []
                
            if category == "mod":
                is_mod = any(role.id in config.MOD_ROLES for role in self.ctx.author.roles) if self.ctx.guild else False
                if not is_mod and self.ctx.author.id != config.OWNER_ID:
                    return []
                    
            return self.commands_by_category.get(category, [])
    
    def get_embed(self):
        """Generate the help embed for the current page and category"""
        if self.current_category == "all":
            title = "Bot Commands Help"
        elif self.current_category == "owner":
            title = "🔒 Owner Commands"
        elif self.current_category == "mod":
            title = "🛡️ Moderator Commands"
        else:
            title = "📝 General Commands"
            
        embed = create_embed(title)
        
        # Get the commands for this category and page
        commands_list = self.get_visible_commands()
        
        # Calculate pagination
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(commands_list))
        
        # Generate command list text
        if not commands_list:
            embed.description = "No commands available in this category."
        else:
            page_commands = commands_list[start_idx:end_idx]
            
            # If showing all categories, group by category
            if self.current_category == "all":
                # Group commands by category
                by_category = {"owner": [], "mod": [], "general": []}
                
                for cmd in page_commands:
                    for cat in ["owner", "mod", "general"]:
                        if cmd in self.commands_by_category.get(cat, []):
                            by_category[cat].append(cmd)
                            break
                
                # Add owner commands field if any
                if by_category["owner"] and self.ctx.author.id == config.OWNER_ID:
                    owner_text = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}"
                                          for cmd in by_category["owner"]])
                    embed.add_field(name="🔒 Owner Commands", value=owner_text, inline=False)
                    
                # Add mod commands field if any
                if by_category["mod"]:
                    mod_text = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}"
                                        for cmd in by_category["mod"]])
                    embed.add_field(name="🛡️ Moderator Commands", value=mod_text, inline=False)
                    
                # Add general commands field if any
                if by_category["general"]:
                    general_text = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}"
                                            for cmd in by_category["general"]])
                    embed.add_field(name="📝 General Commands", value=general_text, inline=False)
            else:
                # Just show the commands from the selected category
                commands_text = "\n".join([f"`{config.PREFIX}{cmd['name']}` - {cmd['description']}"
                                         for cmd in page_commands])
                embed.description = commands_text
        
        # Add pagination info to footer
        total_pages = self.get_total_pages()
        total_commands = len(commands_list)
        
        if total_commands > 0:
            pagination_info = f"Page {self.current_page + 1}/{total_pages} • "
            pagination_info += f"Showing {min(self.items_per_page, end_idx - start_idx)} of {total_commands} commands"
        else:
            pagination_info = "No commands to display"
            
        embed.set_footer(text=f"{pagination_info} • Use {config.PREFIX}help [command] for details")
        
        return embed
        
    async def interaction_check(self, interaction):
        """Ensure only the user who initiated the help command can use the components"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("You can't use this menu. Please run your own help command.", ephemeral=True)
            return False
        return True


class Commands(commands.Cog):
    """Main commands for the bot."""
    
    def __init__(self, bot):
        self.bot: commands.Bot = bot
    
    # Core system commands (owner only)
    @command_help("owner", "Shuts down the bot completely", "shutdown")
    @owner_only()
    @commands.hybrid_command(name="shutdown", description="Shuts down the bot completely")
    async def shutdown(self, ctx):
        """Shut down the bot completely."""
        await ctx.send("Shutting down... Sayonara!")

        # Safely close HTTP session if it exists
        if hasattr(self.bot, "session"):
            await self.bot.session.close()
            
        await self.bot.close()
        
    @commands.hybrid_command(name="reboot", description="Reloads all cogs to update code")
    @owner_only()
    @command_help("owner", "Reloads all cogs to update code", "reboot")
    async def reboot(self, ctx):
        """Reload all cogs to implement code changes."""
        from utils import HelpInfo
        HelpInfo._commands = {"owner": [], "mod": [], "general": []}  # Clear all help data

        message: discord.Message = await ctx.send("Rebooting cogs...")
        extensions = list(self.bot.extensions)

        for extension in extensions:
            try:
                await self.bot.unload_extension(extension)
            except Exception as e:
                await message.edit(content=f"Error unloading {extension}: {e}")
                return

        for extension in extensions:
            try:
                await self.bot.load_extension(extension)
            except Exception as e:
                await message.edit(content=f"Error loading {extension}: {e}")
                return

        await message.edit(content="✅ All cogs have been reloaded successfully!")

    @command_help("owner", "Syncs application commands (slash commands)", "sync")
    @owner_only()
    @commands.hybrid_command(name="sync", description="Syncs application commands (slash commands)")
    async def sync(self, ctx):
        """Sync application commands (slash commands)."""
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} application commands.")
        except Exception as e:
            await ctx.send(f"Failed to sync application commands: {e}")
        await ctx.send("All application commands have been synced successfully!")
    
    @command_help("owner", "Set the bot's status", "status [status]")
    @owner_only()
    @commands.hybrid_command(name="status", description="Set the bot's status")
    async def status(self, ctx, *, status: str):
        """Set the bot's status."""
        await self.bot.change_presence(activity=discord.Game(name=status))
        await ctx.send(f"Bot status set to: {status}")
        await ctx.send("Bot status has been updated successfully!")

    @command_help(
        category="owner",
        description="Lists all available cogs in the cogs folder",
        usage="listcogs",
        examples=["listcogs"],
        note="Shows all .py files in the cogs directory"
    )
    @owner_only()
    @commands.hybrid_command(name="listcogs", description="Lists all available cogs")
    async def listcogs(self, ctx):
        """List all .py files in the cogs folder."""
        files = [f[:-3] for f in os.listdir("./cogs") if f.endswith(".py") and not f.startswith("__")]
        if files:
            await ctx.send("📁 Available cogs:\n" + "\n".join(f"- `{f}`" for f in files))
        else:
            await ctx.send("⚠️ No cogs found.")
    
    # Help commands
    @command_help("general", "Shows help information for commands", "help [command]")
    @commands.hybrid_command(name="help", description="Shows help information for commands")
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
            # Show all commands with pagination and category selection
            commands_by_category = HelpInfo.get_all_commands()
            
            # Create the paginated help view
            view = HelpView(ctx, commands_by_category)
            
            # Send the initial embed with the view
            await ctx.send(embed=view.get_embed(), view=view)
    
    # Example commands
    @command_help("mod", "Example command for moderators", "mod_command")
    @mod_only()
    @commands.hybrid_command(name="mod", description="Example command for demonstration of mod-only access")
    async def mod_command(self, ctx):
        """Example moderator command."""
        await ctx.send("This is a moderator-only command!")
    
    @command_help("owner", "Example command for bot owners", "owner_command")
    @owner_only()
    @commands.hybrid_command(name="owner", description="Example command for demonstration of owner-only access")
    async def owner_command(self, ctx):
        """Example owner-only command."""
        await ctx.send("This is an owner-only command!")
    
    @command_help("general", "Ping the bot to check latency", "ping")
    @commands.hybrid_command(name="ping", description="Check the bot's latency")
    async def ping(self, ctx):
        """Check the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! Latency: {latency}ms")


    @command_help("general", "Display the server rules", "rules")
    @commands.hybrid_command(name="rules", description="Display the server rules")
    async def rules(self, ctx):
        embed = discord.Embed(
            title="📜 ISTE CEAL Discord Server Rules",
            description="Welcome to the official ISTE CEAL server! This is a chill space to learn, create, and connect. "
                        "To keep things smooth and respectful for everyone, here are some simple ground rules:",
            color=discord.Color.from_str("#58B9FF")
        )

        embed.add_field(
            name="🗣️ Be Respectful",
            value="Treat everyone kindly. Avoid bullying, rude behavior, or personal attacks. "
                  "Healthy discussions are great—just keep it friendly.",
            inline=False
        )

        embed.add_field(
            name="❌ No Hateful or Offensive Language",
            value="Avoid slurs, hate speech, or anything that makes the server uncomfortable. "
                  "Casual swearing is okay—don’t go overboard or be toxic.",
            inline=False
        )

        embed.add_field(
            name="🌍 Speak Any Language",
            value="Use whatever language you're comfortable with. "
                  "Just keep things inclusive in public channels when possible.",
            inline=False
        )

        embed.add_field(
            name="📌 Stay On Topic",
            value="Use each channel for its intended purpose. Keep memes, music, and chill convos in the right spots.",
            inline=False
        )

        embed.add_field(
            name="🚫 No Spam or Random Promotions",
            value="Avoid spamming messages, emojis, or links. Don’t advertise other servers or content without checking first.",
            inline=False
        )

        embed.add_field(
            name="⚠️ Rule Violations",
            value="We’re a relaxed community, but if someone’s ruining the vibe, "
                  "actions like a warning or mute might happen—nothing personal.",
            inline=False
        )

        embed.set_footer(text="🎉 Let’s make this a fun and welcoming space for all ISTE CEAL members!")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Commands(bot))
