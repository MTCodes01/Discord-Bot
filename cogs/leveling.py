import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import json
import typing
from typing import Dict, List, Optional, Union, Any
from util.leveling_utils import LevelingSystem
import traceback
from utils import command_help


class Leveling(commands.Cog):
    """User XP and leveling system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.leveling = LevelingSystem(bot)
        
        # Task for voice XP updates
        self.voice_xp_task = None
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        if self.voice_xp_task:
            self.voice_xp_task.cancel()
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize leveling system when bot is ready"""
        self.logger.info("Leveling system initialized")
        
        # Start voice XP task
        if not self.voice_xp_task:
            self.voice_xp_task = self.bot.loop.create_task(self.update_voice_xp())
    
    async def update_voice_xp(self):
        """Background task to periodically update voice XP"""
        try:
            await self.bot.wait_until_ready()
            
            while not self.bot.is_closed():
                # Process all active voice connections
                for guild in self.bot.guilds:
                    for member in guild.members:
                        if member.voice and member.voice.channel:
                            # Update voice tracking
                            await self.leveling.update_voice_tracking(member, member.voice)
                
                # Wait before next update (60 seconds by default)
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            # Task was cancelled, exit cleanly
            pass
        except Exception as e:
            self.logger.error(f"Error in voice XP task: {str(e)}\n{traceback.format_exc()}")
            
            # Restart task after a delay
            await asyncio.sleep(60)
            self.voice_xp_task = self.bot.loop.create_task(self.update_voice_xp())
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages"""
        # Skip if bot is not ready
        if not self.bot.is_ready():
            return
            
        try:
            # Process message XP
            success, old_level, new_level, leveled_up = await self.leveling.reward_xp_for_message(message)
            
            # Send level up message if leveled up
            if success and leveled_up:
                await self._send_level_up_message(message, old_level, new_level)
                
                # Process level rewards
                await self.leveling.process_level_rewards(message.author, new_level)
                
        except Exception as e:
            self.logger.error(f"Error processing message XP: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Track voice activity"""
        # Skip if bot is not ready
        if not self.bot.is_ready():
            return
            
        try:
            # User joined a voice channel
            if before.channel is None and after.channel is not None:
                await self.leveling.start_voice_tracking(member, after)
                
            # User left a voice channel
            elif before.channel is not None and after.channel is None:
                await self.leveling.end_voice_tracking(member, before)
                
            # User moved between voice channels
            elif before.channel != after.channel:
                # End tracking in old channel
                await self.leveling.end_voice_tracking(member, before)
                
                # Start tracking in new channel
                await self.leveling.start_voice_tracking(member, after)
                
            # User's voice state changed (mute, deafen, etc.)
            elif before.self_mute != after.self_mute or before.self_deaf != after.self_deaf or before.afk != after.afk:
                await self.leveling.update_voice_tracking(member, after)
                
        except Exception as e:
            self.logger.error(f"Error processing voice state: {str(e)}\n{traceback.format_exc()}")
    
    async def _send_level_up_message(self, message, old_level, new_level):
        """Send level up notification"""
        try:
            # Get config
            config = await self.leveling.get_config(message.guild.id)
            
            # Skip if level up messages disabled
            if not config["settings"].get("level_up_messages", True):
                return
                
            # Create embed
            embed = discord.Embed(
                title=f"🎉 Level Up!",
                description=f"{message.author.mention} has reached level **{new_level}**!",
                color=discord.Color.green()
            )
            
            embed.set_thumbnail(url=message.author.display_avatar.url)
            
            # Determine where to send
            if config["settings"].get("level_up_dm", False):
                # Send DM to user
                try:
                    await message.author.send(embed=embed)
                    return
                except:
                    # Failed to send DM, fall back to channel
                    pass
            
            # Check for specific channel
            level_up_channel_id = config["settings"].get("level_up_channel")
            
            if level_up_channel_id:
                channel = message.guild.get_channel(level_up_channel_id)
                
                if channel:
                    await channel.send(embed=embed)
                    return
            
            # Otherwise, send in the original channel
            await message.channel.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error sending level up message: {str(e)}\n{traceback.format_exc()}")
    
    # === Rank Commands ===
    
    @command_help("leveling", "View your rank and level information", "rank [member]")
    @commands.hybrid_command(name="rank", description="View your rank and level")
    @commands.guild_only()
    async def rank(self, ctx, member: Optional[discord.Member] = None):
        """Show rank/level card for a user"""
        await ctx.defer()
        
        # Use author if no member provided
        if not member:
            member = ctx.author
        
        try:
            # Generate rank card
            rank_card = await self.leveling.generate_rank_card(member)
            
            if rank_card:
                # Send rank card image
                await ctx.send(file=rank_card)
            else:
                # Get user data
                user_data = await self.leveling.get_user_xp(member.id, ctx.guild.id)
                user_rank = await self.leveling.get_user_rank(member.id, ctx.guild.id)
                
                if not user_data:
                    await ctx.send(f"{member.display_name} has not earned any XP yet.")
                    return
                
                # Create embed
                embed = discord.Embed(
                    title=f"{member.display_name}'s Level Stats",
                    color=discord.Color.blue()
                )
                
                embed.set_thumbnail(url=member.display_avatar.url)
                
                # Add level and rank
                embed.add_field(name="Level", value=str(user_data["level"]), inline=True)
                embed.add_field(name="Rank", value=f"#{user_rank}", inline=True)
                
                # Add XP
                embed.add_field(
                    name="Level Progress", 
                    value=f"{user_data['current_level_xp']} / {user_data['xp_needed']} XP ({user_data['progress']:.1f}%)", 
                    inline=False
                )
                
                # Add XP breakdown
                embed.add_field(name="Text XP", value=str(user_data["text_xp"]), inline=True)
                embed.add_field(name="Voice XP", value=str(user_data["voice_xp"]), inline=True)
                embed.add_field(name="Total XP", value=str(user_data["total_xp"]), inline=True)
                
                # Add activity stats
                embed.add_field(name="Messages", value=str(user_data["total_messages"]), inline=True)
                embed.add_field(name="Voice Time", value=f"{user_data['total_voice_minutes']:.1f} min", inline=True)
                
                await ctx.send(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error showing rank: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to show rank information.")
    
    @command_help("leveling", "View the server XP leaderboard", "leaderboard [page] [afk]")
    @commands.hybrid_command(name="leaderboard", aliases=["lb"], description="View the server leaderboard")
    @app_commands.describe(
        page="Page number to view (default: 1)",
        afk="Show the inactive VC time leaderboard instead of XP"
    )
    @commands.guild_only()
    async def leaderboard(self, ctx, page: int = 1, afk: bool = False):
        """Show server leaderboard"""
        await ctx.defer()
        
        try:
            # Validate page number
            if page < 1:
                page = 1
                
            # Items per page
            per_page = 10
            
            # Calculate offset
            offset = (page - 1) * per_page
            
            # Determine leaderboard mode
            show_afk = afk is True

            # Get leaderboard data
            leaderboard_data = await self.leveling.get_leaderboard(ctx.guild.id, per_page, offset, afk=show_afk)
            
            if not leaderboard_data or not leaderboard_data["leaderboard"]:
                await ctx.send("No XP data found for this server.")
                return
                
            # Total pages
            total_users = leaderboard_data["total_users"]
            total_pages = (total_users + per_page - 1) // per_page
            
            # Create embed
            if show_afk:
                embed_title = f"😴 {ctx.guild.name} Inactive VC Leaderboard"
                embed_description = f"Top {per_page} users by AFK/inactive time in VC - Page {page}/{total_pages}"
            else:
                embed_title = f"🏆 {ctx.guild.name} Leaderboard"
                embed_description = f"Top {per_page} users by XP - Page {page}/{total_pages}"

            embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=discord.Color.blurple() if show_afk else discord.Color.gold()
            )
            
            # Add server icon
            if ctx.guild.icon:
                embed.set_thumbnail(url=ctx.guild.icon.url)
            
            # Format leaderboard entries
            leaderboard_text = ""
            
            for i, entry in enumerate(leaderboard_data["leaderboard"], start=1):
                # Get username
                user = self.bot.get_user(entry["user_id"])
                
                if user:
                    username = user.name
                else:
                    # Try to get member from guild
                    member = ctx.guild.get_member(entry["user_id"])
                    
                    if member:
                        username = member.display_name
                    else:
                        username = f"User {entry['user_id']}"
                
                # Format rank emojis for top 3
                rank = entry["rank"]
                if rank == 1:
                    rank_emoji = "🥇"
                elif rank == 2:
                    rank_emoji = "🥈"
                elif rank == 3:
                    rank_emoji = "🥉"
                else:
                    rank_emoji = f"#{rank}"
                
                # Create entry
                if show_afk:
                    afk_duration = self._format_duration(entry.get("afk_time", 0))
                    leaderboard_text += f"{rank_emoji} **{username}** - {afk_duration} inactive (Level {entry['level']})\n"
                else:
                    leaderboard_text += f"{rank_emoji} **{username}** - Level {entry['level']} ({entry['total_xp']} XP)\n"
            
            # Add leaderboard entries as a field instead of setting description
            # This prevents the 1024 character limit error in embeds
            embed.add_field(name="Rankings", value=leaderboard_text, inline=False)
            
            # Add page navigation guide
            if total_pages > 1:
                if show_afk:
                    embed.set_footer(text=f"Use /leaderboard [page] afk:True to view other pages • {total_users} total users")
                else:
                    embed.set_footer(text=f"Use /leaderboard [page] to view other pages • {total_users} total users • Use afk:True to view the inactive VC leaderboard")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error showing leaderboard: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to show the leaderboard.")
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format a duration in seconds to a human-readable string (e.g. 1h 23m 45s)"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        return " ".join(parts)
    
    # === Admin Commands ===
    
    @command_help("leveling"), "Configure the leveling system", "levelconfig")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_group(name="levelconfig", fallback="show", description="Configure the leveling system")
    async def levelconfig(self, ctx):
        """Show leveling system configuration"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Create embed
            embed = discord.Embed(
                title="⚙️ Leveling System Configuration",
                color=discord.Color.blue()
            )
            
            # XP settings
            text_xp = config["text_xp"]
            voice_xp = config["voice_xp"]
            
            embed.add_field(
                name="Text XP",
                value=f"Min: {text_xp['min']}\nMax: {text_xp['max']}\nCooldown: {text_xp['cooldown_seconds']}s",
                inline=True
            )
            
            embed.add_field(
                name="Voice XP",
                value=f"Per Minute: {voice_xp['per_minute']}\nAFK: {voice_xp['afk_multiplier']}x\nSolo: {voice_xp['solo_multiplier']}x",
                inline=True
            )
            
            # Level curve
            curve = config["level_curve"]
            embed.add_field(
                name="Level Curve",
                value=f"Base: {curve['base']}\nExponent: {curve['exponent']}",
                inline=True
            )
            
            # Notification settings
            settings = config["settings"]
            notification_status = []
            
            notification_status.append(f"Level Up Messages: {'✅' if settings.get('level_up_messages', True) else '❌'}")
            
            level_up_channel_id = settings.get("level_up_channel")
            if level_up_channel_id:
                channel = ctx.guild.get_channel(level_up_channel_id)
                notification_status.append(f"Level Up Channel: {channel.mention if channel else 'Invalid Channel'}")
            else:
                notification_status.append("Level Up Channel: Same as message")
                
            notification_status.append(f"DM on Level Up: {'✅' if settings.get('level_up_dm', False) else '❌'}")
            
            embed.add_field(
                name="Notifications",
                value="\n".join(notification_status),
                inline=False
            )
            
            # Role rewards
            rewards = config["rewards"]
            rewards_enabled = rewards.get("enabled", False)
            
            reward_text = [f"Enabled: {'✅' if rewards_enabled else '❌'}"]
            
            if rewards_enabled and rewards.get("roles"):
                reward_text.append("Role Rewards:")
                
                for level, role_id in rewards.get("roles", {}).items():
                    role = ctx.guild.get_role(int(role_id))
                    reward_text.append(f"Level {level}: {role.mention if role else 'Invalid Role'}")
            
            if len(reward_text) == 1:
                reward_text.append("No role rewards configured")
                
            embed.add_field(
                name="Rewards",
                value="\n".join(reward_text),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error showing level config: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to show the configuration.")
    
    @command_help("leveling"), "Enable or disable level rewards", "levelconfig rewards <enabled>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="rewards", description="Enable or disable level rewards")
    async def rewards(self, ctx, enabled: bool):
        """Configure level rewards"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update setting
            config["rewards"]["enabled"] = enabled
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                status = "enabled" if enabled else "disabled"
                await ctx.send(f"✅ Level rewards have been {status}.")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring rewards: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Add a role reward for a specific level", "levelconfig addrole <level> <role>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="addrole", description="Add a role reward for a level")
    async def addrole(self, ctx, level: int, role: discord.Role):
        """Add role reward for a level"""
        await ctx.defer()
        
        try:
            # Validate level
            if level < 1:
                await ctx.send("❌ Level must be at least 1.")
                return
                
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update role rewards
            if "roles" not in config["rewards"]:
                config["rewards"]["roles"] = {}
                
            # Add role
            config["rewards"]["roles"][str(level)] = role.id
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Role {role.mention} will now be awarded at level {level}.")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error adding role reward: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to add the role reward.")
    
    @command_help("leveling"), "Remove a role reward from a level", "levelconfig removerole <level>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="removerole", description="Remove a role reward for a level")
    async def removerole(self, ctx, level: int):
        """Remove role reward for a level"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Check if level has a role
            if "roles" not in config["rewards"] or str(level) not in config["rewards"]["roles"]:
                await ctx.send(f"❌ No role reward found for level {level}.")
                return
                
            # Get role before removing
            role_id = config["rewards"]["roles"][str(level)]
            role = ctx.guild.get_role(int(role_id))
            role_name = role.name if role else f"Unknown Role ({role_id})"
                
            # Remove role
            del config["rewards"]["roles"][str(level)]
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Removed role reward for level {level} ({role_name}).")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error removing role reward: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to remove the role reward.")
    
    @command_help("leveling"), "Configure whether level roles stack or replace previous ones", "levelconfig stackroles <stack>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="stackroles", description="Configure whether level roles stack or replace previous ones")
    async def stackroles(self, ctx, stack: bool):
        """Configure role stacking"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update setting
            config["settings"]["stack_roles"] = stack
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                if stack:
                    await ctx.send("✅ Level roles will now stack (users keep previous level roles).")
                else:
                    await ctx.send("✅ Level roles will now replace previous level roles.")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring role stacking: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Enable or disable level up messages", "levelconfig messages <enabled>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="messages", description="Enable or disable level up messages")
    async def messages(self, ctx, enabled: bool):
        """Configure level up messages"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update setting
            config["settings"]["level_up_messages"] = enabled
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                status = "enabled" if enabled else "disabled"
                await ctx.send(f"✅ Level up messages have been {status}.")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring level up messages: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Set a channel for level up messages", "levelconfig messagechannel [channel]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="messagechannel", description="Set a channel for level up messages")
    async def messagechannel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Set channel for level up messages"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            if channel:
                # Check permissions
                permissions = channel.permissions_for(ctx.guild.me)
                if not permissions.send_messages or not permissions.embed_links:
                    await ctx.send(f"❌ I don't have permission to send messages and embeds in {channel.mention}.")
                    return
                    
                # Update setting
                config["settings"]["level_up_channel"] = channel.id
                
                # Save config
                success = await self.leveling.save_config(ctx.guild.id, config)
                
                if success:
                    await ctx.send(f"✅ Level up messages will now be sent in {channel.mention}.")
                else:
                    await ctx.send("❌ Failed to update configuration.")
            else:
                # Clear channel setting
                config["settings"]["level_up_channel"] = None
                
                # Save config
                success = await self.leveling.save_config(ctx.guild.id, config)
                
                if success:
                    await ctx.send("✅ Level up messages will now be sent in the same channel as the message.")
                else:
                    await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error setting message channel: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Enable or disable sending level up messages via DM", "levelconfig dm <enabled>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="dm", description="Enable or disable sending level up messages via DM")
    async def levelconfig_dm(self, ctx, enabled: bool):
        """Configure DM level up messages"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update setting
            config["settings"]["level_up_dm"] = enabled
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                status = "enabled" if enabled else "disabled"
                await ctx.send(f"✅ Level up DMs have been {status}.")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring level up DMs: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")

    @command_help("leveling"), "Configure text XP settings", "levelconfig textxp [min_xp] [max_xp] [cooldown]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="textxp", description="Configure text XP settings")
    async def textxp(self, ctx, min_xp: Optional[int] = None, max_xp: Optional[int] = None, cooldown: Optional[int] = None):
        """Configure text XP settings"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update min XP
            if min_xp is not None:
                if min_xp < 0:
                    await ctx.send("❌ Minimum XP cannot be negative.")
                    return
                    
                config["text_xp"]["min"] = min_xp
            
            # Update max XP
            if max_xp is not None:
                if max_xp < 0:
                    await ctx.send("❌ Maximum XP cannot be negative.")
                    return
                    
                if min_xp is not None and max_xp < min_xp:
                    await ctx.send("❌ Maximum XP cannot be less than minimum XP.")
                    return
                    
                config["text_xp"]["max"] = max_xp
            
            # Update cooldown
            if cooldown is not None:
                if cooldown < 0:
                    await ctx.send("❌ Cooldown cannot be negative.")
                    return
                    
                config["text_xp"]["cooldown_seconds"] = cooldown
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                text_xp = config["text_xp"]
                await ctx.send(f"✅ Text XP settings updated:\nMin: {text_xp['min']}\nMax: {text_xp['max']}\nCooldown: {text_xp['cooldown_seconds']}s")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring text XP: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Configure voice XP settings", "levelconfig voicexp [per_minute] [afk_multiplier] [solo_multiplier]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="voicexp", description="Configure voice XP settings")
    async def voicexp(self, ctx, per_minute: Optional[int] = None, afk_multiplier: Optional[float] = None, 
                   solo_multiplier: Optional[float] = None):
        """Configure voice XP settings"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update per minute
            if per_minute is not None:
                if per_minute < 0:
                    await ctx.send("❌ XP per minute cannot be negative.")
                    return
                    
                config["voice_xp"]["per_minute"] = per_minute
            
            # Update AFK multiplier
            if afk_multiplier is not None:
                if afk_multiplier < 0:
                    await ctx.send("❌ AFK multiplier cannot be negative.")
                    return
                    
                config["voice_xp"]["afk_multiplier"] = afk_multiplier
            
            # Update solo multiplier
            if solo_multiplier is not None:
                if solo_multiplier < 0:
                    await ctx.send("❌ Solo multiplier cannot be negative.")
                    return
                    
                config["voice_xp"]["solo_multiplier"] = solo_multiplier
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                voice_xp = config["voice_xp"]
                await ctx.send(f"✅ Voice XP settings updated:\nPer Minute: {voice_xp['per_minute']}\nAFK Multiplier: {voice_xp['afk_multiplier']}x\nSolo Multiplier: {voice_xp['solo_multiplier']}x")
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring voice XP: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Configure level curve settings", "levelconfig curve [base] [exponent]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="curve", description="Configure level curve settings")
    async def curve(self, ctx, base: Optional[int] = None, exponent: Optional[float] = None):
        """Configure level curve settings"""
        await ctx.defer()
        
        try:
            # Get config
            config = await self.leveling.get_config(ctx.guild.id)
            
            # Update base
            if base is not None:
                if base <= 0:
                    await ctx.send("❌ Base must be greater than 0.")
                    return
                    
                config["level_curve"]["base"] = base
            
            # Update exponent
            if exponent is not None:
                if exponent <= 0:
                    await ctx.send("❌ Exponent must be greater than 0.")
                    return
                    
                config["level_curve"]["exponent"] = exponent
            
            # Save config
            success = await self.leveling.save_config(ctx.guild.id, config)
            
            if success:
                curve = config["level_curve"]
                
                # Show level examples
                level_5 = base * (5 ** exponent) if base is not None and exponent is not None else \
                          curve["base"] * (5 ** curve["exponent"])
                level_10 = base * (10 ** exponent) if base is not None and exponent is not None else \
                           curve["base"] * (10 ** curve["exponent"])
                level_20 = base * (20 ** exponent) if base is not None and exponent is not None else \
                           curve["base"] * (20 ** curve["exponent"])
                
                await ctx.send(
                    f"✅ Level curve settings updated:\nBase: {curve['base']}\nExponent: {curve['exponent']}\n\n"
                    f"Example XP requirements:\nLevel 5: {level_5:.0f} XP\nLevel 10: {level_10:.0f} XP\nLevel 20: {level_20:.0f} XP"
                )
            else:
                await ctx.send("❌ Failed to update configuration.")
                
        except Exception as e:
            self.logger.error(f"Error configuring level curve: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to update the configuration.")
    
    @command_help("leveling"), "Reset a user's XP to 0", "levelconfig resetuser <member>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @levelconfig.command(name="resetuser", description="Reset a user's XP to 0")
    async def resetuser(self, ctx, member: discord.Member):
        """Reset XP for a user"""
        await ctx.defer()
        
        try:
            # Confirm reset
            confirm_msg = await ctx.send(f"⚠️ Are you sure you want to reset all XP for {member.mention}? This cannot be undone.")
            
            # Add reaction confirmation
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
            
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                
                if str(reaction.emoji) == "✅":
                    # Reset user XP
                    success = await self.leveling.reset_user_xp(member.id, ctx.guild.id)
                    
                    if success:
                        await ctx.send(f"✅ XP for {member.mention} has been reset to 0.")
                    else:
                        await ctx.send("❌ Failed to reset user XP.")
                else:
                    await ctx.send("Reset canceled.")
                    
            except asyncio.TimeoutError:
                await ctx.send("Reset canceled (timed out).")
                
        except Exception as e:
            self.logger.error(f"Error resetting user XP: {str(e)}\n{traceback.format_exc()}")
            await ctx.send("❌ An error occurred while trying to reset the user's XP.")


async def setup(bot):
    await bot.add_cog(Leveling(bot))