"""旺文社の取り下げを見張る（2026-10 著作権警告の件）。1時間おきに launchd から動かす。

data/oubunsha_37.txt の動画が YouTube に戻ってきたら（＝申し立てが取り下げられたら）、
旺文社との約束どおり、すぐ非公開にする。削除は坂本さんが Studio で行う。
結果は logs/strike-watch.log に追記し、戻ってきた動画があれば Mac の通知を出す。
"""
from __future__ import annotations
import subprocess
from datetime import datetime
from pathlib import Path

from ondoku_upload import service

ROOT = Path(__file__).resolve().parent
IDS = (ROOT / "data" / "oubunsha_37.txt").read_text().split()


def main():
    yt = service()
    back = []
    for k in range(0, len(IDS), 50):
        back += yt.videos().list(part="snippet,status", id=",".join(IDS[k:k + 50])).execute()["items"]
    made_private = []
    for v in back:
        if v["status"]["privacyStatus"] != "private":
            yt.videos().update(part="status", body={"id": v["id"], "status": {
                "privacyStatus": "private", "selfDeclaredMadeForKids": v["status"].get("selfDeclaredMadeForKids", False)}}).execute()
            made_private.append(v["id"])
    now = datetime.now().strftime("%m/%d %H:%M")
    line = f"{now} 戻った {len(back)}/{len(IDS)} 本・今回非公開にした {len(made_private)} 本 {' '.join(made_private)}"
    print(line)
    with open(ROOT / "logs" / "strike-watch.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if made_private:
        subprocess.run(["osascript", "-e", f'display notification "取り下げで{len(made_private)}本戻りました（非公開にしました）" with title "YouTube 著作権の警告"'])


if __name__ == "__main__":
    main()
