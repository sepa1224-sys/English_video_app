"""短文（日本語→英語）の聞き流し素材を、テーマから作る。

瞬間英作文の聞き流し動画（phrase_video.py）の素材。Claude が大人向けの短文を
書き下ろし、data/phrases/<set>.json に保存する。

作り方は3段階:
  1. 場面の設計図 … テーマの中で「言いたいこと」を count 個、重ならないように決める
  2. 執筆 …… 場面1つにつき1文だけ書く
  3. 校閲 …… 不自然な英語と日英のずれだけを直す（場面は変えない）
後から重複を見つけて差し替える方式だと、差し替えた文がまた別の文と重なり、
何度見直しても収まらなかった（「保留にしよう」が消えては戻った）。
最初に場面を決めておけば、そもそも重ならない。

  python3 phrase_gen.py --set p001 --count 100 --theme "仕事の雑談で言えそうで言えない表現"
  python3 phrase_gen.py --set p001 --review-only     # 作成済みのセットに校閲だけかける
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PHRASE_DIR = Path("data/phrases")
BATCH = 25
MAX_WORDS = 12

PLAN_SYSTEM = """あなたは日本の大人向け英会話スクールのコーチです。
瞬間英作文（日本語を聞いてすぐ英語で言う）の教材を作るため、まず「場面の設計図」を作ります。

テーマの中で、大人が実際に口にする「言いたいこと（発話の意図）」を指定の数だけ挙げてください。
- 1つずつ、誰に・どんな状況で・何を伝えたいかが分かる一行にする
  （例: 同僚に、頼まれた作業を来週に回してよいか聞く）
- **意図が重なるものは1つにまとめ、別の意図で埋める**。
  「保留にしよう」と「一旦置いておこう」、「脱線した」と「話がそれた」は同じ意図とみなす。
- 依頼・断り・謝罪・報告・相づち・意見・質問・感想・気づかいなど、機能を散らす。
- 日本人が「知っている単語なのに、とっさに出てこない」ものを優先する。
- テーマの場面と口調に合わせる（「雑談」ならくだけた会話。かしこまった敬語の場面ばかりにしない）。"""

PICK_SYSTEM = """瞬間英作文の教材の「場面の一覧」から、互いに最も重ならない場面を指定の数だけ選びます。
意図がほぼ同じ場面（例:「時間がかかりそう」と「思ったより時間がかかる」、
「今日は切り上げよう」と「続きは次回に」、「誤解を招く言い方」が2つ）は、どちらか1つだけ残す。
依頼・断り・謝罪・報告・相づち・意見・質問・感想・気づかいがかたよらないように選ぶ。
選んだ場面の番号を返す。"""

PICK_TOOL = {
    "name": "pick_situations",
    "description": "重ならない場面の番号を選ぶ",
    "input_schema": {
        "type": "object",
        "properties": {"picked": {"type": "array", "items": {"type": "integer"}}},
        "required": ["picked"],
    },
}

DUP_SYSTEM = """瞬間英作文の教材の短文リストから、「言いたいこと」がほぼ同じ文の組を全部挙げます。
言い回しが違っても、学習者から見て同じ練習になるものは重複とみなす。
（例:「今日は集中できない」と「集中力が続かない」、「話を戻そう」と「本題に戻ろう」、
「説明で分かった」と「イメージがつかめた」、「結局何が決まった？」が2つ）
組は [前の番号, 後の番号] で返す。無ければ空の配列。"""

DUP_TOOL = {
    "name": "report_duplicates",
    "description": "意味がほぼ同じ文の組",
    "input_schema": {
        "type": "object",
        "properties": {"pairs": {"type": "array", "items": {
            "type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}}},
        "required": ["pairs"],
    },
}

PLAN_TOOL = {
    "name": "plan_situations",
    "description": "重ならない場面（発話の意図）の一覧",
    "input_schema": {
        "type": "object",
        "properties": {"situations": {"type": "array", "items": {"type": "string"}}},
        "required": ["situations"],
    },
}

SYSTEM = f"""あなたは日本の大人向け英会話スクールのコーチです。
「日本語を聞いて、すぐ英語で言う」練習（瞬間英作文）用の短文を書きます。
与えられた場面1つにつき、1文だけ書いてください。場面の番号をそのまま n に入れる。

守ること:
- 英文は{MAX_WORDS}語以内。口に出して気持ちよく言える、自然な話し言葉にする。
- ネイティブが実際に口にする形だけを書く。和製英語的・直訳的な不自然な英語は禁止
  （例: × by this week → ○ by the end of the week / × I have a question to you）。
- 日本語は、日本人が普通に言う自然な文にする。直訳調にしない。
  ただし英文と意味がずれないこと（聞いた人が「その英語になる」と納得できる日本語）。
- 人名・実在の会社名は使わない。
- point には、その文で身につく型を日本語10字程度で書く（例: 現在完了の経験）。
"""

TOOL = {
    "name": "write_phrases",
    "description": "場面ごとに瞬間英作文用の短文を1つ書く",
    "input_schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "integer", "description": "場面の番号"},
                        "ja": {"type": "string"},
                        "en": {"type": "string"},
                        "point": {"type": "string"},
                    },
                    "required": ["n", "ja", "en", "point"],
                },
            },
        },
        "required": ["items"],
    },
}

REVIEW_SYSTEM = """あなたは英語ネイティブの編集者で、日本の大人向け瞬間英作文の教材を校閲します。
番号付きの短文リストを見て、次に当たる文だけを直してください。問題ない文は返さない。

1. 不自然な英語: ネイティブがその場面で言わない英語、直訳調、和製英語的な言い方
   （例: by today → by the end of the day）。→ 自然な英語に直す。
2. 日英のずれ: 日本語と英語の意味がずれているもの
   （例:「手が離せない」に I can't step away は「その場を離れられない」になる → I'm tied up right now）。
   → 日本語に合う英語に直す（必要なら日本語側を直す）。

言いたいこと（場面）は変えない。別の話題の文に差し替えない。直すのは言い方だけ。
直した後も英文12語以内。"""

REVIEW_TOOL = {
    "name": "fix_phrases",
    "description": "不自然・日英がずれている文だけを直す",
    "input_schema": {
        "type": "object",
        "properties": {
            "fixes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "integer", "description": "直す文の番号"},
                        "problem": {"type": "string", "enum": ["unnatural", "mismatch"]},
                        "reason": {"type": "string", "description": "何が問題か（短く）"},
                        "new_ja": {"type": "string", "description": "直した後の日本語"},
                        "new_en": {"type": "string", "description": "直した後の英語"},
                    },
                    "required": ["n", "problem", "reason", "new_ja", "new_en"],
                },
            },
        },
        "required": ["fixes"],
    },
}

TITLE_TOOL = {
    "name": "name_set",
    "description": "動画のタイトル案を付ける",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_ja": {"type": "string",
                         "description": "YouTubeタイトル。数（◯フレーズ）と『聞き流し』を入れる。45字以内"},
            "hook": {"type": "string", "description": "サムネ用の短い一言。12字以内"},
        },
        "required": ["title_ja", "hook"],
    },
}


def usable(item: dict) -> bool:
    en, ja = item.get("en", "").strip(), item.get("ja", "").strip()
    return bool(en and ja) and len(en.split()) <= MAX_WORDS + 2


def tool_list(r, key: str) -> list:
    """tool_use の入力から配列を取り出す。まれに JSON 文字列で返ってくるので戻す。"""
    data = next((b.input for b in r.content if b.type == "tool_use"), {})
    v = data.get(key, [])
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except json.JSONDecodeError:
            return []
        if isinstance(v, dict):
            v = v.get(key, [])
    return v if isinstance(v, list) else []


def plan(client, model: str, theme: str, count: int) -> list[str]:
    """多めに（1.3倍）挙げさせてから、重ならないものを count 個選ばせる。
    選ぶだけなら削るだけなので、書き直しと違って新しい重複が生まれない。"""
    want = int(count * 1.3)
    r = client.messages.create(
        model=model, max_tokens=12000, system=PLAN_SYSTEM,
        messages=[{"role": "user", "content": f"テーマ: {theme}\n場面を{want}個挙げてください。"}],
        tools=[PLAN_TOOL], tool_choice={"type": "tool", "name": PLAN_TOOL["name"]})
    cands = [str(s).strip() for s in tool_list(r, "situations") if str(s).strip()]
    if len(cands) <= count:
        return cands
    listing = "\n".join(f"{i}. {s}" for i, s in enumerate(cands, 1))
    r = client.messages.create(
        model=model, max_tokens=4096, system=PICK_SYSTEM,
        messages=[{"role": "user", "content":
                   f"テーマ: {theme}\n次の{len(cands)}個から{count}個選んでください。\n\n{listing}"}],
        tools=[PICK_TOOL], tool_choice={"type": "tool", "name": PICK_TOOL["name"]})
    picked = []
    for n in tool_list(r, "picked"):
        if isinstance(n, int) and 1 <= n <= len(cands) and n not in picked:
            picked.append(n)
    # 足りなければ、選ばれなかった中から先頭順に補う
    for n in range(1, len(cands) + 1):
        if len(picked) >= count:
            break
        if n not in picked:
            picked.append(n)
    print(f"  {len(cands)}個から{count}個に絞りました")
    return [cands[n - 1] for n in sorted(picked[:count])]


def write(client, model: str, theme: str, situations: list[str]) -> list[dict]:
    items: dict[int, dict] = {}
    for start in range(0, len(situations), BATCH):
        todo = list(range(start + 1, min(start + BATCH, len(situations)) + 1))
        # 返ってこなかった場面・条件を満たさなかった場面だけ、もう一度頼む
        for _ in range(3):
            lines = "\n".join(f"{n}. {situations[n - 1]}" for n in todo)
            r = client.messages.create(
                model=model, max_tokens=8192, system=SYSTEM,
                messages=[{"role": "user", "content": f"テーマ: {theme}\n\n{lines}"}],
                tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]})
            for x in tool_list(r, "items"):
                if isinstance(x, dict) and x.get("n") in todo and usable(x):
                    items[x["n"]] = {"ja": x["ja"].strip(), "en": x["en"].strip(),
                                     "point": str(x.get("point", "")).strip(),
                                     "situation": situations[x["n"] - 1]}
            todo = [n for n in todo if n not in items]
            if not todo:
                break
        print(f"  {len(items)}/{len(situations)}")
    return [items[n] for n in sorted(items)]


def find_dups(client, model: str, items: list[dict]) -> list[int]:
    """重複の組を挙げさせ、後ろ側の番号（0始まり）を返す。直させはしない。"""
    listing = "\n".join(f"{i}. {x['ja']} → {x['en']}" for i, x in enumerate(items, 1))
    r = client.messages.create(
        model=model, max_tokens=4096, system=DUP_SYSTEM,
        messages=[{"role": "user", "content": listing}],
        tools=[DUP_TOOL], tool_choice={"type": "tool", "name": DUP_TOOL["name"]})
    drop = set()
    for pair in tool_list(r, "pairs"):
        if (isinstance(pair, list) and len(pair) == 2
                and all(isinstance(n, int) and 1 <= n <= len(items) for n in pair)
                and pair[0] != pair[1]):
            a, b = sorted(pair)
            if a - 1 not in drop:          # 前側がもう消える予定なら、後ろ側は残す
                drop.add(b - 1)
                print(f"  重複: {a:03d} {items[a-1]['ja']} ／ {b:03d} {items[b-1]['ja']}")
    return sorted(drop)


def dedupe(client, model: str, theme: str, items: list[dict], rounds: int = 1) -> list[dict]:
    """重複を消して、消した数だけ新しい場面で補う。
    既定は1回。2回目以降は判定が厳しくなりすぎ、重複でない良い文まで消していった。"""
    for _ in range(rounds):
        drop = find_dups(client, model, items)
        if not drop:
            break
        keep = [x for i, x in enumerate(items) if i not in drop]
        have = "\n".join(f"- {x.get('situation') or x['ja']}" for x in keep)
        r = client.messages.create(
            model=model, max_tokens=4096, system=PLAN_SYSTEM,
            messages=[{"role": "user", "content":
                       f"テーマ: {theme}\n次の場面はもう使っています。どれとも重ならない"
                       f"新しい場面を{len(drop)}個挙げてください。\n\n{have}"}],
            tools=[PLAN_TOOL], tool_choice={"type": "tool", "name": PLAN_TOOL["name"]})
        new_sits = [str(x).strip() for x in tool_list(r, "situations") if str(x).strip()][:len(drop)]
        items = keep + write(client, model, theme, new_sits)
        print(f"  {len(drop)}文を差し替えました")
    return items


def review(client, model: str, items: list[dict], theme: str) -> list[dict]:
    """不自然な英語と日英のずれだけを直す。場面（言いたいこと）は変えない。"""
    listing = "\n".join(f"{i}. {x['ja']} → {x['en']}" for i, x in enumerate(items, 1))
    r = client.messages.create(
        model=model, max_tokens=16384, system=REVIEW_SYSTEM,
        messages=[{"role": "user", "content": f"テーマ: {theme}\n\n{listing}"}],
        tools=[REVIEW_TOOL], tool_choice={"type": "tool", "name": REVIEW_TOOL["name"]})
    items = [dict(x) for x in items]
    for f in tool_list(r, "fixes"):
        if not isinstance(f, dict):
            continue
        n = f.get("n", 0)
        if not (1 <= n <= len(items)):
            continue
        new = dict(items[n - 1], ja=str(f.get("new_ja", "")).strip(),
                   en=str(f.get("new_en", "")).strip())
        if not usable(new):
            continue
        old = items[n - 1]
        items[n - 1] = new
        print(f"  {n:03d} [{f.get('problem')}] {old['ja']} → {old['en']}")
        print(f"      ⇒ {new['ja']} → {new['en']}")
    return items


def main() -> int:
    ap = argparse.ArgumentParser(description="瞬間英作文の短文セットを作る")
    ap.add_argument("--set", required=True, help="セットID（例: p001）")
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--theme", default="日本人が英会話で言えそうで言えない表現")
    ap.add_argument("--model")
    ap.add_argument("--review-only", action="store_true",
                    help="作成済みのセットに、校閲（不自然・日英のずれの修正）だけをかける")
    a = ap.parse_args()

    load_dotenv()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY がありません。")
    model = a.model or os.getenv("EXAMPLE_MODEL", "claude-sonnet-5")
    client = anthropic.Anthropic(api_key=key)
    out = PHRASE_DIR / f"{a.set}.json"

    if a.review_only:
        data = json.loads(out.read_text(encoding="utf-8"))
        print(f"🧹 {out} の重複チェック")
        data["items"] = dedupe(client, model, data["theme"], data["items"])
        print("🔎 校閲中（不自然な英語・日英のずれ）")
        data["items"] = review(client, model, data["items"], data["theme"])
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 保存しました → {out}")
        return 0
    if out.exists():
        raise SystemExit(f"{out} は作成済みです。作り直すなら消してから実行してください。")

    print(f"🗺  場面を{a.count}個決めています")
    situations = plan(client, model, a.theme, a.count)
    if len(situations) < a.count:
        print(f"  ⚠ 場面が{len(situations)}個しか出ませんでした")
    print("✍️  場面ごとに1文ずつ書いています")
    items = write(client, model, a.theme, situations)
    print("🧹 重複チェック")
    items = dedupe(client, model, a.theme, items)
    print("🔎 校閲中（不自然な英語・日英のずれ）")
    items = review(client, model, items, a.theme)

    r = client.messages.create(
        model=model, max_tokens=1024,
        messages=[{"role": "user", "content":
                   f"テーマ「{a.theme}」の瞬間英作文 {len(items)}フレーズの聞き流し動画。"
                   f"例: {items[0]['ja']} → {items[0]['en']}"}],
        tools=[TITLE_TOOL], tool_choice={"type": "tool", "name": TITLE_TOOL["name"]})
    meta = next((b.input for b in r.content if b.type == "tool_use"), {})

    PHRASE_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"set": a.set, "theme": a.theme, **meta, "items": items},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ {len(items)}文 → {out}\n   タイトル案: {meta.get('title_ja')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
