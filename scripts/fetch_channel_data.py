#!/usr/bin/env python3
"""
fetch_channel_data.py
気合イングリッシュ チャンネルの全動画データを YouTube Data API v3 で取得する。

出力先:
  data/channel_analysis/kiiai_english_channel.json
  data/channel_analysis/kiiai_english_channel.csv
"""

import os
import json
import csv
import re
import sys
from datetime import datetime, timezone

import requests

# ─────────────────────────────────────────────
# 設定
# ─────────────────────────────────────────────
API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
CHANNEL_HANDLE = "@気合イングリッシュ"
BASE_URL = "https://www.googleapis.com/youtube/v3"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "channel_analysis")
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "kiiai_english_channel.json")
OUTPUT_CSV  = os.path.join(OUTPUT_DIR, "kiiai_english_channel.csv")

CSV_FIELDS = [
    "video_id",
    "title",
    "published_at",
    "view_count",
    "like_count",
    "comment_count",
    "duration_seconds",
    "thumbnail_url",
    "description",
    "tags",
]


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────
def iso8601_duration_to_seconds(duration: str) -> int:
    """ISO 8601 duration (PT1H2M3S) を秒数に変換する。"""
    pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
    m = re.match(pattern, duration)
    if not m:
        return 0
    hours   = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def get_channel_id_by_handle(handle: str) -> str:
    """チャンネルハンドル (@xxx) からチャンネル ID を取得する。"""
    url = f"{BASE_URL}/search"
    params = {
        "part": "snippet",
        "q": handle,
        "type": "channel",
        "maxResults": 5,
        "key": API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    if not items:
        raise ValueError(f"チャンネルが見つかりません: {handle}")
    # 最初の結果を使用
    channel_id = items[0]["snippet"]["channelId"]
    print(f"[INFO] チャンネルID: {channel_id}  ({items[0]['snippet']['title']})")
    return channel_id


def get_uploads_playlist_id(channel_id: str) -> str:
    """チャンネル ID からアップロードプレイリスト ID を取得する。"""
    url = f"{BASE_URL}/channels"
    params = {
        "part": "contentDetails",
        "id": channel_id,
        "key": API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    playlist_id = (
        data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    )
    print(f"[INFO] アップロードプレイリストID: {playlist_id}")
    return playlist_id


def get_all_video_ids(playlist_id: str) -> list[str]:
    """プレイリストから全動画 ID を取得する（ページネーション対応）。"""
    url = f"{BASE_URL}/playlistItems"
    video_ids = []
    page_token = None

    while True:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
            "key": API_KEY,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])

        page_token = data.get("nextPageToken")
        print(f"[INFO] 取得済み動画数: {len(video_ids)}")
        if not page_token:
            break

    return video_ids


def get_video_details(video_ids: list[str]) -> list[dict]:
    """動画 ID リストから詳細情報を取得する（50件ずつバッチ処理）。"""
    url = f"{BASE_URL}/videos"
    videos = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(batch),
            "key": API_KEY,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("items", []):
            snippet     = item.get("snippet", {})
            stats       = item.get("statistics", {})
            content     = item.get("contentDetails", {})
            thumbnails  = snippet.get("thumbnails", {})
            thumb_url   = (
                thumbnails.get("maxres", {}).get("url")
                or thumbnails.get("high", {}).get("url")
                or thumbnails.get("default", {}).get("url")
                or ""
            )

            videos.append({
                "video_id":       item["id"],
                "title":          snippet.get("title", ""),
                "published_at":   snippet.get("publishedAt", ""),
                "view_count":     int(stats.get("viewCount", 0)),
                "like_count":     int(stats.get("likeCount", 0)),
                "comment_count":  int(stats.get("commentCount", 0)),
                "duration_seconds": iso8601_duration_to_seconds(
                    content.get("duration", "PT0S")
                ),
                "thumbnail_url":  thumb_url,
                "description":    snippet.get("description", ""),
                "tags":           "|".join(snippet.get("tags", [])),
            })

        print(f"[INFO] 詳細取得済み: {len(videos)} 件")

    return videos


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    if not API_KEY:
        print("[ERROR] 環境変数 YOUTUBE_API_KEY が設定されていません。")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== 気合イングリッシュ チャンネルデータ取得開始 ===")
    print(f"実行日時: {datetime.now(timezone.utc).isoformat()}")

    # Step 1: チャンネル ID 取得
    channel_id = get_channel_id_by_handle(CHANNEL_HANDLE)

    # Step 2: アップロードプレイリスト ID 取得
    playlist_id = get_uploads_playlist_id(channel_id)

    # Step 3: 全動画 ID 取得
    video_ids = get_all_video_ids(playlist_id)
    print(f"[INFO] 総動画数: {len(video_ids)}")

    # Step 4: 動画詳細取得
    videos = get_video_details(video_ids)

    # 公開日の新しい順にソート
    videos.sort(key=lambda v: v["published_at"], reverse=True)

    # Step 5: JSON 保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "channel_id": channel_id,
                "total_videos": len(videos),
                "videos": videos,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[OK] JSON 保存: {OUTPUT_JSON}")

    # Step 6: CSV 保存
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(videos)
    print(f"[OK] CSV 保存: {OUTPUT_CSV}")

    # Step 7: 先頭10行をコンソール表示
    print("\n=== CSV 先頭10行 ===")
    print(",".join(CSV_FIELDS))
    for v in videos[:10]:
        row = [
            v["video_id"],
            v["title"][:40],
            v["published_at"][:10],
            str(v["view_count"]),
            str(v["like_count"]),
            str(v["comment_count"]),
            str(v["duration_seconds"]),
            v["thumbnail_url"][:40],
            v["description"][:30].replace("\n", " "),
            v["tags"][:30],
        ]
        print(",".join(row))

    print(f"\n=== 完了: 合計 {len(videos)} 件の動画データを取得しました ===")


if __name__ == "__main__":
    main()
