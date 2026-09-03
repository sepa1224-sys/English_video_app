"""プロファイルの計画に沿って、指定シーンだけ動画クリップを生成する。

出力先は output/ondoku/<id>/clips/sNN.mp4。
ondoku_video.py はこのファイルがあるシーンを自動でアニメに切り替える。
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
import imageio_ffmpeg
from pathlib import Path

from ondoku_profiles import PROFILES, DEFAULT_PROFILE, animated_scenes, estimate, paths

OUTPUT_DIR = Path("output/ondoku")
MOTION = (
    "Preserve the exact look of the source image: same style, same colors, "
    "same composition. Add natural continuous motion for the entire duration "
    "with no freezing and no style change. {extra} "
    "Subtle living detail throughout. No text, no captions, no watermark."
)


def download(url: str, dest: Path) -> bool:
    """urllib は macOS の証明書設定で失敗するため curl を使う。"""
    r = subprocess.run(["curl", "-sSL", "--fail", "-o", str(dest), url],
                       capture_output=True, text=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 0


def credits() -> float:
    out = subprocess.run(["higgsfield", "account", "status", "--json"],
                         capture_output=True, text=True).stdout
    return float(json.loads(out)["credits"])



FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def last_frame(clip: Path, out: Path) -> bool:
    """クリップの最終フレームを取り出す。続きを生成する起点にする。"""
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-sseof", "-0.2",
                        "-i", str(clip), "-frames:v", "1", str(out)],
                       capture_output=True, text=True)
    return r.returncode == 0 and out.exists()


def concat(parts: list[Path], out: Path) -> bool:
    """複数クリップを1本に繋ぐ。"""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat",
                        "-safe", "0", "-i", str(lst), "-c", "copy", str(out)],
                       capture_output=True, text=True)
    lst.unlink(missing_ok=True)
    return r.returncode == 0 and out.exists()


def scene_spans(material_id: str, sb: dict) -> dict[int, float]:
    """シーンごとの実尺（秒）。音声のタイミングから求める。"""
    t = json.loads((OUTPUT_DIR / f"{material_id}_timing.json").read_text(encoding="utf-8"))
    of = {sid: sc["id"] for sc in sb["scenes"] for sid in sc["sentence_ids"]}
    span: dict[int, list[float]] = {}
    for x in t["sentences"]:
        sc = of[x["id"]]
        st, en = x["start"], x["start"] + x["duration"]
        span.setdefault(sc, [st, en])[1] = en
    return {k: v[1] - v[0] for k, v in span.items()}


_PARAM_CACHE: dict[str, set[str]] = {}


def supported_params(model: str) -> set[str]:
    """モデルが受け付けるパラメータ名。渡せない引数でジョブを落とさないため。"""
    if model not in _PARAM_CACHE:
        out = subprocess.run(["higgsfield", "model", "get", model],
                             capture_output=True, text=True).stdout
        names = set()
        for line in out.splitlines()[2:]:          # ヘッダ2行を飛ばす
            tok = line.split()
            if tok and tok[0].islower():
                names.add(tok[0])
        _PARAM_CACHE[model] = names
    return _PARAM_CACHE[model]


def generate(model: str, still: Path, out: Path, prompt: str,
             duration: int, resolution: str) -> bool:
    ok = supported_params(model)
    cmd = ["higgsfield", "generate", "create", model,
           "--prompt", prompt, "--start-image", str(still)]
    for flag, val in (("duration", str(duration)), ("resolution", resolution),
                      ("generate_audio", "false")):
        if flag in ok:
            cmd += [f"--{flag}", val]
    cmd.append("--wait")
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.findall(r"https://\S+\.mp4", r.stdout + r.stderr)
    if not m:
        print(f"    ❌ 動画URLが返らなかった\n    {(r.stdout + r.stderr)[-300:]}")
        return False
    return download(m[-1], out)


def build_scene(model: str, still: Path, out: Path, prompt: str,
                need: float, resolution: str, work: Path) -> tuple[bool, int]:
    """1シーン分のクリップを作る。尺が足りなければ続きを繋ぐ。

    2本目以降は前クリップの最終フレームから始めるので、繋ぎ目で絵が飛ばない。
    戻り値: (成功したか, 購入した秒数)
    """
    work.mkdir(parents=True, exist_ok=True)
    parts, bought, start = [], 0, still
    while sum(10 if i else (5 if need <= 5 else 10)
              for i in range(len(parts) + 1)) < need + (0 if parts else 0):
        break
    # 必要な本数を先に決める（1本目は5秒か10秒、2本目以降は10秒）
    if need <= 5:
        plan = [5]
    else:
        plan, acc = [10], 10.0
        while acc < need:
            plan.append(10); acc += 10
    for n, dur in enumerate(plan, 1):
        part = work / f"{out.stem}_p{n}.mp4"
        if not (part.exists() and part.stat().st_size > 0):
            tail = "" if n == 1 else " Continue the motion smoothly from this moment."
            if not generate(model, start, part, prompt + tail, dur, resolution):
                return False, bought
        bought += dur
        parts.append(part)
        if n < len(plan):
            f = work / f"{out.stem}_p{n}_last.png"
            if not last_frame(part, f):
                return False, bought
            start = f
    ok = concat(parts, out) if len(parts) > 1 else bool(parts[0].replace(out) or True)
    return ok and out.exists(), bought


def main() -> int:
    ap = argparse.ArgumentParser(description="プロファイルに沿ってクリップを生成")
    ap.add_argument("--id", required=True)
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    ap.add_argument("--all-scenes", action="store_true",
                    help="全シーンをアニメにする（尺に合わせて本数を決める）")
    ap.add_argument("--model", default="kling3_0_turbo")
    ap.add_argument("--resolution", default="1080p")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    P = paths(a.id, a.profile)
    sb = json.loads(P["storyboard"].read_text(encoding="utf-8"))
    scenes = {s["id"]: s for s in sb["scenes"]}

    if not a.all_scenes:
        est = estimate(a.profile, len(scenes))
        plan = {i: dict(c, need=float(c["duration"])) for i, c in est["plan"].items()}
    else:
        spans = scene_spans(a.id, sb)
        plan = {i: {"model": a.model, "resolution": a.resolution,
                    "need": spans[i], "role": "full"} for i in sorted(scenes)}

    done = {i for i in plan
            if (P["clips"] / f"s{i:02d}.mp4").exists()
            and (P["clips"] / f"s{i:02d}.mp4").stat().st_size > 0}
    if done:
        print(f"生成済みのためスキップ: {len(done)}シーン {sorted(done)}")
        plan = {i: c for i, c in plan.items() if i not in done}
    if not plan:
        print("すべて生成済みです")
        return 0

    RATE = {"1080p": 2.0, "720p": 1.5}
    total = 0
    for i, c in plan.items():
        need = c["need"]
        secs = 5 if need <= 5 else 10 * -(-int(need * 100) // 1000)
        total += secs * RATE.get(c["resolution"], 2.0)
    print(f"プロファイル: {a.profile} / 対象 {len(plan)}シーン / 見込み {total:.0f} クレジット")
    if a.dry_run:
        for i, c in plan.items():
            print(f"  s{i:02d} {c['need']:5.1f}秒")
        return 0

    have = credits()
    if have < total:
        print(f"❌ 残高不足: {have:.1f} < {total:.0f}")
        return 1
    print(f"残高: {have:.1f}\n")

    P["clips"].mkdir(parents=True, exist_ok=True)
    work = P["clips"] / "_parts"
    ok = 0
    for i in sorted(plan):
        c = plan[i]
        still = P["images"] / f"s{i:02d}.png"
        out = P["clips"] / f"s{i:02d}.mp4"
        if out.exists() and out.stat().st_size > 0:
            print(f"  s{i:02d} スキップ（生成済み）"); ok += 1; continue
        if not still.exists():
            print(f"  s{i:02d} ❌ 元画像なし"); continue
        extra = scenes[i].get("motion_prompt") or scenes[i].get("prompt", "")[:170]
        before = credits()
        good, bought = build_scene(c["model"], still, out,
                                   MOTION.format(extra=extra), c["need"],
                                   c["resolution"], work)
        used = before - credits()
        if good:
            print(f"  s{i:02d} ✅ {c['need']:4.1f}秒に対し{bought}秒購入 （消費 {used:.0f}）"); ok += 1
        else:
            print(f"  s{i:02d} ❌ 失敗 （消費 {used:.0f}）")

    print(f"\n完了: {ok}/{len(plan)}  残高 {credits():.1f}")
    return 0 if ok == len(plan) else 1


if __name__ == "__main__":
    sys.exit(main())
