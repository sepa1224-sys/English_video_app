"""上げ済みの単語帳の動画（稽古N）に、チャンネルから本のリンクのコメントを1つずつ付ける。

  python3 scripts/tango_comment.py             … まだ付けていない動画すべて（old_* は除く）
  python3 scripts/tango_comment.py keiko1 ...  … 指定した動画だけ
  python3 scripts/tango_comment.py --dry-run   … 付けずに、付ける文面と対象だけ出す

付けたコメントの ID は data/tango_comments.json に記録し、同じ動画には二度と付けない。
scripts/tango_publish.py --auto からも呼ばれる。公開された動画にだけ付ける（非公開の動画には付けられない）。
YouTube Data API ではコメントのピン留めができない。付けたあと YouTube Studio で手でピン留めする
（--dry-run や付けたあとの出力に、ピン留め待ちの動画の URL を出す）。
権限は youtube.force-ssl（ondoku_upload.SCOPES に入っている）。足りなければ再認証が必要。
"""
import json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te
from book_guard import check

COMMENTS = ROOT / "data" / "tango_comments.json"
APP_URL = te.APP_URL


def book_url() -> str:
    b = json.loads(te.BOOK.read_text(encoding="utf-8")) if te.BOOK.exists() else {}
    return b.get("paperback_url") or ""


def text_for(title: str) -> str | None:
    m = re.search(r"稽古(\d+)（No\.(\d+)〜(\d+)）", title)
    if not m or not book_url():
        return None
    k, a, b = m.groups()
    t = (f"📕 この動画の100語は単語帳『気合の英単語 必修』の稽古{k}（No.{a}〜{b}）です。"
         f"紙の本：{book_url()} ／ アプリで毎日テスト：{APP_URL}")
    check(t)
    return t


def pending(done: dict, posted: dict, only: list[str] | None = None) -> list[str]:
    names = only if only else [n for n in done if not n.startswith("old_")]
    # 非公開の動画にはコメントを付けられない（API が 403「insufficient permissions」を返す・2026-10-23 に確認）。公開してから付ける
    return [n for n in names if n in done and n not in posted and done[n].get("privacy") == "public"
            and text_for(done[n]["title"])]


def post(yt, done: dict, names: list[str], posted: dict) -> dict:
    """names の動画にコメントを付け、付けるたびに記録する。失敗した動画は飛ばして続ける"""
    out = {}
    for n in names:
        vid = done[n]["id"]
        try:
            r = yt.commentThreads().insert(part="snippet", body={"snippet": {
                "videoId": vid, "topLevelComment": {"snippet": {"textOriginal": text_for(done[n]["title"])}}}}).execute()
        except Exception as e:  # 403（権限・コメント無効）など。記録しないので次の回にやり直す
            print(f"{n}：コメントを付けられませんでした：{str(e)[:300]}")
            continue
        posted[n] = {"video": vid, "comment": r["id"], "privacy": done[n].get("privacy")}
        COMMENTS.write_text(json.dumps(posted, ensure_ascii=False, indent=1), encoding="utf-8")  # 1件ごとに保存（二重に付けない）
        out[n] = r["id"]
        print(f"{n}：コメントを付けた https://www.youtube.com/watch?v={vid}&lc={r['id']}")
    return out


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    only = [a for a in argv if not a.startswith("--")]
    done = json.loads(te.UPLOADED.read_text(encoding="utf-8"))
    posted = json.loads(COMMENTS.read_text(encoding="utf-8")) if COMMENTS.exists() else {}
    names = pending(done, posted, only)
    if dry:
        for n in names:
            print(f"{n}（{done[n].get('privacy')}）https://www.youtube.com/watch?v={done[n]['id']}\n  {text_for(done[n]['title'])}")
        print(f"対象 {len(names)} 本")
        return 0
    if names:
        os.chdir(te.config_root())
        from ondoku_upload import service
        post(service(), done, names, posted)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
