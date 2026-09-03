"""章ごとのBGMを生成して assets/bgm/ に貯める。

Higgsfield の sonilo_music で作り、音量をそろえてから保存する。
曲ごとに音量が違うと、章が変わるたびに音楽だけ大きくなって耳障りになるため。
"""
from __future__ import annotations
import argparse, os, re, subprocess, sys
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def download(url: str, dest: Path) -> bool:
    """urllib は macOS の証明書設定で失敗するため curl を使う。"""
    r = subprocess.run(["curl", "-sSL", "--fail", "-o", str(dest), url],
                       capture_output=True, text=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0
OUT_DIR = Path("assets/bgm")
COMMON = ("Purely instrumental, no vocals, no voice, no lyrics. "
          "Steady and even throughout with no sudden swells or stops, "
          "so spoken narration can sit on top. Quiet, unobtrusive, loopable.")

MOODS = {
    "curious": "Soft warm synth pads and gentle piano, light airy texture, "
               "slow steady tempo near 80 BPM, a feeling of curiosity and wonder.",
    "tension": "Low sustained strings and a soft pulsing bass note, muted and "
               "restrained, slight unease, slow tempo, minor key, no percussion hits.",
    "discovery": "Gentle rising arpeggios on marimba and warm synth, quietly hopeful "
                 "and building, steady mid tempo, major key, bright but soft.",
    "ancient": "Sparse plucked strings and a distant soft flute, dry and open, very "
               "slow, an old world feeling, spacious and reflective.",
    "closing": "Warm calm piano with soft pads settling downward, resolving and "
               "peaceful, very slow, a gentle sense of ending.",
    "lab": "Clean minimal electronic texture, soft ticking pulse, precise and tidy, "
           "steady mid tempo, neutral and analytical, very light.",
}


def generate(mood: str, seconds: int) -> str | None:
    prompt = f"{MOODS[mood]} {COMMON}"
    r = subprocess.run(["higgsfield", "generate", "create", "sonilo_music",
                        "--prompt", prompt, "--duration", str(seconds), "--wait"],
                       capture_output=True, text=True)
    m = re.findall(r"https://\S+\.(?:m4a|mp3|wav)", r.stdout + r.stderr)
    if not m:
        print(f"  ❌ {mood}: 生成に失敗\n     {(r.stdout + r.stderr)[-200:]}")
        return None
    return m[-1]


def normalize(src: Path, dst: Path, lufs: float = -20.0) -> bool:
    """曲ごとの音量差をならす。章が替わるたび音量が跳ねるのを防ぐ。"""
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(src),
                        "-af", f"loudnorm=I={lufs}:TP=-2.0:LRA=7",
                        "-c:a", "aac", "-b:a", "192k", str(dst)],
                       capture_output=True, text=True)
    return r.returncode == 0 and dst.exists()


def main() -> int:
    ap = argparse.ArgumentParser(description="章ごとのBGMを生成する")
    ap.add_argument("--moods", default=",".join(MOODS),
                    help=f"カンマ区切り。使えるのは: {', '.join(MOODS)}")
    ap.add_argument("--duration", type=int, default=120, help="秒。120で約7クレジット")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    moods = [m.strip() for m in a.moods.split(",") if m.strip()]
    bad = [m for m in moods if m not in MOODS]
    if bad:
        print(f"❌ 知らない雰囲気: {bad}", file=sys.stderr)
        return 1
    cost = {60: 3, 120: 7, 180: 11}.get(a.duration, round(a.duration * 0.06))
    print(f"{len(moods)}曲 × {a.duration}秒 = 約{cost * len(moods)} クレジット")
    if a.dry_run:
        for m in moods:
            print(f"  {m}: {MOODS[m][:70]}")
        return 0

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_raw"
    tmp.mkdir(exist_ok=True)
    ok = 0
    for i, mood in enumerate(moods, 1):
        dst = out / f"{i:02d}_{mood}.m4a"
        if dst.exists():
            print(f"  [{i}] スキップ（already {dst.name}）"); ok += 1; continue
        url = generate(mood, a.duration)
        if not url:
            continue
        raw = tmp / f"{mood}.m4a"
        # urllib は macOS の証明書設定で失敗するため curl を使う
        if not download(url, raw):
            print(f"  ❌ {mood}: 取得できず（生成は課金済み。--recover で回収できます）")
            continue
        if normalize(raw, dst):
            print(f"  [{i}] ✅ {dst.name}  {dst.stat().st_size/1e6:.1f}MB")
            ok += 1
        else:
            print(f"  [{i}] ⚠ 音量をそろえられなかったのでそのまま置きます")
            raw.replace(dst); ok += 1
    print(f"完了: {ok}/{len(moods)} → {out}/")
    return 0 if ok == len(moods) else 1


if __name__ == "__main__":
    sys.exit(main())
