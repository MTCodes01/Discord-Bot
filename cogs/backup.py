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

class BackupListView(discord.ui.View):
    """Interactive backup list with pagination"""
    
    def __init__(self, ctx, backups, timeout=120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.backups = backups
        self.current_page = 0
        self.items_per_page = 10
        
        # Setup the navigation buttons
        self.previous_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Previous",
            emoji="◀️",
            disabled=True
        )
        self.previous_button.callback = self.on_previous
        self.add_item(self.previous_button)
        
        self.next_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Next",
            emoji="▶️",
            disabled=self.get_total_pages() <= 1
        )
        self.next_button.callback = self.on_next
        self.add_item(self.next_button)
        
    async def on_previous(self, interaction):
        """Handle previous page button"""
        self.current_page -= 1
        await self.update_view(interaction)
    
    async def on_next(self, interaction):
        """Handle next page button"""
        self.current_page += 1
        await self.update_view(interaction)
    
    async def update_view(self, interaction):
        """Update the view and embed"""
        # Update button states
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.get_total_pages() - 1)
        
        # Update the message
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    def get_total_pages(self):
        """Calculate the total number of pages"""
        return max(1, (len(self.backups) + self.items_per_page - 1) // self.items_per_page)
    
    def get_embed(self):
        """Generate the backups embed for the current page"""
        guild = self.ctx.guild
        
        embed = discord.Embed(
            title=f"📦 Server Backups - {guild.name}",
            color=discord.Color.blue()
        )
        
        # Add server info
        server_info = (
            f"**Server ID:** {guild.id}\n"
            f"**Members:** {guild.member_count}\n"
            f"**Created:** <t:{int(guild.created_at.timestamp())}:R>\n"
            f"**Features:** {', '.join(guild.features) if guild.features else 'None'}"
        )
        embed.add_field(name="📊 Server Information", value=server_info, inline=False)
        
        # Set server icon if available
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Calculate pagination
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.backups))
        
        # Add backups to embed
        embed.add_field(name="Available Backups", 
                       value=f"Found {len(self.backups)} backup(s) for this server:", 
                       inline=False)
        
        page_backups = self.backups[start_idx:end_idx]
        for i, backup in enumerate(page_backups):
            channels = backup.get("channel_count", 0)
            roles = backup.get("role_count", 0)
            
            backup_text = (
                f"**ID:** `{backup['id']}`\n"
                f"**Date:** {backup['date']}\n"
                f"**Size:** {backup['file_size']} KB\n"
                f"**Content:** {channels} channels, {roles} roles"
            )
            
            embed.add_field(
                name=f"Backup #{start_idx + i + 1}",
                value=backup_text,
                inline=False
            )
        
        # Add pagination info to footer
        total_pages = self.get_total_pages()
        
        footer_text = f"Page {self.current_page + 1}/{total_pages} • "
        footer_text += f"Showing {len(page_backups)} of {len(self.backups)} backups • "
        footer_text += f"Use {self.ctx.prefix}restore_backup <backup_id> to restore a backup"
        
        embed.set_footer(text=footer_text)
        
        return embed
        
    async def interaction_check(self, interaction):
        """Ensure only the user who initiated the command can use the components"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("You can't use this menu. Please run your own backup list command.", ephemeral=True)
            return False
        return True

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
        
        if not backups:
            embed = discord.Embed(
                title="📦 Server Backups",
                description="No backups found for this server.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        
        # Create pagination view for backups
        view = BackupListView(ctx, backups)
        embed = view.get_embed()
        
        await ctx.send(embed=embed, view=view)
    
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