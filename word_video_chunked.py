"""単語動画を小分けに作って、無劣化で1本につなぐ。

500語を一度に moviepy へ渡すと、音声クリップ500本ぶんの ffmpeg を同時に
抱えてパイプが詰まり、CPU 0% のまま止まる（実際に48分間固まった）。
50語ずつなら詰まらないので、小分けに作って ffmpeg で連結する。
描画も音声も既存の処理をそのまま使うので、見た目と音は従来と同じ。
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time
from pathlib import Path

import imageio_ffmpeg

import audio_gen
import script_gen
import video_gen

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT_DIR = Path("output/word_audio")


def make_chunk(book: str, rng: str, submode: str, dest: Path,
               extras: dict, audio_dir: str = "output_audio_word") -> Path:
    """1つの塊を作る。既存の生成処理をそのまま呼ぶ。"""
    script = script_gen.generate_word_audio_script(book, rng, use_shuffle=False)
    if not script:
        raise RuntimeError(f"{rng} の単語を取れませんでした")
    audio = audio_gen.generate_word_audio(
        script, submode, output_dir=audio_dir,
        gap_eng_to_jap=extras["gap_eng_to_jap"],
        gap_between_jap=extras["gap_between_jap"],
        gap_next_word=extras["gap_next_word"])
    if not audio:
        raise RuntimeError(f"{rng} の音声を作れませんでした")
    video_gen.generate_word_audio_video(audio, str(dest), extras=extras)
    if not dest.exists():
        raise RuntimeError(f"{rng} の書き出しに失敗しました")
    return dest


def concat(parts: list[Path], out: Path) -> Path:
    """無劣化でつなぐ。同じ設定で作った塊なので再エンコードは要らない。"""
    # 塊は work の中にあるので、一覧も同じ場所に置いて work から実行する
    work = parts[0].parent
    lst = work / "_concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = out.resolve()
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat",
                        "-safe", "0", "-i", lst.name, "-c", "copy", str(out)],
                       cwd=str(work), capture_output=True, text=True)
    if r.returncode != 0:
        # 連結できないときだけ、作り直して揃える
        print("  無劣化の連結に失敗したので、そろえ直します")
        r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat",
                            "-safe", "0", "-i", lst.name,
                            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                            "-c:a", "aac", "-b:a", "128k", str(out)],
                           cwd=str(work), capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"連結に失敗: {r.stderr[-300:]}")
    lst.unlink(missing_ok=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="単語動画を小分けに作ってつなぐ")
    ap.add_argument("--book", required=True,
                    help="t1200 / t1400 / t1900 / teppeki / systan / derujun / leap")
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--submode", default="en_jp", choices=["en_jp", "jp_en", "en_only"])
    ap.add_argument("--chunk", type=int, default=50, help="1つの塊に入れる語数")
    ap.add_argument("--gap-eng-jap", type=float, default=0.4)
    ap.add_argument("--gap-between-jap", type=float, default=0.4)
    ap.add_argument("--gap-next-word", type=float, default=0.7)
    ap.add_argument("--end-duration", type=int, default=10)
    ap.add_argument("--countdown", action="store_true",
                    help="冒頭に5秒のカウントダウンを入れる")
    ap.add_argument("--out", help="出力ファイル名（既定は自動）")
    ap.add_argument("--audio-dir", default="output_audio_word",
                    help="単語音声の作業フォルダ。同時に複数走らせるときは分ける")
    a = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work = OUT_DIR / f"_parts_{a.book}_{a.start}-{a.end}"
    work.mkdir(exist_ok=True)
    out = Path(a.out) if a.out else OUT_DIR / f"word_audio_{a.book}_{a.start}-{a.end}.mp4"

    bounds = list(range(a.start, a.end + 1, a.chunk))
    print(f"{a.book} {a.start}-{a.end} を {len(bounds)}個の塊に分けて作ります"
          f"（1塊 {a.chunk}語）\n")
    parts, t0 = [], time.time()
    for i, s in enumerate(bounds, 1):
        e = min(s + a.chunk - 1, a.end)
        dest = work / f"p{i:03d}_{s}-{e}.mp4"
        last = (e == a.end)
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i}/{len(bounds)}] {s}-{e} スキップ（作成済み）")
            parts.append(dest)
            continue
        first = (s == a.start)
        extras = {
            "gap_eng_to_jap": a.gap_eng_jap,
            "gap_between_jap": a.gap_between_jap,
            "gap_next_word": a.gap_next_word,
            # カウントダウンは先頭の塊だけ、終了画面は最後の塊だけに付ける
            "use_countdown": a.countdown and first,
            "end_duration": a.end_duration if last else 0,
        }
        t1 = time.time()
        print(f"[{i}/{len(bounds)}] {s}-{e} を生成中...")
        make_chunk(a.book, f"{s}-{e}", a.submode, dest, extras, a.audio_dir)
        print(f"        ✅ {dest.stat().st_size/1e6:.1f}MB  {time.time()-t1:.0f}秒")
        parts.append(dest)

    print(f"\n{len(parts)}個をつなぎます")
    concat(parts, out)
    print(f"\n✅ 完成: {out}  ({out.stat().st_size/1e6:.1f}MB / "
          f"合計 {(time.time()-t0)/60:.0f}分)")
    print(f"   塊は {work} に残しています（確認後に削除してください）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
