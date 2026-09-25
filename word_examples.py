"""単語帳の各語に、例文1つと和訳を付けて作り置きする。

例文つき聞き流し（word_video_chunked.py --submode en_jp_ex）の素材。
動画を作るたびに生成すると、同じ語の例文が毎回変わり、費用もかさむ。
単語帳ごとに data/examples/<book>.json へ貯めて、作成済みの語は二度と生成しない。

例文は単語帳の例文を写さず、ここで書き下ろす（単語帳の例文は著作物なので使えない）。

  python word_examples.py --book t1900 --start 1 --end 500
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

import script_gen

EX_DIR = Path("data/examples")
BATCH = 40
MAX_WORDS = 14

SYSTEM = f"""あなたは日本の大学受験生向けに、英単語の例文を書く英語教師です。

守ること:
- 1語につき例文を1つ。{MAX_WORDS}語以内の、短く自然な英文にする。
- 単語帳の訳の「①」（最初の意味）で使う。多義語でも最初の意味に合わせる。
- 見出し語以外はやさしい語（高校1年レベル）で書く。難しい語を重ねない。
- 情景が浮かぶ具体的な文にする。"This is important." のような空疎な文は禁止。
- 同じ主語・同じ型を続けない。I / We / The ... / 人名 などを散らす。
- target には、例文の中で見出し語が実際に現れた形をそのまま書く
  （活用形・複数形を含む。例: create → created）。熟語は熟語全体を書く。
- ja は例文の自然な和訳。見出し語の部分は単語帳の訳①に合わせる。
- 単語帳や既存の教材の例文をそのまま写さない。必ず新しく書く。
"""

TOOL = {
    "name": "write_examples",
    "description": "単語ごとの例文と和訳を書く",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "en": {"type": "string", "description": "例文（英語）"},
                        "target": {"type": "string",
                                   "description": "例文中に現れた見出し語の形（そのままの綴り）"},
                        "ja": {"type": "string", "description": "例文の和訳"},
                    },
                    "required": ["id", "en", "target", "ja"],
                },
            },
        },
        "required": ["items"],
    },
}


def cache_path(book: str) -> Path:
    return EX_DIR / f"{book}.json"


def load_cache(book: str) -> dict:
    p = cache_path(book)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_cache(book: str, cache: dict) -> None:
    EX_DIR.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(cache.items(), key=lambda kv: int(kv[0])))
    cache_path(book).write_text(json.dumps(ordered, ensure_ascii=False, indent=1),
                                encoding="utf-8")


def load_words(book: str, start: int, end: int) -> list[dict]:
    script = script_gen.generate_word_audio_script(book, f"{start}-{end}")
    if not script:
        raise SystemExit(f"{book} {start}-{end} の単語を読めませんでした")
    return script["words"]


def problem(ex: dict, word: str) -> str | None:
    """使えない例文なら理由を返す。"""
    en, target = ex.get("en", "").strip(), ex.get("target", "").strip()
    if not en or not target or not ex.get("ja", "").strip():
        return "空の項目がある"
    if target.lower() not in en.lower():
        return f"target「{target}」が例文に含まれていない"
    if len(en.split()) > MAX_WORDS + 2:
        return f"{len(en.split())}語で長すぎる"
    # 見出し語と target が全く別物になっていないか（語頭3文字で緩く確かめる）
    head = re.sub(r"[^a-z]", "", word.lower().split()[0])[:3]
    if head and head not in target.lower():
        return f"target「{target}」が見出し語「{word}」と対応しない"
    return None


def generate(client, model: str, words: list[dict]) -> dict[int, dict]:
    lines = "\n".join(f"- id {w['id']}: {w['word']} … {w['meaning']}" for w in words)
    r = client.messages.create(
        model=model, max_tokens=8192, system=SYSTEM,
        messages=[{"role": "user", "content": f"次の語の例文を書いてください。\n\n{lines}"}],
        tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]})
    data = next((b.input for b in r.content if b.type == "tool_use"), None)
    if not data:
        return {}
    return {int(x["id"]): x for x in data.get("items", []) if "id" in x}


def ensure_examples(book: str, words: list[dict], model: str | None = None) -> dict:
    """words のうち例文が無い語だけ生成して保存し、キャッシュ全体を返す。"""
    cache = load_cache(book)
    todo = [w for w in words if str(w["id"]) not in cache]
    if not todo:
        return cache
    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY がありません。")
    model = model or os.getenv("EXAMPLE_MODEL", "claude-sonnet-5")
    client = anthropic.Anthropic(api_key=key)

    print(f"📝 {book}: {len(todo)}語の例文を生成します（{model}）")
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        # 基準を満たさなかった語だけ、最大3回まで書き直させる
        for attempt in range(3):
            got = generate(client, model, batch)
            retry = []
            for w in batch:
                ex = got.get(w["id"])
                why = problem(ex, w["word"]) if ex else "返ってこなかった"
                if why:
                    retry.append(w)
                    if attempt == 2:
                        print(f"   ⚠ No.{w['id']} {w['word']}: {why}（あきらめます）")
                    continue
                cache[str(w["id"])] = {"word": w["word"], "en": ex["en"].strip(),
                                       "target": ex["target"].strip(), "ja": ex["ja"].strip()}
            if not retry:
                break
            batch = retry
        save_cache(book, cache)
        print(f"   {min(i + BATCH, len(todo))}/{len(todo)}")
    return cache


def attach_examples(book: str, words: list[dict]) -> list[dict]:
    """words に example を付ける。例文の無い語が1つでもあれば止める。"""
    cache = ensure_examples(book, words)
    missing = [w for w in words if str(w["id"]) not in cache]
    if missing:
        ids = ", ".join(f"No.{w['id']} {w['word']}" for w in missing[:10])
        raise RuntimeError(f"例文が無い語があります: {ids}\n"
                           f"data/examples/{book}.json を直すか、"
                           f"word_examples.py を再実行してください。")
    for w in words:
        w["example"] = cache[str(w["id"])]
    return words


def main() -> int:
    ap = argparse.ArgumentParser(description="単語帳の例文を作り置きする")
    ap.add_argument("--book", required=True)
    ap.add_argument("--start", type=int, required=True)
    ap.add_argument("--end", type=int, required=True)
    ap.add_argument("--model")
    ap.add_argument("--redo", action="store_true", help="範囲内の既存の例文を作り直す")
    a = ap.parse_args()

    words = load_words(a.book, a.start, a.end)
    if a.redo:
        cache = load_cache(a.book)
        for w in words:
            cache.pop(str(w["id"]), None)
        save_cache(a.book, cache)
    cache = ensure_examples(a.book, words, a.model)
    done = sum(1 for w in words if str(w["id"]) in cache)
    print(f"✅ {done}/{len(words)}語に例文があります → {cache_path(a.book)}")
    return 0 if done == len(words) else 1


if __name__ == "__main__":
    sys.exit(main())
