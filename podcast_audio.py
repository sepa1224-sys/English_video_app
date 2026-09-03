"""2人対話のポッドキャスト音声を作る。

話者ごとに声を変えて1ターンずつ読み上げ、間を置いて並べる。
出力は <out>/turns/tNNN.mp3 と <out>/timing.json。
"""
from __future__ import annotations
import argparse, base64, json, os, sys
from pathlib import Path

from dotenv import load_dotenv

from ondoku_audio import VOICES, _tts_with_timestamps

GAP = 0.45          # ターンの間。詰めすぎると聞き取りにくい
SPEED = 0.94        # 会話なので音読版より少しだけ速い

# Edge-TTS は無料。25分の台本は約17,000文字あり ElevenLabs の月枠(1万)を超えるため、
# ポッドキャストはこちらを既定にする。字幕同期が要らない形式なので精度も足りる。
EDGE_VOICES = {
    "andrew": "en-US-AndrewNeural",     # 男性・落ち着いた
    "brian_e": "en-US-BrianNeural",     # 男性・軽やか
    "ryan": "en-GB-RyanNeural",         # 男性・英国
    "ava": "en-US-AvaNeural",           # 女性・自然
    "emma": "en-US-EmmaNeural",         # 女性・明るい
    "sonia": "en-GB-SoniaNeural",       # 女性・英国
}


def _duration(path: Path) -> float:
    import imageio_ffmpeg, subprocess, re
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path)],
                       capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def edge_turn(text: str, voice: str, dest: Path, speed: float) -> float:
    """Edge-TTS で1ターン合成する。"""
    import asyncio, edge_tts
    rate = f"{int(round((speed - 1) * 100)):+d}%"

    async def go():
        c = edge_tts.Communicate(text, EDGE_VOICES[voice], rate=rate)
        await c.save(str(dest))
    asyncio.run(go())
    return _duration(dest)


def turn_audio(text: str, voice: str, api_key: str, dest: Path,
               speed: float = SPEED) -> float:
    """1ターンを合成して保存し、長さ（秒）を返す。"""
    vid = VOICES[voice][0]
    res = _tts_with_timestamps(text, vid, api_key, speed)
    dest.write_bytes(base64.b64decode(res["audio_base64"]))
    al = res.get("alignment") or {}
    ends = al.get("character_end_times_seconds") or []
    if ends:
        return float(ends[-1])
    # alignment が無い場合はファイルから測る
    import imageio_ffmpeg, subprocess, re
    r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(dest)],
                       capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def build(script_path: Path, out_dir: Path, voice_a: str, voice_b: str,
          speed: float = SPEED, engine: str = "edge") -> Path:
    load_dotenv()
    api_key = None
    if engine == "eleven":
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            raise SystemExit("ELEVENLABS_API_KEY が設定されていません。")

    data = json.loads(script_path.read_text(encoding="utf-8"))
    turns = data["dialogue"]
    meta = data.get("meta", {})
    names = {"A": meta.get("speaker_a_name", "A"),
             "B": meta.get("speaker_b_name", "B")}
    voices = {"A": voice_a, "B": voice_b}

    tdir = out_dir / "turns"
    tdir.mkdir(parents=True, exist_ok=True)
    rows, t = [], 0.0
    for i, tn in enumerate(turns, 1):
        sp = tn["speaker"]
        f = tdir / f"t{i:03d}.mp3"
        if f.exists() and f.stat().st_size > 0:
            import imageio_ffmpeg, subprocess, re
            r = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(f)],
                               capture_output=True, text=True).stderr
            m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r)
            dur = int(m[1])*3600 + int(m[2])*60 + float(m[3]) if m else 0.0
            print(f"  [{i:3d}/{len(turns)}] スキップ {dur:5.2f}秒")
        else:
            if engine == "edge":
                dur = edge_turn(tn["text_en"], voices[sp], f, speed)
            else:
                dur = turn_audio(tn["text_en"], voices[sp], api_key, f, speed)
            print(f"  [{i:3d}/{len(turns)}] {names[sp][:8]:<8} {dur:5.2f}秒  "
                  f"{tn['text_en'][:46]}")
        rows.append({"id": i, "speaker": sp, "name": names[sp],
                     "en": tn["text_en"], "ja": tn.get("text_ja", ""),
                     "audio": str(f), "start": round(t, 3),
                     "duration": round(dur, 3)})
        t += dur + GAP

    timing = {"turns": rows, "total": round(t - GAP, 3),
              "speakers": names, "voices": voices,
              "title_ja": (data.get("meta") or {}).get("title_ja")
                          or (data.get("title_candidates") or [None])[0]}
    out = out_dir / "timing.json"
    out.write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ {out}  合計 {timing['total']:.1f}秒 ({timing['total']/60:.1f}分)")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="2人対話の音声を作る")
    ap.add_argument("--script", required=True, help="dialogue_script_gen の JSON")
    ap.add_argument("--out", required=True, help="出力ディレクトリ")
    ap.add_argument("--engine", default="edge", choices=["edge", "eleven"],
                    help="edge は無料。eleven は高品質だが月1万文字の枠がある")
    ap.add_argument("--voice-a", default="andrew")
    ap.add_argument("--voice-b", default="ava")
    ap.add_argument("--speed", type=float, default=SPEED)
    a = ap.parse_args()
    names = EDGE_VOICES if a.engine == "edge" else VOICES
    for v in (a.voice_a, a.voice_b):
        if v not in names:
            raise SystemExit(f"{a.engine} の声は次から選んでください: {', '.join(names)}")
    build(Path(a.script), Path(a.out), a.voice_a, a.voice_b, a.speed, a.engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
