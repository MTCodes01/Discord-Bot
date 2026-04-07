import discord
import traceback
from discord.ext import commands
from util.welcome_utils import WelcomeSystem
from utils import command_help

class Welcome(commands.Cog):
    """Handles Welcome and Leave messages and configurations"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = bot.logger
        self.welcome_system = WelcomeSystem(bot)

    def _format_welcome_message(self, member: discord.Member, config: dict) -> str:
        """Formats the adaptive welcome message based on configured channels"""
        
        msg = f"Welcome To {member.guild.name} {member.mention} ✨\n"
        msg += "Learn, build, and contribute to open source.\n"
        msg += "--------------------------------------------\n"
        
        channels = config.get("channels", {})
        has_channels = False
        
        rules = channels.get("rules")
        if rules:
            msg += f"📜 Check out <#{rules}> to get started.\n"
            has_channels = True
            
        xp = channels.get("xp")
        if xp:
            msg += f"🏅 Check your ranks in <#{xp}>\n"
            has_channels = True
            
        announcements = channels.get("announcements")
        if announcements:
            msg += f"💬 Stay tuned for announcements in <#{announcements}>\n"
            has_channels = True
            
        if not has_channels:
            msg += f"Say hi and introduce yourself to the community!\n"
            
        msg += "\nHappy Learning! 💻✨"
        return msg

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
            
        try:
            config = await self.welcome_system.get_config(member.guild.id)
            if not config.get("welcome", {}).get("enabled", False):
                return
                
            channel_id = config.get("welcome", {}).get("channel_id")
            if not channel_id:
                return
                
            channel = member.guild.get_channel(int(channel_id))
            if not channel:
                return
                
            card = await self.welcome_system.generate_card(member, is_welcome=True)
            msg_text = self._format_welcome_message(member, config)
            
            if card:
                await channel.send(content=msg_text, file=card)
            else:
                await channel.send(content=msg_text)
                
        except Exception as e:
            self.logger.error(f"Error executing welcome event: {e}\n{traceback.format_exc()}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
            
        try:
            config = await self.welcome_system.get_config(member.guild.id)
            if not config.get("leave", {}).get("enabled", False):
                return
                
            channel_id = config.get("leave", {}).get("channel_id")
            if not channel_id:
                return
                
            channel = member.guild.get_channel(int(channel_id))
            if not channel:
                return
                
            card = await self.welcome_system.generate_card(member, is_welcome=False)
            msg_text = f"Goodbye **{member.display_name}**... We hope to see you again soon. 💫"
            
            if card:
                await channel.send(content=msg_text, file=card)
            else:
                await channel.send(content=msg_text)
                
        except Exception as e:
            self.logger.error(f"Error executing leave event: {e}\n{traceback.format_exc()}")

    # --- Moderation Setup Commands ---
    
    @command_help("mod", "Configure the Welcome and Leave systems", "welcomeconfig")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @commands.hybrid_group(name="welcomeconfig", fallback="show", description="Configure the Welcome and Leave systems")
    async def welcomeconfig(self, ctx):
        """Configuration options for the Welcome and Leave systems."""
        await ctx.defer()
        await ctx.send("Available commands: `toggle`, `setchannel`, `setdata`, `test`")

    @command_help("mod", "Toggle the welcome or leave system on/off", "welcomeconfig toggle <system> <enabled>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @welcomeconfig.command(name="toggle", description="Toggle the welcome or leave system on/off")
    async def toggle(self, ctx, system: str, enabled: bool):
        """Toggle the welcome or leave system on/off (e.g. !welcomeconfig toggle welcome True)"""
        await ctx.defer()
        system = system.lower()
        if system not in ["welcome", "leave"]:
            return await ctx.send("❌ System must be either 'welcome' or 'leave'")
            
        config = await self.welcome_system.get_config(ctx.guild.id)
        config[system]["enabled"] = enabled
        await self.welcome_system.save_config(ctx.guild.id, config)
        await ctx.send(f"✅ Turned **{system}** system {'ON' if enabled else 'OFF'}.")

    @command_help("mod", "Set the channel where welcome/leave messages are sent", "welcomeconfig setchannel <system> <channel>")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @welcomeconfig.command(name="setchannel", description="Set the channel where welcome/leave messages are sent")
    async def setchannel(self, ctx, system: str, channel: discord.TextChannel):
        """Set the channel where welcome/leave messages are sent."""
        await ctx.defer()
        system = system.lower()
        if system not in ["welcome", "leave"]:
            return await ctx.send("❌ System must be either 'welcome' or 'leave'")
            
        config = await self.welcome_system.get_config(ctx.guild.id)
        config[system]["channel_id"] = channel.id
        await self.welcome_system.save_config(ctx.guild.id, config)
        await ctx.send(f"✅ Set **{system}** alerts to post in {channel.mention}.")

    @command_help("mod", "Map data channels (rules, xp, announcements)", "welcomeconfig setdata <data_type> [channel]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @welcomeconfig.command(name="setdata", description="Map data channels (rules, xp, announcements)")
    async def setdata(self, ctx, data_type: str, channel: discord.TextChannel = None):
        """Map data channels (rules, xp, announcements). Leave channel blank to un-map."""
        await ctx.defer()
        data_type = data_type.lower()
        if data_type not in ["rules", "xp", "announcements"]:
            return await ctx.send("❌ Data type must be 'rules', 'xp', or 'announcements'")
            
        config = await self.welcome_system.get_config(ctx.guild.id)
        config["channels"][data_type] = channel.id if channel else None
        await self.welcome_system.save_config(ctx.guild.id, config)
        
        if channel:
            await ctx.send(f"✅ Mapped the **{data_type}** data field to {channel.mention}.")
        else:
            await ctx.send(f"✅ Un-mapped the **{data_type}** data field.")

    @command_help("mod", "Test the welcome or leave message manually", "welcomeconfig test [system]")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    @welcomeconfig.command(name="test", description="Test the welcome or leave message in the current channel")
    async def test(self, ctx, system: str = "welcome"):
        """Test the welcome or leave message in the current channel"""
        system = system.lower()
        if system not in ["welcome", "leave"]:
            return await ctx.send("❌ System must be either 'welcome' or 'leave'")
            
        await ctx.defer()
        config = await self.welcome_system.get_config(ctx.guild.id)
        
        if system == "welcome":
            card = await self.welcome_system.generate_card(ctx.author, is_welcome=True)
            msg_text = self._format_welcome_message(ctx.author, config)
        else:
            card = await self.welcome_system.generate_card(ctx.author, is_welcome=False)
            msg_text = f"Goodbye **{ctx.author.display_name}**... We hope to see you again soon. 💫"
            
        if card:
            await ctx.send(content=msg_text, file=card)
        else:
            await ctx.send(content=msg_text)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
