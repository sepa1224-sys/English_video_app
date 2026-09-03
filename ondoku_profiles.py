"""音読動画の制作プロファイル。

系統ごとに「絵柄・画像モデル・どのシーンを何で動かすか」をまとめて持つ。
クレジット単価は higgsfield generate cost の実測値（2026-09-01 時点）。
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

OUTPUT_DIR = Path("output/ondoku")

# 実測単価（クレジット/秒）。cost 照会が通らないモデルは実消費から算出。
RATES = {
    "seedance_2_0":     {"1080p": 9.0, "720p": 4.5, "4k": 22.0},
    "seedance_2_5":     {"1080p": 9.0, "720p": 6.5},
    "kling3_0_turbo":   {"1080p": 2.0, "720p": 1.5},
    "kling2_6":         {"1080p": 2.0},
    "seedance_2_0_mini": {"720p": 2.5},
}
IMAGE_COST = {"z_image": 0.15, "nano_banana_2": 2.0, "gpt_image_2": 7.0}

PROFILES = {
    # 系統1: TED-Ed / Kurzgesagt 路線。安く量を出す。
    "illustrated": {
        "label": "イラスト（手描き水彩・参照動画のタッチ）",
        "style": "handdrawn",
        "image_model": "z_image",
        "hero": None,                 # 冒頭アニメなし
        "support": None,              # 全編 静止画＋カメラワーク
        "note": "静止画＋カメラワークのみ。1本あたり数クレジットで量産できる。",
        # z_image はアマツバメをツバメに描き、"swift"を「素早く落ちる人」と
        # 取り違えることがある。主題を肯定形で先頭に固定して防ぐ。
        "accuracy": {
            "swift": ("A common swift (Apus apus), a bird: plumage entirely sooty "
                      "blackish-brown with only a small pale grey throat patch, "
                      "long narrow stiff sickle-shaped wings held rigid like a "
                      "boomerang, very short shallowly forked tail without "
                      "streamers, tiny bill, extremely short legs tucked away. "
                      "The subject is this bird, never a person"),
        },
    },
    # 系統2: 実写ドキュメンタリー路線。冒頭に予算を集中させる。
    "cinematic": {
        "label": "実写ドキュメンタリー（高品質・ダイナミック）",
        "style": "documentary",
        "image_model": "nano_banana_2",   # z_image はアマツバメをツバメに描くため
        "hero": {"model": "seedance_2_0", "resolution": "1080p", "duration": 10},
        "support": {"model": "kling3_0_turbo", "resolution": "1080p",
                    "duration": 10, "count": 2},
        "note": "冒頭1カットだけ Seedance 2.0、要所2カットは Kling 3.0 Turbo。",
        # 実写は種の形が誤ると一目で分かるため、形状を明示して補正する
        "accuracy": {
            "swift": ("A common swift (Apus apus): plumage entirely sooty "
                      "blackish-brown above and below with only a small pale "
                      "grey throat patch, uniformly dark underparts, long "
                      "narrow stiff sickle-shaped wings held rigid like a "
                      "boomerang, very short shallowly forked tail without "
                      "streamers, tiny bill, extremely short legs tucked away"),
        },
    },
}
DEFAULT_PROFILE = "illustrated"


def paths(material_id: str, profile: str) -> dict:
    """系統ごとに成果物を完全に分ける。旧 images/ clips/ は過去資産として触らない。"""
    base = OUTPUT_DIR / material_id
    d = {
        "storyboard": OUTPUT_DIR / f"{material_id}_storyboard_{profile}.json",
        "images": base / f"images_{profile}",
        "clips": base / f"clips_{profile}",
        "video": base / f"{material_id}_{profile}.mp4",
    }
    return d


def animated_scenes(profile: dict, n_scenes: int) -> dict[int, dict]:
    """シーン番号 -> 動画生成の設定。冒頭は1、要所は残りを等間隔に選ぶ。"""
    plan: dict[int, dict] = {}
    if profile["hero"]:
        plan[1] = dict(profile["hero"], role="hero")
    sup = profile["support"]
    if sup and sup.get("count"):
        # 冒頭を除いた範囲から等間隔で拾う
        pool = [i for i in range(2, n_scenes + 1)]
        k = min(sup["count"], len(pool))
        if k:
            step = len(pool) / k
            for j in range(k):
                plan[pool[int(j * step)]] = dict(sup, role="support")
    return plan


def estimate(profile_name: str, n_scenes: int) -> dict:
    p = PROFILES[profile_name]
    img = IMAGE_COST.get(p["image_model"], 0) * n_scenes
    plan = animated_scenes(p, n_scenes)
    vid = 0.0
    for cfg in plan.values():
        rate = RATES.get(cfg["model"], {}).get(cfg["resolution"])
        if rate is None:
            raise KeyError(f'単価が未登録: {cfg["model"]} / {cfg["resolution"]}')
        vid += rate * cfg["duration"]
    return {"images": img, "video": vid, "total": img + vid, "plan": plan}


def main() -> int:
    ap = argparse.ArgumentParser(description="制作プロファイルの確認と見積もり")
    ap.add_argument("--id", help="教材ID。指定するとシーン数を実データから読む")
    ap.add_argument("--scenes", type=int, default=12, help="シーン数（--id 未指定時）")
    a = ap.parse_args()

    n = a.scenes
    if a.id:
        f = OUTPUT_DIR / f"{a.id}_storyboard.json"
        if f.exists():
            n = len(json.loads(f.read_text(encoding="utf-8"))["scenes"])
        else:
            print(f"⚠ {f} が無いので --scenes {n} で計算します")

    print(f"シーン数: {n}\n")
    for name, p in PROFILES.items():
        e = estimate(name, n)
        print(f"■ {name} — {p['label']}")
        print(f"   絵柄: {p['style']} / 画像: {p['image_model']}")
        print(f"   {p['note']}")
        if e["plan"]:
            for i in sorted(e["plan"]):
                c = e["plan"][i]
                r = RATES[c["model"]][c["resolution"]]
                print(f"   シーン{i:2d} [{c['role']:7}] {c['model']} "
                      f"{c['duration']}秒 {c['resolution']} = {r * c['duration']:.0f}")
        print(f"   画像 {e['images']:.1f} + 動画 {e['video']:.0f} "
              f"= 1本 {e['total']:.1f} クレジット")
        print(f"   月8本（週2本）: {e['total'] * 8:.0f} クレジット\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


def materials_dir() -> Path:
    """音読教材の置き場所を返す。

    機械によって置き場所が違う（開発機では ~/kiai-coaching-app/materials、
    生成機では英語アプリ配下）。環境変数 KIAI_MATERIALS_DIR があればそれを使い、
    無ければ順に探して、見つからなければアプリ直下の materials/ を作る。
    """
    import os
    env = os.getenv("KIAI_MATERIALS_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent
    for cand in (Path.home() / "kiai-coaching-app" / "materials",
                 here / "materials"):
        if cand.is_dir():
            return cand
    d = here / "materials"
    d.mkdir(parents=True, exist_ok=True)
    return d
