"""
ondoku_video.py — 音読動画を書き出す

timing JSON（実測タイミング）と絵コンテ、生成済みイラストから
1920x1080 の動画を合成する。フレームは ffmpeg に直接パイプするので
中間PNGをディスクに残さない。
"""

import os
import json
import subprocess
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

import ondoku_render as R

OUTPUT_DIR = Path("output") / "ondoku"
FPS = 24
ZOOM_PER_SCENE = 0.06     # 1シーンかけて6%寄せる
TITLE_SEC = 4.5
END_SEC = 4.0
XFADE = 0.28          # 文の切り替わりのクロスフェード秒
BGM_PATH = "assets/bgm_science.m4a"
BGM_VOLUME = 0.055    # ナレーションを邪魔しない音量
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _card(lines, sub=None):
    """タイトル/エンドカードを1枚描く"""
    img = Image.new("RGB", (R.W, R.H), R.BAND_BG)
    d = ImageDraw.Draw(img)
    f_big = ImageFont.truetype(R.F_BLACK, 78)
    f_sub = ImageFont.truetype(R.F_BOLD, 38)
    total = len(lines) * 96 + (96 if sub else 0)
    y = (R.H - total) // 2
    for ln in lines:
        w = d.textbbox((0, 0), ln, font=f_big)[2]
        d.text(((R.W - w) // 2, y), ln, font=f_big, fill=(240, 240, 246))
        y += 96
    if sub:
        w = d.textbbox((0, 0), sub, font=f_sub)[2]
        d.text(((R.W - w) // 2, y + 16), sub, font=f_sub, fill=(150, 150, 168))
    # 上下にブランド色のアクセント
    d.rectangle([0, 0, R.W, 6], fill=R.BAND_EDGE)
    d.rectangle([0, R.H - 6, R.W, R.H], fill=R.BAND_EDGE)
    return img


def build_audio_track(sents: list, total_end: float, out_path: Path,
                      bgm_volume: float = BGM_VOLUME) -> float:
    """文ごとのmp3を、startに従って1本に合成する"""
    from moviepy import AudioFileClip, CompositeAudioClip

    # 映像は冒頭にタイトルカードが入るので、ナレーションもその分だけ後ろにずらす。
    # ここを揃えないと音声が先行して字幕とずれる。
    clips = []
    for s in sents:
        c = AudioFileClip(s["audio"]).with_start(TITLE_SEC + s["start"])
        clips.append(c)
    total = TITLE_SEC + total_end + END_SEC

    # BGM（見つからなければ無音のまま続行する）
    if bgm_volume > 0 and os.path.exists(BGM_PATH):
        try:
            bgm = AudioFileClip(BGM_PATH)
            if bgm.duration < total:          # 足りなければ繰り返す
                from moviepy import concatenate_audioclips
                n = int(total // bgm.duration) + 1
                bgm = concatenate_audioclips([bgm] * n)
            bgm = bgm.subclipped(0, total)
            try:
                bgm = bgm.with_volume_scaled(bgm_volume)
            except AttributeError:            # moviepy v1 互換
                bgm = bgm.volumex(bgm_volume)
            clips.insert(0, bgm.with_start(0))
            print(f"  BGM: {BGM_PATH} (音量 {bgm_volume})")
        except Exception as e:
            print(f"  ⚠ BGMを読めませんでした（無音で続行）: {e}")

    track = CompositeAudioClip(clips).with_duration(total)
    # 中間はPCM wav。同梱ffmpegに libfdk_aac が無く .m4a 直書きは失敗するため。
    track.write_audiofile(str(out_path), fps=44100, codec="pcm_s16le",
                          logger=None)
    for c in clips:
        c.close()
    return total


class SceneSource:
    """シーンの絵の供給元。静止画か、動画クリップのどちらか。

    クリップがある場合は、あらかじめイラスト表示領域の大きさに
    切り出しておいたフレームを順に返す（zoomは効かせない。
    クリップ側に既にカメラの動きが入っているため）。
    """

    def __init__(self, still_path, clip_path, frames_dir):
        self.still = still_path
        self.frames = []
        if clip_path and os.path.exists(clip_path):
            self.frames = self._extract(clip_path, frames_dir)

    @staticmethod
    def _extract(clip_path, frames_dir):
        frames_dir = Path(frames_dir)
        if not frames_dir.exists() or not list(frames_dir.glob("*.jpg")):
            frames_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                FFMPEG, "-y", "-loglevel", "error", "-i", str(clip_path),
                "-vf", f"fps={FPS},scale={R.W}:{R.H}:force_original_"
                       f"aspect_ratio=increase,crop={R.W}:{R.H}",
                "-q:v", "3", str(frames_dir / "%04d.jpg"),
            ], check=True)
        return sorted(frames_dir.glob("*.jpg"))

    @property
    def is_clip(self):
        return bool(self.frames)

    def at(self, elapsed):
        """シーン開始からの経過秒に対応する絵を返す"""
        if not self.frames:
            return self.still
        i = int(elapsed * FPS)
        i = max(0, min(i, len(self.frames) - 1))   # 尺が足りなければ最終フレームで止める
        return Image.open(self.frames[i]).convert("RGB")


def _body_frame(sents, si, bt, scene_of, scene_span, sources, body_end):
    """本文の1フレームを描く（クロスフェードで2回呼ぶため関数に切り出す）"""
    s = sents[si]
    hl = None
    for k, c in enumerate(s["chunks"]):
        if c["start"] <= bt <= c["end"]:
            hl = k
            break
        if bt > c["end"]:
            hl = k
    sc = scene_of[s["id"]]
    st, en = scene_span[sc]
    prog = 0.0 if en <= st else max(0.0, min(1.0, (bt - st) / (en - st)))
    src = sources[sc]
    return R.render_frame(
        src.at(bt - st), s["chunks"], hl, s["ja"],
        progress=max(0.0, min(1.0, bt / body_end)),
        zoom=1.0 if src.is_clip else 1.0 + ZOOM_PER_SCENE * prog,
    )


def render(material_id: str, out_file: str | None = None,
           max_scene: int | None = None, bgm_volume: float = BGM_VOLUME):
    base = OUTPUT_DIR / material_id
    timing = json.loads(
        (OUTPUT_DIR / f"{material_id}_timing.json").read_text(encoding="utf-8"))
    sb = json.loads(
        (OUTPUT_DIR / f"{material_id}_storyboard.json").read_text(encoding="utf-8"))

    # 文id -> シーン、シーン -> 画像パス
    scene_of = {}
    for sc in sb["scenes"]:
        for sid in sc["sentence_ids"]:
            scene_of[sid] = sc["id"]
    sources, animated = {}, []
    for sc in sb["scenes"]:
        i = sc["id"]
        still = base / "images" / f"s{i:02d}.png"
        clip = base / "clips" / f"s{i:02d}.mp4"
        sources[i] = SceneSource(
            str(still) if still.exists() else None,
            str(clip) if clip.exists() else None,
            base / "clips" / f"s{i:02d}_frames",
        )
        if sources[i].is_clip:
            animated.append(i)
    missing = [i for i, s_ in sources.items() if not s_.still and not s_.is_clip]
    if missing:
        print(f"⚠ 絵が無いシーン: {missing}（そこは背景のみになります）")
    if animated:
        print(f"🎞 アニメ適用シーン: {animated}")

    sents = timing["sentences"]
    if max_scene is not None:
        sents = [s for s in sents if scene_of[s["id"]] <= max_scene]
        if not sents:
            raise ValueError("対象の文がありません")
        print(f"ℹ シーン{max_scene}までの{len(sents)}文で書き出します"
              f"（全{len(timing['sentences'])}文）")
    body_end = sents[-1]["start"] + sents[-1]["duration"]

    # シーンごとの開始/終了秒（ズームの進み具合に使う）
    scene_span = {}
    for s in sents:
        sc = scene_of[s["id"]]
        st, en = s["start"], s["start"] + s["duration"]
        if sc not in scene_span:
            scene_span[sc] = [st, en]
        else:
            scene_span[sc][1] = en

    # --- 音声 ---
    audio_path = base / "audio_track.wav"
    print("🔊 音声トラックを合成中...")
    total_sec = build_audio_track(sents, body_end, audio_path, bgm_volume)

    # total_sec には既にタイトルカード分が含まれている（build_audio_track参照）
    total_with_cards = total_sec
    n_frames = int(total_with_cards * FPS)
    out_file = out_file or str(base / f"{material_id}.mp4")

    title_img = _card(
        [sb["title_ja"]],
        f"{sb['meta']['material_title']}  |  {sb['meta']['level']}")
    end_img = _card(["Thanks for watching", "気合イングリッシュ"])

    cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{R.W}x{R.H}", "-r", str(FPS), "-i", "pipe:0",
        "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        out_file,
    ]
    print(f"🎬 書き出し開始: {n_frames}フレーム / {total_with_cards:.1f}秒")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    si = 0
    for f in range(n_frames):
        t = f / FPS
        if t < TITLE_SEC:
            img = title_img
        else:
            bt = t - TITLE_SEC
            if bt >= body_end:
                img = end_img
            else:
                while si + 1 < len(sents) and bt >= sents[si + 1]["start"]:
                    si += 1
                while si > 0 and bt < sents[si]["start"]:
                    si -= 1
                img = _body_frame(sents, si, bt, scene_of, scene_span,
                                  sources, body_end)
                # 文の切り替わりを滑らかにする
                if si > 0:
                    since = bt - sents[si]["start"]
                    if 0 <= since < XFADE:
                        prev = _body_frame(sents, si - 1, sents[si]["start"] - 1e-3,
                                           scene_of, scene_span, sources, body_end)
                        img = Image.blend(prev, img, since / XFADE)
        proc.stdin.write(img.tobytes())
        if f % (FPS * 10) == 0:
            print(f"  {t:6.1f}秒 / {total_with_cards:.1f}秒")

    proc.stdin.close()
    proc.wait()
    size = os.path.getsize(out_file) / 1e6
    print(f"\n✅ 書き出し完了: {out_file}  ({size:.1f} MB)")
    return out_file


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="音読動画の書き出し")
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--bgm-volume", type=float, default=BGM_VOLUME,
                    help="BGM音量。0で無効")
    ap.add_argument("--max-scene", type=int, default=None,
                    help="このシーン番号までで書き出す（イラスト未生成時の部分出力用）")
    a = ap.parse_args()
    render(a.id, a.out, a.max_scene, a.bgm_volume)
