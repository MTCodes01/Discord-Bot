import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import datetime
import os
import json
from typing import Dict, List, Optional, Union, Any
from util.backups import ServerBackupSystem
import traceback
import io
import textwrap
import utils
from utils import command_help

class Backup(commands.Cog):
    """Server backup & restoration system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.backup_system = ServerBackupSystem(bot)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize backup system when bot is ready"""
        self.logger.info("Backup system initialized")
    
    # === Backup Commands ===
    
    @command_help(
        category="mod",
        description="Create a complete backup of the server structure and settings",
        usage="backup_server",
        examples=["backup_server"],
        note="Creates a backup with channels, roles, permissions, and emojis"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="backup_server", aliases=["backup"])
    async def backup_server(self, ctx):
        """Create a complete backup of the server structure"""
        await ctx.defer()
        
        # Create status embed
        embed = discord.Embed(
            title="📦 Creating Server Backup",
            description="Please wait while I create a backup of this server...",
            color=discord.Color.blue()
        )
        
        message = await ctx.send(embed=embed)
        
        # Perform backup
        success, result_msg, backup_id = await self.backup_system.create_backup(ctx.guild)
        
        # Update embed based on result
        if success:
            embed.title = "✅ Server Backup Complete!"
            embed.description = result_msg
            embed.color = discord.Color.green()
            
            # Add backup info
            embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=False)
            embed.add_field(
                name="Restore Command",
                value=f"To restore this backup to another server, use:\n`{ctx.prefix}restore_backup {backup_id}`",
                inline=False
            )
        else:
            embed.title = "❌ Backup Failed"
            embed.description = result_msg
            embed.color = discord.Color.red()
        
        await message.edit(embed=embed)
    
    @command_help(
        category="mod",
        description="List all available backups for this server",
        usage="list_backups",
        examples=["list_backups"],
        note="Shows all backups with their creation date and ID"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="list_backups", aliases=["backups"])
    async def list_backups(self, ctx):
        """List all available backups for this server"""
        await ctx.defer()
        
        # Get backups
        backups = await self.backup_system.list_backups(ctx.guild.id)
        
        # Create embed
        embed = discord.Embed(
            title="📦 Server Backups",
            color=discord.Color.blue()
        )
        
        if not backups:
            embed.description = "No backups found for this server."
            embed.color = discord.Color.orange()
            await ctx.send(embed=embed)
            return
            
        # Add backups to embed
        embed.description = f"Found {len(backups)} backup(s) for this server:"
        
        for i, backup in enumerate(backups[:10]):  # Show only top 10
            channels = backup.get("channels", 0)
            roles = backup.get("roles", 0)
            
            backup_text = (
                f"**ID:** `{backup['id']}`\n"
                f"**Date:** {backup['date']}\n"
                f"**Size:** {backup['file_size']} KB\n"
                f"**Content:** {channels} channels, {roles} roles"
            )
            
            embed.add_field(
                name=f"Backup #{i+1}",
                value=backup_text,
                inline=False
            )
        
        # Add usage hint
        embed.set_footer(text=f"Use {ctx.prefix}restore_backup <backup_id> to restore a backup")
        
        await ctx.send(embed=embed)
    
    @command_help(
        category="owner",
        description="Restore a server backup to the current server",
        usage="restore_backup <backup_id>",
        examples=["restore_backup 123456789_20250101_120000"],
        note="This will not overwrite existing channels with the same name"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="restore_backup", aliases=["restore"])
    async def restore_backup(self, ctx, backup_id: str):
        """Restore a server from a backup ID"""
        await ctx.defer()
        
        # Verify backup ID format
        if "_" not in backup_id:
            await ctx.send("❌ Invalid backup ID format. Use the ID from `list_backups` command.")
            return
            
        # Confirm with user
        confirmation_embed = discord.Embed(
            title="⚠️ Restore Confirmation",
            description=(
                "**WARNING:** This will add channels, roles and categories from the backup "
                "to this server. Existing items with the same name will be skipped.\n\n"
                "Are you sure you want to continue?"
            ),
            color=discord.Color.gold()
        )
        
        confirmation_embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=False)
        confirmation_embed.set_footer(text="Reply with 'yes' within 30 seconds to confirm.")
        
        await ctx.send(embed=confirmation_embed)
        
        # Wait for confirmation
        try:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "yes"
                
            await self.bot.wait_for("message", check=check, timeout=30.0)
            
            # Create status embed
            embed = discord.Embed(
                title="📦 Restoring Server Backup",
                description="Please wait while I restore the server structure...",
                color=discord.Color.blue()
            )
            
            message = await ctx.send(embed=embed)
            
            # Perform restore
            success, result_msg = await self.backup_system.restore_backup(ctx.guild, backup_id)
            
            # Update embed based on result
            if success:
                embed.title = "✅ Server Restore Complete!"
                embed.description = result_msg
                embed.color = discord.Color.green()
            else:
                embed.title = "❌ Restore Failed"
                embed.description = result_msg
                embed.color = discord.Color.red()
            
            await message.edit(embed=embed)
            
        except asyncio.TimeoutError:
            await ctx.send("Restore canceled: confirmation timeout.")
    
    @command_help(
        category="owner",
        description="Delete a server backup",
        usage="delete_backup <backup_id>",
        examples=["delete_backup 123456789_20250101_120000"],
        note="This permanently removes the backup and cannot be undone"
    )
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="delete_backup")
    async def delete_backup(self, ctx, backup_id: str):
        """Delete a server backup"""
        await ctx.defer()
        
        # Verify backup ID format
        if "_" not in backup_id:
            await ctx.send("❌ Invalid backup ID format. Use the ID from `list_backups` command.")
            return
            
        # Confirm with user
        confirmation_embed = discord.Embed(
            title="⚠️ Delete Confirmation",
            description="Are you sure you want to permanently delete this backup? This cannot be undone.",
            color=discord.Color.red()
        )
        
        confirmation_embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=False)
        confirmation_embed.set_footer(text="Reply with 'yes' within 30 seconds to confirm.")
        
        await ctx.send(embed=confirmation_embed)
        
        # Wait for confirmation
        try:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "yes"
                
            await self.bot.wait_for("message", check=check, timeout=30.0)
            
            # Perform delete
            success, result_msg = await self.backup_system.delete_backup(backup_id)
            
            # Send result
            if success:
                embed = discord.Embed(
                    title="✅ Backup Deleted",
                    description=result_msg,
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ Delete Failed",
                    description=result_msg,
                    color=discord.Color.red()
                )
            
            await ctx.send(embed=embed)
            
        except asyncio.TimeoutError:
            await ctx.send("Delete canceled: confirmation timeout.")

async def setup(bot):
    await bot.add_cog(Backup(bot))
    
    @command_help(
        name="backup_server",
        description="Create a complete backup of the server structure",
        usage=">backup_server",
        examples=[">backup_server"],
        note="Backs up channels, roles, permissions, and server settings. Does not backup messages or user data."
    )
    @commands.command(name="backup_server")
    @commands.has_permissions(administrator=True)
    async def backup_server_command(self, ctx):
        """Create a backup of the server structure"""
        await self.backup_server(ctx, is_slash=False)
    
    @app_commands.command(name="backup_server", description="Create a complete backup of the server structure")
    @app_commands.default_permissions(administrator=True)
    async def backup_server_slash(self, interaction: discord.Interaction):
        """Create a backup of the server structure (slash command)"""
        await self.backup_server(interaction, is_slash=True)
    
    async def backup_server(self, ctx_or_interaction, is_slash=False):
        """Common implementation for backing up a server"""
        
        guild = ctx_or_interaction.guild
        user = ctx_or_interaction.user
        
        # Prevent multiple backup operations for the same guild
        if guild.id in self.operations_in_progress:
            response = "A backup operation is already in progress for this server."
            if is_slash:
                await ctx_or_interaction.response.send_message(response, ephemeral=True)
            else:
                await ctx_or_interaction.reply(response)
            return
            
        self.operations_in_progress.add(guild.id)
        
        try:
            # Send initial response
            loading_message = "Creating server backup... This may take a few minutes depending on server size."
            
            if is_slash:
                await ctx_or_interaction.response.send_message(loading_message, ephemeral=True)
                message = await ctx_or_interaction.original_response()
            else:
                message = await ctx_or_interaction.send(loading_message)
            
            # Create initial embed
            embed = discord.Embed(
                title="📦 Server Backup",
                description="Creating backup... please wait",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Status", value="📝 Collecting server information...", inline=False)
            embed.add_field(name="Progress", value="⬜⬜⬜⬜⬜ 0%", inline=False)
            embed.set_footer(text=f"Requested by {user}")
            
            await message.edit(content=None, embed=embed)
            
            # Create the backup
            backup_id = await self.backup_system.create_backup(guild, user)
            
            if backup_id:
                # Get backup info
                backup_info = await self.backup_system.get_backup_info(guild.id, backup_id)
                
                # Update embed with success info
                embed.description = f"✅ Backup created successfully!"
                embed.clear_fields()
                
                embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
                embed.add_field(name="Created At", value=backup_info['created_at'], inline=True)
                
                # Add counts
                counts = backup_info['counts']
                counts_text = (
                    f"Categories: {counts['categories']}\n"
                    f"Channels: {counts['channels']}\n"
                    f"Roles: {counts['roles']}\n"
                    f"Emojis: {counts['emojis']}"
                )
                embed.add_field(name="Items Backed Up", value=counts_text, inline=False)
                
                # Add restore instructions
                embed.add_field(
                    name="To Restore",
                    value=f"Use command: `/restore_backup {backup_id}` or `>restore_backup {backup_id}`",
                    inline=False
                )
                
                embed.color = discord.Color.green()
                await message.edit(embed=embed)
                
            else:
                embed.description = "❌ Failed to create backup"
                embed.color = discord.Color.red()
                embed.clear_fields()
                embed.add_field(
                    name="Error",
                    value="An error occurred while creating the backup. Please check bot logs for details.",
                    inline=False
                )
                await message.edit(embed=embed)
                
        except Exception as e:
            # Log the error
            self.logger.error(f"Error creating backup: {str(e)}\n{traceback.format_exc()}")
            
            # Respond with error
            error_response = f"❌ An error occurred while creating backup: {str(e)}"
            
            try:
                if is_slash:
                    await ctx_or_interaction.edit_original_response(content=error_response)
                else:
                    await message.edit(content=error_response)
            except:
                pass
                
        finally:
            # Remove from in-progress set
            self.operations_in_progress.discard(guild.id)
    
    @command_help(
        name="restore_backup",
        description="Restore a server from a backup",
        usage=">restore_backup [backup_id] [--roles] [--channels] [--categories] [--emojis] [--settings]",
        examples=[
            ">restore_backup 20250501_120000",
            ">restore_backup 20250501_120000 --channels --categories",
            ">restore_backup 12345678_123456 --roles --settings"
        ],
        note="You can specify what to restore using the flags. If no flags are provided, everything will be restored."
    )
    @commands.command(name="restore_backup")
    @commands.has_permissions(administrator=True)
    async def restore_backup_command(self, ctx, backup_id: str = None, *args):
        """Restore a server from a backup"""
        if not backup_id:
            await ctx.send("❌ Please provide a backup ID. Use `>list_backups` to see available backups.")
            return
        
        # Parse flags
        options = {
            'roles': '--roles' in args or len(args) == 0,
            'categories': '--categories' in args or len(args) == 0,
            'channels': '--channels' in args or len(args) == 0,
            'emojis': '--emojis' in args or len(args) == 0,
            'settings': '--settings' in args or len(args) == 0
        }
        
        await self.restore_backup_server(ctx, backup_id, options, is_slash=False)
    
    @app_commands.command(name="restore_backup", description="Restore a server from a backup")
    @app_commands.describe(
        backup_id="ID of the backup to restore",
        restore_roles="Restore roles from backup",
        restore_categories="Restore categories from backup",
        restore_channels="Restore channels from backup",
        restore_emojis="Restore emojis from backup",
        restore_settings="Restore server settings from backup"
    )
    @app_commands.default_permissions(administrator=True)
    async def restore_backup_slash(self, interaction: discord.Interaction, 
                                  backup_id: str,
                                  restore_roles: bool = True,
                                  restore_categories: bool = True,
                                  restore_channels: bool = True,
                                  restore_emojis: bool = True,
                                  restore_settings: bool = True):
        """Restore a server from a backup (slash command)"""
        options = {
            'roles': restore_roles,
            'categories': restore_categories,
            'channels': restore_channels,
            'emojis': restore_emojis,
            'settings': restore_settings
        }
        
        await self.restore_backup_server(interaction, backup_id, options, is_slash=True)
    
    async def restore_backup_server(self, ctx_or_interaction, backup_id: str, options: Dict[str, bool], is_slash=False):
        """Common implementation for restoring a server backup"""
        
        guild = ctx_or_interaction.guild
        user = ctx_or_interaction.user
        
        # Prevent multiple operations for the same guild
        if guild.id in self.operations_in_progress:
            response = "A server operation is already in progress. Please wait for it to complete."
            if is_slash:
                await ctx_or_interaction.response.send_message(response, ephemeral=True)
            else:
                await ctx_or_interaction.reply(response)
            return
            
        self.operations_in_progress.add(guild.id)
        
        try:
            # Check if backup exists
            backup_info = await self.backup_system.get_backup_info(guild.id, backup_id)
            
            if not backup_info:
                response = f"❌ Backup with ID `{backup_id}` not found."
                if is_slash:
                    await ctx_or_interaction.response.send_message(response, ephemeral=True)
                else:
                    await ctx_or_interaction.reply(response)
                self.operations_in_progress.discard(guild.id)
                return
            
            # Send confirmation message
            confirmation_embed = discord.Embed(
                title="⚠️ Restore Confirmation Required",
                description=(
                    "**Warning:** This will modify your server structure according to the backup.\n"
                    "Existing channels with the same names may be duplicated, and role permissions will be replaced.\n\n"
                    "Are you sure you want to continue?"
                ),
                color=discord.Color.gold()
            )
            
            # Add backup info
            confirmation_embed.add_field(name="Backup ID", value=backup_id, inline=True)
            confirmation_embed.add_field(name="Created At", value=backup_info['created_at'], inline=True)
            confirmation_embed.add_field(name="Server Name", value=backup_info['name'], inline=True)
            
            # Add what will be restored
            to_restore = []
            if options['roles']:
                to_restore.append(f"✅ Roles ({backup_info['counts']['roles']})")
            else:
                to_restore.append("❌ Roles (skipped)")
                
            if options['categories']:
                to_restore.append(f"✅ Categories ({backup_info['counts']['categories']})")
            else:
                to_restore.append("❌ Categories (skipped)")
                
            if options['channels']:
                to_restore.append(f"✅ Channels ({backup_info['counts']['channels']})")
            else:
                to_restore.append("❌ Channels (skipped)")
                
            if options['emojis']:
                to_restore.append(f"✅ Emojis ({backup_info['counts']['emojis']})")
            else:
                to_restore.append("❌ Emojis (skipped)")
                
            if options['settings']:
                to_restore.append("✅ Server Settings")
            else:
                to_restore.append("❌ Server Settings (skipped)")
            
            confirmation_embed.add_field(name="Will Restore", value="\n".join(to_restore), inline=False)
            confirmation_embed.set_footer(text="Type 'confirm' to proceed or 'cancel' to abort")
            
            if is_slash:
                await ctx_or_interaction.response.send_message(embed=confirmation_embed)
                message = await ctx_or_interaction.original_response()
            else:
                message = await ctx_or_interaction.send(embed=confirmation_embed)
            
            # Wait for confirmation
            try:
                def check(m):
                    return m.author.id == user.id and m.channel.id == message.channel.id and m.content.lower() in ['confirm', 'cancel']
                
                confirm_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
                
                # Delete the confirmation message to keep things clean
                try:
                    await confirm_msg.delete()
                except:
                    pass
                
                if confirm_msg.content.lower() == 'cancel':
                    cancel_embed = discord.Embed(
                        title="🚫 Restore Cancelled",
                        description="The backup restoration has been cancelled.",
                        color=discord.Color.red()
                    )
                    await message.edit(embed=cancel_embed)
                    self.operations_in_progress.discard(guild.id)
                    return
                    
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏱️ Confirmation Timeout",
                    description="The confirmation timed out. The backup restoration was not started.",
                    color=discord.Color.red()
                )
                await message.edit(embed=timeout_embed)
                self.operations_in_progress.discard(guild.id)
                return
            
            # Start the restoration
            progress_embed = discord.Embed(
                title="🔄 Restoring Backup",
                description=f"Restoring backup with ID `{backup_id}`...",
                color=discord.Color.blue()
            )
            progress_embed.add_field(name="Status", value="Starting restoration...", inline=False)
            await message.edit(embed=progress_embed)
            
            # Perform the restoration
            results = await self.backup_system.restore_backup(guild, backup_id, options)
            
            # Show results
            if results['success']:
                result_embed = discord.Embed(
                    title="✅ Backup Restored",
                    description=f"Successfully restored backup with ID `{backup_id}`.",
                    color=discord.Color.green()
                )
                
                # Add restoration stats
                stats = []
                if options['roles']:
                    stats.append(f"Roles Created: {results['roles_created']}")
                if options['categories']:
                    stats.append(f"Categories Created: {results['categories_created']}")
                if options['channels']:
                    stats.append(f"Channels Created: {results['channels_created']}")
                if options['emojis']:
                    stats.append(f"Emojis Created: {results['emojis_created']}")
                if options['settings']:
                    stats.append(f"Settings Updated: {'Yes' if results['settings_updated'] else 'No'}")
                
                result_embed.add_field(name="Restoration Results", value="\n".join(stats), inline=False)
                
                if results['errors']:
                    error_text = "\n".join(results['errors'][:5])
                    if len(results['errors']) > 5:
                        error_text += f"\n...and {len(results['errors']) - 5} more errors"
                    result_embed.add_field(name="⚠️ Warnings", value=error_text, inline=False)
                
                await message.edit(embed=result_embed)
                
            else:
                error_embed = discord.Embed(
                    title="❌ Restore Failed",
                    description="Failed to restore the backup. See errors below.",
                    color=discord.Color.red()
                )
                
                if results['errors']:
                    error_text = "\n".join(results['errors'][:5])
                    if len(results['errors']) > 5:
                        error_text += f"\n...and {len(results['errors']) - 5} more errors"
                    error_embed.add_field(name="Errors", value=error_text, inline=False)
                
                await message.edit(embed=error_embed)
                
        except Exception as e:
            # Log the error
            self.logger.error(f"Error restoring backup: {str(e)}\n{traceback.format_exc()}")
            
            # Respond with error
            error_response = f"❌ An error occurred while restoring backup: {str(e)}"
            
            try:
                if is_slash and not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(error_response, ephemeral=True)
                elif is_slash:
                    await ctx_or_interaction.edit_original_response(content=error_response)
                else:
                    await ctx_or_interaction.send(error_response)
            except:
                pass
                
        finally:
            # Remove from in-progress set
            self.operations_in_progress.discard(guild.id)
    
    @command_help(
        name="list_backups",
        description="List all available backups for this server",
        usage=">list_backups",
        examples=[">list_backups"],
        note="Shows backups for the current server only. Use backup_info for details about a specific backup."
    )
    @commands.command(name="list_backups")
    @commands.has_permissions(administrator=True)
    async def list_backups_command(self, ctx):
        """List all backups for the server"""
        await self.list_server_backups(ctx, is_slash=False)
    
    @app_commands.command(name="list_backups", description="List all available backups for this server")
    @app_commands.default_permissions(administrator=True)
    async def list_backups_slash(self, interaction: discord.Interaction):
        """List all backups for the server (slash command)"""
        await self.list_server_backups(interaction, is_slash=True)
    
    async def list_server_backups(self, ctx_or_interaction, is_slash=False):
        """Common implementation for listing server backups"""
        
        guild = ctx_or_interaction.guild
        
        try:
            # Send initial response
            loading_message = "Fetching backups..."
            
            if is_slash:
                await ctx_or_interaction.response.send_message(loading_message, ephemeral=True)
                message = await ctx_or_interaction.original_response()
            else:
                message = await ctx_or_interaction.send(loading_message)
            
            # Get the backups
            backups = self.backup_system.list_backups(guild.id)
            
            if not backups:
                no_backups_embed = discord.Embed(
                    title="📦 Server Backups",
                    description="No backups found for this server.",
                    color=discord.Color.blue()
                )
                no_backups_embed.add_field(
                    name="Create a Backup",
                    value="Use `/backup_server` or `>backup_server` to create a backup.",
                    inline=False
                )
                await message.edit(content=None, embed=no_backups_embed)
                return
            
            # Create a list of backup entries
            backup_list = []
            for i, backup in enumerate(backups[:10], 1):  # Limit to 10 most recent
                created_date = datetime.datetime.fromtimestamp(backup['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                backup_list.append(
                    f"**{i}. `{backup['id']}`** - {created_date}\n" +
                    f"Channels: {backup['channel_count']} | Roles: {backup['role_count']} | Size: {backup['size'] // 1024} KB"
                )
            
            # Create embed
            backups_embed = discord.Embed(
                title="📦 Server Backups",
                description=f"Found {len(backups)} backups for this server.",
                color=discord.Color.blue()
            )
            
            backups_embed.add_field(
                name="Recent Backups",
                value="\n\n".join(backup_list) if backup_list else "No backups available.",
                inline=False
            )
            
            backups_embed.add_field(
                name="Backup Commands",
                value=(
                    "• `/backup_server` - Create a new backup\n" +
                    "• `/backup_info <id>` - Show backup details\n" +
                    "• `/restore_backup <id>` - Restore a backup\n" +
                    "• `/delete_backup <id>` - Delete a backup"
                ),
                inline=False
            )
            
            # Show total count if more than shown
            if len(backups) > 10:
                backups_embed.set_footer(text=f"Showing 10 most recent backups out of {len(backups)} total")
            
            await message.edit(content=None, embed=backups_embed)
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error listing backups: {str(e)}\n{traceback.format_exc()}")
            
            # Respond with error
            error_response = f"❌ An error occurred while listing backups: {str(e)}"
            
            try:
                if is_slash:
                    await ctx_or_interaction.edit_original_response(content=error_response)
                else:
                    await message.edit(content=error_response)
            except:
                pass
    
    @command_help(
        name="backup_info",
        description="Show detailed information about a specific backup",
        usage=">backup_info [backup_id]",
        examples=[">backup_info 20250501_120000"],
        note="Shows the contents and metadata of the backup."
    )
    @commands.command(name="backup_info")
    @commands.has_permissions(administrator=True)
    async def backup_info_command(self, ctx, backup_id: str = None):
        """Show details about a specific backup"""
        if not backup_id:
            await ctx.send("❌ Please provide a backup ID. Use `>list_backups` to see available backups.")
            return
            
        await self.show_backup_info(ctx, backup_id, is_slash=False)
    
    @app_commands.command(name="backup_info", description="Show detailed information about a specific backup")
    @app_commands.describe(backup_id="ID of the backup to show information about")
    @app_commands.default_permissions(administrator=True)
    async def backup_info_slash(self, interaction: discord.Interaction, backup_id: str):
        """Show details about a specific backup (slash command)"""
        await self.show_backup_info(interaction, backup_id, is_slash=True)
    
    async def show_backup_info(self, ctx_or_interaction, backup_id: str, is_slash=False):
        """Common implementation for showing backup info"""
        
        guild = ctx_or_interaction.guild
        
        try:
            # Send initial response
            loading_message = f"Fetching information for backup `{backup_id}`..."
            
            if is_slash:
                await ctx_or_interaction.response.send_message(loading_message, ephemeral=True)
                message = await ctx_or_interaction.original_response()
            else:
                message = await ctx_or_interaction.send(loading_message)
            
            # Get backup info
            backup_info = await self.backup_system.get_backup_info(guild.id, backup_id)
            
            if not backup_info:
                not_found_embed = discord.Embed(
                    title="❌ Backup Not Found",
                    description=f"No backup with ID `{backup_id}` was found.",
                    color=discord.Color.red()
                )
                not_found_embed.add_field(
                    name="Available Backups",
                    value="Use `/list_backups` or `>list_backups` to see available backups.",
                    inline=False
                )
                await message.edit(content=None, embed=not_found_embed)
                return
            
            # Create detailed embed
            info_embed = discord.Embed(
                title="📦 Backup Information",
                description=f"Details for backup `{backup_id}`",
                color=discord.Color.blue()
            )
            
            # Add basic info
            info_embed.add_field(name="Server Name", value=backup_info['name'], inline=True)
            info_embed.add_field(name="Created At", value=backup_info['created_at'], inline=True)
            info_embed.add_field(name="Size", value=f"{backup_info['size'] // 1024} KB", inline=True)
            
            # Add requester info if available
            if backup_info.get('requester'):
                requester = backup_info['requester']
                requester_text = f"<@{requester.get('id')}> ({requester.get('name', 'Unknown')})"
                info_embed.add_field(name="Requested By", value=requester_text, inline=True)
            
            # Add content counts
            counts = backup_info['counts']
            counts_text = (
                f"Categories: {counts['categories']}\n"
                f"Channels: {counts['channels']}\n"
                f"Roles: {counts['roles']}\n"
                f"Emojis: {counts['emojis']}\n"
                f"Bots: {counts['bots']}"
            )
            info_embed.add_field(name="Contents", value=counts_text, inline=False)
            
            # Add server settings
            settings = backup_info['settings']
            settings_text = (
                f"Verification Level: {settings.get('verification_level', 'Unknown')}\n"
                f"Content Filter: {settings.get('explicit_content_filter', 'Unknown')}\n"
                f"Notifications: {settings.get('default_notifications', 'Unknown')}"
            )
            info_embed.add_field(name="Settings", value=settings_text, inline=False)
            
            # Add restore command
            info_embed.add_field(
                name="Restore Command",
                value=f"`/restore_backup {backup_id}` or `>restore_backup {backup_id}`",
                inline=False
            )
            
            await message.edit(content=None, embed=info_embed)
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error getting backup info: {str(e)}\n{traceback.format_exc()}")
            
            # Respond with error
            error_response = f"❌ An error occurred while getting backup info: {str(e)}"
            
            try:
                if is_slash:
                    await ctx_or_interaction.edit_original_response(content=error_response)
                else:
                    await message.edit(content=error_response)
            except:
                pass
    
    @command_help(
        name="delete_backup",
        description="Delete a server backup",
        usage=">delete_backup [backup_id]",
        examples=[">delete_backup 20250501_120000"],
        note="This action cannot be undone."
    )
    @commands.command(name="delete_backup")
    @commands.has_permissions(administrator=True)
    async def delete_backup_command(self, ctx, backup_id: str = None):
        """Delete a server backup"""
        if not backup_id:
            await ctx.send("❌ Please provide a backup ID. Use `>list_backups` to see available backups.")
            return
            
        await self.delete_server_backup(ctx, backup_id, is_slash=False)
    
    @app_commands.command(name="delete_backup", description="Delete a server backup")
    @app_commands.describe(backup_id="ID of the backup to delete")
    @app_commands.default_permissions(administrator=True)
    async def delete_backup_slash(self, interaction: discord.Interaction, backup_id: str):
        """Delete a server backup (slash command)"""
        await self.delete_server_backup(interaction, backup_id, is_slash=True)
    
    async def delete_server_backup(self, ctx_or_interaction, backup_id: str, is_slash=False):
        """Common implementation for deleting a server backup"""
        
        guild = ctx_or_interaction.guild
        user = ctx_or_interaction.user
        
        try:
            # Check if backup exists
            backup_info = await self.backup_system.get_backup_info(guild.id, backup_id)
            
            if not backup_info:
                response = f"❌ Backup with ID `{backup_id}` not found."
                if is_slash:
                    await ctx_or_interaction.response.send_message(response, ephemeral=True)
                else:
                    await ctx_or_interaction.reply(response)
                return
            
            # Send confirmation message
            confirmation_embed = discord.Embed(
                title="⚠️ Delete Confirmation Required",
                description=(
                    f"Are you sure you want to delete backup `{backup_id}`?\n"
                    f"Created: {backup_info['created_at']}\n"
                    f"Server: {backup_info['name']}\n\n"
                    "**This action cannot be undone.**"
                ),
                color=discord.Color.red()
            )
            confirmation_embed.set_footer(text="Type 'confirm' to proceed or 'cancel' to abort")
            
            if is_slash:
                await ctx_or_interaction.response.send_message(embed=confirmation_embed)
                message = await ctx_or_interaction.original_response()
            else:
                message = await ctx_or_interaction.send(embed=confirmation_embed)
            
            # Wait for confirmation
            try:
                def check(m):
                    return m.author.id == user.id and m.channel.id == message.channel.id and m.content.lower() in ['confirm', 'cancel']
                
                confirm_msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                
                # Delete the confirmation message to keep things clean
                try:
                    await confirm_msg.delete()
                except:
                    pass
                
                if confirm_msg.content.lower() == 'cancel':
                    cancel_embed = discord.Embed(
                        title="🚫 Deletion Cancelled",
                        description=f"The backup `{backup_id}` was not deleted.",
                        color=discord.Color.blue()
                    )
                    await message.edit(embed=cancel_embed)
                    return
                    
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏱️ Confirmation Timeout",
                    description="The confirmation timed out. The backup was not deleted.",
                    color=discord.Color.blue()
                )
                await message.edit(embed=timeout_embed)
                return
            
            # Delete the backup
            success = await self.backup_system.delete_backup(guild.id, backup_id)
            
            if success:
                success_embed = discord.Embed(
                    title="✅ Backup Deleted",
                    description=f"Successfully deleted backup `{backup_id}`.",
                    color=discord.Color.green()
                )
                await message.edit(embed=success_embed)
            else:
                error_embed = discord.Embed(
                    title="❌ Deletion Failed",
                    description=f"Failed to delete backup `{backup_id}`.",
                    color=discord.Color.red()
                )
                await message.edit(embed=error_embed)
            
        except Exception as e:
            # Log the error
            self.logger.error(f"Error deleting backup: {str(e)}\n{traceback.format_exc()}")
            
            # Respond with error
            error_response = f"❌ An error occurred while deleting backup: {str(e)}"
            
            try:
                if is_slash and not ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.response.send_message(error_response, ephemeral=True)
                elif is_slash:
                    await ctx_or_interaction.edit_original_response(content=error_response)
                else:
                    await ctx_or_interaction.send(error_response)
            except:
                pass


async def setup(bot):
    await bot.add_cog(Backup(bot))