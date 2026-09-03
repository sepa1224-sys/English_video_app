"""「1日5分 英語で聞く教養」を1本作って、翌朝の予約公開まで通す。

夜に実行し、翌朝7時に自動公開させる想定。
途中で失敗したら、そこで止めて理由を残す（中途半端な動画を公開しないため）。
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

from ondoku_profiles import materials_dir

APP = Path(__file__).resolve().parent
MATERIALS = materials_dir()
LOG_DIR = APP / "output" / "daily_logs"
MIN_FREE_MB = 2500          # これを下回ると書き出しが落ちるので先に止める


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def run(cmd: list[str], step: str) -> str:
    log(f"▶ {step}")
    r = subprocess.run(cmd, cwd=str(APP), capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.strip().splitlines()[-6:]:
        print("    " + line, flush=True)
    if r.returncode != 0:
        raise SystemExit(f"❌ {step} で失敗しました（終了コード {r.returncode}）")
    return out


def free_mb() -> int:
    st = os.statvfs("/")
    return int(st.f_bavail * st.f_frsize / 1024 / 1024)


def cleanup(material_id: str, keep_video: bool) -> None:
    """次の晩のために場所を空ける。

    動画はYouTubeに上がっているので手元には残さない。毎日1本を貯めると
    ひと月で約4GB になり、この機械の空き容量では回らないため。
    作り直したいときは絵コンテと教材から再生成できる。
    サムネ・字幕・絵コンテ（数MB）だけ残す。
    """
    base = APP / "output" / "ondoku" / material_id
    freed = 0
    for pat in ("images_*", "clips_*", "audio", "audio_track.wav"):
        for p in base.glob(pat):
            if p.is_dir():
                freed += sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                freed += p.stat().st_size
                p.unlink()
    if not keep_video:
        for p in base.glob("*_illustrated.mp4"):
            freed += p.stat().st_size
            p.unlink()
    log(f"🧹 後片付け: {freed/1e6:.0f}MB 解放（空き {free_mb():,}MB）")


def main() -> int:
    ap = argparse.ArgumentParser(description="1日1本を作って予約公開する")
    ap.add_argument("--publish-at", default="07:00",
                    help="翌朝の公開時刻。既定 07:00")
    ap.add_argument("--topic-id", help="題材を指定（既定は在庫の先頭）")
    ap.add_argument("--id", help="教材IDを指定（既定は自動採番）")
    ap.add_argument("--privacy", default="unlisted",
                    choices=["private", "unlisted", "public"],
                    help="予約公開を使わない場合の公開範囲")
    ap.add_argument("--no-schedule", action="store_true",
                    help="予約公開せず、そのままの公開範囲で上げる")
    ap.add_argument("--keep-files", action="store_true",
                    help="中間ファイルと動画を消さない（確認したいとき用）")
    ap.add_argument("--min-free-mb", type=int, default=MIN_FREE_MB,
                    help="この空き容量を下回っていたら実行しない")
    a = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if free_mb() < a.min_free_mb:
        raise SystemExit(f"❌ ディスクの空きが {free_mb():,}MB しかありません。"
                         f"{a.min_free_mb:,}MB 以上空けてください。")
    log(f"ディスク空き {free_mb():,}MB")

    # 1. 教材本文
    cmd = [sys.executable, "-u", "ondoku_kyoyo.py"]
    if a.topic_id:
        cmd += ["--topic-id", a.topic_id]
    if a.id:
        cmd += ["--id", a.id]
    out = run(cmd, "教材本文を生成")
    mid = a.id or out.strip().splitlines()[-1].strip()
    if not mid.endswith("L"):
        raise SystemExit(f"❌ 教材IDを取れませんでした: {mid!r}")
    log(f"教材ID: {mid}")

    # 2. 絵コンテ（illustrated プロファイルにも保存される）
    run([sys.executable, "-u", "ondoku_storyboard.py", "--id", mid,
         "--style", "handdrawn", "--profile", "illustrated"], "絵コンテ")

    # 3. 画像
    run([sys.executable, "-u", "ondoku_images.py", "--id", mid,
         "--profile", "illustrated"], "画像")

    # 4. 音声
    run([sys.executable, "-u", "ondoku_audio.py", "--id", mid], "音声")

    # 5. 書き出し
    run([sys.executable, "-u", "ondoku_video.py", "--id", mid,
         "--profile", "illustrated"], "書き出し")

    # 6. 字幕
    run([sys.executable, "-u", "ondoku_subtitles.py", "--id", mid,
         "--lang", "ja", "--offset", "4.5"], "字幕")

    # 7. サムネイル（絵コンテの中で一番大きい絵を使う）
    sb_path = APP / "output" / "ondoku" / f"{mid}_storyboard_illustrated.json"
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    img_dir = APP / "output" / "ondoku" / mid / "images_illustrated"
    base_img = max(img_dir.glob("s*.png"), key=lambda p: p.stat().st_size)
    title_ja = sb.get("title_ja", "")
    title_en = sb["meta"].get("material_title", "")
    thumb = APP / "output" / "ondoku" / mid / f"{mid}_thumb.png"
    run([sys.executable, "-u", "ondoku_thumbnail.py",
         "--base", str(base_img), "--out", str(thumb),
         "--title-en", title_en, "--title-ja", title_ja,
         "--zoom", "1.28", "--shift-x", "0.12"], "サムネイル")

    # 8. アップロード
    desc = APP / "output" / "ondoku" / mid / "description.txt"
    desc.write_text(sb.get("youtube_description", ""), encoding="utf-8")
    pl = subprocess.run([sys.executable, "ondoku_playlists.py", "--id", mid],
                        cwd=str(APP), capture_output=True, text=True).stdout.strip()
    video = APP / "output" / "ondoku" / mid / f"{mid}_illustrated.mp4"
    srt = APP / "output" / "ondoku" / f"{mid}.ja.srt"
    cands = sb.get("youtube_title_candidates") or [title_ja]
    cmd = [sys.executable, "-u", "ondoku_upload.py",
           "--video", str(video), "--title", cands[0],
           "--description-file", str(desc), "--thumbnail", str(thumb),
           "--captions", str(srt), "--playlist", pl,
           "--tags", "英語学習,英語リスニング,多読,音読,教養英語,A2,B1"]
    if a.no_schedule:
        cmd += ["--privacy", a.privacy]
    else:
        when = datetime.now() + timedelta(days=1)
        hh, mm = a.publish_at.split(":")
        when = when.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        cmd += ["--publish-at", when.strftime("%Y-%m-%d %H:%M")]
        log(f"公開予約: {when:%Y-%m-%d %H:%M}")
    out = run(cmd, "アップロード")
    url = next((l.strip() for l in out.splitlines()
                if l.strip().startswith("https://www.youtube.com/watch")), "")

    if not a.keep_files:
        cleanup(mid, keep_video=False)

    log(f"✅ 完了 {mid}  {url}  （{(time.time()-t0)/60:.0f}分）")
    (LOG_DIR / f"{datetime.now():%Y%m%d}.txt").write_text(
        f"{datetime.now():%Y-%m-%d %H:%M}\t{mid}\t{url}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
