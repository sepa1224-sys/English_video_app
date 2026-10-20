"""「3秒クイズ」の縦長ショート（1080×1920）。YouTube ショートとインスタのリールに同じ動画を出す。

  word   … 単語帳『気合の英単語 必修』の英単語を見せて発音 → 3・2・1 → 意味（Keita）と本の絵
  phrase … レッスンで実際に出た日本語を見せて読む → 3・2・1 → 英語の答え（ネイティブの声）とひとこと

  python3 tango_quiz.py word --words appear,consider,support,condition,lead --name w_tamei1 \\
      --title "2つ目の意味まで,言える？"
  python3 tango_quiz.py phrase --phrases data/quiz_phrases/sample.json --name p_sample

番号（No.）や稽古は出さない（単語帳の並びがまだ変わることがあり、ショートは並びと関係なく作れるように）。
声・絵・書き出しは tango_exercise.py のものを使い回す（作った声は edu/public/tango/ に貯まる）。
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

import tango_exercise
from tango_exercise import (
    ENTRIES, PUB, ROOT, WORD_MODEL, WORD_VOICE, EDU, art, common_assets, duration, ff, fr, ja_audio, line_audio, meanings,
    mix_audio, peak_normalize, render, tts, word_audio,
)

OUT = ROOT / "output" / "quiz"
COUNT = 3.0  # 秒読み
# 意味の読み上げは聞き流し（-10%）より速く、ふつうの速さで（ショートは30秒前後に収めたい）
tango_exercise.JA_RATE = "+0%"
GAP = 0.3  # 読み上げと読み上げの間


def phrase_audio(text: str) -> dict:
    """英文の答えを、単語の発音と同じアメリカ英語の声（Bella・v3）で読む。同じ文は作り置きを使う"""
    key = hashlib.sha256(f"{WORD_VOICE}|{WORD_MODEL}|{text}".encode()).hexdigest()[:12]  # ファイル名を決めるだけ
    p = PUB / "phrase" / f"{key}.mp3"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        tts(text, WORD_VOICE, p, 1.0, WORD_MODEL)
        peak_normalize(p)
    return {"audio": f"tango/phrase/{p.name}", "dur": duration(p)}


def entry(headword: str) -> dict:
    for e in json.loads(ENTRIES.read_text(encoding="utf-8")):
        if e["headword"] == headword:
            return e
    raise SystemExit(f"単語帳に無い語です: {headword}")


def build_word(words: list[str]) -> tuple[list[dict], list[dict], list[tuple[str, int, float]]]:
    """問題・時間割・音（コマ）。時間割は語の頭からのコマ"""
    items, plan, events, t = [], [], [], 0
    for h in words:
        e = entry(h)
        v, vd = word_audio(h)
        senses = e.get("senses") or [e["meanings"]]
        ja = [ja_audio("、".join(s)) for s in senses]
        q_at = fr(0.2)
        think = q_at + fr(vd + 0.25)
        reveal = think + fr(COUNT)
        at, a_at = reveal + fr(0.15), []
        for x in ja:
            a_at.append(at)
            at += fr(x["dur"] + GAP)
        end = at + fr(0.6)
        events.append((v, t + q_at, 1.0))
        events += [("tango/tick.mp3", t + think + fr(k), 0.45) for k in range(3)]
        events += [(x["audio"], t + a, 1.0) for x, a in zip(ja, a_at)]
        items.append({"q": h, "pos": e["pos"], "img": art(h), "a": meanings(e)})
        plan.append({"start": t, "len": end, "think": think, "reveal": reveal})
        t += end
    return items, plan, events


def build_phrase(rows: list[dict]) -> tuple[list[dict], list[dict], list[tuple[str, int, float]]]:
    items, plan, events, t = [], [], [], 0
    for r in rows:
        q = ja_audio(r["q"].replace("\n", ""))
        a = phrase_audio(r["a"])
        q_at = fr(0.2)
        think = q_at + fr(q["dur"] + 0.3)
        reveal = think + fr(COUNT)
        a_at = reveal + fr(0.15)
        end = a_at + fr(a["dur"] + 2.4)  # ひとことを読む間
        events += [(q["audio"], t + q_at, 1.0), (a["audio"], t + a_at, 1.0)]
        events += [("tango/tick.mp3", t + think + fr(k), 0.45) for k in range(3)]
        items.append({"q": r["q"], "a": [r["a"]], "note": r.get("note", "")})
        plan.append({"start": t, "len": end, "think": think, "reveal": reveal})
        t += end
    return items, plan, events


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["word", "phrase"])
    ap.add_argument("--words", help="英単語をカンマ区切りで（word）")
    ap.add_argument("--phrases", help="[{q, a, note}] の JSON（phrase）")
    ap.add_argument("--name", required=True)
    ap.add_argument("--title", help="問いかけ。改行はカンマ")
    a = ap.parse_args()

    common_assets()
    if a.mode == "word":
        items, plan, events = build_word([w.strip() for w in a.words.split(",") if w.strip()])
        outro_line = line_audio("master", "何問言えたかの？ コメントで教えるのじゃ！")
        d = {"mode": "word", "badge": "気合の英単語 必修", "title": (a.title or "3秒で,意味を言える？").split(","),
             "outroTitle": "何問言えた？", "outroSub": "全部の単語は『気合の英単語 必修』で", "cover": "tango/cover.jpg"}
    else:
        rows = json.loads(Path(a.phrases).read_text(encoding="utf-8"))
        items, plan, events = build_phrase(rows)
        outro_line = line_audio("master", "レッスンで本当に出た英語じゃ。保存して覚えるのじゃ！")
        d = {"mode": "phrase", "badge": "レッスンで実際に出た英語", "title": (a.title or "3秒で,英語にできる？").split(","),
             "outroTitle": "何問言えた？", "outroSub": "気合イングリッシュのレッスンから"}
    outro = sum(p["len"] for p in plan)
    events.append((outro_line["audio"], outro + fr(0.3), 1.0))
    total = outro + fr(outro_line["dur"] + 1.6)
    d.update(items=items, outro=[outro_line], plan={"items": plan, "outro": outro, "total": total})

    OUT.mkdir(parents=True, exist_ok=True)
    props = OUT / f"{a.name}.props.json"
    props.write_text(json.dumps({"data": d}, ensure_ascii=False), encoding="utf-8")
    tmp = ROOT / ".tmp" / "quiz"
    tmp.mkdir(parents=True, exist_ok=True)
    audio, video = tmp / f"{a.name}.m4a", tmp / f"{a.name}.video.mp4"
    mix_audio(total, events, audio)
    render("TangoQuiz", video, props)
    out = OUT / f"{a.name}.mp4"
    ff("-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", str(out))
    video.unlink()
    audio.unlink()
    print(f"✅ {out}（{total / 30:.1f}秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
