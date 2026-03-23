#!/usr/bin/env python3
"""
upload_video.py
動画ファイルを YouTube にアップロードし、ジャンルマスターに基づいて
再生リストへ自動追加するスクリプト。

使い方:
  python3 scripts/upload_video.py \\
      --file output/my_video.mp4 \\
      --genre vocab_teppeki \\
      --title "【英語音声のみ】鉄壁 No.1〜500" \\
      [--description "説明文"] \\
      [--privacy public|private|unlisted]

引数:
  --file        アップロードする動画ファイルのパス（必須）
  --genre       genre_master.json に定義されたジャンルID（必須）
  --title       動画タイトル（必須）
  --description 動画説明文（省略時はジャンルのデフォルト説明を使用）
  --privacy     公開設定: public / private / unlisted（デフォルト: public）
"""

import os
import json
import argparse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR    = os.path.join(os.path.dirname(__file__), "..")
TOKEN_FILE  = os.path.join(BASE_DIR, "config", "token.json")
MASTER_FILE = os.path.join(BASE_DIR, "data", "channel_analysis", "genre_master.json")

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
            token_data["token"] = creds.token
            with open(TOKEN_FILE, "w") as f:
                json.dump(token_data, f, indent=2)
            print("[INFO] トークンを自動更新しました")

    return creds


def upload_video(youtube, file_path, title, description, tags, privacy):
    """動画をアップロードして video_id を返す"""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",  # Education
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        file_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 10,  # 10MB チャンク
    )

    print(f"[INFO] アップロード開始: {os.path.basename(file_path)}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            progress = int(status.progress() * 100)
            print(f"  進捗: {progress}%", end="\r")

    print(f"\n[OK] アップロード完了: video_id = {response['id']}")
    return response["id"]


def add_to_playlist(youtube, video_id, playlist_id):
    """動画を再生リストに追加する"""
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
        }
    }
    youtube.playlistItems().insert(
        part="snippet",
        body=body,
    ).execute()
    print(f"[OK] 再生リストに追加: playlist_id = {playlist_id}")


def main():
    parser = argparse.ArgumentParser(description="YouTube 動画自動アップロードスクリプト")
    parser.add_argument("--file",        required=True,  help="動画ファイルのパス")
    parser.add_argument("--genre",       required=True,  help="ジャンルID（genre_master.json参照）")
    parser.add_argument("--title",       required=True,  help="動画タイトル")
    parser.add_argument("--description", default="",     help="動画説明文（省略可）")
    parser.add_argument("--privacy",     default="public",
                        choices=["public", "private", "unlisted"],
                        help="公開設定（デフォルト: public）")
    args = parser.parse_args()

    # ファイル存在確認
    if not os.path.exists(args.file):
        print(f"[ERROR] ファイルが見つかりません: {args.file}")
        return 1

    # genre_master.json を読み込む
    with open(MASTER_FILE) as f:
        master = json.load(f)

    genres = master["genres"]
    if args.genre not in genres:
        print(f"[ERROR] 不明なジャンルID: {args.genre}")
        print(f"  利用可能なジャンル: {list(genres.keys())}")
        return 1

    genre = genres[args.genre]
    playlist_id = genre.get("playlist_id", "")
    tags = genre.get("tags", [])

    # 説明文の組み立て
    description = args.description if args.description else (
        f"気合イングリッシュ - {genre['name']}\n\n"
        f"チャンネル登録はこちら: https://www.youtube.com/@気合イングリッシュ\n\n"
        f"#{' #'.join(tags)}"
    )

    print("=== YouTube 動画自動アップロード ===")
    print(f"  ファイル  : {args.file}")
    print(f"  タイトル  : {args.title}")
    print(f"  ジャンル  : {genre['name']} ({args.genre})")
    print(f"  再生リスト: {playlist_id or '未設定'}")
    print(f"  公開設定  : {args.privacy}")
    print()

    # 認証
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    # アップロード
    video_id = upload_video(
        youtube,
        file_path=args.file,
        title=args.title,
        description=description,
        tags=tags,
        privacy=args.privacy,
    )

    # 再生リストに追加
    if playlist_id:
        add_to_playlist(youtube, video_id, playlist_id)
    else:
        print(f"[WARN] ジャンル '{args.genre}' に playlist_id が設定されていません。再生リストへの追加をスキップします。")

    print(f"\n動画URL: https://www.youtube.com/watch?v={video_id}")
    return 0


if __name__ == "__main__":
    exit(main())
