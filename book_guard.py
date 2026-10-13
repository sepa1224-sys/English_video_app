"""市販の単語帳・参考書の中身を使った動画を、YouTube や Instagram に上げないための関所。

2026-10 に旺文社（ターゲット・でる順）の申し立てで著作権の警告を9件受け、チャンネルが消えかけた。
出版社は「書籍の収録内容（見出し語・訳・番号の並び）を動画で公開する」ことを侵害とみなす。
どのスクリプトから上げるときも、アップロードの直前にここを通す。
"""
from __future__ import annotations
import re

# 書名・シリーズ名（表記ゆれも）。見つかったら上げない
BOOK_WORDS = [
    "ターゲット", "target1900", "target1400", "target1200", "t1900", "t1400", "t1200",
    "でる順", "パス単", "鉄壁", "teppeki", "システム英単語", "シス単", "LEAP", "必携英単語",
    "速単", "速読英単語", "DUO", "金のフレーズ", "金フレ", "出る単", "キクタン", "銀のフレーズ",
]
_PAT = re.compile("|".join(re.escape(w) for w in BOOK_WORDS), re.IGNORECASE)


class BookContentError(RuntimeError):
    pass


def check(*texts) -> None:
    """題名・説明文・タグ・ファイル名などに書名が入っていたら止める。"""
    for t in texts:
        if t is None:
            continue
        s = " ".join(map(str, t)) if isinstance(t, (list, tuple, set)) else str(t)
        m = _PAT.search(s)
        if m:
            raise BookContentError(
                f"市販の単語帳（「{m.group(0)}」）の内容を使った動画は上げません（著作権の警告が来るため）。")


def disabled(name: str) -> None:
    """単語帳の中身から動画を作るスクリプトの入口で呼ぶ。動かさずに終わる。"""
    raise SystemExit(f"{name} は停止中です：市販の単語帳の内容を使った動画は作りません（2026-10 著作権の警告を受けたため）。")
