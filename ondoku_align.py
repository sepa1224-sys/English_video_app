"""
ondoku_align.py — 教材のSVOチャンクと絵コンテの文を対応づける

教材の `gap` は音読の区切り（カンマ等も含む）であって文境界ではないため、
チャンクを順に消費しながら絵コンテの文に一致させる。
"""

import json
from pathlib import Path

MATERIALS_DIR = Path.home() / "kiai-coaching-app" / "materials"


def _norm(s: str) -> str:
    return " ".join(s.split())


def load_chunks(material_id: str) -> list[dict]:
    """教材を、段落番号つきのチャンク列（gapを除く）に平坦化する"""
    mat = json.loads(
        (MATERIALS_DIR / f"{material_id}.json").read_text(encoding="utf-8")
    )
    out = []
    for pi, para in enumerate(mat["content"]["paragraphs"], 1):
        for u in para:
            if "w" in u:
                out.append({
                    "w": u["w"],
                    "l": u.get("l", "M"),
                    "kata": bool(u.get("kata")),
                    "para": pi,
                })
    return out


def align(material_id: str, sentences: list[dict]) -> list[dict]:
    """各文に対応するチャンク列を割り当てる。

    Returns: [{id, para, en, ja, chunks: [...]}, ...]
    失敗した場合は ValueError を投げる（黙って崩れた動画を作らないため）。
    """
    chunks = load_chunks(material_id)
    pos = 0
    result = []
    for s in sentences:
        target = _norm(s["en"])
        acc, taken = "", []
        while pos < len(chunks):
            c = chunks[pos]
            cand = _norm(f"{acc} {c['w']}") if acc else _norm(c["w"])
            if not target.startswith(cand):
                break
            acc, _ = cand, taken.append(c)
            pos += 1
            if acc == target:
                break
        if acc != target:
            raise ValueError(
                f"文{s['id']} をチャンクに対応づけられません。\n"
                f"  期待: {target}\n"
                f"  実際: {acc}"
            )
        result.append({
            "id": s["id"],
            "para": taken[0]["para"] if taken else s.get("para", 1),
            "en": s["en"],
            "ja": s["ja"],
            "chunks": taken,
        })
    if pos != len(chunks):
        raise ValueError(
            f"未使用のチャンクが {len(chunks) - pos} 個残っています"
            f"（本文の一部が動画に含まれません）"
        )
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    a = ap.parse_args()
    sb = json.loads(
        Path(f"output/ondoku/{a.id}_storyboard.json").read_text(encoding="utf-8")
    )
    rows = align(a.id, sb["sentences"])
    print(f"✅ {len(rows)}文すべてを対応づけました（未使用チャンクなし）")
    for r in rows[:3]:
        parts = " ".join(f"[{c['l']}{'★' if c['kata'] else ''}]{c['w']}" for c in r["chunks"])
        print(f"  文{r['id']} (段落{r['para']}): {parts}")
        print(f"    {r['ja']}")
