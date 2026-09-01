"""
dialogue_script_gen.py — Podcast Mode / 会話型台本生成

2人の話者による英会話ダイアログ形式のポッドキャスト台本を Claude API で生成する。
既存の解説型（podcast_script_gen.py）と対になるモジュール。

構成:
  1. オープニング（日本語ナレーション）
  2. 会話パート（英語のみ・通常スピード）
  3. 解説パート（日本語で重要表現を解説）
  4. リピートパート（同じ会話をもう一度）
  5. エンディング（日本語ナレーション）
"""

import os
import json
import time
import datetime
from pathlib import Path
from dotenv import load_dotenv

import anthropic

from podcast_script_gen import (
    ALLOWED_MODELS,
    MAX_RETRIES,
    RETRY_BACKOFF,
    _extract_tool_input,
    _to_theme_slug,
    _validate_model,
)

OUTPUT_BASE_DIR = Path("output") / "podcast"

# CEFR レベルと、その目安をプロンプトに渡すための説明
LEVEL_GUIDE = {
    "A2": "中学卒業〜高校初級。基本時制と頻出動詞が中心。1文は10語程度まで。",
    "A2B1": "高校中級。日常会話の大半をカバー。1文は12語程度まで。",
    "B1": "高校卒業〜大学初級。TOEIC 500-650。現在完了や関係代名詞も可。1文は15語程度まで。",
    "B2": "大学中級以上。TOEIC 700+。仮定法や複文も自然に使う。1文は18語程度まで。",
}

# --- 構造化出力ツール定義 ---
_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "description": "1からの連番"},
        "speaker": {
            "type": "string",
            "enum": ["A", "B"],
            "description": "話者ID",
        },
        "text_en": {"type": "string", "description": "英語のセリフ"},
        "text_ja": {"type": "string", "description": "自然な日本語訳"},
    },
    "required": ["id", "speaker", "text_en", "text_ja"],
}

_EXPRESSION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "expression_en": {
            "type": "string",
            "description": "会話中に実際に出てきた表現をそのまま抜き出す",
        },
        "meaning_ja": {"type": "string", "description": "日本語訳（原則1文）"},
        "explanation_ja": {
            "type": "string",
            "description": "なぜこの言い方をするか・どんな場面で使うかの解説（1〜2文）",
        },
        "extra_example_en": {
            "type": "string",
            "description": "会話とは別の場面での例文（15語以内）",
        },
        "from_turn_id": {
            "type": "integer",
            "description": "この表現が登場したターンのid",
        },
    },
    "required": [
        "id", "expression_en", "meaning_ja",
        "explanation_ja", "extra_example_en", "from_turn_id",
    ],
}

DIALOGUE_TOOL = {
    "name": "submit_dialogue_script",
    "description": "生成した英会話ダイアログ形式のポッドキャスト台本を提出する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "meta": {
                "type": "object",
                "properties": {
                    "title_candidates": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "タイトル候補を厳密に3つ",
                    },
                    "scene_summary_ja": {
                        "type": "string",
                        "description": "どんな場面の会話かの1文説明",
                    },
                    "speaker_a_name": {"type": "string", "description": "話者Aの名前"},
                    "speaker_b_name": {"type": "string", "description": "話者Bの名前"},
                },
                "required": [
                    "title_candidates", "scene_summary_ja",
                    "speaker_a_name", "speaker_b_name",
                ],
            },
            "opening": {
                "type": "object",
                "properties": {"narration_ja": {"type": "string"}},
                "required": ["narration_ja"],
            },
            "dialogue": {"type": "array", "items": _TURN_SCHEMA},
            "key_expressions": {"type": "array", "items": _EXPRESSION_SCHEMA},
            "ending": {
                "type": "object",
                "properties": {"narration_ja": {"type": "string"}},
                "required": ["narration_ja"],
            },
        },
        "required": [
            "meta", "opening", "dialogue", "key_expressions", "ending",
        ],
    },
}

SYSTEM_PROMPT_TEMPLATE = """あなたは英語学習ポッドキャストの台本ライターです。
日本人学習者向けに、2人の話者による英会話ダイアログの台本を作ってください。

## 前提
- 視聴者は通勤中・作業中に聞き流す日本人学習者
- 画面を見なくても学習が成立する、音声主体のコンテンツ
- チャンネル名は「気合イングリッシュ」

## レベル設定
目標レベル: {level}（{level_guide}）
このレベルを超える語彙・構文は使わないこと。ただし不自然に平易にする必要はない。

## 会話の作り方
1. ターン数は{turn_count}ターン（AとBが交互に話す。同じ人が2連続で話さない）
2. 話者Aと話者Bには一貫した人物設定を与える（名前・関係性）。meta に名前を記載すること
3. **会話に流れと着地をつける。** 質問と応答の羅列にしない。
   良い例: 相談を持ちかける → 事情を聞く → 提案する → 受け入れて次の行動が決まる
   悪い例: 天気の話 → 週末の話 → 仕事の話（脈絡なく話題が飛ぶ）
4. **自然な話し言葉にする。** 教科書的な完全文の応酬を避ける:
   - 短縮形を使う（I'm / don't / it's / that's）
   - 相槌や短い応答を混ぜる（Sure. / Right. / Oh, really? / Got it.）
   - ただし filler（um, uh, like）は聞き取りの妨げになるので使わない
5. 1ターンは長くても3文まで。長い説明を1人に喋らせない
6. 日本の学習者に馴染みのない固有名詞・文化前提を必要とする話題は避ける

## 日本語訳（text_ja）
- 直訳ではなく、その場面の日本語話者が実際に言う自然なセリフにする
- 英文の語順に引きずられないこと
- 例: "You should've told me." → ○「言ってくれればよかったのに。」× 「あなたは私に言うべきだった。」

## 重要表現の抜き出し（key_expressions）
- {expression_count}個を選ぶ
- **必ず会話中に実際に登場した表現をそのまま抜き出すこと。** 会話に無い表現を足さない
- from_turn_id には、その表現が出てきたターンのidを正確に入れる
- 選ぶ基準は「他の場面でも使い回せる汎用性」。その場限りの言い回しは選ばない
- explanation_ja では、なぜその言い方をするのか・どんなニュアンスかを具体的に書く
  「丁寧な表現です」のような曖昧な説明で終わらせない
- extra_example_en は会話とは別の場面での使用例にする

## 解説の文体
- 敬語だが堅すぎない「〜ですね」「〜してみましょう」調
- 文末表現を意図的にバラつかせる（「〜ますよ」の連続を避ける）
- 英文法用語の多用を避ける（「現在完了」程度はOK）

## オープニング・エンディング
- opening.narration_ja: 3〜4文。チャンネル名を含む挨拶 → 今回の場面紹介 →
  「まず通常スピードで会話を聞き、そのあと重要表現を解説します」という構成予告
- ending.narration_ja: 3〜4文。学習内容の振り返り → 次回への繋ぎ →
  チャンネル登録の自然な促し → 締めの挨拶

## タイトル候補
meta.title_candidates に3つ。各タイトルに以下を含める:
1. 利用シーンの明示（「聞き流し」「通勤中」「シャドーイング」など）
2. レベルまたは場面の明示
3. 具体的な会話テーマ

## 禁止事項
- 架空の英語表現や造語を使わない
- 文法的に誤った英文を作らない
- 特定の国・文化を戯画化した会話にしない"""

USER_PROMPT_TEMPLATE = """以下の条件で会話型の台本を生成してください。

場面・テーマ: {theme}
目標レベル: {level}
会話のターン数: {turn_count}
抜き出す重要表現の数: {expression_count}"""


def _validate_dialogue(data: dict, turn_count: int, expression_count: int) -> list[str]:
    """会話台本のバリデーション。エラーメッセージのリストを返す（空なら正常）"""
    errors = []

    for field in ["meta", "opening", "dialogue", "key_expressions", "ending"]:
        if field not in data:
            errors.append(f"'{field}' フィールドがありません")
    if "dialogue" not in data:
        return errors

    turns = data["dialogue"]
    if len(turns) != turn_count:
        errors.append(f"ターン数が {len(turns)} です（期待値: {turn_count}）")

    # 話者が交互になっているか
    for i in range(1, len(turns)):
        if turns[i].get("speaker") == turns[i - 1].get("speaker"):
            errors.append(
                f"dialogue[{i}] で話者 '{turns[i].get('speaker')}' が連続しています"
            )

    turn_ids = {t.get("id") for t in turns}
    exprs = data.get("key_expressions", [])
    if len(exprs) != expression_count:
        errors.append(
            f"重要表現が {len(exprs)} 個です（期待値: {expression_count}）"
        )

    # 抜き出した表現が本当に会話中に存在するか（ハルシネーション検出）
    turn_text = " ".join(t.get("text_en", "") for t in turns).lower()
    for i, e in enumerate(exprs):
        expr = e.get("expression_en", "")
        # 記号と大文字小文字を無視して部分一致を見る
        norm = "".join(c for c in expr.lower() if c.isalnum() or c.isspace()).strip()
        norm_turns = "".join(
            c for c in turn_text if c.isalnum() or c.isspace()
        )
        if norm and norm not in norm_turns:
            errors.append(
                f"key_expressions[{i}] '{expr}' は会話中に存在しません"
            )
        if e.get("from_turn_id") not in turn_ids:
            errors.append(
                f"key_expressions[{i}].from_turn_id={e.get('from_turn_id')} "
                f"は存在しないターンidです"
            )

    return errors


def _dialogue_to_markdown(data: dict) -> str:
    """会話台本をレビュー用Markdownに変換"""
    meta = data.get("meta", {})
    a = meta.get("speaker_a_name", "A")
    b = meta.get("speaker_b_name", "B")
    names = {"A": a, "B": b}

    lines = []
    lines.append(f"# 会話台本: {meta.get('theme', '不明')}")
    lines.append(f"> 生成日時: {meta.get('generated_at', '不明')}")
    lines.append(f"> モデル: {meta.get('model_version', '不明')}")
    lines.append(f"> レベル: {meta.get('level', '不明')}")
    lines.append("")
    lines.append(f"**場面**: {meta.get('scene_summary_ja', '')}")
    lines.append(f"**登場人物**: {a}（A） / {b}（B）")
    lines.append("")

    lines.append("## タイトル候補")
    for i, t in enumerate(meta.get("title_candidates", []), 1):
        lines.append(f"{i}. {t}")
    lines.append("")

    lines.append("## オープニング")
    lines.append(data.get("opening", {}).get("narration_ja", ""))
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 会話")
    for t in data.get("dialogue", []):
        who = names.get(t.get("speaker"), t.get("speaker"))
        lines.append(f"**{t.get('id')}. {who}**: {t.get('text_en','')}")
        lines.append(f"　{t.get('text_ja','')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 重要表現")
    for e in data.get("key_expressions", []):
        lines.append(f"### {e.get('id')}. {e.get('expression_en','')}")
        lines.append(f"- **日本語訳**: {e.get('meaning_ja','')}")
        lines.append(f"- **解説**: {e.get('explanation_ja','')}")
        lines.append(f"- **別の例文**: {e.get('extra_example_en','')}")
        lines.append(f"- **登場ターン**: {e.get('from_turn_id')}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## エンディング")
    lines.append(data.get("ending", {}).get("narration_ja", ""))
    lines.append("")

    return "\n".join(lines)


def generate_dialogue_script(
    theme: str,
    level: str = "A2B1",
    turn_count: int = 12,
    expression_count: int = 5,
) -> dict | None:
    """
    Claude API を使って会話型ポッドキャスト台本を生成する。

    Args:
        theme: 場面・テーマ（例: "同僚に残業を代わってもらう"）
        level: CEFR レベル（A2 / A2B1 / B1 / B2）
        turn_count: 会話のターン数
        expression_count: 抜き出す重要表現の数

    Returns:
        台本データ（dict）。失敗時は None。
    """
    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY が設定されていません。\n"
            ".env ファイルに ANTHROPIC_API_KEY=sk-ant-... を追加してください。"
        )

    if level not in LEVEL_GUIDE:
        raise ValueError(
            f"level '{level}' は無効です。"
            f"次のいずれかを指定してください: {', '.join(LEVEL_GUIDE)}"
        )

    model = _validate_model(os.getenv("PODCAST_SCRIPT_MODEL", "claude-opus-5"))

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        level=level,
        level_guide=LEVEL_GUIDE[level],
        turn_count=turn_count,
        expression_count=expression_count,
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        theme=theme,
        level=level,
        turn_count=turn_count,
        expression_count=expression_count,
    )

    client = anthropic.Anthropic(api_key=api_key)

    data = None
    for attempt in range(MAX_RETRIES):
        try:
            print(
                f"🎙 会話台本を生成中... "
                f"(attempt {attempt + 1}/{MAX_RETRIES}, model: {model})"
            )
            response = client.messages.create(
                model=model,
                max_tokens=16384,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[DIALOGUE_TOOL],
                tool_choice={"type": "tool", "name": DIALOGUE_TOOL["name"]},
            )
            data = _extract_tool_input(response, DIALOGUE_TOOL["name"])
            if data is None:
                raise ValueError("tool_use ブロックが返りませんでした")
            break
        except anthropic.RateLimitError:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"⏳ レート制限。{wait}秒後にリトライ")
                time.sleep(wait)
            else:
                print("❌ レート制限が解除されません。数分後に再実行してください。")
                return None
        except anthropic.AuthenticationError:
            print("❌ ANTHROPIC_API_KEY が無効です。")
            return None
        except anthropic.APIError as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"⏳ API エラー: {e}。{wait}秒後にリトライ")
                time.sleep(wait)
            else:
                print(f"❌ API エラーが解消されません: {e}")
                return None

    if data is None:
        print("❌ API レスポンスを取得できませんでした。")
        return None

    # --- meta 補完 ---
    data.setdefault("meta", {})
    data["meta"].update({
        "theme": theme,
        "level": level,
        "turn_count": turn_count,
        "expression_count": expression_count,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generator": "claude-api",
        "model_version": model,
        "dialogue_mode": True,
        "version": "1.0",
    })

    # --- バリデーション ---
    errors = _validate_dialogue(data, turn_count, expression_count)
    if errors:
        print("⚠ 台本バリデーション警告:")
        for err in errors:
            print(f"  - {err}")
        fatal = [e for e in errors if "存在しません" in e or "ターン数が" in e]
        if fatal:
            print("❌ 致命的なバリデーションエラーのため中断します。")
            return None

    # --- 保存 ---
    OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = _to_theme_slug(theme)
    base = f"{slug}_dlg{turn_count}_{timestamp}"

    json_path = OUTPUT_BASE_DIR / f"{base}.json"
    md_path = OUTPUT_BASE_DIR / f"{base}.md"

    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ 台本JSON保存: {json_path}")

    md_path.write_text(_dialogue_to_markdown(data), encoding="utf-8")
    print(f"✅ 台本Markdown保存: {md_path}")

    # --- サマリー ---
    meta = data["meta"]
    print(f"\n📊 生成サマリー:")
    print(f"  場面: {meta.get('scene_summary_ja', '')}")
    print(f"  登場人物: {meta.get('speaker_a_name')} / {meta.get('speaker_b_name')}")
    print(f"  ターン数: {len(data.get('dialogue', []))}")
    print(f"  重要表現: {len(data.get('key_expressions', []))}個")
    print(f"  タイトル候補:")
    for i, t in enumerate(meta.get("title_candidates", []), 1):
        print(f"    {i}. {t}")

    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="会話型ポッドキャスト台本生成")
    parser.add_argument("--theme", required=True, help="場面・テーマ")
    parser.add_argument(
        "--level", default="A2B1", choices=sorted(LEVEL_GUIDE),
        help="目標CEFRレベル",
    )
    parser.add_argument("--turns", type=int, default=12, help="会話のターン数")
    parser.add_argument(
        "--expressions", type=int, default=5, help="抜き出す重要表現の数"
    )
    args = parser.parse_args()

    result = generate_dialogue_script(
        theme=args.theme,
        level=args.level,
        turn_count=args.turns,
        expression_count=args.expressions,
    )
    if result is None:
        print("\n❌ 台本生成に失敗しました。")
        exit(1)
    print("\n✅ 台本生成完了。レビューしてください。")
