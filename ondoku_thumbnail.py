"""YouTube サムネイルを組む。

AI 画像は日本語文字を崩すため、絵だけ生成させて文字はここで描く。
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

import ondoku_render as R

W, H = 1280, 720
INK = (38, 34, 30)
ACCENT = (206, 63, 62)      # 差し色（教材バッジ）
SUB = (92, 84, 74)


def _fit(img: Image.Image, zoom: float = 1.0, shift_x: float = 0.0) -> Image.Image:
    """16:9 に切り出して 1280x720 にする。

    zoom    : 1より大きいほど被写体が大きく写る
    shift_x : 正の値で被写体が右へ寄る（切り出し窓を左へずらす）
    """
    src = img.convert("RGB")
    sw, sh = src.size
    scale = max(W / sw, H / sh) * zoom
    src = src.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    x = int((src.width - W) / 2 - shift_x * W)
    y = (src.height - H) // 2
    x = max(0, min(x, src.width - W))
    y = max(0, min(y, src.height - H))
    return src.crop((x, y, x + W, y + H))


def _shrink_to_fit(text: str, path: str, start: int, max_w: int, floor: int = 22):
    """max_w に収まるまで字を小さくする。"""
    size = start
    while size > floor:
        f = R._font(path, size)
        if ImageDraw.Draw(Image.new("RGB", (10, 10))).textbbox((0, 0), text, font=f)[2] <= max_w:
            return f
        size -= 2
    return R._font(path, floor)


def _level_list(d, items, x, y, font):
    """レベル表記を縦に並べる。囲みは付けない。"""
    for it in items:
        d.text((x, y), it, font=font, fill=SUB)
        y += font.size + 12
    return y


def build(base_path: Path, out: Path, title_ja: str, title_en: str,
          badge: str, level: str, zoom: float = 1.0, shift_x: float = 0.0) -> Path:
    img = _fit(Image.open(base_path), zoom, shift_x)

    # 左側に白いベールをかけて文字を読ませる。
    # 縦の境目が出ないよう、左端から右へなめらかに薄れる勾配にする。
    A0, HOLD, FADE = 198, 0.34, 0.70   # 最大濃度 / ここまで保つ / ここで消える
    mask = Image.new("L", (W, 1))
    px = mask.load()
    for x in range(W):
        r = x / W
        if r <= HOLD:
            a = 1.0
        elif r >= FADE:
            a = 0.0
        else:
            t = (r - HOLD) / (FADE - HOLD)
            a = 1 - t * t * (3 - 2 * t)      # smoothstep
        px[x, 0] = int(A0 * a)
    mask = mask.resize((W, H))
    veil = Image.new("RGBA", (W, H), (255, 252, 245, 0))
    veil.putalpha(mask)
    img = Image.alpha_composite(img.convert("RGBA"), veil).convert("RGB")

    d = ImageDraw.Draw(img)
    x, MAXW = 62, 700          # 文字を置ける横幅
    f_badge = R._font(R.F_BOLD, 42)
    f_ja = R._font(R.F_BOLD, 34)
    f_lv = R._font(R.F_BOLD, 23)

    # --- 教材バッジ ---
    BH = 68
    bw = d.textbbox((0, 0), badge, font=f_badge)[2] + 52
    d.rounded_rectangle([x, 50, x + bw, 50 + BH], radius=BH // 2, fill=ACCENT)
    d.text((x + 26, 50 + 12), badge, font=f_badge, fill=(255, 255, 255))

    # --- 英語タイトル（主役。行ごとに幅へ合わせて縮める） ---
    y = 158
    en_lines = title_en.split("\n")
    fonts = [_shrink_to_fit(l, R.F_BLACK, 72, MAXW) for l in en_lines]
    size = min(f.size for f in fonts)
    for line in en_lines:
        f = R._font(R.F_BLACK, size)
        d.text((x + 3, y + 3), line, font=f, fill=(0, 0, 0, 60))
        d.text((x, y), line, font=f, fill=INK)
        y += int(size * 1.16)

    # --- 日本語タイトル（副） ---
    y += 10
    for line in title_ja.split("\n"):
        f = _shrink_to_fit(line, R.F_BOLD, 34, MAXW)
        d.text((x, y), line, font=f, fill=SUB)
        y += f.size + 8

    # --- レベル表記 ---
    y += 26
    d.line([x, y, x + 108, y], fill=ACCENT, width=5)
    items = [t.strip() for t in level.replace("｜", "/").split("/") if t.strip()]
    _level_list(d, items, x, y + 22, f_lv)

    img.save(out, quality=95)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="サムネイルを組む")
    ap.add_argument("--base", required=True, help="AI生成した絵")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title-ja", required=True, help="改行は \\n")
    ap.add_argument("--title-en", required=True)
    ap.add_argument("--badge", default="1日5分 英語で聞く教養")
    ap.add_argument("--level", default="CEFR A2-B1 / 英検 準2級〜2級 / TOEIC 400-600",
                    help="スラッシュ区切り。それぞれ枠付きで並ぶ")
    ap.add_argument("--zoom", type=float, default=1.0, help="1より大きいと被写体が大きくなる")
    ap.add_argument("--shift-x", type=float, default=0.0, help="正で被写体が右へ寄る")
    a = ap.parse_args()
    p = build(Path(a.base), Path(a.out), a.title_ja.replace("\\n", "\n"),
              a.title_en.replace("\\n", "\n"), a.badge, a.level, a.zoom, a.shift_x)
    print(f"✅ {p} ({Image.open(p).size[0]}x{Image.open(p).size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
