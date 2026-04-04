import discord
import asyncio
import datetime
import re
import json
from typing import Dict, List, Optional, Union, Any, Tuple
from pathlib import Path
import traceback
import copy
import config


class AutoModerationSystem:
    """Core system for server auto-moderation functionality"""
    
    # Default settings
    DEFAULT_CONFIG = {
        "enabled": False,
        "log_channel_id": None,
        "strike_system": {
            "enabled": True,
            "decay_ladder_days": [3, 7, 14, 30],
            "thresholds": {
                "1": "warn",
                "2": "timeout_10m",
                "3": "timeout_1h",
                "5": "timeout_12h",
                "7": "timeout_24h",
                "10": "kick",
                "15": "ban"
            }
        },
        "modules": {
            "anti_spam": {
                "enabled": True,
                "max_messages": 5,
                "interval_seconds": 5,
                "action": "strike",
                "strikes": 1
            },
            "anti_mention_spam": {
                "enabled": True,
                "max_mentions": 5,
                "interval_seconds": 10,
                "action": "strike",
                "strikes": 1
            },
            "link_filter": {
                "enabled": True,
                "whitelist": [],
                "blacklist": [],
                "action": "strike",
                "strikes": 2
            },
            "bad_words": {
                "enabled": True,
                "words": config.BAD_WORDS or [],
                "custom_words": [],
                "use_defaults": True,
                "action": "strike",
                "strikes": 1
            },
            "anti_invite": {
                "enabled": True,
                "whitelist": [],
                "action": "strike",
                "strikes": 2
            },
            "anti_caps": {
                "enabled": True,
                "threshold_percent": 70,
                "min_length": 15,
                "action": "strike",
                "strikes": 1
            },
            "anti_zalgo": {
                "enabled": True,
                "action": "strike",
                "strikes": 1
            }
        },
        "exempt_roles": [],
        "exempt_channels": [],
        "strikes": {}
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
        
        # Leet-speak replacement mapping
        self.leet_mapping = {
            '4': 'a', '@': 'a', '8': 'b', '3': 'e', '1': 'i', '!': 'i', '0': 'o', 
            '5': 's', '$': 's', '7': 't', '9': 'g', '2': 'z', '6': 'g', 'z': 's'
        }
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content to handle leet-speak and bypasses"""
        # Convert to lowercase
        normalized = content.lower()
        
        # Replace common leet characters
        for char, replacement in self.leet_mapping.items():
            normalized = normalized.replace(char, replacement)
            
        # Remove extra whitespace and special characters used to bypass filters
        normalized = re.sub(r'[^a-z\s]', '', normalized)
        
        # Collapse repeated characters (e.g., "ffffuuuu" -> "fu")
        normalized = re.sub(r'(.)\1+', r'\1', normalized)
        
        return normalized
    
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
        config = copy.deepcopy(self.DEFAULT_CONFIG)
        self.server_configs[guild_id] = config
        
        # Automatically save the default config so the user can see it
        await self.save_config(guild_id, config)
        
        return config
    
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
        merged = copy.deepcopy(self.DEFAULT_CONFIG)
        
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
        result = copy.deepcopy(default)
        
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
    
    async def get_active_strikes(self, guild_id: int, user_id: int, config: Dict[str, Any]) -> int:
        """Calculate total active strikes for a user considering decay"""
        strikes_data = config.get("strikes", {})
        user_strikes = strikes_data.get(str(user_id), [])
        
        if not user_strikes:
            return 0
            
        now = datetime.datetime.now().timestamp()
        
        # Filter active strikes
        active_strikes = [s for s in user_strikes if s.get("expires", 0) > now]
        
        # Clean up expired strikes from config
        if len(active_strikes) != len(user_strikes):
            strikes_data[str(user_id)] = active_strikes
            config["strikes"] = strikes_data
            await self.save_config(guild_id, config)
            
        # Sum strike values
        return sum(s.get("value", 1) for s in active_strikes)
        
    async def add_strike(self, guild_id: int, user_id: int, rule: str, value: int, config: Dict[str, Any]) -> int:
        """Add strike(s) to a user and return their new total"""
        strikes_data = config.get("strikes", {})
        user_strikes = strikes_data.get(str(user_id), [])
        
        now = datetime.datetime.now().timestamp()
        
        # Clean up existing expired strikes first
        active_strikes = [s for s in user_strikes if s.get("expires", 0) > now]
        current_active = sum(s.get("value", 1) for s in active_strikes)
        
        # Determine decay time for this new strike based on current active strikes
        decay_ladder = config.get("strike_system", {}).get("decay_ladder_days", [3, 7, 14, 30])
        ladder_index = min(current_active, len(decay_ladder) - 1)
        decay_days = decay_ladder[ladder_index]
        
        # Calculate expiration
        expires = now + (decay_days * 24 * 60 * 60)
        
        # Add new strike
        active_strikes.append({
            "ts": now,
            "expires": expires,
            "rule": rule,
            "value": value
        })
        
        strikes_data[str(user_id)] = active_strikes
        config["strikes"] = strikes_data
        await self.save_config(guild_id, config)
        
        return current_active + value
    
    async def check_message(self, message: discord.Message) -> Tuple[bool, List[str], int, str, bool]:
        """Check a message against automod rules (Accumulative)
        
        Returns:
            Tuple of (violation_found, rule_names, total_strikes, primary_action, needs_review)
        """
        # Skip if no guild
        if not message.guild:
            return False, [], 0, "delete", False
            
        # Get config
        config = await self.get_config(message.guild.id)
        
        # Skip if automod disabled
        if not config.get("enabled", False):
            return False, [], 0, "delete", False
            
        # Skip exempt users/channels
        if await self.is_exempt(message, config):
            return False, [], 0, "delete", False
            
        violations = []
        total_strikes = 0
        primary_action = "delete"
        needs_review = False
        
        # Check against each rule
        
        # 1. Anti-spam
        spam_config = config["modules"]["anti_spam"]
        if spam_config.get("enabled", False):
            if await self._check_spam(message, spam_config):
                violations.append("anti_spam")
                total_strikes += spam_config.get("strikes", 1)
                if spam_config.get("action") == "strike":
                    primary_action = "strike"
        
        # 2. Anti-mention spam
        mention_config = config["modules"]["anti_mention_spam"]
        if mention_config.get("enabled", False):
            if await self._check_mention_spam(message, mention_config):
                violations.append("anti_mention_spam")
                total_strikes += mention_config.get("strikes", 1)
                primary_action = "strike"
        
        # 3. Link filter
        link_config = config["modules"]["link_filter"]
        if link_config.get("enabled", False):
            if await self._check_links(message, link_config):
                violations.append("link_filter")
                total_strikes += link_config.get("strikes", 2)
                primary_action = "strike"
        
        # 4. Bad words filter (includes normalization/fuzzy detection as requested)
        words_config = config["modules"]["bad_words"]
        if words_config.get("enabled", False):
            found, review_needed = await self._check_bad_words(message, words_config)
            if found:
                violations.append("bad_words")
                total_strikes += words_config.get("strikes", 1)
                primary_action = "strike"
                if review_needed:
                    needs_review = True
                
        # 5. Anti-invite
        invite_config = config["modules"].get("anti_invite", {})
        if invite_config.get("enabled", False):
            if await self._check_invites(message, invite_config):
                violations.append("anti_invite")
                total_strikes += invite_config.get("strikes", 2)
                primary_action = "strike"
                
        # 6. Anti-caps
        caps_config = config["modules"].get("anti_caps", {})
        if caps_config.get("enabled", False):
            if await self._check_caps(message, caps_config):
                violations.append("anti_caps")
                total_strikes += caps_config.get("strikes", 1)
                if primary_action != "strike":
                    primary_action = "warn"
                
        # 7. Anti-Zalgo
        zalgo_config = config["modules"].get("anti_zalgo", {})
        if zalgo_config.get("enabled", False):
            if await self._check_zalgo(message, zalgo_config):
                violations.append("anti_zalgo")
                total_strikes += zalgo_config.get("strikes", 1)
                primary_action = "strike"
        
        if violations:
            return True, violations, total_strikes, primary_action, needs_review
            
        # No violations
        return False, [], 0, "delete", False
    
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
    
    async def _check_bad_words(self, message: discord.Message, config: Dict[str, Any]) -> Tuple[bool, bool]:
        """Check for bad words
        
        Returns:
            Tuple of (found, review_needed)
        """
        # Skip if empty message
        if not message.content:
            return False, False
            
        # Get word lists
        default_words = self.default_bad_words
        custom_words = config.get("custom_words", [])
        
        # Combine lists
        bad_words = set(custom_words)
        bad_words.update(config.get("words", []))
        
        # Also include global default words if configured to do so
        # or if no other words are defined
        if not bad_words or config.get("use_defaults", True):
            bad_words.update(default_words)
        
        # Normalize message content
        content = message.content.lower()
        normalized_content = self._normalize_content(message.content)
        
        # Check for bad words
        for word in bad_words:
            word_lower = word.lower()
            # Check for word boundaries in original content
            pattern = r'\b' + re.escape(word_lower) + r'\b'
            if re.search(pattern, content):
                return True, False # Exact match, no review needed
                
            # Check for fuzzy/normalized match (detects bypasses like a55)
            # Use original word without boundaries on normalized content for better detection
            if word_lower in normalized_content:
                return True, True # Fuzzy/Leet match, needs review
        
        return False, False
        
    async def _check_invites(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        if not message.content:
            return False
            
        invite_pattern = r'(discord\.gg/|discord\.com/invite/)[a-zA-Z0-9]+'
        invites = re.findall(invite_pattern, message.content, re.IGNORECASE)
        
        if not invites:
            return False
            
        whitelist = config.get("whitelist", [])
        
        for invite in invites:
            pass # simplified checking
            
        return len(invites) > 0
        
    async def _check_caps(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        content = message.content
        min_length = config.get("min_length", 15)
        
        if len(content) < min_length:
            return False
            
        caps_count = sum(1 for c in content if c.isupper())
        alpha_count = sum(1 for c in content if c.isalpha())
        
        if alpha_count == 0:
            return False
            
        percent = (caps_count / alpha_count) * 100
        return percent >= config.get("threshold_percent", 70)
        
    async def _check_zalgo(self, message: discord.Message, config: Dict[str, Any]) -> bool:
        if not message.content:
            return False
            
        zalgo_pattern = r'[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]{3,}'
        return bool(re.search(zalgo_pattern, message.content))
    
    async def take_action(self, message: discord.Message, rules: List[str], action: str, total_strikes: int, needs_review: bool = False) -> Optional[discord.Embed]:
        """Take action against a user for violation(s) handling strike mechanics"""
        try:
            guild = message.guild
            user = message.author
            config = await self.get_config(guild.id)
            
            # Always try to delete the message first
            try:
                await message.delete()
            except (discord.errors.NotFound, discord.errors.Forbidden):
                pass
                
            rules_str = ", ".join([r.replace('_', ' ').title() for r in rules])
            
            if needs_review:
                # Create review embed for the Cog to send with buttons
                embed = discord.Embed(
                    title="🔍 AutoMod: Review Requested",
                    description=f"Suspicious activity detected in {message.channel.mention}",
                    color=discord.Color.yellow(),
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
                embed.add_field(name="Suspected Rules", value=rules_str, inline=True)
                embed.add_field(name="Potential Strikes", value=f"+{total_strikes}", inline=True)
                
                content = message.content[:1020] + "..." if len(message.content) > 1024 else message.content
                embed.add_field(name="Message Content", value=content, inline=False)
                
                return embed
            
            # Process strikes and determine real action
            duration_minutes = 0
            current_strikes = 0
            
            if action == "strike":
                current_strikes = await self.add_strike(guild.id, user.id, rules_str, total_strikes, config)
                system_config = config.get("strike_system", {})
                thresholds = system_config.get("thresholds", {})
                
                # Look up the highest threshold we passed
                real_action = "delete"
                for t in sorted([int(k) for k in thresholds.keys()]):
                    if current_strikes >= t:
                        real_action = thresholds[str(t)]
                
                # Map threshold strings to actions/durations
                if real_action == "warn":
                    action = "warn"
                elif real_action.startswith("timeout"):
                    action = "timeout"
                    if real_action == "timeout_10m":
                        duration_minutes = 10
                    elif real_action == "timeout_1h":
                        duration_minutes = 60
                    elif real_action == "timeout_12h":
                        duration_minutes = 720
                    elif real_action == "timeout_24h":
                        duration_minutes = 1440
                elif real_action == "kick":
                    action = "kick"
                elif real_action == "ban":
                    action = "ban"
                else:
                    action = real_action
                    
            try:
                action_name = action.title()
                if action == "timeout":
                    action_name = "Timed Out"
                
                dm_embed = discord.Embed(
                    title=f"⚠️ AutoMod Alert: {action_name}",
                    description=f"Action taken in {guild.name}",
                    color=discord.Color.red()
                )
                
                dm_embed.add_field(name="Reason", value=f"Violation: {rules_str}", inline=False)
                
                if current_strikes > 0:
                    dm_embed.add_field(name="Active Strikes", value=f"{current_strikes}", inline=True)
                
                if duration_minutes > 0 and action == "timeout":
                    dm_embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
                
                await user.send(embed=dm_embed)
            except Exception:
                pass
            
            # Execute physical action
            if action == "timeout" and duration_minutes > 0:
                await user.timeout(datetime.timedelta(minutes=duration_minutes), reason=f"AutoMod: {rules_str} ({current_strikes} strikes)")
            elif action == "kick":
                await guild.kick(user, reason=f"AutoMod: {rules_str} ({current_strikes} strikes)")
            elif action == "ban":
                await guild.ban(user, reason=f"AutoMod: {rules_str} ({current_strikes} strikes)")
            
            await self._log_action(message, rules_str, action, duration_minutes, strikes=current_strikes, added_strikes=total_strikes)
            return None
            
        except Exception as e:
            self.logger.error(f"Error taking automod action: {str(e)}")
            return None
            
    async def _log_action(self, message: discord.Message, rule: str, action: str, duration: int, strikes: int = 0, added_strikes: int = 0) -> None:
        try:
            guild = message.guild
            config = await self.get_config(guild.id)
            
            log_channel_id = config.get("log_channel_id")
            if not log_channel_id:
                return
                
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                return
            
            embed = discord.Embed(
                title=f"🛡️ AutoMod: {action.title()}",
                description=f"AutoMod has taken action in {message.channel.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
            embed.add_field(name="Rule Violation", value=rule.replace('_', ' ').title(), inline=True)
            
            if added_strikes > 0:
                embed.add_field(name="Strikes", value=f"+{added_strikes} (Total: {strikes})", inline=True)
            
            if duration > 0 and action == "timeout":
                embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
            
            content = message.content[:1020] + "..." if len(message.content) > 1024 else message.content
            embed.add_field(name="Message Content", value=content, inline=False)
            
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
            action = module_config.get("action", "strike").title()
            
            # Format duration/strikes if present
            duration = module_config.get("duration_minutes", 0)
            strikes = module_config.get("strikes", 1)
            
            action_text = f"{action}"
            if action.lower() == "strike":
                action_text += f" (+{strikes})"
            elif duration > 0 and action.lower() == "timeout":
                action_text += f" ({duration} min)"
                
            embed.add_field(
                name=f"{module_name.replace('_', ' ').title()}",
                value=f"{'✅' if module_enabled else '❌'} {action_text}",
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