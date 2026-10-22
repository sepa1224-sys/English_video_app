"""稽古のまとめ版：output/tango/keiko{from..to}(_listen).mp4 を1本につないで、非公開で上げる。

  python3 scripts/tango_compile.py 1 2 --kind listen --no-upload   … つなぐだけ（output/tango/compile1-2_listen.mp4）
  python3 scripts/tango_compile.py 1 5 --kind exercise              … つないで非公開で上げる（上げ済みなら何もしない）

収益会議（kiai-coaching-app の media_actions）で決まった「まとめ版」を、scripts/factory_poll.py がこれで作る。
公開は坂本さんが決める（ここでは必ず非公開。tango_publish.py --auto も keiko{N} しか公開しない）。
いまは必修（稽古1〜10）だけ。突破の稽古はまだ動画が無い。
"""
from __future__ import annotations
import argparse, fcntl, json, os, subprocess, sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tango_exercise as te

FIRST, LAST = 1, 10  # 必修の稽古


class CompileError(RuntimeError):
    """作れない理由（そのまま会議の結果に書く）"""


class UploadedButIncomplete(RuntimeError):
    """動画は非公開で上がったが、そのあと（サムネ・再生リストなど）で失敗した。video_id は残す"""

    def __init__(self, video_id: str, msg: str):
        super().__init__(msg)
        self.video_id = video_id


LOCK = te.UPLOADED.with_name(".tango_uploaded.lock")


@contextmanager
def uploaded_lock():
    """data/tango_uploaded.json の読み書きの間だけ持つ錠（tango_publish.py なども同じファイルに書くので、書く直前に読み直す）"""
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def uploaded() -> dict:
    return json.loads(te.UPLOADED.read_text(encoding="utf-8")) if te.UPLOADED.exists() else {}


def record_upload(name: str, entry: dict) -> None:
    """上げた記録を1件足す。読み直し→足す→書く を錠の中で一気に（アップロードの数分のあいだに他が書いた分を消さない）"""
    with uploaded_lock():
        done = uploaded()
        done[name] = entry
        te.UPLOADED.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")


def name_of(a: int, b: int, kind: str) -> str:
    return f"compile{a}-{b}" + ("_listen" if kind == "listen" else "")


def parts_of(a: int, b: int, kind: str) -> list[Path]:
    if not (FIRST <= a < b <= LAST):
        raise CompileError(f"まとめ版は必修の稽古{FIRST}〜{LAST}の中で2本以上（稽古{a}〜{b}は作れない。突破の動画はまだ無い）")
    suffix = "_listen" if kind == "listen" else ""
    parts = [te.OUT / f"keiko{k}{suffix}.mp4" for k in range(a, b + 1)]
    missing = [p.stem for p in parts if not p.exists()]
    if missing:
        raise CompileError(f"稽古の動画が足りない：{'・'.join(missing)}")
    return parts


def title(a: int, b: int, kind: str) -> str:
    series = te.LISTEN_SERIES if kind == "listen" else te.SERIES
    return f"{series}｜稽古{a}〜{b}まとめ（No.{(a - 1) * 100 + 1}〜{b * 100}）【気合の英単語 必修】"


def description(a: int, b: int, kind: str, starts: list[float]) -> str:
    """各稽古の説明文と同じ宣伝＋目次（各稽古の始まりの時刻）"""
    n = (b - a + 1) * 100
    bk = te.book()
    if bk.get("kindle_url") or bk.get("paperback_url"):
        buy = "\n".join(x for x in [
            f"Kindle版：{bk['kindle_url']}" if bk.get("kindle_url") else "",
            f"紙の本：{bk['paperback_url']}" if bk.get("paperback_url") else ""] if x)
    else:
        buy = "Kindle版・紙の本：近日発売（発売したら、ここに購入リンクを載せます）"
    if kind == "listen":
        head = f"""単語帳『気合の英単語 必修』（大学入試 頻出1000語）の稽古{a}〜{b}（No.{(a - 1) * 100 + 1}〜{b * 100}）の聞き流しを、1本にまとめました。英単語の発音のあとに、日本語の意味を読み上げます。

■ 使い方
1. 通学中や寝る前に、流して聞く
2. 慣れてきたら、日本語が流れる前に意味を言ってみる
3. 絵を見て意味を思い出す練習は「{te.SERIES}」で
"""
    else:
        head = f"""単語帳『気合の英単語 必修』（大学入試 頻出1000語）の稽古{a}〜{b}（No.{(a - 1) * 100 + 1}〜{b * 100}）を1本にまとめた、イラストだけを見て英語で答えるエクササイズです。

■ やり方
1. 絵と頭文字のヒントを見て、3秒以内に英単語を声に出す
2. 答えが出たら、発音を聞いて、あとについて2回まねする
3. 言えなかった単語は、もう一度この動画で稽古する
"""
    promo = f"""▼ この{n}語を、アプリで毎日テスト（気合イングリッシュ）
まちがえた単語は苦手リストに入り、日を空けてまた出てきます。本と同じ番号・同じ稽古でテストできます。
{te.APP_URL}

"""
    chapters = [f"{te.ts(int(s * te.FPS))} 稽古{k}（No.{(k - 1) * 100 + 1}〜{k * 100}）" for k, s in zip(range(a, b + 1), starts)]
    tags = TAGS_LISTEN if kind == "listen" else te.TAGS
    return promo + head + f"""
■ 単語帳『気合の英単語 必修』
大学入試によく出る1000語を、100語ずつ10の稽古に分けた単語帳です。この動画のイラストは、本と同じものです。
{buy}

■ 目次
""" + "\n".join(chapters) + f"""

■ この動画について
単語・訳・イラストは、すべて気合イングリッシュのオリジナルです。イラストは AI（Google Gemini）で作りました。発音とキャラクターの声は AI 音声（ElevenLabs）です。

{' '.join('#' + t for t in tags[:5])}
"""


TAGS_LISTEN = [t.replace("英単語エクササイズ", "英単語 聞き流し") for t in te.TAGS]


def build(a: int, b: int, kind: str) -> tuple[Path, dict]:
    """つないだ mp4 と meta（題・説明文・タグ・再生リスト・サムネ）を返す。できていればつなぎ直さない"""
    from book_guard import check
    parts = parts_of(a, b, kind)
    starts, t = [], 0.0
    for p in parts:
        starts.append(t)
        t += te.duration(p)
    name = name_of(a, b, kind)
    meta = {"title": title(a, b, kind), "description": description(a, b, kind, starts),
            "tags": TAGS_LISTEN if kind == "listen" else te.TAGS,
            "playlist": te.LISTEN_PLAYLIST if kind == "listen" else te.PLAYLIST,
            "thumb": str(parts[0].with_suffix(".jpg")), "seconds": round(t, 2)}
    check(meta["title"], meta["description"], meta["tags"])
    out = te.OUT / f"{name}.mp4"
    if not out.exists():
        lst = ROOT / ".tmp" / "tango" / f"{name}.parts.txt"
        lst.parent.mkdir(parents=True, exist_ok=True)
        lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
        tmp = out.with_suffix(".tmp.mp4")
        try:
            te.ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(tmp))
            tmp.replace(out)
        finally:
            lst.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
    return out, meta


def upload(a: int, b: int, kind: str, video: Path, meta: dict) -> str:
    """非公開で上げる。上げ済みなら前の ID を返す。1日の上限なら te.QuotaExceeded"""
    from googleapiclient.errors import HttpError
    name = name_of(a, b, kind)
    done = uploaded()
    if name in done:
        return done[name]["id"]
    privacy = "private"
    cwd = os.getcwd()
    os.chdir(te.config_root())  # ondoku_upload は config/ を今いる場所から探す
    try:
        from ondoku_upload import service, upload as yt_upload
        yt = service()
        try:
            vid = yt_upload(yt, video, meta["title"], meta["description"], meta["tags"], privacy)
        except HttpError as e:
            if e.resp.status == 403 and "quota" in str(e).lower():
                raise te.QuotaExceeded(str(e)[:200])
            raise
    finally:
        os.chdir(cwd)
    try:
        record_upload(name, {"id": vid, "privacy": privacy, "title": meta["title"]})
        finish_upload(yt, vid, privacy, meta)
    except Exception as e:
        raise UploadedButIncomplete(vid, f"{type(e).__name__}: {e}") from e
    return vid


def finish_upload(yt, vid: str, privacy: str, meta: dict) -> None:
    """稽古の1本ずつと同じ status・サムネ・再生リスト（tango_exercise.upload と同じ）"""
    from googleapiclient.http import MediaFileUpload
    yt.videos().update(part="status", body={"id": vid, "status": {
        "privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
        "embeddable": True, "publicStatsViewable": True, "license": "youtube"}}).execute()
    yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(meta["thumb"])).execute()
    pid, req = None, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req and not pid:
        r = req.execute()
        pid = next((x["id"] for x in r["items"] if x["snippet"]["title"] == meta["playlist"]), None)
        req = yt.playlists().list_next(req, r)
    if not pid:
        pid = yt.playlists().insert(part="snippet,status", body={"snippet": {"title": meta["playlist"]},
                                    "status": {"privacyStatus": privacy}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={"snippet": {"playlistId": pid,
                              "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--kind", default="exercise", choices=["exercise", "listen"])
    ap.add_argument("--no-upload", action="store_true", help="つなぐだけ（上げない）")
    a = ap.parse_args()
    try:
        out, meta = build(a.start, a.end, a.kind)
    except CompileError as e:
        print(f"✖ {e}")
        return 2
    print(f"✅ {out}（{te.ts(int(meta['seconds'] * te.FPS))}）\n   {meta['title']}")
    if a.no_upload:
        return 0
    try:
        vid = upload(a.start, a.end, a.kind, out, meta)
    except te.QuotaExceeded as e:
        print(f"⏸ YouTube の1日の上限に達しました。明日もう一度上げてください：{e}")
        return 3
    except UploadedButIncomplete as e:
        print(f"⚠ https://www.youtube.com/watch?v={e.video_id} は非公開で上がったが、そのあとで失敗：{e}")
        return 4
    print(f"✅ https://www.youtube.com/watch?v={vid}（非公開）／再生リスト「{meta['playlist']}」に追加")
    return 0


if __name__ == "__main__":
    sys.exit(main())
