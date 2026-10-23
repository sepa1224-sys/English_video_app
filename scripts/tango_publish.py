"""上げ済みの単語帳の動画を公開にする（坂本さんの OK が出た稽古だけ）。再生リストも公開にする。

  python3 scripts/tango_publish.py keiko1 keiko1_listen
  python3 scripts/tango_publish.py --auto   … 稽古2〜30 を、上がったものから番号順に公開（前の稽古が公開済みのときだけ）
                                            launchd com.kiai.tango.autopublish が30分ごとに動かす（2026-10-21 坂本さん「上がったら順番に公開していい」）
"""
import json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te

names = sys.argv[1:]
done = json.loads(te.UPLOADED.read_text(encoding="utf-8"))
if names == ["--auto"]:
    names = []
    for k in range(2, 31):
        pair = [f"keiko{k}", f"keiko{k}_listen"]
        if not all(n in done for n in pair):
            break  # 番号順：この稽古の2本がそろうまで先は出さない
        names += [n for n in pair if done[n].get("privacy") != "public"]
os.chdir(te.config_root())
import tango_comment as tc
if not names:
    # 公開するものが無くても、公開済みでコメント未投稿の動画があれば付ける（本のリンクのコメント）
    posted = json.loads(tc.COMMENTS.read_text(encoding="utf-8")) if tc.COMMENTS.exists() else {}
    todo = tc.pending(done, posted)
    if todo:
        from ondoku_upload import service
        tc.post(service(), done, todo, posted)
    sys.exit(0)
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
# 公開した動画に、本のリンクのコメントを付ける（付けたものは data/tango_comments.json に残り、二度は付けない。ピン留めは YouTube Studio で手作業）
posted = json.loads(tc.COMMENTS.read_text(encoding="utf-8")) if tc.COMMENTS.exists() else {}
todo = tc.pending(done, posted, [n for n in names if n in done])
if todo:
    tc.post(yt, done, todo, posted)
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
