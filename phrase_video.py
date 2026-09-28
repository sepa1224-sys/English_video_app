"""瞬間英作文の聞き流し動画（横 1280x720）を作る。

1文ごと: 日本語を表示して読む → 考える時間（バーが縮む） → 英語を表示して2回読む。
素材は phrase_gen.py が作る data/phrases/<set>.json。

25文ずつ小分けに書き出して無劣化でつなぐ（word_video_chunked.py と同じ理由：
一度に大量の音声を moviepy に渡すと ffmpeg が詰まる）。

  python3 phrase_video.py --set p001
  python3 phrase_video.py --set p001 --think 4     # 考える時間を4秒に
"""
from __future__ import annotations
import argparse, json, sys, tempfile, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (AudioClip, AudioFileClip, ImageClip, VideoClip,
                     concatenate_audioclips, concatenate_videoclips)

import audio_gen
from video_gen import FONT_PATH_BLACK, FONT_PATH_BOLD, _wrap_chars, _wrap_words
from word_video_chunked import concat

W, H = 1280, 720
OUT_DIR = Path("output/phrases")
VOICE_JP = "ja-JP-NanamiNeural"
VOICE_EN = "en-US-ChristopherNeural"
YELLOW, GRAY, BLUE = "#FFD24A", "#AAAAAA", "#2060C0"
BAR_STEPS = 12


def silence(d: float) -> AudioClip:
    return AudioClip(lambda t: np.zeros((len(t), 2)) if not np.isscalar(t) else np.zeros(2),
                     duration=d, fps=44100)


def tts(text: str, voice: str, path: str) -> AudioFileClip:
    for _ in range(3):
        if audio_gen.generate_audio_segment_edge(text, voice, path):
            return AudioFileClip(path)
        time.sleep(2)
    raise RuntimeError(f"音声を作れませんでした: {text!r}")


class Painter:
    def __init__(self, total: int):
        bg = Image.open("assets/background_black.png").convert("RGB").resize((W, H))
        logo = Image.open("assets/logo_kiai.png").convert("RGBA")
        s = 170 / logo.width
        logo = logo.resize((170, int(logo.height * s)), Image.LANCZOS)
        bg.paste(logo, (W - logo.width - 20, 16), logo)
        self.bg = bg
        self.total = total
        self.f_no = ImageFont.truetype(FONT_PATH_BOLD, 28)
        self.f_pt = ImageFont.truetype(FONT_PATH_BOLD, 30)

    def _center(self, d, y, text, f, fill, stroke=0):
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill=fill,
               stroke_width=stroke, stroke_fill="white")

    def frame(self, n: int, item: dict, bar: float | None, show_en: bool) -> np.ndarray:
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        d.text((40, 36), f"{n:03d} / {self.total}", font=self.f_no, fill=GRAY)
        # 型のヒントは答えを明かすので、英語を出してから見せる
        if show_en and item.get("point"):
            self._center(d, 560, f"― {item['point']} ―", self.f_pt, GRAY)

        # 日本語（上半分）
        size = 60
        while True:
            f = ImageFont.truetype(FONT_PATH_BOLD, size)
            lines = _wrap_chars(d, item["ja"], f, 1120)
            if len(lines) <= 2 or size <= 40:
                break
            size -= 4
        y = 190 if len(lines) == 1 else 165
        for ln in lines[:2]:
            self._center(d, y, ln, f, "white")
            y += size + 18

        if bar is not None and not show_en:
            # 考える時間。残り時間ぶんのバーを中央から縮める
            full = 700
            w = int(full * bar)
            x0 = (W - w) // 2
            d.rounded_rectangle([x0, 430, x0 + w, 446], radius=8, fill=YELLOW)
            self._center(d, 470, "英語で言ってみよう", ImageFont.truetype(FONT_PATH_BOLD, 34), GRAY)

        if show_en:
            size = 64
            while True:
                f = ImageFont.truetype(FONT_PATH_BLACK, size)
                lines = _wrap_words(d, item["en"].split(" "), f, 1120)
                if len(lines) <= 2 or size <= 42:
                    break
                size -= 4
            y = 410 if len(lines) == 1 else 380
            for ln in lines[:2]:
                self._center(d, y, " ".join(ln), f, BLUE, stroke=4)
                y += size + 20
        return np.array(img)

    def card(self, lines: list[tuple[str, int, str]]) -> np.ndarray:
        img = self.bg.copy()
        d = ImageDraw.Draw(img)
        y = 200
        for text, size, color in lines:
            f = ImageFont.truetype(FONT_PATH_BLACK, size)
            while d.textlength(text, font=f) > 1160 and size > 30:
                size -= 4
                f = ImageFont.truetype(FONT_PATH_BLACK, size)
            self._center(d, y, text, f, color)
            y += size + 40
        return np.array(img)


def phrase_clip(p: Painter, n: int, item: dict, think: float, tmp: str) -> VideoClip:
    ja = tts(audio_gen.jp_reading(item["ja"]), VOICE_JP, f"{tmp}/ja{n}.mp3")
    en = tts(item["en"], VOICE_EN, f"{tmp}/en{n}.mp3")
    en2 = tts(item["en"], VOICE_EN, f"{tmp}/en{n}b.mp3")
    parts = [silence(0.3), ja, silence(think), en, silence(0.7), en2, silence(1.0)]
    audio = concatenate_audioclips(parts)
    t_think = 0.3 + ja.duration
    t_en = t_think + think

    cache: dict = {}

    def make_frame(t):
        if t < t_think:
            key = ("ja",)
        elif t < t_en:
            key = ("bar", int((t - t_think) / think * BAR_STEPS))
        else:
            key = ("en",)
        if key not in cache:
            if key[0] == "bar":
                cache[key] = p.frame(n, item, 1 - key[1] / BAR_STEPS, False)
            else:
                cache[key] = p.frame(n, item, None, key[0] == "en")
        return cache[key]

    return VideoClip(make_frame, duration=audio.duration).with_audio(audio)


def render_chunk(p: Painter, items: list[tuple[int, dict]], dest: Path, think: float,
                 intro: list | None, outro: list | None) -> None:
    clips = []
    with tempfile.TemporaryDirectory() as tmp:
        if intro:
            clips.append(ImageClip(p.card(intro)).with_duration(4.0)
                         .with_audio(silence(4.0)))
        for n, item in items:
            clips.append(phrase_clip(p, n, item, think, tmp))
        if outro:
            clips.append(ImageClip(p.card(outro)).with_duration(6.0)
                         .with_audio(silence(6.0)))
        video = concatenate_videoclips(clips)
        video.write_videofile(str(dest), fps=24, codec="libx264", audio_codec="aac",
                              audio_bitrate="192k", threads=4, logger=None)
        video.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="瞬間英作文の聞き流し動画を作る")
    ap.add_argument("--set", required=True)
    ap.add_argument("--think", type=float, default=3.0, help="考える時間（秒）")
    ap.add_argument("--chunk", type=int, default=25)
    a = ap.parse_args()

    data = json.loads(Path(f"data/phrases/{a.set}.json").read_text(encoding="utf-8"))
    items = list(enumerate(data["items"], 1))
    p = Painter(len(items))
    title = data.get("title_ja") or data["theme"]
    intro = [(data.get("hook") or "瞬間英作文", 64, YELLOW),
             ("日本語を聞いたら、すぐ英語で言ってみよう", 40, "white"),
             (f"全{len(items)}フレーズ", 40, GRAY)]
    outro = [("おつかれさまでした！", 64, "white"),
             ("何フレーズ言えたか、コメントで教えてください", 38, YELLOW)]

    work = OUT_DIR / f"_parts_{a.set}"
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    groups = [items[i:i + a.chunk] for i in range(0, len(items), a.chunk)]
    for k, g in enumerate(groups, 1):
        dest = work / f"p{k:03d}.mp4"
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{k}/{len(groups)}] スキップ（作成済み）")
        else:
            t0 = time.time()
            print(f"[{k}/{len(groups)}] {g[0][0]}〜{g[-1][0]} を生成中...")
            render_chunk(p, g, dest, a.think,
                         intro if k == 1 else None, outro if k == len(groups) else None)
            print(f"   ✅ {time.time() - t0:.0f}秒")
        parts.append(dest)

    out = OUT_DIR / f"phrases_{a.set}.mp4"
    concat(parts, out)
    # 概要欄は5,000字まで。一覧が収まらなければ、入る所までで切る
    head = [f"日本語を聞いたら、{a.think:g}秒以内に英語で言ってみましょう。聞き流しでもOK。", "",
            "【フレーズ一覧】"]
    tail = ["", "#瞬間英作文 #英会話 #聞き流し #英語フレーズ"]
    body = []
    for n, it in items:
        line = f"{n:03d}. {it['ja']} → {it['en']}"
        if len("\n".join(head + body + [line, "（以下は動画で）"] + tail)) > 4900:
            body.append("（以下は動画で）")
            break
        body.append(line)
    meta = {
        "title": title,
        "description": "\n".join(head + body + tail),
        "tags": ["瞬間英作文", "英会話", "聞き流し", "英語フレーズ", "英語リスニング"],
    }
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    print(f"✅ 完成: {out}\n   タイトル案: {title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
