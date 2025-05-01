import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
from utils import command_help, create_embed

class ClearMessages(commands.Cog):
    """Commands for clearing messages in channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize when bot is ready"""
        self.logger.info("Message clearing commands initialized")
    
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.hybrid_command(name="clear", aliases=["purge"], description="Clear a specified number of messages")
    @command_help("mod", "Clear messages from the channel", "clear [count]", 
                 examples=["clear 10", "clear 50"],
                 note="Can clear up to 100 messages at once. Messages older than 14 days cannot be bulk-deleted due to Discord limitations.")
    async def clear(self, ctx, count: int = 10):
        """Clear a specified number of messages from the channel

        Parameters:
            count: The number of messages to clear (default: 10, max: 100)
        """
        # Validate count
        if count <= 0:
            await ctx.send("❌ Number of messages to clear must be positive.")
            return
            
        if count > 100:
            await ctx.send("⚠️ You can only delete up to 100 messages at once. Setting count to 100.")
            count = 100
        
        # Delete command message if it's a text command
        if ctx.interaction is None:
            await ctx.message.delete()
            
        try:
            # Perform deletion
            deleted = await ctx.channel.purge(limit=count)
            
            # Send confirmation
            msg = await ctx.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
            
            # Log the action
            self.logger.info(f"{ctx.author} cleared {len(deleted)} messages in #{ctx.channel.name}")
            
            # Auto-delete confirmation after a few seconds if possible
            try:
                await asyncio.sleep(5)
                await msg.delete()
            except:
                pass
                
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel.")
        except discord.errors.HTTPException as e:
            if e.code == 50034:
                await ctx.send("❌ Cannot delete messages older than 14 days due to Discord limitations.")
            else:
                await ctx.send(f"❌ Error deleting messages: {str(e)}")
    
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.hybrid_command(name="clearuser", aliases=["purgeuser"], description="Clear messages from a specific user")
    @command_help("mod", "Clear messages from a specific user", "clearuser [user] [count]", 
                 examples=["clearuser @username 20", "clearuser 123456789012345678 50"],
                 note="Can clear up to 100 messages at once. Messages older than 14 days cannot be bulk-deleted.")
    async def clear_user(self, ctx, user: discord.Member, count: int = 10):
        """Clear messages from a specific user in the channel

        Parameters:
            user: The user whose messages to clear
            count: The maximum number of messages to check (default: 10, max: 100)
        """
        # Validate count
        if count <= 0:
            await ctx.send("❌ Number of messages to clear must be positive.")
            return
            
        if count > 100:
            await ctx.send("⚠️ You can only check up to 100 messages at once. Setting count to 100.")
            count = 100
        
        # Delete command message if it's a text command
        if ctx.interaction is None:
            await ctx.message.delete()
            
        try:
            # Define check function to filter messages by the specified user
            def check(message):
                return message.author.id == user.id
                
            # Perform deletion
            deleted = await ctx.channel.purge(limit=count, check=check)
            
            # Send confirmation
            msg = await ctx.send(f"✅ Deleted {len(deleted)} messages from {user.mention}.", ephemeral=True)
            
            # Log the action
            self.logger.info(f"{ctx.author} cleared {len(deleted)} messages from {user} in #{ctx.channel.name}")
            
            # Auto-delete confirmation after a few seconds if possible
            try:
                await asyncio.sleep(5)
                await msg.delete()
            except:
                pass
                
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel.")
        except discord.errors.HTTPException as e:
            if e.code == 50034:
                await ctx.send("❌ Cannot delete messages older than 14 days due to Discord limitations.")
            else:
                await ctx.send(f"❌ Error deleting messages: {str(e)}")

async def setup(bot):
    await bot.add_cog(ClearMessages(bot))