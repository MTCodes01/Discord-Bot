from PIL import Image, ImageDraw, ImageFont
import math

def test_wavy_card():
    WIDTH, HEIGHT = 800, 250
    
    img = Image.new('RGBA', (WIDTH, HEIGHT), color=(10, 12, 16, 255))
    draw = ImageDraw.Draw(img)
    
    # Draw waves
    def draw_wave(draw_obj, w, h, base_y, amplitude, period, phase, fill):
        points = [(0, h)]
        for x in range(w + 1):
            # phase is offset in x
            y = base_y + math.sin((x + phase) * 2 * math.pi / period) * amplitude
            points.append((x, y))
        points.append((w, h))
        draw_obj.polygon(points, fill=fill)
        
    # Layer 1 (Dark gradient base for waves, we just use solid for now)
    draw_wave(draw, WIDTH, HEIGHT, base_y=80, amplitude=40, period=600, phase=0, fill=(40, 20, 80, 255))
    draw_wave(draw, WIDTH, HEIGHT, base_y=120, amplitude=50, period=700, phase=150, fill=(60, 30, 120, 255))
    draw_wave(draw, WIDTH, HEIGHT, base_y=160, amplitude=40, period=500, phase=300, fill=(80, 40, 160, 255))
    
    # In the provided image, the waves don't cover the entire bottom, they kind of fill the right side and background.
    # Actually, let's just make the left side dark for the avatar.
    # Or just leave the left side with a soft dark fading polygon.
    draw.rectangle([(0, 0), (250, HEIGHT)], fill=(15, 18, 22, 255))
    # Draw an arc to smooth the transition!
    draw.ellipse([(150, -100), (350, HEIGHT+100)], fill=(15, 18, 22, 255))
    
    # Avatar
    avatar_radius = 80
    avatar_x, avatar_y = 40, HEIGHT // 2 - avatar_radius
    
    avatar_img = Image.new("RGBA", (avatar_radius*2, avatar_radius*2), color=(100, 100, 100, 255))
    mask = Image.new("L", (avatar_radius*2, avatar_radius*2), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_radius*2, avatar_radius*2), fill=255)
    circle_avatar = Image.new("RGBA", (avatar_radius*2, avatar_radius*2))
    circle_avatar.paste(avatar_img, (0, 0), mask)
    
    # Draw avatar stroke
    stroke_w = 4
    draw.ellipse(
        (avatar_x - stroke_w, avatar_y - stroke_w, 
         avatar_x + avatar_radius*2 + stroke_w, avatar_y + avatar_radius*2 + stroke_w),
        fill=(200, 200, 200)
    )
    img.paste(circle_avatar, (avatar_x, avatar_y), circle_avatar)
    
    # Top text: Username
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        label_font = ImageFont.truetype("arial.ttf", 18)
        lbl_md_font = ImageFont.truetype("arial.ttf", 26)
        val_font = ImageFont.truetype("arial.ttf", 18)
    except:
        title_font = ImageFont.load_default()
        label_font = ImageFont.load_default()
        lbl_md_font = ImageFont.load_default()
        val_font = ImageFont.load_default()
        
    draw.text((320, 30), "not_meackermann", fill=(255, 255, 255), font=title_font)
    
    # Row 1: Text
    row1_y = 90
    draw.text((280, row1_y), "LVL\n12", fill=(255, 255, 255), font=label_font)
    # Chat icon mock
    draw.rectangle([(320, row1_y+5), (340, row1_y+20)], fill=(200, 200, 200))
    
    draw.text((380, row1_y+5), "Rank: #1", fill=(220, 220, 220), font=label_font)
    draw.text((680, row1_y+5), "Total: 5518", fill=(220, 220, 220), font=label_font)
    
    # Bar
    bar_w = 380
    bar_h = 24
    bx = 380
    by = row1_y + 25
    draw.rounded_rectangle([(bx, by), (bx+bar_w, by+bar_h)], radius=12, fill=(40, 40, 40, 200), outline=(150, 150, 150), width=2)
    # Filling
    prog = int(bar_w * 0.6)
    draw.rounded_rectangle([(bx+2, by+2), (bx+prog-2, by+bar_h-2)], radius=10, fill=(150, 100, 200, 255))
    draw.text((bx + bar_w//2, by + bar_h//2), "518 / 878", fill=(255, 255, 255), anchor="mm")
    
    # Row 2: Voice
    row2_y = 170
    draw.text((280, row2_y), "LVL\n23", fill=(255, 255, 255), font=label_font)
    draw.ellipse([(325, row2_y+5), (335, row2_y+20)], fill=(200, 200, 200)) # mic mock
    
    draw.text((380, row2_y+5), "Rank: #5", fill=(220, 220, 220), font=label_font)
    draw.text((680, row2_y+5), "Total: 39860", fill=(220, 220, 220), font=label_font)
    
    by2 = row2_y + 25
    draw.rounded_rectangle([(bx, by2), (bx+bar_w, by2+bar_h)], radius=12, fill=(40, 40, 40, 200), outline=(150, 150, 150), width=2)
    prog2 = int(bar_w * 0.95)
    draw.rounded_rectangle([(bx+2, by2+2), (bx+prog2-2, by2+bar_h-2)], radius=10, fill=(150, 100, 200, 255))
    draw.text((bx + bar_w//2, by2 + bar_h//2), "3124 / 3264", fill=(255, 255, 255), anchor="mm")
    
    img.save("wavy_test.png")

if __name__ == "__main__":
    test_wavy_card()
