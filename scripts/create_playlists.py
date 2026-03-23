#!/usr/bin/env python3
"""
create_playlists.py
genre_master.json に定義された各ジャンルの YouTube 再生リストを作成し、
playlist_id を genre_master.json に書き戻すスクリプト。

使い方:
  python3 scripts/create_playlists.py
"""

import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

BASE_DIR     = os.path.join(os.path.dirname(__file__), "..")
TOKEN_FILE   = os.path.join(BASE_DIR, "config", "token.json")
SECRET_FILE  = os.path.join(BASE_DIR, "config", "client_secret.json")
MASTER_FILE  = os.path.join(BASE_DIR, "data", "channel_analysis", "genre_master.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_credentials():
    """token.json からクレデンシャルを読み込み、必要なら更新する"""
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"],
    )

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # 更新後のトークンを保存
            token_data["token"] = creds.token
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f, indent=2)
            print("[INFO] トークンを自動更新しました")

    return creds


def create_playlist(youtube, title, description, privacy="public"):
    """YouTube に再生リストを作成して playlist_id を返す"""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy,
        },
    }
    resp = youtube.playlists().insert(
        part="snippet,status",
        body=body,
    ).execute()
    return resp["id"]


def main():
    print("=== YouTube 再生リスト作成 ===\n")

    # 認証
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # genre_master.json を読み込む
    with open(MASTER_FILE) as f:
        master = json.load(f)

    genres = master["genres"]
    created = 0
    skipped = 0

    for genre_id, genre in genres.items():
        # すでに playlist_id が設定済みならスキップ
        if genre.get("playlist_id"):
            print(f"[SKIP] {genre_id}: すでに設定済み ({genre['playlist_id']})")
            skipped += 1
            continue

        playlist_title = genre["name"]
        description = f"気合イングリッシュ - {genre['name']}\n\n" \
                      f"ジャンルID: {genre_id}\n" \
                      f"タグ: {', '.join(genre.get('tags', []))}"

        try:
            playlist_id = create_playlist(youtube, playlist_title, description)
            genre["playlist_id"] = playlist_id
            print(f"[OK] {genre_id}: 「{playlist_title}」→ {playlist_id}")
            created += 1
        except Exception as e:
            print(f"[ERROR] {genre_id}: {e}")

    # genre_master.json を更新
    with open(MASTER_FILE, "w") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)

    print(f"\n=== 完了 ===")
    print(f"  作成: {created} 件")
    print(f"  スキップ: {skipped} 件")
    print(f"  genre_master.json を更新しました: {MASTER_FILE}")


if __name__ == "__main__":
    main()
