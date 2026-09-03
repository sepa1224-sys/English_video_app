"""
ondoku_camera.py — 既存の絵コンテにカメラワークを割り当てる

絵コンテを作り直すとシーン番号とイラストの対応が崩れるため、
camera フィールドだけを追記する。
"""

import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

import anthropic

from podcast_script_gen import _extract_tool_input, _validate_model
from ondoku_render import CAMERA_MOVES

OUTPUT_DIR = Path("output") / "ondoku"

CAMERA_TOOL = {
    "name": "submit_camera_plan",
    "description": "各シーンにカメラワークを割り当てる。",
    "input_schema": {
        "type": "object",
        "properties": {
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "camera": {
                            "type": "string",
                            "enum": sorted(CAMERA_MOVES),
                        },
                        "reason": {
                            "type": "string",
                            "description": "なぜその動きなのか（10〜30字）",
                        },
                    },
                    "required": ["id", "camera", "reason"],
                },
            },
        },
        "required": ["scenes"],
    },
}

SYSTEM_PROMPT = """あなたは映像作品のカメラマンです。
静止画の連続で構成される解説動画に、シーンごとのカメラワークを付けてください。

## 使える動き
- push_in   ゆっくり寄る。対象に注目させたいとき
- pull_out  ゆっくり引く。全体像や状況を見せたいとき
- pan_right 右へ流す。移動・進行・時間の経過
- pan_left  左へ流す。回帰・振り返り
- tilt_up   下から上へ。上昇・высот・見上げる対象
- tilt_down 上から下へ。落下・地上へ降りる
- zoom_pan  寄りながら右へ流す。動きのある場面
- rise      引きながら上へ。開放感・スケールの拡大
- static    動かさない。ここぞの一枚を見せるとき

## 割り当ての原則
1. **描かれている内容に合わせる。** 空へ上昇する場面なら tilt_up、
   地面に降りる場面なら tilt_down、渡りの場面なら pan_right。
2. **同じ動きを3回以上連続させない。** 単調になる。
3. push_in ばかりにしない。全体の3割以下に抑える。
4. static は1本に多くて1回。ここぞという場面にだけ使う。
5. 直前のシーンと逆方向の動きを続けると視線が振られるので避ける。"""


def assign_cameras(material_id: str) -> dict | None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません。")

    path = OUTPUT_DIR / f"{material_id}_storyboard.json"
    sb = json.loads(path.read_text(encoding="utf-8"))

    sent = {s["id"]: s for s in sb["sentences"]}
    lines = []
    for sc in sb["scenes"]:
        text = " ".join(sent[i]["en"] for i in sc["sentence_ids"] if i in sent)
        lines.append(f"シーン{sc['id']}: {sc['prompt']}\n  本文: {text}")
    user_prompt = "以下のシーンにカメラワークを割り当ててください。\n\n" + "\n\n".join(lines)

    model = _validate_model(os.getenv("PODCAST_SCRIPT_MODEL", "claude-opus-5"))
    client = anthropic.Anthropic(api_key=api_key)

    print(f"🎥 カメラワークを割り当て中... (model: {model})")
    res = client.messages.create(
        model=model, max_tokens=4096, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[CAMERA_TOOL],
        tool_choice={"type": "tool", "name": CAMERA_TOOL["name"]},
    )
    plan = _extract_tool_input(res, CAMERA_TOOL["name"])
    if plan is None:
        print("❌ tool_use ブロックが返りませんでした。")
        return None

    by_id = {p["id"]: p for p in plan["scenes"]}
    missing = [sc["id"] for sc in sb["scenes"] if sc["id"] not in by_id]
    if missing:
        print(f"⚠ 割り当てが無いシーン {missing} は {'push_in'} にします")

    for sc in sb["scenes"]:
        p = by_id.get(sc["id"])
        sc["camera"] = p["camera"] if p else "push_in"
        sc["camera_reason"] = p["reason"] if p else "既定"

    path.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 保存: {path}\n")
    for sc in sb["scenes"]:
        print(f"  シーン{sc['id']:2d}  {sc['camera']:<10} {sc['camera_reason']}")
    return sb


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="絵コンテにカメラワークを割り当てる")
    ap.add_argument("--id", required=True)
    a = ap.parse_args()
    if assign_cameras(a.id) is None:
        raise SystemExit(1)
