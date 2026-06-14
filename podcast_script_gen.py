"""
podcast_script_gen.py — Podcast Mode 台本生成

Claude API を使って、聞き流し英語学習ポッドキャストの台本を生成する。
仕様書: docs/specs/podcast_mode_spec.md
"""

import os
import json
import time
import datetime
import re
from pathlib import Path
from dotenv import load_dotenv

import anthropic

# --- 定数 ---
PODCAST_SCRIPT_MODEL = os.getenv("PODCAST_SCRIPT_MODEL", "claude-sonnet-4-6")
ALLOWED_MODELS = {"claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"}
OUTPUT_BASE_DIR = Path("output") / "podcast"
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]

# 難易度配分デフォルト
DEFAULT_DIFFICULTY_DISTRIBUTION = {
    "beginner": 10,
    "intermediate": 15,
    "advanced": 5,
}

# --- JSON スキーマ定義（System Prompt に埋め込む） ---
JSON_SCHEMA = """{
  "meta": {
    "theme": "(string) テーマ名",
    "phrase_count": "(int) フレーズ数",
    "target_audience": "(string) 対象者",
    "detail_level": "(string) brief / normal / detailed",
    "difficulty_distribution": {
      "beginner": "(int)",
      "intermediate": "(int)",
      "advanced": "(int)"
    },
    "generated_at": "(string) ISO 8601",
    "generator": "(string) claude-api",
    "model_version": "(string) 使用モデルID",
    "dialogue_mode": false,
    "version": "1.0",
    "title_candidates": ["(string) タイトル候補1", "(string) 候補2", "(string) 候補3"]
  },
  "opening": {
    "narration_ja": "(string) オープニングナレーション"
  },
  "phrases": [
    {
      "id": "(int) 1から連番",
      "phrase_en": "(string) 英語フレーズ",
      "meaning_ja": "(string) 日本語訳",
      "explanation_ja": "(string) 使用場面の解説",
      "example_en": "(string) 例文",
      "difficulty": "(string) beginner / intermediate / advanced",
      "category": "(string) テーマ内カテゴリ",
      "is_review": "(bool) 復習パートに含めるか（trueは最大10個）"
    }
  ],
  "ending": {
    "narration_ja": "(string) エンディングナレーション"
  }
}"""

# --- System Prompt ---
SYSTEM_PROMPT_TEMPLATE = """あなたは英語学習ポッドキャストの台本ライターです。
YouTube向けの聞き流し学習動画の台本をJSON形式で生成してください。

## あなたの役割
- NHKラジオ英会話のような、フレンドリーかつ実務的なトーンで解説を書く
- 視聴者は通勤中・作業中に聞き流す社会人・大学生（TOEIC 400〜650レンジ）
- 画面を見なくても学習が成立する、音声主体のコンテンツを前提とする

## フレーズ選定ルール
1. 指定されたテーマに沿った実用フレーズを{phrase_count}個選定する
2. 「実際の場面で週1回以上使われる頻度」を実用度の基準とする
3. 同義表現の重複禁止。以下の例を参考に判断すること：
   - "I look forward to" と "Looking forward to" は同義なので片方のみ
   - "Please find attached" と "Please see the attached" は同義なので片方のみ
   - "Thank you for your email" と "Thanks for your email" は同義なので片方のみ
   - ただし "Could you ~?" と "Would you ~?" は丁寧度のニュアンスが違うので両方OK
4. 難易度バランス: 初級（TOEIC400相当）{n_beginner}個 / 中級（TOEIC550相当）{n_intermediate}個 / 上級（TOEIC650相当）{n_advanced}個
5. テーマ内のカテゴリを網羅する（例: ビジネスメールなら 挨拶・依頼・確認・報告・謝罪・締め など偏りなく）
6. 並び順はメール等の実際の使用フローに沿った自然な順序にする
7. 例文の多様性: {phrase_count}個の例文がすべて違う文頭で始まること。"Dear Mr. Smith" のような決まり文句で複数の例文が始まらないようにする。文の構造（平叙文、疑問文、依頼文など）も適度に混ぜる。

## 各フレーズの構成要素
- phrase_en: 英語フレーズ（単独で意味が通る最小単位）
- meaning_ja: 日本語訳（自然な日本語、直訳ではなく意訳）
- explanation_ja: 使用場面の解説（1〜2文、敬語だが堅すぎない「〜ですね」「〜してみましょう」調、具体的なシチュエーション描写を含める）
- example_en: 例文（15語以内、学習対象フレーズを必ず含む、TOEIC500-600レベル）
- difficulty: "beginner" / "intermediate" / "advanced"
- category: テーマ内のカテゴリ名（例: "挨拶", "依頼", "締め"）
- is_review: 復習パートに含めるかどうか（trueは厳密に10個。以下の優先順位で選ぶ）
  1. 初級難易度かつ実用度が最も高いもの（メール冒頭・締めの定番表現）
  2. 中級難易度の中で特に頻出する表現
  3. 上級からは含めない（上級は1回聞いて理解できれば十分）

## オープニング・エンディング
- opening.narration_ja: 以下の要素を3〜4文で自然につなぐ：
  (1) チャンネル名「気合イングリッシュ」を含む挨拶
  (2) 今回のテーマ紹介
  (3) なぜこのテーマが重要か（学習者にとっての価値）を1文
  (4) 「通勤中や作業中の聞き流しにぴったりです」等の使い方ガイド
  (5) 「最後に重要フレーズの復習もあります」という構成予告
- ending.narration_ja: 以下の要素を3〜4文で自然につなぐ：
  (1) 今回の学習内容の振り返り
  (2) 次回予告への繋ぎ（例: 次は会議英語編を予定しています）
  (3) チャンネル登録・高評価の自然な促し
  (4) 締めの挨拶

## タイトル候補
meta.title_candidates に3つのタイトル候補を生成する。各タイトルには以下の3要素を必ず含める：
1. 利用シーンの明示（例: 「通勤中」「作業用」「聞き流し」「BGM代わりに」）
2. 効果・規模の強調（例: 「完全攻略」「これだけでOK」「30選」「保存版」）
3. 具体的テーマ（例: 「ビジネスメール」「会議英語」「電話応対」）

## 出力JSON形式
厳密に以下のスキーマに従うこと。フィールドの追加・省略・名称変更は禁止。
{json_schema}

## JSON出力上の注意
- JSON文字列値の中にダブルクォート（"）を含める場合は、必ずバックスラッシュでエスケープすること（例: \\"Dear Mr. Smith\\"）
- 日本語の鉤括弧「」を使うことで、ダブルクォートの使用を避けることを推奨する

## 禁止事項
- 架空の英語表現や造語を含めないこと
- 文法的に誤った例文を生成しないこと
- 日本語の解説に英文法用語を多用しないこと（「仮定法」程度はOK、「接続法的用法」等はNG）
- is_review: true は10個を超えないこと

## 品質向上のための具体的注意点（試作1本目フィードバック反映）

### 言い換え・代替表現の必須遵守
- "Best regards," のような結びの言葉（クロージング）は学習対象に含めない（フレーズではないため）
- "Please revert" は使わない（インド英語特有、グローバル標準では "Please get back to me" を使う）
- "Kindly" 単独の表現は使わない（ネイティブには古風または上から目線に響くため "Please" を優先）

### 日本語訳の品質ルール
- 1つの英語フレーズに対して、日本語訳は原則1文に収める（2文に分割しない）
- 直訳ではなく、日本人がビジネスメールで実際に使う自然な日本語に意訳する
- 例: "I hope this email finds you well." → ○「お元気でお過ごしのことと存じます。」× 「ご連絡いたします。お変わりないでしょうか。」（2文に分かれて冗長）

### 解説の文末表現の多様性
- 「〜ますよ」が連続しないよう、「〜です」「〜ですね」「〜ます」「〜でしょう」を混ぜる
- 1フレーズの解説内で文末表現を意図的にバラつかせる

### 例文の品質ルール
- 各例文は学習対象フレーズが実際に使われる典型的な文脈で構成する
- "Best regards, [名前], [役職], [会社名]" のような署名ブロックは例文として不適切
- "We would like to take this opportunity to thank you for your continued support" のような年末挨拶限定の例文は避け、より広い場面で使える例文を選ぶ

### 解説の正確性ルール
- 「単なる Sorry より印象がよくなる」のような曖昧な比較は避け、具体的に何が良くなるかを説明する
- 文化的・地域的に偏った表現（インド英語、東南アジア英語のローカル用法など）を「ビジネス英語」として教えない

### バリデーション必達ルール
- is_review: true は厳密に10個（11個や9個は不可）
- difficulty 配分は厳密に beginner:10 / intermediate:15 / advanced:5"""

USER_PROMPT_TEMPLATE = """以下の条件で台本を生成してください。

テーマ: {theme}
フレーズ数: {phrase_count}
対象者: {target_audience}
解説の詳しさ: {detail_level}

JSONのみを出力してください。説明文やコードブロック記法は不要です。"""


def _validate_model(model: str) -> str:
    """モデル文字列のバリデーション"""
    if model not in ALLOWED_MODELS:
        raise ValueError(
            f"PODCAST_SCRIPT_MODEL の値 '{model}' は無効です。"
            f"以下のいずれかを指定してください: {', '.join(sorted(ALLOWED_MODELS))}"
        )
    return model


def _validate_script(data: dict, expected_count: int) -> list[str]:
    """台本JSONのバリデーション。エラーメッセージのリストを返す（空なら正常）"""
    errors = []

    # トップレベルフィールド
    for field in ["meta", "opening", "phrases", "ending"]:
        if field not in data:
            errors.append(f"'{field}' フィールドがありません")

    if "phrases" not in data:
        return errors  # これ以上チェックできない

    phrases = data["phrases"]
    if len(phrases) != expected_count:
        errors.append(
            f"フレーズ数が {len(phrases)} 個です（期待値: {expected_count}）"
        )

    # is_review の数チェック
    review_count = sum(1 for p in phrases if p.get("is_review"))
    if review_count > 10:
        errors.append(f"is_review=true が {review_count} 個です（上限: 10）")
    if review_count == 0:
        errors.append("is_review=true のフレーズが0個です（1個以上必要）")

    # 各フレーズの必須フィールドチェック
    required_fields = [
        "id", "phrase_en", "meaning_ja", "explanation_ja",
        "example_en", "difficulty", "category", "is_review",
    ]
    valid_difficulties = {"beginner", "intermediate", "advanced"}
    for i, p in enumerate(phrases):
        for field in required_fields:
            if field not in p:
                errors.append(f"phrases[{i}] に '{field}' がありません")
        if p.get("difficulty") and p["difficulty"] not in valid_difficulties:
            errors.append(
                f"phrases[{i}].difficulty '{p['difficulty']}' は無効です"
            )

    # meta フィールドチェック
    if "meta" in data:
        meta = data["meta"]
        for field in ["theme", "phrase_count", "title_candidates"]:
            if field not in meta:
                errors.append(f"meta.{field} がありません")
        if "title_candidates" in meta:
            tc = meta["title_candidates"]
            if not isinstance(tc, list) or len(tc) != 3:
                errors.append(
                    f"meta.title_candidates は3要素のリストである必要があります"
                    f"（現在: {len(tc) if isinstance(tc, list) else 'リストではない'}）"
                )

    # opening/ending チェック
    if "opening" in data and "narration_ja" not in data["opening"]:
        errors.append("opening.narration_ja がありません")
    if "ending" in data and "narration_ja" not in data["ending"]:
        errors.append("ending.narration_ja がありません")

    return errors


def _repair_json_quotes(text: str) -> str:
    """JSON文字列値内の未エスケープダブルクォートを修復する。

    例: "explanation_ja": "性別がわからない場合は "Dear [名前]," が無難です"
    → "explanation_ja": "性別がわからない場合は「Dear [名前],」が無難です"
    """
    # 戦略: 行ごとに処理し、": "の後ろの文字列値内の未エスケープクォートを鉤括弧に置換
    lines = text.split("\n")
    repaired_lines = []
    for line in lines:
        # "key": "value" パターンの value 部分を特定
        match = re.match(r'^(\s*"[^"]+"\s*:\s*)"(.*)"([,\s]*)$', line)
        if match:
            prefix = match.group(1)
            value = match.group(2)
            suffix = match.group(3)
            # value内の未エスケープダブルクォートを鉤括弧に置換
            # すでにエスケープ済み (\") はスキップ
            fixed_value = re.sub(r'(?<!\\)"([^"]*?)(?<!\\)"', r'「\1」', value)
            repaired_lines.append(f'{prefix}"{fixed_value}"{suffix}')
        else:
            repaired_lines.append(line)
    return "\n".join(repaired_lines)


def _to_theme_slug(theme: str) -> str:
    """テーマ名をファイル名用のslugに変換"""
    # よく使うテーマのマッピング
    slug_map = {
        "ビジネスメール": "business_email",
        "会議英語": "meeting",
        "電話応対": "phone",
        "顧客対応": "customer_service",
        "出張・海外赴任": "business_trip",
        "上司への報告・相談": "reporting",
    }
    for ja, en in slug_map.items():
        if ja in theme:
            return en
    # マッチしない場合は英数字のみ残す
    slug = re.sub(r"[^a-zA-Z0-9]", "_", theme)
    slug = re.sub(r"_+", "_", slug).strip("_").lower()
    return slug or "podcast"


def _script_to_markdown(data: dict) -> str:
    """台本JSONをレビュー用Markdownに変換"""
    meta = data.get("meta", {})
    lines = []
    lines.append(f"# 台本: {meta.get('theme', '不明')}")
    lines.append(f"> 生成日時: {meta.get('generated_at', '不明')}")
    lines.append(f"> モデル: {meta.get('model_version', '不明')}")
    lines.append("")

    # タイトル候補
    candidates = meta.get("title_candidates", [])
    if candidates:
        lines.append("## タイトル候補")
        for i, t in enumerate(candidates, 1):
            lines.append(f"{i}. {t}")
        lines.append("")

    # オープニング
    lines.append("## オープニング")
    lines.append(data.get("opening", {}).get("narration_ja", "(なし)"))
    lines.append("")
    lines.append("---")
    lines.append("")

    # フレーズ一覧
    lines.append("## フレーズ一覧")
    lines.append("")

    difficulty_ja = {
        "beginner": "初級",
        "intermediate": "中級",
        "advanced": "上級",
    }

    for p in data.get("phrases", []):
        pid = p.get("id", "?")
        lines.append(f"### {pid}. {p.get('phrase_en', '')}")
        lines.append(f"- **日本語訳**: {p.get('meaning_ja', '')}")
        lines.append(f"- **解説**: {p.get('explanation_ja', '')}")
        lines.append(f"- **例文**: {p.get('example_en', '')}")
        diff = difficulty_ja.get(p.get("difficulty", ""), p.get("difficulty", ""))
        cat = p.get("category", "")
        review = "✓" if p.get("is_review") else ""
        lines.append(f"- **難易度**: {diff} | **カテゴリ**: {cat} | **復習対象**: {review}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # エンディング
    lines.append("## エンディング")
    lines.append(data.get("ending", {}).get("narration_ja", "(なし)"))
    lines.append("")

    return "\n".join(lines)


def generate_podcast_script(
    theme: str,
    phrase_count: int = 30,
    target_audience: str = "社会人・大学生",
    detail_level: str = "normal",
    difficulty_distribution: dict | None = None,
) -> dict | None:
    """
    Claude API を使ってポッドキャスト台本を生成する。

    Args:
        theme: テーマ名（例: "ビジネスメールで使える英語表現30選"）
        phrase_count: フレーズ数（デフォルト: 30）
        target_audience: 対象者
        detail_level: 解説の詳しさ（brief / normal / detailed）
        difficulty_distribution: 難易度配分（デフォルト: 初級10/中級15/上級5）

    Returns:
        台本データ（dict）。失敗時は None。
        成功時は output/podcast/ にJSONとMarkdownを保存する。
    """
    load_dotenv()

    # --- 環境変数チェック ---
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY が設定されていません。\n"
            ".env ファイルに ANTHROPIC_API_KEY=sk-ant-... を追加してください。\n"
            "参考: .env.example"
        )

    model = os.getenv("PODCAST_SCRIPT_MODEL", "claude-sonnet-4-6")
    model = _validate_model(model)

    # --- 難易度配分 ---
    dist = difficulty_distribution or DEFAULT_DIFFICULTY_DISTRIBUTION
    n_beginner = dist["beginner"]
    n_intermediate = dist["intermediate"]
    n_advanced = dist["advanced"]

    if n_beginner + n_intermediate + n_advanced != phrase_count:
        print(
            f"⚠ 難易度配分の合計({n_beginner + n_intermediate + n_advanced})"
            f"がフレーズ数({phrase_count})と一致しません。配分を調整します。"
        )
        # 比率を維持しつつ調整
        total = n_beginner + n_intermediate + n_advanced
        n_beginner = round(phrase_count * n_beginner / total)
        n_intermediate = round(phrase_count * n_intermediate / total)
        n_advanced = phrase_count - n_beginner - n_intermediate

    # --- プロンプト構築 ---
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        phrase_count=phrase_count,
        n_beginner=n_beginner,
        n_intermediate=n_intermediate,
        n_advanced=n_advanced,
        json_schema=JSON_SCHEMA,
    )
    user_prompt = USER_PROMPT_TEMPLATE.format(
        theme=theme,
        phrase_count=phrase_count,
        target_audience=target_audience,
        detail_level=detail_level,
    )

    # --- API 呼び出し（リトライ付き） ---
    client = anthropic.Anthropic(api_key=api_key)

    raw_content = None
    for attempt in range(MAX_RETRIES):
        try:
            print(f"🎙 台本生成中... (attempt {attempt + 1}/{MAX_RETRIES}, model: {model})")
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw_content = response.content[0].text
            break
        except anthropic.RateLimitError:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"⏳ レート制限。{wait}秒後にリトライ ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                print("❌ レート制限が解除されません。数分後に再実行してください。")
                return None
        except anthropic.AuthenticationError:
            print("❌ ANTHROPIC_API_KEY が無効です。キーを確認してください。")
            return None
        except anthropic.APIError as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"⏳ API エラー: {e}。{wait}秒後にリトライ ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                print(f"❌ API エラーが解消されません: {e}")
                return None

    if raw_content is None:
        print("❌ API レスポンスを取得できませんでした。")
        return None

    # --- JSON パース ---
    # コードブロック記法が含まれている場合は除去
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    theme_slug = _to_theme_slug(theme)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # 修復を試みる: JSON文字列値内の未エスケープのダブルクォートを修正
        repaired = _repair_json_quotes(cleaned)
        try:
            data = json.loads(repaired)
            print("⚠ JSON内の未エスケープ文字を自動修復しました。")
        except json.JSONDecodeError as e:
            print(f"❌ JSON パースエラー: {e}")
            print(f"- 生のレスポンス冒頭500文字: {repr(raw_content[:500])}")
            # デバッグ用に生レスポンスを保存
            OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
            error_path = OUTPUT_BASE_DIR / f"{theme_slug}_raw_error_{timestamp}.txt"
            error_path.write_text(raw_content, encoding="utf-8")
            print(f"- 生レスポンスを保存: {error_path}")
            return None

    # --- meta フィールドの補完（AIが埋めない可能性があるフィールド） ---
    if "meta" not in data:
        data["meta"] = {}
    data["meta"]["generated_at"] = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()
    data["meta"]["generator"] = "claude-api"
    data["meta"]["model_version"] = model
    data["meta"]["dialogue_mode"] = False
    data["meta"]["version"] = "1.0"
    # 入力パラメータも記録
    data["meta"]["theme"] = theme
    data["meta"]["phrase_count"] = phrase_count
    data["meta"]["target_audience"] = target_audience
    data["meta"]["detail_level"] = detail_level
    data["meta"]["difficulty_distribution"] = {
        "beginner": n_beginner,
        "intermediate": n_intermediate,
        "advanced": n_advanced,
    }

    # --- バリデーション ---
    errors = _validate_script(data, phrase_count)
    if errors:
        print("⚠ 台本バリデーション警告:")
        for err in errors:
            print(f"  - {err}")
        # 警告は出すが、致命的でなければ続行（フレーズ数不一致は致命的）
        phrase_count_errors = [e for e in errors if "フレーズ数が" in e]
        missing_field_errors = [e for e in errors if "がありません" in e and "meta" not in e]
        if phrase_count_errors or len(missing_field_errors) > 5:
            print("❌ 致命的なバリデーションエラーのため中断します。")
            return None

    # --- ファイル保存 ---
    OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)

    json_filename = f"{theme_slug}_{phrase_count}_{timestamp}.json"
    md_filename = f"{theme_slug}_{phrase_count}_{timestamp}.md"

    json_path = OUTPUT_BASE_DIR / json_filename
    md_path = OUTPUT_BASE_DIR / md_filename

    # JSON 保存
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ 台本JSON保存: {json_path}")

    # Markdown 保存
    md_content = _script_to_markdown(data)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"✅ 台本Markdown保存: {md_path}")

    # --- サマリー表示 ---
    phrases = data.get("phrases", [])
    diff_counts = {}
    for p in phrases:
        d = p.get("difficulty", "unknown")
        diff_counts[d] = diff_counts.get(d, 0) + 1
    review_count = sum(1 for p in phrases if p.get("is_review"))

    print(f"\n📊 生成サマリー:")
    print(f"  テーマ: {theme}")
    print(f"  フレーズ数: {len(phrases)}")
    print(f"  難易度配分: {diff_counts}")
    print(f"  復習対象: {review_count}個")
    print(f"  タイトル候補:")
    for i, t in enumerate(data.get("meta", {}).get("title_candidates", []), 1):
        print(f"    {i}. {t}")

    return data


# --- CLI エントリーポイント ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Podcast台本生成")
    parser.add_argument(
        "--theme",
        default="ビジネスメールで使える英語表現30選",
        help="テーマ名",
    )
    parser.add_argument("--count", type=int, default=30, help="フレーズ数")
    parser.add_argument(
        "--audience", default="社会人・大学生", help="対象者"
    )
    parser.add_argument(
        "--detail", default="normal",
        choices=["brief", "normal", "detailed"],
        help="解説の詳しさ",
    )
    args = parser.parse_args()

    result = generate_podcast_script(
        theme=args.theme,
        phrase_count=args.count,
        target_audience=args.audience,
        detail_level=args.detail,
    )
    if result is None:
        print("\n❌ 台本生成に失敗しました。")
        exit(1)
    else:
        print("\n✅ 台本生成完了。レビューしてください。")
