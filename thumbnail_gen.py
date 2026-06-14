"""
Exam thumbnail generator.

Takes a fixed base thumbnail (e.g. the Todai gate image with the catch copy
already baked in) and overlays "Part N" in the bottom-left, matching the
existing channel style (bright green text with a thick black outline).
Only the number changes between videos.
"""
import os
from PIL import Image, ImageDraw, ImageFont

# Bundled bold font (handles JP+EN); falls back to a system font.
_FONT_CANDIDATES = [
    os.path.join("assets", "fonts", "NotoSansCJKjp-Black.otf"),
    os.path.join("assets", "fonts", "NotoSansCJKjp-Bold.otf"),
    "C:\\Windows\\Fonts\\arialbd.ttf",
]

# Rainbow palette, cycled by part number so each video differs from the previous.
# (part-1) % 7  ->  red, orange, yellow, green, blue, indigo, violet
RAINBOW = [
    (255, 59, 48),    # red
    (255, 149, 0),    # orange
    (255, 214, 10),   # yellow
    (45, 255, 60),    # green
    (10, 132, 255),   # blue
    (94, 92, 230),    # indigo (藍)
    (191, 90, 242),   # violet (紫)
]
OUTLINE = (0, 0, 0)          # black outline
OUTLINE_W = 9


def part_color(part_number: int):
    return RAINBOW[(int(part_number) - 1) % len(RAINBOW)]


def _font(size: int):
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def generate_exam_thumbnail(part_number: int, base_image_path: str, output_path: str,
                            label: str = "Part") -> str:
    """
    Draw "{label} {part_number}" (e.g. "Part 4") on the base image, bottom-left.
    Returns output_path, or raises if the base image is missing.
    """
    if not base_image_path or not os.path.exists(base_image_path):
        raise FileNotFoundError(f"Thumbnail base image not found: {base_image_path}")

    img = Image.open(base_image_path).convert("RGB").resize((1280, 720))
    draw = ImageDraw.Draw(img)

    text = f"{label}{part_number}"
    font = _font(120)
    color = part_color(part_number)

    # Bottom-left position with margin
    x = 45
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        th = bbox[3] - bbox[1]
        top_off = bbox[1]
    except Exception:
        th, top_off = 120, 0
    y = 720 - th - 60 - top_off

    # Thick black outline then green fill
    try:
        draw.text((x, y), text, font=font, fill=color,
                  stroke_width=OUTLINE_W, stroke_fill=OUTLINE)
    except TypeError:
        # Pillow without stroke support: manual outline
        for ox in range(-OUTLINE_W, OUTLINE_W + 1):
            for oy in range(-OUTLINE_W, OUTLINE_W + 1):
                if ox or oy:
                    draw.text((x + ox, y + oy), text, font=font, fill=OUTLINE)
        draw.text((x, y), text, font=font, fill=color)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path)
    return output_path


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    base = sys.argv[2] if len(sys.argv) > 2 else "assets/thumbnail_base_todai.png"
    out = sys.argv[3] if len(sys.argv) > 3 else f"thumb_part{n}.png"
    print(generate_exam_thumbnail(n, base, out))
