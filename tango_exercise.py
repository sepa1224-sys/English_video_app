"""「イメージで英単語エクササイズ」を稽古ごと（100語）に作る。

自前の単語帳「気合の英単語 初段」（~/kiai-tango）の絵を見て英単語を答える横長の動画。
  冒頭：単語帳の紹介（表紙）→ やり方 → 100語（絵と頭文字のヒント → 3秒 → 答え・意味・発音2回）→ 締め

  python3 tango_exercise.py 1                 … 稽古1の 声→動画→サムネ→説明文 を output/tango/ に作る
  python3 tango_exercise.py 1 --words 12      … 試しに最初の12語だけ（見た目の確認用）
  python3 tango_exercise.py --channel-art     … チャンネルのアイコンとバナー
  python3 tango_exercise.py 1 --upload        … 作った動画を非公開でアップ（坂本さんの OK のあと）

単語帳の購入リンクは data/tango_book.json に書く（空なら「近日発売」と出す）。
声：単語の発音は ElevenLabs の英語ネイティブの声（ondoku_audio.py と同じ Alice）、
セリフは edu/cast.json のキャラの声。作った声は edu/public/tango/ に貯めて、稽古をまたいで使い回す。
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

import imageio_ffmpeg
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent
EDU = ROOT / "edu"
PUB = EDU / "public" / "tango"
OUT = ROOT / "output" / "tango"
TANGO = Path(os.environ.get("KIAI_TANGO", Path.home() / "kiai-tango"))
ENTRIES = TANGO / "data" / "shodan_entries.json"
ART = TANGO / "art" / "gemini"
COVER = TANGO / "out" / "cover_kindle.png"
BOOK = ROOT / "data" / "tango_book.json"
CAST = json.loads((EDU / "cast.json").read_text(encoding="utf-8"))

SERIES = "イメージで英単語エクササイズ"
PLAYLIST = "イメージで英単語エクササイズ（気合の英単語 初段）"
WORD_VOICE = "Xb7hH8MSUJpSbSDYk0k2"   # Alice（英語ネイティブ・はっきり）
TAGS = ["英単語", "大学受験", "英語学習", "気合イングリッシュ", "気合の英単語", "英単語エクササイズ", "受験英語"]

# 冒頭と締めのセリフ（誰が・何を）。キャラは edu/cast.json の名前
INTRO = [("master", "単語帳『気合の英単語 初段』。この絵で、英単語を鍛えるぞ！")]
HOWTO = [
    ("nekketsu", "絵を見たら、3秒以内に英語で言ってみろ！"),
    ("megane", "答えが出たら、発音のあとについて声に出しましょう。"),
    ("master", "稽古{keiko}、100語。はじめッ！"),
]
OUTRO = [("master", "よくぞやりきった！ 言えなかった単語は、もう一度稽古じゃ。")]


def ff(*args: str) -> None:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-v", "error", *args], check=True)


def duration(p: Path) -> float:
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(p)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), 2)


def slug(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_")


def api_key() -> str:
    if os.environ.get("ELEVENLABS_API_KEY"):
        return os.environ["ELEVENLABS_API_KEY"]
    # worktree から動かしても、本体のチェックアウトの .env を読む
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    for env in [ROOT / ".env", (ROOT / common).resolve().parent / ".env"]:
        if env.exists():
            m = re.search(r"^ELEVENLABS_API_KEY=(.+)$", env.read_text(encoding="utf-8"), re.M)
            if m:
                return m[1].strip()
    raise SystemExit("ELEVENLABS_API_KEY が見つかりません（.env）")


def tts(text: str, voice: str, out: Path, speed: float = 1.0) -> None:
    for i in range(3):
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                          headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
                          json={"text": text, "model_id": "eleven_multilingual_v2"}, timeout=120)
        if r.ok:
            break
        if r.status_code < 500 and r.status_code != 429:
            raise RuntimeError(f"ElevenLabs {r.status_code} {r.text[:200]}")
        import time
        time.sleep(3 * (i + 1))
    else:
        raise RuntimeError(f"ElevenLabs で声を作れませんでした: {text}")
    raw = out.with_suffix(".raw.mp3")
    raw.write_bytes(r.content)
    # 頭と最後の無音を詰める（単語の発音は答えの表示と同時に聞こえてほしい）
    trim = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
    tempo = f",atempo={speed}" if speed != 1 else ""
    ff("-i", str(raw), "-af", f"aresample=44100,{trim}{tempo}", "-c:a", "libmp3lame", "-b:a", "160k", str(out))
    raw.unlink()


def spoken(text: str) -> str:
    """「はじめッ！」の小さい「ッ」を ElevenLabs が「つ」と読むので外す（edu/scripts/voice.mjs と同じ）"""
    return re.sub(r"[ッっ]+(?=[！？!?。、，,…ー〜～\s」』）)]|$)", "", text)


def line_audio(who: str, text: str) -> dict:
    c = CAST.get(who, CAST["master"])
    speed = c.get("speed", 1.1)
    key = hashlib.sha1(f"{c['voice']}|{speed}|{spoken(text)}".encode()).hexdigest()[:12]
    p = PUB / "lines" / f"{who}_{key}.mp3"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tts(spoken(text), c["voice"], p, speed)
    return {"who": who, "line": text, "audio": f"tango/lines/{p.name}", "dur": duration(p)}


def peak_normalize(p: Path, target: float = -3.0) -> None:
    """いちばん大きいところを target dB にそろえる（単語の発音がセリフより小さく聞こえたため）"""
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(p), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume: (-?[\d.]+) dB", r.stderr)
    gain = target - float(m[1]) if m else 0
    if abs(gain) > 0.5:
        tmp = p.with_suffix(".norm.mp3")
        ff("-i", str(p), "-af", f"volume={gain:.1f}dB", "-c:a", "libmp3lame", "-b:a", "160k", str(tmp))
        tmp.replace(p)


def word_audio(headword: str) -> tuple[str, float]:
    p = PUB / "voice" / f"{slug(headword)}.mp3"
    mark = p.with_suffix(".normed")
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        # 文として読ませると単語だけより発音が安定する
        tts(f"{headword}.", WORD_VOICE, p, 0.9)
    if not mark.exists():
        peak_normalize(p)
        mark.touch()
    return f"tango/voice/{p.name}", duration(p)


def art(headword: str) -> str:
    """1024px の PNG を動画用の 720px JPEG にして public に置く（書き出しが軽くなる）"""
    p = PUB / "art" / f"{slug(headword)}.jpg"
    if not p.exists():
        src = ART / f"{slug(headword)}.png"
        if not src.exists():
            raise SystemExit(f"絵がありません: {src}")
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGB").resize((720, 720), Image.LANCZOS).save(p, quality=90)
    return f"tango/art/{p.name}"


def hint(headword: str) -> list[str]:
    """頭文字と字数のヒント。語ごとに「l_____」の形で返す（according to → ['a________', 't_']）"""
    return [w[0] + "_" * (len(w) - 1) for w in headword.split()]


def meanings(e: dict) -> list[str]:
    senses = e.get("senses") or [e["meanings"]]
    marks = "①②③④⑤"
    return ["、".join(s) if len(senses) == 1 else f"{marks[i]} " + "、".join(s) for i, s in enumerate(senses)]


def book() -> dict:
    b = json.loads(BOOK.read_text(encoding="utf-8")) if BOOK.exists() else {}
    # 動画の中の札は、発売の前後で古くならない言い方にする（発売状況は説明文のほうで変える）
    return {"label": "くわしくは概要欄へ", **b}


def common_assets() -> None:
    PUB.mkdir(parents=True, exist_ok=True)
    cover = PUB / "cover.jpg"
    if not cover.exists() or cover.stat().st_mtime < COVER.stat().st_mtime:
        Image.open(COVER).convert("RGB").resize((800, 1280), Image.LANCZOS).save(cover, quality=92)
    # 秒読みの音。解説ショートの tick.mp3 があればそれを、無ければ短い音を作る
    tick = PUB / "tick.mp3"
    if not tick.exists():
        se = EDU / "public" / "se" / "tick.mp3"
        if se.exists():
            shutil.copy(se, tick)
        else:
            ff("-f", "lavfi", "-i", "sine=frequency=1200:duration=0.07", "-af", "afade=t=out:st=0.03:d=0.04,volume=0.6",
               "-c:a", "libmp3lame", str(tick))
    font = EDU / "public" / "fonts" / "DelaGothicOne-Regular.ttf"
    if not font.exists():
        shutil.copy(TANGO / "fonts" / "DelaGothicOne-Regular.ttf", font)
        shutil.copy(TANGO / "fonts" / "OFL-DelaGothicOne.txt", font.with_name("DelaGothicOne-OFL.txt"))


def build_props(keiko: int, limit: int | None) -> dict:
    entries = [e for e in json.loads(ENTRIES.read_text(encoding="utf-8")) if e["keiko"] == keiko]
    if not entries:
        raise SystemExit(f"稽古{keiko} の単語がありません")
    if limit:
        entries = entries[:limit]
    common_assets()
    words = []
    for i, e in enumerate(entries, 1):
        v, d = word_audio(e["headword"])
        words.append({"no": e["no"], "headword": e["headword"], "pos": e["pos"], "meanings": meanings(e),
                      "hint": hint(e["headword"]), "img": art(e["headword"]), "voice": v, "voiceDur": d})
        print(f"  {e['no']:04d} {e['headword']:<16} {d:4.2f}s  {' / '.join(meanings(e))}")
    return {
        "keiko": keiko,
        "range": [entries[0]["no"], entries[-1]["no"]],
        "series": SERIES,
        "book": {"label": book()["label"]},
        "intro": [line_audio(w, t) for w, t in INTRO],
        "howto": [line_audio(w, t.format(keiko=keiko)) for w, t in HOWTO],
        "outro": [line_audio(w, t) for w, t in OUTRO],
        "words": words,
        "thumbs": [w["img"] for w in words[:4]],
    }


# 動画の時間割（edu/src/tango/timing.ts と同じ式。説明文の目次に使う）
THINK, AFTER1, AFTER2, LINE_GAP = 3.5, 0.9, 1.6, 0.35


def timeline(p: dict) -> dict:
    t = 0.0
    marks = {"intro": 0.0}
    t += max(5.0, sum(x["dur"] + LINE_GAP for x in p["intro"]) + 0.6)
    marks["howto"] = t
    t += sum(x["dur"] + LINE_GAP for x in p["howto"]) + 0.6
    marks["words"] = t
    starts = []
    for w in p["words"]:
        starts.append(t)
        t += THINK + 0.1 + w["voiceDur"] + AFTER1 + w["voiceDur"] + AFTER2
    marks["outro"] = t
    return {**marks, "starts": starts}


def ts(sec: float) -> str:
    s = int(sec)
    return f"{s // 60}:{s % 60:02d}"


def title(p: dict) -> str:
    a, b = p["range"]
    return f"【気合イングリッシュ】{SERIES} 稽古{p['keiko']}（No.{a}〜{b}）"


def description(p: dict) -> str:
    a, b = p["range"]
    tl = timeline(p)
    bk = book()
    chapters = [f"{ts(tl['intro'])} 単語帳『気合の英単語 初段』", f"{ts(tl['howto'])} やり方"]
    for i in range(0, len(p["words"]), 10):
        grp = p["words"][i:i + 10]
        chapters.append(f"{ts(tl['starts'][i])} No.{grp[0]['no']}〜{grp[-1]['no']}")
    chapters.append(f"{ts(tl['outro'])} おわり")
    if bk.get("kindle_url") or bk.get("paperback_url"):
        buy = "\n".join(x for x in [
            f"Kindle版：{bk['kindle_url']}" if bk.get("kindle_url") else "",
            f"紙の本：{bk['paperback_url']}" if bk.get("paperback_url") else ""] if x)
    else:
        buy = "Kindle版・紙の本：近日発売（発売したら、ここに購入リンクを載せます）"
    return f"""単語帳『気合の英単語 初段』（大学入試 頻出1000語）の稽古{p['keiko']}（No.{a}〜{b}）を、イラストだけを見て英語で答えるエクササイズです。

■ やり方
1. 絵と頭文字のヒントを見て、3秒以内に英単語を声に出す
2. 答えが出たら、発音を聞いて、あとについて2回まねする
3. 言えなかった単語は、もう一度この動画で稽古する

■ 単語帳『気合の英単語 初段』
大学入試によく出る1000語を、100語ずつ10の稽古に分けた単語帳です。この動画のイラストは、本と同じものです。
{buy}

■ 目次
""" + "\n".join(chapters) + f"""

■ この動画について
単語・訳・イラストは、すべて気合イングリッシュのオリジナルです。イラストは AI（Google Gemini）で作りました。発音とキャラクターの声は AI 音声（ElevenLabs）です。

{' '.join('#' + t for t in TAGS[:5])}
"""


def render(comp: str, out: Path, props: Path | None = None, still: bool = False) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "remotion", "still" if still else "render", "src/index.ts", comp, str(out), "--log=error"]
    if not still:
        cmd.append(f"--concurrency={os.cpu_count() or 4}")  # 既定は半分。100語で1時間以上かかるので全部使う
    if props:
        cmd.append(f"--props={props}")
    print("▶", " ".join(cmd))
    subprocess.run(cmd, cwd=EDU, check=True)


def upload(keiko: int, privacy: str) -> None:
    from book_guard import check
    from ondoku_upload import service, upload as yt_upload
    from googleapiclient.http import MediaFileUpload
    base = OUT / f"keiko{keiko}"
    meta = json.loads((base.with_suffix(".meta.json")).read_text(encoding="utf-8"))
    check(meta["title"], meta["description"], meta["tags"])
    yt = service()
    vid = yt_upload(yt, base.with_suffix(".mp4"), meta["title"], meta["description"], meta["tags"], privacy)
    # 絵はドット絵の作り物で、実在の人や出来事と見間違えるものではないので「改変・合成コンテンツ」には当たらない。
    # 念のため明示的に「含まない」と送る（YouTube の基準：見た目が本物そっくりの合成のみ申告が要る）
    yt.videos().update(part="status", body={"id": vid, "status": {
        "privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}}).execute()
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(base.with_suffix(".jpg")))).execute()
    # シリーズの再生リストに入れる（無ければ動画と同じ公開範囲で作る）
    pid, req = None, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req and not pid:
        r = req.execute()
        pid = next((x["id"] for x in r["items"] if x["snippet"]["title"] == PLAYLIST), None)
        req = yt.playlists().list_next(req, r)
    if not pid:
        pid = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": PLAYLIST},
                                    "status": {"privacyStatus": privacy}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid,
                              "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    print(f"✅ https://www.youtube.com/watch?v={vid}（{privacy}）／再生リスト「{PLAYLIST}」に追加")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("keiko", type=int, nargs="?")
    ap.add_argument("--words", type=int, help="最初のN語だけで作る（試作用）")
    ap.add_argument("--channel-art", action="store_true", help="チャンネルのアイコンとバナーを作る")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    a = ap.parse_args()

    if a.channel_art:
        common_assets()
        render("ChannelIcon", OUT / "channel_icon.png", still=True)
        render("ChannelBanner", OUT / "channel_banner.png", still=True)
        return 0
    if not a.keiko:
        ap.error("稽古の番号を指定してください")
    if a.upload:
        upload(a.keiko, a.privacy)
        return 0

    p = build_props(a.keiko, a.words)
    from book_guard import check
    meta = {"title": title(p), "description": description(p), "tags": TAGS, "playlist": PLAYLIST}
    check(meta["title"], meta["description"], meta["tags"])
    name = f"keiko{a.keiko}" + (f"_try{a.words}" if a.words else "")
    OUT.mkdir(parents=True, exist_ok=True)
    props = OUT / f"{name}.props.json"
    props.write_text(json.dumps({"data": p}, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / f"{name}_description.txt").write_text(meta["description"], encoding="utf-8")
    render("TangoThumb", OUT / f"{name}.png", props, still=True)
    Image.open(OUT / f"{name}.png").convert("RGB").save(OUT / f"{name}.jpg", quality=90)
    render("TangoExercise", OUT / f"{name}.mp4", props)
    print(f"✅ {OUT / name}.mp4 （{ts(timeline(p)['outro'])} ＋締め）\n   {meta['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
