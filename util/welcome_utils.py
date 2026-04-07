import discord
import os
import json
import logging
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

class WelcomeSystem:
    """Manages configurations and image generation for welcome/leave systems"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("WelcomeSystem")
        self.data_dir = "data/welcome"
        
        # Ensure data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Default configuration template
        self.default_config = {
            "welcome": {
                "enabled": False,
                "channel_id": None
            },
            "leave": {
                "enabled": False,
                "channel_id": None
            },
            "channels": {
                "rules": None,
                "xp": None,
                "announcements": None
            }
        }

    async def get_config(self, guild_id: int) -> Dict[str, Any]:
        """Get the welcome configuration for a guild"""
        file_path = os.path.join(self.data_dir, f"{guild_id}.json")
        
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    
                # Merge with default to ensure all keys exist
                merged = json.loads(json.dumps(self.default_config)) # Deep copy
                for k, v in config.items():
                    if isinstance(v, dict) and k in merged:
                        merged[k].update(v)
                    else:
                        merged[k] = v
                return merged
            else:
                return json.loads(json.dumps(self.default_config))
        except Exception as e:
            self.logger.error(f"Error loading config for {guild_id}: {e}")
            return json.loads(json.dumps(self.default_config))

    async def save_config(self, guild_id: int, config: Dict[str, Any]) -> bool:
        """Save the welcome configuration for a guild"""
        file_path = os.path.join(self.data_dir, f"{guild_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            self.logger.error(f"Error saving config for {guild_id}: {e}")
            return False

    async def generate_card(self, member: discord.Member, is_welcome: bool = True) -> Optional[discord.File]:
        """Generate a welcome or leave card image for a user"""
        try:
            # Load background image
            bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Welcome Card.png")
            if not os.path.exists(bg_path):
                # Try generic image.png fallback if Welcome Card is missing
                bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "image.png")
                
            if os.path.exists(bg_path):
                img = Image.open(bg_path).convert("RGBA")
            else:
                # Absolute fallback
                img = Image.new("RGBA", (800, 280), (30, 30, 35, 255))
                
            WIDTH, HEIGHT = img.size
            
            draw = ImageDraw.Draw(img)
            
            # Load fonts safely
            def load_font(font_names, size):
                for name in font_names:
                    try:
                        return ImageFont.truetype(name, size)
                    except Exception:
                        continue
                return ImageFont.load_default()
                
            # Base text sizes dynamic to image height
            # Assuming standard image is ~800x300. We scale font size based on image height.
            scale_factor = min(WIDTH / 800, HEIGHT / 300)
            
            title_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], int(50 * scale_factor))
            sub_font = load_font(["arial.ttf", "LiberationSans-Regular.ttf"], int(26 * scale_factor))
            
            # Avatar size proportional to image height
            ar = int(HEIGHT * 0.3)
            ax, ay = int(WIDTH * 0.1), HEIGHT // 2 - ar
            
            # Download avatar
            avatar_img = None
            try:
                avatar_url = member.display_avatar.url
                async with self.bot.session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        av_raw = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                        av_raw = av_raw.resize((ar*2, ar*2))
                        
                        # Apply rounded square mask
                        av_mask = Image.new("L", (ar*2, ar*2), 0)
                        av_mask_draw = ImageDraw.Draw(av_mask)
                        av_mask_draw.rounded_rectangle((0, 0, ar*2, ar*2), radius=int(ar*0.3), fill=255)
                        
                        avatar_img = Image.new("RGBA", (ar*2, ar*2))
                        avatar_img.paste(av_raw, (0, 0), av_mask)
            except Exception as e:
                self.logger.error(f"Error downloading avatar: {str(e)}")
            
            if avatar_img:
                # Add a subtle dark glow behind avatar
                shadow_rect = [ax-4, ay-4, ax+ar*2+4, ay+ar*2+4]
                try:
                    draw.rounded_rectangle(shadow_rect, radius=int(ar*0.3), fill=(0,0,0,100))
                except:
                    pass
                img.paste(avatar_img, (ax, ay), avatar_img)
            
            # Draw semi-transparent box for text
            box_x, box_y = ax + ar * 2 + int(WIDTH * 0.05), int(HEIGHT * 0.3)
            box_w, box_h = int(WIDTH * 0.9) - box_x, int(HEIGHT * 0.4)
            
            try:
                # Try rounded rectangle box
                overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
                ImageDraw.Draw(overlay).rounded_rectangle([box_x, box_y, box_x+box_w, box_y+box_h], radius=int(HEIGHT*0.05), fill=(20, 20, 25, 180))
                img.paste(overlay, (0,0), overlay)
            except:
                pass
            
            # Text placing
            text_x = box_x + box_w // 2
            
            display_name = member.display_name
            username_txt = f"@{member.name}"
            
            # Adjust title for Leave
            if not is_welcome:
                display_name = f"Farewell, {display_name}"
            
            # Name
            draw.text((text_x, box_y + box_h // 2 - int(10*scale_factor)), display_name, fill=(255, 255, 255), font=title_font, anchor="mb")
            
            # Username
            draw.text((text_x, box_y + box_h // 2 + int(10*scale_factor)), username_txt, fill=(180, 190, 200), font=sub_font, anchor="mt")
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            filename = "welcome_card.png" if is_welcome else "leave_card.png"
            return discord.File(buffer, filename=filename)
            
        except Exception as e:
            self.logger.error(f"Error generating welcome card: {str(e)}")
            return None
