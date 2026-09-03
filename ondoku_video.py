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
BGM_DIR = "assets/bgm"        # ここに曲を足すと章ごとに使い分ける
BGM_VOLUME = 0.055    # ナレーションを邪魔しない音量
BGM_XFADE = 2.0       # 章の変わり目で重ねる秒数


def bgm_tracks() -> list[str]:
    """使えるBGMを集める。assets/bgm/ を優先し、無ければ従来の1曲。"""
    d = Path(BGM_DIR)
    if d.is_dir():
        found = sorted(str(f) for f in d.iterdir()
                       if f.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg"))
        if found:
            return found
    return [p for p in (BGM_PATH, "assets/podcast_bgm.mp3") if os.path.exists(p)]


def chapter_bounds(sents: list, n_chapters: int) -> list[tuple[float, float]]:
    """段落の切れ目で本文を章に分け、それぞれの開始・終了秒を返す。

    話題が変わるところで曲を替えたいので、文の途中では切らない。
    """
    paras = []
    for s_ in sents:
        if not paras or s_["para"] != paras[-1][0]:
            paras.append((s_["para"], []))
        paras[-1][1].append(s_)
    if n_chapters < 1:
        n_chapters = 1
    n_chapters = min(n_chapters, len(paras))
    size = len(paras) / n_chapters
    out, i = [], 0
    for k in range(n_chapters):
        j = len(paras) if k == n_chapters - 1 else int(round((k + 1) * size))
        j = max(j, i + 1)
        group = [s_ for _, ss in paras[i:j] for s_ in ss]
        out.append((group[0]["start"], group[-1]["start"] + group[-1]["duration"]))
        i = j
    return out
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _wrap_card_lines(lines, d, size, max_w):
    """長い行は区切り記号か読点で2行に折る。"""
    out = []
    f = ImageFont.truetype(R.F_BLACK, size)
    for ln in lines:
        if d.textbbox((0, 0), ln, font=f)[2] <= max_w:
            out.append(ln); continue
        best = None
        for sep in ("―", "—", "、", "｜", "|", " "):
            i = ln.find(sep)
            if i > 0:
                # なるべく真ん中で折る
                cand = min((ln.count(sep) and [j for j, c in enumerate(ln) if c == sep] or []),
                           key=lambda j: abs(j - len(ln) // 2), default=None)
                if cand is not None:
                    best = (cand, sep); break
        if best:
            i, sep = best
            out += [ln[:i].strip(sep).strip(), ln[i:].lstrip(sep).strip()]
        else:
            h = len(ln) // 2
            out += [ln[:h], ln[h:]]
    return out


def _card(lines, sub=None):
    """タイトル/エンドカードを1枚描く。長い題名でもはみ出さないよう縮める。"""
    img = Image.new("RGB", (R.W, R.H), R.BAND_BG)
    d = ImageDraw.Draw(img)
    MAX_W = R.W - 160
    lines = _wrap_card_lines(lines, d, 78, MAX_W)
    size = 78
    while size > 34:
        f = ImageFont.truetype(R.F_BLACK, size)
        if max(d.textbbox((0, 0), ln, font=f)[2] for ln in lines) <= MAX_W:
            break
        size -= 2
    f_big = ImageFont.truetype(R.F_BLACK, size)
    f_sub = ImageFont.truetype(R.F_BOLD, 38)
    step = int(size * 1.22)
    total = len(lines) * step + (96 if sub else 0)
    y = (R.H - total) // 2
    for ln in lines:
        w = d.textbbox((0, 0), ln, font=f_big)[2]
        d.text(((R.W - w) // 2, y), ln, font=f_big, fill=(240, 240, 246))
        y += step
    if sub:
        w = d.textbbox((0, 0), sub, font=f_sub)[2]
        d.text(((R.W - w) // 2, y + 16), sub, font=f_sub, fill=(150, 150, 168))
    # 上下にブランド色のアクセント
    d.rectangle([0, 0, R.W, 6], fill=R.BAND_EDGE)
    d.rectangle([0, R.H - 6, R.W, R.H], fill=R.BAND_EDGE)
    return img


def build_audio_track(sents: list, total_end: float, out_path: Path,
                      bgm_volume: float = BGM_VOLUME,
                      bgm_chapters: int = 0) -> float:
    """文ごとのmp3を、startに従って1本に合成する"""
    from moviepy import AudioFileClip, CompositeAudioClip

    # 映像は冒頭にタイトルカードが入るので、ナレーションもその分だけ後ろにずらす。
    # ここを揃えないと音声が先行して字幕とずれる。
    clips = []
    for s in sents:
        c = AudioFileClip(s["audio"]).with_start(TITLE_SEC + s["start"])
        clips.append(c)
    total = TITLE_SEC + total_end + END_SEC

    # BGM。話題の変わり目で曲を替える（見つからなければ無音のまま続行）
    tracks = bgm_tracks() if bgm_volume > 0 else []
    if tracks:
        try:
            from moviepy import concatenate_audioclips
            import moviepy.audio.fx as afx
            # 既定は4章。曲が1つしかないときだけ切り替えない。
            n_ch = bgm_chapters or (4 if len(tracks) > 1 else 1)
            n_ch = max(1, n_ch)
            bounds = chapter_bounds(sents, n_ch)
            # 曲順を話の流れに合わせる。終わりの曲(closing)は必ず最後の章に置く。
            order = list(tracks)
            closing = next((t for t in order if "closing" in os.path.basename(t).lower()), None)
            if closing and len(bounds) > 1:
                order.remove(closing)
                order = order[:len(bounds) - 1] + [closing]
            used = {}
            for k, (b0, b1) in enumerate(bounds):
                path = order[k % len(order)]
                # 同じ曲が再登場するときは、頭から流すと繰り返しに聞こえる。
                # 使った回数だけ後ろへずらして別の場所から鳴らす。
                rep = used.get(path, 0)
                used[path] = rep + 1
                # 章の頭と尻に重ねしろを足し、前後の曲と自然につなぐ
                start = TITLE_SEC + b0 - (BGM_XFADE if k else TITLE_SEC)
                start = max(0.0, start)
                end = TITLE_SEC + b1 + (BGM_XFADE if k < len(bounds) - 1 else END_SEC)
                need = end - start
                bgm = AudioFileClip(path)
                off = (rep * 37.0) % max(bgm.duration, 1.0) if rep else 0.0
                if off:
                    bgm = concatenate_audioclips(
                        [bgm.subclipped(off, bgm.duration), bgm.subclipped(0, off)])
                if bgm.duration < need:       # 足りなければ繰り返す
                    n = int(need // bgm.duration) + 1
                    bgm = concatenate_audioclips([bgm] * n)
                bgm = bgm.subclipped(0, need)
                fade = min(BGM_XFADE, need / 2)
                bgm = bgm.with_effects([afx.AudioFadeIn(fade), afx.AudioFadeOut(fade)])
                try:
                    bgm = bgm.with_volume_scaled(bgm_volume)
                except AttributeError:        # moviepy v1 互換
                    bgm = bgm.volumex(bgm_volume)
                clips.insert(0, bgm.with_start(start))
                print(f"  BGM{k+1}: {os.path.basename(path)} "
                      f"{start:6.1f}〜{end:6.1f}秒")
            if len(bounds) == 1:
                print(f"  （曲が1つしかないため切り替えなし。{BGM_DIR}/ に足すと章ごとに替わります）")
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
        have = sorted(frames_dir.glob("*.jpg")) if frames_dir.exists() else []
        # クリップを作り直したのに古いフレームが残っていると、
        # 差し替え前の絵がそのまま動画に入ってしまう。新しければ作り直す。
        stale = bool(have) and os.path.getmtime(clip_path) > os.path.getmtime(have[0])
        if stale:
            print(f"  ↻ {frames_dir.name} は古いので作り直します")
            for f in have:
                f.unlink()
            have = []
        if not have:
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


def _body_frame(sents, si, bt, scene_of, scene_span, sources, body_end,
                cameras=None, show_ja=True):
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
    if src.is_clip:
        # クリップ側に既にカメラの動きが入っているので二重にかけない
        zoom, ox, oy = 1.0, 0.0, 0.0
    else:
        move = (cameras or {}).get(sc, R.DEFAULT_MOVE)
        zoom, ox, oy = R.camera_at(move, prog)
    return R.render_frame(
        src.at(bt - st), s["chunks"], hl, s["ja"],
        progress=max(0.0, min(1.0, bt / body_end)),
        zoom=zoom, ox=ox, oy=oy, show_ja=show_ja,
    )


def render(material_id: str, out_file: str | None = None,
           max_scene: int | None = None, bgm_volume: float = BGM_VOLUME,
           bgm_chapters: int = 0,
           profile: str | None = None, show_ja: bool = False):
    from ondoku_profiles import paths
    base = OUTPUT_DIR / material_id
    # ナレーションは系統共通。絵と動画だけ系統別に持つ。
    P = paths(material_id, profile) if profile else None
    timing = json.loads(
        (OUTPUT_DIR / f"{material_id}_timing.json").read_text(encoding="utf-8"))
    sb_path = P["storyboard"] if P else OUTPUT_DIR / f"{material_id}_storyboard.json"
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    img_dir = P["images"] if P else base / "images"
    clip_dir = P["clips"] if P else base / "clips"
    if out_file is None and P:
        out_file = str(P["video"])

    # 文id -> シーン、シーン -> 画像パス
    scene_of = {}
    for sc in sb["scenes"]:
        for sid in sc["sentence_ids"]:
            scene_of[sid] = sc["id"]
    sources, animated = {}, []
    for sc in sb["scenes"]:
        i = sc["id"]
        still = img_dir / f"s{i:02d}.png"
        clip = clip_dir / f"s{i:02d}.mp4"
        sources[i] = SceneSource(
            str(still) if still.exists() else None,
            str(clip) if clip.exists() else None,
            clip_dir / f"s{i:02d}_frames",
        )
        if sources[i].is_clip:
            animated.append(i)
    missing = [i for i, s_ in sources.items() if not s_.still and not s_.is_clip]
    if missing:
        print(f"⚠ 絵が無いシーン: {missing}（そこは背景のみになります）")
    if animated:
        print(f"🎞 アニメ適用シーン: {animated}")

    cameras = {sc["id"]: sc.get("camera", R.DEFAULT_MOVE) for sc in sb["scenes"]}
    used = {}
    for sc in sb["scenes"]:
        used[cameras[sc["id"]]] = used.get(cameras[sc["id"]], 0) + 1
    print(f"🎥 カメラワーク: {used}")

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
    total_sec = build_audio_track(sents, body_end, audio_path, bgm_volume,
                                  bgm_chapters)

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
                                  sources, body_end, cameras, show_ja)
                # 文の切り替わりを滑らかにする
                if si > 0:
                    since = bt - sents[si]["start"]
                    if 0 <= since < XFADE:
                        prev = _body_frame(sents, si - 1, sents[si]["start"] - 1e-3,
                                           scene_of, scene_span, sources, body_end,
                                           cameras, show_ja)
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
    ap.add_argument("--bgm-chapters", type=int, default=0,
                    help="BGMを切り替える章の数。0で自動（曲が複数あれば4章）")
    ap.add_argument("--max-scene", type=int, default=None,
                    help="このシーン番号までで書き出す（イラスト未生成時の部分出力用）")
    ap.add_argument("--profile", default=None,
                    help="制作系統（illustrated / cinematic）")
    ap.add_argument("--show-ja", action="store_true",
                    help="日本語訳を画面に焼き込む（既定は出さない。YouTube字幕を使う）")
    a = ap.parse_args()
    render(a.id, a.out, a.max_scene, a.bgm_volume, a.bgm_chapters,
           a.profile, a.show_ja)
