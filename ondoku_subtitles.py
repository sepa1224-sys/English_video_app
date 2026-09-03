"""YouTube 用の字幕ファイルを書き出す。

画面には英語だけを出し、日本語訳は字幕トラックに逃がす。
視聴者が必要なときだけ開けるようにするため。
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

OUTPUT_DIR = Path("output") / "ondoku"


def _ts(sec: float) -> str:
    if sec < 0:
        sec = 0.0
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


def build(material_id: str, lang: str, offset: float = 0.0) -> Path:
    timing = json.loads(
        (OUTPUT_DIR / f"{material_id}_timing.json").read_text(encoding="utf-8"))
    key = {"ja": "ja", "en": "en"}[lang]
    lines = []
    for i, s in enumerate(timing["sentences"], 1):
        text = str(s.get(key) or "").strip()
        if not text:
            continue
        st = s["start"] + offset
        en = st + s["duration"]
        lines += [str(i), f"{_ts(st)} --> {_ts(en)}", text, ""]
    out = OUTPUT_DIR / f"{material_id}.{lang}.srt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="字幕ファイル(SRT)を書き出す")
    ap.add_argument("--id", required=True)
    ap.add_argument("--lang", default="ja", choices=["ja", "en"])
    ap.add_argument("--offset", type=float, default=0.0,
                    help="本文の開始位置(秒)。タイトルカードの尺だけずらす")
    a = ap.parse_args()
    p = build(a.id, a.lang, a.offset)
    n = p.read_text(encoding="utf-8").count("-->")
    print(f"✅ {p} （{n}件 / オフセット {a.offset:.1f}秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
