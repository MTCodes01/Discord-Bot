from PIL import Image, ImageDraw, ImageFont
import random

def test_rank_card():
    accent_color = (114, 137, 218)
    themes = [
        # 1. Modern Dark
        {
            "bg": (30, 33, 36, 255),
            "text_main": (255, 255, 255),
            "text_sec": (180, 180, 180),
            "bar_bg": (60, 60, 60),
            "bar_fg": accent_color,
            "accent": accent_color
        },
        # 2. Neon Nights
        {
            "bg": (15, 15, 30, 255),
            "text_main": (0, 255, 255),
            "text_sec": (255, 0, 255),
            "bar_bg": (40, 20, 50),
            "bar_fg": (0, 255, 255),
            "accent": (255, 0, 255)
        },
        # 3. Midnight Gradient
        {
            "bg": (25, 10, 40, 255),
            "text_main": (255, 255, 255),
            "text_sec": (200, 150, 255),
            "bar_bg": (40, 20, 60),
            "bar_fg": (255, 200, 0),
            "accent": (255, 200, 0)
        },
        # 4. Minimalist Light
        {
            "bg": (240, 240, 245, 255),
            "text_main": (30, 30, 30),
            "text_sec": (100, 100, 100),
            "bar_bg": (210, 210, 215),
            "bar_fg": accent_color,
            "accent": accent_color
        }
    ]
    
    # Generate one image per theme
    for i, theme in enumerate(themes):
        WIDTH, HEIGHT = 800, 250
        
        img = Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        radius = 20
        try:
            draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=radius, fill=theme["bg"])
        except AttributeError:
            draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=theme["bg"])
            
        try:
            name_font = ImageFont.truetype("arial.ttf", 40)
            level_font = ImageFont.truetype("arial.ttf", 36)
            info_font = ImageFont.truetype("arial.ttf", 26)
        except Exception:
            name_font = ImageFont.load_default()
            level_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
            
        avatar_size = 180
        avatar_x, avatar_y = 35, 35
        # fake avatar
        avatar_img = Image.new("RGBA", (avatar_size, avatar_size), color=(100, 100, 100, 255))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
        circle_avatar = Image.new("RGBA", (avatar_size, avatar_size))
        circle_avatar.paste(avatar_img, (0, 0), mask)
        avatar_img = circle_avatar
        
        stroke_width = 6
        draw.ellipse(
            (avatar_x - stroke_width, avatar_y - stroke_width, 
             avatar_x + avatar_size + stroke_width, avatar_y + avatar_size + stroke_width),
            fill=theme["accent"]
        )
        
        img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
        
        draw.text((250, 45), "TestUser99", fill=theme["text_main"], font=name_font)
        draw.text((250, 95), "Level 12", fill=theme["accent"], font=level_font)
        draw.text((450, 95), "Rank #5", fill=theme["text_sec"], font=level_font)
        
        xp_text = "XP: 1500 / 500 of 2000 to next level"
        draw.text((250, 145), xp_text, fill=theme["text_sec"], font=info_font)
        
        bar_width = 510
        bar_height = 30
        bar_x = 250
        bar_y = 185
        radius_bar = 15
        
        try:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)], radius=radius_bar, fill=theme["bar_bg"])
        except AttributeError:
            draw.rectangle([(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)], fill=theme["bar_bg"])
            
        progress_width = int(bar_width * (75.5 / 100))
        progress_width = max(progress_width, radius_bar * 2) if progress_width > 0 else 0
        try:
            draw.rounded_rectangle([(bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height)], radius=radius_bar, fill=theme["bar_fg"])
        except AttributeError:
            draw.rectangle([(bar_x, bar_y), (bar_x + progress_width, bar_y + bar_height)], fill=theme["bar_fg"])
            
        percent_text = "75.5%"
        text_x = bar_x + (bar_width // 2)
        if hasattr(draw, 'textlength'):
            draw.text((text_x, bar_y + (bar_height // 2) - 2), percent_text, fill=theme["text_main"], font=info_font, anchor="mm")
        else:
            draw.text((text_x, bar_y), percent_text, fill=theme["text_main"], font=info_font, anchor="mt")
            
        img.save(f"test_theme_{i}.png")
        print(f"Saved test_theme_{i}.png")

if __name__ == '__main__':
    test_rank_card()
