from PIL import Image, ImageDraw, ImageFont
import math
import random

def draw_halftone(draw, x_start, y_start, width, height, dot_color, dot_size=3, spacing=15):
    for x in range(x_start, x_start + width, spacing):
        for y in range(y_start, y_start + height, spacing):
            # Calculate distance from the center of the halftone region to fade out dots
            cx, cy = x_start + width//2, y_start + height//2
            dist = math.hypot(x - cx, y - cy)
            max_dist = math.hypot(width//2, height//2)
            alpha = max(0, 255 - int((dist / max_dist) * 255))
            if alpha > 20:
                color = dot_color[:3] + (alpha,)
                draw.ellipse([x, y, x+dot_size, y+dot_size], fill=color)

def test_mixed_card():
    WIDTH, HEIGHT = 800, 280
    
    themes = [
        # 1. Clean Light
        {"bg": (225, 230, 232, 255), "text_main": (50, 60, 70), "text_sec": (100, 110, 120), "accent": (74, 193, 224), "dots": (180, 185, 190, 255), "swoosh": (50, 60, 70, 200)},
        # 2. Sakura Pink
        {"bg": (250, 240, 245, 255), "text_main": (100, 50, 70), "text_sec": (150, 100, 120), "accent": (255, 130, 160), "dots": (230, 210, 220, 255), "swoosh": (255, 130, 160, 180)},
        # 3. Midnight Node
        {"bg": (20, 24, 32, 255), "text_main": (240, 245, 250), "text_sec": (150, 160, 170), "accent": (80, 220, 160), "dots": (40, 48, 60, 255), "swoosh": (80, 220, 160, 150)},
        # 4. Deep Violet
        {"bg": (15, 10, 25, 255), "text_main": (255, 255, 255), "text_sec": (180, 160, 200), "accent": (210, 100, 255), "dots": (40, 20, 60, 255), "swoosh": (210, 100, 255, 150)},
        # 5. Golden Onyx
        {"bg": (30, 30, 30, 255), "text_main": (250, 240, 220), "text_sec": (180, 170, 150), "accent": (255, 200, 80), "dots": (60, 60, 60, 255), "swoosh": (255, 200, 80, 180)}
    ]
    
    for i, theme in enumerate(themes):
        img = Image.new('RGBA', (WIDTH, HEIGHT), color=(0,0,0,0))
        draw = ImageDraw.Draw(img)
        
        # Rounded Base
        radius = 25
        try:
            draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=radius, fill=theme["bg"])
        except AttributeError:
            draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=theme["bg"])
            
        # FX Layer (Halftones & Swooshes)
        fx_layer = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
        fx_draw = ImageDraw.Draw(fx_layer)
        draw_halftone(fx_draw, WIDTH - 250, -50, 350, 250, theme["dots"], dot_size=4, spacing=15)
        draw_halftone(fx_draw, -50, HEIGHT - 200, 300, 250, theme["dots"], dot_size=4, spacing=15)
        
        fx_draw.ellipse([(-100, HEIGHT - 150), (WIDTH + 300, HEIGHT + 400)], outline=theme["swoosh"], width=2)
        fx_draw.ellipse([(200, -300), (WIDTH + 400, HEIGHT // 2 + 50)], outline=theme["swoosh"], width=1)
        fx_draw.ellipse([(-200, -100), (WIDTH // 2 + 100, HEIGHT + 100)], outline=theme["swoosh"][:3] + (50,), width=3)
        
        # Merge FX with crop
        mask = Image.new("L", (WIDTH, HEIGHT), 0)
        mask_draw = ImageDraw.Draw(mask)
        try:
            mask_draw.rounded_rectangle([(0, 0), (WIDTH, HEIGHT)], radius=radius, fill=255)
        except AttributeError:
            mask_draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=255)
        
        img.paste(fx_layer, (0, 0), mask)
        
        # Sidebar Overlay (darkens/lightens left side for avatar)
        sb = Image.new('RGBA', (WIDTH, HEIGHT), (0,0,0,0))
        ImageDraw.Draw(sb).ellipse([(-100, -100), (320, HEIGHT+100)], fill=(0,0,0,60))
        img.paste(sb, (0,0), sb)
        
        # Fonts
        try:
            title_font = ImageFont.truetype("arialbd.ttf", 36)
            label_font = ImageFont.truetype("arial.ttf", 16)
            num_font = ImageFont.truetype("arialbd.ttf", 26)
            info_font = ImageFont.truetype("arial.ttf", 14)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            num_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
            
        # Avatar
        ar = 90
        ax, ay = 50, HEIGHT//2 - ar
        av = Image.new("RGBA", (ar*2, ar*2), (100,100,150,255))
        m2 = Image.new("L", (ar*2, ar*2), 0)
        ImageDraw.Draw(m2).ellipse((0,0,ar*2,ar*2), fill=255)
        cav = Image.new("RGBA", (ar*2, ar*2))
        cav.paste(av, (0,0), m2)
        
        draw.ellipse((ax-3, ay-3, ax+ar*2+3, ay+ar*2+3), outline=theme["accent"], width=3)
        img.paste(cav, (ax, ay), cav)
        
        # Username
        draw.text((280, 20), "HILLARYLINK", fill=theme["accent"], font=title_font)
        
        def draw_stat_row(draw_obj, base_y, level, is_text, rank, total, curr, req):
            # LVL
            draw_obj.text((280, base_y), "LVL", fill=theme["text_sec"], font=label_font, anchor="mm")
            draw_obj.text((280, base_y+20), str(level), fill=theme["text_main"], font=num_font, anchor="mm")
            
            # Icons
            icon_x = 315
            icon_y = base_y - 2
            icon_col = theme["text_sec"]
            if is_text:
                draw_obj.rounded_rectangle([(icon_x, icon_y), (icon_x+20, icon_y+14)], radius=3, fill=icon_col)
                draw_obj.polygon([(icon_x+4, icon_y+14), (icon_x+8, icon_y+14), (icon_x+4, icon_y+18)], fill=icon_col)
            else:
                draw_obj.rounded_rectangle([(icon_x+6, icon_y), (icon_x+12, icon_y+10)], radius=3, fill=icon_col)
                draw_obj.arc([(icon_x+4, icon_y+3), (icon_x+14, icon_y+13)], start=0, end=180, fill=icon_col, width=2)
                draw_obj.line([(icon_x+9, icon_y+13), (icon_x+9, icon_y+17)], fill=icon_col, width=2)
                draw_obj.line([(icon_x+5, icon_y+17), (icon_x+13, icon_y+17)], fill=icon_col, width=2)
                
            # Info text
            bar_x = 350
            draw_obj.text((bar_x, base_y-6), f"Rank: #{rank}", fill=theme["text_sec"], font=info_font)
            draw_obj.text((760, base_y-6), f"Total: {total}", fill=theme["text_sec"], font=info_font, anchor="ra")
            
            # Progress bar
            bar_w = 410
            bar_h = 16
            bar_y = base_y + 10
            bar_radius = 8
            
            draw_obj.rounded_rectangle([(bar_x, bar_y), (bar_x+bar_w, bar_y+bar_h)], radius=bar_radius, fill=theme["swoosh"][:3]+(50,))
            
            pct = min(1.0, max(0.0, curr / req))
            prog = int(bar_w * pct)
            if prog > bar_radius * 2:
                draw_obj.rounded_rectangle([(bar_x, bar_y), (bar_x+prog, bar_y+bar_h)], radius=bar_radius, fill=theme["accent"])
                
            # Center text inside bar
            text_col = (255,255,255) if pct < 0.5 and theme["bg"][0] < 128 else theme["text_main"] if pct >= 0.5 else theme["text_sec"]
            # To be simple: let's use text_main but maybe lightened/darkened based on theme
            if theme["bg"][0] < 128:
                draw_obj.text((bar_x + bar_w//2, bar_y + bar_h//2), f"{curr} / {req}", fill=(255,255,255), font=info_font, anchor="mm")
            else:
                draw_obj.text((bar_x + bar_w//2, bar_y + bar_h//2), f"{curr} / {req}", fill=(0,0,0), font=info_font, anchor="mm")

        # Draw Text Row
        draw_stat_row(draw, 100, 16, True, 1, 3300, 2230, 3300)
        
        # Draw Voice Row
        draw_stat_row(draw, 190, 5, False, 4968, 1200, 400, 1800)
        
        img.save(f"mixed_test_{i}.png")
        
if __name__ == "__main__":
    test_mixed_card()
