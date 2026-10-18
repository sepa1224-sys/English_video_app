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
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys
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
INTRO = [("master", "気合の英単語！", "きあいのえいたんご！")]  # 字幕・読み
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


def tts(text: str, voice: str, out: Path, speed: float = 1.0, model: str = "eleven_multilingual_v2") -> None:
    for i in range(3):
        r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                          headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
                          json={"text": text, "model_id": model}, timeout=120)
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


def line_audio(who: str, text: str, reading: str | None = None) -> dict:
    """reading は読み上げ用（字幕は text のまま）。「気合」を「きあい」と読ませたいときなど"""
    c = CAST.get(who, CAST["master"])
    speed = c.get("speed", 1.1)
    say = spoken(reading or text)
    key = hashlib.sha256(f"{c['voice']}|{speed}|{say}".encode()).hexdigest()[:12]  # 声のファイル名を決めるだけ（暗号用ではない）
    p = PUB / "lines" / f"{who}_{key}.mp3"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tts(say, c["voice"], p, speed)
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


def transcribe(p: Path) -> str:
    """ElevenLabs の文字起こし（scribe）で、発音がその単語に聞こえるか確かめる。
    頭と最後の無音を詰めた短い音だと聞き取れないことがある（though が空になった）ので、前後に0.5秒の無音を足して渡す"""
    pad = p.with_suffix(".pad.mp3")
    ff("-i", str(p), "-af", "adelay=500,apad=pad_dur=0.5", "-c:a", "libmp3lame", str(pad))
    with open(pad, "rb") as fh:
        r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": api_key()},
                          data={"model_id": "scribe_v1", "language_code": "en"}, files={"file": fh}, timeout=60)
    pad.unlink()
    r.raise_for_status()
    return r.json().get("text", "")


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def phones(s: str) -> set[str]:
    """CMU 発音辞書の発音（強勢の印は外す）。語が辞書に無ければ空"""
    try:
        import pronouncing
    except ImportError:
        return set()
    out = {""}
    for w in re.findall(r"[a-z']+", s.lower()):
        ps = {re.sub(r"\d", "", x) for x in pronouncing.phones_for_word(w)}
        if not ps:
            return set()
        out = {f"{a} {b}".strip() for a in out for b in ps}
    return out


def sounds_like(heard: str, word: str) -> bool:
    """同じ綴り、または同じ発音（main と Maine）なら合格"""
    return norm(heard) == norm(word) or bool(phones(heard) & phones(word))


# 単語ひとつだけだと読み違えることがある（base を「バルジー」と読んだ）。
# 文字起こしで違う語に聞こえたら、読ませ方とモデルを変えて作り直す
WORD_TRIES = [("{w}.", "eleven_multilingual_v2"), ("{w}", "eleven_turbo_v2_5"),
              ("{w}!", "eleven_multilingual_v2"), ("{w}.", "eleven_flash_v2_5")]
CHECKS = PUB / "voice" / "checked.json"


def word_audio(headword: str) -> tuple[str, float]:
    p = PUB / "voice" / f"{slug(headword)}.mp3"
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = json.loads(CHECKS.read_text(encoding="utf-8")) if CHECKS.exists() else {}
    if headword not in checks:
        heard = []
        for i, (fmt, model) in enumerate(WORD_TRIES):
            if i or not p.exists():
                tts(fmt.format(w=headword), WORD_VOICE, p, 0.9, model)
            got = transcribe(p)
            heard.append(got)
            if sounds_like(got, headword):
                break
            print(f"    ↻ {headword}：「{got}」に聞こえたので作り直し")
        else:
            # 1語だけの文字起こしはぶれることもある。どれも合わなければ最初の読ませ方に戻し、人が聞いて確かめる
            print(f"    ⚠ 要確認：{headword} → {heard}")
            tts(WORD_TRIES[0][0].format(w=headword), WORD_VOICE, p, 0.9, WORD_TRIES[0][1])
        peak_normalize(p)
        checks[headword] = heard[-1]
        CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
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
        "intro": [line_audio(*x) for x in INTRO],
        "howto": [line_audio(w, t.format(keiko=keiko)) for w, t in HOWTO],
        "outro": [line_audio(w, t) for w, t in OUTRO],
        "words": words,
        "thumbs": [w["img"] for w in words[:4]],
    }


# 動画の時間割。edu/src/tango/types.ts の sections() と同じ式で、コマ（1/30秒）単位に丸める。
# 丸め方がずれると100語で1秒以上ずれるので、JS の Math.round と同じ丸めにする
FPS = 30
THINK, AFTER1, AFTER2, LINE_GAP = 3.5, 0.9, 1.6, 0.35


def fr(sec: float) -> int:
    return math.floor(sec * FPS + 0.5)


def line_starts(lines: list[dict]) -> list[int]:
    t, out = fr(0.3), []
    for x in lines:
        out.append(t)
        t += fr(x["dur"] + LINE_GAP)
    return out


def timeline(p: dict) -> dict:
    """各場面の始まり（コマ）"""
    def lines_len(ls: list[dict]) -> float:
        # 足す順番も types.ts の linesLen（reduce で n + dur + LINE_GAP）と同じにする。
        # n + (dur + LINE_GAP) と足すと小数の誤差で 274.5 と 274.4999… に分かれ、丸めて1コマずれた
        n = 0.0
        for x in ls:
            n = n + x["dur"] + LINE_GAP
        return n + 0.6
    t = 0
    marks = {"intro": 0}
    t += fr(max(3.0, lines_len(p["intro"])))
    marks["howto"] = t
    t += fr(lines_len(p["howto"]))
    marks["words"] = t
    starts = []
    for w in p["words"]:
        starts.append(t)
        t += fr(THINK + 0.1 + w["voiceDur"] + AFTER1 + w["voiceDur"] + AFTER2)
    marks["outro"] = t
    marks["total"] = t + fr(lines_len(p["outro"]) + 1.5)
    return {**marks, "starts": starts}


# 音は Remotion で混ぜない。<Audio> が500個近くあると、Remotion は部品ごとに動画1本ぶんの
# 一時 WAV を作ってディスクを使い切った（2026-10-17、空き8GBで失敗）。
# ここで1本に混ぜ、Remotion は映像だけ（--muted）を書き出して最後に合わせる。
SR = 48000


def decode(path: Path) -> "np.ndarray":
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    import numpy as np
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def mix_audio(p: dict, out: Path) -> None:
    import numpy as np
    tl = timeline(p)
    total = tl["total"]
    buf = np.zeros((int(total / FPS * SR) + SR, 2), dtype=np.float32)
    cache: dict[str, np.ndarray] = {}

    def put(rel: str, frame: int, vol: float = 1.0) -> None:
        if rel not in cache:
            cache[rel] = decode(EDU / "public" / rel)
        a = cache[rel]
        i = int(frame / FPS * SR)
        n = min(len(a), len(buf) - i)
        buf[i:i + n] += a[:n] * vol

    for key, sec_start in (("intro", tl["intro"]), ("howto", tl["howto"]), ("outro", tl["outro"])):
        for x, at in zip(p[key], line_starts(p[key])):
            put(x["audio"], sec_start + at)
    for w, st in zip(p["words"], tl["starts"]):
        for k in (3, 2, 1):
            put("tango/tick.mp3", st + fr(THINK - k), 0.45)
        v1 = st + fr(THINK + 0.1)
        put(w["voice"], v1)
        put(w["voice"], v1 + fr(w["voiceDur"] + AFTER1))
    # BGM（解説ショートと同じレトロRPG風・村）を小さく流し、最初と最後はフェード
    bgm = decode(EDU / "public" / "bgm" / "03_village.mp3")
    reps = int(np.ceil(len(buf) / len(bgm)))
    track = np.tile(bgm, (reps, 1))[:len(buf)]
    t = np.arange(len(buf)) / SR * FPS
    vol = np.interp(t, [0, 20, total - 60, total], [0, 0.06, 0.06, 0]).astype(np.float32)
    buf += track * vol[:, None]
    buf = buf[:int(total / FPS * SR)]
    wav = out.with_suffix(".mix.f32")
    wav.write_bytes(np.clip(buf, -1, 1).astype(np.float32).tobytes())
    ff("-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(wav), "-af", "alimiter=limit=0.95",
       "-c:a", "aac", "-b:a", "192k", str(out))
    wav.unlink()


def ts(frame: int) -> str:
    s = int(frame / FPS)
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


def render(comp: str, out: Path, props: Path | None = None, still: bool = False, frames: str | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "remotion", "still" if still else "render", "src/index.ts", comp, str(out), "--log=error"]
    if frames:
        cmd.append(f"--frames={frames}")
    if not still:
        cmd.append(f"--concurrency={os.cpu_count() or 4}")  # 既定は半分。100語で1時間以上かかるので全部使う
        cmd.append("--muted")  # 音は mix_audio() で別に作る
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
    tmp = ROOT / ".tmp" / "tango"
    tmp.mkdir(parents=True, exist_ok=True)
    audio = tmp / f"{name}.m4a"
    mix_audio(p, audio)
    # Remotion は書き出し中の1コマずつの画像を一時フォルダに貯める。13分ぶん（2万3千コマ）だと
    # 空き5GBほどのディスクを使い切った（2026-10-18）。3,000コマずつに分けて書き出し、最後につなぐ
    video = tmp / f"{name}.video.mp4"
    total, step, parts = timeline(p)["total"], 3000, []
    # 音（Python の時間割）と映像（Remotion）の長さが1コマでも違えば、音と絵がずれるので止める
    r = subprocess.run(["npx", "remotion", "compositions", "src/index.ts", f"--props={props}"],
                       cwd=EDU, capture_output=True, text=True, check=True)
    m = re.search(r"TangoExercise\s+\d+\s+\S+\s+(\d+)", r.stdout)
    if not m or int(m[1]) != total:
        raise SystemExit(f"長さが合いません：Python {total}コマ／Remotion {m[1] if m else '?'}コマ（types.ts と timeline() を見比べる）")
    for a in range(0, total, step):
        part = tmp / f"{name}.part{a // step:02d}.mp4"
        if not part.exists():
            render("TangoExercise", part.with_suffix(".tmp.mp4"), props, frames=f"{a}-{min(a + step, total) - 1}")
            part.with_suffix(".tmp.mp4").replace(part)  # 途中で止まっても、できた区切りは作り直さない
        parts.append(part)
    lst = tmp / f"{name}.parts.txt"
    lst.write_text("".join(f"file '{x}'\n" for x in parts), encoding="utf-8")
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video))
    for x in [*parts, lst]:
        x.unlink()
    ff("-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
       "-shortest", "-movflags", "+faststart", str(OUT / f"{name}.mp4"))
    video.unlink()
    audio.unlink()
    print(f"✅ {OUT / name}.mp4 （{ts(timeline(p)['total'])}）\n   {meta['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
