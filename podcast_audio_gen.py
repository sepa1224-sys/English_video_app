"""
podcast_audio_gen.py — Podcast Mode 音声生成

ElevenLabs API を使って、台本JSONから音声ファイルを生成する。
ハイブリッド戦略: 英語→ネイティブAI声、日本語→ユーザーのクローン声

仕様書: docs/specs/podcast_mode_spec.md §4
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# --- 定数 ---
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_ENGLISH_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam
MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]

# voice_settings プリセット
VOICE_SETTINGS_EN_SLOW = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "speed": 0.85,
}
VOICE_SETTINGS_EN_NORMAL = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "speed": 1.0,
}
VOICE_SETTINGS_JA_DEFAULT = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "speed": 1.0,
}
# 先行テスト用のバリエーション
VOICE_SETTINGS_JA_CLONE_BOOST = {
    "stability": 0.5,
    "similarity_boost": 0.85,
    "speed": 1.0,
}
VOICE_SETTINGS_JA_CLONE_STABLE = {
    "stability": 0.7,
    "similarity_boost": 0.85,
    "speed": 1.0,
}


def _load_config():
    """環境変数を読み込み、必須チェックを行う"""
    load_dotenv()

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError(
            "ELEVENLABS_API_KEY が設定されていません。\n"
            ".env ファイルに追加してください。参考: .env.example"
        )

    user_ja_voice = os.getenv("ELEVENLABS_VOICE_ID_USER_JA")
    if not user_ja_voice:
        raise ValueError(
            "ELEVENLABS_VOICE_ID_USER_JA が設定されていません。\n"
            "ElevenLabs で Voice Cloning を作成し、Voice ID を .env に追加してください。"
        )

    en_voice = os.getenv("ELEVENLABS_VOICE_ID_ENGLISH_MALE", DEFAULT_ENGLISH_VOICE)
    model = os.getenv("PODCAST_TTS_MODEL", DEFAULT_MODEL)

    return {
        "api_key": api_key,
        "voice_en": en_voice,
        "voice_ja": user_ja_voice,
        "model": model,
    }


def _generate_speech(
    text: str,
    voice_id: str,
    api_key: str,
    model_id: str,
    voice_settings: dict,
    output_path: Path,
) -> bool:
    """
    ElevenLabs API で音声を生成し、ファイルに保存する。

    Returns:
        True: 成功, False: 失敗
    """
    url = ELEVENLABS_API_URL.format(voice_id=voice_id)
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": voice_settings,
    }

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(response.content)
                return True
            elif response.status_code == 401:
                print(f"  ❌ 認証エラー: ELEVENLABS_API_KEY が無効です。")
                return False
            elif response.status_code == 404:
                print(f"  ❌ Voice ID が見つかりません: {voice_id}")
                return False
            elif response.status_code in (402, 429):
                if response.status_code == 402:
                    print(f"  ❌ クレジット不足です。ElevenLabs のプランを確認してください。")
                    return False
                # 429: レート制限
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    print(f"  ⏳ レート制限。{wait}秒後にリトライ ({attempt + 1}/{MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    print(f"  ❌ レート制限が解除されません。")
                    return False
            else:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF[attempt]
                    print(f"  ⏳ API エラー ({response.status_code})。{wait}秒後にリトライ")
                    time.sleep(wait)
                else:
                    print(f"  ❌ API エラー ({response.status_code}): {response.text[:200]}")
                    return False
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  ⏳ タイムアウト。{wait}秒後にリトライ ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                print(f"  ❌ タイムアウトが解消されません。")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  ⏳ 通信エラー: {e}。{wait}秒後にリトライ")
                time.sleep(wait)
            else:
                print(f"  ❌ 通信エラー: {e}")
                return False

    return False


def _load_manifest(manifest_path: Path) -> dict:
    """マニフェストを読み込む。なければ新規作成用の空dictを返す"""
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"completed": [], "failed": [], "status": "new"}


def _save_manifest(manifest_path: Path, manifest: dict):
    """マニフェストを保存する"""
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_pilot_test(script_path: str) -> dict:
    """
    先行テスト: 5ファイルを生成して voice_settings の最適値を検証する。

    生成ファイル:
      - pilot_opening_default.mp3      (JA, stability=0.5, similarity_boost=0.75)
      - pilot_opening_clone_boost.mp3   (JA, stability=0.5, similarity_boost=0.85)
      - pilot_opening_clone_stable.mp3  (JA, stability=0.7, similarity_boost=0.85)
      - pilot_phrase1_en_slow.mp3       (EN, speed=0.85)
      - pilot_phrase1_en_normal.mp3     (EN, speed=1.0)

    Returns:
        生成結果の dict（ファイルパス、サイズ、成否）
    """
    config = _load_config()
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))

    # 出力先ディレクトリ
    script_stem = Path(script_path).stem
    pilot_dir = Path("output/podcast/audio") / f"{script_stem}_pilot"
    pilot_dir.mkdir(parents=True, exist_ok=True)

    opening_text = script["opening"]["narration_ja"]
    phrase1_en = script["phrases"][0]["phrase_en"]

    # 5パターン定義
    tests = [
        {
            "name": "pilot_opening_default",
            "text": opening_text,
            "voice_id": config["voice_ja"],
            "settings": VOICE_SETTINGS_JA_DEFAULT,
            "desc": "日本語クローン (default: stab=0.5, sim=0.75)",
        },
        {
            "name": "pilot_opening_clone_boost",
            "text": opening_text,
            "voice_id": config["voice_ja"],
            "settings": VOICE_SETTINGS_JA_CLONE_BOOST,
            "desc": "日本語クローン (clone_boost: stab=0.5, sim=0.85)",
        },
        {
            "name": "pilot_opening_clone_stable",
            "text": opening_text,
            "voice_id": config["voice_ja"],
            "settings": VOICE_SETTINGS_JA_CLONE_STABLE,
            "desc": "日本語クローン (clone_stable: stab=0.7, sim=0.85)",
        },
        {
            "name": "pilot_phrase1_en_slow",
            "text": phrase1_en,
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_SLOW,
            "desc": "英語 Adam (speed=0.85)",
        },
        {
            "name": "pilot_phrase1_en_normal",
            "text": phrase1_en,
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_NORMAL,
            "desc": "英語 Adam (speed=1.0)",
        },
    ]

    results = {}
    total_chars = 0
    for t in tests:
        out_path = pilot_dir / f"{t['name']}.mp3"
        print(f"🎙 {t['desc']}")
        print(f"  テキスト: {t['text'][:50]}...")

        success = _generate_speech(
            text=t["text"],
            voice_id=t["voice_id"],
            api_key=config["api_key"],
            model_id=config["model"],
            voice_settings=t["settings"],
            output_path=out_path,
        )

        char_count = len(t["text"])
        total_chars += char_count
        if success:
            size = out_path.stat().st_size
            print(f"  ✅ 生成完了: {out_path.name} ({size:,} bytes, {char_count}文字)")
            results[t["name"]] = {"path": str(out_path), "size": size, "chars": char_count, "ok": True}
        else:
            print(f"  ❌ 生成失敗: {t['name']}")
            results[t["name"]] = {"path": str(out_path), "size": 0, "chars": char_count, "ok": False}

    print(f"\n📊 先行テスト完了: {sum(1 for r in results.values() if r['ok'])}/5 成功")
    print(f"  消費クレジット（概算）: {total_chars}")
    print(f"  出力先: {pilot_dir}")

    return results


def generate_all_audio(script_path: str, voice_settings_ja: dict = None) -> bool:
    """
    台本JSONから全音声ファイルを生成する。

    Args:
        script_path: 台本JSONのパス
        voice_settings_ja: 日本語クローン声の voice_settings（先行テストで確定した値）。
                           None の場合はデフォルト値を使用。

    Returns:
        True: 全ファイル生成完了, False: 一部失敗
    """
    config = _load_config()
    script = json.loads(Path(script_path).read_text(encoding="utf-8"))

    ja_settings = voice_settings_ja or VOICE_SETTINGS_JA_DEFAULT

    # 出力先ディレクトリ
    script_stem = Path(script_path).stem
    audio_dir = Path("output/podcast/audio") / script_stem
    audio_dir.mkdir(parents=True, exist_ok=True)

    # マニフェスト（リジューム用）
    manifest_path = audio_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest["status"] == "new":
        manifest["script_file"] = script_path
        manifest["status"] = "in_progress"

    completed = set(manifest["completed"])

    # --- 生成タスクリスト ---
    tasks = []

    # オープニング
    tasks.append({
        "filename": "opening.mp3",
        "text": script["opening"]["narration_ja"],
        "voice_id": config["voice_ja"],
        "settings": ja_settings,
    })

    # メインパート（30フレーズ × 5パーツ）
    for p in script["phrases"]:
        pid = f"{p['id']:02d}"
        tasks.append({
            "filename": f"phrase_{pid}_en.mp3",
            "text": p["phrase_en"],
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_SLOW,
        })
        tasks.append({
            "filename": f"phrase_{pid}_ja_meaning.mp3",
            "text": p["meaning_ja"],
            "voice_id": config["voice_ja"],
            "settings": ja_settings,
        })
        tasks.append({
            "filename": f"phrase_{pid}_ja_explanation.mp3",
            "text": p["explanation_ja"],
            "voice_id": config["voice_ja"],
            "settings": ja_settings,
        })
        tasks.append({
            "filename": f"phrase_{pid}_en_example.mp3",
            "text": p["example_en"],
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_SLOW,
        })
        tasks.append({
            "filename": f"phrase_{pid}_en_reread.mp3",
            "text": p["phrase_en"],
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_NORMAL,
        })

    # 復習パート
    review_phrases = [p for p in script["phrases"] if p.get("is_review")]
    tasks.append({
        "filename": "review_intro.mp3",
        "text": "それでは復習です。特に重要なフレーズを10個、もう一度聞いてみましょう。",
        "voice_id": config["voice_ja"],
        "settings": ja_settings,
    })
    for i, p in enumerate(review_phrases, 1):
        rid = f"{i:02d}"
        tasks.append({
            "filename": f"review_{rid}_en.mp3",
            "text": p["phrase_en"],
            "voice_id": config["voice_en"],
            "settings": VOICE_SETTINGS_EN_SLOW,
        })
        tasks.append({
            "filename": f"review_{rid}_ja.mp3",
            "text": p["meaning_ja"],
            "voice_id": config["voice_ja"],
            "settings": ja_settings,
        })

    # エンディング
    tasks.append({
        "filename": "ending.mp3",
        "text": script["ending"]["narration_ja"],
        "voice_id": config["voice_ja"],
        "settings": ja_settings,
    })

    # --- 生成実行 ---
    total = len(tasks)
    skipped = 0
    success = 0
    failed = 0

    print(f"🎙 音声生成開始: 全{total}ファイル（生成済み{len(completed)}件はスキップ）")

    for i, task in enumerate(tasks, 1):
        filename = task["filename"]

        if filename in completed:
            skipped += 1
            continue

        print(f"  [{i}/{total}] {filename} ({len(task['text'])}文字)")
        out_path = audio_dir / filename

        ok = _generate_speech(
            text=task["text"],
            voice_id=task["voice_id"],
            api_key=config["api_key"],
            model_id=config["model"],
            voice_settings=task["settings"],
            output_path=out_path,
        )

        if ok:
            success += 1
            manifest["completed"].append(filename)
        else:
            failed += 1
            manifest["failed"].append(filename)
            # クレジット不足は即停止
            # （_generate_speech 内で 402 の場合は False を返す）

        # 進捗を随時保存（リジューム用）
        _save_manifest(manifest_path, manifest)

    if failed == 0:
        manifest["status"] = "completed"
    else:
        manifest["status"] = "partial"
    manifest["total_files"] = total
    _save_manifest(manifest_path, manifest)

    print(f"\n📊 音声生成完了:")
    print(f"  成功: {success}  スキップ: {skipped}  失敗: {failed}  合計: {total}")
    print(f"  出力先: {audio_dir}")

    return failed == 0


# --- CLI エントリーポイント ---
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Podcast音声生成")
    parser.add_argument("script", help="台本JSONのパス")
    parser.add_argument(
        "--pilot", action="store_true",
        help="先行テスト（5ファイルのみ生成）",
    )
    parser.add_argument(
        "--ja-stability", type=float, default=None,
        help="日本語クローン声の stability（先行テスト後に確定）",
    )
    parser.add_argument(
        "--ja-similarity", type=float, default=None,
        help="日本語クローン声の similarity_boost（先行テスト後に確定）",
    )
    args = parser.parse_args()

    if args.pilot:
        results = run_pilot_test(args.script)
        ok_count = sum(1 for r in results.values() if r["ok"])
        if ok_count == 0:
            print("\n❌ 先行テスト全失敗。設定を確認してください。")
            exit(1)
    else:
        ja_settings = None
        if args.ja_stability is not None or args.ja_similarity is not None:
            ja_settings = {
                "stability": args.ja_stability or 0.5,
                "similarity_boost": args.ja_similarity or 0.75,
                "speed": 1.0,
            }
        success = generate_all_audio(args.script, voice_settings_ja=ja_settings)
        if not success:
            print("\n⚠ 一部ファイルの生成に失敗しました。再実行でリジュームできます。")
            exit(1)
        else:
            print("\n✅ 全音声ファイルの生成が完了しました。")
