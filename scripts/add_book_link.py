"""チャンネルの全部の動画（公開・限定公開）の概要欄のいちばん上に、単語帳『気合の英単語 必修』の Amazon のリンクを入れる。

  python3 scripts/add_book_link.py          … 何が変わるかだけ見る（YouTube は触らない）
  python3 scripts/add_book_link.py --apply  … 書き換える

もう Amazon のリンク（go/amazon・amazon.co.jp）が入っている動画は飛ばす。公開の動画だけ（非公開・限定公開は触らない）。
2026-10-27 坂本さん「全てのYoutubeの動画の概要欄に単語帳の購入リンクを入れてほしい」。
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te

FREE = "🎁 稽古1（100語）を無料で試せます → https://kiaienglish.com/go/tango?src=yt_desc\n"
BLOCK = ("📕 単語帳『気合の英単語 必修』（大学入試 頻出1000語・イラストつき）は Amazon で発売中\n"
         "https://kiaienglish.com/go/amazon?src=yt_desc\n\n")
HAS = ("go/amazon", "amazon.co.jp")


def main(apply: bool):
    os.chdir(te.config_root())
    from ondoku_upload import service
    yt = service()
    ch = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, req = [], yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
    while req:
        r = req.execute(); ids += [x["contentDetails"]["videoId"] for x in r["items"]]
        req = yt.playlistItems().list_next(req, r)
    todo = skip = 0
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,status", id=",".join(ids[i:i + 50])).execute()["items"]:
            sn, priv = v["snippet"], v["status"]["privacyStatus"]
            cur = sn.get("description", "")
            if priv != "public" or "go/tango" in cur:
                skip += 1; continue
            # 無料の案内をいちばん上に。Amazon の案内がまだ無ければ一緒に足す（2026-10-27 坂本さん）
            desc = FREE + (cur if any(h in cur for h in HAS) else BLOCK + cur)
            if len(desc) > 5000:
                print("長すぎて飛ばす", v["id"], sn["title"]); skip += 1; continue
            todo += 1
            print(("書き換え" if apply else "予定"), v["id"], priv, sn["title"][:50])
            if apply:
                body = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage", "defaultAudioLanguage") if k in sn}
                body["description"] = desc
                yt.videos().update(part="snippet", body={"id": v["id"], "snippet": body}).execute()
    print(f"動画 {len(ids)}本：{'書き換えた' if apply else '書き換える予定'} {todo}本・飛ばした {skip}本")


if __name__ == "__main__":
    main("--apply" in sys.argv)
