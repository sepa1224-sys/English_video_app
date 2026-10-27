"""「3秒で意味言える？」ショート（縦 1080x1920）を、自前の単語帳『気合の英単語 必修』で作る。

以前いちばん見られたショート（他社の単語帳で作っていた shorts_quiz.py の形式・著作権の警告で非公開にした）と
同じ作り・同じ間で、中身だけ自分の本にしたもの。
  1問 = 絵と英単語と本の番号（No.xxx）→ 発音 → 3・2・1 → 意味（日本語で読む）
  最後 = 本の表紙と、稽古1の無料見本への QR。仙人の声「全部 単語帳に入っておる。稽古1は無料じゃ！概要欄からじゃ！」（2026-10-27）

  python3 scripts/tango_shorts.py --part 1            … output/tango_shorts/shorts1.mp4（と .meta.json）
  python3 scripts/tango_shorts.py --part 1 --upload   … 作って非公開で上げる（上げ済みなら何もしない）

出題：必修の絵のある語から、Part 番号を種にしたランダム5語。Part 1〜N-1 で出した語は Part N では出さない
（何度作っても同じ5語になる）。
声：英語の発音・日本語の意味・仙人のセリフは tango_exercise.py の作り置き（edu/public/tango/）を使い回す。
映像は Remotion を使わず、PIL の静止画を ffmpeg でつなぐ（edu/ の書き出しの順番待ちとぶつからない）。
"""
from __future__ import annotations
import argparse, json, random, shutil, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import tango_exercise as te  # noqa: E402

W, H = 1080, 1920
FPS = 30
# ショートは右端にボタン、下にタイトル・チャンネル名が重なる。大事な文字は横 120〜960・縦 1500 より上に
SAFE_W = 820
OUT = ROOT / "output" / "tango_shorts"
FONT_BOLD = str(ROOT / "assets" / "fonts" / "NotoSansCJKjp-Bold.otf")
FONT_BLACK = str(ROOT / "assets" / "fonts" / "NotoSansCJKjp-Black.otf")
BLUE, YELLOW, GRAY = "#2060C0", "#FFD24A", "#AAAAAA"
LABEL = "気合の英単語"
COUNT = 5
MAX_PART = 10  # この番号までは語が重ならない

# 2026-10-27 坂本さん「仙人のセリフとQRとショート、全部入れて」：稽古1（100語）の無料見本へ誘う
END_LINE = ("master", "全部 単語帳に入っておる。稽古1は無料じゃ！概要欄からじゃ！",
            "ぜんぶ、たんごちょうに、はいっておる。けいこいちは、むりょうじゃ！がいようらんからじゃ！")
FREE = te.FREE_URL.format(src="yt_shorts")
QR_SRC = "yt_shorts_qr"
AMAZON = "https://kiaienglish.com/go/amazon?src=yt_shorts"
APP = "https://kiaienglish.com/go/line?src=yt_shorts"
TAGS = ["気合の英単語", "英単語", "大学受験", "英単語クイズ", "受験英語", "shorts"]


# ---------- 出題 ----------

def pool() -> list[dict]:
    """必修のうち、絵があって発音の確認に通った語（番号順）"""
    checks = json.loads(te.CHECKS.read_text(encoding="utf-8")) if te.CHECKS.exists() else {}
    out = []
    for e in json.loads(te.ENTRIES.read_text(encoding="utf-8")):
        if not (te.ART / f"{te.slug(e['headword'])}.png").exists():
            continue
        c = checks.get(e["headword"])
        if c and len(c.get("notes", [])) >= te.WORD_TRIES:  # 作り直しても聞き取りが合わなかった語は出さない
            continue
        out.append(e)
    return out


def pick(part: int) -> list[dict]:
    """Part N の5語。Part 1〜N-1 で出した語を除いてから、N を種にランダムに選ぶ"""
    words, used = [], set()
    base = pool()
    for n in range(1, part + 1):
        left = [e for e in base if e["no"] not in used] if n <= MAX_PART else base
        words = random.Random(n).sample(left, COUNT)
        used |= {e["no"] for e in words}
    return words


def answer_lines(e: dict) -> list[str]:
    """答えに出す訳（2行まで）。意味が2つ以上の群に分かれる語は群ごと、1群なら訳を2つまで"""
    senses = e.get("senses") or [e["meanings"]]
    if len(senses) > 1:
        return ["、".join(s[:2]) for s in senses[:2]]
    return list(senses[0][:2])


# ---------- 絵 ----------

def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def fit(d: ImageDraw.ImageDraw, text: str, path: str, size: int, max_w: int, min_size: int = 48):
    while size > min_size:
        f = font(path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 6
    return font(path, min_size)


def centered(d, y, text, f, fill, stroke=0, stroke_fill="white"):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)


def rounded(img: Image.Image, size: int, radius: int = 36, border: int = 8) -> Image.Image:
    """絵を角丸にして白い縁をつける"""
    img = img.convert("RGB").resize((size, size), Image.LANCZOS)
    out = Image.new("RGBA", (size + border * 2, size + border * 2), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle([0, 0, out.width - 1, out.height - 1], radius + border, fill="white")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    out.paste(img, (border, border), mask)
    return out


class Frames:
    IMG = 450      # 絵の大きさ
    IMG_Y = 632
    WORD_Y = 1110
    LOWER_Y = 1300  # 秒読みの数字・答え

    def __init__(self):
        src = Image.open(ROOT / "assets" / "background_black.png").convert("RGB")
        s = H / src.height
        src = src.resize((int(src.width * s), H), Image.LANCZOS)
        x = (src.width - W) // 2
        self.bg = src.crop((x, 0, x + W, H))
        logo = Image.open(ROOT / "assets" / "logo_kiai.png").convert("RGBA")
        self.logo = logo.resize((220, int(logo.height * 220 / logo.width)), Image.LANCZOS)

    def base(self, idx: int | None) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = self.bg.copy()
        img.paste(self.logo, ((W - self.logo.width) // 2, 70), self.logo)
        d = ImageDraw.Draw(img)
        centered(d, 330, f"【{LABEL}】", font(FONT_BLACK, 76), YELLOW)
        centered(d, 440, "3秒で意味を言えるか？", font(FONT_BOLD, 60), "white")
        if idx is not None:
            centered(d, 526, f"{idx + 1} / {COUNT}", font(FONT_BOLD, 44), GRAY)
        return img, d

    def word(self, idx: int, e: dict, count: int | None = None, answer: list[str] | None = None) -> Image.Image:
        img, d = self.base(idx)
        art = rounded(Image.open(te.ART / f"{te.slug(e['headword'])}.png"), self.IMG)
        ax = (W - art.width) // 2
        img.paste(art, (ax, self.IMG_Y), art)
        # 本の番号の札（絵の左上）
        tag = f"No.{e['no']:03d}"
        tf = font(FONT_BLACK, 44)
        tw = d.textlength(tag, font=tf)
        bx, by = ax - 14, self.IMG_Y - 26
        d.rounded_rectangle([bx, by, bx + tw + 40, by + 70], 18, fill=YELLOW)
        d.text((bx + 20, by + 2), tag, font=tf, fill="#1a1a1a")
        f = fit(d, e["headword"], FONT_BLACK, 150, SAFE_W, 80)
        centered(d, self.WORD_Y, e["headword"], f, BLUE, stroke=5)
        if count is not None:
            centered(d, self.LOWER_Y - 20, str(count), font(FONT_BLACK, 190), YELLOW)
        if answer:
            y = self.LOWER_Y
            for i, m in enumerate(answer):
                line = f"{chr(0x2460 + i)} {m}" if len(answer) > 1 else m
                centered(d, y, line, fit(d, line, FONT_BOLD, 80, SAFE_W), "white")
                y += 110
        return img

    def end(self) -> Image.Image:
        """表紙（左）と、稽古1の無料見本への QR（右）。大事な文字は縦 1500 より上に"""
        img, d = self.base(None)
        centered(d, 545, "何問言えた？", font(FONT_BLACK, 84), "white")
        cover = Image.open(te.COVER).convert("RGB")
        cw, cy = 290, 690
        cover = cover.resize((cw, int(cover.height * cw / cover.width)), Image.LANCZOS)
        cx = 140
        d.rectangle([cx - 6, cy - 6, cx + cw + 5, cy + cover.height + 5], fill="white")
        img.paste(cover, (cx, cy))
        # QR の札（白地・余白込みの QR を、ドットのまま大きくする）
        qs = 360
        qr = Image.open(te.qr_png(QR_SRC)).convert("RGB").resize((qs, qs), Image.NEAREST)
        kx, ky, kw = 490, cy - 10, 430
        lf, sf = fit(d, "無料で稽古1（100語）", FONT_BLACK, 40, kw - 30, 30), font(FONT_BOLD, 32)
        kh = 22 + 48 + qs + 12 + 40 + 18
        d.rounded_rectangle([kx, ky, kx + kw, ky + kh], 28, fill="white", outline=YELLOW, width=8)
        lw = d.textlength("無料で稽古1（100語）", font=lf)
        d.text((kx + (kw - lw) / 2, ky + 20), "無料で稽古1（100語）", font=lf, fill="#C0262E")
        img.paste(qr, (kx + (kw - qs) // 2, ky + 22 + 48))
        sw = d.textlength("スマホで読み取り", font=sf)
        d.text((kx + (kw - sw) / 2, ky + 22 + 48 + qs + 8), "スマホで読み取り", font=sf, fill="#1a1a1a")
        y = max(cy + cover.height, ky + kh) + 40
        centered(d, y, "全部 単語帳に入っておる。", font(FONT_BOLD, 56), "white")
        centered(d, y + 85, "稽古1は無料じゃ！概要欄からじゃ！", fit(d, "稽古1は無料じゃ！概要欄からじゃ！", FONT_BLACK, 64, SAFE_W), YELLOW)
        return img


# ---------- 音 ----------

def pub(rel: str) -> Path:
    return te.EDU / "public" / rel


def mix(total: float, events: list[tuple[Path, float, float]], out: Path) -> None:
    sr = te.SR
    buf = np.zeros((int(total * sr) + sr, 2), dtype=np.float32)
    cache: dict[Path, np.ndarray] = {}
    for p, t, vol in events:
        if p not in cache:
            cache[p] = te.decode(p)
        a = cache[p]
        i = int(t * sr)
        n = min(len(a), len(buf) - i)
        buf[i:i + n] += a[:n] * vol
    buf = buf[:int(total * sr)]
    raw = out.with_suffix(".f32")
    raw.write_bytes(np.clip(buf, -1, 1).astype(np.float32).tobytes())
    te.ff("-f", "f32le", "-ar", str(sr), "-ac", "2", "-i", str(raw), "-af", "alimiter=limit=0.95",
          "-c:a", "aac", "-b:a", "160k", str(out))
    raw.unlink()


def snap(sec: float) -> float:
    """コマ（1/30秒）にそろえる。絵の切り替えと音がずれないように"""
    return round(sec * FPS) / FPS


# ---------- 作る ----------

def build(part: int) -> tuple[Path, dict]:
    words = pick(part)
    name = f"shorts{part}"
    out = OUT / f"{name}.mp4"
    work = OUT / f".work_{name}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    fr = Frames()
    tick = pub("tango/tick.mp3")
    segs: list[tuple[Image.Image, float]] = []  # (絵, 秒)
    events: list[tuple[Path, float, float]] = []
    t = 0.0
    print(f"Part.{part}: " + ", ".join(f"No.{e['no']} {e['headword']}" for e in words))
    for i, e in enumerate(words):
        v, vdur = te.word_audio(e["headword"])
        ans = answer_lines(e)
        ja = te.ja_audio("、".join(ans))
        # 英単語を見せて読む（最短1秒）。以前のショートと同じ間
        show = snap(max(vdur + 0.3, 1.0))
        events.append((pub(v), t + 0.15, 1.0))
        segs.append((fr.word(i, e), show))
        t += show
        for n in (3, 2, 1):
            events.append((tick, t, 0.5))
            segs.append((fr.word(i, e, count=n), 1.0))
            t += 1.0
        dur = snap(ja["dur"] + 0.7)
        events.append((pub(ja["audio"]), t + 0.1, 1.0))
        segs.append((fr.word(i, e, answer=ans), dur))
        t += dur
    line = te.line_audio(*END_LINE)
    end = snap(max(line["dur"] + 0.8, 3.0))
    events.append((pub(line["audio"]), t + 0.2, 1.0))
    segs.append((fr.end(), end))
    t = snap(t + end)

    lst = []
    for k, (img, sec) in enumerate(segs):
        p = work / f"{k:02d}.jpg"  # PNG だと1枚3MB近くになる（空きの少ない Mac で Part 5 が止まった）
        img.save(p, quality=95)
        lst.append(f"file '{p}'\nduration {sec:.4f}\n")
    lst.append(f"file '{work / f'{len(segs) - 1:02d}.jpg'}'\n")  # concat は最後の1枚の長さを捨てるので足す
    (work / "list.txt").write_text("".join(lst), encoding="utf-8")
    audio = work / "audio.m4a"
    mix(t, events, audio)
    tmp = out.with_suffix(".tmp.mp4")
    te.ff("-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-i", str(audio),
          "-map", "0:v", "-map", "1:a", "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264",
          "-preset", "medium", "-crf", "23", "-tune", "stillimage", "-c:a", "copy",
          "-t", f"{t:.3f}", "-movflags", "+faststart", str(tmp))
    tmp.replace(out)
    shutil.rmtree(work)
    meta = metadata(part, words) | {"duration": round(t, 1)}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {out}（{t:.1f}秒・{out.stat().st_size / 1e6:.1f}MB）")
    return out, meta


def metadata(part: int, words: list[dict]) -> dict:
    from book_guard import check
    title = f"【{LABEL}】3秒で意味言える？ ランダム{COUNT}問 Part.{part} #shorts"
    answers = "\n".join(f"No.{e['no']} {e['headword']} … {'、'.join(answer_lines(e))}" for e in words)
    desc = "\n".join([
        f"🎁 稽古1（100語）を無料で試せます → {FREE}",
        f"📕 単語帳『気合の英単語 必修』は Amazon で発売中 {AMAZON}",
        f"📱 アプリで毎日テスト（気合イングリッシュ）{APP}",
        "",
        f"『気合の英単語 必修』からランダム{COUNT}問。3秒で意味を言えるかチェック！何問言えたかコメントで教えてください。",
        "",
        "【答え】",
        answers,
        "",
        "#気合の英単語 #英単語 #大学受験 #shorts",
    ])
    check(title, desc, TAGS)
    return {"title": title, "description": desc, "tags": TAGS, "nos": [e["no"] for e in words],
            "words": [e["headword"] for e in words]}


def upload(part: int, video: Path, meta: dict, privacy: str = "private") -> str | None:
    """非公開で上げて data/tango_uploaded.json に shorts{N} で記録する。上限に達していたら None"""
    from googleapiclient.errors import HttpError
    import tango_compile as tc
    name = f"shorts{part}"
    done = tc.uploaded()
    if name in done:
        print(f"  {name} は上げ済み：https://www.youtube.com/watch?v={done[name]['id']}")
        return done[name]["id"]
    cwd = Path.cwd()
    import os
    os.chdir(te.config_root())  # ondoku_upload は config/ を今いる場所から探す
    try:
        from ondoku_upload import service, upload as yt_upload
        yt = service()
        try:
            vid = yt_upload(yt, video, meta["title"], meta["description"], meta["tags"], privacy)
        except HttpError as e:
            if e.resp.status == 403 and "quota" in str(e).lower():
                print("⚠ YouTube API の1日の上限（quotaExceeded）。mp4 だけ残しました")
                return None
            raise
        tc.record_upload(name, {"id": vid, "privacy": privacy, "title": meta["title"], "nos": meta["nos"]})
        try:
            yt.videos().update(part="status", body={"id": vid, "status": {
                "privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
                "embeddable": True, "publicStatsViewable": True, "license": "youtube"}}).execute()
        except HttpError as e:
            print(f"⚠ 公開設定の更新に失敗（動画は上がっています）: {str(e)[:200]}")
    finally:
        os.chdir(cwd)
    print(f"✅ https://www.youtube.com/shorts/{vid}（{privacy}）")
    return vid


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--part", type=int, required=True)
    ap.add_argument("--upload", action="store_true", help="非公開で上げる")
    ap.add_argument("--force", action="store_true", help="動画がもうあっても作り直す")
    a = ap.parse_args()
    out = OUT / f"shorts{a.part}.mp4"
    if out.exists() and not a.force:
        meta = json.loads(out.with_suffix(".meta.json").read_text(encoding="utf-8"))
        print(f"作成済み：{out}")
    else:
        out, meta = build(a.part)
    if a.upload:
        upload(a.part, out, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
