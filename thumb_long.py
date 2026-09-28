"""例文つき聞き流し・瞬間英作文の長尺動画のサムネイル（1280x720）。

単語帳の表紙やキャラクターは出版社のものなので使わず、文字と「中身の見本」で見せる。

  python3 thumb_long.py example --book t1900 --start 1 --end 250 --word estimate \\
      --sentence "Experts estimate the damage at ten million dollars." --out x.jpg
  python3 thumb_long.py phrase --set p001 --out y.jpg
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BLACK = "assets/fonts/NotoSansCJKjp-Black.otf"
BOLD = "assets/fonts/NotoSansCJKjp-Bold.otf"
YELLOW, RED, BLUE, WHITE, GRAY = "#FFD24A", "#E53935", "#2F6FE0", "#FFFFFF", "#BBBBBB"
BOOK_LABEL = {"t1200": "ターゲット1200", "t1400": "ターゲット1400", "t1900": "ターゲット1900",
              "teppeki": "鉄壁", "systan": "システム英単語", "derujun": "でる順準1級", "leap": "LEAP"}


def f(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def fit(d, text, path, size, max_w):
    while size > 24 and d.textlength(text, font=f(path, size)) > max_w:
        size -= 4
    return f(path, size)


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.open("assets/background_black.png").convert("RGB").resize((W, H))
    logo = Image.open("assets/logo_kiai.png").convert("RGBA")
    logo = logo.resize((150, int(logo.height * 150 / logo.width)), Image.LANCZOS)
    img.paste(logo, (W - 170, H - logo.height - 16), logo)
    return img, ImageDraw.Draw(img)


def badge(d, xy, text, size, bg, fg=WHITE):
    ft = f(BLACK, size)
    x, y = xy
    w = d.textlength(text, font=ft)
    d.rounded_rectangle([x, y, x + w + 40, y + size + 30], radius=14, fill=bg)
    d.text((x + 20, y + 6), text, font=ft, fill=fg)


def outlined(d, xy, text, ft, fill, stroke=6, stroke_fill="#000000"):
    d.text(xy, text, font=ft, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def example(book, start, end, word, sentence, out: Path):
    img, d = base()
    badge(d, (50, 40), "例文つき", 64, RED)
    label = BOOK_LABEL.get(book, book)
    outlined(d, (50, 170), label, fit(d, label, BLACK, 128, 760), WHITE)
    outlined(d, (56, 330), f"No.{start}〜{end}", f(BLACK, 96), YELLOW)
    # 右側：画面の見本（見出し語＋例文）
    d.rounded_rectangle([800, 190, 1240, 470], radius=20, fill="#15161c", outline="#444", width=3)
    ft = fit(d, word, BLACK, 76, 380)
    d.text((1020 - d.textlength(word, font=ft) / 2, 215), word, font=ft, fill=BLUE,
           stroke_width=3, stroke_fill=WHITE)
    fs = f(BOLD, 28)
    words, lines, cur = sentence.split(), [], ""
    for w_ in words:
        t = (cur + " " + w_).strip()
        if d.textlength(t, font=fs) > 390 and cur:
            lines.append(cur)
            cur = w_
        else:
            cur = t
    lines.append(cur)
    y = 330
    for ln in lines[:3]:
        d.text((1020 - d.textlength(ln, font=fs) / 2, y), ln, font=fs, fill=WHITE)
        y += 40
    d.text((50, 520), "英単語 → 訳 → 例文 → 和訳", font=f(BLACK, 54), fill=WHITE)
    d.text((50, 600), "聞き流しOK｜全{}語".format(end - start + 1), font=f(BOLD, 44), fill=GRAY)
    img.save(out, quality=92)
    return out


def phrase(set_id: str, out: Path, pick: int | None = None):
    data = json.loads(Path(f"data/phrases/{set_id}.json").read_text(encoding="utf-8"))
    img, d = base()
    badge(d, (50, 40), "瞬間英作文", 56, RED)
    hook = data.get("hook") or "それ、英語で言える？"
    outlined(d, (50, 150), hook, fit(d, hook, BLACK, 118, 1180), YELLOW)
    theme = data["theme"].replace("言えそうで言えない表現", "").strip("のでにをはが ")
    sub = f"{theme} {len(data['items'])}フレーズ"
    outlined(d, (50, 310), sub, fit(d, sub, BLACK, 80, 1180), WHITE, stroke=5)
    # 見本1つ（日本語→英語）。指定が無ければ短いものを選ぶ
    it = (data["items"][pick - 1] if pick else
          min(data["items"], key=lambda x: len(x["ja"]) + len(x["en"])))
    d.rounded_rectangle([50, 450, 1080, 640], radius=20, fill="#15161c", outline="#444", width=3)
    d.text((80, 470), it["ja"], font=fit(d, it["ja"], BOLD, 46, 960), fill=WHITE)
    # 答えは伏せる。「言える？」と問うサムネなので、見たくなる方が強い
    d.text((80, 545), "→ ？", font=f(BLACK, 64), fill=YELLOW)
    img.save(out, quality=92)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="kind", required=True)
    e = sub.add_parser("example")
    e.add_argument("--book", required=True)
    e.add_argument("--start", type=int, required=True)
    e.add_argument("--end", type=int, required=True)
    e.add_argument("--word", required=True)
    e.add_argument("--sentence", required=True)
    e.add_argument("--out", required=True)
    p = sub.add_parser("phrase")
    p.add_argument("--set", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--pick", type=int, help="見本に出す文の番号（1始まり）")
    a = ap.parse_args()
    if a.kind == "example":
        print(example(a.book, a.start, a.end, a.word, a.sentence, Path(a.out)))
    else:
        print(phrase(a.set, Path(a.out), a.pick))
    return 0


if __name__ == "__main__":
    sys.exit(main())
