"""単語帳『気合の英単語 必修』の15秒の YouTube 広告を、横長（動画の前に流れる広告）と縦長（ショートの広告）で作る。

  python3 scripts/book_ad15.py            … output/ad/book_ad15.mp4（1920×1080）と book_ad15_v.mp4（1080×1920）、説明文
  python3 scripts/book_ad15.py --still    … 書き出す前に、場面ごとの1コマを output/ad/stills/ に出して見た目を確かめる

27秒版（scripts/book_ad.py）と見開き・絵・声の作り方は同じ。最初の3秒で「共通テストの英文の単語が93%分かる」を出す。
数字は kiai-coaching-app の lib/tango-coverage.json（本・サイトと同じ。切り捨て）。値段は lib/site.ts の TANGO と同じ。
行き先は https://kiaienglish.com/go/tango?src=yt_ad15（横）／yt_ad15v（縦）で、どちらの広告から来たか数える（2026-11-02）。
"""
from __future__ import annotations
import json, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import tango_exercise as te  # noqa: E402
import book_ad  # noqa: E402  見開きを作る関数をそのまま使う
from PIL import Image  # noqa: E402

OUT = ROOT / "output" / "ad"
COVERAGE = Path.home() / "kiai-coaching-app" / "lib" / "tango-coverage.json"
FPS = 30
SPREADS = book_ad.SPREADS[:2]  # 15秒なので見開きは2つ
ARTS = ["likely", "research", "increase", "improve", "develop", "environment"]
PAPER, KINDLE = "1,650円", "1,200円"

# 仙人（稽古の動画と同じ声）。字幕、読み
LINES = [
    ("共通テストの英文、単語の93%が分かるぞ！", "きょうつうテストのえいぶん、たんごの、きゅうじゅうさんパーセントが、わかるぞ！"),
    ("入試に出る順の1000語、全部イラストつきじゃ！", "にゅうしにでるじゅんの、せんご。ぜんぶ、イラストつきじゃ！"),
    ("YouTubeで聞いて、アプリでテストじゃ！", "ユーチューブできいて、アプリでテストじゃ！"),
    ("気合の英単語、Amazonで発売中じゃ！", "きあいのえいたんご、アマゾンで、はつばいちゅうじゃ！"),
]
MIN_SCENE = [4.0, 4.0, 3.3, 3.7]  # 合わせて15秒。声が長ければその分のばす

TITLE = "『気合の英単語 必修』共通テストの英文の単語が93%分かる1000語（15秒）"
DESCRIPTION = """📕 Amazonで発売中『気合の英単語 必修』紙の本 {paper}（税込）・Kindle {kindle}
🎁 稽古1（100語）は無料で見られます → https://kiaienglish.com/go/tango?src={src}_desc

大学入試に出る順の1000語。全部イラストつき。
YouTubeで聞き流し、アプリでテスト。本・動画・アプリで単語の番号が全部同じです。

※中学の単語に「必修」の1000語を足したとき、{year}年の共通テスト英語の本文で分かる単語の割合（中学の単語だけでは{base}%）。気合イングリッシュ調べ。

#気合の英単語 #英単語 #大学受験 #共通テスト
"""


def coverage() -> dict:
    d = json.loads(COVERAGE.read_text(encoding="utf-8"))
    row = next(r for r in d["groups"] if r["name"] == "共通テスト")
    return {"base": math.floor(row["base"]), "w1000": math.floor(row["w1000"]), "year": d["test_year"]}


def build() -> dict:
    te.common_assets()
    cov = coverage()
    if cov["w1000"] != 93:
        raise SystemExit(f"数字が変わっています（{cov['w1000']}%）。LINES の1つ目の「93%」と読みを直してから作り直してください")
    lines = [te.line_audio("master", t, r) for t, r in LINES]
    scenes = [round(max(mn, ln["dur"] + 0.5) * FPS) for ln, mn in zip(lines, MIN_SCENE)]
    start = 0
    for ln, n in zip(lines, scenes):
        ln["at"] = start + 5
        start += n
    book_ad.SPREADS = SPREADS
    qr = te.qr_png("yt_ad15_qr")
    return {"scenes": scenes, "total": sum(scenes), "lines": lines, "spreads": book_ad.spreads(),
            "arts": [te.art(w) for w in ARTS], "qr": f"tango/{qr.name}",
            "paper": PAPER, "kindle": KINDLE, **cov}


def render(args: list[str]) -> None:
    print("▶", " ".join(args[:4]))
    subprocess.run(["npx", "remotion", *args, "--log=error"], cwd=te.EDU, check=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ad = build()
    print(f"長さ {ad['total'] / FPS:.1f}秒 場面 {[round(s / FPS, 1) for s in ad['scenes']]}")
    props = ROOT / ".tmp" / "book_ad15_props.json"
    props.parent.mkdir(parents=True, exist_ok=True)
    props.write_text(json.dumps({"ad15": ad}, ensure_ascii=False), encoding="utf-8")
    jobs = [("BookAd15", "book_ad15", "yt_ad15"), ("BookAd15V", "book_ad15_v", "yt_ad15v")]

    if "--still" in sys.argv:
        st = OUT / "stills"
        st.mkdir(exist_ok=True)
        starts = [0]
        for s in ad["scenes"][:-1]:
            starts.append(starts[-1] + s)
        for comp, name, _ in jobs:
            for i, s in enumerate(starts):
                frame = s + min(ad["scenes"][i] - 1, 75)
                png = st / f"{name}_{i + 1}.png"
                render(["still", "src/index.ts", comp, str(png), f"--props={props}", f"--frame={frame}"])
        print("✅", st)
        return 0

    for comp, name, _ in jobs:
        tmp = OUT / f"{name}.tmp.mp4"
        render(["render", "src/index.ts", comp, str(tmp), f"--props={props}", "--concurrency=2",
                "--codec=h264", "--crf=18", "--audio-bitrate=192k"])
        tmp.replace(OUT / f"{name}.mp4")
    txt = OUT / "説明文_15秒.txt"
    body = [f"【タイトル】\n{TITLE}\n"]
    for comp, name, src in jobs:
        body.append(f"【{name}.mp4 の説明文・最終ページの URL：https://kiaienglish.com/go/tango?src={src}】\n"
                    + DESCRIPTION.format(paper=PAPER, kindle=KINDLE, src=src, year=ad["year"], base=ad["base"]))
    txt.write_text("\n".join(body), encoding="utf-8")
    print("✅", OUT / "book_ad15.mp4", OUT / "book_ad15_v.mp4", txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
