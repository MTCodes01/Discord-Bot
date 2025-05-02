import discord
import asyncio
import datetime
import json
import os
import random
import string
import time
import traceback
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
import re


class ServerBackupSystem:
    """Core system for server structure backup and restoration"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        
        # Set up backup directory
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True, parents=True)
    
    def get_backup_path(self, guild_id: int) -> Path:
        """Get the path for a guild's backup file"""
        return self.backup_dir / f"backup_{guild_id}.json"
    
    async def create_backup(self, guild: discord.Guild) -> Union[bool, str]:
        """Create a complete backup of a server's structure
        
        Args:
            guild: The Discord guild to backup
            
        Returns:
            Backup data as a dictionary
        """
        backup_data = {
            "guild": {
                "id": guild.id,
                "name": guild.name,
                "icon_url": str(guild.icon.url) if guild.icon else None,
                "banner_url": str(guild.banner.url) if guild.banner else None,
                "description": guild.description,
                "created_at": int(guild.created_at.timestamp()),
                "owner_id": guild.owner_id,
                "system_channel_id": guild.system_channel.id if guild.system_channel else None,
                "afk_timeout": guild.afk_timeout,
                "afk_channel_id": guild.afk_channel.id if guild.afk_channel else None,
                "mfa_level": guild.mfa_level.value if hasattr(guild.mfa_level, 'value') else guild.mfa_level,
                "verification_level": guild.verification_level.value if hasattr(guild.verification_level, 'value') else guild.verification_level,
                "explicit_content_filter": guild.explicit_content_filter.value if hasattr(guild.explicit_content_filter, 'value') else guild.explicit_content_filter,
                "default_notifications": guild.default_notifications.value if hasattr(guild.default_notifications, 'value') else guild.default_notifications,
                "features": list(guild.features),
                "premium_tier": guild.premium_tier,
                "premium_subscription_count": guild.premium_subscription_count,
                "preferred_locale": guild.preferred_locale,
                "member_count": guild.member_count,
            },
            "roles": [],
            "categories": [],
            "text_channels": [],
            "voice_channels": [],
            "forum_channels": [],
            "stage_channels": [],
            "emojis": [],
            "stickers": [],
            "bots": [],
            "backup_date": int(datetime.datetime.now().timestamp()),
            "backup_version": "1.0"
        }
        
        # Backup roles (except @everyone)
        for role in guild.roles:
            if role.name == "@everyone":
                # Save @everyone separately with its permissions
                backup_data["guild"]["everyone_permissions"] = role.permissions.value
                continue
                
            role_data = {
                "id": role.id,
                "name": role.name,
                "permissions": role.permissions.value,
                "color": role.color.value,
                "hoist": role.hoist,
                "position": role.position,
                "mentionable": role.mentionable,
                "is_bot_managed": role.is_bot_managed(),
                "is_premium_subscriber": role.is_premium_subscriber(),
                "is_integration": role.is_integration(),
            }
            
            backup_data["roles"].append(role_data)
        
        # Sort roles by position
        backup_data["roles"].sort(key=lambda r: r["position"])
        
        # Backup categories
        for category in guild.categories:
            category_data = {
                "id": category.id,
                "name": category.name,
                "position": category.position,
                "overwrites": self._get_permission_overwrites(category)
            }
            
            backup_data["categories"].append(category_data)
        
        # Sort categories by position
        backup_data["categories"].sort(key=lambda c: c["position"])
        
        # Backup text channels
        for channel in guild.text_channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "topic": channel.topic,
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,
                "nsfw": channel.is_nsfw(),
                "slowmode_delay": channel.slowmode_delay,
                "overwrites": self._get_permission_overwrites(channel),
                "default_auto_archive_duration": channel.default_auto_archive_duration,
                "type": "text"
            }
            
            backup_data["text_channels"].append(channel_data)
        
        # Sort text channels by position
        backup_data["text_channels"].sort(key=lambda c: (c["category_id"] or 0, c["position"]))
        
        # Backup voice channels
        for channel in guild.voice_channels:
            channel_data = {
                "id": channel.id,
                "name": channel.name,
                "position": channel.position,
                "category_id": channel.category.id if channel.category else None,
                "bitrate": channel.bitrate,
                "user_limit": channel.user_limit,
                "rtc_region": channel.rtc_region,
                "overwrites": self._get_permission_overwrites(channel),
                "type": "voice"
            }
            
            backup_data["voice_channels"].append(channel_data)
        
        # Sort voice channels by position
        backup_data["voice_channels"].sort(key=lambda c: (c["category_id"] or 0, c["position"]))
        
        # Backup forum channels (Discord 2.0)
        try:
            for channel in guild.forums:
                channel_data = {
                    "id": channel.id,
                    "name": channel.name,
                    "topic": channel.topic if hasattr(channel, 'topic') else None,
                    "position": channel.position,
                    "category_id": channel.category.id if channel.category else None,
                    "nsfw": channel.is_nsfw(),
                    "overwrites": self._get_permission_overwrites(channel),
                    "type": "forum",
                    "available_tags": []
                }
                
                # Backup tags if available
                if hasattr(channel, 'available_tags'):
                    for tag in channel.available_tags:
                        tag_data = {
                            "name": tag.name,
                            "emoji": str(tag.emoji) if tag.emoji else None,
                            "moderated": tag.moderated
                        }
                        channel_data["available_tags"].append(tag_data)
                
                backup_data["forum_channels"].append(channel_data)
            
            # Sort forum channels by position
            backup_data["forum_channels"].sort(key=lambda c: (c["category_id"] or 0, c["position"]))
        except Exception as e:
            self.logger.warning(f"Could not backup forum channels: {str(e)}")
        
        # Backup stage channels
        try:
            for channel in guild.stage_channels:
                channel_data = {
                    "id": channel.id,
                    "name": channel.name,
                    "position": channel.position,
                    "category_id": channel.category.id if channel.category else None,
                    "bitrate": channel.bitrate if hasattr(channel, 'bitrate') else None,
                    "user_limit": channel.user_limit if hasattr(channel, 'user_limit') else None,
                    "rtc_region": channel.rtc_region if hasattr(channel, 'rtc_region') else None,
                    "topic": channel.topic if hasattr(channel, 'topic') else None,
                    "overwrites": self._get_permission_overwrites(channel),
                    "type": "stage"
                }
                
                backup_data["stage_channels"].append(channel_data)
            
            # Sort stage channels by position
            backup_data["stage_channels"].sort(key=lambda c: (c["category_id"] or 0, c["position"]))
        except Exception as e:
            self.logger.warning(f"Could not backup stage channels: {str(e)}")
        
        # Backup emojis
        for emoji in guild.emojis:
            emoji_data = {
                "id": emoji.id,
                "name": emoji.name,
                "url": str(emoji.url),
                "animated": emoji.animated,
                "available": emoji.available,
                "managed": emoji.managed,
                "require_colons": emoji.require_colons,
            }
            
            backup_data["emojis"].append(emoji_data)
        
        # Backup stickers
        try:
            for sticker in guild.stickers:
                sticker_data = {
                    "id": sticker.id,
                    "name": sticker.name,
                    "description": sticker.description,
                    "url": str(sticker.url),
                    "format_type": sticker.format.value if hasattr(sticker.format, 'value') else sticker.format,
                    "available": sticker.available,
                }
                
                backup_data["stickers"].append(sticker_data)
        except Exception as e:
            self.logger.warning(f"Could not backup stickers: {str(e)}")
        
        # Backup bots (IDs and names only, not invites or permissions)
        for member in guild.members:
            if member.bot:
                bot_data = {
                    "id": member.id,
                    "name": member.name,
                    "discriminator": member.discriminator,
                    "display_name": member.display_name,
                    "bot": True
                }
                
                backup_data["bots"].append(bot_data)
        
        backup_id = await self.save_backup(guild.id, backup_data)

        # return success, result_msg, backup_id
        return (True, "Backup created successfully", backup_id)
    
    async def save_backup(self, guild_id: int, backup_data: Dict[str, Any], custom_name: str = None) -> str:
        """Save backup data to file
        
        Args:
            guild_id: The Discord guild ID
            backup_data: Backup data dictionary
            custom_name: Optional custom name for the backup
            
        Returns:
            ID of the saved backup
        """
        try:
            # Generate a unique backup ID using timestamp and random string
            timestamp = int(time.time())
            random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            backup_id = f"{timestamp}_{random_str}"
            
            # Add metadata to backup_data
            backup_data['metadata'] = {
                'backup_id': backup_id,
                'created_at': timestamp,
                'custom_name': custom_name
            }
            
            # Generate filename with backup_id
            if custom_name:
                # Sanitize custom name
                safe_name = re.sub(r'[^\w\-\.]', '_', custom_name)
                filename = f"backup_{guild_id}_{backup_id}_{safe_name}.json"
            else:
                filename = f"backup_{guild_id}_{backup_id}.json"
            
            # Check if we need to delete old backups
            existing_backups = await self.get_server_backups(guild_id)
            
            # If we have reached the limit, delete the oldest backup
            MAX_BACKUPS = 10
            if len(existing_backups) >= MAX_BACKUPS:
                # Sort backups by creation timestamp (oldest first)
                existing_backups.sort(key=lambda x: x.get('created_at', 0))
                
                # Delete oldest backup
                oldest_backup = existing_backups[0]
                oldest_backup_path = self.backup_dir / oldest_backup['filename']
                
                try:
                    if os.path.exists(oldest_backup_path):
                        os.remove(oldest_backup_path)
                        self.logger.info(f"Deleted oldest backup {oldest_backup['filename']} to stay within limit")
                except Exception as e:
                    self.logger.error(f"Error deleting oldest backup: {str(e)}")
            
            # Save new backup
            backup_path = self.backup_dir / filename
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2)
            
            self.logger.info(f"Saved backup {filename} for guild {guild_id}")
            return backup_id
        
        except Exception as e:
            self.logger.error(f"Error saving backup: {str(e)}\n{traceback.format_exc()}")
            raise
            
    async def get_server_backups(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all backups for a specific server
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            List of backup information dictionaries
        """
        try:
            backups = []
            backup_pattern = f"backup_{guild_id}*.json"
            
            for backup_file in self.backup_dir.glob(backup_pattern):
                try:
                    # Extract backup ID from filename
                    # Format: backup_GUILDID_TIMESTAMP_RANDOM_[CUSTOMNAME].json
                    filename_parts = backup_file.stem.split('_')
                    if len(filename_parts) >= 4:  # At minimum: backup, guild_id, timestamp, random
                        timestamp_str = filename_parts[2]
                        
                        # Get file stats
                        stats = backup_file.stat()
                        created_at = int(stats.st_mtime)
                        file_size = round(stats.st_size / 1024, 2)  # Size in KB
                        
                        # Try to get metadata from file
                        metadata = {}
                        try:
                            with open(backup_file, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                                metadata = data.get('metadata', {})
                        except:
                            # If we can't read the file, use filename data
                            pass
                        
                        # Use metadata if available, otherwise use filename/stats
                        backup_id = metadata.get('backup_id', f"{timestamp_str}_{filename_parts[3]}")
                        created_at = metadata.get('created_at', created_at)
                        custom_name = metadata.get('custom_name', None)
                        
                        # Read file to get counts
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            channel_count = len(data.get('channels', []))
                            role_count = len(data.get('roles', []))
                        
                        backups.append({
                            'id': backup_id,
                            'filename': backup_file.name,
                            'date': datetime.datetime.fromtimestamp(created_at).strftime('%Y-%m-%d %H:%M:%S'),
                            'created_at': created_at,
                            'file_size': file_size,
                            'custom_name': custom_name,
                            'channel_count': channel_count,
                            'role_count': role_count
                        })
                except Exception as e:
                    self.logger.error(f"Error processing backup file {backup_file}: {str(e)}")
                    continue
                
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x.get('created_at', 0), reverse=True)
            return backups
            
        except Exception as e:
            self.logger.error(f"Error listing backups: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def load_backup(self, backup_id: str) -> Dict[str, Any]:
        """Load backup data from file
        
        Args:
            backup_id: The backup ID (filename or guild ID)
            
        Returns:
            Backup data dictionary
        """
        try:
            # Check if backup_id is a guild ID or filename
            if backup_id.isdigit():
                # Guild ID
                backup_path = self.get_backup_path(int(backup_id))
            else:
                # Filename
                backup_path = self.backup_dir / backup_id
                
                # If no extension, add .json
                if not backup_path.suffix:
                    backup_path = backup_path.with_suffix('.json')
            
            # Check if file exists
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Load backup
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            return backup_data
        
        except Exception as e:
            self.logger.error(f"Error loading backup: {str(e)}\n{traceback.format_exc()}")
            raise
    
    async def list_backups(self, guild_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List available backups
        
        Args:
            guild_id: Optional Discord guild ID to filter backups
            
        Returns:
            List of backup information dictionaries
        """
        try:
            # Get all backup files
            backup_files = list(self.backup_dir.glob("backup_*.json"))
            
            # Filter by guild ID if provided
            if guild_id is not None:
                backup_files = [f for f in backup_files if f"backup_{guild_id}" in f.name]
            
            # Load basic info from each backup
            backups = []
            
            for file in backup_files:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Extract metadata
                    guild_info = data.get("guild", {})
                    backup_info = {
                        "id": file.name[:-5],  # Remove .json extension
                        "filename": file.name,
                        "path": str(file),
                        "guild_id": guild_info.get("id"),
                        "guild_name": guild_info.get("name"),
                        "date": data.get("backup_date"),
                        "member_count": guild_info.get("member_count"),
                        "channel_count": (
                            len(data.get("text_channels", [])) +
                            len(data.get("voice_channels", [])) +
                            len(data.get("forum_channels", [])) +
                            len(data.get("stage_channels", []))
                        ),
                        "role_count": len(data.get("roles", [])),
                        "emoji_count": len(data.get("emojis", [])),
                        "sticker_count": len(data.get("stickers", [])),
                        "file_size": file.stat().st_size
                    }
                    
                    backups.append(backup_info)
                except Exception as e:
                    self.logger.warning(f"Error reading backup file {file}: {str(e)}")
            
            # Sort by backup date (newest first)
            backups.sort(key=lambda b: b.get("backup_date", 0), reverse=True)
            
            return backups
        
        except Exception as e:
            self.logger.error(f"Error listing backups: {str(e)}\n{traceback.format_exc()}")
            return []
    
    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup file
        
        Args:
            backup_id: The backup ID (filename or guild ID)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if backup_id is a guild ID or filename
            if backup_id.isdigit():
                # Guild ID
                backup_path = self.get_backup_path(int(backup_id))
            else:
                # Filename
                backup_path = self.backup_dir / backup_id
                
                # If no extension, add .json
                if not backup_path.suffix:
                    backup_path = backup_path.with_suffix('.json')
            
            # Check if file exists
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Delete file
            os.remove(backup_path)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting backup: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def restore_backup(self, guild: discord.Guild, backup_data: Dict[str, Any], options: Dict[str, bool] = None) -> Dict[str, Any]:
        """Restore a backup to a guild
        
        Args:
            guild: The Discord guild to restore to
            backup_data: Backup data dictionary
            options: Optional restoration options
            
        Returns:
            Dictionary with restoration statistics and results
        """
        # Default options
        if options is None:
            options = {
                "roles": True,
                "categories": True,
                "channels": True,
                "emojis": True,
                "settings": True,
                "delete_existing": False
            }
        
        stats = {
            "roles_created": 0,
            "roles_updated": 0,
            "roles_skipped": 0,
            "categories_created": 0,
            "categories_updated": 0,
            "categories_skipped": 0,
            "text_channels_created": 0,
            "text_channels_updated": 0,
            "text_channels_skipped": 0,
            "voice_channels_created": 0,
            "voice_channels_updated": 0,
            "voice_channels_skipped": 0,
            "forum_channels_created": 0,
            "forum_channels_skipped": 0,
            "stage_channels_created": 0,
            "stage_channels_skipped": 0,
            "emojis_created": 0,
            "emojis_skipped": 0,
            "errors": []
        }
        
        # Check bot permissions
        required_permissions = [
            "manage_guild",
            "manage_channels",
            "manage_roles",
            "manage_emojis_and_stickers"
        ]
        
        missing_permissions = []
        for perm in required_permissions:
            if not getattr(guild.me.guild_permissions, perm):
                missing_permissions.append(perm)
        
        if missing_permissions:
            formatted_perms = ", ".join([p.replace("_", " ").title() for p in missing_permissions])
            stats["errors"].append(f"Missing required permissions: {formatted_perms}")
            return stats
        
        # Create ID mapping for roles and channels
        id_mapping = {
            "roles": {},
            "categories": {},
            "channels": {}
        }
        
        # Delete existing (if option enabled)
        if options.get("delete_existing", False):
            try:
                # Delete channels
                for channel in guild.channels:
                    try:
                        await channel.delete(reason="Server restore - deleting existing channels")
                    except Exception as e:
                        stats["errors"].append(f"Could not delete channel {channel.name}: {str(e)}")
                
                # Delete roles (except @everyone)
                for role in guild.roles:
                    if role.name != "@everyone" and role.position < guild.me.top_role.position:
                        try:
                            await role.delete(reason="Server restore - deleting existing roles")
                        except Exception as e:
                            stats["errors"].append(f"Could not delete role {role.name}: {str(e)}")
                
                # Delete emojis
                for emoji in guild.emojis:
                    try:
                        await emoji.delete(reason="Server restore - deleting existing emojis")
                    except Exception as e:
                        stats["errors"].append(f"Could not delete emoji {emoji.name}: {str(e)}")
            
            except Exception as e:
                stats["errors"].append(f"Error during deletion of existing elements: {str(e)}")
        
        # Restore server settings
        if options.get("settings", True):
            try:
                guild_settings = backup_data.get("guild", {})
                
                # Update name if different
                if guild.name != guild_settings.get("name"):
                    try:
                        await guild.edit(name=guild_settings.get("name"), reason="Server restore - updating settings")
                    except Exception as e:
                        stats["errors"].append(f"Could not update server name: {str(e)}")
                
                # Update other settings if possible
                try:
                    # Create a dict with only editable attributes
                    edit_params = {}
                    
                    # Some settings can be edited
                    if guild_settings.get("description") and guild.description != guild_settings.get("description"):
                        edit_params["description"] = guild_settings.get("description")
                        
                    if guild_settings.get("afk_timeout") and guild.afk_timeout != guild_settings.get("afk_timeout"):
                        edit_params["afk_timeout"] = guild_settings.get("afk_timeout")
                        
                    if guild_settings.get("verification_level") and guild.verification_level != guild_settings.get("verification_level"):
                        edit_params["verification_level"] = discord.VerificationLevel(guild_settings.get("verification_level"))
                        
                    if guild_settings.get("explicit_content_filter") and guild.explicit_content_filter != guild_settings.get("explicit_content_filter"):
                        edit_params["explicit_content_filter"] = discord.ContentFilter(guild_settings.get("explicit_content_filter"))
                        
                    if guild_settings.get("default_notifications") and guild.default_notifications != guild_settings.get("default_notifications"):
                        edit_params["default_notifications"] = discord.NotificationLevel(guild_settings.get("default_notifications"))
                    
                    # Apply changes if any
                    if edit_params:
                        await guild.edit(**edit_params, reason="Server restore - updating settings")
                        
                except Exception as e:
                    stats["errors"].append(f"Could not update server settings: {str(e)}")
            
            except Exception as e:
                stats["errors"].append(f"Error updating server settings: {str(e)}")
        
        # Restore roles
        if options.get("roles", True):
            try:
                # Get @everyone role
                everyone_role = guild.default_role
                
                # Update @everyone permissions if needed
                everyone_perms = backup_data.get("guild", {}).get("everyone_permissions")
                if everyone_perms is not None:
                    try:
                        await everyone_role.edit(
                            permissions=discord.Permissions(permissions=everyone_perms),
                            reason="Server restore - updating @everyone permissions"
                        )
                    except Exception as e:
                        stats["errors"].append(f"Could not update @everyone permissions: {str(e)}")
                
                # Get existing roles
                existing_roles = {role.name.lower(): role for role in guild.roles}
                
                # Restore roles (in reverse to maintain hierarchy)
                for role_data in reversed(backup_data.get("roles", [])):
                    role_name = role_data.get("name")
                    
                    # Skip managed roles (bot roles, booster roles)
                    if role_data.get("is_bot_managed") or role_data.get("is_integration") or role_data.get("is_premium_subscriber"):
                        stats["roles_skipped"] += 1
                        continue
                    
                    # Check if role exists
                    existing_role = existing_roles.get(role_name.lower())
                    
                    if existing_role:
                        # Update existing role
                        try:
                            await existing_role.edit(
                                name=role_name,
                                permissions=discord.Permissions(permissions=role_data.get("permissions")),
                                color=discord.Color(role_data.get("color")),
                                hoist=role_data.get("hoist"),
                                mentionable=role_data.get("mentionable"),
                                reason="Server restore - updating role"
                            )
                            
                            # Add to ID mapping
                            id_mapping["roles"][role_data.get("id")] = existing_role.id
                            
                            stats["roles_updated"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not update role {role_name}: {str(e)}")
                            stats["roles_skipped"] += 1
                    else:
                        # Create new role
                        try:
                            new_role = await guild.create_role(
                                name=role_name,
                                permissions=discord.Permissions(permissions=role_data.get("permissions")),
                                color=discord.Color(role_data.get("color")),
                                hoist=role_data.get("hoist"),
                                mentionable=role_data.get("mentionable"),
                                reason="Server restore - creating role"
                            )
                            
                            # Add to ID mapping
                            id_mapping["roles"][role_data.get("id")] = new_role.id
                            
                            stats["roles_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not create role {role_name}: {str(e)}")
                            stats["roles_skipped"] += 1
            
            except Exception as e:
                stats["errors"].append(f"Error restoring roles: {str(e)}")
        
        # Restore categories
        if options.get("categories", True):
            try:
                # Get existing categories
                existing_categories = {category.name.lower(): category for category in guild.categories}
                
                # Restore categories
                for cat_data in backup_data.get("categories", []):
                    cat_name = cat_data.get("name")
                    
                    # Check if category exists
                    existing_category = existing_categories.get(cat_name.lower())
                    
                    if existing_category:
                        # Update existing category
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(cat_data.get("overwrites", {}), guild, id_mapping)
                            
                            await existing_category.edit(
                                name=cat_name,
                                overwrites=overwrites,
                                reason="Server restore - updating category"
                            )
                            
                            # Add to ID mapping
                            id_mapping["categories"][cat_data.get("id")] = existing_category.id
                            
                            stats["categories_updated"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not update category {cat_name}: {str(e)}")
                            stats["categories_skipped"] += 1
                    else:
                        # Create new category
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(cat_data.get("overwrites", {}), guild, id_mapping)
                            
                            new_category = await guild.create_category(
                                name=cat_name,
                                overwrites=overwrites,
                                reason="Server restore - creating category"
                            )
                            
                            # Add to ID mapping
                            id_mapping["categories"][cat_data.get("id")] = new_category.id
                            
                            stats["categories_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not create category {cat_name}: {str(e)}")
                            stats["categories_skipped"] += 1
            
            except Exception as e:
                stats["errors"].append(f"Error restoring categories: {str(e)}")
        
        # Restore channels
        if options.get("channels", True):
            # Restore text channels
            try:
                # Get existing text channels
                existing_text_channels = {channel.name.lower(): channel for channel in guild.text_channels}
                
                # Restore text channels
                for channel_data in backup_data.get("text_channels", []):
                    channel_name = channel_data.get("name")
                    
                    # Check if channel exists
                    existing_channel = existing_text_channels.get(channel_name.lower())
                    
                    if existing_channel:
                        # Update existing channel
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                            
                            # Get category
                            category_id = channel_data.get("category_id")
                            category = None
                            
                            if category_id and category_id in id_mapping["categories"]:
                                category = guild.get_channel(id_mapping["categories"][category_id])
                            
                            await existing_channel.edit(
                                name=channel_name,
                                topic=channel_data.get("topic"),
                                nsfw=channel_data.get("nsfw", False),
                                slowmode_delay=channel_data.get("slowmode_delay", 0),
                                category=category,
                                overwrites=overwrites,
                                reason="Server restore - updating text channel"
                            )
                            
                            # Add to ID mapping
                            id_mapping["channels"][channel_data.get("id")] = existing_channel.id
                            
                            stats["text_channels_updated"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not update text channel {channel_name}: {str(e)}")
                            stats["text_channels_skipped"] += 1
                    else:
                        # Create new channel
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                            
                            # Get category
                            category_id = channel_data.get("category_id")
                            category = None
                            
                            if category_id and category_id in id_mapping["categories"]:
                                category = guild.get_channel(id_mapping["categories"][category_id])
                            
                            new_channel = await guild.create_text_channel(
                                name=channel_name,
                                topic=channel_data.get("topic"),
                                nsfw=channel_data.get("nsfw", False),
                                slowmode_delay=channel_data.get("slowmode_delay", 0),
                                category=category,
                                overwrites=overwrites,
                                reason="Server restore - creating text channel"
                            )
                            
                            # Add to ID mapping
                            id_mapping["channels"][channel_data.get("id")] = new_channel.id
                            
                            stats["text_channels_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not create text channel {channel_name}: {str(e)}")
                            stats["text_channels_skipped"] += 1
            
            except Exception as e:
                stats["errors"].append(f"Error restoring text channels: {str(e)}")
            
            # Restore voice channels
            try:
                # Get existing voice channels
                existing_voice_channels = {channel.name.lower(): channel for channel in guild.voice_channels}
                
                # Restore voice channels
                for channel_data in backup_data.get("voice_channels", []):
                    channel_name = channel_data.get("name")
                    
                    # Check if channel exists
                    existing_channel = existing_voice_channels.get(channel_name.lower())
                    
                    if existing_channel:
                        # Update existing channel
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                            
                            # Get category
                            category_id = channel_data.get("category_id")
                            category = None
                            
                            if category_id and category_id in id_mapping["categories"]:
                                category = guild.get_channel(id_mapping["categories"][category_id])
                            
                            edit_params = {
                                "name": channel_name,
                                "bitrate": min(channel_data.get("bitrate", 64000), guild.bitrate_limit),
                                "user_limit": channel_data.get("user_limit", 0),
                                "category": category,
                                "overwrites": overwrites,
                                "reason": "Server restore - updating voice channel"
                            }
                            
                            # Add rtc_region if specified
                            if channel_data.get("rtc_region"):
                                edit_params["rtc_region"] = channel_data.get("rtc_region")
                            
                            await existing_channel.edit(**edit_params)
                            
                            # Add to ID mapping
                            id_mapping["channels"][channel_data.get("id")] = existing_channel.id
                            
                            stats["voice_channels_updated"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not update voice channel {channel_name}: {str(e)}")
                            stats["voice_channels_skipped"] += 1
                    else:
                        # Create new channel
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                            
                            # Get category
                            category_id = channel_data.get("category_id")
                            category = None
                            
                            if category_id and category_id in id_mapping["categories"]:
                                category = guild.get_channel(id_mapping["categories"][category_id])
                            
                            create_params = {
                                "name": channel_name,
                                "bitrate": min(channel_data.get("bitrate", 64000), guild.bitrate_limit),
                                "user_limit": channel_data.get("user_limit", 0),
                                "category": category,
                                "overwrites": overwrites,
                                "reason": "Server restore - creating voice channel"
                            }
                            
                            # Add rtc_region if specified
                            if channel_data.get("rtc_region"):
                                create_params["rtc_region"] = channel_data.get("rtc_region")
                            
                            new_channel = await guild.create_voice_channel(**create_params)
                            
                            # Add to ID mapping
                            id_mapping["channels"][channel_data.get("id")] = new_channel.id
                            
                            stats["voice_channels_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not create voice channel {channel_name}: {str(e)}")
                            stats["voice_channels_skipped"] += 1
            
            except Exception as e:
                stats["errors"].append(f"Error restoring voice channels: {str(e)}")
            
            # Restore stage channels
            try:
                # Check if guild has stage channels capability
                if "STAGE_INSTANCES" in guild.features:
                    # Get existing stage channels
                    existing_stage_channels = {channel.name.lower(): channel for channel in guild.stage_channels}
                    
                    # Restore stage channels
                    for channel_data in backup_data.get("stage_channels", []):
                        channel_name = channel_data.get("name")
                        
                        # Check if channel exists
                        existing_channel = existing_stage_channels.get(channel_name.lower())
                        
                        if existing_channel:
                            # Updating stage channels isn't well supported
                            stats["stage_channels_skipped"] += 1
                        else:
                            # Create new channel
                            try:
                                # Convert overwrites
                                overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                                
                                # Get category
                                category_id = channel_data.get("category_id")
                                category = None
                                
                                if category_id and category_id in id_mapping["categories"]:
                                    category = guild.get_channel(id_mapping["categories"][category_id])
                                
                                create_params = {
                                    "name": channel_name,
                                    "topic": channel_data.get("topic"),
                                    "category": category,
                                    "overwrites": overwrites,
                                    "reason": "Server restore - creating stage channel"
                                }
                                
                                new_channel = await guild.create_stage_channel(**create_params)
                                
                                # Add to ID mapping
                                id_mapping["channels"][channel_data.get("id")] = new_channel.id
                                
                                stats["stage_channels_created"] += 1
                                
                            except Exception as e:
                                stats["errors"].append(f"Could not create stage channel {channel_name}: {str(e)}")
                                stats["stage_channels_skipped"] += 1
                else:
                    stats["errors"].append("Guild does not have STAGE_INSTANCES feature, skipping stage channels")
            
            except Exception as e:
                stats["errors"].append(f"Error restoring stage channels: {str(e)}")
            
            # Restore forum channels
            try:
                # Check if guild has forum channels capability
                if hasattr(guild, 'create_forum') and callable(getattr(guild, 'create_forum')):
                    # Get existing forum channels
                    existing_forum_channels = {}
                    if hasattr(guild, 'forums'):
                        existing_forum_channels = {channel.name.lower(): channel for channel in guild.forums}
                    
                    # Restore forum channels
                    for channel_data in backup_data.get("forum_channels", []):
                        channel_name = channel_data.get("name")
                        
                        # Creating forum channel is complex, not trying to update existing ones
                        # Just create new ones
                        try:
                            # Convert overwrites
                            overwrites = self._convert_permission_overwrites(channel_data.get("overwrites", {}), guild, id_mapping)
                            
                            # Get category
                            category_id = channel_data.get("category_id")
                            category = None
                            
                            if category_id and category_id in id_mapping["categories"]:
                                category = guild.get_channel(id_mapping["categories"][category_id])
                            
                            create_params = {
                                "name": channel_name,
                                "topic": channel_data.get("topic"),
                                "category": category,
                                "overwrites": overwrites,
                                "reason": "Server restore - creating forum channel"
                            }
                            
                            # Forum channels are complex, and API may change
                            # This is a best effort to create them
                            new_channel = await guild.create_forum(**create_params)
                            
                            # Add to ID mapping
                            id_mapping["channels"][channel_data.get("id")] = new_channel.id
                            
                            stats["forum_channels_created"] += 1
                            
                        except Exception as e:
                            stats["errors"].append(f"Could not create forum channel {channel_name}: {str(e)}")
                            stats["forum_channels_skipped"] += 1
                else:
                    stats["errors"].append("Guild does not support forum channels, skipping forum channels")
            
            except Exception as e:
                stats["errors"].append(f"Error restoring forum channels: {str(e)}")
        
        # Restore emojis
        if options.get("emojis", True):
            try:
                # Get existing emojis
                existing_emojis = {emoji.name.lower(): emoji for emoji in guild.emojis}
                
                # Check emoji limit
                emoji_limit = guild.emoji_limit
                emoji_count = len(guild.emojis)
                
                # Restore emojis (up to the limit)
                for emoji_data in backup_data.get("emojis", []):
                    emoji_name = emoji_data.get("name")
                    
                    # Skip if at emoji limit
                    if emoji_count >= emoji_limit:
                        stats["errors"].append(f"Emoji limit reached ({emoji_limit}), skipping remaining emojis")
                        break
                    
                    # Check if emoji exists
                    existing_emoji = existing_emojis.get(emoji_name.lower())
                    
                    if existing_emoji:
                        # Skip, can't update existing emoji
                        stats["emojis_skipped"] += 1
                    else:
                        # Create new emoji
                        try:
                            # Get emoji data
                            emoji_url = emoji_data.get("url")
                            
                            # Download emoji image
                            async with self.bot.session.get(emoji_url) as resp:
                                if resp.status == 200:
                                    emoji_bytes = await resp.read()
                                    
                                    # Create emoji
                                    await guild.create_custom_emoji(
                                        name=emoji_name,
                                        image=emoji_bytes,
                                        reason="Server restore - creating emoji"
                                    )
                                    
                                    emoji_count += 1
                                    stats["emojis_created"] += 1
                                else:
                                    stats["errors"].append(f"Could not download emoji {emoji_name} from {emoji_url}: HTTP {resp.status}")
                                    stats["emojis_skipped"] += 1
                        except Exception as e:
                            stats["errors"].append(f"Could not create emoji {emoji_name}: {str(e)}")
                            stats["emojis_skipped"] += 1
            
            except Exception as e:
                stats["errors"].append(f"Error restoring emojis: {str(e)}")
        
        return stats
    
    def _get_permission_overwrites(self, channel) -> Dict[str, Dict[str, bool]]:
        """Convert channel permission overwrites to a serializable format
        
        Args:
            channel: The Discord channel
            
        Returns:
            Dict of overwrite pairs
        """
        overwrites = {}
        
        for target, overwrite in channel.overwrites.items():
            # Get target type and ID
            if isinstance(target, discord.Role):
                target_type = "role"
            else:
                target_type = "member"
            
            target_id = target.id
            
            # Convert overwrite to serializable format
            allow, deny = overwrite.pair()
            
            overwrites[f"{target_type}:{target_id}"] = {
                "allow": allow.value,
                "deny": deny.value
            }
        
        return overwrites
    
    def _convert_permission_overwrites(self, overwrites_data: Dict[str, Dict[str, int]], guild: discord.Guild, id_mapping: Dict[str, Dict[int, int]]) -> Dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]:
        """Convert serialized permission overwrites back to Discord objects
        
        Args:
            overwrites_data: Serialized permission overrides
            guild: The Discord guild
            id_mapping: Mapping of old IDs to new IDs
            
        Returns:
            Dict of permission overwrite objects
        """
        result = {}
        
        for key, data in overwrites_data.items():
            # Parse key
            parts = key.split(":", 1)
            
            if len(parts) != 2:
                continue
                
            target_type, target_id_str = parts
            target_id = int(target_id_str)
            
            # Skip invalid targets
            if not target_id:
                continue
            
            # Get target object
            target = None
            
            if target_type == "role":
                # Check if role ID is in mapping
                if target_id in id_mapping["roles"]:
                    target = guild.get_role(id_mapping["roles"][target_id])
                else:
                    # Try to find by original ID
                    target = guild.get_role(target_id)
                    
                    # If not found and it's @everyone, use default role
                    if not target and target_id == guild.id:
                        target = guild.default_role
            
            elif target_type == "member":
                # Member overrides can't be easily restored
                # Just skip them
                continue
            
            # Skip if target not found
            if not target:
                continue
            
            # Create permission overwrite
            allow = discord.Permissions(data.get("allow", 0))
            deny = discord.Permissions(data.get("deny", 0))
            
            overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
            result[target] = overwrite
        
        return result


class ChannelArchiver:
    """Utility class for archiving channel content"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        
        # Set up archive directory
        self.archive_dir = Path("archives")
        self.archive_dir.mkdir(exist_ok=True, parents=True)
    
    async def archive_text_channel(self, channel: discord.TextChannel, limit: int = None, filename: str = None) -> str:
        """Archive messages from a text channel
        
        Args:
            channel: The Discord text channel
            limit: Maximum number of messages to archive (None for all)
            filename: Optional custom filename
            
        Returns:
            Path to the archive file
        """
        try:
            # Generate default filename if not provided
            if not filename:
                date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = re.sub(r'[^\w\-\.]', '_', channel.name)
                filename = f"archive_{channel.guild.id}_{channel.id}_{safe_name}_{date_str}.txt"
            
            # Create archive path
            archive_path = self.archive_dir / filename
            
            # Fetch messages
            messages = []
            
            async for message in channel.history(limit=limit, oldest_first=True):
                # Format message
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = message.content or ""
                
                # Add attachments
                attachments = []
                for attachment in message.attachments:
                    attachments.append(f"[Attachment: {attachment.filename} | {attachment.url}]")
                
                if attachments:
                    content += " " + " ".join(attachments)
                
                # Add embeds
                embeds = []
                for embed in message.embeds:
                    if embed.title:
                        embeds.append(f"[Embed: {embed.title}]")
                    else:
                        embeds.append("[Embed]")
                
                if embeds:
                    content += " " + " ".join(embeds)
                
                # Format message
                formatted = f"[{timestamp}] {message.author} ({message.author.id}): {content}"
                messages.append(formatted)
            
            # Save to file
            with open(archive_path, 'w', encoding='utf-8') as f:
                # Add header
                f.write(f"Archive of #{channel.name} ({channel.id}) from {channel.guild.name} ({channel.guild.id})\n")
                f.write(f"Archived at: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total messages: {len(messages)}\n")
                f.write("=" * 80 + "\n\n")
                
                # Write messages
                for msg in messages:
                    f.write(msg + "\n")
            
            return str(archive_path)
        
        except Exception as e:
            self.logger.error(f"Error archiving channel: {str(e)}\n{traceback.format_exc()}")
            raise
    
    async def export_channel_as_json(self, channel: discord.TextChannel, limit: int = None, filename: str = None) -> str:
        """Export messages from a text channel as JSON
        
        Args:
            channel: The Discord text channel
            limit: Maximum number of messages to export (None for all)
            filename: Optional custom filename
            
        Returns:
            Path to the JSON file
        """
        try:
            # Generate default filename if not provided
            if not filename:
                date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = re.sub(r'[^\w\-\.]', '_', channel.name)
                filename = f"export_{channel.guild.id}_{channel.id}_{safe_name}_{date_str}.json"
            
            # Create export path
            export_path = self.archive_dir / filename
            
            # Fetch messages
            messages = []
            
            async for message in channel.history(limit=limit, oldest_first=True):
                # Format message
                msg_data = {
                    "id": message.id,
                    "author": {
                        "id": message.author.id,
                        "name": message.author.name,
                        "discriminator": message.author.discriminator,
                        "display_name": message.author.display_name,
                        "bot": message.author.bot
                    },
                    "content": message.content,
                    "created_at": int(message.created_at.timestamp()),
                    "edited_at": int(message.edited_at.timestamp()) if message.edited_at else None,
                    "attachments": [
                        {
                            "id": attachment.id,
                            "filename": attachment.filename,
                            "url": attachment.url,
                            "size": attachment.size,
                            "content_type": attachment.content_type
                        }
                        for attachment in message.attachments
                    ],
                    "embeds": [embed.to_dict() for embed in message.embeds],
                    "reactions": [
                        {
                            "emoji": str(reaction.emoji),
                            "count": reaction.count
                        }
                        for reaction in message.reactions
                    ]
                }
                
                messages.append(msg_data)
            
            # Create export data
            export_data = {
                "channel": {
                    "id": channel.id,
                    "name": channel.name,
                    "guild_id": channel.guild.id,
                    "guild_name": channel.guild.name,
                    "category_id": channel.category.id if channel.category else None,
                    "category_name": channel.category.name if channel.category else None,
                    "topic": channel.topic,
                    "position": channel.position,
                    "nsfw": channel.is_nsfw(),
                    "slowmode_delay": channel.slowmode_delay
                },
                "messages": messages,
                "export_date": int(datetime.datetime.now().timestamp()),
                "export_version": "1.0"
            }
            
            # Save to file
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            return str(export_path)
        
        except Exception as e:
            self.logger.error(f"Error exporting channel: {str(e)}\n{traceback.format_exc()}")
            raise