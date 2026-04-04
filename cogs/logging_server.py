import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import json
import typing
from typing import Dict, List, Optional, Union, Any
from util.logging_utils import LoggingSystem, LogEmbed
import traceback
from utils import command_help, create_embed


class ServerLogging(commands.Cog):
    """Server event logging system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.logging_system = LoggingSystem(bot)
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize logging system when bot is ready"""
        self.logger.info("Logging system initialized")
    
    async def get_audit_log_executor(self, guild, action, target_id=None):
        if not guild.me.guild_permissions.view_audit_log:
            return None
        try:
            await asyncio.sleep(1.0)
            async for entry in guild.audit_logs(action=action, limit=5):
                if (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
                    if target_id is None or (hasattr(entry.target, 'id') and entry.target.id == target_id) or entry.target == target_id:
                        return entry.user
        except Exception:
            pass
        return None

    # === Event Listeners ===
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log message deletions"""
        # Skip bot messages
        if message.author.bot:
            return
            
        # Skip non-guild messages
        if not message.guild:
            return
            
        try:
            # Check who deleted it
            executor = await self.get_audit_log_executor(message.guild, discord.AuditLogAction.message_delete, message.author.id)
            
            self.logger.info(f"[Guild: {message.guild.name}] Message by {message.author} deleted in #{message.channel.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.message_delete(message, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(message.guild, "message-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging message delete: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        """Log bulk message deletions"""
        # Skip empty lists
        if not messages:
            return
            
        # Get guild from first message
        first_message = messages[0]
        guild = first_message.guild
        
        if not guild:
            return
            
        self.logger.info(f"[Guild: {guild.name}] Bulk message delete ({len(messages)} messages) in #{first_message.channel.name}")
            
        try:
            # Create embed
            embed = discord.Embed(
                title="🗑️ Bulk Messages Deleted",
                description=f"{len(messages)} messages were deleted in {first_message.channel.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Channel", value=f"{first_message.channel.name} ({first_message.channel.id})", inline=True)
            embed.add_field(name="Count", value=str(len(messages)), inline=True)
            
            # Log to appropriate channel
            await self.logging_system.log_event(guild, "message-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging bulk message delete: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log message edits"""
        # Skip bot messages
        if before.author.bot:
            return
            
        # Skip non-guild messages
        if not before.guild:
            return
            
        # Skip if content didn't change
        if before.content == after.content:
            return
            
        try:
            self.logger.info(f"[Guild: {before.guild.name}] Message by {after.author} edited in #{after.channel.name}")

            # Create embed
            embed = LogEmbed.message_edit(before, after)
            
            # Log to appropriate channel
            await self.logging_system.log_event(before.guild, "message-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging message edit: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log member joins"""
        # Skip bots if needed
        # if member.bot:
        #     return
            
        try:
            self.logger.info(f"[Guild: {member.guild.name}] Member joined: {member}")

            # Create embed
            embed = LogEmbed.member_join(member)
            
            # Log to appropriate channel
            await self.logging_system.log_event(member.guild, "member-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging member join: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log member leaves"""
        # Skip bots if needed
        # if member.bot:
        #     return
            
        try:
            self.logger.info(f"[Guild: {member.guild.name}] Member left/kicked: {member}")

            # Create embed
            embed = LogEmbed.member_leave(member)
            
            # Log to appropriate channel
            await self.logging_system.log_event(member.guild, "member-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging member leave: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Log member updates (nickname, roles)"""
        # Skip bots if needed
        # if before.bot:
        #     return
            
        # Skip if nothing relevant changed
        if (before.nick == after.nick and 
            before.roles == after.roles):
            return
            
        try:
            self.logger.info(f"[Guild: {after.guild.name}] Member updated: {after}")

            # Create embed
            embed = LogEmbed.member_update(before, after)
            
            # Log to appropriate channel
            await self.logging_system.log_event(after.guild, "member-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging member update: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Log member bans"""
        self.logger.info(f"[Guild: {guild.name}] Member banned: {user}")
        try:
            # Create embed
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"{user.mention} was banned from the server",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            
            # Add user thumbnail
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            # Try to get ban reason
            try:
                # Get ban entry
                await asyncio.sleep(1)  # Wait a moment for ban to process
                ban_entry = await guild.fetch_ban(user)
                
                if ban_entry and ban_entry.reason:
                    embed.add_field(name="Reason", value=ban_entry.reason, inline=False)
            except:
                # Failed to get ban reason
                pass
            
            # Log to appropriate channel
            await self.logging_system.log_event(guild, "mod-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging member ban: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Log member unbans"""
        self.logger.info(f"[Guild: {guild.name}] Member unbanned: {user}")
        try:
            # Create embed
            embed = discord.Embed(
                title="🔓 Member Unbanned",
                description=f"{user.mention} was unbanned from the server",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            
            # Add user thumbnail
            if user.avatar:
                embed.set_thumbnail(url=user.avatar.url)
            
            # Log to appropriate channel
            await self.logging_system.log_event(guild, "mod-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging member unban: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Log role creation"""
        try:
            executor = await self.get_audit_log_executor(role.guild, discord.AuditLogAction.role_create, role.id)
            self.logger.info(f"[Guild: {role.guild.name}] Role created: {role.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.role_create(role, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(role.guild, "role-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging role create: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Log role deletion"""
        try:
            executor = await self.get_audit_log_executor(role.guild, discord.AuditLogAction.role_delete, role.id)
            self.logger.info(f"[Guild: {role.guild.name}] Role deleted: {role.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.role_delete(role, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(role.guild, "role-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging role delete: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        """Log role updates"""
        # Skip if nothing changed
        if (before.name == after.name and
            before.color == after.color and
            before.hoist == after.hoist and
            before.mentionable == after.mentionable and
            before.permissions == after.permissions and
            before.position == after.position):
            return
            
        try:
            executor = await self.get_audit_log_executor(after.guild, discord.AuditLogAction.role_update, after.id)
            self.logger.info(f"[Guild: {after.guild.name}] Role updated: {after.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.role_update(before, after, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(after.guild, "role-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging role update: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Log channel creation"""
        try:
            executor = await self.get_audit_log_executor(channel.guild, discord.AuditLogAction.channel_create, channel.id)
            self.logger.info(f"[Guild: {channel.guild.name}] Channel created: {channel.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.channel_create(channel, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(channel.guild, "server-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging channel create: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Log channel deletion"""
        try:
            executor = await self.get_audit_log_executor(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
            self.logger.info(f"[Guild: {channel.guild.name}] Channel deleted: {channel.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.channel_delete(channel, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(channel.guild, "server-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging channel delete: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        """Log channel updates"""
        # Skip logging channels being updated
        if (hasattr(after, 'name') and 
            any(log_name in after.name for log_name in ['mod-log', 'message-log', 'member-log', 'role-log', 'voice-log', 'server-changes'])):
            if before.name == after.name:  # Only skip if the name didn't change
                return
                
        try:
            executor = await self.get_audit_log_executor(after.guild, discord.AuditLogAction.channel_update, after.id)
            self.logger.info(f"[Guild: {after.guild.name}] Channel updated: {after.name}" + (f" by {executor}" if executor else ""))

            # Create embed
            embed = LogEmbed.channel_update(before, after, executor=executor)
            
            # Log to appropriate channel
            await self.logging_system.log_event(after.guild, "server-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging channel update: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Log voice state updates"""
        # Skip if user didn't join/leave/move between channels
        if before.channel == after.channel:
            return
            
        try:
            self.logger.info(f"[Guild: {member.guild.name}] Voice state update for: {member}")

            # Create embed
            embed = LogEmbed.voice_state_update(member, before, after)
            
            # Log to appropriate channel
            await self.logging_system.log_event(member.guild, "voice-log", embed)
            
        except Exception as e:
            self.logger.error(f"Error logging voice state update: {str(e)}\n{traceback.format_exc()}")
    
    # === Logging Commands ===
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="setup_logging", description="Set up logging channels")
    @command_help("mod", "Set up logging channels for the server", "setup_logging")
    async def setup_logging(self, ctx):
        """Set up logging channels for the server"""
        await ctx.defer()
        
        # Set up logging
        result = await self.logging_system.setup_logging(ctx.guild)
        success, message, config = result
        
        # Create embed
        if success:
            embed = discord.Embed(
                title="✅ Logging Setup Complete",
                description=message,
                color=discord.Color.green()
            )
            
            # Add category details
            category_id = result["category"]
            if category_id:
                embed.add_field(
                    name="Category",
                    value=f"<#{category_id}>",
                    inline=False
                )
            
            # Add channel details
            if result["created_channels"]:
                embed.add_field(
                    name="Created Channels",
                    value=", ".join([f"#{channel}" for channel in result["created_channels"]]),
                    inline=False
                )
                
            if result["existing_channels"]:
                embed.add_field(
                    name="Existing Channels",
                    value=", ".join([f"#{channel}" for channel in result["existing_channels"]]),
                    inline=False
                )
            
        else:
            embed = discord.Embed(
                title="❌ Logging Setup Failed",
                description=message,
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="disable_logging", description="Disable logging system")
    @command_help("mod", "Disable the logging system", "disable_logging")
    async def disable_logging(self, ctx):
        """Disable logging system"""
        await ctx.defer()
        
        # Disable logging
        success, message = await self.logging_system.disable_logging(ctx.guild.id)
        
        # Create embed
        if success:
            embed = discord.Embed(
                title="✅ Logging Disabled",
                description=message,
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ Failed to Disable Logging",
                description=message,
                color=discord.Color.red()
            )
        
        await ctx.send(embed=embed)
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="logging_status", description="Show logging system status")
    @command_help("mod", "Show the current logging system status", "logging_status")
    async def logging_status(self, ctx):
        """Show logging system status"""
        await ctx.defer()
        
        # Get config
        config = await self.logging_system.get_config(ctx.guild.id)
        
        # Create embed
        embed = discord.Embed(
            title="🛡️ Logging System Status",
            description=f"Logging is currently **{'ENABLED' if config.get('enabled', False) else 'DISABLED'}**",
            color=discord.Color.blue()
        )
        
        # Add category
        category_id = config.get("category_id")
        category = ctx.guild.get_channel(category_id) if category_id else None
        
        embed.add_field(
            name="Category",
            value=f"{category.mention} (`{category.id}`)" if category else "Not set",
            inline=False
        )
        
        # Add channel status
        channels_text = ""
        for log_type, channel_id in config.get("channels", {}).items():
            channel = ctx.guild.get_channel(channel_id) if channel_id else None
            
            if log_type == "mod-log":
                emoji = "🛡️"
                description = "Moderator actions"
            elif log_type == "message-log":
                emoji = "💬"
                description = "Message edits and deletions"
            elif log_type == "member-log":
                emoji = "👤"
                description = "Member joins, leaves, and updates"
            elif log_type == "role-log":
                emoji = "🏷️"
                description = "Role changes"
            elif log_type == "voice-log":
                emoji = "🔊"
                description = "Voice channel activity"
            elif log_type == "server-log":
                emoji = "⚙️"
                description = "Server changes"
            else:
                emoji = "📋"
                description = "Logging"
                
            setting_key = f"log_{log_type.replace('-', '_')}"
            enabled = config.get("settings", {}).get(setting_key, True)
            status = "✅" if enabled else "❌"
            
            if channel:
                channels_text += f"{status} {emoji} {channel.mention} (`{channel.id}`) - {description}\n"
            else:
                channels_text += f"{status} {emoji} Not set - {description}\n"
        
        embed.add_field(name="Log Channels", value=channels_text if channels_text else "No channels configured", inline=False)
        
        await ctx.send(embed=embed)


# Setup function
async def setup(bot):
    await bot.add_cog(ServerLogging(bot))