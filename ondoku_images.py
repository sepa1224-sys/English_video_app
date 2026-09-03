"""プロファイルの絵コンテからイラスト/写真を生成する。"""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
from ondoku_profiles import PROFILES, DEFAULT_PROFILE, paths, IMAGE_COST

MAX_PROMPT = 800   # z_image はこれを超えると失敗する


def download(url: str, dest: Path) -> bool:
    """urllib は macOS の証明書設定で失敗するため curl を使う。"""
    import shutil
    if shutil.which("curl"):
        r = subprocess.run(["curl", "-sSL", "--fail", "-o", str(dest), url],
                           capture_output=True, text=True)
        if r.returncode == 0 and dest.exists() and dest.stat().st_size > 0:
            return True
    # curl が無い環境（古いWindowsなど）向けの代替
    try:
        import requests
        with requests.get(url, stream=True, timeout=180) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fp:
                for chunk in resp.iter_content(1 << 16):
                    fp.write(chunk)
    except Exception:
        return False
    return dest.exists() and dest.stat().st_size > 0


def build_prompt(scene: dict, prof: dict) -> str:
    p = scene.get("prompt_full") or scene["prompt"]
    # 否定形は効かないため、外見を肯定形で先頭に置いて主題を固定する
    for key, note in (prof.get("accuracy") or {}).items():
        if key in scene["prompt"].lower() and note not in p:
            p = f"{note}. {p}"
    return p[:MAX_PROMPT]


def main() -> int:
    ap = argparse.ArgumentParser(description="プロファイルの画像を生成")
    ap.add_argument("--id", required=True)
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    ap.add_argument("--only", help="シーン番号をカンマ区切りで指定（例: 1,2,7）")
    a = ap.parse_args()

    prof = PROFILES[a.profile]
    P = paths(a.id, a.profile)
    sb = json.loads(P["storyboard"].read_text(encoding="utf-8"))
    scenes = sb["scenes"]
    # prompt_full は prompt に画風を足しただけのもの。両者がずれていると、
    # prompt を書き直しても古い prompt_full が使われて絵が変わらない。
    suffix = (sb.get("meta") or {}).get("style_suffix", "")
    for sc in scenes:
        pf = sc.get("prompt_full")
        if pf and not pf.startswith(sc["prompt"][:60]):
            sc["prompt_full"] = f"{sc['prompt']}, {suffix}" if suffix else sc["prompt"]
            print(f"  ↻ s{sc['id']:02d}: prompt_full を prompt に合わせ直しました")
    if a.only:
        want = {int(x) for x in a.only.split(",")}
        scenes = [s for s in scenes if s["id"] in want]
    P["images"].mkdir(parents=True, exist_ok=True)

    print(f"{a.profile} / {prof['style']} / {prof['image_model']} "
          f"— {len(scenes)}枚 (約{IMAGE_COST.get(prof['image_model'],0)*len(scenes):.1f}クレジット)")
    ok = 0
    for s in scenes:
        f = P["images"] / f"s{s['id']:02d}.png"
        if f.exists() and f.stat().st_size > 0:
            print(f"  [{s['id']:2d}] スキップ"); ok += 1; continue
        r = subprocess.run(
            ["higgsfield", "generate", "create", prof["image_model"],
             "--prompt", build_prompt(s, prof), "--aspect_ratio", "16:9", "--wait"],
            capture_output=True, text=True)
        m = re.findall(r"https://\S+\.(?:png|jpg|webp)", r.stdout + r.stderr)
        if not m:
            print(f"  [{s['id']:2d}] ❌ 失敗"); continue
        if not download(m[-1], f):
            print(f"  [{s['id']:2d}] ❌ ダウンロード失敗"); continue
        print(f"  [{s['id']:2d}] ✅ {f.name} {f.stat().st_size/1e6:.1f}MB"); ok += 1
    print(f"完了: {ok}/{len(scenes)}")
    return 0 if ok == len(scenes) else 1


if __name__ == "__main__":
    sys.exit(main())
