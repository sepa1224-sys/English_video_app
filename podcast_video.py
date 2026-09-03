"""ポッドキャスト動画を組み立てる。

音読版と違い、字幕帯（SVO色分け）は使わない。
絵を全画面でゆっくり寄せ、英語字幕を焼き込むだけの落ち着いた作りにする。
描画はPILの逐次処理ではなくffmpegに任せるので、長尺でも速い。
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

import ondoku_render as R
from ondoku_video import bgm_tracks, TITLE_SEC, END_SEC, BGM_VOLUME, BGM_XFADE

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 24


def _card(lines, sub=None) -> Image.Image:
    img = Image.new("RGB", (W, H), (26, 22, 18))       # 銅版画に合わせた暗い茶
    d = ImageDraw.Draw(img)
    MAXW = W - 200
    size = 78
    while size > 34:
        f = ImageFont.truetype(R.F_BLACK, size)
        if max(d.textbbox((0, 0), l, font=f)[2] for l in lines) <= MAXW:
            break
        size -= 2
    f_big = ImageFont.truetype(R.F_BLACK, size)
    f_sub = ImageFont.truetype(R.F_BOLD, 36)
    step = int(size * 1.24)
    total = len(lines) * step + (90 if sub else 0)
    y = (H - total) // 2
    for l in lines:
        w = d.textbbox((0, 0), l, font=f_big)[2]
        d.text(((W - w) // 2, y), l, font=f_big, fill=(238, 232, 220))
        y += step
    if sub:
        w = d.textbbox((0, 0), sub, font=f_sub)[2]
        d.text(((W - w) // 2, y + 14), sub, font=f_sub, fill=(160, 148, 130))
    d.rectangle([0, 0, W, 6], fill=(178, 122, 58))
    d.rectangle([0, H - 6, W, H], fill=(178, 122, 58))
    return img


def srt_time(t: float) -> str:
    h, r = divmod(max(t, 0), 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def write_srt(turns: list, offset: float, dest: Path) -> Path:
    out = []
    for i, t in enumerate(turns, 1):
        a = offset + t["start"]
        b = a + t["duration"]
        out.append(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{t['en']}\n")
    dest.write_text("\n".join(out), encoding="utf-8")
    return dest


def build_audio(turns: list, total: float, scenes: list, out: Path,
                bgm_volume: float, bgm_chapters: int) -> float:
    """語りとBGMを1本にまとめる。BGMは場面のまとまりごとに替える。"""
    from moviepy import AudioFileClip, CompositeAudioClip, concatenate_audioclips
    import moviepy.audio.fx as afx

    clips = [AudioFileClip(t["audio"]).with_start(TITLE_SEC + t["start"])
             for t in turns]
    dur = TITLE_SEC + total + END_SEC

    tracks = bgm_tracks() if bgm_volume > 0 else []
    if tracks:
        n_ch = max(1, bgm_chapters or min(len(tracks), max(1, len(scenes) // 2)))
        n_ch = min(n_ch, len(scenes))
        size = len(scenes) / n_ch
        bounds = []
        i = 0
        for k in range(n_ch):
            j = len(scenes) if k == n_ch - 1 else int(round((k + 1) * size))
            j = max(j, i + 1)
            bounds.append((scenes[i]["start"], scenes[j - 1]["end"]))
            i = j
        order = list(tracks)
        closing = next((t for t in order if "closing" in os.path.basename(t).lower()), None)
        if closing and len(bounds) > 1:
            order.remove(closing)
            order = order[:len(bounds) - 1] + [closing]
        used = {}
        for k, (b0, b1) in enumerate(bounds):
            path = order[k % len(order)]
            rep = used.get(path, 0)
            used[path] = rep + 1
            start = max(0.0, TITLE_SEC + b0 - (BGM_XFADE if k else TITLE_SEC))
            end = TITLE_SEC + b1 + (BGM_XFADE if k < len(bounds) - 1 else END_SEC)
            need = end - start
            m = AudioFileClip(path)
            off = (rep * 37.0) % max(m.duration, 1.0) if rep else 0.0
            if off:
                m = concatenate_audioclips([m.subclipped(off, m.duration),
                                            m.subclipped(0, off)])
            if m.duration < need:
                m = concatenate_audioclips([m] * (int(need // m.duration) + 1))
            m = m.subclipped(0, need)
            fade = min(BGM_XFADE, need / 2)
            m = m.with_effects([afx.AudioFadeIn(fade), afx.AudioFadeOut(fade)])
            m = m.with_volume_scaled(bgm_volume)
            clips.insert(0, m.with_start(start))
            print(f"  BGM{k+1}: {os.path.basename(path)} {start:6.1f}〜{end:6.1f}秒")

    track = CompositeAudioClip(clips).with_duration(dur)
    track.write_audiofile(str(out), fps=44100, codec="pcm_s16le", logger=None)
    for c in clips:
        c.close()
    return dur


def kenburns(img: Path, seconds: float, dest: Path, zoom_in: bool) -> None:
    """1枚をゆっくり寄せ（引き）ながら動画にする。"""
    n = max(int(seconds * FPS), 1)
    z = (f"min(zoom+{0.12/n:.6f},1.12)" if zoom_in
         else f"if(eq(on,0),1.12,max(zoom-{0.12/n:.6f},1.0))")
    vf = (f"scale=3840:-1,crop=3840:2160,"
          f"zoompan=z='{z}':d={n}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":s={W}x{H}:fps={FPS},format=yuv420p")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-i", str(img),
                    "-t", f"{seconds:.3f}", "-vf", vf, "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    str(dest)], check=True)


def render(work: Path, out_file: Path, bgm_volume: float = BGM_VOLUME,
           bgm_chapters: int = 0, burn_subs: bool = True) -> Path:
    timing = json.loads((work / "timing.json").read_text(encoding="utf-8"))
    sb = json.loads((work / "storyboard.json").read_text(encoding="utf-8"))
    turns, scenes = timing["turns"], sb["scenes"]
    total = timing["total"]

    tmp = work / "_build"
    tmp.mkdir(exist_ok=True)

    print("🔊 音声を合成中...")
    audio = tmp / "audio.wav"
    dur = build_audio(turns, total, scenes, audio, bgm_volume, bgm_chapters)

    print("🎞 場面ごとの映像を作成中...")
    parts = []
    card = tmp / "title.png"
    _card([sb["title_ja"]], sb.get("title_en", "")).save(card)
    seg = tmp / "p000.mp4"
    kenburns(card, TITLE_SEC, seg, True)
    parts.append(seg)
    for i, s in enumerate(scenes):
        img = work / "images" / f"s{s['id']:02d}.png"
        # 最後の場面はエンドカードの分だけ伸ばす
        length = (s["end"] - s["start"]) + (END_SEC if i == len(scenes) - 1 else 0)
        seg = tmp / f"p{s['id']:03d}.mp4"
        kenburns(img, length, seg, i % 2 == 0)
        parts.append(seg)
        print(f"  s{s['id']:02d} {length:5.1f}秒")

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    silent = tmp / "video.mp4"
    # cwd を tmp にしているので、ここは相対名で渡す
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", lst.name, "-c", "copy", silent.name],
                   check=True, cwd=str(tmp))

    vf = []
    if burn_subs:
        srt = write_srt(turns, TITLE_SEC, tmp / "en.srt")
        style = ("FontName=Arial,FontSize=21,PrimaryColour=&H00F0F0F0,"
                 "OutlineColour=&H00201810,BorderStyle=1,Outline=2,Shadow=0,"
                 "MarginV=54")
        vf = ["-vf", f"subtitles={srt.name}:force_style='{style}'"]
    print("🎬 書き出し中...")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", "video.mp4", "-i", "audio.wav",
           *vf, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
           "-crf", "21", "-c:a", "aac", "-b:a", "192k", "-shortest",
           str(out_file.resolve())]
    subprocess.run(cmd, check=True, cwd=str(tmp))
    print(f"\n✅ 書き出し完了: {out_file}  "
          f"({out_file.stat().st_size/1e6:.1f} MB / {dur/60:.1f}分)")
    return out_file


def main() -> int:
    ap = argparse.ArgumentParser(description="ポッドキャスト動画を書き出す")
    ap.add_argument("--work", required=True, help="timing.json と storyboard.json のある場所")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bgm-volume", type=float, default=BGM_VOLUME)
    ap.add_argument("--bgm-chapters", type=int, default=0)
    ap.add_argument("--no-subs", action="store_true", help="英語字幕を焼き込まない")
    a = ap.parse_args()
    render(Path(a.work), Path(a.out), a.bgm_volume, a.bgm_chapters, not a.no_subs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
