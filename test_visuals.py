import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Mocking the logic from video_gen.py to test visuals locally without moviepy dependency if possible,
# but we need to verify the actual video_gen functions.
# So we will import from video_gen.

from video_gen import get_font_path, draw_centered_text, get_text_layout, create_bg_clip

def test_visual_generation():
    print("Testing Visual Generation Logic...")
    
    # 1. Setup Background
    bg_path = "assets/background_black.png"
    if not os.path.exists(bg_path):
        print(f"Creating dummy background at {bg_path}")
        img = Image.new('RGB', (1280, 720), color=(50, 50, 50))
        img.save(bg_path)
    
    bg_img = Image.open(bg_path).convert('RGB').resize((1280, 720))
    
    # 2. Test Text Drawing with Shadow/Stroke
    draw = ImageDraw.Draw(bg_img)
    font_path = get_font_path()
    if not font_path:
        print("Warning: Noto Sans JP not found, using default.")
        font = ImageFont.load_default()
    else:
        print(f"Using Font: {font_path}")
        try:
            font = ImageFont.truetype(font_path, 50)
        except:
            font = ImageFont.load_default()
            
    # Test Case 1: Short Text
    draw_centered_text(draw, "Short Text Test", font, start_y=100, color="white")
    
    # Test Case 2: Long Text (Wrapping)
    long_text = "This is a very long text that should wrap automatically at 85% of the screen width. It needs to be readable with a shadow."
    draw_centered_text(draw, long_text, font, start_y=200, color="yellow")
    
    # Test Case 3: Japanese Text
    jp_text = "これは日本語のテストです。画面幅の85%で自動的に改行されるべきです。影も付いているはずです。"
    draw_centered_text(draw, jp_text, font, start_y=400, color="cyan")
    
    # Test Case 4: Highlight (Brackets)
    highlight_text = "The [highlighted] word should be gold."
    # Note: The draw_centered_text logic handles brackets coloring if implemented
    draw_centered_text(draw, highlight_text, font, start_y=600, color="white", highlight_words=["highlighted"])

    output_img = "temp/test_visual_output.png"
    if not os.path.exists("temp"): os.makedirs("temp")
    bg_img.save(output_img)
    print(f"Saved visual test to {output_img}")

if __name__ == "__main__":
    test_visual_generation()
