"""大学別「〇〇によく出る英単語100」：稽古の動画と同じ作りで、大学のまとまりごとの100語を1本にする。

  python3 scripts/tango_group.py GMARCH --kind exercise           … 声→動画→サムネ→説明文 を output/tango/group_GMARCH.* に作る
  python3 scripts/tango_group.py 早慶 --kind listen                … 聞き流し（output/tango/group_早慶_listen.*）
  python3 scripts/tango_group.py GMARCH --kind exercise --words 4  … 試しに最初の4語だけ（見た目の確認用）
  python3 scripts/tango_group.py GMARCH --kind exercise --upload   … 作った動画を非公開で上げる（上げ済みなら何もしない）

単語は ~/kiai-tango/data/group_words.json（100語・並び順そのまま）。どれも『気合の英単語 必修』の語。
tango_exercise.py は稽古の書き出し（launchd の一括処理）が使っているので書き換えず、ここから関数を借りる。
説明文に、出どころのデータ・大学ごとの数字・割合・他社の本の名前は書かない。
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import tango_exercise as te
import tango_compile as tc  # 上げた記録の錠（record_upload）と、サムネ・再生リストの後処理（finish_upload）

GROUPS = te.TANGO / "data" / "group_words.json"
# 声に出す読み（字幕はそのまま）
READING = {"GMARCH": "ジーマーチ", "早慶": "そうけい"}
PLAYLIST = "大学別 よく出る英単語100（気合の英単語 必修）"
TAGS_EXTRA = ["大学別", "頻出英単語"]


def howto(g: str) -> list[dict]:
    r = READING.get(g, g)
    return [te.line_audio(w, t) for w, t in te.HOWTO[:2]] + [
        te.line_audio("master", f"{g}によく出る英単語、100語。はじめッ！", f"{r}によくでるえいたんご、ひゃくご。はじめッ！")]


def outro_book() -> list[dict]:
    return [te.line_audio("master", "この100語は、ぜんぶ本の必修に入っておる。続きは本で！概要欄からじゃ！",
                          "このひゃくごは、ぜんぶ、ほんのひっしゅうに、はいっておる。つづきは、ほんで！がいようらんからじゃ！")]


def build_props(g: str, limit: int | None, kind: str) -> dict:
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    if g not in groups:
        raise SystemExit(f"{g} は group_words.json にありません（{', '.join(groups)}）")
    by_no = {e["no"]: e for e in json.loads(te.ENTRIES.read_text(encoding="utf-8"))}
    entries = []
    for w in groups[g]["words"]:
        e = by_no.get(w["no"])
        if not e or e["headword"] != w["headword"]:
            raise SystemExit(f"必修の No.{w['no']} が {w['headword']} ではありません")
        entries.append(e)
    if limit:
        entries = entries[:limit]
    te.common_assets()
    # 新しく作る語だけ、稽古と同じく声の高さを確かめる（既に稽古で使っている声は作り直さない）
    checks = json.loads(te.CHECKS.read_text(encoding="utf-8")) if te.CHECKS.exists() else {}
    new = [e["headword"] for e in entries if e["headword"] not in checks]
    for e in entries:
        te.word_audio(e["headword"])
    if new:
        meds = {e["headword"]: te.median_f0(te.VOICE_DIR / f"{te.slug(e['headword'])}.mp3") for e in entries}
        vals = sorted(m for m in meds.values() if m)
        center = vals[len(vals) // 2]
        for h in new:
            m = meds.get(h)
            if m and abs(m / center - 1) > 0.2:
                print(f"    ↻ {h}：声の高さが {m:.0f}Hz（ほかは {center:.0f}Hz 前後）なので作り直し")
                checks = json.loads(te.CHECKS.read_text(encoding="utf-8"))
                checks.pop(h, None)
                te.CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
                # 消してから作る（word_audio は残っているファイルを1回目にそのまま確かめるので、消さないと作り直されない）
                (te.VOICE_DIR / f"{te.slug(h)}.mp3").unlink(missing_ok=True)
                te.word_audio(h)
                m2 = te.median_f0(te.VOICE_DIR / f"{te.slug(h)}.mp3")
                if m2 and abs(m2 / center - 1) > 0.2:
                    print(f"    ⚠ 要確認：{h} は作り直しても声の高さが {m2:.0f}Hz")
                checks = json.loads(te.CHECKS.read_text(encoding="utf-8"))
                checks[h]["pitch_redo"] = True
                te.CHECKS.write_text(json.dumps(checks, ensure_ascii=False, indent=1), encoding="utf-8")
    words = []
    for e in entries:
        v, d = te.word_audio(e["headword"])
        words.append({"no": e["no"], "headword": e["headword"], "pos": e["pos"], "meanings": te.meanings(e),
                      "hint": te.hint(e["headword"]), "img": te.art(e["headword"]), "voice": v, "voiceDur": d})
        print(f"  {e['no']:04d} {e['headword']:<16} {d:4.2f}s  {' / '.join(te.meanings(e))}")
    nos = [w["no"] for w in words]
    p = {
        "keiko": 0,
        "range": [min(nos), max(nos)],
        "label": f"{g}頻出100",
        "outroTitle": f"{len(words)}語 完了！",
        "bookOf": "に",
        "bookBig": "ぜんぶ収録",
        "series": te.SERIES,
        "book": {"label": te.book()["label"]},
        "intro": [te.line_audio(*x) for x in te.INTRO],
        "howto": howto(g),
        "outro": [te.line_audio(w, t) for w, t in te.OUTRO],
        "outroBook": outro_book(),
        "words": words,
        "thumbs": [w["img"] for w in words[:4]],
    }
    if kind == "listen":
        senses = {e["headword"]: e.get("senses") or [e["meanings"]] for e in entries}
        for w in p["words"]:
            w["ja"] = [te.ja_audio("、".join(s)) for s in senses[w["headword"]]]
        r = READING.get(g, g)
        p.update(series=te.LISTEN_SERIES, thumbTop="聞き流し", howto=[],
                 outro=[te.line_audio("master", f"{g}によく出る英単語、聞き流し完了じゃ！",
                                      f"{r}によくでるえいたんご、ききながし、かんりょうじゃ！")])
        p["plan"] = te.listen_plan(p)
    return p


def title(g: str, kind: str) -> str:
    return f"{g}によく出る英単語100｜" + ("聞き流し" if kind == "listen" else "イメージで覚える") + "【気合の英単語 必修】"


def description(g: str, p: dict) -> str:
    listen = "plan" in p
    bk = te.book()
    if listen:
        starts, outro = [w["start"] for w in p["plan"]["words"]], p["plan"]["outro"]
        toc = [f"{te.ts(0)} はじめに"]
    else:
        tl = te.timeline(p)
        starts, outro = tl["starts"], tl["outro"]
        toc = [f"{te.ts(tl['intro'])} はじめに", f"{te.ts(tl['howto'])} やり方"]
    toc += [f"{te.ts(s)} {i}. {w['headword']}（No.{w['no']}）" for i, (w, s) in enumerate(zip(p["words"], starts), 1)]
    toc.append(f"{te.ts(outro)} おわり")
    if bk.get("kindle_url") or bk.get("paperback_url"):
        buy = "\n".join(x for x in [
            f"Kindle版：{bk['kindle_url']}" if bk.get("kindle_url") else "",
            f"紙の本：{bk['paperback_url']}" if bk.get("paperback_url") else ""] if x)
    else:
        buy = "Kindle版・紙の本：近日発売（発売したら、ここに購入リンクを載せます）"
    n = len(p["words"])
    if listen:
        how = """■ 使い方
1. 通学中や寝る前に、流して聞く
2. 慣れてきたら、日本語が流れる前に意味を言ってみる
3. 絵を見て英語で言う練習は「イメージで覚える英単語」で
"""
        kind_line = "英単語の発音のあとに、日本語の意味を読み上げる聞き流しです。"
    else:
        how = """■ やり方
1. 絵と頭文字のヒントを見て、3秒以内に英単語を声に出す
2. 答えが出たら、発音を聞いて、あとについて2回まねする
3. 言えなかった単語は、もう一度この動画で練習する
"""
        kind_line = "イラストだけを見て、英語で答えるエクササイズです。"
    return f"""▼ アプリで毎日テスト（気合イングリッシュ）
まちがえた単語は苦手リストに入り、日を空けてまた出てきます。本と同じ番号でテストできます。
{te.APP_URL}

{g}の入試の英文に特によく出る英単語を、過去の入試問題の分析から{n}語選びました。{kind_line}
📕 {n}語はすべて、単語帳『気合の英単語 必修』に入っています（下の一覧の No. は本の番号です）。
{buy}

{how}
■ 単語帳『気合の英単語 必修』
大学入試によく出る1000語を、100語ずつ10の稽古に分けた単語帳です。この動画のイラストは、本と同じものです。
{buy}

■ 単語の一覧（時間を押すと、その単語へ）
""" + "\n".join(toc) + f"""

■ この動画について
単語・訳・イラストは、すべて気合イングリッシュのオリジナルです。イラストは AI（Google Gemini）で作りました。発音とキャラクターの声は AI 音声（ElevenLabs）です。

{' '.join('#' + t for t in [g, *te.TAGS[:4]])}
"""


def names(g: str, kind: str, limit: int | None = None) -> str:
    return f"group_{g}" + ("_listen" if kind == "listen" else "") + (f"_try{limit}" if limit else "")


def make(g: str, kind: str, limit: int | None, force: bool) -> int:
    from book_guard import check
    listen = kind == "listen"
    name = names(g, kind, limit)
    if (te.OUT / f"{name}.mp4").exists() and not force:
        print(f"  {name}.mp4 はもうあります（作り直すなら --force）")
        return 0
    p = build_props(g, limit, kind)
    tags = [t.replace("英単語エクササイズ", "英単語 聞き流し") for t in te.TAGS] if listen else list(te.TAGS)
    tags = [g, *TAGS_EXTRA, *tags]
    meta = {"title": title(g, kind), "description": description(g, p), "tags": tags, "playlist": PLAYLIST}
    check(meta["title"], meta["description"], meta["tags"])
    if len(meta["description"]) > 4900:
        raise SystemExit(f"説明文が長すぎます（{len(meta['description'])}字）")
    te.OUT.mkdir(parents=True, exist_ok=True)
    props = te.OUT / f"{name}.props.json"
    props.write_text(json.dumps({"data": p}, ensure_ascii=False), encoding="utf-8")
    (te.OUT / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (te.OUT / f"{name}_description.txt").write_text(meta["description"], encoding="utf-8")
    te.render("TangoThumb", te.OUT / f"{name}.png", props, still=True)
    Image.open(te.OUT / f"{name}.png").convert("RGB").save(te.OUT / f"{name}.jpg", quality=90)
    (te.OUT / f"{name}.png").unlink()
    total, events = te.listen_events(p) if listen else te.exercise_events(p)
    out = te.produce(p, name, "TangoListen" if listen else "TangoExercise", total, events, props)
    print(f"✅ {out} （{te.ts(total)}）\n   {meta['title']}")
    return 0


def upload(g: str, kind: str) -> int:
    """非公開で上げる。上げ済みなら何もしない。1日の上限なら 3"""
    from book_guard import check
    from googleapiclient.errors import HttpError
    name = names(g, kind)
    done = tc.uploaded()
    if name in done:
        print(f"  {name} は上げ済み：https://www.youtube.com/watch?v={done[name]['id']}")
        return 0
    base = te.OUT / name
    meta = json.loads(base.with_suffix(".meta.json").read_text(encoding="utf-8"))
    meta["thumb"] = str(base.with_suffix(".jpg"))
    check(meta["title"], meta["description"], meta["tags"])
    privacy = "private"
    cwd = os.getcwd()
    os.chdir(te.config_root())  # ondoku_upload は config/ を今いる場所から探す
    try:
        from ondoku_upload import service, upload as yt_upload
        yt = service()
        try:
            vid = yt_upload(yt, base.with_suffix(".mp4"), meta["title"], meta["description"], meta["tags"], privacy)
        except HttpError as e:
            if e.resp.status == 403 and ("quota" in str(e).lower() or "uploadlimit" in str(e).lower()):
                print(f"⏸ YouTube の1日の上限に達しました。明日もう一度上げてください：{str(e)[:200]}")
                return 3
            raise
    finally:
        os.chdir(cwd)
    tc.record_upload(name, {"id": vid, "privacy": privacy, "title": meta["title"]})
    try:
        tc.finish_upload(yt, vid, privacy, meta)
    except Exception as e:
        print(f"⚠ https://www.youtube.com/watch?v={vid} は非公開で上がったが、そのあとで失敗：{type(e).__name__}: {e}")
        return 4
    print(f"✅ https://www.youtube.com/watch?v={vid}（{privacy}）／再生リスト「{meta['playlist']}」に追加")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("group", help="GMARCH / 早慶 など（group_words.json の見出し）")
    ap.add_argument("--kind", default="exercise", choices=["exercise", "listen"])
    ap.add_argument("--words", type=int, help="最初のN語だけで作る（試作用・上げない）")
    ap.add_argument("--upload", action="store_true", help="作って（作ってあれば飛ばして）非公開で上げる")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.upload and a.words:
        ap.error("--words の試作は上げません")
    rc = make(a.group, a.kind, a.words, a.force)  # 作ってあれば飛ばす
    return upload(a.group, a.kind) if a.upload and rc == 0 else rc


if __name__ == "__main__":
    sys.exit(main())
