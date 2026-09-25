"""単語帳の「3秒クイズ」ショート（縦 1080x1920）を作る。

1本 = 5語。英単語を見せて読み上げ → 3・2・1 → 訳を出して読み上げ。
最後に「何問言えた？」でコメントを促し、聞き流し動画へ誘導する。
単語帳の CSV だけで作れるので、AI も手作業も要らない。

  python shorts_quiz.py --book t1900 --start 1 --shorts 4
      → No.1-5, 6-10, 11-15, 16-20 の4本
"""
from __future__ import annotations
import argparse, json, os, re, sys, tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (AudioFileClip, CompositeAudioClip, ImageClip,
                     concatenate_videoclips)

import audio_gen
import script_gen
from video_gen import FONT_PATH_BLACK, FONT_PATH_BOLD

W, H = 1080, 1920
# ショートは右端にボタン、下にタイトル・チャンネル名が重なる。
# 大事な文字は横 120〜960・縦 1500 より上に収める。
SAFE_W = 820
OUT_DIR = Path("output/shorts")
VOICE_EN = "en-US-ChristopherNeural"
VOICE_JP = "ja-JP-KeitaNeural"
TICK_SE = "assets/Accent08-1.mp3"
BLUE, YELLOW, GRAY = "#2060C0", "#FFD24A", "#AAAAAA"

BOOK_LABEL = {
    "t1200": "ターゲット1200", "t1400": "ターゲット1400", "t1900": "ターゲット1900",
    "teppeki": "鉄壁", "systan": "システム英単語", "derujun": "でる順準1級", "leap": "LEAP",
}


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def fit(draw, text, path, size, max_w, min_size=48):
    """幅に収まるまで字を小さくする。"""
    while size > min_size:
        f = font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 6
    return font(path, min_size)


def background() -> Image.Image:
    """横長の既存背景を縦に切り出す。同じ質感でチャンネルの統一感を出す。"""
    src = Image.open("assets/background_black.png").convert("RGB")
    scale = H / src.height
    src = src.resize((int(src.width * scale), H), Image.LANCZOS)
    x = (src.width - W) // 2
    return src.crop((x, 0, x + W, H))


def centered(draw, y, text, f, fill, stroke=0, stroke_fill="white"):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill,
              stroke_width=stroke, stroke_fill=stroke_fill)


def meanings_of(item: dict) -> list[str]:
    parts = [p.strip() for p in re.split(r"[、,，／/]", item["meaning"]) if p.strip()]
    return parts[:2] or [item["meaning"]]


class Frames:
    def __init__(self, book: str, total: int):
        self.bg = background()
        self.label = BOOK_LABEL.get(book, book)
        self.total = total
        logo = Image.open("assets/logo_kiai.png").convert("RGBA")
        s = 220 / logo.width
        self.logo = logo.resize((220, int(logo.height * s)), Image.LANCZOS)

    def base(self, idx: int | None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = self.bg.copy()
        img.paste(self.logo, ((W - self.logo.width) // 2, 70), self.logo)
        d = ImageDraw.Draw(img)
        centered(d, 330, f"【{self.label}】", fit(d, f"【{self.label}】", FONT_PATH_BLACK, 76, SAFE_W), YELLOW)
        centered(d, 440, "3秒で意味を言えるか？", font(FONT_PATH_BOLD, 60), "white")
        if idx is not None:
            centered(d, 560, f"{idx + 1} / {self.total}", font(FONT_PATH_BOLD, 44), GRAY)
        return img, d

    def word(self, idx: int, item: dict, count: int | None = None,
             meanings: list[str] | None = None) -> np.ndarray:
        img, d = self.base(idx)
        f = fit(d, item["word"], FONT_PATH_BLACK, 170, SAFE_W, 80)
        centered(d, 760, item["word"], f, BLUE, stroke=5)
        if count is not None:
            centered(d, 1060, str(count), font(FONT_PATH_BLACK, 200), YELLOW)
        if meanings:
            y = 1080
            for i, m in enumerate(meanings):
                line = f"{chr(0x2460 + i)} {m}" if len(meanings) > 1 else m
                centered(d, y, line, fit(d, line, FONT_PATH_BOLD, 84, SAFE_W), "white")
                y += 120
        centered(d, 1400, f"No.{item['id']:04d}", font(FONT_PATH_BOLD, 40), GRAY)
        return np.array(img)

    def end(self, first: int, last: int) -> np.ndarray:
        img, d = self.base(None)
        centered(d, 820, "何問言えた？", font(FONT_PATH_BLACK, 120), "white")
        centered(d, 1000, "コメントで教えて！", font(FONT_PATH_BOLD, 70), YELLOW)
        centered(d, 1200, f"No.{first}〜{last} の聞き流しは", font(FONT_PATH_BOLD, 48), GRAY)
        centered(d, 1270, "チャンネルの動画で", font(FONT_PATH_BOLD, 48), GRAY)
        return np.array(img)


def tts(text: str, voice: str, path: str) -> AudioFileClip:
    for _ in range(3):
        if audio_gen.generate_audio_segment_edge(text, voice, path):
            return AudioFileClip(path)
    raise RuntimeError(f"音声を作れませんでした: {text!r}")


def build_short(book: str, words: list[dict], out: Path) -> dict:
    fr = Frames(book, len(words))
    clips, audio, t = [], [], 0.0
    tick = AudioFileClip(TICK_SE) if os.path.exists(TICK_SE) else None

    with tempfile.TemporaryDirectory() as tmp:
        for i, w in enumerate(words):
            ms = meanings_of(w)
            en = tts(w["word"], VOICE_EN, f"{tmp}/en{i}.mp3")
            ja = tts(audio_gen.jp_reading("、".join(ms)), VOICE_JP, f"{tmp}/ja{i}.mp3")

            # 英単語を見せて読む（最短1秒）
            show = max(en.duration + 0.3, 1.0)
            audio.append(en.with_start(t + 0.15))
            clips.append(ImageClip(fr.word(i, w)).with_duration(show))
            t += show
            # 3・2・1
            for n in (3, 2, 1):
                if tick:
                    audio.append(tick.with_start(t).with_volume_scaled(0.5))
                clips.append(ImageClip(fr.word(i, w, count=n)).with_duration(1.0))
                t += 1.0
            # 答え
            ans = ja.duration + 0.7
            audio.append(ja.with_start(t + 0.1))
            clips.append(ImageClip(fr.word(i, w, meanings=ms)).with_duration(ans))
            t += ans

        clips.append(ImageClip(fr.end(words[0]["id"], words[-1]["id"])).with_duration(2.5))
        t += 2.5

        video = concatenate_videoclips(clips).with_audio(
            CompositeAudioClip(audio).with_duration(t))
        out.parent.mkdir(parents=True, exist_ok=True)
        video.write_videofile(str(out), fps=30, codec="libx264", audio_codec="aac",
                              audio_bitrate="192k", threads=4, logger=None)
        video.close()
    return {"duration": round(t, 1)}


def metadata(book: str, words: list[dict], long_url: str | None) -> dict:
    label = BOOK_LABEL.get(book, book)
    s, e = words[0]["id"], words[-1]["id"]
    answers = "\n".join(f"{w['word']} … {'、'.join(meanings_of(w))}" for w in words)
    desc = [f"{label} No.{s}〜{e} を3秒でチェック。何問言えたかコメントで教えてください。", "",
            "【答え】", answers, ""]
    if long_url:
        desc += [f"▶ {label} の聞き流しはこちら", long_url, ""]
    desc += [f"#{label.replace(' ', '')} #英単語 #大学受験 #shorts"]
    return {
        "title": f"【{label}】3秒で意味言える？ No.{s}〜{e} #shorts",
        "description": "\n".join(desc),
        "tags": [label, "英単語", "大学受験", "英単語クイズ", "shorts"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="単語帳の3秒クイズ・ショートを作る")
    ap.add_argument("--book", required=True, help=" / ".join(BOOK_LABEL))
    ap.add_argument("--start", type=int, required=True, help="最初の単語番号")
    ap.add_argument("--count", type=int, default=5, help="1本に入れる語数")
    ap.add_argument("--shorts", type=int, default=1, help="続けて何本作るか")
    ap.add_argument("--long-url", help="概要欄に載せる聞き流し動画のURL")
    a = ap.parse_args()

    end = a.start + a.count * a.shorts - 1
    script = script_gen.generate_word_audio_script(a.book, f"{a.start}-{end}")
    if not script:
        return 1
    all_words = script["words"]
    for k in range(a.shorts):
        words = all_words[k * a.count:(k + 1) * a.count]
        if not words:
            break
        s, e = words[0]["id"], words[-1]["id"]
        out = OUT_DIR / f"short_{a.book}_{s:04d}-{e:04d}.mp4"
        if out.exists():
            print(f"[{k + 1}/{a.shorts}] {out.name} は作成済み（スキップ）")
            continue
        print(f"[{k + 1}/{a.shorts}] No.{s}-{e} を生成中...")
        info = build_short(a.book, words, out)
        meta = metadata(a.book, words, a.long_url) | info
        out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
        print(f"   ✅ {out}（{info['duration']}秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
