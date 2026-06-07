import discord
from discord.ext import commands
from discord import app_commands
import config
import sys
import asyncio
import os
import logging
import platform
import datetime
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
        self.start_time = datetime.datetime.now(datetime.timezone.utc)
    
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

    @command_help("owner", "Syncs application commands (slash commands)", "sync [scope]")
    @owner_only()
    @commands.hybrid_command(name="sync", description="Syncs application commands (slash commands)")
    async def sync(self, ctx, scope: str = None):
        """Sync application commands (slash commands).
        
        Scope 'guild' syncs global commands to the current server (immediate).
        Scope 'clear' removes server-specific commands to fix duplicates.
        No scope syncs globally (takes up to an hour).
        """
        await ctx.defer(ephemeral=True)
        try:
            if scope == "guild" or scope == "local":
                self.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send(f"Synced {len(synced)} application commands to **this guild**.", ephemeral=True)
            elif scope == "clear":
                self.bot.tree.clear_commands(guild=ctx.guild)
                await self.bot.tree.sync(guild=ctx.guild)
                await ctx.send("Cleared all guild-specific application commands to fix duplicates.", ephemeral=True)
            else:
                synced = await self.bot.tree.sync()
                await ctx.send(f"Synced {len(synced)} application commands **globally**.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Failed to sync application commands: {e}", ephemeral=True)

    
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

    @command_help("general", "Show bot vitals, version, and info", "about")
    @commands.hybrid_command(name="about", aliases=["vitals", "botinfo", "info"], description="Show bot vitals, version, and information")
    async def about(self, ctx):
        """Display information about the bot, its vitals, and its creator."""
        uptime = datetime.datetime.now(datetime.timezone.utc) - self.start_time
        
        # Format uptime nicely
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s" if days > 0 else f"{hours}h {minutes}m {seconds}s"
        
        # Get owner info
        owner = self.bot.get_user(config.OWNER_ID)
        owner_str = str(owner).replace("#0", "") if owner else f"User ID: {config.OWNER_ID}"
        
        embed = create_embed("Bot Vitals & Information")
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            
        # Core Vitals
        embed.add_field(
            name="📊 Vitals", 
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n"
                  f"**Uptime:** {uptime_str}\n"
                  f"**Servers:** {len(self.bot.guilds)}\n"
                  f"**Cached Users:** {len(self.bot.users)}", 
            inline=False
        )
        
        # System Info
        embed.add_field(
            name="💻 System Details", 
            value=f"**Python:** v{platform.python_version()}\n"
                  f"**Discord.py:** v{discord.__version__}\n"
                  f"**OS:** {platform.system()} {platform.release()}\n"
                  f"**Host:** {platform.node()}", 
            inline=False
        )
        
        # Ownership
        embed.add_field(
            name="👑 Ownership", 
            value=f"**Owner:** {owner_str}\n"
                  f"**Status:** Running perfectly fine! ✨", 
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


    @command_help("general", "Display the server rules", "rules")
    @commands.hybrid_command(name="rules", description="Display the server rules")
    async def rules(self, ctx):
        embed = discord.Embed(
            title="📜 Server Rules",
            description="Welcome to the server! To keep this a friendly, safe, and productive space for everyone, please follow these rules:",
            color=discord.Color.from_str("#58B9FF")
        )

        embed.add_field(
            name="1️⃣ Be respectful",
            value="Treat everyone kindly. No hate speech, bullying, or harassment.",
            inline=False
        )

        embed.add_field(
            name="2️⃣ Stay on topic",
            value="Use the correct channels for specific topics.",
            inline=False
        )

        embed.add_field(
            name="3️⃣ No spam or self-promotion",
            value="Avoid mass messages, links, or ads without permission.",
            inline=False
        )

        embed.add_field(
            name="4️⃣ Use appropriate language",
            value="No NSFW or offensive content. Keep it clean.",
            inline=False
        )

        embed.add_field(
            name="5️⃣ Respect privacy",
            value="Do not share personal or sensitive info — yours or others’.",
            inline=False
        )

        embed.add_field(
            name="6️⃣ Follow Discord’s Terms of Service",
            value="Keep it legal and respectful.",
            inline=False
        )

        embed.add_field(
            name="7️⃣ Respect mods",
            value="Moderators help keep things safe. Follow their instructions.",
            inline=False
        )

        embed.add_field(
            name="8️⃣ No piracy or illegal content",
            value="No cracked software, pirated media, or hacks.",
            inline=False
        )

        embed.add_field(
            name="9️⃣ Keep names & avatars appropriate",
            value="No offensive usernames or profile pictures.",
            inline=False
        )

        embed.add_field(
            name="🔟 No impersonation",
            value="Don't pretend to be someone else, including staff members or other users.",
            inline=False
        )

        embed.set_footer(text="✅ Thanks for being a part of our FOSS CEAL community! Let's make it awesome together.")

        await ctx.send(embed=embed)

    @command_help(
        category="mod",
        description="Send a direct message to a user from the bot",
        usage="dm <user> <message>",
        examples=["dm @User Hello there!", "dm 123456789 Your report has been reviewed."],
        note="The target user must share a server with the bot and have DMs open."
    )
    @mod_only()
    @commands.hybrid_command(name="dm", description="Send a direct message to a user from the bot")
    @app_commands.describe(user="The user to send a DM to", message="The plain text message to send")
    async def dm(self, ctx, user: discord.User, *, message: str):
        """Send a direct message to a specified user from the bot."""
        await ctx.defer()
        try:
            await user.send(message)
        except discord.Forbidden:
            await ctx.send(
                f"❌ Could not send a DM to **{user.display_name}**. "
                "They may have DMs disabled or have blocked the bot."
            )
            return
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send DM: {e}")
            return

        # Confirm to the moderator
        await ctx.send(f"✅ Message successfully sent to **{user.display_name}**: {message}")




async def setup(bot):
    await bot.add_cog(Commands(bot))

