import discord
import datetime
from .detector import DetectionResult

class ProfanityLogger:
    def __init__(self, bot):
        self.bot = bot

    async def log_detection(self, message: discord.Message, result: DetectionResult, log_channel_id: int):
        """Logs the profanity detection context to the specified channel."""
        if not log_channel_id:
            return

        channel = self.bot.get_channel(log_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="🛑 Profanity Detected",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
        embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=True)
        embed.add_field(name="Confidence", value=f"{result.confidence}/100", inline=True)
        
        embed.add_field(name="Matched Word", value=f"`{result.matched_word}`", inline=True)
        embed.add_field(name="Detection Method", value=f"{result.detection_method}", inline=True)
        
        # Format text to avoid breaking embed limits
        orig_text = result.original_text[:1020] + "..." if len(result.original_text) > 1024 else result.original_text
        norm_text = result.normalized_text[:1020] + "..." if len(result.normalized_text) > 1024 else result.normalized_text
        
        embed.add_field(name="Original Message", value=f"```\n{orig_text}\n```", inline=False)
        embed.add_field(name="Normalized Message", value=f"```\n{norm_text}\n```", inline=False)
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Failed to send profanity log: {e}")
