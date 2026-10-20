"""「イメージで英単語エクササイズ」を稽古ごと（100語）に作る。

自前の単語帳「気合の英単語 必修」（~/kiai-tango）の絵を見て英単語を答える横長の動画。
  冒頭：単語帳の紹介（表紙）→ やり方 → 100語（絵と頭文字のヒント → 3秒 → 答え・意味・発音2回）→ 締め

  python3 tango_exercise.py 1                 … 稽古1の 声→動画→サムネ→説明文 を output/tango/ に作る
  python3 tango_exercise.py 1 --words 12      … 試しに最初の12語だけ（見た目の確認用）
  python3 tango_exercise.py --channel-art     … チャンネルのアイコンとバナー
  python3 tango_exercise.py 1 --upload        … 作った動画を非公開でアップ（坂本さんの OK のあと）
  python3 tango_exercise.py 1 --kind listen   … 聞き流し（英単語の発音→日本語の意味。以前ターゲット1900などで作っていた形式）

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

SERIES = "イメージで覚える英単語"  # 2026-10-20 坂本さん：題は「イメージで覚える英単語」。中身は必修の番号順のままなので、題やサムネはあとで変えられる
PLAYLIST = "イメージで覚える英単語（気合の英単語 必修）"
# 単語の発音はアメリカ英語の声（Bella・教育向け）。最初は Alice（イギリス英語）だったが、
# source が sauce に聞こえるなど入試の発音と違うので替えた（2026-10-18 坂本さんの指示）
WORD_VOICE = "hpp4J3VqNfWAUOO0d1Us"
# モデルは eleven_v3。multilingual_v2 では according to の語尾が上がり（続きがある読み方）、
# 文に入れて切り出しても不自然だった。v3 はそのまま読ませて語尾が下がった（2026-10-18 坂本さんが選んだ）
WORD_MODEL = "eleven_v3"
VOICE_DIR = PUB / "voice_v3"
TAGS = ["英単語", "大学受験", "英語学習", "気合イングリッシュ", "気合の英単語", "英単語エクササイズ", "受験英語"]

# 冒頭と締めのセリフ（誰が・何を）。キャラは edu/cast.json の名前
INTRO = [("master", "気合の英単語！", "きあいのえいたんご！")]  # 字幕・読み
HOWTO = [
    ("nekketsu", "絵を見たら、3秒以内に英語で言ってみろ！"),
    ("megane", "答えが出たら、発音のあとについて声に出しましょう。"),
    ("master", "稽古{keiko}、100語。はじめッ！"),
]
OUTRO = [("master", "よくぞやりきった！ 言えなかった単語は、もう一度稽古じゃ。")]

# 聞き流し（英語→日本語）。以前ターゲット1900などで作っていた形式を、自前の単語帳で作り直したもの。
# 間の長さも以前と同じ（英語→日本語 0.4秒、意味と意味 0.4秒、次の語へ 0.7秒）
LISTEN_SERIES = "英単語 聞き流し"
LISTEN_PLAYLIST = "英単語 聞き流し（気合の英単語 必修）"
# 日本語の意味は、鉄壁などの単語動画と同じ Microsoft の Keita（落ち着いた男性の声）。キャラの声ではなく（2026-10-19 坂本さんの指示）。
# 以前の動画は速さ±0%。少しゆっくり読む。edge-tts は古いと 403 で弾かれるので新しくしておく（7.3.1 で動いた）
JA_VOICE, JA_RATE = "ja-JP-KeitaNeural", "-10%"
# 英語→日本語の間は以前（0.4秒）より空ける（坂本さんの指示）
G_EJ, G_JJ, G_NEXT = 0.8, 0.4, 0.7
OUTRO_LISTEN = [("master", "稽古{keiko}、聞き流し完了じゃ！")]


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


def post(url: str, **kw) -> requests.Response:
    """通信が一瞬切れることがある（SSL: UNEXPECTED_EOF で100語の途中で止まった）。少し待って5回まで試す"""
    import time
    for i in range(5):
        try:
            return requests.post(url, **kw)
        except requests.exceptions.RequestException as e:
            if i == 4:
                raise
            print(f"    通信エラー（{type(e).__name__}）／{5 * (i + 1)}秒後にやり直し")
            time.sleep(5 * (i + 1))


def tts(text: str, voice: str, out: Path, speed: float = 1.0, model: str = "eleven_multilingual_v2") -> None:
    for i in range(3):
        r = post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
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
    # -50dB だと出だしの弱い母音（according の a）まで削ることがあるので -60dB
    trim = "silenceremove=start_periods=1:start_threshold=-60dB,areverse,silenceremove=start_periods=1:start_threshold=-60dB,areverse"
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
    # ファイルは中身で渡す（やり直すときに読み終わったファイルを渡して空にならないように）
    r = post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": api_key()},
             data={"model_id": "scribe_v1", "language_code": "en"},
             files={"file": (pad.name, pad.read_bytes(), "audio/mpeg")}, timeout=60)
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


def f0_track(p: Path, sr: int = 16000) -> "np.ndarray":
    """10ミリ秒ごとの声の高さ（Hz）。声が無いところは nan"""
    import numpy as np
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(p), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    win, hop, out = int(0.04 * sr), int(0.01 * sr), []
    for i in range(0, len(x) - win, hop):
        f = x[i:i + win] * np.hanning(win)
        if np.sqrt((f ** 2).mean()) < 0.02:
            out.append(np.nan)
            continue
        ac = np.correlate(f, f, "full")[win - 1:]
        lo, hi = int(sr / 400), int(sr / 80)
        k = lo + int(np.argmax(ac[lo:hi]))
        out.append(sr / k if ac[k] > 0.3 * ac[0] else np.nan)
    return np.array(out)


def tail_slope(p: Path) -> float | None:
    """最後の有声のかたまりで、声の高さが0.1秒あたり何Hz動くか（プラス＝語尾が上がる）"""
    import numpy as np
    f = f0_track(p)
    idx = np.where(~np.isnan(f))[0]
    if len(idx) < 4:
        return None
    runs = np.split(idx, np.where(np.diff(idx) > 2)[0] + 1)
    run = runs[-1] if len(runs[-1]) >= 4 else np.concatenate(runs[-2:])
    return float(np.polyfit(np.arange(len(run)), f[run], 1)[0] * 10)


def median_f0(p: Path) -> float | None:
    import numpy as np
    f = f0_track(p)
    return float(np.nanmedian(f)) if (~np.isnan(f)).sum() >= 4 else None


# 確かめること：①その語に聞こえるか（文字起こし）②語尾が上がっていないか（声の高さ）。
# v3 は同じ文でも読むたびに違うので、だめなら同じ頼み方で作り直す
WORD_TRIES = 6
RISE = 0.0  # 0.1秒あたり少しでも上がっていたら「語尾が上がる」（according to が +2.8 で上がって聞こえた）
CHECKS = VOICE_DIR / "checked.json"


def word_audio(headword: str) -> tuple[str, float]:
    p = VOICE_DIR / f"{slug(headword)}.mp3"
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = json.loads(CHECKS.read_text(encoding="utf-8")) if CHECKS.exists() else {}
    if headword not in checks:
        best, notes = None, []
        for i in range(WORD_TRIES):
            if i or not p.exists():
                tts(f"{headword}.", WORD_VOICE, p, 1.0, WORD_MODEL)
            peak_normalize(p)  # 声の高さの測り方は音量に左右されるので、そろえてから測る
            got, rise = transcribe(p), tail_slope(p)
            bad = (f"「{got}」に聞こえた" if not sounds_like(got, headword)
                   else f"語尾が上がった（{rise:+.1f}）" if rise is not None and rise > RISE else "")
            if not bad:
                break
            notes.append(bad)
            # 聞き取りは合っていて語尾だけ上がるものは、いちばん上がり方が小さいものを残しておく
            if sounds_like(got, headword) and (best is None or rise < best[0]):
                best = (rise, p.read_bytes())
            print(f"    ↻ {headword}：{bad}ので作り直し")
        else:
            print(f"    ⚠ 要確認：{headword} → {notes}")
            if best:
                p.write_bytes(best[1])
                rise = best[0]
        peak_normalize(p)
        checks[headword] = {"heard": got, "rise": None if rise is None else round(rise, 1), "notes": notes}
        CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
    return f"tango/{VOICE_DIR.name}/{p.name}", duration(p)


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


def ja_audio(text: str) -> dict:
    """日本語の意味を Keita で読む。同じ文は作り置きを使う"""
    say = ja_reading(text)
    key = hashlib.sha256(f"{JA_VOICE}|{JA_RATE}|{say}".encode()).hexdigest()[:12]  # ファイル名を決めるだけ
    p = PUB / "ja_keita" / f"{key}.mp3"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        raw = p.with_suffix(".raw.mp3")
        for i in range(3):
            r = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", JA_VOICE, f"--rate={JA_RATE}",
                                "--text", say, "--write-media", str(raw)], capture_output=True, text=True)
            if r.returncode == 0 and raw.exists() and raw.stat().st_size > 500:
                break
            import time
            time.sleep(3 * (i + 1))
        else:
            raise RuntimeError(f"Keita の声を作れませんでした（edge-tts を新しくすると直ることがある）: {say}\n{r.stderr[-300:]}")
        trim = "silenceremove=start_periods=1:start_threshold=-60dB,areverse,silenceremove=start_periods=1:start_threshold=-60dB,areverse"
        ff("-i", str(raw), "-af", f"aresample=44100,{trim}", "-c:a", "libmp3lame", "-b:a", "160k", str(p))
        raw.unlink()
        peak_normalize(p)
    return {"audio": f"tango/ja_keita/{p.name}", "dur": duration(p)}


def ja_reading(text: str) -> str:
    """意味の読み上げ用。「～によれば」の ～ と（家族を）の括弧は読まない記号なので外す（括弧の中身は読む）"""
    return re.sub(r"[～〜~（）()]", "", text).replace("・", "、").strip()


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


def build_props(keiko: int, limit: int | None, kind: str = "exercise") -> dict:
    entries = [e for e in json.loads(ENTRIES.read_text(encoding="utf-8")) if e["keiko"] == keiko]
    if not entries:
        raise SystemExit(f"稽古{keiko} の単語がありません")
    if limit:
        entries = entries[:limit]
    common_assets()
    # v3 は読むたびに声色がぶれることがある。声の高さがほかの語と大きく違う語は1回だけ作り直す
    for e in entries:
        word_audio(e["headword"])
    meds = {e["headword"]: median_f0(VOICE_DIR / f"{slug(e['headword'])}.mp3") for e in entries}
    vals = sorted(m for m in meds.values() if m)
    center = vals[len(vals) // 2]
    checks = json.loads(CHECKS.read_text(encoding="utf-8"))
    for h, m in meds.items():
        if m and abs(m / center - 1) > 0.2 and not checks[h].get("pitch_redo"):
            print(f"    ↻ {h}：声の高さが {m:.0f}Hz（ほかは {center:.0f}Hz 前後）なので作り直し")
            checks.pop(h)
            CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
            word_audio(h)
            checks = json.loads(CHECKS.read_text(encoding="utf-8"))
            checks[h]["pitch_redo"] = True
            m2 = median_f0(VOICE_DIR / f"{slug(h)}.mp3")
            if m2 and abs(m2 / center - 1) > 0.2:
                print(f"    ⚠ 要確認：{h} は作り直しても声の高さが {m2:.0f}Hz")
            CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
    words = []
    for i, e in enumerate(entries, 1):
        v, d = word_audio(e["headword"])
        words.append({"no": e["no"], "headword": e["headword"], "pos": e["pos"], "meanings": meanings(e),
                      "hint": hint(e["headword"]), "img": art(e["headword"]), "voice": v, "voiceDur": d})
        print(f"  {e['no']:04d} {e['headword']:<16} {d:4.2f}s  {' / '.join(meanings(e))}")
    p = {
        "keiko": keiko,
        "range": [entries[0]["no"], entries[-1]["no"]],
        "series": SERIES,
        "book": {"label": book()["label"]},
        "intro": [line_audio(*x) for x in INTRO],
        "howto": [line_audio(w, t.format(keiko=keiko)) for w, t in HOWTO],
        "outro": [line_audio(w, t) for w, t in OUTRO],
        "words": words,
        "thumbs": [w["img"] for w in words[:4]],  # サムネは左に4枚大きく
    }
    if kind == "listen":
        senses = {e["headword"]: e.get("senses") or [e["meanings"]] for e in entries}
        for w in p["words"]:
            w["ja"] = []
            for s in senses[w["headword"]]:
                w["ja"].append(ja_audio("、".join(s)))
        p.update(series=LISTEN_SERIES, thumbTop="聞き流し", howto=[],
                 outro=[line_audio(w, t.format(keiko=keiko)) for w, t in OUTRO_LISTEN])
        p["plan"] = listen_plan(p)
    return p


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


def listen_plan(p: dict) -> dict:
    """聞き流しの時間割（コマ）。ここで1回だけ計算して Remotion に渡す（両方で計算すると丸めでずれた）"""
    lines_len = lambda ls: sum(x["dur"] + LINE_GAP for x in ls) + 0.6
    t = fr(max(3.0, lines_len(p["intro"])))
    plan = {"intro": t, "words": []}
    for w in p["words"]:
        # 語の中の位置は、語の頭からの秒を足していってからコマに直す（1つずつ丸めると積み重なってずれる）
        sec, ja = 0.1 + w["voiceDur"] + G_EJ, []
        for k, x in enumerate(w["ja"]):
            ja.append(fr(sec))
            sec += x["dur"] + (G_JJ if k + 1 < len(w["ja"]) else 0)
        n = fr(sec + G_NEXT)
        plan["words"].append({"start": t, "len": n, "ja": ja})
        t += n
    plan["outro"] = t
    plan["total"] = t + fr(lines_len(p["outro"]) + 1.5)
    return plan


def exercise_events(p: dict) -> tuple[int, list[tuple[str, int, float]]]:
    """エクササイズの音（どの音を何コマ目に、どの大きさで）"""
    tl = timeline(p)
    ev = []
    for key in ("intro", "howto", "outro"):
        for x, at in zip(p[key], line_starts(p[key])):
            ev.append((x["audio"], tl[key] + at, 1.0))
    for w, st in zip(p["words"], tl["starts"]):
        for k in (3, 2, 1):
            ev.append(("tango/tick.mp3", st + fr(THINK - k), 0.45))
        v1 = st + fr(THINK + 0.1)
        ev += [(w["voice"], v1, 1.0), (w["voice"], v1 + fr(w["voiceDur"] + AFTER1), 1.0)]
    return tl["total"], ev


def listen_events(p: dict) -> tuple[int, list[tuple[str, int, float]]]:
    P = p["plan"]
    ev = [(x["audio"], at, 1.0) for x, at in zip(p["intro"], line_starts(p["intro"]))]
    ev += [(x["audio"], P["outro"] + at, 1.0) for x, at in zip(p["outro"], line_starts(p["outro"]))]
    for w, pw in zip(p["words"], P["words"]):
        ev.append((w["voice"], pw["start"] + fr(0.1), 1.0))
        ev += [(x["audio"], pw["start"] + at, 1.0) for x, at in zip(w["ja"], pw["ja"])]
    return P["total"], ev


# 音は Remotion で混ぜない。<Audio> が500個近くあると、Remotion は部品ごとに動画1本ぶんの
# 一時 WAV を作ってディスクを使い切った（2026-10-17、空き8GBで失敗）。
# ここで1本に混ぜ、Remotion は映像だけ（--muted）を書き出して最後に合わせる。
SR = 48000


def decode(path: Path) -> "np.ndarray":
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "f32le",
                          "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    import numpy as np
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def mix_audio(total: int, events: list[tuple[str, int, float]], out: Path) -> None:
    import numpy as np
    buf = np.zeros((int(total / FPS * SR) + SR, 2), dtype=np.float32)
    cache: dict[str, np.ndarray] = {}

    def put(rel: str, frame: int, vol: float = 1.0) -> None:
        if rel not in cache:
            cache[rel] = decode(EDU / "public" / rel)
        a = cache[rel]
        i = int(frame / FPS * SR)
        n = min(len(a), len(buf) - i)
        buf[i:i + n] += a[:n] * vol

    for rel, frame, vol in events:
        put(rel, frame, vol)
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
    return f"{p['series']}｜稽古{p['keiko']}（No.{a}〜{b}）【気合の英単語 必修】"


def description(p: dict) -> str:
    a, b = p["range"]
    listen = "plan" in p
    bk = book()
    if listen:
        starts, outro = [w["start"] for w in p["plan"]["words"]], p["plan"]["outro"]
        chapters = [f"{ts(0)} 単語帳『気合の英単語 必修』"]
    else:
        tl = timeline(p)
        starts, outro = tl["starts"], tl["outro"]
        chapters = [f"{ts(tl['intro'])} 単語帳『気合の英単語 必修』", f"{ts(tl['howto'])} やり方"]
    for i in range(0, len(p["words"]), 10):
        grp = p["words"][i:i + 10]
        chapters.append(f"{ts(starts[i])} No.{grp[0]['no']}〜{grp[-1]['no']}")
    chapters.append(f"{ts(outro)} おわり")
    if bk.get("kindle_url") or bk.get("paperback_url"):
        buy = "\n".join(x for x in [
            f"Kindle版：{bk['kindle_url']}" if bk.get("kindle_url") else "",
            f"紙の本：{bk['paperback_url']}" if bk.get("paperback_url") else ""] if x)
    else:
        buy = "Kindle版・紙の本：近日発売（発売したら、ここに購入リンクを載せます）"
    if listen:
        head = f"""単語帳『気合の英単語 必修』（大学入試 頻出1000語）の稽古{p['keiko']}（No.{a}〜{b}）の聞き流しです。英単語の発音のあとに、日本語の意味を読み上げます。

■ 使い方
1. 通学中や寝る前に、流して聞く
2. 慣れてきたら、日本語が流れる前に意味を言ってみる
3. 絵を見て意味を思い出す練習は「イメージで英単語エクササイズ」で
"""
    else:
        head = f"""単語帳『気合の英単語 必修』（大学入試 頻出1000語）の稽古{p['keiko']}（No.{a}〜{b}）を、イラストだけを見て英語で答えるエクササイズです。

■ やり方
1. 絵と頭文字のヒントを見て、3秒以内に英単語を声に出す
2. 答えが出たら、発音を聞いて、あとについて2回まねする
3. 言えなかった単語は、もう一度この動画で稽古する
"""
    return head + f"""
■ 単語帳『気合の英単語 必修』
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
        # 並列数は4。8にすると Chrome を8つ同時に開き、メモリ8GBの Mac ではスワップが6GBまで膨らんで
        # ディスクの空きを使い切った（2026-10-19）。少し遅くなるが止まらないほうを取る
        cmd.append(f"--concurrency={max(2, (os.cpu_count() or 4) // 2)}")
        cmd.append("--muted")  # 音は mix_audio() で別に作る
    if props:
        cmd.append(f"--props={props}")
    print("▶", " ".join(cmd))
    subprocess.run(cmd, cwd=EDU, check=True)


UPLOADED = ROOT / "data" / "tango_uploaded.json"  # 上げた動画の記録（二重に上げないため）


class QuotaExceeded(RuntimeError):
    pass


def config_root() -> Path:
    """YouTube の認証ファイル（config/）がある場所。worktree には無いので本体のチェックアウトを見る"""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    for d in [ROOT, (ROOT / common).resolve().parent]:
        if (d / "config" / "client_secret.json").exists():
            return d
    raise SystemExit("config/client_secret.json が見つかりません")


def upload(keiko: int, privacy: str, kind: str = "exercise") -> str | None:
    """作った動画を上げる。上げ済みなら何もしない。1日の上限に達したら QuotaExceeded"""
    from book_guard import check
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    name = f"keiko{keiko}" + ("_listen" if kind == "listen" else "")
    done = json.loads(UPLOADED.read_text(encoding="utf-8")) if UPLOADED.exists() else {}
    if name in done:
        print(f"  {name} は上げ済み：https://www.youtube.com/watch?v={done[name]['id']}")
        return done[name]["id"]
    base = OUT / name
    meta = json.loads((base.with_suffix(".meta.json")).read_text(encoding="utf-8"))
    check(meta["title"], meta["description"], meta["tags"])
    cwd = os.getcwd()
    os.chdir(config_root())  # ondoku_upload は config/ を今いる場所から探す
    try:
        from ondoku_upload import service, upload as yt_upload
        yt = service()
        try:
            vid = yt_upload(yt, base.with_suffix(".mp4"), meta["title"], meta["description"], meta["tags"], privacy)
        except HttpError as e:
            if e.resp.status == 403 and "quota" in str(e).lower():
                raise QuotaExceeded(str(e)[:200])
            raise
    finally:
        os.chdir(cwd)
    done[name] = {"id": vid, "privacy": privacy, "title": meta["title"]}
    UPLOADED.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    # 絵はドット絵の作り物で、実在の人や出来事と見間違えるものではないので「改変・合成コンテンツ」には当たらない。
    # 念のため明示的に「含まない」と送る（YouTube の基準：見た目が本物そっくりの合成のみ申告が要る）。
    # status を書き換えると書かなかった項目は既定に戻るので、埋め込み可などもいっしょに送る
    yt.videos().update(part="status", body={"id": vid, "status": {
        "privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
        "embeddable": True, "publicStatsViewable": True, "license": "youtube"}}).execute()
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(base.with_suffix(".jpg")))).execute()
    # シリーズの再生リストに入れる（無ければ動画と同じ公開範囲で作る）
    pid, req = None, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req and not pid:
        r = req.execute()
        pid = next((x["id"] for x in r["items"] if x["snippet"]["title"] == meta["playlist"]), None)
        req = yt.playlists().list_next(req, r)
    if not pid:
        pid = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": meta["playlist"]},
                                    "status": {"privacyStatus": privacy}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid,
                              "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
    print(f"✅ https://www.youtube.com/watch?v={vid}（{privacy}）／再生リスト「{meta['playlist']}」に追加")
    return vid


def produce(p: dict, name: str, comp: str, total: int, events: list, props: Path) -> Path:
    """音を混ぜ、映像を区切って書き出し、1本にする"""
    tmp = ROOT / ".tmp" / "tango"
    tmp.mkdir(parents=True, exist_ok=True)
    audio = tmp / f"{name}.m4a"
    mix_audio(total, events, audio)
    # 音（Python の時間割）と映像（Remotion）の長さが1コマでも違えば、音と絵がずれるので止める
    r = subprocess.run(["npx", "remotion", "compositions", "src/index.ts", f"--props={props}"],
                       cwd=EDU, capture_output=True, text=True, check=True)
    m = re.search(rf"{comp}\s+\d+\s+\S+\s+(\d+)", r.stdout)
    if not m or int(m[1]) != total:
        raise SystemExit(f"長さが合いません：Python {total}コマ／Remotion {m[1] if m else '?'}コマ")
    # Remotion は書き出し中の1コマずつの画像を一時フォルダに貯める。13分ぶん（2万3千コマ）だと
    # 空き5GBほどのディスクを使い切った（2026-10-18）。3,000コマずつに分けて書き出し、最後につなぐ
    video, step, parts = tmp / f"{name}.video.mp4", 3000, []
    for a in range(0, total, step):
        part = tmp / f"{name}.part{a // step:02d}.mp4"
        if not part.exists():
            render(comp, part.with_suffix(".tmp.mp4"), props, frames=f"{a}-{min(a + step, total) - 1}")
            part.with_suffix(".tmp.mp4").replace(part)  # 途中で止まっても、できた区切りは作り直さない
        parts.append(part)
    lst = tmp / f"{name}.parts.txt"
    lst.write_text("".join(f"file '{x}'\n" for x in parts), encoding="utf-8")
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(video))
    for x in [*parts, lst]:
        x.unlink()
    out = OUT / f"{name}.mp4"
    ff("-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
       "-movflags", "+faststart", str(out))  # -shortest は最後の3コマを落としたので付けない（音は mix_audio で同じ長さに切ってある）
    video.unlink()
    audio.unlink()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("keiko", type=int, nargs="?")
    ap.add_argument("--kind", default="exercise", choices=["exercise", "listen"],
                    help="exercise＝絵を見て答える／listen＝英語→日本語の聞き流し")
    ap.add_argument("--words", type=int, help="最初のN語だけで作る（試作用）")
    ap.add_argument("--channel-art", action="store_true", help="チャンネルのアイコンとバナーを作る")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--force", action="store_true", help="動画がもうあっても作り直す")
    a = ap.parse_args()

    if a.channel_art:
        common_assets()
        render("ChannelIcon", OUT / "channel_icon.png", still=True)
        render("ChannelBanner", OUT / "channel_banner.png", still=True)
        return 0
    if not a.keiko:
        ap.error("稽古の番号を指定してください")
    if a.upload:
        try:
            upload(a.keiko, a.privacy, a.kind)
        except QuotaExceeded as e:
            print(f"⏸ YouTube の1日の上限に達しました。明日もう一度上げてください：{e}")
            return 3
        return 0

    listen = a.kind == "listen"
    name = f"keiko{a.keiko}" + ("_listen" if listen else "") + (f"_try{a.words}" if a.words else "")
    if (OUT / f"{name}.mp4").exists() and not a.force:
        print(f"  {name}.mp4 はもうあります（作り直すなら --force）")
        return 0
    p = build_props(a.keiko, a.words, a.kind)
    from book_guard import check
    tags = [t.replace("英単語エクササイズ", "英単語 聞き流し") for t in TAGS] if listen else TAGS
    meta = {"title": title(p), "description": description(p), "tags": tags,
            "playlist": LISTEN_PLAYLIST if listen else PLAYLIST}
    check(meta["title"], meta["description"], meta["tags"])
    OUT.mkdir(parents=True, exist_ok=True)
    props = OUT / f"{name}.props.json"
    props.write_text(json.dumps({"data": p}, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / f"{name}_description.txt").write_text(meta["description"], encoding="utf-8")
    render("TangoThumb", OUT / f"{name}.png", props, still=True)
    Image.open(OUT / f"{name}.png").convert("RGB").save(OUT / f"{name}.jpg", quality=90)
    total, events = listen_events(p) if listen else exercise_events(p)
    out = produce(p, name, "TangoListen" if listen else "TangoExercise", total, events, props)
    print(f"✅ {out} （{ts(total)}）\n   {meta['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
