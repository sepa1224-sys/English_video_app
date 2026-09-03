"""題材の在庫から「英語で聞く教養」の教材本文を生成する。

出力は音読教材と同じ reading_materials スキーマ（materials/<id>.json）。
手で書いていた工程を自動化し、毎日の生成に載せるためのもの。
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import date
from pathlib import Path

from ondoku_profiles import materials_dir

import anthropic
from dotenv import load_dotenv

TOPICS = Path("topics_kyoyo.json")
MATERIALS = materials_dir()

SYSTEM = """あなたは英語学習教材の書き手です。日本の学習者（CEFR A2-B1）に向けて、
教養テーマを「やさしい英語」で読ませる本文を書きます。

守ること:
- 1文は短く。平均12語、最長20語まで。関係代名詞の多重修飾は使わない。
- 語彙はA2-B1。難語を使うときは、その場で言い換えて説明する。
- 事実に忠実に。年号・数値・固有名詞は確かなものだけを書く。曖昧なら書かない。
- 冒頭2文で「逆説」を提示して引き込む。数字を入れる。
- 分量を必ず守ること。ここが最も重要:
  * 段落は14〜16
  * 1段落あたり5〜6文（少なくしない）
  * 全体で75〜85文、640〜720語
  読み上げて約5分になる分量です。短いと動画として成立しません。
- 最後は読者に問いかけるか、日常の景色が変わる一文で締める。
- 各文を意味のかたまり（チャンク）に割り、SVOラベルを付ける。
  S=主語 V=動詞 O=目的語 C=補語 M=修飾(前置詞句・副詞など) +=接続詞
- チャンクは3〜6語程度。長すぎると読みにくい。
"""

TOOL = {
    "name": "write_material",
    "description": "音読教材の本文を書く",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_en": {"type": "string", "description": "英語タイトル。5語以内"},
            "title_ja": {"type": "string",
                         "description": "日本語タイトル。数字＋逆説の型。20字以内"},
            "theme": {"type": "string", "description": "教養（分野・題材）の形式"},
            "phrases": {
                "type": "array", "minItems": 4, "maxItems": 5,
                "description": "本文で使った、覚える価値のある熟語",
                "items": {
                    "type": "object",
                    "properties": {"en": {"type": "string"}, "ja": {"type": "string"}},
                    "required": ["en", "ja"],
                },
            },
            "paragraphs": {
                "type": "array", "minItems": 12, "maxItems": 16,
                "description": "段落の配列。段落は文の配列",
                "items": {
                    "type": "array",
                    "description": "文の配列",
                    "items": {
                        "type": "array",
                        "description": "チャンクの配列",
                        "items": {
                            "type": "object",
                            "properties": {
                                "w": {"type": "string", "description": "語句"},
                                "l": {"type": "string",
                                      "enum": ["S", "V", "O", "C", "M", "+"]},
                            },
                            "required": ["w", "l"],
                        },
                    },
                },
            },
        },
        "required": ["title_en", "title_ja", "theme", "phrases", "paragraphs"],
    },
}


def pick_topic(field: str | None = None, topic_id: str | None = None) -> dict:
    data = json.loads(TOPICS.read_text(encoding="utf-8"))
    if topic_id:
        # 明示指定なら、使用済みでも作り直せるようにする
        for t in data["topics"]:
            if t["id"] == topic_id:
                return t
        raise SystemExit(f"題材 {topic_id} が見つかりません。")
    for t in data["topics"]:
        if t.get("used"):
            continue
        if field and t.get("field") != field:
            continue
        return t
    raise SystemExit("使える題材がありません。topics_kyoyo.json に足してください。")


def mark_used(topic_id: str, material_id: str) -> None:
    data = json.loads(TOPICS.read_text(encoding="utf-8"))
    for t in data["topics"]:
        if t["id"] == topic_id:
            t["used"] = True
            t["done_as"] = material_id
            t["done_on"] = date.today().isoformat()
    TOPICS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def next_material_id() -> str:
    used = set()
    for f in MATERIALS.glob("*L.json"):
        stem = f.stem[:-1]
        if stem.isdigit():
            used.add(int(stem))
    n = max(used) + 1 if used else 60
    return f"{n:03d}L"


def build(topic: dict, material_id: str) -> Path:
    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY がありません。")
    model = os.getenv("PODCAST_SCRIPT_MODEL", "claude-opus-5")
    client = anthropic.Anthropic(api_key=key)
    prompt = (f"題材: {topic['title_ja']}\n"
              f"分野: {topic['field']}\n"
              f"核となる事実: {topic['hook']}\n\n"
              "この題材で、A2-B1の本文を書いてください。")
    msgs = [{"role": "user", "content": prompt}]
    data = None
    for attempt in range(1, 4):
        print(f"📝 本文を生成中... ({model}, {attempt}回目)")
        r = client.messages.create(
            model=model, max_tokens=16384, system=SYSTEM,
            messages=msgs, tools=[TOOL],
            tool_choice={"type": "tool", "name": TOOL["name"]})
        cand = next((b.input for b in r.content if b.type == "tool_use"), None)
        if not cand:
            raise SystemExit("本文が返りませんでした。")
        w = sum(len(c["w"].split())
                for p_ in cand["paragraphs"] for s_ in p_ for c in s_)
        n = sum(len(p_) for p_ in cand["paragraphs"])
        if 560 <= w <= 820:
            data = cand
            break
        # 分量が外れたら、実測値を伝えて書き直させる
        print(f"   ⚠ {w}語 / {n}文。分量が外れたので書き直します")
        data = cand
        msgs = [{"role": "user", "content": prompt},
                {"role": "assistant", "content": [
                    {"type": "text",
                     "text": f"（{w}語・{n}文で書きました）"}]},
                {"role": "user", "content":
                    f"{w}語・{n}文では{'短すぎます' if w < 560 else '長すぎます'}。"
                    f"640〜720語・75〜85文になるよう書き直してください。"
                    f"段落を14〜16、1段落5〜6文にしてください。"}]
    if data is None:
        raise SystemExit("分量の条件を満たす本文が得られませんでした。")

    # モデルは文末の句読点を落とすことがある。読み上げの抑揚と字幕の見え方に
    # 響くので、ここで必ず補う。
    fixed = 0
    for para in data["paragraphs"]:
        for sent in para:
            if not sent:
                continue
            last = sent[-1]["w"].rstrip()
            if not last.endswith((".", "!", "?", '."', '!"', '?"', "…")):
                sent[-1]["w"] = last + "."
                fixed += 1
    if fixed:
        print(f"   句読点を補いました: {fixed}文")

    paras = []
    for para in data["paragraphs"]:
        flat = []
        for i, sent in enumerate(para):
            if i:
                flat.append({"gap": True})
            flat += [{"w": c["w"], "l": c["l"]} for c in sent]
        paras.append(flat)
    n_sent = sum(len(p) for p in data["paragraphs"])
    words = sum(len(c["w"].split()) for p in data["paragraphs"] for s in p for c in s)

    out = {
        "id": material_id,
        "title": data["title_en"],
        "theme": data["theme"],
        "level": "A2-B1",
        "dates": "動画版（5分）",
        "content": {"phrases": data["phrases"], "paragraphs": paras},
    }
    dest = MATERIALS / f"{material_id}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ {dest}")
    print(f"   {data['title_ja']} / {data['title_en']}")
    print(f"   段落 {len(paras)} / 文 {n_sent} / 語数 {words} → 約{words/130:.1f}分")
    if not 500 <= words <= 800:
        print(f"   ⚠ 語数が想定(600〜700)から外れています")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description="教養テーマの音読教材を作る")
    ap.add_argument("--topic-id", help="題材を指定（既定は在庫の先頭）")
    ap.add_argument("--field", help="分野で絞る")
    ap.add_argument("--id", help="教材ID（既定は自動採番）")
    ap.add_argument("--keep-topic", action="store_true", help="在庫を使用済みにしない")
    a = ap.parse_args()

    topic = pick_topic(a.field, a.topic_id)
    mid = a.id or next_material_id()
    print(f"題材 {topic['id']}: {topic['title_ja']}  → 教材 {mid}")
    build(topic, mid)
    if not a.keep_topic:
        mark_used(topic["id"], mid)
    print(mid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
