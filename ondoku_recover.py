"""通信断などで取りこぼした、課金済みクリップを拾い直す。

Higgsfield 側でジョブが完成していても、CLI が切断で URL を受け取れないと
成果物だけ手元に残らない。完了ジョブを新しい順に並べ、
まだファイルが無いシーンへ順に割り当てて回収する。
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

from ondoku_profiles import PROFILES, DEFAULT_PROFILE, paths
from PIL import Image
import imageio_ffmpeg

from ondoku_animate import download

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def completed_videos(limit: int = 60) -> list[tuple[str, str]]:
    """(ジョブID, mp4のURL) を新しい順に返す。"""
    out = subprocess.run(["higgsfield", "generate", "list", "--json"],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except Exception:
        return []
    items = d if isinstance(d, list) else d.get("items", d.get("data", d.get("jobs", [])))
    res = []
    for it in items[:limit]:
        if (it.get("status") or it.get("state")) != "completed":
            continue
        urls: list[str] = []
        def walk(o):
            if isinstance(o, dict):
                for v in o.values():
                    if isinstance(v, str) and v.startswith("http") and ".mp4" in v:
                        urls.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(it)
        if urls:
            res.append((str(it.get("id", "?")), list(dict.fromkeys(urls))[-1]))
    return res


def first_frame(clip: Path, out: Path) -> bool:
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(clip),
                        "-frames:v", "1", str(out)], capture_output=True, text=True)
    return r.returncode == 0 and out.exists()


def signature(path: Path, n: int = 32):
    """小さなグレースケールにして数値の並びにする。絵の同一性の判定用。"""
    im = Image.open(path).convert("L").resize((n, n), Image.LANCZOS)
    px = list(im.getdata())
    avg = sum(px) / len(px)
    return [v - avg for v in px]


def distance(a, b) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def main() -> int:
    ap = argparse.ArgumentParser(description="取りこぼしたクリップを回収")
    ap.add_argument("--id", required=True)
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    ap.add_argument("--scenes", help="対象シーンをカンマ区切りで限定（例: 4,5,6,7）")
    ap.add_argument("--max-distance", type=float, default=18.0,
                    help="この値より離れていたら別物とみなす")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    P = paths(a.id, a.profile)
    sb = json.loads(P["storyboard"].read_text(encoding="utf-8"))
    n = len(sb["scenes"])
    missing = [i for i in range(1, n + 1)
               if not (P["clips"] / f"s{i:02d}.mp4").exists()]
    if a.scenes:
        want = {int(x) for x in a.scenes.split(",")}
        missing = [i for i in missing if i in want]
    if not missing:
        print("未取得のシーンはありません")
        return 0

    sigs = {i: signature(P["images"] / f"s{i:02d}.png") for i in missing
            if (P["images"] / f"s{i:02d}.png").exists()}
    print(f"対象シーン: {missing}")

    vids = completed_videos()
    print(f"完了ジョブ(動画): {len(vids)}件 — 内容を照合します\n")

    tmp = P["clips"] / "_recover"
    tmp.mkdir(parents=True, exist_ok=True)
    taken, plan = set(), {}
    for jid, url in vids:
        c = tmp / f"{jid[:8]}.mp4"
        if not c.exists() and not download(url, c):
            continue
        f = tmp / f"{jid[:8]}.png"
        if not first_frame(c, f):
            continue
        cand = [(distance(sigs[i], signature(f)), i) for i in sigs if i not in taken]
        if not cand:
            continue
        d, best = min(cand)
        if d <= a.max_distance:
            taken.add(best)
            plan[best] = (jid, c, d)
            print(f"  s{best:02d} <- {jid[:8]}  一致度 {d:.1f}")
        else:
            print(f"  （{jid[:8]} は一致するシーンなし 最小 {d:.1f}）")

    nomatch = [i for i in missing if i not in plan]
    print(f"\n照合できた: {sorted(plan)} / できなかった: {nomatch}")
    if a.apply:
        for i, (jid, c, d) in plan.items():
            c.replace(P["clips"] / f"s{i:02d}.mp4")
            print(f"  ✅ s{i:02d}.mp4 を復元")
    else:
        print("\n--apply で確定します")
    return 0


if __name__ == "__main__":
    sys.exit(main())
