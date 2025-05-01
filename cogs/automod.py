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
            violation, rule, action = await self.automod.check_message(message)
            
            if violation:
                await self.automod.take_action(message, rule, action)
                
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
            violation, rule, action = await self.automod.check_message(after)
            
            if violation:
                await self.automod.take_action(after, rule, action)
                
        except Exception as e:
            self.logger.error(f"AutoMod error on edit: {str(e)}\n{traceback.format_exc()}")
    
    # === AutoMod Configuration Commands ===
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "View AutoMod status and configuration", "automod", examples=["automod"])
    @commands.hybrid_group(name="automod", fallback="status")
    @command_help("mod", "View AutoMod status and configuration", "automod")
    async def automod_group(self, ctx):
        """View AutoMod status and configuration"""
        await self.show_status(ctx)
    
    async def show_status(self, ctx):
        """Show current automod status"""
        await ctx.defer()
        
        config = await self.automod.get_config(ctx.guild.id)
        embed = AutoModEmbed.status(ctx.guild, config)
        
        await ctx.send(embed=embed)
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Enable the AutoMod system", "automod enable")
    @automod_group.command(name="enable", description="Enable the AutoMod system")
    @command_help("mod", "Enable the AutoMod system for this server", "automod enable")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Disable the AutoMod system", "automod disable")
    @automod_group.command(name="disable", description="Disable the AutoMod system")
    @command_help("mod", "Disable the AutoMod system for this server", "automod disable")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Set the log channel for AutoMod", "automod log_channel [channel]",
                 examples=["automod log_channel #automod-logs", "automod log_channel"])
    @automod_group.command(name="log_channel", description="Set the log channel for AutoMod")
    @command_help("mod", "Set the log channel for AutoMod notifications", "automod log_channel [channel]")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Configure an AutoMod module", "automod module <module> [enabled] [action] [duration]",
                 examples=["automod module spam true timeout 10", "automod module words false", "automod module link true delete"])
    @automod_group.command(name="module", description="Configure an AutoMod module")
    @command_help("mod", "Configure an AutoMod module", "automod module <module> [enabled] [action] [duration]",
                 "Modules: spam, mention, link, words | Actions: delete, warn, timeout, kick")
    async def configure_module(self, ctx, 
                              module: str, 
                              enabled: bool = None, 
                              action: str = None, 
                              duration: int = None):
        """Configure an automod module
        
        Parameters:
            module: The module to configure (spam, mention, link, words)
            enabled: Whether to enable or disable the module
            action: The action to take (delete, warn, timeout, kick)
            duration: The duration in minutes for timeouts
        """
        await ctx.defer()
        
        # Map short module names to full names
        module_mapping = {
            "spam": "anti_spam",
            "mention": "anti_mention_spam",
            "link": "link_filter",
            "words": "bad_words"
        }
        
        # Get the full module name
        module_name = module_mapping.get(module.lower(), module.lower())
        
        # Valid actions
        valid_actions = ["delete", "warn", "timeout", "kick"]
        
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
            
        # Update duration if provided
        if duration is not None:
            if duration < 0:
                await ctx.send("❌ Duration cannot be negative.")
                return
                
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
                response += f"\n- Duration set to {duration} minutes"
                
            await ctx.send(response, embed=embed)
        else:
            await ctx.send("❌ Failed to update module configuration.")
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Add or remove a role exempt from AutoMod", "automod exempt_role <role> [remove]",
                 examples=["automod exempt_role @Moderators", "automod exempt_role @Moderators true"])
    @automod_group.command(name="exempt_role", description="Add or remove an exempt role")
    @command_help("mod", "Add or remove a role exempt from AutoMod", "automod exempt_role <role> [remove]")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Add or remove a channel exempt from AutoMod", "automod exempt_channel <channel> [remove]",
                 examples=["automod exempt_channel #bot-commands", "automod exempt_channel #bot-commands true"])
    @automod_group.command(name="exempt_channel", description="Add or remove an exempt channel")
    @command_help("mod", "Add or remove a channel exempt from AutoMod", "automod exempt_channel <channel> [remove]")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Add a word to the bad words filter", "automod add_bad_word <word>",
                 examples=["automod add_bad_word badword"])
    @automod_group.command(name="add_bad_word", description="Add a word to the bad words filter")
    @command_help("mod", "Add a word to the bad words filter", "automod add_bad_word <word>")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Remove a word from the bad words filter", "automod remove_bad_word <word>",
                 examples=["automod remove_bad_word badword"])
    @automod_group.command(name="remove_bad_word", description="Remove a word from the bad words filter")
    @command_help("mod", "Remove a word from the bad words filter", "automod remove_bad_word <word>")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "List all custom bad words in the filter", "automod list_bad_words")
    @automod_group.command(name="list_bad_words", description="List all custom bad words")
    @command_help("mod", "List all custom bad words in the filter", "automod list_bad_words")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Add a domain to the link whitelist", "automod add_link_whitelist <domain>",
                 examples=["automod add_link_whitelist discord.com"])
    @automod_group.command(name="add_link_whitelist", description="Add a domain to the link whitelist")
    @command_help("mod", "Add a domain to the link whitelist", "automod add_link_whitelist <domain>")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Remove a domain from the link whitelist", "automod remove_link_whitelist <domain>",
                 examples=["automod remove_link_whitelist discord.com"])
    @automod_group.command(name="remove_link_whitelist", description="Remove a domain from the link whitelist")
    @command_help("mod", "Remove a domain from the link whitelist", "automod remove_link_whitelist <domain>")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Add a domain to the link blacklist", "automod add_link_blacklist <domain>",
                 examples=["automod add_link_blacklist badsite.com"])
    @automod_group.command(name="add_link_blacklist", description="Add a domain to the link blacklist")
    @command_help("mod", "Add a domain to the link blacklist", "automod add_link_blacklist <domain>")
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
    
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @command_help("mod", "Remove a domain from the link blacklist", "automod remove_link_blacklist <domain>",
                 examples=["automod remove_link_blacklist badsite.com"])
    @automod_group.command(name="remove_link_blacklist", description="Remove a domain from the link blacklist")
    @command_help("mod", "Remove a domain from the link blacklist", "automod remove_link_blacklist <domain>")
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


async def setup(bot):
    await bot.add_cog(AutoMod(bot))