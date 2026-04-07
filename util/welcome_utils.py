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
                
            # Scale variables
            scale_factor = min(WIDTH / 800, HEIGHT / 300)
            
            ar = int(HEIGHT * 0.3)
            ax, ay = int(WIDTH * 0.12), HEIGHT // 2 - ar  # Moved further left
            
            # Download avatar
            avatar_img = None
            try:
                avatar_url = member.display_avatar.url
                async with self.bot.session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        av_raw = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
                        av_raw = av_raw.resize((ar*2, ar*2))
                        
                        # Apply precise circular mask
                        av_mask = Image.new("L", (ar*2, ar*2), 0)
                        av_mask_draw = ImageDraw.Draw(av_mask)
                        av_mask_draw.ellipse((0, 0, ar*2, ar*2), fill=255)
                        
                        avatar_img = Image.new("RGBA", (ar*2, ar*2))
                        avatar_img.paste(av_raw, (0, 0), av_mask)
                        
                        # Draw ethereal radial aura with smoother fade-out
                        aura = Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0))
                        aura_draw = ImageDraw.Draw(aura)
                        aura_radius = int(ar * 1.8)
                        for i in range(40):
                            r = int(ar + (aura_radius - ar) * i / 40)
                            # Softer edge fade
                            alpha = int(40 * (1 - (i / 40)**1.5))
                            if alpha > 0:
                                aura_draw.ellipse((ax + ar - r, ay + ar - r, ax + ar + r, ay + ar + r), fill=(255, 255, 255, alpha))
                        img.paste(aura, (0,0), aura)
                        
                        # rim is removed per user's preference
                        
            except Exception as e:
                self.logger.error(f"Error downloading avatar: {str(e)}")
            
            if avatar_img:
                img.paste(avatar_img, (ax, ay), avatar_img)
            
            # Text placing - increase offset to avoid overlap
            text_x = ax + ar*2 + int(WIDTH * 0.22)
            text_y = HEIGHT // 2
            
            display_name = member.display_name
            username_txt = f"@{member.name}"
            greeting_txt = "WELCOME" if is_welcome else "FAREWELL"
            
            # Helper for text drop shadow
            def draw_text_shadow(d, text, x, y, font, anchor, main_color, shadow_color=(0,0,0,230), offset=max(2, int(scale_factor*3))):
                d.text((x + offset, y + offset), text, fill=shadow_color, font=font, anchor=anchor)
                d.text((x, y), text, fill=main_color, font=font, anchor=anchor)

            # Load special tiny font for header
            def load_font(font_names, size):
                for name in font_names:
                    try:
                        return ImageFont.truetype(name, size)
                    except Exception:
                        continue
                return ImageFont.load_default()
                
            header_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], int(20 * scale_factor))
            title_font = load_font(["arialbd.ttf", "LiberationSans-Bold.ttf"], int(46 * scale_factor))
            sub_font = load_font(["arial.ttf", "LiberationSans-Regular.ttf"], int(24 * scale_factor))

            # Greeting
            draw_text_shadow(draw, greeting_txt, text_x, text_y - int(28*scale_factor), header_font, "mb", (245, 195, 105)) # Golden accent
            
            # Name
            if len(display_name) > 16:
                display_name = display_name[:14] + '...'
            draw_text_shadow(draw, display_name, text_x, text_y + int(10*scale_factor), title_font, "mb", (255, 255, 255))
            
            # Username
            draw_text_shadow(draw, username_txt, text_x, text_y + int(18*scale_factor), sub_font, "mt", (200, 210, 220))
            
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            filename = "welcome_card.png" if is_welcome else "leave_card.png"
            return discord.File(buffer, filename=filename)
            
        except Exception as e:
            self.logger.error(f"Error generating welcome card: {str(e)}")
            return None
