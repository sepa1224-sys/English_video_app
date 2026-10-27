"""単語帳『気合の英単語 必修』の YouTube 広告（横長 1920×1080・約27秒）とサムネ（1280×720）を作る。

  python3 scripts/book_ad.py          … 声・見開き・QR を用意して output/ad/book_ad.mp4 と book_ad_thumb.jpg を書き出す

広告の目的は「ウェブサイトのトラフィック」（ボタン「ダウンロード」→ https://kiaienglish.com/go/tango?src=yt_ad）。
アップロードは坂本さんが手で行う（2026-10-27）。説明文は output/ad/説明文.txt に書く。
中身は edu/src/ad/BookAd.tsx（Composition「BookAd」「BookAdThumb」）。
"""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te  # noqa: E402
from PIL import Image  # noqa: E402

OUT = ROOT / "output" / "ad"
AD = te.PUB / "ad"  # edu/public/tango/ad（git に入らない）
PDF = te.TANGO / "out" / "kindle" / "keiko1.pdf"
SPREADS = [(1, 2), (3, 4), (7, 8), (13, 14)]  # 稽古1の見開き（左：見出し語と絵／右：例文）
ARTS = ["likely", "research", "increase", "improve", "develop", "environment"]
FPS = 30

# 仙人（稽古の動画と同じ声）。字幕・読み
LINES = [
    ("新しい英単語帳が出たぞ！", "あたらしい、えいたんごちょうが、でたぞ！"),
    ("大学入試の過去問を数えて選んだ1000語。全部イラストつきじゃ！",
     "だいがくにゅうしの、かこもんをかぞえてえらんだ、せんご。ぜんぶ、イラストつきじゃ！"),
    ("YouTubeで聞き流し、アプリでテスト。番号が全部同じじゃ！",
     "ユーチューブでききながし、アプリでテスト。ばんごうが、ぜんぶおなじじゃ！"),
    ("稽古1の100語は無料じゃ！ 今すぐダウンロードじゃ！",
     "けいこいちの、ひゃくごは、むりょうじゃ！ いますぐ、ダウンロードじゃ！"),
]
MIN_SCENE = [5.0, 8.0, 7.0, 7.0]  # 場面ごとの最低の長さ（秒）

TITLE = "新しい英単語帳『気合の英単語 必修』｜稽古1（100語）無料"
DESCRIPTION = """🎁 稽古1（100語）を無料で試せます → https://kiaienglish.com/go/tango?src=yt_ad_desc
📕 Amazonで発売中『気合の英単語 必修』紙の本 1,650円（税込）→ https://kiaienglish.com/go/amazon?src=yt_ad

大学入試の過去問を数えて選んだ1000語。
・全部イラストつき
・100語ずつの「稽古」で進める
・YouTubeで聞き流し、アプリでテスト。本・動画・アプリで単語の番号が全部同じ

#気合の英単語 #英単語 #大学受験 #気合イングリッシュ
"""


def spreads() -> list[str]:
    AD.mkdir(parents=True, exist_ok=True)
    out = []
    for a, b in SPREADS:
        p = AD / f"spread_{a:02d}.jpg"
        if not p.exists():
            tmp = AD / "_pages"
            tmp.mkdir(exist_ok=True)
            subprocess.run(["pdftoppm", "-r", "130", "-jpeg", "-f", str(a), "-l", str(b), str(PDF), str(tmp / "p")], check=True)
            pages = sorted(tmp.glob("p-*.jpg"))
            ims = [Image.open(x).convert("RGB") for x in pages]
            w, h = ims[0].size
            s = Image.new("RGB", (w * 2 + 6, h), (200, 190, 170))  # 真ん中にのどの線
            s.paste(ims[0], (0, 0))
            s.paste(ims[1], (w + 6, 0))
            s.save(p.with_suffix(".tmp.jpg"), quality=88)
            p.with_suffix(".tmp.jpg").replace(p)
            for x in pages:
                x.unlink()
            tmp.rmdir()
        out.append(f"tango/ad/{p.name}")
    return out


def build() -> dict:
    te.common_assets()
    lines = [te.line_audio("master", t, r) for t, r in LINES]
    scenes, at = [], []
    for ln, mn in zip(lines, MIN_SCENE):
        scenes.append(round(max(mn, ln["dur"] + 0.8) * FPS))
    start = 0
    for i, n in enumerate(scenes):
        at.append(start + 6)
        start += n
    for ln, a in zip(lines, at):
        ln["at"] = a
    qr = te.qr_png("yt_ad_qr")
    return {"scenes": scenes, "total": sum(scenes), "lines": lines, "spreads": spreads(),
            "arts": [te.art(w) for w in ARTS],
            "qr": f"tango/{qr.name}"}


def render(args: list[str]) -> None:
    print("▶", " ".join(args))
    subprocess.run(["npx", "remotion", *args, "--log=error"], cwd=te.EDU, check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ad = build()
    print(f"長さ {ad['total'] / FPS:.1f}秒 場面 {[round(s / FPS, 1) for s in ad['scenes']]}")
    props = ROOT / ".tmp" / "book_ad_props.json"
    props.parent.mkdir(parents=True, exist_ok=True)
    props.write_text(json.dumps({"ad": ad}, ensure_ascii=False), encoding="utf-8")
    mp4 = OUT / "book_ad.mp4"
    tmp = OUT / "book_ad.tmp.mp4"
    render(["render", "src/index.ts", "BookAd", str(tmp), f"--props={props}", "--concurrency=2",
            "--codec=h264", "--crf=18", "--audio-bitrate=192k"])
    tmp.replace(mp4)
    png = OUT / "book_ad_thumb.tmp.png"
    render(["still", "src/index.ts", "BookAdThumb", str(png), f"--props={props}"])
    Image.open(png).convert("RGB").save(OUT / "book_ad_thumb.tmp.jpg", quality=92)
    (OUT / "book_ad_thumb.tmp.jpg").replace(OUT / "book_ad_thumb.jpg")
    png.unlink()
    txt = OUT / "説明文.txt"
    txt.with_suffix(".tmp").write_text(f"【タイトル】\n{TITLE}\n\n【説明文】\n{DESCRIPTION}", encoding="utf-8")
    txt.with_suffix(".tmp").replace(txt)
    print("✅", mp4, OUT / "book_ad_thumb.jpg", txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
