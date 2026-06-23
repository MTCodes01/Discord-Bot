import discord
import datetime
from .detector import DetectionResult
from .config import ProfanityConfig

class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Approve (Safe)", style=discord.ButtonStyle.green, custom_id="profanity_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # When approved, we could optionally add to whitelist, but for now just log it
        await interaction.response.send_message("Message marked as safe. The detector will learn from this in the future.", ephemeral=True)
        
        # Update the embed to show it was approved
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ Profanity Review: Approved"
        embed.set_footer(text=f"Approved by {interaction.user.display_name}")
        
        for item in self.children:
            item.disabled = True
            
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Reject (Delete)", style=discord.ButtonStyle.red, custom_id="profanity_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = interaction.message.embeds[0]
        channel_id_str = ""
        msg_id_str = ""
        for field in embed.fields:
            if field.name == "Channel":
                channel_id_str = field.value.strip("<#>")
            elif field.name == "Message ID":
                msg_id_str = field.value

        delete_status = "Original message could not be found."
        if channel_id_str and msg_id_str:
            try:
                channel = interaction.guild.get_channel(int(channel_id_str))
                if channel:
                    msg = await channel.fetch_message(int(msg_id_str))
                    await msg.delete()
                    delete_status = "Message deleted."
            except Exception:
                delete_status = "Could not delete message (already deleted or missing permissions)."

        await interaction.response.send_message(f"Message rejected. {delete_status}", ephemeral=True)
        
        # Update the embed to show it was rejected
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ Profanity Review: Rejected & Deleted"
        embed.set_footer(text=f"Rejected by {interaction.user.display_name}")
        
        for item in self.children:
            item.disabled = True
            
        await interaction.message.edit(embed=embed, view=self)


class ModeratorReviewSystem:
    def __init__(self, bot, config: ProfanityConfig):
        self.bot = bot
        self.config = config

    async def send_for_review(self, message: discord.Message, result: DetectionResult, log_channel_id: int):
        """Sends an interactive embed to the moderator queue."""
        if not log_channel_id:
            return

        channel = self.bot.get_channel(log_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="⚠️ Profanity Review Required",
            description="A message was flagged for suspicious content but falls below the auto-delete threshold.",
            color=discord.Color.yellow(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(name="User", value=f"{message.author.mention} ({message.author.id})", inline=True)
        embed.add_field(name="Channel", value=f"{message.channel.mention}", inline=True)
        embed.add_field(name="Message ID", value=str(message.id), inline=True)
        
        embed.add_field(name="Confidence", value=f"{result.confidence}/100", inline=True)
        
        embed.add_field(name="Matched Word", value=f"`{result.matched_word}`", inline=True)
        embed.add_field(name="Detection Method", value=f"{result.detection_method}", inline=True)
        
        orig_text = result.original_text[:1020] + "..." if len(result.original_text) > 1024 else result.original_text
        embed.add_field(name="Original Message", value=f"```\n{orig_text}\n```", inline=False)
        
        view = ReviewView()
        
        try:
            await channel.send(embed=embed, view=view)
        except Exception as e:
            self.bot.logger.error(f"Failed to send profanity review queue: {e}")
