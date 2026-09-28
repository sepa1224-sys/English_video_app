"""YouTube で公開されたショートを、Instagram（@kiai_english）のリールにも出す。

Instagram の API には予約公開が無い。そこで YouTube の予約時刻（毎日19:00 JST）の
直後にこのスクリプトを走らせ、「YouTube で公開済み・Instagram 未投稿」の分を出す。
何を出したかは YouTube と同じ台帳 data/shorts_ledger.json に書く（instagram_id）。

必要な設定（.env）:
  IG_USER_ID       Instagram のプロアカウントのユーザーID
  IG_ACCESS_TOKEN  長期トークン（instagram_business_basic と
                   instagram_business_content_publish の権限）
長期トークンは60日で切れる。このスクリプトが残り15日を切ったら自動で延長し、
config/instagram_token.json に保存する（以後はそちらを使う）。

  python3 instagram_reels.py --dry-run    # 何を出すか・キャプションだけ表示
  python3 instagram_reels.py              # 投稿する
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

JST = timezone(timedelta(hours=9))
LEDGER = Path("data/shorts_ledger.json")
SHORTS_DIR = Path("output/shorts")
TOKEN_FILE = Path("config/instagram_token.json")
API = f"https://graph.instagram.com/{os.getenv('IG_API_VERSION', 'v23.0')}"
MAX_POSTS = 3   # 取りこぼしが溜まっていても、一度に大量に出さない


def token() -> str:
    """保存済みのトークン（延長済み）を優先し、期限が近ければ延長する。"""
    saved = json.loads(TOKEN_FILE.read_text()) if TOKEN_FILE.exists() else {}
    tok = saved.get("access_token") or os.getenv("IG_ACCESS_TOKEN")
    if not tok:
        raise SystemExit("IG_ACCESS_TOKEN がありません（.env に設定してください）")
    exp = saved.get("expires_at")
    if exp is None or datetime.fromisoformat(exp) - datetime.now(JST) < timedelta(days=15):
        r = requests.get("https://graph.instagram.com/refresh_access_token",
                         params={"grant_type": "ig_refresh_token", "access_token": tok},
                         timeout=30)
        if r.ok:
            d = r.json()
            tok = d["access_token"]
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            TOKEN_FILE.write_text(json.dumps({
                "access_token": tok,
                "expires_at": (datetime.now(JST) + timedelta(seconds=d["expires_in"])).isoformat(),
            }))
            print("  - トークンを延長しました")
        else:
            print(f"  ⚠ トークンを延長できませんでした: {r.text[:200]}")
    return tok


def caption(meta: dict) -> str:
    """YouTube 用の概要欄から作る。Instagram のキャプションはリンクが押せないので
    URL は入れず、プロフィールと YouTube へ誘導する。"""
    title = meta["title"].replace(" #shorts", "")
    answers = meta["description"].split("【答え】", 1)[-1].split("\n\n", 1)[0].strip()
    book = title.split("】")[0].lstrip("【")
    return "\n".join([
        title, "何問言えたかコメントで教えてください👇", "",
        "【答え】", answers, "",
        "聞き流し動画は YouTube「気合イングリッシュ」で公開中",
        "大人の英会話コーチングはプロフィールのリンクから", "",
        f"#{book} #英単語 #大学受験 #英語学習 #英単語クイズ",
    ])


def post_reel(user_id: str, tok: str, video: Path, text: str) -> str:
    # 1) 入れ物を作る（resumable で、動画ファイルを直接送る）
    r = requests.post(f"{API}/{user_id}/media", timeout=60, data={
        "media_type": "REELS", "upload_type": "resumable", "caption": text,
        "share_to_feed": "true", "access_token": tok})
    r.raise_for_status()
    cid, uri = r.json()["id"], r.json()["uri"]
    # 2) 動画を送る
    data = video.read_bytes()
    r = requests.post(uri, data=data, timeout=600, headers={
        "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(data))})
    r.raise_for_status()
    # 3) Instagram 側の処理を待つ（数十秒〜数分）
    for _ in range(60):
        s = requests.get(f"{API}/{cid}", timeout=30,
                         params={"fields": "status_code,status", "access_token": tok}).json()
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram 側の処理に失敗: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram 側の処理が10分で終わりませんでした")
    # 4) 公開する
    r = requests.post(f"{API}/{user_id}/media_publish", timeout=60,
                      data={"creation_id": cid, "access_token": tok})
    r.raise_for_status()
    return r.json()["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description="YouTube で公開済みのショートを Instagram リールに出す")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_POSTS)
    a = ap.parse_args()
    load_dotenv()

    ledger = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else {}
    now = datetime.now(JST)
    todo = sorted(
        ((name, v) for name, v in ledger.items()
         if not v.get("instagram_id")
         # published_now は予約を待たずに手で公開したもの
         and (v.get("published_now") or datetime.fromisoformat(v["publish_at"]) <= now)),
        key=lambda kv: kv[1]["publish_at"])[:a.max]
    if not todo:
        print("✅ Instagram に出す分はありません（YouTube で公開済みのものは全部投稿済み）")
        return 0

    user_id = os.getenv("IG_USER_ID")
    tok = None if a.dry_run else token()
    if not a.dry_run and not user_id:
        raise SystemExit("IG_USER_ID がありません（.env に設定してください）")
    for name, v in todo:
        video = SHORTS_DIR / name
        meta = json.loads(video.with_suffix(".json").read_text(encoding="utf-8"))
        text = caption(meta)
        print(f"▶ {name}（YouTube {v['publish_at'][:16]} 公開）")
        if a.dry_run:
            print(text, "\n")
            continue
        mid = post_reel(user_id, tok, video, text)
        v["instagram_id"] = mid
        v["instagram_at"] = datetime.now(JST).isoformat(timespec="seconds")
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ Instagram に投稿しました（{mid}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
