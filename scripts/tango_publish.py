"""上げ済みの単語帳の動画を公開にする（坂本さんの OK が出た稽古だけ）。再生リストも公開にする。

  python3 scripts/tango_publish.py keiko1 keiko1_listen
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te

names = sys.argv[1:]
done = json.loads(te.UPLOADED.read_text(encoding="utf-8"))
os.chdir(te.config_root())
from ondoku_upload import service
yt = service()
for n in names:
    if n not in done:
        print(f"{n} はまだ上がっていない"); continue
    vid = done[n]["id"]
    yt.videos().update(part="status", body={"id": vid, "status": {
        "privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
        "embeddable": True, "publicStatsViewable": True, "license": "youtube"}}).execute()
    done[n]["privacy"] = "public"
    print(f"{n} を公開：https://www.youtube.com/watch?v={vid}")
te.UPLOADED.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
# 再生リストも公開に
for title in (te.PLAYLIST, te.LISTEN_PLAYLIST):
    req = yt.playlists().list(part="snippet,status", mine=True, maxResults=50)
    while req:
        r = req.execute()
        for x in r["items"]:
            if x["snippet"]["title"] == title and x["status"]["privacyStatus"] != "public":
                yt.playlists().update(part="snippet,status", body={"id": x["id"], "snippet": {"title": title},
                                      "status": {"privacyStatus": "public"}}).execute()
                print(f"再生リスト「{title}」を公開")
        req = yt.playlists().list_next(req, r)
