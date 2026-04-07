import discord
import asyncio
import datetime
import json
import os
import random
import traceback
import math
from discord.ext import commands
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
import io
from PIL import Image, ImageDraw, ImageFont, ImageColor
from io import BytesIO


class LevelingSystem:
    """Core system for user leveling and experience tracking"""
    
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.logger = bot.logger
        
        # Set up data directory
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Data caches
        self.user_data = {}
        self.configs = {}
        
        # Default leveling config
        self.DEFAULT_CONFIG = {
            "enabled": True,
            "text_xp": {
                "min": 15,
                "max": 25,
                "cooldown_seconds": 60
            },
            "voice_xp": {
                "per_minute": 10,
                "afk_multiplier": 0.0,
                "solo_multiplier": 0.5
            },
            "level_curve": {
                "base": 100,
                "exponent": 1.5
            },
            "settings": {
                "level_up_messages": True,
                "level_up_channel": None,
                "level_up_dm": False,
                "stack_roles": True
            },
            "rewards": {
                "enabled": False,
                "roles": {}
            }
        }
        
        # Active voice sessions
        self.voice_sessions = {}
    
    async def get_config(self, guild_id: int) -> Dict[str, Any]:
        """Get leveling configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            Leveling configuration dictionary
        """
        # Check cache first
        if guild_id in self.configs:
            return self.configs[guild_id]
            
        # Load from file
        config_path = self.data_dir / f"leveling_config_{guild_id}.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Cache config
                self.configs[guild_id] = config
                return config
                
            except Exception as e:
                self.logger.error(f"Error loading leveling config for {guild_id}: {str(e)}")
        
        # Create default config
        default_config = self.DEFAULT_CONFIG.copy()
        
        # Save as new config
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving default leveling config for {guild_id}: {str(e)}")
        
        # Cache config
        self.configs[guild_id] = default_config
        return default_config
    
    async def save_config(self, guild_id: int, config: Dict[str, Any]) -> bool:
        """Save leveling configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            config: Leveling configuration dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Create backup of existing config
            config_path = self.data_dir / f"leveling_config_{guild_id}.json"
            
            if config_path.exists():
                backup_path = self.data_dir / f"leveling_config_{guild_id}_backup.json"
                
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
            self.logger.error(f"Error saving leveling config for {guild_id}: {str(e)}")
            return False
    
    def _get_user_data_path(self, guild_id: int) -> Path:
        """Get the path for a guild's user data file"""
        return self.data_dir / f"leveling_data_{guild_id}.json"
    
    async def _load_guild_data(self, guild_id: int) -> Dict[str, Dict[str, Any]]:
        """Load all user data for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            Dictionary of user data
        """
        # Check cache first
        if guild_id in self.user_data:
            return self.user_data[guild_id]
            
        # Load from file
        data_path = self._get_user_data_path(guild_id)
        
        if data_path.exists():
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Cache data
                self.user_data[guild_id] = data
                return data
                
            except Exception as e:
                self.logger.error(f"Error loading leveling data for {guild_id}: {str(e)}")
        
        # Return empty data if not found
        self.user_data[guild_id] = {}
        return {}
    
    async def _save_guild_data(self, guild_id: int) -> bool:
        """Save all user data for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Get cached data
            if guild_id not in self.user_data:
                return False
                
            data = self.user_data[guild_id]
            
            # Save to file
            data_path = self._get_user_data_path(guild_id)
            
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving leveling data for {guild_id}: {str(e)}")
            return False
    
    async def get_user_xp(self, user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get XP data for a user
        
        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            
        Returns:
            User XP data or None if not found
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Get user data
            user_id_str = str(user_id)
            
            if user_id_str not in guild_data:
                return None
                
            user_data = guild_data[user_id_str]
            
            # Get config for calculations
            config = await self.get_config(guild_id)
            level_curve = config["level_curve"]
            
            # Calculate derived values
            text_xp = user_data.get("text_xp", 0)
            voice_xp = user_data.get("voice_xp", 0)
            total_xp = text_xp + voice_xp
            
            # Calculate level and progress
            level = 0
            xp_needed = level_curve["base"]
            
            while total_xp >= xp_needed:
                level += 1
                xp_needed = self._calculate_xp_for_level(level + 1, level_curve)
            
            # Calculate XP needed for next level
            current_level_xp = total_xp - self._calculate_xp_for_level(level, level_curve)
            xp_to_next_level = xp_needed - self._calculate_xp_for_level(level, level_curve)
            progress = (current_level_xp / xp_to_next_level) * 100 if xp_to_next_level > 0 else 100
            
            # Calculate voice time in minutes
            voice_seconds = user_data.get("voice_time", 0)
            voice_minutes = voice_seconds / 60
            
            # Create result
            result = {
                "user_id": user_id,
                "text_xp": text_xp,
                "voice_xp": voice_xp,
                "total_xp": total_xp,
                "level": level,
                "current_level_xp": current_level_xp,
                "xp_needed": xp_to_next_level,
                "progress": progress,
                "total_messages": user_data.get("message_count", 0),
                "total_voice_seconds": voice_seconds,
                "total_voice_minutes": voice_minutes,
                "last_message_time": user_data.get("last_message_time", 0)
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting user XP: {str(e)}\n{traceback.format_exc()}")
            return None
    
    async def set_user_xp(self, user_id: int, guild_id: int, text_xp: int, voice_xp: int) -> bool:
        """Set XP values for a user
        
        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            text_xp: Text XP value
            voice_xp: Voice XP value
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Get user data
            user_id_str = str(user_id)
            
            if user_id_str not in guild_data:
                guild_data[user_id_str] = {}
                
            user_data = guild_data[user_id_str]
            
            # Get previous values for level calculation
            old_text_xp = user_data.get("text_xp", 0)
            old_voice_xp = user_data.get("voice_xp", 0)
            old_total_xp = old_text_xp + old_voice_xp
            
            # Update values
            user_data["text_xp"] = max(0, text_xp)
            user_data["voice_xp"] = max(0, voice_xp)
            
            # Calculate new total
            new_total_xp = user_data["text_xp"] + user_data["voice_xp"]
            
            # Save data
            self.user_data[guild_id] = guild_data
            await self._save_guild_data(guild_id)
            
            # Get config for level calculation
            config = await self.get_config(guild_id)
            level_curve = config["level_curve"]
            
            # Calculate old and new levels
            old_level = self._calculate_level(old_total_xp, level_curve)
            new_level = self._calculate_level(new_total_xp, level_curve)
            
            # Return level change info
            return (True, old_level, new_level, new_level > old_level)
            
        except Exception as e:
            self.logger.error(f"Error setting user XP: {str(e)}\n{traceback.format_exc()}")
            return (False, 0, 0, False)
    
    async def add_user_xp(self, user_id: int, guild_id: int, text_xp: int = 0, voice_xp: int = 0) -> tuple:
        """Add XP to a user
        
        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            text_xp: Text XP to add
            voice_xp: Voice XP to add
            
        Returns:
            Tuple of (success, old_level, new_level, leveled_up)
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Get user data
            user_id_str = str(user_id)
            
            if user_id_str not in guild_data:
                guild_data[user_id_str] = {
                    "text_xp": 0,
                    "voice_xp": 0,
                    "message_count": 0,
                    "voice_time": 0,
                    "last_message_time": 0
                }
                
            user_data = guild_data[user_id_str]
            
            # Get previous values for level calculation
            old_text_xp = user_data.get("text_xp", 0)
            old_voice_xp = user_data.get("voice_xp", 0)
            old_total_xp = old_text_xp + old_voice_xp
            
            # Update values
            user_data["text_xp"] = max(0, old_text_xp + text_xp)
            user_data["voice_xp"] = max(0, old_voice_xp + voice_xp)
            
            # Calculate new total
            new_total_xp = user_data["text_xp"] + user_data["voice_xp"]
            
            # Save data
            self.user_data[guild_id] = guild_data
            await self._save_guild_data(guild_id)
            
            # Get config for level calculation
            config = await self.get_config(guild_id)
            level_curve = config["level_curve"]
            
            # Calculate old and new levels
            old_level = self._calculate_level(old_total_xp, level_curve)
            new_level = self._calculate_level(new_total_xp, level_curve)
            
            # Return level change info
            return (True, old_level, new_level, new_level > old_level)
            
        except Exception as e:
            self.logger.error(f"Error adding user XP: {str(e)}\n{traceback.format_exc()}")
            return (False, 0, 0, False)
    
    async def reset_user_xp(self, user_id: int, guild_id: int) -> bool:
        """Reset XP for a user
        
        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            
        Returns:
            True if reset successfully, False otherwise
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Remove user data
            user_id_str = str(user_id)
            
            if user_id_str in guild_data:
                del guild_data[user_id_str]
                
                # Save data
                self.user_data[guild_id] = guild_data
                await self._save_guild_data(guild_id)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting user XP: {str(e)}\n{traceback.format_exc()}")
            return False
    
    async def get_user_rank(self, user_id: int, guild_id: int) -> int:
        """Get user's rank on the leaderboard
        
        Args:
            user_id: The Discord user ID
            guild_id: The Discord guild ID
            
        Returns:
            Rank position (1-based) or 0 if not found
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Check if user exists
            user_id_str = str(user_id)
            
            if user_id_str not in guild_data:
                return 0
                
            # Get all users and sort by total XP
            users = []
            
            for user_id_key, data in guild_data.items():
                text_xp = data.get("text_xp", 0)
                voice_xp = data.get("voice_xp", 0)
                total_xp = text_xp + voice_xp
                
                users.append({
                    "user_id": int(user_id_key),
                    "total_xp": total_xp
                })
                
            # Sort by XP (descending)
            users.sort(key=lambda u: u["total_xp"], reverse=True)
            
            # Find user position
            for i, user in enumerate(users):
                if user["user_id"] == user_id:
                    return i + 1
                    
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting user rank: {str(e)}\n{traceback.format_exc()}")
            return 0
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """Get the server leaderboard
        
        Args:
            guild_id: The Discord guild ID
            limit: Number of entries to return
            offset: Offset from top of leaderboard
            
        Returns:
            Dictionary with leaderboard data and total user count
        """
        try:
            # Load guild data
            guild_data = await self._load_guild_data(guild_id)
            
            # Get config for calculations
            config = await self.get_config(guild_id)
            level_curve = config["level_curve"]
            
            # Get all users and calculate levels
            users = []
            
            for user_id_str, data in guild_data.items():
                text_xp = data.get("text_xp", 0)
                voice_xp = data.get("voice_xp", 0)
                total_xp = text_xp + voice_xp
                level = self._calculate_level(total_xp, level_curve)
                
                users.append({
                    "user_id": int(user_id_str),
                    "text_xp": text_xp,
                    "voice_xp": voice_xp,
                    "total_xp": total_xp,
                    "level": level
                })
                
            # Sort by XP (descending)
            users.sort(key=lambda u: u["total_xp"], reverse=True)
            
            # Apply pagination
            total_users = len(users)
            
            if offset < 0:
                offset = 0
                
            if offset >= total_users:
                offset = max(0, total_users - limit)
                
            users_page = users[offset:offset + limit]
            
            # Add rank to each user
            for i, user in enumerate(users_page):
                user["rank"] = offset + i + 1
                
            # Create result
            result = {
                "leaderboard": users_page,
                "total_users": total_users
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting leaderboard: {str(e)}\n{traceback.format_exc()}")
            return {"leaderboard": [], "total_users": 0}
    
    def _calculate_xp_for_level(self, level: int, level_curve: Dict[str, Any]) -> int:
        """Calculate XP required for a given level
        
        Args:
            level: The level to calculate
            level_curve: Level curve configuration
            
        Returns:
            XP required to reach the level
        """
        if level <= 0:
            return 0
            
        base = level_curve["base"]
        exponent = level_curve["exponent"]
        
        return int(base * (level ** exponent))
    
    def _calculate_level(self, total_xp: int, level_curve: Dict[str, Any]) -> int:
        """Calculate level from total XP
        
        Args:
            total_xp: Total XP amount
            level_curve: Level curve configuration
            
        Returns:
            Level based on XP
        """
        level = 0
        xp_needed = self._calculate_xp_for_level(level + 1, level_curve)
        
        while total_xp >= xp_needed:
            level += 1
            xp_needed = self._calculate_xp_for_level(level + 1, level_curve)
            
        return level
    
    async def reward_xp_for_message(self, message: discord.Message) -> tuple:
        """Award XP for a message
        
        Args:
            message: The Discord message
            
        Returns:
            Tuple of (success, old_level, new_level, leveled_up)
        """
        # Skip invalid messages
        if not message.guild or message.author.bot:
            return (False, 0, 0, False)
            
        try:
            # Get config
            config = await self.get_config(message.guild.id)
            
            # Skip if disabled
            if not config.get("enabled", True):
                return (False, 0, 0, False)
                
            # Load guild data
            guild_data = await self._load_guild_data(message.guild.id)
            
            # Get user data
            user_id_str = str(message.author.id)
            
            if user_id_str not in guild_data:
                guild_data[user_id_str] = {
                    "text_xp": 0,
                    "voice_xp": 0,
                    "message_count": 0,
                    "voice_time": 0,
                    "last_message_time": 0
                }
                
            user_data = guild_data[user_id_str]
            
            # Check cooldown
            now = datetime.datetime.now().timestamp()
            last_message_time = user_data.get("last_message_time", 0)
            cooldown = config["text_xp"]["cooldown_seconds"]
            
            if now - last_message_time < cooldown:
                return (False, 0, 0, False)
                
            # Update message count
            user_data["message_count"] = user_data.get("message_count", 0) + 1
            
            # Update last message time
            user_data["last_message_time"] = now
            
            # Calculate XP to award
            min_xp = config["text_xp"]["min"]
            max_xp = config["text_xp"]["max"]
            
            xp_amount = random.randint(min_xp, max_xp)
            
            # Get previous values for level calculation
            old_text_xp = user_data.get("text_xp", 0)
            old_voice_xp = user_data.get("voice_xp", 0)
            old_total_xp = old_text_xp + old_voice_xp
            
            # Update XP
            user_data["text_xp"] = old_text_xp + xp_amount
            
            # Calculate new total
            new_total_xp = user_data["text_xp"] + old_voice_xp
            
            # Save data
            self.user_data[message.guild.id] = guild_data
            await self._save_guild_data(message.guild.id)
            
            # Calculate old and new levels
            level_curve = config["level_curve"]
            old_level = self._calculate_level(old_total_xp, level_curve)
            new_level = self._calculate_level(new_total_xp, level_curve)
            
            # Return level change info
            return (True, old_level, new_level, new_level > old_level)
            
        except Exception as e:
            self.logger.error(f"Error rewarding XP for message: {str(e)}\n{traceback.format_exc()}")
            return (False, 0, 0, False)
    
    async def start_voice_tracking(self, member: discord.Member, voice_state: discord.VoiceState) -> None:
        """Start tracking voice activity for a member
        
        Args:
            member: The Discord member
            voice_state: The voice state
        """
        if not member.guild or member.bot:
            return
            
        try:
            # Get config
            config = await self.get_config(member.guild.id)
            
            # Skip if disabled
            if not config.get("enabled", True):
                return
                
            # Create session data
            session_key = f"{member.guild.id}:{member.id}"
            
            self.voice_sessions[session_key] = {
                "start_time": datetime.datetime.now().timestamp(),
                "channel_id": voice_state.channel.id,
                "guild_id": member.guild.id,
                "user_id": member.id,
                "afk": voice_state.afk,
                "self_mute": voice_state.self_mute,
                "self_deaf": voice_state.self_deaf,
                "last_update": datetime.datetime.now().timestamp()
            }
            
        except Exception as e:
            self.logger.error(f"Error starting voice tracking: {str(e)}\n{traceback.format_exc()}")
    
    async def end_voice_tracking(self, member: discord.Member, voice_state: discord.VoiceState) -> None:
        """End tracking voice activity for a member
        
        Args:
            member: The Discord member
            voice_state: The voice state
        """
        if not member.guild or member.bot:
            return
            
        try:
            # Get session
            session_key = f"{member.guild.id}:{member.id}"
            
            if session_key not in self.voice_sessions:
                return
                
            session = self.voice_sessions[session_key]
            
            # Calculate duration
            start_time = session["start_time"]
            end_time = datetime.datetime.now().timestamp()
            duration_seconds = end_time - start_time
            
            # Get config
            config = await self.get_config(member.guild.id)
            
            # Calculate XP
            voice_xp = await self._calculate_voice_xp(member, session, duration_seconds, config)
            
            # Update user data with voice time and XP
            if voice_xp > 0:
                # Load guild data
                guild_data = await self._load_guild_data(member.guild.id)
                
                # Get user data
                user_id_str = str(member.id)
                
                if user_id_str not in guild_data:
                    guild_data[user_id_str] = {
                        "text_xp": 0,
                        "voice_xp": 0,
                        "message_count": 0,
                        "voice_time": 0,
                        "last_message_time": 0
                    }
                    
                user_data = guild_data[user_id_str]
                
                # Update voice time
                user_data["voice_time"] = user_data.get("voice_time", 0) + int(duration_seconds)
                
                # Update voice XP
                user_data["voice_xp"] = user_data.get("voice_xp", 0) + voice_xp
                
                # Save data
                self.user_data[member.guild.id] = guild_data
                await self._save_guild_data(member.guild.id)
            
            # Remove session
            del self.voice_sessions[session_key]
            
        except Exception as e:
            self.logger.error(f"Error ending voice tracking: {str(e)}\n{traceback.format_exc()}")
    
    async def update_voice_tracking(self, member: discord.Member, voice_state: discord.VoiceState) -> None:
        """Update tracking for voice activity
        
        Args:
            member: The Discord member
            voice_state: The voice state
        """
        if not member.guild or member.bot:
            return
            
        try:
            # Get session
            session_key = f"{member.guild.id}:{member.id}"
            
            if session_key not in self.voice_sessions:
                # Start new session if not exists
                await self.start_voice_tracking(member, voice_state)
                return
                
            session = self.voice_sessions[session_key]
            
            # Calculate duration since last update
            last_update = session["last_update"]
            now = datetime.datetime.now().timestamp()
            duration_seconds = now - last_update
            
            # Skip if too short (less than a minute)
            if duration_seconds < 60:
                # Just update state
                session["afk"] = voice_state.afk
                session["self_mute"] = voice_state.self_mute
                session["self_deaf"] = voice_state.self_deaf
                session["last_update"] = now
                return
                
            # Get config
            config = await self.get_config(member.guild.id)
            
            # Calculate XP
            voice_xp = await self._calculate_voice_xp(member, session, duration_seconds, config)
            
            # Update user data with voice time and XP
            if voice_xp > 0:
                # Load guild data
                guild_data = await self._load_guild_data(member.guild.id)
                
                # Get user data
                user_id_str = str(member.id)
                
                if user_id_str not in guild_data:
                    guild_data[user_id_str] = {
                        "text_xp": 0,
                        "voice_xp": 0,
                        "message_count": 0,
                        "voice_time": 0,
                        "last_message_time": 0
                    }
                    
                user_data = guild_data[user_id_str]
                
                # Update voice time
                user_data["voice_time"] = user_data.get("voice_time", 0) + int(duration_seconds)
                
                # Update voice XP
                user_data["voice_xp"] = user_data.get("voice_xp", 0) + voice_xp
                
                # Save data
                self.user_data[member.guild.id] = guild_data
                await self._save_guild_data(member.guild.id)
            
            # Update session
            session["afk"] = voice_state.afk
            session["self_mute"] = voice_state.self_mute
            session["self_deaf"] = voice_state.self_deaf
            session["last_update"] = now
            
        except Exception as e:
            self.logger.error(f"Error updating voice tracking: {str(e)}\n{traceback.format_exc()}")
    
    async def _calculate_voice_xp(self, member: discord.Member, session: Dict[str, Any], 
                               duration_seconds: float, config: Dict[str, Any]) -> int:
        """Calculate voice XP based on session data
        
        Args:
            member: The Discord member
            session: Voice session data
            duration_seconds: Duration in seconds
            config: Leveling configuration
            
        Returns:
            XP to award
        """
        try:
            # Get channel
            channel = member.guild.get_channel(session["channel_id"])
            
            if not channel:
                return 0
                
            # Base XP calculation
            voice_config = config["voice_xp"]
            minutes = duration_seconds / 60
            base_xp = int(minutes * voice_config["per_minute"])
            
            # Apply AFK multiplier if in AFK channel or self AFK
            if session["afk"] or (member.guild.afk_channel and channel.id == member.guild.afk_channel.id):
                return int(base_xp * voice_config["afk_multiplier"])
                
            # Check if solo in channel
            members_in_channel = len([m for m in channel.members if not m.bot])
            
            if members_in_channel <= 1:
                return int(base_xp * voice_config["solo_multiplier"])
                
            # Apply self mute/deaf reduction if enabled
            if session["self_mute"] and session["self_deaf"]:
                return int(base_xp * 0.5)  # Both muted and deafened: 50%
            elif session["self_mute"] or session["self_deaf"]:
                return int(base_xp * 0.75)  # Either muted or deafened: 75%
                
            # Return full XP
            return base_xp
            
        except Exception as e:
            self.logger.error(f"Error calculating voice XP: {str(e)}\n{traceback.format_exc()}")
            return 0
    
    async def process_level_rewards(self, member: discord.Member, new_level: int) -> None:
        """Process rewards for a level up
        
        Args:
            member: The Discord member
            new_level: The new level
        """
        if not member.guild or member.bot:
            return
            
        try:
            # Get config
            config = await self.get_config(member.guild.id)
            
            # Check if rewards are enabled
            rewards = config.get("rewards", {})
            
            if not rewards.get("enabled", False):
                return
                
            # Check if there are role rewards
            role_rewards = rewards.get("roles", {})
            
            if not role_rewards:
                return
                
            # Process role rewards
            available_roles = []
            
            # Convert level strings to integers and sort
            level_roles = {}
            for level_str, role_id in role_rewards.items():
                try:
                    level_int = int(level_str)
                    level_roles[level_int] = role_id
                except ValueError:
                    continue
                    
            sorted_levels = sorted(level_roles.keys())
            
            # Find roles for the current level and below
            for level in sorted_levels:
                if level <= new_level:
                    role_id = level_roles[level]
                    role = member.guild.get_role(int(role_id))
                    
                    if role and role not in member.roles:
                        available_roles.append(role)
            
            # Skip if no roles to add
            if not available_roles:
                return
                
            # Check if roles stack
            stack_roles = config.get("settings", {}).get("stack_roles", True)
            
            # Get existing level roles if not stacking
            if not stack_roles:
                existing_level_roles = []
                
                for role in member.roles:
                    if role.id in role_rewards.values():
                        existing_level_roles.append(role)
                        
                # Remove existing level roles
                if existing_level_roles:
                    try:
                        await member.remove_roles(*existing_level_roles, reason="Level Role Update")
                    except Exception as e:
                        self.logger.error(f"Error removing old level roles: {str(e)}")
            
            # Add new roles
            if available_roles:
                try:
                    await member.add_roles(*available_roles, reason="Level Role Reward")
                except Exception as e:
                    self.logger.error(f"Error adding level reward roles: {str(e)}")
            
        except Exception as e:
            self.logger.error(f"Error processing level rewards: {str(e)}\n{traceback.format_exc()}")
    
    async def generate_rank_card(self, member: discord.Member) -> Optional[discord.File]:
        """Generate a rank card image for a user
        
        Args:
            member: The Discord member
            
        Returns:
            Discord file with rank card image or None if error
        """
        try:
            # Load guild_data for direct rank calculations
            guild_data = await self._load_guild_data(member.guild.id)
            config = await self.get_config(member.guild.id)
            level_curve = config["level_curve"]
            
            user_id_str = str(member.id)
            if user_id_str not in guild_data:
                return None
                
            u_data = guild_data[user_id_str]
            text_xp = u_data.get("text_xp", 0)
            voice_xp = u_data.get("voice_xp", 0)
            
            # Sort for ranks
            users_text = [{"id": uid, "xp": d.get("text_xp", 0)} for uid, d in guild_data.items()]
            users_text.sort(key=lambda x: x["xp"], reverse=True)
            text_rank = next((i+1 for i, u in enumerate(users_text) if int(u["id"]) == member.id), 0)
            
            users_voice = [{"id": uid, "xp": d.get("voice_xp", 0)} for uid, d in guild_data.items()]
            users_voice.sort(key=lambda x: x["xp"], reverse=True)
            voice_rank = next((i+1 for i, u in enumerate(users_voice) if int(u["id"]) == member.id), 0)
            
            # Calculate levels for text and voice independently
            text_level = self._calculate_level(text_xp, level_curve)
            voice_level = self._calculate_level(voice_xp, level_curve)
            
            def get_xp_progress(curr_xp, level):
                needed = self._calculate_xp_for_level(level + 1, level_curve)
                prev = self._calculate_xp_for_level(level, level_curve)
                return curr_xp - prev, needed - prev
                
            text_cur, text_req = get_xp_progress(text_xp, text_level)
            voice_cur, voice_req = get_xp_progress(voice_xp, voice_level)
            
            WIDTH, HEIGHT = 800, 280
            
            # Select Theme colors
            accent_color = member.color.to_rgb()
            if accent_color == (0, 0, 0):
                accent_color = (114, 137, 218)
                
            bg_base = (20, 22, 28, 255)
            
            # Create base image with transparent background
            img = Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 0))
            
            # Draw rounded card mask
            radius = 25
            mask = Image.new("L", (WIDTH, HEIGHT), 0)
            mask_draw = ImageDraw.Draw(mask)
            try:
                mask_draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=radius, fill=255)
            except AttributeError:
                mask_draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=255)
                
            # Load background image
            try:
                import os
                bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "image.png")
                bg_img = Image.open(bg_path).convert("RGBA")
                # Resize and crop to fill the Width and Height
                # If image is smaller, this scales it up
                bg_w, bg_h = bg_img.size
                scale = max(WIDTH/bg_w, HEIGHT/bg_h)
                new_w, new_h = int(bg_w * scale), int(bg_h * scale)
                bg_img = bg_img.resize((new_w, new_h))
                # Crop center
                left = (new_w - WIDTH) // 2
                top = (new_h - HEIGHT) // 2
                bg_img = bg_img.crop((left, top, left + WIDTH, top + HEIGHT))
            except Exception as e:
                self.logger.error(f"Error loading background image: {e}")
                # Fallback to dark bg
                bg_img = Image.new("RGBA", (WIDTH, HEIGHT), bg_base)
                
            # Paste background using mask for rounded corners
            img.paste(bg_img, (0, 0), mask)
            
            draw = ImageDraw.Draw(img)
            
            # Left sidebar dark overlay
            try:
                # Add transparency overlapping
                sidebar_overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
                sd_draw = ImageDraw.Draw(sidebar_overlay)
                sd_draw.ellipse([(-100, -100), (320, HEIGHT+100)], fill=(12, 14, 18, 230))
                img.paste(sidebar_overlay, (0, 0), sidebar_overlay)
            except Exception:
                pass
            
            # Load fonts
            def load_font(font_names, size):
                for name in font_names:
                    try:
                        return ImageFont.truetype(name, size)
                    except Exception:
                        continue
                return ImageFont.load_default()
                
            title_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], 36)
            label_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], 16)  # Bold format
            num_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], 28)
            info_font = load_font(["arial.ttf", "LiberationSans-Regular.ttf"], 15)
            
            # Download avatar
            avatar_radius = 90
            avatar_x, avatar_y = 50, HEIGHT // 2 - avatar_radius
            avatar_img = None
            
            try:
                avatar_url = member.display_avatar.url
                async with self.bot.session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        av_raw = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                        av_raw = av_raw.resize((avatar_radius*2, avatar_radius*2))
                        
                        av_mask = Image.new("L", (avatar_radius*2, avatar_radius*2), 0)
                        av_mask_draw = ImageDraw.Draw(av_mask)
                        av_mask_draw.ellipse((0, 0, avatar_radius*2, avatar_radius*2), fill=255)
                        
                        avatar_img = Image.new("RGBA", (avatar_radius*2, avatar_radius*2))
                        avatar_img.paste(av_raw, (0, 0), av_mask)
            except Exception as e:
                self.logger.error(f"Error downloading avatar: {str(e)}")
            
            # Draw avatar stroke
            stroke_width = 4
            try:
                draw.ellipse(
                    (avatar_x - stroke_width, avatar_y - stroke_width, 
                     avatar_x + avatar_radius*2 + stroke_width, avatar_y + avatar_radius*2 + stroke_width),
                    fill=(150, 160, 180)
                )
            except Exception:
                pass

            if avatar_img:
                img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
                
            # Top text: Username
            d_name = member.display_name
            if len(d_name) > 16:
                d_name = d_name[:14] + "..."
            draw.text((280, 20), d_name, fill=(255, 255, 255), font=title_font)
            
            # Helper to draw progress bars
            def draw_stat_row(draw_obj, base_y, level, is_text, rank, total, curr, req):
                # LVL text
                draw_obj.text((280, base_y), "LVL", fill=(200, 200, 220), font=label_font, anchor="mm")
                draw_obj.text((280, base_y+26), str(level), fill=(255, 255, 255), font=num_font, anchor="mm")
                
                # Icons
                icon_x = 315
                icon_y = base_y
                if is_text:
                    try:
                        draw_obj.rounded_rectangle([(icon_x, icon_y-2), (icon_x+24, icon_y+16)], radius=4, fill=(220, 220, 220))
                    except:
                        draw_obj.rectangle([(icon_x, icon_y-2), (icon_x+24, icon_y+16)], fill=(220, 220, 220))
                    draw_obj.polygon([(icon_x+5, icon_y+16), (icon_x+10, icon_y+16), (icon_x+5, icon_y+22)], fill=(220, 220, 220))
                    draw_obj.ellipse((icon_x+4, icon_y+5, icon_x+7, icon_y+8), fill=(50,50,50))
                    draw_obj.ellipse((icon_x+10, icon_y+5, icon_x+13, icon_y+8), fill=(50,50,50))
                    draw_obj.ellipse((icon_x+16, icon_y+5, icon_x+19, icon_y+8), fill=(50,50,50))
                else:
                    try:
                        draw_obj.rounded_rectangle([(icon_x+6, icon_y-3), (icon_x+14, icon_y+13)], radius=4, fill=(220,220,220))
                    except:
                        draw_obj.rectangle([(icon_x+6, icon_y-3), (icon_x+14, icon_y+13)], fill=(220,220,220))
                    draw_obj.arc([(icon_x+3, icon_y+5), (icon_x+17, icon_y+19)], start=0, end=180, fill=(220,220,220), width=3)
                    draw_obj.line([(icon_x+10, icon_y+19), (icon_x+10, icon_y+24)], fill=(220,220,220), width=3)
                    draw_obj.line([(icon_x+5, icon_y+24), (icon_x+15, icon_y+24)], fill=(220,220,220), width=3)
                
                # Info text
                bar_x = 360
                draw_obj.text((bar_x, base_y-5), f"Rank: #{rank}", fill=(220, 220, 230), font=info_font)
                draw_obj.text((760, base_y-5), f"Total: {total}", fill=(220, 220, 230), font=info_font, anchor="ra")
                
                # Progress bar
                bar_w = 400
                bar_h = 24
                bar_y = base_y + 15
                bar_radius = 12
                
                try:
                    draw_obj.rounded_rectangle([(bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h)], radius=bar_radius, fill=(30, 30, 35, 180), outline=(150, 150, 160), width=2)
                except AttributeError:
                    draw_obj.rectangle([(bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h)], fill=(30, 30, 35, 180))
                    
                # Fill
                pct = curr / req if req > 0 else 0
                pct = min(1.0, max(0.0, pct))
                prog = int(bar_w * pct)
                if prog > bar_radius * 2:
                    try:
                        draw_obj.rounded_rectangle([(bar_x+2, bar_y+2), (bar_x+prog-2, bar_y+bar_h-2)], radius=bar_radius-2, fill=(200, 210, 230, 255))
                    except AttributeError:
                        draw_obj.rectangle([(bar_x+2, bar_y+2), (bar_x+prog-2, bar_y+bar_h-2)], fill=(200, 210, 230, 255))
                
                # Center text inside bar
                draw_obj.text((bar_x + bar_w//2, bar_y + bar_h//2), f"{curr} / {req}", fill=(255, 255, 255) if pct < 0.5 else (20, 20, 20), font=info_font, anchor="mm")

            # Draw Text Row
            draw_stat_row(draw, 100, text_level, True, text_rank, text_xp, text_cur, text_req)
            
            # Draw Voice Row
            draw_stat_row(draw, 190, voice_level, False, voice_rank, voice_xp, voice_cur, voice_req)
            
            # Save image to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            return discord.File(buffer, filename="rank_card.png")
            
        except Exception as e:
            self.logger.error(f"Error generating rank card: {str(e)}\n{traceback.format_exc()}")
            return None