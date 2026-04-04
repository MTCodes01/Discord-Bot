import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import json
import typing
from typing import Dict, List, Optional, Union, Any
from util.automod_utils import AutoModerationSystem, AutoModEmbed
import traceback
from utils import command_help


class AutoModReviewView(discord.ui.View):
    """View with buttons for moderator review of suspected violations"""
    def __init__(self, automod_system, message, rules, strikes):
        super().__init__(timeout=None)
        self.automod = automod_system
        self.message = message
        self.rules = rules
        self.strikes = strikes

    @discord.ui.button(label="✅ Confirm & Strike", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Add the strikes manually
        rules_str = ", ".join([r.replace('_', ' ').title() for r in self.rules])
        config = await self.automod.get_config(interaction.guild.id)
        
        # We call take_action with needs_review=False to actually execute it
        await self.automod.take_action(self.message, self.rules, "strike", self.strikes, needs_review=False)
        
        # Update the original message to show it was handled
        embed = interaction.message.embeds[0]
        embed.title = "🛡️ AutoMod: Violation Confirmed"
        embed.color = discord.Color.green()
        embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
            
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="⚠️ Warn Only", style=discord.ButtonStyle.secondary)
    async def warn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Just send a warning action
        await self.automod.take_action(self.message, self.rules, "warn", 0, needs_review=False)
        
        embed = interaction.message.embeds[0]
        embed.title = "⚖️ AutoMod: User Warned (No Strike)"
        embed.color = discord.Color.gold()
        embed.add_field(name="Handled By", value=interaction.user.mention, inline=False)
        
        for child in self.children:
            child.disabled = True
            
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="❌ False Positive", style=discord.ButtonStyle.danger)
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = interaction.message.embeds[0]
        embed.title = "✅ AutoMod: Dismissed"
        embed.color = discord.Color.light_grey()
        embed.add_field(name="Dismissed By", value=interaction.user.mention, inline=False)
        
        for child in self.children:
            child.disabled = True
            
        await interaction.edit_original_response(embed=embed, view=self)


class AutoMod(commands.Cog):
    """Automated server moderation system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.automod = AutoModerationSystem(bot)
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize automod system when bot is ready"""
        self.logger.info("AutoMod system initialized")
        
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check all messages against automod rules"""
        # Skip if message is a command
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return
        
        # Process message through automod
        try:
            violation, rules, strikes, action, needs_review = await self.automod.check_message(message)
            
            if violation:
                review_embed = await self.automod.take_action(message, rules, action, strikes, needs_review)
                
                if needs_review and review_embed:
                    # Send the review request to the log channel
                    config = await self.automod.get_config(message.guild.id)
                    log_channel_id = config.get("log_channel_id")
                    if log_channel_id:
                        log_channel = message.guild.get_channel(log_channel_id)
                        if log_channel:
                            view = AutoModReviewView(self.automod, message, rules, strikes)
                            await log_channel.send(embed=review_embed, view=view)
                
        except Exception as e:
            self.logger.error(f"AutoMod error: {str(e)}\n{traceback.format_exc()}")
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Check edited messages against automod rules"""
        # Skip if content didn't change
        if before.content == after.content:
            return
            
        # Process the edited message
        try:
            violation, rules, strikes, action, needs_review = await self.automod.check_message(after)
            
            if violation:
                review_embed = await self.automod.take_action(after, rules, action, strikes, needs_review)
                
                if needs_review and review_embed:
                    config = await self.automod.get_config(after.guild.id)
                    log_channel_id = config.get("log_channel_id")
                    if log_channel_id:
                        log_channel = after.guild.get_channel(log_channel_id)
                        if log_channel:
                            view = AutoModReviewView(self.automod, after, rules, strikes)
                            await log_channel.send(embed=review_embed, view=view)
                
        except Exception as e:
            self.logger.error(f"AutoMod error on edit: {str(e)}\n{traceback.format_exc()}")
    
    # === AutoMod Configuration Commands ===
    
    @command_help(
        category="mod",
        description="View AutoMod status and configuration",
        usage="automod",
        examples=["automod"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_group(name="automod", fallback="status")
    async def automod_group(self, ctx):
        """View AutoMod status and configuration"""
        await self.show_status(ctx)
    
    async def show_status(self, ctx):
        """Show current automod status"""
        await ctx.defer()
        
        config = await self.automod.get_config(ctx.guild.id)
        embed = AutoModEmbed.status(ctx.guild, config)
        
        await ctx.send(embed=embed)
    
    @command_help(
        category="mod",
        description="Enable the AutoMod system for this server",
        usage="automod enable"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="enable", description="Enable the AutoMod system")
    async def automod_enable(self, ctx):
        """Enable automod for this server"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Skip if already enabled
        if config.get("enabled", False):
            await ctx.send("⚠️ AutoMod is already enabled!")
            return
        
        # Enable automod
        config["enabled"] = True
        
        # Save config
        success = await self.automod.save_config(ctx.guild.id, config)
        
        if success:
            embed = AutoModEmbed.status(ctx.guild, config)
            await ctx.send("✅ AutoMod has been enabled!", embed=embed)
        else:
            await ctx.send("❌ Failed to enable AutoMod.")
    
    @command_help(
        category="mod",
        description="Disable the AutoMod system for this server",
        usage="automod disable"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="disable", description="Disable the AutoMod system")
    async def automod_disable(self, ctx):
        """Disable automod for this server"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Skip if already disabled
        if not config.get("enabled", False):
            await ctx.send("⚠️ AutoMod is already disabled!")
            return
        
        # Disable automod
        config["enabled"] = False
        
        # Save config
        success = await self.automod.save_config(ctx.guild.id, config)
        
        if success:
            embed = AutoModEmbed.status(ctx.guild, config)
            await ctx.send("✅ AutoMod has been disabled!", embed=embed)
        else:
            await ctx.send("❌ Failed to disable AutoMod.")
    
    @command_help(
        category="mod",
        description="Set the log channel for AutoMod",
        usage="automod log_channel [channel]",
        examples=["automod log_channel #automod-logs", "automod log_channel"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="log_channel", description="Set the log channel for AutoMod")
    async def set_log_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the log channel for automod"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        if channel:
            # Check if bot has permissions to send messages
            permissions = channel.permissions_for(ctx.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await ctx.send(f"❌ I don't have permission to send messages and embeds in {channel.mention}!")
                return
            
            # Update config
            config["log_channel_id"] = channel.id
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                embed = AutoModEmbed.status(ctx.guild, config)
                await ctx.send(f"✅ Log channel set to {channel.mention}!", embed=embed)
            else:
                await ctx.send("❌ Failed to set log channel.")
        else:
            # If no channel provided, clear the log channel
            config["log_channel_id"] = None
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                embed = AutoModEmbed.status(ctx.guild, config)
                await ctx.send("✅ Log channel has been cleared.", embed=embed)
            else:
                await ctx.send("❌ Failed to clear log channel.")
    
    @command_help(
        category="mod",
        description="Configure an AutoMod module",
        usage="automod module <module> [enabled] [action] [duration]",
        examples=["automod module spam true strike 1", "automod module words false", "automod module link true delete"],
        note="Modules: spam, mention, link, words, invite, caps, zalgo | Actions: strike, delete, warn, timeout, kick"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="module", description="Configure an AutoMod module")
    async def configure_module(self, ctx, 
                              module: str, 
                              enabled: bool = None, 
                              action: str = None, 
                              duration: int = None):
        """Configure an automod module
        
        Parameters:
            module: The module to configure (spam, mention, link, words)
            enabled: Whether to enable or disable the module
            action: The action to take (strike, delete, warn, timeout, kick)
            duration: The duration in minutes for timeouts, or the number of strikes for action 'strike'
        """
        await ctx.defer()
        
        # Map short module names to full names
        module_mapping = {
            "spam": "anti_spam",
            "mention": "anti_mention_spam",
            "link": "link_filter",
            "words": "bad_words",
            "invite": "anti_invite",
            "caps": "anti_caps",
            "zalgo": "anti_zalgo"
        }
        
        # Get the full module name
        module_name = module_mapping.get(module.lower(), module.lower())
        
        # Valid actions
        valid_actions = ["strike", "delete", "warn", "timeout", "kick"]
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Check if module exists
        if module_name not in config["modules"]:
            await ctx.send(f"❌ Invalid module name. Valid modules: {', '.join(module_mapping.values())}")
            return
            
        # Create reference to the module config
        module_config = config["modules"][module_name]
        
        # Update enabled status if provided
        if enabled is not None:
            module_config["enabled"] = enabled
            
        # Update action if provided and valid
        if action is not None:
            if action.lower() not in valid_actions:
                await ctx.send(f"❌ Invalid action. Valid actions: {', '.join(valid_actions)}")
                return
                
            module_config["action"] = action.lower()
            
        if duration is not None:
            if duration < 0:
                await ctx.send("❌ Value cannot be negative.")
                return
                
            if action and action.lower() == "strike":
                module_config["strikes"] = duration
            else:
                module_config["duration_minutes"] = duration
            
        # Save config
        success = await self.automod.save_config(ctx.guild.id, config)
        
        if success:
            # Show updated status
            embed = AutoModEmbed.status(ctx.guild, config)
            
            response = f"✅ Module '{module_name}' updated:"
            
            if enabled is not None:
                response += f"\n- {'Enabled' if enabled else 'Disabled'}"
                
            if action is not None:
                response += f"\n- Action set to '{action}'"
                
            if duration is not None:
                if action and action.lower() == "strike":
                    response += f"\n- Strikes set to {duration}"
                else:
                    response += f"\n- Duration set to {duration} minutes"
                
            await ctx.send(response, embed=embed)
        else:
            await ctx.send("❌ Failed to update module configuration.")
    
    @command_help(
        category="mod",
        description="Add or remove a role exempt from AutoMod",
        usage="automod exempt_role <role> [remove]",
        examples=["automod exempt_role @Moderators", "automod exempt_role @Moderators true"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="exempt_role", description="Add or remove an exempt role")
    async def exempt_role(self, ctx, role: discord.Role, remove: bool = False):
        """Add or remove a role exempt from automod"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get exempt roles list
        exempt_roles = config.get("exempt_roles", [])
        
        if remove:
            # Remove role if it exists
            if role.id in exempt_roles:
                exempt_roles.remove(role.id)
                message = f"✅ {role.mention} is no longer exempt from AutoMod."
            else:
                await ctx.send(f"⚠️ {role.mention} is not in the exempt list.")
                return
        else:
            # Add role if it doesn't exist
            if role.id not in exempt_roles:
                exempt_roles.append(role.id)
                message = f"✅ {role.mention} is now exempt from AutoMod."
            else:
                await ctx.send(f"⚠️ {role.mention} is already exempt.")
                return
        
        # Update config
        config["exempt_roles"] = exempt_roles
        
        # Save config
        success = await self.automod.save_config(ctx.guild.id, config)
        
        if success:
            embed = AutoModEmbed.status(ctx.guild, config)
            await ctx.send(message, embed=embed)
        else:
            await ctx.send("❌ Failed to update exempt roles.")
    
    @command_help(
        category="mod",
        description="Add or remove a channel exempt from AutoMod",
        usage="automod exempt_channel <channel> [remove]",
        examples=["automod exempt_channel #bot-commands", "automod exempt_channel #bot-commands true"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="exempt_channel", description="Add or remove an exempt channel")
    async def exempt_channel(self, ctx, channel: discord.TextChannel, remove: bool = False):
        """Add or remove a channel exempt from automod"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get exempt channels list
        exempt_channels = config.get("exempt_channels", [])
        
        if remove:
            # Remove channel if it exists
            if channel.id in exempt_channels:
                exempt_channels.remove(channel.id)
                message = f"✅ {channel.mention} is no longer exempt from AutoMod."
            else:
                await ctx.send(f"⚠️ {channel.mention} is not in the exempt list.")
                return
        else:
            # Add channel if it doesn't exist
            if channel.id not in exempt_channels:
                exempt_channels.append(channel.id)
                message = f"✅ {channel.mention} is now exempt from AutoMod."
            else:
                await ctx.send(f"⚠️ {channel.mention} is already exempt.")
                return
        
        # Update config
        config["exempt_channels"] = exempt_channels
        
        # Save config
        success = await self.automod.save_config(ctx.guild.id, config)
        
        if success:
            embed = AutoModEmbed.status(ctx.guild, config)
            await ctx.send(message, embed=embed)
        else:
            await ctx.send("❌ Failed to update exempt channels.")
    
    @command_help(
        category="mod",
        description="Add a word to the bad words filter",
        usage="automod add_bad_word <word>",
        examples=["automod add_bad_word badword"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="add_bad_word", description="Add a word to the bad words filter")
    async def add_bad_word(self, ctx, *, word: str):
        """Add a word to the bad words filter"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get custom bad words list
        custom_words = config["modules"]["bad_words"].get("custom_words", [])
        
        # Add word if it doesn't exist
        if word.lower() not in [w.lower() for w in custom_words]:
            custom_words.append(word.lower())
            config["modules"]["bad_words"]["custom_words"] = custom_words
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Added '{word}' to the bad words filter.")
            else:
                await ctx.send("❌ Failed to update bad words list.")
        else:
            await ctx.send(f"⚠️ '{word}' is already in the bad words list.")
    
    @command_help(
        category="mod",
        description="Remove a word from the bad words filter",
        usage="automod remove_bad_word <word>",
        examples=["automod remove_bad_word badword"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="remove_bad_word", description="Remove a word from the bad words filter")
    async def remove_bad_word(self, ctx, *, word: str):
        """Remove a word from the bad words filter"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get custom bad words list
        custom_words = config["modules"]["bad_words"].get("custom_words", [])
        
        # Find matching word (case insensitive)
        found = False
        for i, w in enumerate(custom_words):
            if w.lower() == word.lower():
                del custom_words[i]
                found = True
                break
        
        if found:
            config["modules"]["bad_words"]["custom_words"] = custom_words
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Removed '{word}' from the bad words filter.")
            else:
                await ctx.send("❌ Failed to update bad words list.")
        else:
            await ctx.send(f"⚠️ '{word}' was not found in the custom bad words list.")
    
    @command_help(
        category="mod",
        description="List all custom bad words in the filter",
        usage="automod list_bad_words"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="list_bad_words", description="List all custom bad words")
    async def list_bad_words(self, ctx):
        """List all custom bad words in the filter"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get custom bad words list
        custom_words = config["modules"]["bad_words"].get("custom_words", [])
        
        if not custom_words:
            await ctx.send("No custom bad words are configured.")
            return
            
        # Create embed
        embed = discord.Embed(
            title="🔍 Custom Bad Words",
            description=f"There are {len(custom_words)} custom bad words configured:",
            color=discord.Color.blue()
        )
        
        # Add words in a code block
        words_text = "```\n"
        for word in sorted(custom_words):
            words_text += f"• {word}\n"
        words_text += "```"
        
        embed.add_field(name="Words", value=words_text, inline=False)
        
        # Add note about default words
        embed.set_footer(text="Note: Default bad words are not shown.")
        
        await ctx.send(embed=embed)
    
    @command_help(
        category="mod",
        description="Add a domain to the link whitelist",
        usage="automod add_link_whitelist <domain>",
        examples=["automod add_link_whitelist discord.com"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="add_link_whitelist", description="Add a domain to the link whitelist")
    async def add_link_whitelist(self, ctx, *, domain: str):
        """Add a domain to the link whitelist"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get whitelist
        whitelist = config["modules"]["link_filter"].get("whitelist", [])
        
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Add domain if it doesn't exist
        if domain not in whitelist:
            whitelist.append(domain)
            config["modules"]["link_filter"]["whitelist"] = whitelist
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Added '{domain}' to the link whitelist.")
            else:
                await ctx.send("❌ Failed to update link whitelist.")
        else:
            await ctx.send(f"⚠️ '{domain}' is already in the whitelist.")
    
    @command_help(
        category="mod",
        description="Remove a domain from the link whitelist",
        usage="automod remove_link_whitelist <domain>",
        examples=["automod remove_link_whitelist discord.com"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="remove_link_whitelist", description="Remove a domain from the link whitelist")
    async def remove_link_whitelist(self, ctx, *, domain: str):
        """Remove a domain from the link whitelist"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get whitelist
        whitelist = config["modules"]["link_filter"].get("whitelist", [])
        
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Remove domain if it exists
        if domain in whitelist:
            whitelist.remove(domain)
            config["modules"]["link_filter"]["whitelist"] = whitelist
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Removed '{domain}' from the link whitelist.")
            else:
                await ctx.send("❌ Failed to update link whitelist.")
        else:
            await ctx.send(f"⚠️ '{domain}' is not in the whitelist.")
    
    @command_help(
        category="mod",
        description="Add a domain to the link blacklist",
        usage="automod add_link_blacklist <domain>",
        examples=["automod add_link_blacklist badsite.com"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="add_link_blacklist", description="Add a domain to the link blacklist")
    async def add_link_blacklist(self, ctx, *, domain: str):
        """Add a domain to the link blacklist"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get blacklist
        blacklist = config["modules"]["link_filter"].get("blacklist", [])
        
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Add domain if it doesn't exist
        if domain not in blacklist:
            blacklist.append(domain)
            config["modules"]["link_filter"]["blacklist"] = blacklist
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Added '{domain}' to the link blacklist.")
            else:
                await ctx.send("❌ Failed to update link blacklist.")
        else:
            await ctx.send(f"⚠️ '{domain}' is already in the blacklist.")
    
    @command_help(
        category="mod",
        description="Remove a domain from the link blacklist",
        usage="automod remove_link_blacklist <domain>",
        examples=["automod remove_link_blacklist badsite.com"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="remove_link_blacklist", description="Remove a domain from the link blacklist")
    async def remove_link_blacklist(self, ctx, *, domain: str):
        """Remove a domain from the link blacklist"""
        await ctx.defer()
        
        # Get current config
        config = await self.automod.get_config(ctx.guild.id)
        
        # Get blacklist
        blacklist = config["modules"]["link_filter"].get("blacklist", [])
        
        # Clean domain
        domain = domain.lower().strip()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Remove domain if it exists
        if domain in blacklist:
            blacklist.remove(domain)
            config["modules"]["link_filter"]["blacklist"] = blacklist
            
            # Save config
            success = await self.automod.save_config(ctx.guild.id, config)
            
            if success:
                await ctx.send(f"✅ Removed '{domain}' from the link blacklist.")
            else:
                await ctx.send("❌ Failed to update link blacklist.")
        else:
            await ctx.send(f"⚠️ '{domain}' is not in the blacklist.")

    @command_help(
        category="mod",
        description="Check active strikes for a user",
        usage="automod strikes <user>",
        examples=["automod strikes @User"]
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @automod_group.command(name="strikes", description="Check active strikes for a user")
    async def automod_strikes(self, ctx, user: discord.Member):
        """Check active strikes for a user"""
        await ctx.defer()
        
        config = await self.automod.get_config(ctx.guild.id)
        active_strikes = await self.automod.get_active_strikes(ctx.guild.id, user.id, config)
        
        embed = discord.Embed(
            title="⚖️ User Strikes",
            description=f"{user.mention} currently has **{active_strikes}** active strikes.",
            color=discord.Color.blue() if active_strikes == 0 else discord.Color.orange()
        )
        
        # List individual strikes
        strikes_list = config.get("strikes", {}).get(str(user.id), [])
        now = datetime.datetime.now().timestamp()
        valid = [s for s in strikes_list if s.get("expires", 0) > now]
        
        if valid:
            details = []
            for i, s in enumerate(valid, 1):
                rule = s.get("rule", "Manual").replace('_', ' ').title()
                val = s.get("value", 1)
                exp = discord.utils.format_dt(datetime.datetime.fromtimestamp(s.get("expires", 0)), style="R")
                details.append(f"**{i}.** `{rule}` (+{val}) - Expires {exp}")
            embed.add_field(name="Active Strike History", value="\n".join(details), inline=False)
            
        await ctx.send(embed=embed)
        
    @command_help(
        category="mod",
        description="Add manual strikes to a user",
        usage="automod add_strike <user> <amount> [reason]",
        examples=["automod add_strike @User 1 Warning"]
    )
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @automod_group.command(name="add_strike", description="Add manual strikes to a user")
    async def automod_add_strike(self, ctx, user: discord.Member, amount: int = 1, *, reason: str = "Manual application"):
        """Add manual strikes to a user"""
        await ctx.defer()
        
        if amount <= 0:
            await ctx.send("❌ Amount must be positive.")
            return
            
        config = await self.automod.get_config(ctx.guild.id)
        
        # Add the strike
        new_total = await self.automod.add_strike(ctx.guild.id, user.id, f"Manual: {reason}", amount, config)
        
        embed = discord.Embed(
            title="⚒️ Strike Added",
            description=f"Added **{amount}** strikes to {user.mention}.",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="New Total", value=f"{new_total} strikes", inline=False)
        
        await ctx.send(embed=embed)

    @command_help(
        category="mod",
        description="Clear all strikes from a user",
        usage="automod clear_strikes <user>",
        examples=["automod clear_strikes @User"]
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @automod_group.command(name="clear_strikes", description="Clear all strikes from a user")
    async def automod_clear_strikes(self, ctx, user: discord.Member):
        """Clear all active strikes from a user"""
        await ctx.defer()
        
        config = await self.automod.get_config(ctx.guild.id)
        
        strikes_data = config.get("strikes", {})
        if str(user.id) in strikes_data:
            del strikes_data[str(user.id)]
            config["strikes"] = strikes_data
            await self.automod.save_config(ctx.guild.id, config)
            
            embed = discord.Embed(
                title="🧹 Strikes Cleared",
                description=f"Successfully removed all strikes from {user.mention}.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"⚠️ {user.mention} has no strikes to clear.")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))