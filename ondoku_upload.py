"""音読動画を YouTube に上げる。

必要な権限が既存の youtube-api.ts（読み取り専用）と違うため、
このスクリプト専用に OAuth を取り直す。廃止された OOB ではなく
ループバック方式（ブラウザが自動で開く）を使う。
"""
from __future__ import annotations
import argparse, time, json, sys, time
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",     # 動画の投稿
    "https://www.googleapis.com/auth/youtube.force-ssl",  # サムネ・字幕・再生リスト
]
SECRET = Path("config/client_secret.json")
TOKEN = Path("config/youtube_token.json")


def service():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not SECRET.exists():
                raise SystemExit(
                    f"❌ {SECRET} がありません。\n"
                    "   Google Cloud Console → 認証情報 → OAuth クライアント ID\n"
                    "   （種類: デスクトップ アプリ）を作成し、JSON をここに置いてください。")
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
            # access_type=offline と prompt=consent が無いと refresh_token が返らない
            creds = flow.run_local_server(port=0, access_type="offline",
                                          prompt="consent")
        TOKEN.parent.mkdir(parents=True, exist_ok=True)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def to_rfc3339(text: str) -> str:
    """'2026-09-04 07:00' のような書き方を、端末の時間帯つきISO8601に直す。"""
    from datetime import datetime
    t = text.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            d = datetime.strptime(t, fmt)
            break
        except ValueError:
            d = None
    if d is None:
        return text          # 既にISO8601とみなす
    return d.astimezone().isoformat()


def upload(yt, video: Path, title: str, description: str, tags: list[str],
           privacy: str, publish_at: str | None = None) -> str:
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        # 予約公開は private でしか受け付けられない。指定時刻にYouTube側が公開する。
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    body = {
        "snippet": {"title": title, "description": description,
                    "tags": tags, "categoryId": "27"},   # 27 = 教育
        "status": status,
    }
    # chunksize=-1 は全体を1回で送るため、切断すると最初からになる。
    # 4MB ずつ送れば、途中で切れてもその塊だけ再送すれば済む。
    media = MediaFileUpload(str(video), chunksize=4 * 1024 * 1024,
                            resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    res, fails = None, 0
    while res is None:
        try:
            status, res = req.next_chunk()
            fails = 0
            if status:
                print(f"  アップロード {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status not in (500, 502, 503, 504):
                raise
            fails += 1
            if fails > 8:
                raise
            wait = 2 ** fails
            print(f"  一時エラー {e.resp.status}／{wait}秒後に再送 ({fails}/8)")
            time.sleep(wait)
        except (ConnectionError, OSError) as e:
            fails += 1
            if fails > 8:
                raise
            wait = 2 ** fails
            print(f"  通信が切れました／{wait}秒後に再開 ({fails}/8): {type(e).__name__}")
            time.sleep(wait)
    return res["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube にアップロード")
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description-file", required=True)
    ap.add_argument("--thumbnail")
    ap.add_argument("--captions", help="日本語字幕の SRT")
    ap.add_argument("--playlist", help="追加する再生リスト名。カンマ区切りで複数可（無ければ作る）")
    ap.add_argument("--playlist-privacy", default="unlisted",
                    choices=["private", "unlisted", "public"],
                    help="新規作成する再生リストの公開範囲")
    ap.add_argument("--privacy", default="unlisted",
                    choices=["private", "unlisted", "public"])
    ap.add_argument("--tags", default="英語,英語学習,教養,リスニング,多読")
    a = ap.parse_args()

    yt = service()
    desc = Path(a.description_file).read_text(encoding="utf-8")
    print(f"▶ 投稿中: {a.title} ({a.privacy})")
    pub = None
    if a.publish_at:
        pub = to_rfc3339(a.publish_at)
        print(f"  予約公開: {pub}")
    vid = upload(yt, Path(a.video), a.title, desc, a.tags.split(","), a.privacy, pub)
    url = f"https://www.youtube.com/watch?v={vid}"
    print(f"✅ 投稿完了: {url}")

    if a.thumbnail:
        yt.thumbnails().set(videoId=vid,
                            media_body=MediaFileUpload(a.thumbnail)).execute()
        print("✅ サムネイル設定")

    if a.captions:
        yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": vid, "language": "ja",
                              "name": "日本語", "isDraft": False}},
            media_body=MediaFileUpload(a.captions)).execute()
        print("✅ 日本語字幕を追加")

    for name in [n.strip() for n in (a.playlist or "").split(",") if n.strip()]:
        # 50件で切ると既存を見落として同名を作ってしまうため、全ページ見る
        pls, req = {}, yt.playlists().list(part="snippet", mine=True, maxResults=50)
        while req:
            r = req.execute()
            for p_ in r["items"]:
                pls[p_["snippet"]["title"]] = p_["id"]
            req = yt.playlists().list_next(req, r)
        pid = pls.get(name)
        if not pid:
            # 直前の作成/改名が一覧に反映されるまで数秒かかる。
            # 待たずに作ると同名の再生リストが二重にできる。
            time.sleep(4)
            pls2, req2 = {}, yt.playlists().list(part="snippet", mine=True, maxResults=50)
            while req2:
                r2 = req2.execute()
                for p2 in r2["items"]:
                    pls2[p2["snippet"]["title"]] = p2["id"]
                req2 = yt.playlists().list_next(req2, r2)
            pid = pls2.get(name)
        if not pid:
            pid = yt.playlists().insert(
                part="snippet,status",
                body={"snippet": {"title": name},
                      "status": {"privacyStatus": a.playlist_privacy}}).execute()["id"]
            print(f"  再生リストを作成: {name}（{a.playlist_privacy}）")
        # 作成直後は反映待ちで404になることがあるので少し粘る
        for wait in (0, 5, 10, 20):
            if wait:
                time.sleep(wait)
            try:
                yt.playlistItems().insert(
                    part="snippet",
                    body={"snippet": {"playlistId": pid,
                                      "resourceId": {"kind": "youtube#video",
                                                     "videoId": vid}}}).execute()
                print(f"✅ 再生リストに追加: {name}")
                break
            except HttpError as e:
                last = e
        else:
            print(f"⚠ 再生リストに追加できず: {name} — {last}")

    print(f"\n{url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
