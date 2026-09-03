"""
ondoku_storyboard.py — 音読教材から動画の絵コンテを生成する

kiai-coaching-app の materials/*.json を読み、
  - 文ごとの日本語訳（字幕用）
  - シーンごとのイラスト生成プロンプト（英語・絵柄は固定）
を Claude で作る。
"""

import os
import json
import argparse
import datetime
from pathlib import Path
from dotenv import load_dotenv

import anthropic

from podcast_script_gen import _extract_tool_input, _validate_model

MATERIALS_DIR = materials_dir()
OUTPUT_DIR = Path("output") / "ondoku"

# 全カットで共通の絵柄。--style で切り替える。
# 絵コンテのpromptは「何が描かれているか」だけを持ち、画風はここで後付けする。
from ondoku_profiles import PROFILES, DEFAULT_PROFILE, paths, materials_dir

STYLES = {
    # 銅版画・木版画（ポッドキャスト用。古書の挿絵の質感）
    # z_image はプロンプトが約800字を超えると失敗するため簡潔に保つこと
    "engraving": (
        "antique copperplate engraving illustration, dense fine hatching and "
        "cross-hatching, crisp black ink linework on warm aged paper, "
        "no color or only a single muted sepia tone, high contrast between "
        "deep blacks and bare paper, old encyclopedia plate feel, "
        "visible plate texture and slight print imperfections, "
        "no text, no letters, no words, no watermark, horizontal composition"
    ),
    # 手描き・水彩（絵本寄り）
    "handdrawn": (
        "hand-drawn illustration, visible pencil and ink linework, "
        "slightly rough uneven outlines, muted desaturated earth-tone palette, "
        "soft paper grain texture, flat shading with light watercolor washes, "
        "warm and calm, storybook feel, no text, no letters, no words, "
        "no watermark, horizontal composition"
    ),
    # フラットベクター（Kurzgesagt風）
    "flat": (
        # z_image はプロンプトが約800字を超えると失敗するため簡潔に保つこと
        "flat vector illustration, no outlines, bold color blocking, extremely "
        "vibrant neon-saturated colors, deep violet and hot magenta, electric "
        "purple, vivid cyan, intense lime green, richly saturated orange to "
        "yellow gradient sky, never pastel, never muted, never washed out, "
        "faceted crystalline rocks, simple leaf silhouettes, cute minimal "
        "creatures with dot eyes, smooth gradients, no texture, maximum color "
        "contrast, no text, horizontal composition"
    ),
    # 水彩エディトリアル（TED-Ed風・明るく彩度高め）
    "watercolor": (
        "editorial watercolor illustration, loose confident brush strokes with "
        "visible pigment pooling and soft bleeding edges, clean simple shapes "
        "over the wash, bright saturated but natural palette, warm ochre, deep "
        "teal, soft coral, generous white paper showing through, subtle cold "
        "press paper texture, light ink accents, airy and uncluttered, "
        "explanatory science illustration feel, no text, no letters, "
        "no watermark, horizontal composition"
    ),
    # 実写ドキュメンタリー（ディスカバリーチャンネル風）
    "documentary": (
        "photorealistic wildlife documentary still frame, shot on a long "
        "telephoto lens, shallow depth of field with soft bokeh, natural golden "
        "hour light, crisp feather and texture detail, subtle atmospheric haze, "
        "cinematic color grading, filmic contrast, BBC Planet Earth aesthetic, "
        "no illustration, no cartoon, no text, no watermark, horizontal "
        "composition"
    ),
}
DEFAULT_STYLE = "flat"
STYLE_SUFFIX = STYLES[DEFAULT_STYLE]   # 後方互換

STORYBOARD_TOOL = {
    "name": "submit_storyboard",
    "description": "音読教材の動画用の絵コンテを提出する。",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_ja": {
                "type": "string",
                "description": "動画用の日本語タイトル（英題の直訳ではなく、興味を引く形に）",
            },
            "youtube_title_candidates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "YouTubeのタイトル候補を3つ。英語学習コンテンツと分かる形に",
            },
            "youtube_description": {
                "type": "string",
                "description": "YouTubeの概要欄。内容紹介と重要フレーズを含む",
            },
            "sentences": {
                "type": "array",
                "description": "本文を文単位に分割したもの。字幕に使う",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "1からの連番"},
                        "para": {"type": "integer", "description": "元の段落番号(1始まり)"},
                        "en": {
                            "type": "string",
                            "description": "英文。本文から一字一句そのまま抜き出すこと",
                        },
                        "ja": {
                            "type": "string",
                            "description": "自然な日本語訳。直訳しない",
                        },
                    },
                    "required": ["id", "para", "en", "ja"],
                },
            },
            "scenes": {
                "type": "array",
                "description": "イラストを差し替える単位。1シーン=1枚の絵",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "sentence_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "このシーンで表示する文のid",
                        },
                        "prompt": {
                            "type": "string",
                            "description": (
                                "画像生成用の英語プロンプト。何が描かれているかを具体的に。"
                                "画風の指定は書かない（別途付与するため）。"
                                "文字・文章は絶対に描かせない"
                            ),
                        },
                        "motion": {
                            "type": "boolean",
                            "description": (
                                "このシーンを動画化(image-to-video)する価値があるか。"
                                "冒頭と山場だけ true にし、全体の3割以下に抑える"
                            ),
                        },
                    },
                    "required": ["id", "sentence_ids", "prompt", "motion"],
                },
            },
        },
        "required": [
            "title_ja", "youtube_title_candidates", "youtube_description",
            "sentences", "scenes",
        ],
    },
}

# 長い教材は1回の応答に収まらず文IDを見失うため、2段階に分ける。
SENTENCE_TOOL = {
    "name": "submit_sentences",
    "description": "本文を文に分割し、日本語訳を付ける。",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentences": STORYBOARD_TOOL["input_schema"]["properties"]["sentences"],
        },
        "required": ["sentences"],
    },
}

SCENE_TOOL = {
    "name": "submit_scenes",
    "description": "分割済みの文にシーンを割り当てる。",
    "input_schema": {
        "type": "object",
        "properties": {
            k: STORYBOARD_TOOL["input_schema"]["properties"][k]
            for k in STORYBOARD_TOOL["input_schema"]["properties"]
            if k != "sentences"
        },
        "required": [k for k in STORYBOARD_TOOL["input_schema"]["required"]
                     if k != "sentences"],
    },
}

TWO_PASS_THRESHOLD = 40   # この文数を超えたら2段階にする


SYSTEM_PROMPT = """あなたは英語学習動画の演出家です。
日本人学習者向けの教養系リーディング教材から、YouTube動画の絵コンテを作ってください。

## 動画の形式
- 画面上部にイラスト、中央にSVO色分けした英文、下部に日本語訳字幕
- 英語ナレーションが流れ、読まれている箇所がハイライトされる
- TED-Edのような、静かで知的なトーン

## 文の分割（sentences）
- 本文をピリオド単位で文に分割する
- **en は本文から一字一句そのまま抜き出すこと。** 言い換え・省略・記号の変更を一切しない
- ja は自然な日本語にする。英語の語順に引きずられないこと
  例: "The sky is not a road for this bird. It is home."
      → ○「この鳥にとって空は通り道ではありません。住まいなのです。」
      × 「空はこの鳥にとって道ではない。それは家である。」

## シーン分け（scenes）
- 1シーン = イラスト1枚。目安は1シーンあたり1〜3文
- **場面が変わるところで切る。** 同じ絵で通せる文はまとめる
- prompt は「何が描かれているか」を具体的に書く。抽象的な指示にしない
  ○ "a small dark bird sleeping in mid-air high above night clouds, moonlight, stars"
  × "a bird in the sky"
- **文字・数字・文章を絵の中に描かせない。** 図解が必要な場合も文字なしで表現する
- motion は冒頭の掴みと、最も印象的な1〜2シーンだけ true にする

## YouTube向けメタデータ
- タイトル候補は「英語学習コンテンツだと分かること」と「内容の面白さ」を両立させる
- 概要欄には内容紹介、レベル表記、重要フレーズを含める"""


def build_storyboard(material_id: str, style: str = DEFAULT_STYLE) -> dict | None:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY が設定されていません。")

    path = MATERIALS_DIR / f"{material_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"教材が見つかりません: {path}")
    material = json.loads(path.read_text(encoding="utf-8"))

    # 本文を段落ごとに復元
    paras = []
    for p in material["content"]["paragraphs"]:
        paras.append(" ".join(w["w"] for w in p if "w" in w))

    body = "\n\n".join(f"[段落{i}] {t}" for i, t in enumerate(paras, 1))
    phrases = "\n".join(
        f"- {p['en']} = {p['ja']}" for p in material["content"]["phrases"]
    )

    user_prompt = (
        f"タイトル: {material['title']}\n"
        f"テーマ: {material['theme']}\n"
        f"レベル: {material['level']}\n\n"
        f"重要フレーズ:\n{phrases}\n\n"
        f"本文:\n{body}"
    )

    model = _validate_model(os.getenv("PODCAST_SCRIPT_MODEL", "claude-opus-5"))
    client = anthropic.Anthropic(api_key=api_key)

    def _call(tools, name, msgs):
        r = client.messages.create(
            model=model, max_tokens=16384, system=SYSTEM_PROMPT,
            messages=msgs, tools=tools,
            tool_choice={"type": "tool", "name": name},
        )
        return _extract_tool_input(r, name)

    n_sent = sum(t.count(".") + t.count("!") + t.count("?") for t in paras)
    if n_sent <= TWO_PASS_THRESHOLD:
        print(f"🎬 絵コンテ生成中... (model: {model})")
        data = _call([STORYBOARD_TOOL], STORYBOARD_TOOL["name"],
                     [{"role": "user", "content": user_prompt}])
        if data is None:
            print("❌ tool_use ブロックが返りませんでした。")
            return None
    else:
        # 長文は 文分割 → シーン設計 の2段階。1回の出力量を半分に抑える。
        print(f"🎬 絵コンテ生成中... 長文のため2段階 (model: {model}, 約{n_sent}文)")
        print("  [1/2] 文の分割と翻訳")
        first = _call([SENTENCE_TOOL], SENTENCE_TOOL["name"],
                      [{"role": "user", "content": user_prompt}])
        if first is None:
            print("❌ 文分割が返りませんでした。")
            return None
        sents = first["sentences"]
        print(f"       {len(sents)}文")

        listing = "\n".join(f'{x["id"]}: {x["en"]}' for x in sents)
        print("  [2/2] シーンの設計")
        second = _call(
            [SCENE_TOOL], SCENE_TOOL["name"],
            [{"role": "user", "content":
              f"{user_prompt}\n\n## 分割済みの文（この id をそのまま使うこと）\n"
              f"{listing}\n\n上の全 {len(sents)} 文を、"
              f"id 1〜{len(sents)} のどれも漏らさず重複させずにシーンへ割り当てること。"}])
        if second is None:
            print("❌ シーン設計が返りませんでした。")
            return None
        data = {"sentences": sents, **second}

    # --- 検証: en が本文と一致するか（ハルシネーション防止） ---
    full = " ".join(paras)
    norm_full = " ".join(full.split())
    problems = []
    for s in data["sentences"]:
        if " ".join(s["en"].split()) not in norm_full:
            problems.append(f"  文{s['id']}: 本文に存在しません -> {s['en'][:60]}")
    ids = {s["id"] for s in data["sentences"]}
    for sc in data["scenes"]:
        missing = [i for i in sc["sentence_ids"] if i not in ids]
        if missing:
            problems.append(f"  シーン{sc['id']}: 存在しない文id {missing}")
    covered = {i for sc in data["scenes"] for i in sc["sentence_ids"]}
    if covered != ids:
        problems.append(f"  シーンに含まれない文: {sorted(ids - covered)}")

    if problems:
        print("⚠ 検証エラー:")
        print("\n".join(problems))
        return None

    # --- 絵柄を全プロンプトに付与 ---
    if style not in STYLES:
        raise ValueError(f"style は次から選んでください: {', '.join(STYLES)}")
    for sc in data["scenes"]:
        sc["prompt_full"] = f"{sc['prompt']}, {STYLES[style]}"

    data["meta"] = {
        "material_id": material_id,
        "material_title": material["title"],
        "theme": material["theme"],
        "level": material["level"],
        "style": style,
        "style_suffix": STYLES[style],
        "model_version": model,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{material_id}_storyboard.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 絵コンテ保存: {out}")

    n_motion = sum(1 for s in data["scenes"] if s["motion"])
    print(f"\n📊 サマリー")
    print(f"  文数: {len(data['sentences'])}")
    print(f"  シーン数: {len(data['scenes'])}（うち動画化: {n_motion}）")
    print(f"  日本語タイトル: {data['title_ja']}")
    return data


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="音読教材から絵コンテを生成")
    ap.add_argument("--id", required=True, help="教材ID（例: 056）")
    ap.add_argument("--style", default=DEFAULT_STYLE, choices=sorted(STYLES),
                    help="絵柄")
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES),
                    help="この系統の絵コンテとして保存する")
    args = ap.parse_args()
    if build_storyboard(args.id, args.style) is None:
        raise SystemExit(1)
    # 以降の画像・動画は系統ごとのファイル名を見るため、そこへ複製しておく。
    # これが無いと手作業のコピーが要り、忘れると古い絵コンテのまま進んでしまう。
    src = OUTPUT_DIR / f"{args.id}_storyboard.json"
    dst = paths(args.id, args.profile)["storyboard"]
    if src.exists() and src != dst:
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"✅ {args.profile} 用に保存: {dst}")
