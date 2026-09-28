"""短文（日本語→英語）の聞き流し素材を、テーマから作る。

瞬間英作文の聞き流し動画（phrase_video.py）の素材。Claude が大人向けの短文を
書き下ろし、data/phrases/<set>.json に保存する。

  python3 phrase_gen.py --set p001 --count 100 --theme "仕事の雑談で言えそうで言えない表現"
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PHRASE_DIR = Path("data/phrases")
BATCH = 25
MAX_WORDS = 12

SYSTEM = f"""あなたは日本の大人向け英会話スクールのコーチです。
「日本語を聞いて、すぐ英語で言う」練習（瞬間英作文）用の短文を書きます。

守ること:
- 英文は{MAX_WORDS}語以内。口に出して気持ちよく言える、自然な話し言葉にする。
- 大人が仕事・家庭・旅行・雑談で本当に使う場面にする。教科書的な無意味な文は禁止。
- 日本人が「知っている単語なのに、とっさに出てこない」ものを優先する。
- ネイティブが実際に口にする形だけを書く。和製英語的・直訳的な不自然な英語は禁止
  （例: × by this week → ○ by the end of the week / × I have a question to you）。
- 日本語は、日本人が普通に言う自然な文にする。直訳調にしない。
  ただし英文と意味がずれないこと（聞いた人が「その英語になる」と納得できる日本語）。
- 同じ型・同じ主語が続かないように散らす。
- 人名・実在の会社名は使わない。
- point には、その文で身につく型を日本語10字程度で書く（例: 現在完了の経験）。
"""

TOOL = {
    "name": "write_phrases",
    "description": "瞬間英作文用の短文を書く",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ja": {"type": "string"},
                        "en": {"type": "string"},
                        "point": {"type": "string"},
                    },
                    "required": ["ja", "en", "point"],
                },
            },
        },
        "required": ["items"],
    },
}

TITLE_TOOL = {
    "name": "name_set",
    "description": "動画のタイトル案を付ける",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_ja": {"type": "string",
                         "description": "YouTubeタイトル。数（◯フレーズ）と『聞き流し』を入れる。45字以内"},
            "hook": {"type": "string", "description": "サムネ用の短い一言。12字以内"},
        },
        "required": ["title_ja", "hook"],
    },
}


def usable(item: dict) -> bool:
    en, ja = item.get("en", "").strip(), item.get("ja", "").strip()
    return bool(en and ja) and len(en.split()) <= MAX_WORDS + 2


def main() -> int:
    ap = argparse.ArgumentParser(description="瞬間英作文の短文セットを作る")
    ap.add_argument("--set", required=True, help="セットID（例: p001）")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--theme", default="日本人が英会話で言えそうで言えない表現")
    ap.add_argument("--model")
    a = ap.parse_args()

    out = PHRASE_DIR / f"{a.set}.json"
    if out.exists():
        raise SystemExit(f"{out} は作成済みです。作り直すなら消してから実行してください。")
    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY がありません。")
    model = a.model or os.getenv("EXAMPLE_MODEL", "claude-sonnet-5")
    client = anthropic.Anthropic(api_key=key)

    items: list[dict] = []
    seen: set[str] = set()
    for _ in range(a.count // BATCH + 4):
        if len(items) >= a.count:
            break
        need = min(BATCH, a.count - len(items))
        prompt = f"テーマ: {a.theme}\n{need}文書いてください。"
        if items:
            # 既に書いた文と重ならないように、直近の分を見せる
            prompt += "\n\n既に書いた英文（重複禁止）:\n" + "\n".join(x["en"] for x in items[-60:])
        r = client.messages.create(
            model=model, max_tokens=8192, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]})
        data = next((b.input for b in r.content if b.type == "tool_use"), {})
        for x in data.get("items", []):
            k = x.get("en", "").strip().lower()
            if not usable(x) or k in seen:
                continue
            seen.add(k)
            items.append({"ja": x["ja"].strip(), "en": x["en"].strip(),
                          "point": x.get("point", "").strip()})
        print(f"  {min(len(items), a.count)}/{a.count}")
    items = items[:a.count]

    r = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content":
                   f"テーマ「{a.theme}」の瞬間英作文 {len(items)}フレーズの聞き流し動画。"
                   f"例: {items[0]['ja']} → {items[0]['en']}"}],
        tools=[TITLE_TOOL], tool_choice={"type": "tool", "name": TITLE_TOOL["name"]})
    meta = next((b.input for b in r.content if b.type == "tool_use"), {})

    PHRASE_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": a.set, "theme": a.theme, **meta, "items": items},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {len(items)}文 → {out}\n   タイトル案: {meta.get('title_ja')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
