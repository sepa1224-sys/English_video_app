"""
script_gen_radio.py
英会話ラジオ（Radio Conversation Mode）の台本自動生成スクリプト。

【設計方針】
- ターゲット単語帳（ターゲット1900、鉄壁など）から指定範囲の単語を読み込む
- GPT-4oを使ってテーマに沿った自然な英会話シナリオを生成する
- 生成した台本はJSONで保存し、audio_gen.py / video_gen.py と連携できる構造にする

【台本データ構造】
{
  "title": "Traveling by Plane",
  "topic": "旅行・空港",
  "vocab_source": "ターゲット1900",
  "vocab_range": "1-10",
  "target_words": [...],
  "sections": [
    {"type": "intro", "text": "...", "translation": "..."},
    {"type": "dialogue", "lines": [
      {"speaker": "Alex", "text": "...", "translation": "..."},
      ...
    ]},
    {"type": "explanation", "words": [
      {"word": "...", "meaning": "...", "example": "..."},
      ...
    ]}
  ]
}
"""

import os
import json
import csv
import argparse
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# ──────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────
VOCAB_CSV_MAP = {
    "t1900":   os.path.join("data", "vocab", "ターゲット1900.csv"),
    "t1400":   os.path.join("data", "ターゲット1400.csv"),
    "t1200":   os.path.join("data", "ターゲット1200.csv"),
    "teppeki": os.path.join("data", "英単語帳鉄壁.csv"),
    "systan":  os.path.join("data", "システム英単語 - シート1.csv"),
    "leap":    os.path.join("data", "LEAP.csv"),
}

SPEAKER_NAMES = {
    "male":   "Alex",
    "female": "Sarah",
    "narrator": "Narrator",
}

OUTPUT_DIR = os.path.join("data", "radio_scripts")


# ──────────────────────────────────────────────
# 単語読み込み
# ──────────────────────────────────────────────
def load_words(book: str, start_id: int, end_id: int) -> list:
    """
    指定した単語帳CSVから start_id〜end_id の単語を読み込む。
    """
    csv_file = VOCAB_CSV_MAP.get(book)
    if not csv_file:
        raise ValueError(f"Unknown book: '{book}'. Supported: {list(VOCAB_CSV_MAP.keys())}")
    if not os.path.exists(csv_file):
        raise FileNotFoundError(f"CSV not found: {csv_file}")

    words = []
    for enc in ["utf-8-sig", "utf-8", "cp932"]:
        try:
            with open(csv_file, encoding=enc) as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) < 3:
                        continue
                    try:
                        row_id = int(row[0].strip().replace('"', ''))
                    except ValueError:
                        continue  # ヘッダー行などをスキップ
                    if start_id <= row_id <= end_id:
                        words.append({
                            "id": row_id,
                            "word": row[1].strip(),
                            "meaning": row[2].strip(),
                        })
            break
        except UnicodeDecodeError:
            continue

    words.sort(key=lambda x: x["id"])
    print(f"  - Loaded {len(words)} words ({book} #{start_id}-{end_id})")
    return words


# ──────────────────────────────────────────────
# GPT-4o による台本生成
# ──────────────────────────────────────────────
def generate_radio_script(
    words: list,
    topic: str,
    vocab_source: str,
    vocab_range: str,
    episode_number: int = 1,
) -> dict:
    """
    GPT-4oを使って英会話ラジオの台本JSONを生成する。
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        raise RuntimeError("OPENAI_API_KEY が設定されていません。")

    client = OpenAI(api_key=api_key)

    # 単語リストをプロンプト用テキストに変換
    vocab_text = "\n".join([f"- {w['word']}（{w['meaning']}）" for w in words])

    system_prompt = """あなたはプロの英会話教材クリエイターです。
日本人英語学習者向けのYouTubeチャンネル「気合イングリッシュ」の
「英会話ラジオ」シリーズの台本を作成します。

【コンセプト】
- ターゲット単語帳の単語が自然な会話の中に登場する
- ながら学習（通勤・家事中）に最適な聴き流しコンテンツ
- 英語→日本語訳の順で理解できる構成

【品質基準】
- 会話は自然でリアルな英語（教科書的すぎない）
- ターゲット単語は必ず全て1回以上使うこと
- 日本語訳は自然な日本語で（直訳不可）
- 解説は簡潔に（1単語30秒以内で読める量）
"""

    user_prompt = f"""以下の条件で英会話ラジオの台本を作成してください。

【テーマ】{topic}
【エピソード番号】第{episode_number}回
【使用する単語帳】{vocab_source} No.{vocab_range}
【ターゲット単語（全て使うこと）】
{vocab_text}

【出力形式】必ず以下のJSON形式で出力してください。他のテキストは不要です。

{{
  "title": "英語タイトル（例：Checking In at the Airport）",
  "title_jp": "日本語タイトル（例：空港でのチェックイン）",
  "intro": {{
    "text": "状況説明の英文（2〜3文）",
    "translation": "状況説明の日本語訳"
  }},
  "dialogue": [
    {{"speaker": "Alex", "text": "英語セリフ", "translation": "日本語訳"}},
    {{"speaker": "Sarah", "text": "英語セリフ", "translation": "日本語訳"}}
  ],
  "explanation": [
    {{
      "word": "単語",
      "meaning": "日本語の意味",
      "example": "例文（英語）",
      "example_jp": "例文の日本語訳"
    }}
  ],
  "hashtags": ["#英会話", "#英語学習", "#ターゲット1900"]
}}

【ルール】
- dialogue は最低12往復（24行以上）
- 全てのターゲット単語を dialogue または explanation で使うこと
- speaker は "Alex"（男性）または "Sarah"（女性）のみ
- explanation は全ターゲット単語を含めること
"""

    print(f"  - GPT-4oに台本生成をリクエスト中... (テーマ: {topic})")

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        print(f"  - 台本生成完了: '{data.get('title', 'N/A')}'")
        return data
    except Exception as e:
        print(f"  ! GPT-4o エラー: {e}")
        raise


# ──────────────────────────────────────────────
# 台本データの整形（video_gen.py連携用）
# ──────────────────────────────────────────────
def build_script_data(
    raw: dict,
    words: list,
    vocab_source: str,
    vocab_range: str,
    topic: str,
) -> dict:
    """
    GPT生成データを video_gen.py / audio_gen.py が処理できる形式に整形する。
    """
    sections = []

    # 1. イントロ
    intro = raw.get("intro", {})
    if intro.get("text"):
        sections.append({
            "type": "intro",
            "text": intro["text"],
            "translation": intro.get("translation", ""),
            "speaker": SPEAKER_NAMES["narrator"],
        })

    # 2. ダイアログ
    dialogue_lines = raw.get("dialogue", [])
    if dialogue_lines:
        sections.append({
            "type": "dialogue",
            "lines": [
                {
                    "speaker": line.get("speaker", "Alex"),
                    "text": line.get("text", ""),
                    "translation": line.get("translation", ""),
                }
                for line in dialogue_lines
            ],
        })

    # 3. 解説
    explanation = raw.get("explanation", [])
    if explanation:
        sections.append({
            "type": "explanation",
            "words": explanation,
        })

    return {
        "mode": "radio_conversation",
        "title": raw.get("title", topic),
        "title_jp": raw.get("title_jp", topic),
        "topic": topic,
        "vocab_source": vocab_source,
        "vocab_range": vocab_range,
        "target_words": words,
        "sections": sections,
        "hashtags": raw.get("hashtags", []),
        "generated_at": datetime.now().isoformat(),
    }


# ──────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="英会話ラジオ台本自動生成スクリプト")
    parser.add_argument("--book",   default="t1900",    help="単語帳ID (t1900/teppeki/t1400/t1200/systan/leap)")
    parser.add_argument("--range",  default="1-10",     help="単語範囲 (例: 1-10)")
    parser.add_argument("--topic",  default="旅行・空港", help="会話テーマ")
    parser.add_argument("--ep",     default=1, type=int, help="エピソード番号")
    parser.add_argument("--output", default=None,       help="出力JSONファイルパス（省略時は自動命名）")
    args = parser.parse_args()

    # 出力ディレクトリ作成
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 単語範囲をパース
    try:
        start_str, end_str = args.range.split("-")
        start_id, end_id = int(start_str), int(end_str)
    except ValueError:
        print(f"  ! Invalid range format: '{args.range}'. Use 'start-end' (e.g., '1-10')")
        return

    # 単語帳ラベル
    book_label_map = {
        "t1900": "ターゲット1900", "t1400": "ターゲット1400",
        "t1200": "ターゲット1200", "teppeki": "鉄壁",
        "systan": "システム英単語", "leap": "LEAP",
    }
    vocab_source = book_label_map.get(args.book, args.book)

    print(f"\n=== 英会話ラジオ台本生成 ===")
    print(f"  単語帳: {vocab_source} / 範囲: {args.range} / テーマ: {args.topic}")

    # Step 1: 単語読み込み
    words = load_words(args.book, start_id, end_id)
    if not words:
        print("  ! 単語が見つかりませんでした。処理を中断します。")
        return

    # Step 2: GPT-4oで台本生成
    raw_data = generate_radio_script(
        words=words,
        topic=args.topic,
        vocab_source=vocab_source,
        vocab_range=args.range,
        episode_number=args.ep,
    )

    # Step 3: 整形
    script_data = build_script_data(
        raw=raw_data,
        words=words,
        vocab_source=vocab_source,
        vocab_range=args.range,
        topic=args.topic,
    )

    # Step 4: 保存
    if args.output:
        output_path = args.output
    else:
        safe_topic = args.topic.replace("・", "_").replace("/", "_").replace(" ", "_")
        output_path = os.path.join(
            OUTPUT_DIR,
            f"radio_ep{args.ep:03d}_{args.book}_{args.range}_{safe_topic}.json"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 台本を保存しました: {output_path}")
    print(f"  タイトル: {script_data['title']} / {script_data['title_jp']}")
    print(f"  セクション数: {len(script_data['sections'])}")
    dialogue_section = next((s for s in script_data["sections"] if s["type"] == "dialogue"), None)
    if dialogue_section:
        print(f"  ダイアログ行数: {len(dialogue_section['lines'])} 行")
    return output_path


if __name__ == "__main__":
    main()
