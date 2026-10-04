"""気合のアプリで承認された解説ショートを、YouTube に予約投稿する。

  python3 sns_youtube_sync.py

承認済みでまだ YouTube に上げていないものを GET /api/sns-video で取り、
動画をダウンロード → publishAt＝予約時刻（毎日12時JST）で上げ → 結果を PATCH で書き戻す。
予約時刻を過ぎていたら（承認が遅れた・Macが寝ていた）すぐ公開で上げる。
1時間おきに回す想定（launchd）。合言葉は .env の SNS_UPLOAD_SECRET。
"""
from __future__ import annotations
import os, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from ondoku_upload import service, upload

APP = os.getenv("KIAI_APP_URL", "https://kiai-coaching-app.vercel.app")


def main() -> int:
    load_dotenv()
    secret = os.getenv("SNS_UPLOAD_SECRET")
    if not secret:
        raise SystemExit(".env に SNS_UPLOAD_SECRET がありません")
    h = {"Authorization": f"Bearer {secret}"}
    r = requests.get(f"{APP}/api/sns-video", params={"for": "youtube"}, headers=h, timeout=30)
    r.raise_for_status()
    videos = r.json()["videos"]
    if not videos:
        print("YouTube に上げる承認済みの動画はありません")
        return 0
    yt = service()
    for v in videos:
        print(f"⬆ #{v['id']} {v['title']}（予約 {v['scheduledFor']}）")
        try:
            at = datetime.fromisoformat(v["scheduledFor"].replace("Z", "+00:00"))
            future = (at - datetime.now(timezone.utc)).total_seconds() > 15 * 60
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "v.mp4"
                with requests.get(v["videoUrl"], stream=True, timeout=120) as dl:
                    dl.raise_for_status()
                    with open(path, "wb") as f:
                        for chunk in dl.iter_content(1 << 20):
                            f.write(chunk)
                vid = upload(yt, path, v["title"], v["captions"].get("youtube", v["title"]), v.get("tags", []),
                             privacy="public", publish_at=at.isoformat() if future else None)
            print(f"  ✅ https://youtube.com/shorts/{vid}" + ("" if future else "（予約時刻を過ぎていたので即公開）"))
            body = {"id": v["id"], "ytVideoId": vid}
        except Exception as e:  # 1本の失敗で他を止めない。管理画面に出して、消したら再試行
            print(f"  ❌ {e}")
            body = {"id": v["id"], "error": str(e)[:400]}
        requests.patch(f"{APP}/api/sns-video", json=body, headers=h, timeout=30).raise_for_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
