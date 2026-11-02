"""YouTube を読むだけの道具（書き換えはしない）。収益会議の仕事をする Mac の AI（scripts/media_ai_poll.py）が使う。

  python3 scripts/yt_read.py videos <id> [<id> ...]   … 題・説明文・公開状態・再生数
  python3 scripts/yt_read.py find <ことば>             … 自分のチャンネルの動画から、題に<ことば>を含むものを探す
  python3 scripts/yt_read.py comments <id>             … その動画のコメント（新しい順50件）
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ondoku_upload import service  # noqa: E402


def videos(yt, ids: list[str]) -> list[dict]:
    out = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,status,statistics", id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            out.append({
                "id": v["id"], "title": v["snippet"]["title"], "publishedAt": v["snippet"]["publishedAt"],
                "privacy": v["status"]["privacyStatus"], "publishAt": v["status"].get("publishAt"),
                "views": v["statistics"].get("viewCount"), "description": v["snippet"].get("description", ""),
            })
    return out


def find(yt, word: str) -> list[dict]:
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    hits, token = [], None
    while True:
        r = yt.playlistItems().list(part="snippet", playlistId=pl, maxResults=50, pageToken=token).execute()
        for it in r.get("items", []):
            if word in it["snippet"]["title"]:
                hits.append(it["snippet"]["resourceId"]["videoId"])
        token = r.get("nextPageToken")
        if not token:
            break
    rows = videos(yt, list(dict.fromkeys(hits)))
    for x in rows:
        x.pop("description")
    return rows


def comments(yt, vid: str) -> list[dict]:
    r = yt.commentThreads().list(part="snippet", videoId=vid, maxResults=50, order="time", textFormat="plainText").execute()
    return [{"author": c["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"],
             "text": c["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
             "at": c["snippet"]["topLevelComment"]["snippet"]["publishedAt"]} for c in r.get("items", [])]


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("videos", "find", "comments"):
        print(__doc__)
        return 2
    yt = service()
    cmd, args = sys.argv[1], sys.argv[2:]
    res = videos(yt, args) if cmd == "videos" else find(yt, " ".join(args)) if cmd == "find" else comments(yt, args[0])
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
