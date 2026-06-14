#!/usr/bin/env python3
"""
oauth_setup.py
YouTube Data API v3 用の OAuth 2.0 認証トークンを取得・保存するスクリプト。

認証URLを表示してコードを手動入力する方式（サンドボックス環境向け）。

使い方:
  python3 scripts/oauth_setup.py
"""

import os
import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE_DIR    = os.path.join(os.path.dirname(__file__), "..")
SECRET_FILE = os.path.join(BASE_DIR, "config", "client_secret.json")
TOKEN_FILE  = os.path.join(BASE_DIR, "config", "token.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_credentials():
    creds = None

    # 既存トークンがあれば読み込む
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # トークンが無効または期限切れなら更新/再取得
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            print("[INFO] トークンを自動更新しました")
        else:
            # ブラウザで認証（ローカルサーバ方式）。
            # OOB(urn:ietf:wg:oauth:2.0:oob) は Google が廃止したため、
            # デスクトップ環境ではローカルサーバ方式を使う。
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(SECRET_FILE, scopes=SCOPES)
            print("\nブラウザが開きます。気合イングリッシュのGoogleアカウントで認証してください...")
            creds = flow.run_local_server(port=0, prompt="consent")
            print("[INFO] 新規認証が完了しました")

        # トークンを保存
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        print(f"[OK] トークン保存: {TOKEN_FILE}")

    return creds


def main():
    print("=== YouTube OAuth 認証セットアップ ===")
    creds = get_credentials()

    # 認証確認: チャンネル情報を取得
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="snippet", mine=True).execute()

    if resp.get("items"):
        ch = resp["items"][0]["snippet"]
        print(f"\n[OK] 認証成功!")
        print(f"  チャンネル名: {ch['title']}")
        print(f"  チャンネルID: {resp['items'][0]['id']}")
    else:
        print("[WARN] チャンネル情報を取得できませんでした")

    print("\n認証トークンの準備が完了しました。")
    print("次のステップ: python3 scripts/create_playlists.py を実行してください。")


if __name__ == "__main__":
    main()
