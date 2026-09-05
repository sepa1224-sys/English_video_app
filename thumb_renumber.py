"""既存サムネイルの「No.○〜○」だけを描き替える。

同じ単語帳の別の範囲を作るとき、デザインを一から起こす必要はない。
番号の帯だけ塗りつぶして書き直せば、他の要素はそのまま使える。
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 単語帳ごとの「No.○〜○」の位置と見た目。
# 目盛りを引いた画像で実際の座標を読み取った値。
LAYOUTS = {
    "teppeki": {"box": (530, 0, 1280, 128), "fill": (10, 12, 40),
                "color": (255, 255, 255), "outline": (0, 0, 0), "size": 82},
    "t1900":   {"box": (60, 175, 700, 290), "fill": (38, 74, 158),
                "color": (255, 255, 255), "outline": (0, 0, 0), "size": 92},
    # LEAP: 「1〜500」が黄色＋黒縁で中央左。背景は白っぽい紙
    "leap":    {"box": (20, 380, 760, 570), "fill": (252, 250, 245),
                "color": (255, 210, 60), "outline": (40, 30, 10), "size": 104,
                "prefix": ""},
    # ターゲット1400: 「1〜500」が金色で「完全網羅」の下。背景は濃い緑
    "t1400":   {"box": (30, 592, 700, 695), "fill": (10, 34, 16),
                "color": (255, 220, 90), "outline": (20, 15, 5), "size": 76,
                "prefix": ""},
    # システム英単語: 「No.1〜500」が白＋黒縁。背景は青
    "systan":  {"box": (590, 372, 1250, 488), "fill": (60, 100, 152),
                "color": (255, 255, 255), "outline": (0, 0, 0), "size": 78},
}


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in ("assets/fonts/NotoSansCJKjp-Black.otf",
              "assets/fonts/NotoSansCJKjp-Bold.otf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def renumber(src: Path, dst: Path, book: str, start: int, end: int) -> Path:
    if book not in LAYOUTS:
        raise SystemExit(f"{book} の配置が未定義です。使えるのは: {', '.join(LAYOUTS)}")
    L = LAYOUTS[book]
    img = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(img)

    x0, y0, x1, y1 = L["box"]
    # 元の背景色で塗りつぶしてから書き直す
    d.rectangle([x0, y0, x1, y1], fill=L["fill"])

    text = f'{L.get("prefix", "No.")}{start}〜{end}'
    size = L["size"]
    while size > 30:
        f = font(size)
        w = d.textbbox((0, 0), text, font=f)[2]
        h = d.textbbox((0, 0), text, font=f)[3]
        if w <= (x1 - x0) - 20:
            break
        size -= 4
    f = font(size)
    bb = d.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = x0 + ((x1 - x0) - tw) // 2 - bb[0]
    ty = y0 + ((y1 - y0) - th) // 2 - bb[1]

    if L["outline"]:
        for ox in range(-4, 5):
            for oy in range(-4, 5):
                if ox or oy:
                    d.text((tx + ox, ty + oy), text, font=f, fill=L["outline"])
    d.text((tx, ty), text, font=f, fill=L["color"])
    img.save(dst, quality=95)
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description="サムネイルの番号を描き替える")
    ap.add_argument("--src", required=True, help="元にするサムネイル")
    ap.add_argument("--out", required=True)
    ap.add_argument("--book", required=True, choices=sorted(LAYOUTS))
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    a = ap.parse_args()
    p = renumber(Path(a.src), Path(a.out), a.book, a.start, a.end)
    print(f"✅ {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
