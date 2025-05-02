import discord
import asyncio
import datetime
import json
import os
import traceback
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
import re
import difflib


class LogEmbed:
    """Utility class for creating log embeds"""
    
    @staticmethod
    def message_delete(message):
        """Create an embed for a deleted message"""
        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=f"Message by {message.author.mention} was deleted in {message.channel.mention}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        # Add message content if available
        if message.content:
            if len(message.content) > 1024:
                embed.add_field(name="Content", value=message.content[:1020] + "...", inline=False)
            else:
                embed.add_field(name="Content", value=message.content, inline=False)
                
        # Add attachments if any
        if message.attachments:
            attachments = "\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])
            if len(attachments) > 1024:
                attachments = attachments[:1020] + "..."
            embed.add_field(name="Attachments", value=attachments, inline=False)
            
        # Add author info
        embed.add_field(name="Author", value=f"{message.author} ({message.author.id})", inline=True)
        embed.add_field(name="Channel", value=f"{message.channel.name} ({message.channel.id})", inline=True)
        
        # Add message ID and timestamp
        embed.add_field(name="Message ID", value=message.id, inline=True)
        embed.set_footer(text=f"Message sent at {message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Add author thumbnail
        if message.author.avatar:
            embed.set_thumbnail(url=message.author.avatar.url)
            
        return embed
    
    @staticmethod
    def message_edit(before, after):
        """Create an embed for an edited message"""
        embed = discord.Embed(
            title="✏️ Message Edited",
            description=f"Message by {before.author.mention} was edited in {before.channel.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        
        # Add before content
        if before.content:
            if len(before.content) > 1024:
                embed.add_field(name="Before", value=before.content[:1020] + "...", inline=False)
            else:
                embed.add_field(name="Before", value=before.content, inline=False)
        
        # Add after content
        if after.content:
            if len(after.content) > 1024:
                embed.add_field(name="After", value=after.content[:1020] + "...", inline=False)
            else:
                embed.add_field(name="After", value=after.content, inline=False)
                
        # Add author info
        embed.add_field(name="Author", value=f"{before.author} ({before.author.id})", inline=True)
        embed.add_field(name="Channel", value=f"{before.channel.name} ({before.channel.id})", inline=True)
        
        # Add message ID and timestamp
        embed.add_field(name="Message ID", value=before.id, inline=True)
        embed.add_field(name="Jump to Message", value=f"[Click Here]({after.jump_url})", inline=True)
        
        # Add author thumbnail
        if before.author.avatar:
            embed.set_thumbnail(url=before.author.avatar.url)
            
        return embed
    
    @staticmethod
    def member_join(member):
        """Create an embed for a member join event"""
        embed = discord.Embed(
            title="👋 Member Joined",
            description=f"{member.mention} joined the server",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        # Add member info
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
        
        # Add account creation date
        created_at = member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        embed.add_field(name="Account Created", value=created_at, inline=True)
        
        # Calculate account age
        account_age = datetime.datetime.now() - member.created_at.replace(tzinfo=None)
        days = account_age.days
        embed.add_field(name="Account Age", value=f"{days} days", inline=True)
        
        # Add member thumbnail
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        return embed
    
    @staticmethod
    def member_leave(member):
        """Create an embed for a member leave event"""
        embed = discord.Embed(
            title="👋 Member Left",
            description=f"{member.mention} left the server",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        # Add member info
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
        
        # Add join date if available
        if member.joined_at:
            joined_at = member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            embed.add_field(name="Joined At", value=joined_at, inline=True)
            
            # Calculate member tenure
            tenure = datetime.datetime.now() - member.joined_at.replace(tzinfo=None)
            days = tenure.days
            embed.add_field(name="Member For", value=f"{days} days", inline=True)
        
        # Add roles if available
        if len(member.roles) > 1:  # More than just @everyone
            roles = ", ".join([role.name for role in member.roles if role.name != "@everyone"])
            if len(roles) > 1024:
                roles = roles[:1020] + "..."
            embed.add_field(name="Roles", value=roles, inline=False)
        
        # Add member thumbnail
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        return embed
    
    @staticmethod
    def member_update(before, after):
        """Create an embed for a member update event"""
        embed = discord.Embed(
            title="👤 Member Updated",
            description=f"{after.mention} was updated",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Check nickname change
        if before.nick != after.nick:
            embed.add_field(
                name="Nickname Changed",
                value=f"Before: {before.nick or 'None'}\nAfter: {after.nick or 'None'}",
                inline=False
            )
        
        # Check role changes
        if before.roles != after.roles:
            # Find added roles
            added_roles = [role for role in after.roles if role not in before.roles]
            if added_roles:
                roles_text = ", ".join([role.name for role in added_roles])
                embed.add_field(name="Roles Added", value=roles_text, inline=False)
                
            # Find removed roles
            removed_roles = [role for role in before.roles if role not in after.roles]
            if removed_roles:
                roles_text = ", ".join([role.name for role in removed_roles])
                embed.add_field(name="Roles Removed", value=roles_text, inline=False)
        
        # Add member info
        embed.add_field(name="Member", value=f"{after} ({after.id})", inline=True)
        
        # Add member thumbnail
        if after.avatar:
            embed.set_thumbnail(url=after.avatar.url)
            
        return embed
    
    @staticmethod
    def role_create(role):
        """Create an embed for a role creation event"""
        embed = discord.Embed(
            title="🎭 Role Created",
            description=f"Role {role.mention} was created",
            color=role.color,
            timestamp=datetime.datetime.now()
        )
        
        # Add role info
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=f"#{role.color.value:06x}", inline=True)
        embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        
        return embed
    
    @staticmethod
    def role_delete(role):
        """Create an embed for a role deletion event"""
        embed = discord.Embed(
            title="🎭 Role Deleted",
            description=f"Role **{role.name}** was deleted",
            color=role.color,
            timestamp=datetime.datetime.now()
        )
        
        # Add role info
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=f"#{role.color.value:06x}", inline=True)
        embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
        embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
        embed.add_field(name="Position", value=str(role.position), inline=True)
        
        return embed
    
    @staticmethod
    def role_update(before, after):
        """Create an embed for a role update event"""
        embed = discord.Embed(
            title="🎭 Role Updated",
            description=f"Role {after.mention} was updated",
            color=after.color,
            timestamp=datetime.datetime.now()
        )
        
        # Check name change
        if before.name != after.name:
            embed.add_field(
                name="Name Changed",
                value=f"Before: {before.name}\nAfter: {after.name}",
                inline=False
            )
        
        # Check color change
        if before.color != after.color:
            embed.add_field(
                name="Color Changed",
                value=f"Before: #{before.color.value:06x}\nAfter: #{after.color.value:06x}",
                inline=False
            )
        
        # Check hoist change
        if before.hoist != after.hoist:
            embed.add_field(
                name="Hoisted Changed",
                value=f"Before: {before.hoist}\nAfter: {after.hoist}",
                inline=False
            )
        
        # Check mentionable change
        if before.mentionable != after.mentionable:
            embed.add_field(
                name="Mentionable Changed",
                value=f"Before: {before.mentionable}\nAfter: {after.mentionable}",
                inline=False
            )
        
        # Check position change
        if before.position != after.position:
            embed.add_field(
                name="Position Changed",
                value=f"Before: {before.position}\nAfter: {after.position}",
                inline=False
            )
        
        # Add role info
        embed.add_field(name="ID", value=after.id, inline=True)
        
        return embed
    
    @staticmethod
    def channel_create(channel):
        """Create an embed for a channel creation event"""
        embed = discord.Embed(
            title="📝 Channel Created",
            description=f"Channel {channel.mention} was created",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        # Add channel info
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="ID", value=channel.id, inline=True)
        
        # Add channel type
        type_name = str(channel.type).replace('_', ' ').title()
        embed.add_field(name="Type", value=type_name, inline=True)
        
        # Add category if available
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        
        return embed
    
    @staticmethod
    def channel_delete(channel):
        """Create an embed for a channel deletion event"""
        embed = discord.Embed(
            title="📝 Channel Deleted",
            description=f"Channel **{channel.name}** was deleted",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        # Add channel info
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="ID", value=channel.id, inline=True)
        
        # Add channel type
        type_name = str(channel.type).replace('_', ' ').title()
        embed.add_field(name="Type", value=type_name, inline=True)
        
        # Add category if available
        if hasattr(channel, 'category') and channel.category:
            embed.add_field(name="Category", value=channel.category.name, inline=True)
        
        return embed
    
    @staticmethod
    def channel_update(before, after):
        """Create an embed for a channel update event"""
        embed = discord.Embed(
            title="📝 Channel Updated",
            description=f"Channel {after.mention} was updated",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Check name change
        if before.name != after.name:
            embed.add_field(
                name="Name Changed",
                value=f"Before: {before.name}\nAfter: {after.name}",
                inline=False
            )
        
        # Check topic change for text channels
        if hasattr(before, 'topic') and hasattr(after, 'topic') and before.topic != after.topic:
            # Handle None values
            before_topic = before.topic or "None"
            after_topic = after.topic or "None"
            
            # Truncate long topics
            if len(before_topic) > 500:
                before_topic = before_topic[:500] + "..."
            if len(after_topic) > 500:
                after_topic = after_topic[:500] + "..."
                
            embed.add_field(
                name="Topic Changed",
                value=f"Before: {before_topic}\nAfter: {after_topic}",
                inline=False
            )
        
        # Check category change
        if hasattr(before, 'category') and hasattr(after, 'category'):
            before_category = before.category.name if before.category else "None"
            after_category = after.category.name if after.category else "None"
            
            if before_category != after_category:
                embed.add_field(
                    name="Category Changed",
                    value=f"Before: {before_category}\nAfter: {after_category}",
                    inline=False
                )
        
        # Add position change
        if before.position != after.position:
            embed.add_field(
                name="Position Changed",
                value=f"Before: {before.position}\nAfter: {after.position}",
                inline=False
            )
            
        # Add NSFW change for text channels
        if hasattr(before, 'nsfw') and hasattr(after, 'nsfw') and before.nsfw != after.nsfw:
            embed.add_field(
                name="NSFW Changed",
                value=f"Before: {before.nsfw}\nAfter: {after.nsfw}",
                inline=False
            )
            
        # Add slowmode change for text channels
        if hasattr(before, 'slowmode_delay') and hasattr(after, 'slowmode_delay') and before.slowmode_delay != after.slowmode_delay:
            before_delay = f"{before.slowmode_delay} seconds" if before.slowmode_delay else "Off"
            after_delay = f"{after.slowmode_delay} seconds" if after.slowmode_delay else "Off"
            
            embed.add_field(
                name="Slowmode Changed",
                value=f"Before: {before_delay}\nAfter: {after_delay}",
                inline=False
            )
        
        # Add channel info
        embed.add_field(name="ID", value=after.id, inline=True)
        
        return embed
    
    @staticmethod
    def voice_state_update(member, before, after):
        """Create an embed for a voice state update event"""
        # Determine the action
        if not before.channel and after.channel:
            action = "joined"
            color = discord.Color.green()
        elif before.channel and not after.channel:
            action = "left"
            color = discord.Color.red()
        elif before.channel and after.channel and before.channel != after.channel:
            action = "moved"
            color = discord.Color.blue()
        else:
            # No channel change
            return None
            
        embed = discord.Embed(
            title="🔊 Voice Update",
            timestamp=datetime.datetime.now(),
            color=color
        )
        
        # Set description based on action
        if action == "joined":
            embed.description = f"{member.mention} joined voice channel {after.channel.mention}"
        elif action == "left":
            embed.description = f"{member.mention} left voice channel {before.channel.mention}"
        elif action == "moved":
            embed.description = f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}"
            
        # Add member info
        embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
        
        # Add additional voice state changes
        changes = []
        
        if before.deaf != after.deaf:
            changes.append(f"Server Deafened: {before.deaf} → {after.deaf}")
            
        if before.mute != after.mute:
            changes.append(f"Server Muted: {before.mute} → {after.mute}")
            
        if before.self_deaf != after.self_deaf:
            changes.append(f"Self Deafened: {before.self_deaf} → {after.self_deaf}")
            
        if before.self_mute != after.self_mute:
            changes.append(f"Self Muted: {before.self_mute} → {after.self_mute}")
            
        if before.self_stream != after.self_stream:
            changes.append(f"Streaming: {before.self_stream} → {after.self_stream}")
            
        if before.self_video != after.self_video:
            changes.append(f"Video: {before.self_video} → {after.self_video}")
            
        if changes:
            embed.add_field(name="Status Changes", value="\n".join(changes), inline=False)
            
        # Add member thumbnail
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
            
        return embed


class LoggingSystem:
    """Core system for server event logging"""
    
    # Define standard category and channels
    DEFAULT_CATEGORY = "🛡️ Botler Logs"
    LOG_CHANNELS = {
        "mod-log": {
            "name": "mod-log",
            "topic": "Moderator actions such as bans, kicks, and timeouts",
            "position": 0
        },
        "message-log": {
            "name": "message-log",
            "topic": "Message edits and deletions",
            "position": 1
        },
        "member-log": {
            "name": "member-log",
            "topic": "Member joins, leaves, and profile updates",
            "position": 2
        },
        "role-log": {
            "name": "role-log",
            "topic": "Role creation, deletion, and updates",
            "position": 3
        },
        "voice-log": {
            "name": "voice-log",
            "topic": "Voice channel activity and updates",
            "position": 4
        },
        "server-log": {
            "name": "server-log",
            "topic": "Server setting changes and updates",
            "position": 5
        }
    }
    
    # Map event types to log channel types
    LOG_TYPES = {
        "message": "message-log",
        "member": "member-log",
        "role": "role-log",
        "voice": "voice-log",
        "server": "server-log",
        "moderation": "mod-log"
    }
    
    # Event to channel type mapping for consistency
    EVENT_TO_CHANNEL = {
        "message": "message-log",  # For message events
        "member": "member-log",    # For member events
        "moderation": "mod-log",   # For moderation events
        "role": "role-log",        # For role events
        "voice": "voice-log",      # For voice events
        "server": "server-log"     # For server events
    }
    
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        
        # Set up data directory
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Configuration cache
        self.configs = {}
        
        # Default configuration
        self.DEFAULT_CONFIG = {
            "enabled": True,
            "category_id": None,
            "channels": {
                "mod": None,
                "message": None,
                "member": None,
                "role": None,
                "voice": None,
                "server": None
            },
            "webhook_urls": {},
            "settings": {
                "log_message_edits": True,
                "log_message_deletes": True,
                "log_message_bulk_deletes": True,
                "log_member_joins": True,
                "log_member_leaves": True,
                "log_member_updates": True,
                "log_member_bans": True,
                "log_member_unbans": True,
                "log_member_timeouts": True,
                "log_role_create": True,
                "log_role_delete": True,
                "log_role_updates": True,
                "log_channel_create": True,
                "log_channel_delete": True,
                "log_channel_updates": True,
                "log_voice_joins": True,
                "log_voice_leaves": True,
                "log_voice_moves": True,
                "log_server_updates": True,
                "log_emoji_updates": True,
                "include_invite_info": True,
                "include_message_content": True,
                "store_deleted_messages": True,
                "message_deletion_history": 100, # number of deleted messages to track per channel
                "colors": {
                    "create": 0x43B581,  # Green
                    "delete": 0xF04747,  # Red
                    "update": 0xFAA61A,  # Orange/Yellow  
                    "join": 0x43B581,    # Green
                    "leave": 0xF04747,   # Red
                    "info": 0x7289DA     # Blurple
                }
            },
            "ignored_channels": [],
            "ignored_categories": [],
            "ignored_users": []
        }
        
        # Cache for deleted messages (for edit tracking)
        self.deleted_messages = {}
    
    async def get_config(self, guild_id: int) -> Dict[str, Any]:
        """Get logging configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            Logging configuration dictionary
        """
        # Check cache first
        if guild_id in self.configs:
            return self.configs[guild_id]
            
        # Load from file
        config_path = self.data_dir / f"logging_config_{guild_id}.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Cache config
                self.configs[guild_id] = config
                return config
                
            except Exception as e:
                self.logger.error(f"Error loading logging config for {guild_id}: {str(e)}")
        
        # Create default config
        default_config = self.DEFAULT_CONFIG.copy()
        
        # Save as new config
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving default logging config for {guild_id}: {str(e)}")
        
        # Cache config
        self.configs[guild_id] = default_config
        return default_config
    
    async def save_config(self, guild_id: int, config: Dict[str, Any]) -> bool:
        """Save logging configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            config: Logging configuration dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create backup of existing config
            config_path = self.data_dir / f"logging_config_{guild_id}.json"
            
            if config_path.exists():
                backup_path = self.data_dir / f"logging_config_{guild_id}_backup.json"
                
                with open(config_path, 'r', encoding='utf-8') as f_in:
                    with open(backup_path, 'w', encoding='utf-8') as f_out:
                        f_out.write(f_in.read())
            
            # Update cache
            self.configs[guild_id] = config
            
            # Save to file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving logging config for {guild_id}: {str(e)}")
            return False
    
    async def setup_logging(self, guild: discord.Guild, create_missing: bool = True) -> Tuple[bool, str, Dict[str, Any]]:
        """Set up logging channels for a guild
        
        Args:
            guild: The Discord guild
            create_missing: Whether to create missing channels
            
        Returns:
            Tuple of (success, message, config)
        """
        try:
            # Get config
            config = await self.get_config(guild.id)
            
            # Check permissions
            if not guild.me.guild_permissions.manage_channels:
                return (False, "Bot missing manage_channels permission", {
                    "enabled": False,
                    "category_id": None,
                    "channels": {}
                })
            
            # Track results
            created_channels = []
            existing_channels = []
            error = None
            category_status = None
            
            # Check for existing category
            category = None
            category_id = config["category_id"]
            
            if category_id:
                category = guild.get_channel(category_id)
            
            # If category doesn't exist, check by name as a fallback only
            if not category:
                for cat in guild.categories:
                    if cat.name == self.DEFAULT_CATEGORY:
                        category = cat
                        config["category_id"] = cat.id
                        break
            
            # Create category if not found and creation is enabled
            if not category and create_missing:
                try:
                    # Create permissions - only staff can see these logs
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, 
                                                             embed_links=True, attach_files=True,
                                                             manage_channels=True, manage_webhooks=True)
                    }
                    
                    # Add permissions for admin roles
                    for role in guild.roles:
                        if role.permissions.administrator or role.permissions.manage_guild:
                            overwrites[role] = discord.PermissionOverwrite(read_messages=True)
                    
                    # Create category
                    category = await guild.create_category(
                        name=self.DEFAULT_CATEGORY,
                        overwrites=overwrites,
                        reason="Botler logging setup"
                    )
                    
                    # Update config
                    config["category_id"] = category.id
                    category_status = "created"
                    
                except Exception as e:
                    self.logger.error(f"Error creating log category: {str(e)}")
                    
                    return (False, f"Failed to create log category: {str(e)}", {
                        "enabled": False,
                        "category_id": None,
                        "channels": {}
                    })
            
            elif category:
                category_status = "existing"
            else:
                category_status = None
            
            # Check for and create channels
            for channel_id, channel_info in self.LOG_CHANNELS.items():
                channel_name = channel_info["name"]
                
                # Check if channel exists in config
                config_channel_id = config["channels"].get(channel_id)
                channel = None
                
                if config_channel_id:
                    channel = guild.get_channel(config_channel_id)
                
                # If channel doesn't exist by ID, check by name in category as a fallback only
                if not channel and category:
                    for text_channel in category.text_channels:
                        if text_channel.name == channel_name:
                            channel = text_channel
                            config["channels"][channel_id] = text_channel.id
                            self.logger.info(f"Found existing channel {channel_name} with ID {text_channel.id}")
                            break
                
                # Create channel if not found and creation is enabled
                if not channel and create_missing and category:
                    try:
                        # Create the channel
                        channel = await category.create_text_channel(
                            name=channel_name,
                            topic=channel_info["topic"],
                            position=channel_info["position"],
                            reason="Botler logging setup"
                        )
                        
                        # Update config
                        config["channels"][channel_id] = channel.id
                        created_channels.append(channel_name)
                        
                    except Exception as e:
                        self.logger.error(f"Error creating log channel {channel_name}: {str(e)}")
                        error = f"Partial setup: Error with {channel_name}"
                
                elif channel:
                    existing_channels.append(channel_name)
            
            # Save updated config
            await self.save_config(guild.id, config)
            
            # Create result message
            message = "Logging channels have been set up successfully."
            
            if created_channels:
                message += f"\nCreated channels: {', '.join(created_channels)}"
            
            if existing_channels:
                message += f"\nExisting channels: {', '.join(existing_channels)}"
                
            if error:
                message += f"\nWarning: {error}"
                
            return (True, message, config)
            
        except Exception as e:
            self.logger.error(f"Error setting up logging: {str(e)}\n{traceback.format_exc()}")
            
            return (False, f"Failed to set up logging: {str(e)}", {
                "enabled": False,
                "category_id": None,
                "channels": {}
            })
    
    async def disable_logging(self, guild_id: int) -> Tuple[bool, str]:
        """Disable logging for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get config
            config = await self.get_config(guild_id)
            
            # Disable logging
            config["enabled"] = False
            
            # Save config
            await self.save_config(guild_id, config)
            
            return (True, "Logging has been disabled for this server.")
            
        except Exception as e:
            self.logger.error(f"Error disabling logging: {str(e)}")
            return (False, f"Error disabling logging: {str(e)}")
    
    async def get_log_channel(self, guild: discord.Guild, channel_type: str) -> Optional[discord.TextChannel]:
        """Get a specific log channel
        
        Args:
            guild: The Discord guild
            channel_type: Type of log channel to get (e.g., "message", "member")
            
        Returns:
            Discord text channel or None if not found/configured
        """
        try:
            # Get config
            config = await self.get_config(guild.id)
            
            # Check if enabled
            if not config.get("enabled", True):
                return None
            
            # Map to the correct log channel type if needed
            log_channel_type = self.LOG_TYPES.get(channel_type, channel_type)
            
            # Check if channel type is valid
            if log_channel_type not in self.LOG_CHANNELS:
                return None
                
            # Get channel ID
            channel_id = config["channels"].get(log_channel_type)
            
            if not channel_id:
                return None
                
            # Get channel
            channel = guild.get_channel(channel_id)
            
            return channel
            
        except Exception as e:
            self.logger.error(f"Error getting log channel: {str(e)}")
            return None
    
    async def toggle_log_type(self, guild_id: int, log_type: str, enabled: bool) -> Tuple[bool, str]:
        """Toggle a specific log type on or off
        
        Args:
            guild_id: The Discord guild ID
            log_type: The log type to toggle
            enabled: Whether to enable or disable the log type
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate log type
            if log_type not in self.LOG_TYPES and log_type not in self.EVENT_TO_CHANNEL:
                return (False, f"Invalid log type: {log_type}")
                
            # Get config
            config = await self.get_config(guild_id)
            
            # Make sure log_types dict exists
            if "log_types" not in config:
                config["log_types"] = {}
                
            # Set the log type status
            config["log_types"][log_type] = enabled
            
            # Save config
            await self.save_config(guild_id, config)
            
            status = "enabled" if enabled else "disabled"
            return (True, f"Log type '{log_type}' has been {status}.")
            
        except Exception as e:
            self.logger.error(f"Error toggling log type: {str(e)}")
            return (False, f"Error toggling log type: {str(e)}")
    
    async def should_log_event(self, guild: discord.Guild, event_type: str,
                               channel: discord.abc.GuildChannel = None,
                               user: discord.Member = None) -> bool:
        """Check if an event should be logged
        
        Args:
            guild: The Discord guild
            event_type: Type of event to check
            channel: Optional channel involved in the event
            user: Optional user involved in the event
            
        Returns:
            True if event should be logged, False otherwise
        """
        try:
            # Get config
            config = await self.get_config(guild.id)
            
            # Check if logging is enabled
            if not config.get("enabled", True):
                return False
            
            # Check if specific event type is enabled
            event_setting = f"log_{event_type}"
            if not config["settings"].get(event_setting, True):
                return False
                
            # Check ignored channels
            if channel:
                channel_id = channel.id
                
                # Check if specific channel is ignored
                if channel_id in config.get("ignored_channels", []):
                    return False
                    
                # Check if channel's category is ignored
                if channel.category and channel.category.id in config.get("ignored_categories", []):
                    return False
            
            # Check ignored users
            if user and user.id in config.get("ignored_users", []):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking if event should be logged: {str(e)}")
            return False
    
    async def log_event(self, guild: discord.Guild, channel_type: str, embed: discord.Embed) -> bool:
        """Log an event to the specified channel
        
        Args:
            guild: The Discord guild
            channel_type: Type of log channel to use (e.g., "message", "member")
            embed: Embed to send
            
        Returns:
            True if logged successfully, False otherwise
        """
        try:
            # Get log channel
            channel = await self.get_log_channel(guild, channel_type)
            
            if not channel:
                self.logger.warning(f"No log channel found for {channel_type} in guild {guild.id}")
                return False
                
            # Send embed
            try:
                if channel.permissions_for(guild.me).send_messages:
                    await channel.send(embed=embed)
                else:
                    self.logger.warning(f"Missing permissions to send in #{channel.name} ({channel.id}) in guild {guild.id}")
            except discord.Forbidden:
                self.logger.warning(f"Forbidden: Cannot send to #{channel.name} ({channel.id}) in guild {guild.id}")
            except discord.HTTPException as e:
                self.logger.error(f"HTTPException while sending log message: {e}")

            
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging event: {str(e)}")
            return False
    
    async def track_deleted_message(self, message: discord.Message) -> None:
        """Track a deleted message for later reference
        
        Args:
            message: The Discord message that was deleted
        """
        if not message.guild:
            return
            
        try:
            # Get config
            config = await self.get_config(message.guild.id)
            
            # Check if storing deleted messages is enabled
            if not config["settings"].get("store_deleted_messages", True):
                return
                
            # Initialize guild storage if not exists
            guild_id = str(message.guild.id)
            
            if guild_id not in self.deleted_messages:
                self.deleted_messages[guild_id] = {}
                
            # Initialize channel storage if not exists
            channel_id = str(message.channel.id)
            
            if channel_id not in self.deleted_messages[guild_id]:
                self.deleted_messages[guild_id][channel_id] = []
                
            # Add message to tracking
            message_data = {
                "id": message.id,
                "content": message.content,
                "author_id": message.author.id,
                "author_name": str(message.author),
                "created_at": message.created_at.timestamp(),
                "deleted_at": datetime.datetime.now().timestamp(),
                "attachments": [a.url for a in message.attachments],
                "embeds": [e.to_dict() for e in message.embeds]
            }
            
            channel_messages = self.deleted_messages[guild_id][channel_id]
            
            # Add to list, maintaining size limit
            max_history = config["settings"].get("message_deletion_history", 100)
            
            channel_messages.append(message_data)
            
            if len(channel_messages) > max_history:
                channel_messages.pop(0)
                
            self.deleted_messages[guild_id][channel_id] = channel_messages
            
        except Exception as e:
            self.logger.error(f"Error tracking deleted message: {str(e)}")
    
    async def get_invite_uses(self, guild: discord.Guild) -> Dict[str, int]:
        """Get invite usage counts
        
        Args:
            guild: The Discord guild
            
        Returns:
            Dictionary of invite codes and their uses
        """
        try:
            # Check permissions
            if not guild.me.guild_permissions.manage_guild:
                return {}
                
            # Get all invites
            invites = await guild.invites()
            
            # Create dictionary of invite usage
            invite_uses = {}
            
            for invite in invites:
                invite_uses[invite.code] = invite.uses
                
            return invite_uses
            
        except Exception as e:
            self.logger.error(f"Error getting invite uses: {str(e)}")
            return {}
    
    # ----- Message Events -----
    
    async def create_message_edit_embed(self, before: discord.Message, after: discord.Message) -> discord.Embed:
        """Create an embed for a message edit event
        
        Args:
            before: Original message
            after: Edited message
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(after.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Message Edited",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{after.author} ({after.author.id})",
            icon_url=after.author.display_avatar.url
        )
        
        # Set footer
        embed.set_footer(text=f"Channel: #{after.channel.name} | Message ID: {after.id}")
        
        # Add channel link
        embed.add_field(
            name="Channel",
            value=f"[#{after.channel.name}]({after.jump_url})",
            inline=True
        )
        
        # Add message content
        if before.content and after.content and before.content != after.content:
            # If content is too long, truncate it
            if len(before.content) > 1024:
                before_content = before.content[:1021] + "..."
            else:
                before_content = before.content
                
            if len(after.content) > 1024:
                after_content = after.content[:1021] + "..."
            else:
                after_content = after.content
            
            embed.add_field(
                name="Before",
                value=before_content or "[No content]",
                inline=False
            )
            
            embed.add_field(
                name="After",
                value=after_content or "[No content]",
                inline=False
            )
            
            # Add diff if moderate size
            if len(before.content) < 400 and len(after.content) < 400:
                diff = difflib.unified_diff(
                    before.content.splitlines(),
                    after.content.splitlines(),
                    lineterm=""
                )
                
                diff_text = "\n".join([line for line in diff if line.startswith(('+', '-'))])
                
                if diff_text:
                    embed.add_field(
                        name="Differences",
                        value=f"```diff\n{diff_text[:1014]}```",
                        inline=False
                    )
        
        # Add attachment changes
        before_attachments = set([a.url for a in before.attachments])
        after_attachments = set([a.url for a in after.attachments])
        
        # Attachments removed
        removed_attachments = before_attachments - after_attachments
        if removed_attachments:
            embed.add_field(
                name="Attachments Removed",
                value="\n".join([f"[Attachment]({url})" for url in list(removed_attachments)[:3]]),
                inline=False
            )
            
        # Attachments added
        added_attachments = after_attachments - before_attachments
        if added_attachments:
            embed.add_field(
                name="Attachments Added",
                value="\n".join([f"[Attachment]({url})" for url in list(added_attachments)[:3]]),
                inline=False
            )
        
        # Add embed changes if any
        before_embeds = len(before.embeds)
        after_embeds = len(after.embeds)
        
        if before_embeds != after_embeds:
            embed.add_field(
                name="Embeds Changed",
                value=f"Before: {before_embeds} | After: {after_embeds}",
                inline=True
            )
        
        return embed
    
    async def create_message_delete_embed(self, message: discord.Message, bulk: bool = False) -> discord.Embed:
        """Create an embed for a message delete event
        
        Args:
            message: Deleted message
            bulk: Whether this is part of bulk delete
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(message.guild.id)
        colors = config["settings"]["colors"]
        include_content = config["settings"].get("include_message_content", True)
        
        # Create embed
        embed = discord.Embed(
            title="Message Deleted" if not bulk else "Message Bulk Deleted",
            color=colors.get("delete", 0xF04747),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{message.author} ({message.author.id})",
            icon_url=message.author.display_avatar.url
        )
        
        # Set footer
        embed.set_footer(text=f"Channel: #{message.channel.name} | Message ID: {message.id}")
        
        # Add channel info
        embed.add_field(
            name="Channel",
            value=f"#{message.channel.name}",
            inline=True
        )
        
        # Add message creation time
        embed.add_field(
            name="Created",
            value=f"<t:{int(message.created_at.timestamp())}:R>",
            inline=True
        )
        
        # Add message content if allowed
        if include_content and message.content:
            # Truncate if too long
            if len(message.content) > 1024:
                content = message.content[:1021] + "..."
            else:
                content = message.content
                
            embed.add_field(
                name="Content",
                value=content,
                inline=False
            )
        
        # Add attachments if any
        if message.attachments:
            attachments_text = "\n".join([f"[{a.filename}]({a.proxy_url})" for a in message.attachments[:3]])
            
            if len(message.attachments) > 3:
                attachments_text += f"\n+{len(message.attachments) - 3} more attachments"
                
            embed.add_field(
                name="Attachments",
                value=attachments_text,
                inline=False
            )
        
        # Add embeds count if any
        if message.embeds:
            embed.add_field(
                name="Embeds",
                value=f"{len(message.embeds)} embeds were in this message",
                inline=False
            )
        
        return embed
    
    # ----- Member Events -----
    
    async def create_member_join_embed(self, member: discord.Member) -> discord.Embed:
        """Create an embed for a member join event
        
        Args:
            member: The member who joined
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(member.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} {member}",
            color=colors.get("join", 0x43B581),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{member} ({member.id})",
            icon_url=member.display_avatar.url
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Set footer
        embed.set_footer(text=f"User ID: {member.id}")
        
        # Add account creation time
        created_ago = (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days
        
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:F>\n{created_ago} days ago",
            inline=False
        )
        
        # Add join position
        join_position = sorted(member.guild.members, key=lambda m: m.joined_at or datetime.datetime.now()).index(member) + 1
        
        embed.add_field(
            name="Join Position",
            value=f"{join_position:,} of {len(member.guild.members):,}",
            inline=True
        )
        
        # Add mention if new account (< 7 days)
        if created_ago < 7:
            embed.add_field(
                name="⚠️ New Account",
                value=f"This account was created {created_ago} days ago",
                inline=True
            )
        
        return embed
    
    async def create_member_leave_embed(self, member: discord.Member) -> discord.Embed:
        """Create an embed for a member leave event
        
        Args:
            member: The member who left
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(member.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} {member}",
            color=colors.get("leave", 0xF04747),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{member} ({member.id})",
            icon_url=member.display_avatar.url
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Set footer
        embed.set_footer(text=f"User ID: {member.id}")
        
        # Add join time if available
        if member.joined_at:
            joined_ago = (datetime.datetime.now(datetime.timezone.utc) - member.joined_at).days
            
            embed.add_field(
                name="Joined Server",
                value=f"<t:{int(member.joined_at.timestamp())}:F>\n{joined_ago} days ago",
                inline=False
            )
        
        # Add roles if any
        if member.roles[1:]:  # Exclude @everyone
            roles = ", ".join([role.mention for role in reversed(member.roles[1:])[:10]])
            
            if len(member.roles) > 11:
                roles += f" (+{len(member.roles) - 11} more)"
                
            embed.add_field(
                name=f"Roles [{len(member.roles) - 1}]",
                value=roles,
                inline=False
            )
        
        return embed
    
    async def create_member_update_embed(self, before: discord.Member, after: discord.Member) -> discord.Embed:
        """Create an embed for a member update event
        
        Args:
            before: Member before update
            after: Member after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(after.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Member Updated",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{after} ({after.id})",
            icon_url=after.display_avatar.url
        )
        
        # Set footer
        embed.set_footer(text=f"User ID: {after.id}")
        
        # Check for nickname change
        if before.nick != after.nick:
            embed.add_field(
                name="Nickname Changed",
                value=f"**Before:** {before.nick or 'None'}\n**After:** {after.nick or 'None'}",
                inline=False
            )
        
        # Check for roles change
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        
        # Roles added
        added_roles = after_roles - before_roles
        if added_roles:
            roles_text = ", ".join([role.mention for role in added_roles])
            
            embed.add_field(
                name="Roles Added",
                value=roles_text,
                inline=False
            )
        
        # Roles removed
        removed_roles = before_roles - after_roles
        if removed_roles:
            roles_text = ", ".join([role.mention for role in removed_roles])
            
            embed.add_field(
                name="Roles Removed",
                value=roles_text,
                inline=False
            )
        
        # Check for avatar change
        if before.display_avatar.url != after.display_avatar.url:
            embed.add_field(
                name="Avatar Changed",
                value=f"[Before]({before.display_avatar.url}) → [After]({after.display_avatar.url})",
                inline=False
            )
            
            # Set thumbnail to new avatar
            embed.set_thumbnail(url=after.display_avatar.url)
        
        # Check for timeout change
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                embed.add_field(
                    name="Member Timed Out",
                    value=f"Until <t:{int(after.timed_out_until.timestamp())}:F>",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Timeout Removed",
                    value="Member is no longer timed out",
                    inline=False
                )
        
        return embed
    
    async def create_member_ban_embed(self, member: Union[discord.Member, discord.User], reason: str = None) -> discord.Embed:
        """Create an embed for a member ban event
        
        Args:
            member: The member who was banned
            reason: Optional reason for the ban
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(member.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Member Banned",
            description=f"{member.mention} {member}",
            color=colors.get("delete", 0xF04747),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{member} ({member.id})",
            icon_url=member.display_avatar.url
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Set footer
        embed.set_footer(text=f"User ID: {member.id}")
        
        # Add reason if available
        if reason:
            embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )
        
        return embed
    
    async def create_member_unban_embed(self, user: discord.User, reason: str = None) -> discord.Embed:
        """Create an embed for a member unban event
        
        Args:
            user: The user who was unbanned
            reason: Optional reason for the unban
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(user.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Member Unbanned",
            description=f"{user.mention} {user}",
            color=colors.get("create", 0x43B581),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{user} ({user.id})",
            icon_url=user.display_avatar.url
        )
        
        # Set thumbnail
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Set footer
        embed.set_footer(text=f"User ID: {user.id}")
        
        # Add reason if available
        if reason:
            embed.add_field(
                name="Reason",
                value=reason,
                inline=False
            )
        
        return embed
    
    # ----- Role Events -----
    
    async def create_role_create_embed(self, role: discord.Role) -> discord.Embed:
        """Create an embed for a role create event
        
        Args:
            role: The role that was created
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(role.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Role Created",
            description=f"{role.mention} {role.name}",
            color=colors.get("create", 0x43B581),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Role ID: {role.id}")
        
        # Add role info
        embed.add_field(
            name="Color",
            value=f"#{role.color.value:06x}",
            inline=True
        )
        
        embed.add_field(
            name="Mentionable",
            value=str(role.mentionable),
            inline=True
        )
        
        embed.add_field(
            name="Displayed Separately",
            value=str(role.hoist),
            inline=True
        )
        
        embed.add_field(
            name="Position",
            value=str(role.position),
            inline=True
        )
        
        # Add permissions if any
        if role.permissions.value:
            permissions = []
            
            for perm, value in role.permissions:
                if value:
                    permissions.append(perm.replace('_', ' ').title())
            
            if permissions:
                key_perms = ", ".join(permissions[:8])
                
                if len(permissions) > 8:
                    key_perms += f" (+{len(permissions) - 8} more)"
                
                embed.add_field(
                    name="Key Permissions",
                    value=key_perms,
                    inline=False
                )
        
        return embed
    
    async def create_role_delete_embed(self, role: discord.Role) -> discord.Embed:
        """Create an embed for a role delete event
        
        Args:
            role: The role that was deleted
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(role.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Role Deleted",
            description=f"@{role.name}",
            color=colors.get("delete", 0xF04747),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Role ID: {role.id}")
        
        # Add role info
        embed.add_field(
            name="Color",
            value=f"#{role.color.value:06x}",
            inline=True
        )
        
        embed.add_field(
            name="Mentionable",
            value=str(role.mentionable),
            inline=True
        )
        
        embed.add_field(
            name="Displayed Separately",
            value=str(role.hoist),
            inline=True
        )
        
        embed.add_field(
            name="Position",
            value=str(role.position),
            inline=True
        )
        
        # Add member count
        embed.add_field(
            name="Member Count",
            value=str(len(role.members)),
            inline=True
        )
        
        # Add creation time
        embed.add_field(
            name="Created",
            value=f"<t:{int(role.created_at.timestamp())}:R>",
            inline=True
        )
        
        return embed
    
    async def create_role_update_embed(self, before: discord.Role, after: discord.Role) -> discord.Embed:
        """Create an embed for a role update event
        
        Args:
            before: Role before update
            after: Role after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(after.guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Role Updated",
            description=f"{after.mention} {after.name}",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Role ID: {after.id}")
        
        # Check for name change
        if before.name != after.name:
            embed.add_field(
                name="Name Changed",
                value=f"**Before:** {before.name}\n**After:** {after.name}",
                inline=False
            )
        
        # Check for color change
        if before.color != after.color:
            embed.add_field(
                name="Color Changed",
                value=f"**Before:** #{before.color.value:06x}\n**After:** #{after.color.value:06x}",
                inline=False
            )
        
        # Check for mentionable change
        if before.mentionable != after.mentionable:
            embed.add_field(
                name="Mentionable Changed",
                value=f"**Before:** {before.mentionable}\n**After:** {after.mentionable}",
                inline=True
            )
        
        # Check for hoist change
        if before.hoist != after.hoist:
            embed.add_field(
                name="Displayed Separately Changed",
                value=f"**Before:** {before.hoist}\n**After:** {after.hoist}",
                inline=True
            )
        
        # Check for position change
        if before.position != after.position:
            embed.add_field(
                name="Position Changed",
                value=f"**Before:** {before.position}\n**After:** {after.position}",
                inline=True
            )
        
        # Check for permission changes
        if before.permissions.value != after.permissions.value:
            # Find changes
            added_perms = []
            removed_perms = []
            
            for perm, value in after.permissions:
                before_value = getattr(before.permissions, perm)
                
                if value and not before_value:
                    added_perms.append(perm.replace('_', ' ').title())
                elif not value and before_value:
                    removed_perms.append(perm.replace('_', ' ').title())
            
            # Add fields for changes
            if added_perms:
                embed.add_field(
                    name="Permissions Added",
                    value=", ".join(added_perms),
                    inline=False
                )
            
            if removed_perms:
                embed.add_field(
                    name="Permissions Removed",
                    value=", ".join(removed_perms),
                    inline=False
                )
        
        return embed
    
    # ----- Channel Events -----
    
    async def create_channel_create_embed(self, channel: discord.abc.GuildChannel) -> discord.Embed:
        """Create an embed for a channel create event
        
        Args:
            channel: The channel that was created
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(channel.guild.id)
        colors = config["settings"]["colors"]
        
        # Determine channel type name
        if isinstance(channel, discord.TextChannel):
            channel_type = "Text Channel"
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = "Voice Channel"
        elif isinstance(channel, discord.CategoryChannel):
            channel_type = "Category"
        elif isinstance(channel, discord.StageChannel):
            channel_type = "Stage Channel"
        elif hasattr(discord, "ForumChannel") and isinstance(channel, discord.ForumChannel):
            channel_type = "Forum Channel"
        else:
            channel_type = "Channel"
        
        # Create embed
        embed = discord.Embed(
            title=f"{channel_type} Created",
            description=f"{channel.mention} {channel.name}",
            color=colors.get("create", 0x43B581),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        # Add channel info
        if channel.category:
            embed.add_field(
                name="Category",
                value=channel.category.name,
                inline=True
            )
        
        # Add specific info for each channel type
        if isinstance(channel, discord.TextChannel):
            embed.add_field(
                name="Topic",
                value=channel.topic or "None",
                inline=False
            )
            
            embed.add_field(
                name="NSFW",
                value=str(channel.is_nsfw()),
                inline=True
            )
            
            embed.add_field(
                name="Slowmode",
                value=f"{channel.slowmode_delay} seconds" if channel.slowmode_delay else "Off",
                inline=True
            )
            
        elif isinstance(channel, discord.VoiceChannel):
            embed.add_field(
                name="Bitrate",
                value=f"{channel.bitrate // 1000} kbps",
                inline=True
            )
            
            embed.add_field(
                name="User Limit",
                value=str(channel.user_limit) if channel.user_limit else "Unlimited",
                inline=True
            )
            
        elif isinstance(channel, discord.StageChannel):
            embed.add_field(
                name="Topic",
                value=channel.topic or "None",
                inline=True
            )
        
        # Add permission overwrites count
        if channel.overwrites:
            embed.add_field(
                name="Permission Overwrites",
                value=str(len(channel.overwrites)),
                inline=True
            )
        
        return embed
    
    async def create_channel_delete_embed(self, channel: discord.abc.GuildChannel) -> discord.Embed:
        """Create an embed for a channel delete event
        
        Args:
            channel: The channel that was deleted
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(channel.guild.id)
        colors = config["settings"]["colors"]
        
        # Determine channel type name
        if isinstance(channel, discord.TextChannel):
            channel_type = "Text Channel"
        elif isinstance(channel, discord.VoiceChannel):
            channel_type = "Voice Channel"
        elif isinstance(channel, discord.CategoryChannel):
            channel_type = "Category"
        elif isinstance(channel, discord.StageChannel):
            channel_type = "Stage Channel"
        elif hasattr(discord, "ForumChannel") and isinstance(channel, discord.ForumChannel):
            channel_type = "Forum Channel"
        else:
            channel_type = "Channel"
        
        # Create embed
        embed = discord.Embed(
            title=f"{channel_type} Deleted",
            description=f"#{channel.name}",
            color=colors.get("delete", 0xF04747),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Channel ID: {channel.id}")
        
        # Add channel info
        if channel.category:
            embed.add_field(
                name="Category",
                value=channel.category.name,
                inline=True
            )
        
        # Add creation time
        embed.add_field(
            name="Created",
            value=f"<t:{int(channel.created_at.timestamp())}:R>",
            inline=True
        )
        
        # Add specific info for each channel type
        if isinstance(channel, discord.TextChannel):
            if channel.topic:
                embed.add_field(
                    name="Topic",
                    value=channel.topic,
                    inline=False
                )
                
        elif isinstance(channel, discord.VoiceChannel):
            embed.add_field(
                name="Bitrate",
                value=f"{channel.bitrate // 1000} kbps",
                inline=True
            )
        
        return embed
    
    async def create_channel_update_embed(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel) -> discord.Embed:
        """Create an embed for a channel update event
        
        Args:
            before: Channel before update
            after: Channel after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(after.guild.id)
        colors = config["settings"]["colors"]
        
        # Determine channel type name
        if isinstance(after, discord.TextChannel):
            channel_type = "Text Channel"
        elif isinstance(after, discord.VoiceChannel):
            channel_type = "Voice Channel"
        elif isinstance(after, discord.CategoryChannel):
            channel_type = "Category"
        elif isinstance(after, discord.StageChannel):
            channel_type = "Stage Channel"
        elif hasattr(discord, "ForumChannel") and isinstance(after, discord.ForumChannel):
            channel_type = "Forum Channel"
        else:
            channel_type = "Channel"
        
        # Create embed
        embed = discord.Embed(
            title=f"{channel_type} Updated",
            description=f"{after.mention} {after.name}",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set footer
        embed.set_footer(text=f"Channel ID: {after.id}")
        
        # Check for name change
        if before.name != after.name:
            embed.add_field(
                name="Name Changed",
                value=f"**Before:** {before.name}\n**After:** {after.name}",
                inline=False
            )
        
        # Check for category change
        if before.category != after.category:
            before_category = before.category.name if before.category else "None"
            after_category = after.category.name if after.category else "None"
            
            embed.add_field(
                name="Category Changed",
                value=f"**Before:** {before_category}\n**After:** {after_category}",
                inline=False
            )
        
        # Check for position change
        if before.position != after.position:
            embed.add_field(
                name="Position Changed",
                value=f"**Before:** {before.position}\n**After:** {after.position}",
                inline=True
            )
        
        # Add type-specific checks
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            # Topic change
            if before.topic != after.topic:
                embed.add_field(
                    name="Topic Changed",
                    value=f"**Before:** {before.topic or 'None'}\n**After:** {after.topic or 'None'}",
                    inline=False
                )
            
            # NSFW change
            if before.is_nsfw() != after.is_nsfw():
                embed.add_field(
                    name="NSFW Changed",
                    value=f"**Before:** {before.is_nsfw()}\n**After:** {after.is_nsfw()}",
                    inline=True
                )
            
            # Slowmode change
            if before.slowmode_delay != after.slowmode_delay:
                before_slowmode = f"{before.slowmode_delay} seconds" if before.slowmode_delay else "Off"
                after_slowmode = f"{after.slowmode_delay} seconds" if after.slowmode_delay else "Off"
                
                embed.add_field(
                    name="Slowmode Changed",
                    value=f"**Before:** {before_slowmode}\n**After:** {after_slowmode}",
                    inline=True
                )
        
        elif isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
            # Bitrate change
            if before.bitrate != after.bitrate:
                embed.add_field(
                    name="Bitrate Changed",
                    value=f"**Before:** {before.bitrate // 1000} kbps\n**After:** {after.bitrate // 1000} kbps",
                    inline=True
                )
            
            # User limit change
            if before.user_limit != after.user_limit:
                before_limit = str(before.user_limit) if before.user_limit else "Unlimited"
                after_limit = str(after.user_limit) if after.user_limit else "Unlimited"
                
                embed.add_field(
                    name="User Limit Changed",
                    value=f"**Before:** {before_limit}\n**After:** {after_limit}",
                    inline=True
                )
        
        # Check permissions change
        if before.overwrites != after.overwrites:
            # Find changes
            added_overwrites = {}
            removed_overwrites = {}
            changed_overwrites = {}
            
            # Check for added or changed overwrites
            for target, overwrite in after.overwrites.items():
                target_name = target.name
                
                if target not in before.overwrites:
                    added_overwrites[target_name] = target
                elif before.overwrites[target] != overwrite:
                    changed_overwrites[target_name] = target
            
            # Check for removed overwrites
            for target, overwrite in before.overwrites.items():
                target_name = target.name
                
                if target not in after.overwrites:
                    removed_overwrites[target_name] = target
            
            # Add fields for overwrite changes
            if added_overwrites:
                targets_text = ", ".join([f"@{name}" for name in added_overwrites.keys()])
                
                embed.add_field(
                    name="Permissions Added",
                    value=targets_text if len(targets_text) <= 1024 else f"{len(added_overwrites)} overwrites added",
                    inline=False
                )
            
            if removed_overwrites:
                targets_text = ", ".join([f"@{name}" for name in removed_overwrites.keys()])
                
                embed.add_field(
                    name="Permissions Removed",
                    value=targets_text if len(targets_text) <= 1024 else f"{len(removed_overwrites)} overwrites removed",
                    inline=False
                )
            
            if changed_overwrites:
                targets_text = ", ".join([f"@{name}" for name in changed_overwrites.keys()])
                
                embed.add_field(
                    name="Permissions Changed",
                    value=targets_text if len(targets_text) <= 1024 else f"{len(changed_overwrites)} overwrites changed",
                    inline=False
                )
        
        return embed
    
    # ----- Voice Events -----
    
    async def create_voice_state_update_embed(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> discord.Embed:
        """Create an embed for a voice state update event
        
        Args:
            member: The member whose voice state changed
            before: Voice state before update
            after: Voice state after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(member.guild.id)
        colors = config["settings"]["colors"]
        
        # Determine update type and title
        if before.channel is None and after.channel is not None:
            # Joined voice
            title = "Member Joined Voice"
            color = colors.get("join", 0x43B581)
            description = f"{member.mention} joined voice channel {after.channel.mention}"
        elif before.channel is not None and after.channel is None:
            # Left voice
            title = "Member Left Voice"
            color = colors.get("leave", 0xF04747)
            description = f"{member.mention} left voice channel {before.channel.mention}"
        elif before.channel != after.channel:
            # Moved channels
            title = "Member Moved Voice Channels"
            color = colors.get("update", 0xFAA61A)
            description = f"{member.mention} moved from {before.channel.mention} to {after.channel.mention}"
        else:
            # Other changes
            title = "Voice State Updated"
            color = colors.get("update", 0xFAA61A)
            description = f"{member.mention} updated voice state in {after.channel.mention}"
        
        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=f"{member} ({member.id})",
            icon_url=member.display_avatar.url
        )
        
        # Set footer
        embed.set_footer(text=f"User ID: {member.id}")
        
        # Check for self mute/deaf changes
        if before.self_mute != after.self_mute:
            embed.add_field(
                name="Self Mute",
                value=f"**Before:** {before.self_mute}\n**After:** {after.self_mute}",
                inline=True
            )
        
        if before.self_deaf != after.self_deaf:
            embed.add_field(
                name="Self Deaf",
                value=f"**Before:** {before.self_deaf}\n**After:** {after.self_deaf}",
                inline=True
            )
        
        # Check for server mute/deaf changes
        if before.mute != after.mute:
            embed.add_field(
                name="Server Mute",
                value=f"**Before:** {before.mute}\n**After:** {after.mute}",
                inline=True
            )
        
        if before.deaf != after.deaf:
            embed.add_field(
                name="Server Deaf",
                value=f"**Before:** {before.deaf}\n**After:** {after.deaf}",
                inline=True
            )
        
        # Check for streaming/video changes
        if hasattr(before, 'self_stream') and hasattr(after, 'self_stream'):
            if before.self_stream != after.self_stream:
                embed.add_field(
                    name="Streaming",
                    value=f"**Before:** {before.self_stream}\n**After:** {after.self_stream}",
                    inline=True
                )
                
        if hasattr(before, 'self_video') and hasattr(after, 'self_video'):
            if before.self_video != after.self_video:
                embed.add_field(
                    name="Video",
                    value=f"**Before:** {before.self_video}\n**After:** {after.self_video}",
                    inline=True
                )
        
        return embed
    
    # ----- Server Events -----
    
    async def create_server_update_embed(self, before: discord.Guild, after: discord.Guild) -> discord.Embed:
        """Create an embed for a server update event
        
        Args:
            before: Guild before update
            after: Guild after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(after.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Server Updated",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=after.name,
            icon_url=after.icon.url if after.icon else None
        )
        
        # Set footer
        embed.set_footer(text=f"Server ID: {after.id}")
        
        # Check for name change
        if before.name != after.name:
            embed.add_field(
                name="Name Changed",
                value=f"**Before:** {before.name}\n**After:** {after.name}",
                inline=False
            )
        
        # Check for icon change
        if before.icon != after.icon:
            before_icon = "None" if not before.icon else f"[Icon]({before.icon.url})"
            after_icon = "None" if not after.icon else f"[Icon]({after.icon.url})"
            
            embed.add_field(
                name="Icon Changed",
                value=f"**Before:** {before_icon}\n**After:** {after_icon}",
                inline=False
            )
            
            # Set thumbnail to new icon
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
        
        # Check for banner change
        if before.banner != after.banner:
            before_banner = "None" if not before.banner else f"[Banner]({before.banner.url})"
            after_banner = "None" if not after.banner else f"[Banner]({after.banner.url})"
            
            embed.add_field(
                name="Banner Changed",
                value=f"**Before:** {before_banner}\n**After:** {after_banner}",
                inline=False
            )
        
        # Check for splash change
        if before.splash != after.splash:
            before_splash = "None" if not before.splash else f"[Splash]({before.splash.url})"
            after_splash = "None" if not after.splash else f"[Splash]({after.splash.url})"
            
            embed.add_field(
                name="Invite Splash Changed",
                value=f"**Before:** {before_splash}\n**After:** {after_splash}",
                inline=False
            )
        
        # Check for description change
        if before.description != after.description:
            embed.add_field(
                name="Description Changed",
                value=f"**Before:** {before.description or 'None'}\n**After:** {after.description or 'None'}",
                inline=False
            )
        
        # Check for verification level change
        if before.verification_level != after.verification_level:
            embed.add_field(
                name="Verification Level Changed",
                value=f"**Before:** {before.verification_level.name}\n**After:** {after.verification_level.name}",
                inline=True
            )
        
        # Check for explicit content filter change
        if before.explicit_content_filter != after.explicit_content_filter:
            embed.add_field(
                name="Content Filter Changed",
                value=f"**Before:** {before.explicit_content_filter.name}\n**After:** {after.explicit_content_filter.name}",
                inline=True
            )
        
        # Check for default notifications change
        if before.default_notifications != after.default_notifications:
            embed.add_field(
                name="Default Notifications Changed",
                value=f"**Before:** {before.default_notifications.name}\n**After:** {after.default_notifications.name}",
                inline=True
            )
        
        # Check for AFK timeout change
        if before.afk_timeout != after.afk_timeout:
            embed.add_field(
                name="AFK Timeout Changed",
                value=f"**Before:** {before.afk_timeout} seconds\n**After:** {after.afk_timeout} seconds",
                inline=True
            )
        
        # Check for AFK channel change
        if before.afk_channel != after.afk_channel:
            before_afk = "None" if not before.afk_channel else before.afk_channel.mention
            after_afk = "None" if not after.afk_channel else after.afk_channel.mention
            
            embed.add_field(
                name="AFK Channel Changed",
                value=f"**Before:** {before_afk}\n**After:** {after_afk}",
                inline=True
            )
        
        # Check for system channel change
        if before.system_channel != after.system_channel:
            before_system = "None" if not before.system_channel else before.system_channel.mention
            after_system = "None" if not after.system_channel else after.system_channel.mention
            
            embed.add_field(
                name="System Channel Changed",
                value=f"**Before:** {before_system}\n**After:** {after_system}",
                inline=True
            )
        
        # Check for rules channel change
        if hasattr(before, 'rules_channel') and hasattr(after, 'rules_channel'):
            if before.rules_channel != after.rules_channel:
                before_rules = "None" if not before.rules_channel else before.rules_channel.mention
                after_rules = "None" if not after.rules_channel else after.rules_channel.mention
                
                embed.add_field(
                    name="Rules Channel Changed",
                    value=f"**Before:** {before_rules}\n**After:** {after_rules}",
                    inline=True
                )
        
        # Check for public updates channel change
        if hasattr(before, 'public_updates_channel') and hasattr(after, 'public_updates_channel'):
            if before.public_updates_channel != after.public_updates_channel:
                before_updates = "None" if not before.public_updates_channel else before.public_updates_channel.mention
                after_updates = "None" if not after.public_updates_channel else after.public_updates_channel.mention
                
                embed.add_field(
                    name="Updates Channel Changed",
                    value=f"**Before:** {before_updates}\n**After:** {after_updates}",
                    inline=True
                )
        
        # Check for premium tier change
        if before.premium_tier != after.premium_tier:
            embed.add_field(
                name="Premium Tier Changed",
                value=f"**Before:** {before.premium_tier}\n**After:** {after.premium_tier}",
                inline=True
            )
        
        # Check for premium subscription count change
        if before.premium_subscription_count != after.premium_subscription_count:
            embed.add_field(
                name="Boost Count Changed",
                value=f"**Before:** {before.premium_subscription_count}\n**After:** {after.premium_subscription_count}",
                inline=True
            )
        
        # Check for features change
        if before.features != after.features:
            added_features = [f for f in after.features if f not in before.features]
            removed_features = [f for f in before.features if f not in after.features]
            
            if added_features:
                embed.add_field(
                    name="Features Added",
                    value=", ".join(added_features),
                    inline=False
                )
                
            if removed_features:
                embed.add_field(
                    name="Features Removed",
                    value=", ".join(removed_features),
                    inline=False
                )
        
        return embed
    
    async def create_emoji_update_embed(self, guild: discord.Guild, before: List[discord.Emoji], after: List[discord.Emoji]) -> discord.Embed:
        """Create an embed for an emoji update event
        
        Args:
            guild: The guild
            before: Emojis before update
            after: Emojis after update
            
        Returns:
            Discord embed for the event
        """
        # Get config for colors
        config = await self.get_config(guild.id)
        colors = config["settings"]["colors"]
        
        # Create embed
        embed = discord.Embed(
            title="Emoji Updated",
            color=colors.get("update", 0xFAA61A),
            timestamp=datetime.datetime.now()
        )
        
        # Set author info
        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url if guild.icon else None
        )
        
        # Set footer
        embed.set_footer(text=f"Server ID: {guild.id}")
        
        # Find changes
        before_emojis = {e.id: e for e in before}
        after_emojis = {e.id: e for e in after}
        
        # Added emojis
        added_emojis = [e for e in after if e.id not in before_emojis]
        
        if added_emojis:
            emoji_text = " ".join([str(e) for e in added_emojis[:20]])
            
            if len(added_emojis) > 20:
                emoji_text += f" (+{len(added_emojis) - 20} more)"
                
            embed.add_field(
                name=f"Emojis Added [{len(added_emojis)}]",
                value=emoji_text,
                inline=False
            )
        
        # Removed emojis
        removed_emojis = [e for e in before if e.id not in after_emojis]
        
        if removed_emojis:
            emoji_names = ", ".join([f":{e.name}:" for e in removed_emojis[:20]])
            
            if len(removed_emojis) > 20:
                emoji_names += f" (+{len(removed_emojis) - 20} more)"
                
            embed.add_field(
                name=f"Emojis Removed [{len(removed_emojis)}]",
                value=emoji_names,
                inline=False
            )
        
        # Updated emojis
        updated_emojis = []
        
        for emoji_id, after_emoji in after_emojis.items():
            if emoji_id in before_emojis:
                before_emoji = before_emojis[emoji_id]
                
                if before_emoji.name != after_emoji.name:
                    updated_emojis.append((before_emoji, after_emoji))
        
        if updated_emojis:
            changes = []
            
            for before_emoji, after_emoji in updated_emojis[:10]:
                changes.append(f"{str(after_emoji)} :{before_emoji.name}: → :{after_emoji.name}:")
                
            if len(updated_emojis) > 10:
                changes.append(f"(+{len(updated_emojis) - 10} more)")
                
            embed.add_field(
                name=f"Emojis Renamed [{len(updated_emojis)}]",
                value="\n".join(changes),
                inline=False
            )
        
        return embed