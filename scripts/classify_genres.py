#!/usr/bin/env python3
"""
classify_genres.py
GPT-4.1-mini を使って既存動画のジャンルを自動分類し、
ジャンルマスター（JSON）と分類済みCSVを出力する。

出力:
  data/channel_analysis/genre_master.json   — ジャンル定義マスター
  data/channel_analysis/videos_with_genre.csv — 動画ごとのジャンル付きCSV
"""

import os
import json
import csv
import time
from openai import OpenAI

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
BASE_DIR  = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR  = os.path.join(BASE_DIR, "data", "channel_analysis")
CSV_IN    = os.path.join(DATA_DIR, "kiiai_english_channel.csv")
GENRE_MASTER_OUT = os.path.join(DATA_DIR, "genre_master.json")
CSV_OUT   = os.path.join(DATA_DIR, "videos_with_genre.csv")

client = OpenAI()

# ─────────────────────────────────────────────
# ジャンル候補の定義（GPTへのヒントとして渡す）
# ─────────────────────────────────────────────
GENRE_CANDIDATES = {
    "vocab_teppeki":    "英単語聞き流し（鉄壁）— 鉄壁の英単語を英語音声で聞き流す動画",
    "vocab_target1900": "英単語聞き流し（ターゲット1900）— ターゲット1900の英単語聞き流し",
    "vocab_target1400": "英単語聞き流し（ターゲット1400）— ターゲット1400の英単語聞き流し",
    "vocab_target1200": "英単語聞き流し（ターゲット1200）— ターゲット1200の英単語聞き流し",
    "vocab_leap":       "英単語聞き流し（LEAP）— 必携英単語LEAPの聞き流し",
    "vocab_other":      "英単語聞き流し（その他）— 上記以外の単語帳の聞き流し",
    "listening_teppeki":"英文リスニング（鉄壁ベース）— 鉄壁の単語を使った英文リスニング・問題付き動画",
    "listening_toeic":  "TOEICリスニング対策 — TOEIC向けリスニング練習",
    "listening_todai":  "東大リスニング対策 — 東大入試のリスニング対策動画",
    "channel_intro":    "チャンネル紹介・コンセプト動画",
    "other":            "上記に当てはまらないその他の動画",
}

SYSTEM_PROMPT = """あなたは英語学習YouTubeチャンネルのコンテンツ分類専門家です。
動画タイトルと説明文を見て、以下のジャンルIDのうち最も適切な1つを選んでください。

ジャンル一覧:
""" + "\n".join(f"- {k}: {v}" for k, v in GENRE_CANDIDATES.items()) + """

必ずJSONで回答してください。形式:
{"genre_id": "ジャンルID", "confidence": "high/medium/low", "reason": "理由（日本語30字以内）"}
"""


def classify_video(video_id: str, title: str, description: str) -> dict:
    """GPTで1本の動画のジャンルを判定する。"""
    user_msg = f"""動画ID: {video_id}
タイトル: {title}
説明文（先頭200字）: {description[:200]}"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    return result


def main():
    # ─── CSV 読み込み ───
    videos = []
    with open(CSV_IN, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            videos.append(row)

    print(f"[INFO] 対象動画数: {len(videos)} 件")
    print("[INFO] GPT による自動分類を開始します...\n")

    results = []
    for i, v in enumerate(videos, 1):
        vid   = v["video_id"]
        title = v["title"]
        desc  = v.get("description", "")

        try:
            cls = classify_video(vid, title, desc)
            genre_id   = cls.get("genre_id", "other")
            confidence = cls.get("confidence", "low")
            reason     = cls.get("reason", "")
        except Exception as e:
            print(f"  [ERROR] {vid}: {e}")
            genre_id, confidence, reason = "other", "low", "分類エラー"

        print(f"  {i:2}/{len(videos)}  [{confidence:6}] {genre_id:25}  {title[:45]}")

        results.append({
            **v,
            "genre_id":   genre_id,
            "confidence": confidence,
            "reason":     reason,
        })

        # レート制限対策（念のため少し待つ）
        time.sleep(0.3)

    # ─── ジャンルマスター JSON 生成 ───
    # 実際に使われたジャンルのみ抽出してマスターを構築
    used_genres = {}
    for r in results:
        gid = r["genre_id"]
        if gid not in used_genres:
            used_genres[gid] = {
                "genre_id":    gid,
                "name":        GENRE_CANDIDATES.get(gid, gid),
                "playlist_id": "",          # 後でYouTube再生リストIDを設定
                "auto_tags":   [],          # 後で設定
                "video_count": 0,
                "total_views": 0,
                "avg_views":   0,
            }
        used_genres[gid]["video_count"] += 1
        used_genres[gid]["total_views"] += int(r.get("view_count", 0))

    for gid, g in used_genres.items():
        if g["video_count"] > 0:
            g["avg_views"] = round(g["total_views"] / g["video_count"])

    genre_master = {
        "version": "1.0",
        "description": "気合イングリッシュ チャンネル ジャンルマスター（自動生成・要人間確認）",
        "genres": used_genres,
    }

    with open(GENRE_MASTER_OUT, "w", encoding="utf-8") as f:
        json.dump(genre_master, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] ジャンルマスター保存: {GENRE_MASTER_OUT}")

    # ─── 分類済み CSV 保存 ───
    fieldnames = list(results[0].keys())
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"[OK] 分類済みCSV保存: {CSV_OUT}")

    # ─── サマリー表示 ───
    print("\n=== ジャンル別 集計 ===")
    print(f"{'ジャンルID':<28} {'動画数':>5} {'合計再生':>9} {'平均再生':>8}")
    print("-" * 60)
    for gid, g in sorted(used_genres.items(), key=lambda x: -x[1]["avg_views"]):
        print(f"{gid:<28} {g['video_count']:>5} {g['total_views']:>9,} {g['avg_views']:>8,}")

    # ─── 信頼度別集計 ───
    conf_counts = {}
    for r in results:
        c = r["confidence"]
        conf_counts[c] = conf_counts.get(c, 0) + 1
    print(f"\n=== 信頼度 ===")
    for c, n in sorted(conf_counts.items()):
        print(f"  {c}: {n}件")

    print(f"\n=== 完了: {len(results)} 件を分類しました ===")


if __name__ == "__main__":
    main()
