import discord
import asyncio
import datetime
import re
import json
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
import traceback


class AutoModerationSystem:
    """Core system for server auto-moderation functionality"""
    
    # Default settings
    DEFAULT_CONFIG = {
        "enabled": False,
        "log_channel_id": None,
        "modules": {
            "anti_spam": {
                "enabled": True,
                "max_messages": 5,
                "interval_seconds": 5,
                "action": "timeout",
                "duration_minutes": 10
            },
            "anti_mention_spam": {
                "enabled": True,
                "max_mentions": 5,
                "interval_seconds": 10,
                "action": "timeout",
                "duration_minutes": 15
            },
            "link_filter": {
                "enabled": True,
                "whitelist": [],
                "blacklist": [],
                "action": "delete",
                "duration_minutes": 0
            },
            "bad_words": {
                "enabled": True,
                "words": [],
                "custom_words": [],
                "action": "warn",
                "duration_minutes": 0
            }
        },
        "exempt_roles": [],
        "exempt_channels": []
    }
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        
        # Set up data directory
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True, parents=True)
        
        # Cache of server configurations
        self.server_configs = {}
        
        # Cache of user recent actions for spam detection
        self.recent_messages = {}
        self.recent_mentions = {}
        
        # Load default bad words list
        self.default_bad_words = self._load_default_bad_words()
    
    def _load_default_bad_words(self) -> List[str]:
        """Load default bad words list"""
        try:
            bad_words_path = self.data_dir / "bad_words.json"
            
            # Create default file if it doesn't exist
            if not bad_words_path.exists():
                default_words = [
                    "badword1", "badword2"  # Placeholder for actual bad words
                ]
                
                with open(bad_words_path, 'w', encoding='utf-8') as f:
                    json.dump(default_words, f, indent=2)
                
                return default_words
            
            # Load existing file
            with open(bad_words_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Error loading default bad words: {str(e)}")
            return []
    
    async def get_config(self, guild_id: int) -> Dict[str, Any]:
        """Get automod configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            
        Returns:
            Automod configuration dictionary
        """
        # Check cache first
        if guild_id in self.server_configs:
            return self.server_configs[guild_id]
            
        # Load from file
        config_path = self.data_dir / f"automod_{guild_id}.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                # Merge with defaults to ensure all fields exist
                merged_config = self._merge_with_defaults(config)
                self.server_configs[guild_id] = merged_config
                return merged_config
                
            except Exception as e:
                self.logger.error(f"Error loading automod config for {guild_id}: {str(e)}")
        
        # Use default if no config found
        self.server_configs[guild_id] = self.DEFAULT_CONFIG.copy()
        return self.server_configs[guild_id]
    
    async def save_config(self, guild_id: int, config: Dict[str, Any]) -> bool:
        """Save automod configuration for a guild
        
        Args:
            guild_id: The Discord guild ID
            config: Automod configuration dictionary
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Update cache
            self.server_configs[guild_id] = config
            
            # Save to file
            config_path = self.data_dir / f"automod_{guild_id}.json"
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving automod config for {guild_id}: {str(e)}")
            return False
    
    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure config has all required fields by merging with defaults"""
        merged = self.DEFAULT_CONFIG.copy()
        
        # Top level merge
        for key, value in config.items():
            if key in merged:
                if isinstance(value, dict) and isinstance(merged[key], dict):
                    # For nested dictionaries, merge recursively
                    merged[key] = self._merge_dicts(merged[key], value)
                else:
                    # For simple values, replace
                    merged[key] = value
        
        return merged
    
    def _merge_dicts(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to recursively merge dictionaries"""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_dicts(result[key], value)
            else:
                result[key] = value
                
        return result
    
    async def is_exempt(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        """Check if a message is exempt from automod
        
        Args:
            message: The Discord message
            config: Automod configuration
            
        Returns:
            True if exempt, False otherwise
        """
        # Skip if user is bot or webhook
        if message.author.bot or message.webhook_id:
            return True
            
        # Skip DMs
        if not message.guild:
            return True
            
        # Skip if user has admin or manage messages permission
        if (message.author.guild_permissions.administrator or 
            message.author.guild_permissions.manage_messages):
            return True
            
        # Skip if channel is exempt
        if message.channel.id in config.get("exempt_channels", []):
            return True
            
        # Skip if user has exempt role
        if any(role.id in config.get("exempt_roles", []) for role in message.author.roles):
            return True
            
        return False
    
    async def check_message(self, message: discord.Message) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check a message against automod rules
        
        Args:
            message: The Discord message
            
        Returns:
            Tuple of (violation_found, rule_name, action)
        """
        # Skip if no guild
        if not message.guild:
            return False, None, None
            
        # Get config
        config = await self.get_config(message.guild.id)
        
        # Skip if automod disabled
        if not config.get("enabled", False):
            return False, None, None
            
        # Skip exempt users/channels
        if await self.is_exempt(message, config):
            return False, None, None
            
        # Check against each rule
        
        # 1. Anti-spam
        spam_config = config["modules"]["anti_spam"]
        if spam_config.get("enabled", False):
            if await self._check_spam(message, spam_config):
                return True, "anti_spam", spam_config.get("action", "delete")
        
        # 2. Anti-mention spam
        mention_config = config["modules"]["anti_mention_spam"]
        if mention_config.get("enabled", False):
            if await self._check_mention_spam(message, mention_config):
                return True, "anti_mention_spam", mention_config.get("action", "delete")
        
        # 3. Link filter
        link_config = config["modules"]["link_filter"]
        if link_config.get("enabled", False):
            if await self._check_links(message, link_config):
                return True, "link_filter", link_config.get("action", "delete")
        
        # 4. Bad words filter
        words_config = config["modules"]["bad_words"]
        if words_config.get("enabled", False):
            if await self._check_bad_words(message, words_config):
                return True, "bad_words", words_config.get("action", "delete")
        
        # No violations
        return False, None, None
    
    async def _check_spam(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        """Check for message spam
        
        Args:
            message: The Discord message
            config: Anti-spam configuration
            
        Returns:
            True if spam detected, False otherwise
        """
        max_messages = config.get("max_messages", 5)
        interval = config.get("interval_seconds", 5)
        
        author_id = message.author.id
        channel_id = message.channel.id
        
        # Initialize tracking for this user if needed
        if author_id not in self.recent_messages:
            self.recent_messages[author_id] = {}
            
        if channel_id not in self.recent_messages[author_id]:
            self.recent_messages[author_id][channel_id] = []
        
        # Get timestamp
        now = datetime.datetime.now().timestamp()
        
        # Add current message
        self.recent_messages[author_id][channel_id].append(now)
        
        # Clean old messages
        cutoff = now - interval
        self.recent_messages[author_id][channel_id] = [
            ts for ts in self.recent_messages[author_id][channel_id] if ts > cutoff
        ]
        
        # Check count
        return len(self.recent_messages[author_id][channel_id]) >= max_messages
    
    async def _check_mention_spam(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        """Check for mention spam
        
        Args:
            message: The Discord message
            config: Anti-mention-spam configuration
            
        Returns:
            True if mention spam detected, False otherwise
        """
        max_mentions = config.get("max_mentions", 5)
        interval = config.get("interval_seconds", 10)
        
        # Count mentions in this message
        mention_count = len(message.mentions) + len(message.role_mentions)
        
        # Quick check - if this single message has too many mentions
        if mention_count >= max_mentions:
            return True
            
        # Track mentions over time
        author_id = message.author.id
        
        # Initialize tracking for this user if needed
        if author_id not in self.recent_mentions:
            self.recent_mentions[author_id] = []
        
        # Get timestamp
        now = datetime.datetime.now().timestamp()
        
        # Add current mentions
        self.recent_mentions[author_id].extend([now] * mention_count)
        
        # Clean old mentions
        cutoff = now - interval
        self.recent_mentions[author_id] = [
            ts for ts in self.recent_mentions[author_id] if ts > cutoff
        ]
        
        # Check count
        return len(self.recent_mentions[author_id]) >= max_mentions
    
    async def _check_links(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        """Check for disallowed links
        
        Args:
            message: The Discord message
            config: Link filter configuration
            
        Returns:
            True if disallowed link detected, False otherwise
        """
        # Skip if empty message
        if not message.content:
            return False
            
        # URL regex
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        
        # Find all URLs in the message
        urls = re.findall(url_pattern, message.content)
        
        # Skip if no URLs
        if not urls:
            return False
            
        whitelist = config.get("whitelist", [])
        blacklist = config.get("blacklist", [])
        
        for url in urls:
            # Check blacklist first
            if blacklist and any(bad_url in url for bad_url in blacklist):
                return True
                
            # If whitelist is enabled and URL is not in it
            if whitelist and not any(good_url in url for good_url in whitelist):
                return True
        
        return False
    
    async def _check_bad_words(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        """Check for bad words
        
        Args:
            message: The Discord message
            config: Bad words filter configuration
            
        Returns:
            True if bad word detected, False otherwise
        """
        # Skip if empty message
        if not message.content:
            return False
            
        # Get word lists
        default_words = self.default_bad_words
        custom_words = config.get("custom_words", [])
        
        # Combine lists if needed
        bad_words = set(custom_words)
        if config.get("words", []) or not custom_words:
            bad_words.update(default_words)
        
        # Normalize message content
        content = message.content.lower()
        
        # Check for bad words
        for word in bad_words:
            # Check for word boundaries
            pattern = r'\b' + re.escape(word.lower()) + r'\b'
            if re.search(pattern, content):
                return True
        
        return False
    
    async def take_action(self, message: discord.Message, rule: str, action: str) -> None:
        """Take action against a user for a violation
        
        Args:
            message: The Discord message
            rule: The rule that was violated
            action: The action to take ("delete", "warn", "timeout", "kick")
        """
        try:
            guild = message.guild
            user = message.author
            config = await self.get_config(guild.id)
            
            # Get module config for this rule
            module_config = config["modules"].get(rule, {})
            duration_minutes = module_config.get("duration_minutes", 0)
            
            # Always delete the message first
            try:
                await message.delete()
            except discord.errors.NotFound:
                pass
            except discord.errors.Forbidden:
                # Can't delete, but can still take other actions
                pass
                
            # Send DM to the user
            try:
                action_name = action.title()
                if action == "timeout":
                    action_name = "Timed Out"
                
                dm_embed = discord.Embed(
                    title=f"⚠️ AutoMod {action_name}",
                    description=f"You've been {action.lower()}ed in {guild.name}",
                    color=discord.Color.red()
                )
                
                dm_embed.add_field(name="Reason", value=f"AutoMod: {rule.replace('_', ' ').title()} violation", inline=False)
                
                if duration_minutes > 0:
                    dm_embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=False)
                
                await user.send(embed=dm_embed)
            except:
                # Can't DM user, continue with other actions
                pass
            
            # Perform action based on type
            if action == "warn":
                # Just log a warning
                pass
                
            elif action == "timeout":
                if duration_minutes > 0:
                    # Convert minutes to seconds
                    duration = datetime.timedelta(minutes=duration_minutes)
                    await user.timeout(duration, reason=f"AutoMod: {rule.replace('_', ' ').title()} violation")
                
            elif action == "kick":
                await guild.kick(user, reason=f"AutoMod: {rule.replace('_', ' ').title()} violation")
            
            # Log the action to the server's log channel
            await self._log_action(message, rule, action, duration_minutes)
            
        except Exception as e:
            self.logger.error(f"Error taking automod action: {str(e)}")
    
    async def _log_action(
        self, message: discord.Message, rule: str, action: str, duration: int
    ) -> None:
        """Log an automod action to the configured log channel
        
        Args:
            message: The Discord message
            rule: The rule that was violated
            action: The action taken
            duration: The duration of the action in minutes (if applicable)
        """
        try:
            guild = message.guild
            config = await self.get_config(guild.id)
            
            # Get log channel
            log_channel_id = config.get("log_channel_id")
            if not log_channel_id:
                return
                
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"🛡️ AutoMod: {action.title()}",
                description=f"AutoMod has taken action in {message.channel.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now()
            )
            
            # Add user info
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
            embed.add_field(name="Rule Violation", value=rule.replace('_', ' ').title(), inline=True)
            
            if duration > 0:
                embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
            
            # Add message content (truncated if needed)
            content = message.content
            if len(content) > 1024:
                content = content[:1020] + "..."
                
            embed.add_field(name="Message Content", value=content, inline=False)
            
            # Send to log channel
            await log_channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error logging automod action: {str(e)}")


class AutoModEmbed:
    """Utility for creating AutoMod embeds"""
    
    @staticmethod
    def status(guild, config: Dict[str, Any]) -> discord.Embed:
        """Create an embed showing automod status"""
        enabled = config.get("enabled", False)
        
        embed = discord.Embed(
            title="🛡️ AutoMod Status",
            description=f"AutoMod is currently **{'ENABLED' if enabled else 'DISABLED'}**",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        
        # Log channel
        log_channel_id = config.get("log_channel_id")
        log_channel = guild.get_channel(log_channel_id) if log_channel_id else None
        
        embed.add_field(
            name="Log Channel",
            value=log_channel.mention if log_channel else "Not configured",
            inline=False
        )
        
        # Module statuses
        for module_name, module_config in config.get("modules", {}).items():
            module_enabled = module_config.get("enabled", False)
            action = module_config.get("action", "delete").title()
            
            # Format duration if present
            duration = module_config.get("duration_minutes", 0)
            duration_text = f" ({duration} min)" if duration > 0 else ""
            
            embed.add_field(
                name=f"{module_name.replace('_', ' ').title()}",
                value=f"{'✅' if module_enabled else '❌'} {action}{duration_text}",
                inline=True
            )
        
        # Exemptions
        exempt_roles = config.get("exempt_roles", [])
        exempt_channels = config.get("exempt_channels", [])
        
        # Format exemptions
        exempt_roles_text = "None"
        if exempt_roles:
            roles = [f"<@&{role_id}>" for role_id in exempt_roles[:5]]
            exempt_roles_text = ", ".join(roles)
            if len(exempt_roles) > 5:
                exempt_roles_text += f" and {len(exempt_roles) - 5} more"
        
        exempt_channels_text = "None"
        if exempt_channels:
            channels = [f"<#{channel_id}>" for channel_id in exempt_channels[:5]]
            exempt_channels_text = ", ".join(channels)
            if len(exempt_channels) > 5:
                exempt_channels_text += f" and {len(exempt_channels) - 5} more"
        
        embed.add_field(name="Exempt Roles", value=exempt_roles_text, inline=False)
        embed.add_field(name="Exempt Channels", value=exempt_channels_text, inline=False)
        
        return embed