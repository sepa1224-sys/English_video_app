"""3秒クイズのショートを、日本時間の決まった枠に予約投稿する。

何度実行しても同じ動画を二重に上げない。上げた記録は data/shorts_ledger.json。
実行するたびに「今から --days 日先まで」の空き枠を埋める。毎日1回走らせれば、
常に1週間ぶんの予約（朝7:00・夜19:00）が並んだ状態が保たれる。

  python3 shorts_schedule.py --dry-run          # 何をいつ上げるかだけ表示
  python3 shorts_schedule.py                    # 予約投稿する
  python3 shorts_schedule.py --auto-generate    # 在庫が足りなければ次の範囲を作ってから

時刻は常に日本時間。坂本さんのMac（ドイツ時間）でも、Windows生成機でも同じ枠になる。
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))   # 日本は夏時間が無いので固定でよい
SHORTS_DIR = Path("output/shorts")
LEDGER = Path("data/shorts_ledger.json")
# 単語帳ごとの聞き流し動画のURL。あれば概要欄に誘導リンクを差し込む
LINKS = Path("data/shorts_links.json")
# videos.insert は1本1,600ユニット、1日の上限は10,000。他の投稿の分も残す
MAX_UPLOADS = 5
# 番号順: short_t1900_0001-0005.mp4 ／ ランダム: short_t1900_r0001.mp4
NAME_RE = re.compile(r"short_(?P<book>[a-z0-9]+?)_(?:(?P<s>\d{4})-(?P<e>\d{4})|r(?P<r>\d{4}))\.mp4$")


def load_json(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save_ledger(ledger: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")


def stock(ledger: dict) -> list[dict]:
    """作成済みで、まだ上げていないショート。単語帳を交互に並べる。"""
    by_book: dict[str, list[dict]] = {}
    for mp4 in sorted(SHORTS_DIR.glob("short_*.mp4")):
        m = NAME_RE.search(mp4.name)
        if not m or mp4.name in ledger or not mp4.with_suffix(".json").exists():
            continue
        by_book.setdefault(m["book"], []).append(
            {"file": mp4, "book": m["book"], "start": int(m["s"] or m["r"]),
             "end": int(m["e"] or m["r"])})
    # 同じ単語帳が何日も続くと飽きられるので、単語帳を1本ずつ交互に出す
    queues = [sorted(v, key=lambda x: x["start"]) for _, v in sorted(by_book.items())]
    out = []
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    return out


def next_slots(ledger: dict, slots: list[str], days: int, now: datetime) -> list[datetime]:
    """今から days 日先までの、まだ予約の入っていない枠。
    予約済みの枠の間に空きがあれば、そこも埋める（1日1本→2本に増やしたとき、
    予約済みの日の朝の枠が空いたままにならないように）。"""
    taken = {datetime.fromisoformat(v["publish_at"]) for v in ledger.values()}
    # 直前すぎる枠は処理が間に合わないことがあるので、1時間後からにする
    earliest = now + timedelta(hours=1)
    out = []
    for d in range(days + 1):
        day = (now + timedelta(days=d)).date()
        for hm in slots:
            h, m = map(int, hm.split(":"))
            t = datetime(day.year, day.month, day.day, h, m, tzinfo=JST)
            if t >= earliest and t not in taken:
                out.append(t)
    return sorted(out)


def with_link(desc: str, book: str, links: dict) -> str:
    """聞き流し動画のURLが登録されていて、まだ概要欄に無ければ差し込む。"""
    url = links.get(book)
    if not url or url in desc:
        return desc
    lines = desc.rstrip().split("\n")
    tail = lines.pop() if lines and lines[-1].startswith("#") else ""
    body = "\n".join(lines).rstrip()
    return f"{body}\n\n▶ 聞き流しはこちら\n{url}\n\n{tail}".rstrip()


def playlist_id(yt, name: str, cache: dict) -> str:
    if name in cache:
        return cache[name]
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req:
        r = req.execute()
        for p in r["items"]:
            cache[p["snippet"]["title"]] = p["id"]
        req = yt.playlists().list_next(req, r)
    if name not in cache:
        cache[name] = yt.playlists().insert(
            part="snippet,status",
            body={"snippet": {"title": name}, "status": {"privacyStatus": "public"}},
        ).execute()["id"]
        print(f"  再生リストを作成: {name}")
        time.sleep(5)   # 作成直後は追加が404になることがある
    return cache[name]


def auto_generate(ledger: dict, need: int, books: list[str], count: int,
                  sequential: bool = False) -> None:
    """在庫が need 本に満たなければ、単語帳ごとに続きの範囲を作る。"""
    have = len(stock(ledger))
    if have >= need:
        return
    for book in books:
        n = -(-(need - have) // len(books))   # 切り上げ
        if not sequential:
            print(f"🎬 {book}: ランダム出題を{n}本作ります")
            subprocess.run([sys.executable, "shorts_quiz.py", "--book", book, "--random",
                            "--count", str(count), "--shorts", str(n)], check=True)
            continue
        ends = [int(m["e"]) for p in SHORTS_DIR.glob(f"short_{book}_*.mp4")
                if (m := NAME_RE.search(p.name)) and m["e"]]
        ends += [v["end"] for k, v in ledger.items()
                 if v["book"] == book and "_r" not in k]
        start = max(ends, default=0) + 1
        print(f"🎬 {book}: No.{start}〜 を{n}本作ります")
        subprocess.run([sys.executable, "shorts_quiz.py", "--book", book,
                        "--start", str(start), "--count", str(count),
                        "--shorts", str(n)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="ショートを日本時間の枠に予約投稿する")
    ap.add_argument("--slots", default="07:00,19:00",
                    help="毎日の公開時刻（日本時間）。カンマ区切りで複数可 例: 07:00,19:00")
    ap.add_argument("--days", type=int, default=7, help="何日先まで予約で埋めるか")
    ap.add_argument("--max-uploads", type=int, default=MAX_UPLOADS)
    ap.add_argument("--auto-generate", action="store_true",
                    help="在庫が足りなければ次の範囲のショートを作る")
    ap.add_argument("--books", default="t1900,teppeki",
                    help="--auto-generate で作る単語帳（交互に作る）")
    ap.add_argument("--count", type=int, default=5, help="1本あたりの語数")
    ap.add_argument("--sequential", action="store_true",
                    help="--auto-generate で番号順に作る（既定はランダム出題）")
    ap.add_argument("--dry-run", action="store_true", help="予定だけ表示して上げない")
    a = ap.parse_args()

    ledger = load_json(LEDGER, {})
    links = load_json(LINKS, {})
    now = datetime.now(JST)
    slots = next_slots(ledger, [s.strip() for s in a.slots.split(",")], a.days, now)
    slots = slots[:a.max_uploads]
    if not slots:
        print(f"✅ {a.days}日先まで予約で埋まっています。")
        return 0

    if a.auto_generate:
        auto_generate(ledger, len(slots), [b.strip() for b in a.books.split(",")], a.count,
                      a.sequential)
    plan = list(zip(stock(ledger), slots))
    if not plan:
        print("⚠ 上げられるショートがありません。shorts_quiz.py で作るか --auto-generate を付けてください。")
        return 1
    if len(plan) < len(slots):
        print(f"⚠ 空き枠 {len(slots)} に対して在庫が {len(plan)} 本しかありません。")

    for item, when in plan:
        print(f"  {when:%m/%d(%a) %H:%M} JST ← {item['file'].name}")
    if a.dry_run:
        print("（--dry-run なので上げていません）")
        return 0

    import shorts_quiz
    from ondoku_upload import service, upload
    from googleapiclient.errors import HttpError
    yt = service()
    pls: dict[str, str] = {}
    done = 0
    for item, when in plan:
        meta = json.loads(item["file"].with_suffix(".json").read_text(encoding="utf-8"))
        desc = with_link(meta["description"], item["book"], links)
        print(f"▶ {meta['title']}（{when:%m/%d %H:%M} 公開）")
        try:
            vid = upload(yt, item["file"], meta["title"], desc, meta["tags"],
                         "private", when.isoformat())
        except HttpError as e:
            # 上限超過（quotaExceeded）なら残りは明日。上げた分は記録済み
            print(f"  ❌ 投稿できませんでした: {e}")
            break
        ledger[item["file"].name] = {
            "video_id": vid, "book": item["book"], "start": item["start"],
            "end": item["end"], "publish_at": when.isoformat(),
            "uploaded_at": datetime.now(JST).isoformat(timespec="seconds"),
        }
        save_ledger(ledger)   # 1本ごとに記録。途中で落ちても二重投稿しない
        done += 1
        label = shorts_quiz.BOOK_LABEL.get(item["book"], item["book"])
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": playlist_id(yt, f"{label} 3秒クイズ", pls),
                "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        except HttpError as e:
            print(f"  ⚠ 再生リストに追加できず: {e}")
        print(f"  ✅ https://youtube.com/shorts/{vid}")
    print(f"\n{done}本を予約しました。")
    return 0 if done == len(plan) else 1


if __name__ == "__main__":
    sys.exit(main())
