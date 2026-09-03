"""教材のメタ情報から、入れるべき再生リストを決める。

運用ルール:
  - シリーズ共通の「1日5分 英語で聞く教養」には全部入れる
  - 難易度で 初級 / 中級 / 上級 に振り分ける
  - 単語帳ベースで作った教材だけ、その単語帳の再生リストにも入れる
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

from ondoku_profiles import materials_dir

SERIES = "1日5分 英語で聞く教養"

# CEFR表記 → 難易度。上から順に見て最初に当たったものを使う。
LEVEL_BUCKETS = [
    (("a1", "a1-a2", "a2"), "初級"),
    (("a2-b1", "b1-a2"), "中級"),
    (("b1", "b1-b2", "b2"), "上級"),
]

# 単語帳ベースの教材だけ入れる再生リスト。meta の vocab_base と突き合わせる。
VOCAB_PLAYLISTS = {
    "ターゲット1900": "ターゲット1900で作る英語教材",
    "ターゲット1400": "ターゲット1400で作る英語教材",
    "鉄壁": "鉄壁で作る英語教材",
}


def level_bucket(level: str | None) -> str | None:
    key = (level or "").strip().lower().replace(" ", "")
    for keys, name in LEVEL_BUCKETS:
        if key in keys:
            return name
    return None


def playlists_for(meta: dict) -> list[str]:
    names = [SERIES]
    b = level_bucket(meta.get("level"))
    if b:
        names.append(f"英語で聞く教養（{b}）")
    else:
        print(f"⚠ レベル '{meta.get('level')}' は 初級/中級/上級 に対応しません",
              file=sys.stderr)
    vb = meta.get("vocab_base")
    if vb:
        if vb in VOCAB_PLAYLISTS:
            names.append(VOCAB_PLAYLISTS[vb])
        else:
            print(f"⚠ 単語帳 '{vb}' に対応する再生リストが未定義です", file=sys.stderr)
    return names


def load_meta(material_id: str) -> dict:
    """音読教材のJSONと絵コンテの両方からメタを拾う。"""
    meta = {}
    for p in (materials_dir() / f"{material_id}.json",
              materials_dir() / f"{material_id.rstrip('L')}.json"):
        if p.exists():
            m = json.loads(p.read_text(encoding="utf-8"))
            meta = {**m, **(m.get("meta") or {}), **meta}
            break
    for p in Path("output/ondoku").glob(f"{material_id}_storyboard_*.json"):
        sb = json.loads(p.read_text(encoding="utf-8"))
        meta = {**(sb.get("meta") or {}), **meta}
        break
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="教材から再生リスト名を決める")
    ap.add_argument("--id", required=True)
    ap.add_argument("--level", help="メタを上書きする場合")
    ap.add_argument("--vocab-base", help="単語帳ベースならその名前（例: ターゲット1900）")
    a = ap.parse_args()

    meta = load_meta(a.id)
    if a.level:
        meta["level"] = a.level
    if a.vocab_base:
        meta["vocab_base"] = a.vocab_base
    if not meta:
        print(f"⚠ {a.id} のメタが見つかりません", file=sys.stderr)
    print(f"レベル: {meta.get('level')} / 単語帳: {meta.get('vocab_base') or 'なし'}",
          file=sys.stderr)
    print(",".join(playlists_for(meta)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
