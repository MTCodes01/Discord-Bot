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
                        
                        # Apply circular mask instead of rounded square
                        av_mask = Image.new("L", (ar*2, ar*2), 0)
                        av_mask_draw = ImageDraw.Draw(av_mask)
                        av_mask_draw.ellipse((0, 0, ar*2, ar*2), fill=255)
                        
                        avatar_img = Image.new("RGBA", (ar*2, ar*2))
                        avatar_img.paste(av_raw, (0, 0), av_mask)
                        
                        # Draw aesthetic white ring
                        ring_width = max(2, int(HEIGHT * 0.015))
                        ImageDraw.Draw(avatar_img).ellipse((ring_width//2, ring_width//2, ar*2 - ring_width//2, ar*2 - ring_width//2), outline=(255,255,255,255), width=ring_width)
            except Exception as e:
                self.logger.error(f"Error downloading avatar: {str(e)}")
            
            if avatar_img:
                img.paste(avatar_img, (ax, ay), avatar_img)
            
            # Positioning for text without the bulky box
            box_x, box_y = ax + ar * 2 + int(WIDTH * 0.05), int(HEIGHT * 0.3)
            box_w, box_h = int(WIDTH * 0.9) - box_x, int(HEIGHT * 0.4)
            text_x = box_x + box_w // 2
            
            display_name = member.display_name
            username_txt = f"@{member.name}"
            
            # Adjust title for Leave
            if not is_welcome:
                display_name = f"Farewell, {display_name}"
            
            # Helper for text drop shadow
            def draw_text_shadow(d, text, x, y, font, anchor, main_color, shadow_color=(0,0,0,230), offset=max(2, int(scale_factor*4))):
                d.text((x + offset, y + offset), text, fill=shadow_color, font=font, anchor=anchor)
                d.text((x, y), text, fill=main_color, font=font, anchor=anchor)

            # Name
            draw_text_shadow(draw, display_name, text_x, box_y + box_h // 2 - int(10*scale_factor), title_font, "mb", (255, 255, 255))
            
            # Username
            draw_text_shadow(draw, username_txt, text_x, box_y + box_h // 2 + int(10*scale_factor), sub_font, "mt", (220, 230, 240))
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            filename = "welcome_card.png" if is_welcome else "leave_card.png"
            return discord.File(buffer, filename=filename)
            
        except Exception as e:
            self.logger.error(f"Error generating welcome card: {str(e)}")
            return None
