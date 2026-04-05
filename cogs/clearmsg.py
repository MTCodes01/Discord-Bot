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
    
    @command_help("mod", "Clear messages from the channel", "clear [count]",
                 examples=["clear 10", "clear 50"],
                 note="Can clear up to 100 messages at once. Messages older than 14 days cannot be bulk-deleted due to Discord limitations.")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.hybrid_command(name="clear", aliases=["purge"], description="Clear a specified number of messages")
    async def clear(self, ctx, count: int = 10):
        """Clear a specified number of messages from the channel

        Parameters:
            count: The number of messages to clear (default: 10, max: 100)
        """
        # Validate count
        if count <= 0:
            await ctx.send("❌ Number of messages to clear must be positive.", ephemeral=True)
            return
            
        if count > 100:
            await ctx.send("⚠️ You can only delete up to 100 messages at once. Setting count to 100.", ephemeral=True)
            count = 100
        
        # Defer interaction to avoid timeout during deletion, or delete invocation message for text commands
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            
        try:
            # Perform deletion
            deleted = await ctx.channel.purge(limit=count)
            
            # Formulate response
            embed = discord.Embed(
                title="🧹 Messages Cleared",
                description=f"Successfully deleted **{len(deleted)}** messages.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text=f"Action by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            
            msg = await ctx.send(embed=embed, ephemeral=True)
            
            # Log the action with more detail
            self.logger.info(
                f"[Bulk Delete] Moderator: {ctx.author} (ID: {ctx.author.id}) | "
                f"Channel: #{ctx.channel.name} (ID: {ctx.channel.id}) | "
                f"Deleted: {len(deleted)}/{count} messages"
            )
            
            # Only auto-delete confirmation for pure text commands
            if not ctx.interaction:
                try:
                    await asyncio.sleep(5)
                    await msg.delete()
                except discord.HTTPException:
                    pass
                
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)
        except discord.errors.HTTPException as e:
            if e.code == 50034:
                await ctx.send("❌ Cannot delete messages older than 14 days due to Discord limitations.", ephemeral=True)
            else:
                self.logger.error(f"[Bulk Delete Error] {e}")
                await ctx.send(f"❌ Error deleting messages: {str(e)}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"[Bulk Delete Exception] {e}")
            await ctx.send("❌ An unexpected error occurred while deleting messages.", ephemeral=True)
    
    @command_help("mod", "Clear messages from a specific user", "clearuser [user] [count]",
                 examples=["clearuser @username 20", "clearuser 123456789012345678 50"],
                 note="Can clear up to 100 messages at once. Messages older than 14 days cannot be bulk-deleted.")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.hybrid_command(name="clearuser", aliases=["purgeuser"], description="Clear messages from a specific user")
    async def clear_user(self, ctx, user: discord.Member, count: int = 10):
        """Clear messages from a specific user in the channel

        Parameters:
            user: The user whose messages to clear
            count: The maximum number of messages to check (default: 10, max: 100)
        """
        # Validate count
        if count <= 0:
            await ctx.send("❌ Number of messages to clear must be positive.", ephemeral=True)
            return
            
        if count > 100:
            await ctx.send("⚠️ You can only check up to 100 messages at once. Setting count to 100.", ephemeral=True)
            count = 100
        
        # Defer interaction to avoid timeout, or delete invocation message for text commands
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        else:
            try:
                await ctx.message.delete()
            except discord.HTTPException:
                pass
            
        try:
            # Define check function to filter messages by the specified user
            def check(message):
                return message.author.id == user.id
                
            # Perform deletion
            deleted = await ctx.channel.purge(limit=count, check=check)
            
            # Formulate response
            embed = discord.Embed(
                title="🧹 User Messages Cleared",
                description=f"Successfully deleted **{len(deleted)}** messages from {user.mention}.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"Action by {ctx.author}", icon_url=ctx.author.display_avatar.url)
            
            msg = await ctx.send(embed=embed, ephemeral=True)
            
            # Log the action with more detail
            self.logger.info(
                f"[Bulk Delete User] Moderator: {ctx.author} (ID: {ctx.author.id}) | "
                f"Target: {user} (ID: {user.id}) | "
                f"Channel: #{ctx.channel.name} (ID: {ctx.channel.id}) | "
                f"Deleted: {len(deleted)} messages (checked max {count})"
            )
            
            # Only auto-delete confirmation for pure text commands
            if not ctx.interaction:
                try:
                    await asyncio.sleep(5)
                    await msg.delete()
                except discord.HTTPException:
                    pass
                
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)
        except discord.errors.HTTPException as e:
            if e.code == 50034:
                await ctx.send("❌ Cannot delete messages older than 14 days due to Discord limitations.", ephemeral=True)
            else:
                self.logger.error(f"[Bulk Delete User Error] {e}")
                await ctx.send(f"❌ Error deleting messages: {str(e)}", ephemeral=True)
        except Exception as e:
            self.logger.error(f"[Bulk Delete User Exception] {e}")
            await ctx.send("❌ An unexpected error occurred while deleting messages.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ClearMessages(bot))