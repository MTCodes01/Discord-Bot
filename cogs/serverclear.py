import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
from utils import command_help, create_embed

class ServerCleaner(commands.Cog):
    """Commands for clearing channels, categories, or entire server"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize when bot is ready"""
        self.logger.info("Server clearing commands initialized")
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="clearchannel", description="Clear a specific channel")
    @command_help("mod", "Delete and recreate a specific channel", "clearchannel [channel]", 
                examples=["clearchannel #general", "clearchannel 123456789012345678"],
                note="This will delete the channel and recreate it with the same permissions.")
    async def clear_channel(self, ctx, channel: discord.TextChannel = None):
        """Delete and recreate a specific channel
        
        Parameters:
            channel: The channel to clear (default: current channel)
        """
        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
            
        # Ensure we're not trying to delete the channel the command was used in
        if channel.id == ctx.channel.id:
            confirmation_channel = await self._get_confirmation_channel(ctx.guild, channel)
            if confirmation_channel is None:
                await ctx.send("❌ Cannot delete the channel the command was used in when there's no other channel to send confirmation to.")
                return
            await ctx.send(f"⚠️ Since you're deleting this channel, confirmation and results will be sent to {confirmation_channel.mention}.")
        else:
            confirmation_channel = ctx.channel
            
        # Save channel details for recreation
        channel_name = channel.name
        channel_topic = channel.topic
        channel_position = channel.position
        channel_category = channel.category
        channel_permissions = channel.overwrites
        
        # Ask for confirmation
        confirm_msg = await ctx.send(f"⚠️ Are you sure you want to clear {channel.mention}? This will delete and recreate the channel.")
        
        # Add reaction confirmation
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Send confirmation if deleting the current channel
                if channel.id == ctx.channel.id:
                    await confirmation_channel.send(f"🔄 Clearing channel #{channel_name}...")
                
                # Delete the channel
                await channel.delete(reason=f"Channel clear requested by {ctx.author}")
                
                # Recreate the channel
                new_channel = await ctx.guild.create_text_channel(
                    name=channel_name,
                    topic=channel_topic,
                    position=channel_position,
                    category=channel_category,
                    overwrites=channel_permissions,
                    reason=f"Channel clear requested by {ctx.author}"
                )
                
                # Log the action
                self.logger.info(f"{ctx.author} cleared channel #{channel_name} in {ctx.guild.name}")
                
                # Send confirmation
                if channel.id == ctx.channel.id:
                    await confirmation_channel.send(f"✅ Channel {new_channel.mention} has been cleared.")
                else:
                    await ctx.send(f"✅ Channel {new_channel.mention} has been cleared.")
            else:
                await ctx.send("❌ Channel clear cancelled.")
                
        except asyncio.TimeoutError:
            await ctx.send("❌ Channel clear timed out.")
            
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete or create channels.")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            self.logger.error(f"Error clearing channel: {str(e)}")
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="clearcategory", description="Clear all channels in a category")
    @command_help("mod", "Delete all channels in a category", "clearcategory [category]", 
                examples=["clearcategory \"General\"", "clearcategory 123456789012345678"],
                note="This will delete all channels in the category but keep the category itself.")
    async def clear_category(self, ctx, *, category_name: str = None):
        """Delete all channels in a category
        
        Parameters:
            category_name: The name of the category to clear
        """
        if category_name is None:
            if ctx.channel.category:
                category = ctx.channel.category
            else:
                await ctx.send("❌ Please specify a category name or use this command in a channel that belongs to a category.")
                return
        else:
            # Find category by name
            category = discord.utils.get(ctx.guild.categories, name=category_name)
            
            if not category:
                # Try to find by partial name
                categories = [c for c in ctx.guild.categories if category_name.lower() in c.name.lower()]
                
                if len(categories) == 0:
                    await ctx.send(f"❌ Couldn't find category with name containing '{category_name}'.")
                    return
                elif len(categories) > 1:
                    # Multiple matches, list them
                    category_list = "\n".join([f"{i+1}. {c.name}" for i, c in enumerate(categories)])
                    await ctx.send(f"Found multiple categories with that name. Please be more specific:\n{category_list}")
                    return
                else:
                    category = categories[0]
        
        # Ensure we don't clear a category with the channel we're using
        if ctx.channel.category == category:
            confirmation_channel = await self._get_confirmation_channel(ctx.guild, ctx.channel, exclude_category=category)
            if confirmation_channel is None:
                await ctx.send("❌ Cannot delete the category containing the channel the command was used in when there's no other channel to send confirmation to.")
                return
            await ctx.send(f"⚠️ Since you're deleting channels in this category, confirmation and results will be sent to {confirmation_channel.mention}.")
        else:
            confirmation_channel = ctx.channel
        
        # Get channels in the category
        channels = category.channels
        
        if not channels:
            await ctx.send(f"⚠️ Category '{category.name}' has no channels.")
            return
        
        # Ask for confirmation
        confirm_msg = await ctx.send(f"⚠️ Are you sure you want to delete all {len(channels)} channels in the '{category.name}' category?")
        
        # Add reaction confirmation
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Send confirmation if clearing our current category
                if ctx.channel.category == category:
                    await confirmation_channel.send(f"🔄 Clearing all channels in category '{category.name}'...")
                else:
                    await ctx.send(f"🔄 Clearing all channels in category '{category.name}'...")
                
                # Delete all channels
                for channel in channels:
                    try:
                        await channel.delete(reason=f"Category clear requested by {ctx.author}")
                    except Exception as e:
                        if confirmation_channel == ctx.channel and ctx.channel.category == category and ctx.channel.id == channel.id:
                            # We just deleted the channel we were using, switch to the confirmation channel
                            continue
                        else:
                            await confirmation_channel.send(f"❌ Failed to delete channel {channel.mention}: {str(e)}")
                
                # Log the action
                self.logger.info(f"{ctx.author} cleared category '{category.name}' in {ctx.guild.name}")
                
                # Send confirmation
                await confirmation_channel.send(f"✅ All channels in category '{category.name}' have been deleted.")
            else:
                await ctx.send("❌ Category clear cancelled.")
                
        except asyncio.TimeoutError:
            await ctx.send("❌ Category clear timed out.")
            
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete channels.")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            self.logger.error(f"Error clearing category: {str(e)}")
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="clearserver", description="Clear all channels and categories in the server")
    @command_help("mod", "Delete all channels and categories except setup", "clearserver", 
                examples=["clearserver"],
                note="This will delete ALL channels and categories except for a text channel named 'setup'. If no setup channel exists, it will create one.")
    async def clear_server(self, ctx):
        """Delete all channels and categories in the server except for 'setup'
        
        This will delete ALL channels and categories except for a text channel named 'setup'.
        If no setup channel exists, it will create one.
        """
        # Find or create setup channel
        setup_channel = discord.utils.get(ctx.guild.text_channels, name="setup")
        
        # If we don't have a setup channel, create one
        if not setup_channel:
            # Default permissions for the setup channel
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            try:
                setup_channel = await ctx.guild.create_text_channel(
                    name="setup",
                    overwrites=overwrites,
                    reason=f"Server clear requested by {ctx.author}"
                )
            except Exception as e:
                await ctx.send(f"❌ Failed to create setup channel: {str(e)}")
                return
        
        # Send confirmation to current channel and setup channel if different
        if ctx.channel.id != setup_channel.id:
            await setup_channel.send(f"⚠️ {ctx.author.mention} has requested to clear the entire server!")
        
        # Ask for confirmation
        confirm_msg = await ctx.send("⚠️ **DANGER!** Are you sure you want to delete ALL channels and categories in this server?\n\nThis will:\n- Delete all channels and categories\n- Keep only the 'setup' channel\n- This action CANNOT be undone!")
        
        # Add reaction confirmation (require double confirmation for this dangerous action)
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            
            if str(reaction.emoji) == "✅":
                # Send a second confirmation prompt
                second_confirm = await ctx.send("⚠️ **FINAL WARNING!** Type `CONFIRM` to proceed with deleting ALL channels. This cannot be undone!")
                
                def msg_check(m):
                    return m.author == ctx.author and m.channel == ctx.channel and m.content == "CONFIRM"
                
                try:
                    await self.bot.wait_for("message", timeout=30.0, check=msg_check)
                    
                    # Send confirmation to setup channel
                    await setup_channel.send("🔄 Beginning server clear...")
                    
                    # Count channels and categories for logging
                    total_channels = len(ctx.guild.channels) - 1  # Minus setup channel
                    
                    # Delete all channels except setup
                    for channel in ctx.guild.channels:
                        if channel.id != setup_channel.id:
                            try:
                                await channel.delete(reason=f"Server clear requested by {ctx.author}")
                            except Exception as e:
                                await setup_channel.send(f"❌ Failed to delete channel {channel.name}: {str(e)}")
                    
                    # Log the action
                    self.logger.info(f"{ctx.author} cleared the entire server {ctx.guild.name}, removing {total_channels} channels")
                    
                    # Send confirmation
                    await setup_channel.send(f"✅ Server clear complete! All channels and categories have been deleted.\n\nTo start rebuilding the server, use bot commands to create new channels and categories.")
                    
                except asyncio.TimeoutError:
                    await ctx.send("❌ Server clear cancelled due to timeout.")
                    
            else:
                await ctx.send("❌ Server clear cancelled.")
                
        except asyncio.TimeoutError:
            await ctx.send("❌ Server clear timed out.")
            
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete channels.")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
            self.logger.error(f"Error clearing server: {str(e)}")
    
    async def _get_confirmation_channel(self, guild, current_channel, exclude_category=None):
        """Find a suitable channel to send confirmation messages to
        
        Parameters:
            guild: The guild to find a channel in
            current_channel: The current channel being deleted
            exclude_category: Optional category to exclude channels from
            
        Returns:
            A suitable channel or None if no suitable channel found
        """
        # First try to find a channel named "setup"
        setup_channel = discord.utils.get(guild.text_channels, name="setup")
        if setup_channel and setup_channel.id != current_channel.id:
            return setup_channel
        
        # Next try to find any other text channel
        for channel in guild.text_channels:
            if channel.id != current_channel.id:
                if exclude_category and channel.category == exclude_category:
                    continue
                return channel
        
        # No suitable channel found
        return None

async def setup(bot):
    await bot.add_cog(ServerCleaner(bot))