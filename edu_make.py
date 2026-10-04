"""キャラ解説ショートを1本作って、気合のアプリ（/admin/sns-videos）に承認待ちで送る。

  python3 edu_make.py              … 次の題材（文法と単語を交互）で 台本→声→動画→説明文→送信
  python3 edu_make.py --id g001    … 作成済みのエピソードを送るだけ（無ければ作る。--topic/--kind が要る）
  python3 edu_make.py --no-send    … 送らずに動画まで

題材は edu/topics.json、使ったものは data/edu_made.json に記録する。
承認されると、Instagram と TikTok は気合のアプリの cron が、YouTube は sns_youtube_sync.py が予約投稿する。
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
EDU = ROOT / "edu"
OUT = ROOT / "output" / "edu"
TOPICS = EDU / "topics.json"
LEDGER = ROOT / "data" / "edu_made.json"

HASHTAGS = {
    "grammar": ["英文法", "英語学習", "英語", "気合イングリッシュ", "中学英語", "高校英語"],
    "word": ["英単語", "英語学習", "英語", "気合イングリッシュ", "単語", "英会話"],
}


def load_ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {"made": []}


def next_topic(ledger: dict) -> tuple[str, str, str]:
    """(id, kind, topic)。前回と違う種類を優先し、上から順にまだ使っていないもの"""
    topics = json.loads(TOPICS.read_text(encoding="utf-8"))
    used = {(m["kind"], m["topic"]) for m in ledger["made"]}
    last = ledger["made"][-1]["kind"] if ledger["made"] else "word"
    order = ["word", "grammar"] if last == "grammar" else ["grammar", "word"]
    for kind in order:
        for t in topics[kind]:
            if (kind, t) not in used:
                prefix = "g" if kind == "grammar" else "w"
                n = 1 + max([int(m["id"][1:]) for m in ledger["made"] if m["id"].startswith(prefix)] + [0]
                            + [int(p.stem[1:]) for p in (EDU / "episodes").glob(f"{prefix}[0-9]*.json")])
                return f"{prefix}{n:03d}", kind, t
    raise SystemExit("topics.json の題材を使い切りました。追加してください。")


def run(cmd: list[str], cwd: Path = ROOT):
    print("▶", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def duration(video: Path) -> float:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    r = subprocess.run([ff, "-i", str(video)], capture_output=True, text=True)
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def thumbnail(video: Path, out: Path):
    """冒頭のつかみ（タイトル画面）の1枚をサムネ・カバーにする"""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-v", "error", "-ss", "1.2", "-i", str(video), "-frames:v", "1", "-q:v", "3", str(out)], check=True)


def points(ep: dict) -> list[str]:
    """説明文に載せる要点（rule / compare / wrong / word の画面から拾う）"""
    pts: list[str] = []
    for b in ep["beats"]:
        v = b.get("visual") or {}
        k = v.get("kind")
        if k == "rule":
            pts += v.get("lines", [])
        elif k == "compare":
            pts.append(f"{v['a']['label']}：{v['a']['en']}（{v['a'].get('ja', '')}）")
            pts.append(f"{v['b']['label']}：{v['b']['en']}（{v['b'].get('ja', '')}）")
        elif k == "wrong":
            pts.append(f"× {v['wrong']} → ○ {v['right']}")
        elif k == "word":
            pts.append(f"{v['en']}：{v['ja']}" + (f"（{v['note']}）" if v.get("note") else ""))
    seen, uniq = set(), []
    for p in pts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq[:6]


def captions(ep: dict) -> dict:
    tags = HASHTAGS[ep["kind"]]
    pts = "\n".join(f"・{p}" for p in points(ep))
    hook = ep["title"]
    yt = (f"{hook}\n\n{pts}\n\n仙人と弟子たちの掛け合いで、英語のつまずきを1分で解決！\n"
          f"チャンネル登録で毎日1本届きます。\n\n" + " ".join(f"#{t}" for t in ["shorts", *tags]))
    ig = (f"{hook}\n\n{pts}\n\n保存して見返してね📌\n毎日12時に1本更新\n\n" + " ".join(f"#{t}" for t in tags + ["英語勉強", "英語の勉強"]))
    tt = f"{hook} " + " ".join(f"#{t}" for t in tags[:5])
    return {"youtube": yt, "instagram": ig, "tiktok": tt}


def main() -> int:
    ap = argparse.ArgumentParser(description="解説ショートを1本作って承認待ちに送る")
    ap.add_argument("--id")
    ap.add_argument("--kind", choices=["grammar", "word"])
    ap.add_argument("--topic")
    ap.add_argument("--no-send", action="store_true")
    a = ap.parse_args()

    ledger = load_ledger()
    if a.id:
        ep_id = a.id
        ep_file = EDU / "episodes" / f"{ep_id}.json"
        if not ep_file.exists():
            if not (a.kind and a.topic):
                raise SystemExit(f"{ep_file} が無いので --kind と --topic を指定してください")
            run([sys.executable, "edu_script.py", "--id", ep_id, "--kind", a.kind, "--format", "short", "--topic", a.topic])
    else:
        ep_id, kind, topic = next_topic(ledger)
        print(f"🎯 {ep_id}：{topic}（{kind}）")
        run([sys.executable, "edu_script.py", "--id", ep_id, "--kind", kind, "--format", "short", "--topic", topic])
    ep = json.loads((EDU / "episodes" / f"{ep_id}.json").read_text(encoding="utf-8"))

    video = OUT / f"{ep_id}.mp4"
    if not video.exists():
        run(["node", "scripts/voice.mjs", ep_id], cwd=EDU)
        run(["node", "scripts/render.mjs", ep_id], cwd=EDU)
    thumbnail(video, OUT / f"{ep_id}.jpg")

    yt_title = ep.get("youtube_title") or ep["title"]
    if "#shorts" not in yt_title.lower() and len(yt_title) <= 90:
        yt_title += " #shorts"
    meta = {"kind": ep["kind"], "title": yt_title[:100], "captions": captions(ep),
            "tags": HASHTAGS[ep["kind"]], "durationSec": round(duration(video), 1)}
    (OUT / f"{ep_id}.sns.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    if not any(m["id"] == ep_id for m in ledger["made"]):
        ledger["made"].append({"id": ep_id, "kind": ep["kind"], "topic": ep.get("topic", "")})
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")

    if a.no_send:
        print(f"✅ {video}（送信はしていません）")
        return 0
    run(["node", "scripts/upload_sns.mjs", ep_id], cwd=EDU)
    return 0


if __name__ == "__main__":
    sys.exit(main())
