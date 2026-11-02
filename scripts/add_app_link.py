"""公開中の動画の概要欄の上のほうに、iPhone アプリ「気合イングリッシュ」（App Store）の案内を1行入れる。

  python3 scripts/add_app_link.py              … 何が変わるかだけ見る（YouTube は触らない）
  python3 scripts/add_app_link.py --apply 60   … 再生の多い順に60本まで書き換える

1本の書き換えに YouTube の1日の枠（10,000）を50使う。毎日のショートの投稿も枠を使うので、1日60本くらいずつ。
もう go/app が入っている動画は飛ばすので、何度動かしてもよい（続きからになる）。
2026-11-02 坂本さん「アプリが出た。全部やって」（App Store だけ。Android はまだ）。
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


LINE = "📱 iPhone アプリ「気合イングリッシュ」で毎日の単語テスト（App Store で配信中）→ https://kiaienglish.com/go/app?src=yt_app\n"


def place(cur: str) -> str:
    """無料の案内・Amazon の案内のすぐ下（無ければいちばん上）に入れる"""
    lines = cur.split("\n")
    at = 0
    for i, l in enumerate(lines[:8]):
        if "go/tango" in l or "go/amazon" in l or "go/kindle" in l:
            at = i + 1
    return "\n".join(lines[:at] + [LINE.rstrip("\n")] + lines[at:])


def main(apply: bool, limit: int):
    os.chdir(ROOT)
    from ondoku_upload import service
    yt = service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, req = [], yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
    while req:
        r = req.execute(); ids += [x["contentDetails"]["videoId"] for x in r["items"]]
        req = yt.playlistItems().list_next(req, r)
    vids = []
    for i in range(0, len(ids), 50):
        vids += yt.videos().list(part="snippet,status,statistics", id=",".join(ids[i:i + 50])).execute()["items"]
    vids = {v["id"]: v for v in vids}.values()
    todo = [v for v in vids if v["status"]["privacyStatus"] == "public" and "go/app" not in v["snippet"].get("description", "")]
    todo.sort(key=lambda v: -int(v["statistics"].get("viewCount", 0)))
    done = 0
    for v in todo[:limit]:
        sn = v["snippet"]
        desc = place(sn.get("description", ""))
        if len(desc) > 5000:
            print("長すぎて飛ばす", v["id"], sn["title"][:50]); continue
        print(("書き換え" if apply else "予定"), v["id"], v["statistics"].get("viewCount"), sn["title"][:50])
        if apply:
            body = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage") if k in sn}
            body["description"] = desc
            yt.videos().update(part="snippet", body={"id": v["id"], "snippet": body}).execute()
        done += 1
    print(f"公開 {len(todo)}本が未対応：{'書き換えた' if apply else '書き換える予定'} {done}本・残り {len(todo) - done}本")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    main("--apply" in sys.argv, int(args[0]) if args else 60)
