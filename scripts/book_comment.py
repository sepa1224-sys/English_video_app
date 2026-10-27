"""全部の公開動画に、単語帳『気合の英単語 必修』の案内コメントを書く（固定は YouTube の仕組み上、坂本さんが押す）。

  python3 scripts/book_comment.py            … 書く予定だけ見る
  python3 scripts/book_comment.py --apply --limit 60

もう自分（チャンネル）の Amazon 案内のコメントがある動画は飛ばす。コメントを切っている動画も飛ばす。
1件 50 ユニット使うので、動画を上げる分（1本 1600）を残すため1日60件までにする。
2026-10-27 坂本さん「固定コメント書いていいよ 全部やろう」。
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te

TEXT = ("🎁 稽古1（100語）を無料で試せます（登録なし）→ https://kiaienglish.com/go/tango?src=yt_comment\n"
        "📕 この動画の単語は、単語帳『気合の英単語 必修』で覚えられます。\n"
        "大学入試によく出る1000語を、イラストつき・100語ずつの稽古で。動画と本が同じ番号です。\n"
        "▶ Amazon：https://kiaienglish.com/go/amazon?src=yt_comment\n"
        "▶ アプリで毎日テスト：https://kiaienglish.com/go/line?src=yt_comment")


def main(apply: bool, limit: int):
    os.chdir(te.config_root())
    from ondoku_upload import service
    yt = service()
    ch = yt.channels().list(part="id,contentDetails", mine=True).execute()["items"][0]
    me, uploads = ch["id"], ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, req = [], yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
    while req:
        r = req.execute(); ids += [x["contentDetails"]["videoId"] for x in r["items"]]
        req = yt.playlistItems().list_next(req, r)
    public = []
    for i in range(0, len(ids), 50):
        public += [v for v in yt.videos().list(part="snippet,status", id=",".join(ids[i:i + 50])).execute()["items"]
                   if v["status"]["privacyStatus"] == "public"]
    done = skip = 0
    for v in public:
        if done >= limit:
            break
        try:
            th = yt.commentThreads().list(part="snippet", videoId=v["id"], maxResults=100, order="time").execute()["items"]
        except Exception as e:  # コメントを切っている動画
            skip += 1; print("飛ばす（コメント不可）", v["id"], str(e)[:60]); continue
        if any(t["snippet"]["topLevelComment"]["snippet"].get("authorChannelId", {}).get("value") == me
               and "go/amazon" in t["snippet"]["topLevelComment"]["snippet"]["textOriginal"] for t in th):
            skip += 1; continue
        done += 1
        print(("書いた" if apply else "予定"), v["id"], v["snippet"]["title"][:50])
        if apply:
            yt.commentThreads().insert(part="snippet", body={"snippet": {"videoId": v["id"], "topLevelComment": {
                "snippet": {"textOriginal": TEXT}}}}).execute()
    print(f"公開 {len(public)}本：{'書いた' if apply else '書く予定'} {done}件・飛ばした {skip}件")


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**6
    main("--apply" in sys.argv, lim)
