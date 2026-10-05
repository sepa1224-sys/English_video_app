"""キャラが掛け合いで教える解説動画の台本を、Claude に書かせる。

出力は edu/episodes/<id>.json（edu/src/types.ts の Episode 形式）。
そのあと edu で声を付けて（voice.mjs）書き出す（render.mjs）。

  python3 edu_script.py --id g001 --kind grammar --format short --topic "現在完了の継続（for と since）"
  python3 edu_script.py --id w001 --kind word --format short --topic "afford"
  python3 edu_script.py --id g101 --kind grammar --format long --topic "関係代名詞 who / which / that"

一括で動画まで作るなら edu_make.py を使う。
"""
from __future__ import annotations
import argparse, json, os, re, sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

EP_DIR = Path("edu/episodes")
SPEAKERS = ["master", "spartan", "ikemen", "tsundere", "osananajimi", "megane", "nekketsu"]
POSES = ["idle", "talk", "point", "surprised", "laugh", "fist", "arms"]
LABELS = ["S", "V", "O", "C", "M", "+", ""]

CAST = """登場人物（口調を必ず守る）:
- master（仙人）: 先生役。長い白ひげに杖の、山の道場の仙人。静かで短く、核心だけを言う。「〜じゃ」「〜せい」「〜であろう」。たまにボソッととぼけたことを言う。
- nekketsu（熱血）: 声がでかい。自信満々に間違える。「〜だッ！」「よっしゃ！」。正されると素直に燃える。
- megane（ウザメガネ）: 丁寧語で煽るが正論。「〜ですね」「統計的には〜」。人の間違いを嬉しそうに指摘する。
- tsundere（ツンデレライバル）: 素直じゃない。「べ、別に〜」「ふーん」。分かっていないのを隠そうとして墓穴を掘る。
- osananajimi（幼なじみ）: やわらかい。視聴者と同じ素朴な疑問を口にする。「〜だね」「〜なの？」。
- ikemen（オラオラ系イケメン）: ノリと勢い。「〜だぜ」「上等だ」。
- spartan（スパルタ師範代）: 仙人の右腕の女性師範代。厳しい。「〜しなさい」「言い訳は聞きません」。ゲストで締める役。
マスター以外は1話につき1〜2人まで。毎回メンバーを変えてよい。"""

VISUALS = """画面（visual）の種類。ビートに visual を書くとその絵に切り替わり、書かないビートでは前の絵が残る:
- {"kind":"title","text":"題","sub":"副題"} … 冒頭のつかみ
- {"kind":"word","en":"afford","ja":"〜する余裕がある","pos":"動詞","note":"can afford to do の形で"} … 単語カード
- {"kind":"image","emoji":"💸","label":"お金が足りない"} … 絵文字1つで場面を見せる
- {"kind":"sentence","chunks":[{"w":"I","l":"S"},{"w":"have lived","l":"V"},{"w":"here","l":"M"},{"w":"for ten years.","l":"M"}],"ja":"10年住んでいる","mark":[1]}
    … 英文を意味のかたまりに分けて色分け（S主語 V動詞 O目的語 C補語 M修飾 +つなぎ）。mark は丸で囲むかたまりの番号（0始まり）
- {"kind":"wrong","wrong":"I am living here since 2015.","right":"I have lived here since 2015.","why":"since は現在完了と"} … ×のハンコ→正解
- {"kind":"compare","a":{"label":"for","en":"for 3 years","ja":"期間"},"b":{"label":"since","en":"since 2020","ja":"起点"}}
- {"kind":"rule","title":"ルール","lines":["for ＋ 期間","since ＋ 始まった時点"]} … 黒板に要点
- {"kind":"quiz","q":"I have known him ___ 2019.","choices":["for","since"],"answer":1,"reveal":false} … reveal:false のビートに think（秒）を付けて考えさせ、次のビートで同じクイズを reveal:true にして答えを出す
- {"kind":"none"} … 絵を消す"""

RULES = {
    "short": """形式: 縦型ショート。全体で40〜50秒、10〜13ビート。1ビートのセリフは25字以内（声にすると思ったより長くなる）。
構成:
1. 冒頭2ビートで「あるある間違い」か「意外な事実」でつかむ（最初の3秒が勝負）。生徒が自信満々に間違える → 誰かがツッコむ、が基本形
2. マスターが核心を一言で。wrong / compare / rule のどれかで見せる
3. 例文を sentence で1〜2個（en に英文を入れて英語の声で読ませる）
4. クイズ1問（think 3秒）→ 答え
5. オチ（生徒の一言で笑わせて終わる）""",
    "long": """形式: 横型の長尺。全体で5〜8分、60〜100ビート。
構成:
1. つかみ（title と、生徒の間違い）
2. 3〜4つの小見出しに分けて解説。小見出しの頭は title か rule で区切る
3. 各小見出しに例文（sentence, en付き）を2つ以上、ひっかけを1つ（wrong）
4. 途中と最後にクイズ（合計3〜5問、think 4秒）
5. 最後に rule でまとめ、オチで締める""",
}

KIND = {
    "grammar": "文法解説。中高生と大人の学び直しの両方が分かるように。文法用語は最小限にし、使うときはすぐ噛み砕く。",
    "word": "英単語の解説。意味だけでなく、イメージ（核の意味）、よく出る形（コロケーション）、間違えやすい点を見せる。冒頭で word カードを出す。",
}

SYSTEM = f"""あなたは「気合イングリッシュ」の YouTube 解説動画の脚本家です。
キャラクターの掛け合いで、英語を面白おかしく、しかし正確に分かりやすく教える台本を書きます。

{CAST}

{VISUALS}

書き方:
- line は声で読むセリフ。ショートは25字以内、長尺でも40字以内。字幕にもなるので、短く切る。
- line は自然な日本語の話し言葉にする。直訳調や、日本人が言わない言い回し（例：「俺の英語歴を英語で言うぞ」）は禁止。書いたら声に出して不自然でないか確かめる。
- line は音声合成が読む。読みが割れる1字の漢字（金・核・方・何・辛い 等）は避け、「お金」「意味」のように読みが一つに決まる言葉か、ひらがなで書く。
- 英文を読ませたいときは line に入れず en に入れる（英語の声で読む）。line には英単語を混ぜすぎない。
- en は1ビート1文・12語以内。en のあるビートの line は「英語で言うと？」の前振りか和訳にし、line と en の中身をずらさない。
- line に記号（「」『』！？以外）や絵文字を入れない。数字は読み方がぶれないものだけ。
- caption は字幕を line と変えたいときだけ書く（長いセリフを要約したいとき等）。
- マスターのビートには pose を付ける（talk=ふつうに話す / point=指を立てて要点 / surprised=驚く / laugh=大笑い）。生徒のビートには不要。
- fever: true を1話に1〜2回だけ付ける。仙人が宙に浮いて背景が光る見せ場。いちばん大事な一言かオチに使う（クイズの答えのビートは自動でフィーバーになるので付けなくてよい）。
- ビート id は b01, b02, … の連番。
- 英語は必ず正確に。説明の正しさは笑いより優先する。
- 笑いはキャラ同士のズレ（自信満々の誤り、煽り、照れ隠し、マスターの一言）で作る。下品・差別・特定の人をいじる笑いは禁止。
- 最後のビートで「チャンネル登録」等の呼びかけはしない（くどくなる）。"""

TOOL = {
    "name": "write_episode",
    "description": "解説動画の台本",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "画面上部に出す題。16字以内"},
            "youtube_title": {"type": "string", "description": "YouTubeのタイトル。60字以内"},
            "beats": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "who": {"type": "string", "enum": SPEAKERS},
                        "line": {"type": "string"},
                        "en": {"type": "string"},
                        "caption": {"type": "string"},
                        "pose": {"type": "string", "enum": POSES},
                        "think": {"type": "number"},
                        "fever": {"type": "boolean"},
                        "visual": {"type": "object"},
                    },
                    "required": ["id", "who", "line"],
                },
            },
        },
        "required": ["title", "youtube_title", "beats"],
    },
}


def tool_input(r) -> dict:
    data = next((b.input for b in r.content if b.type == "tool_use"), {})
    # まれに配列を JSON 文字列で返すので戻す
    if isinstance(data.get("beats"), str):
        try:
            data["beats"] = json.loads(data["beats"])
        except json.JSONDecodeError:
            data["beats"] = []
    return data


def check(ep: dict) -> list[str]:
    """形式の崩れを機械的に見つける（中身の正しさは見ない）。"""
    probs = []
    beats = ep.get("beats", [])
    if not beats:
        return ["ビートが空"]
    for b in beats:
        v = b.get("visual")
        if isinstance(v, str):
            try:
                b["visual"] = v = json.loads(v)
            except json.JSONDecodeError:
                probs.append(f"{b.get('id')}: visual が JSON でない")
                continue
        if v:
            k = v.get("kind")
            if k == "sentence":
                for c in v.get("chunks", []):
                    if c.get("l") not in LABELS:
                        c["l"] = ""
            if k == "quiz" and not (0 <= v.get("answer", -1) < len(v.get("choices", []))):
                probs.append(f"{b['id']}: クイズの answer が選択肢の範囲外")
        if len(b.get("line", "")) > 60:
            probs.append(f"{b['id']}: セリフが長すぎる（{len(b['line'])}字）")
        if b.get("who") == "master" and not b.get("pose"):
            b["pose"] = "talk"
    return probs


def main() -> int:
    ap = argparse.ArgumentParser(description="キャラ掛け合いの解説動画の台本を書く")
    ap.add_argument("--id", required=True)
    ap.add_argument("--kind", choices=["grammar", "word"], required=True)
    ap.add_argument("--format", choices=["short", "long"], default="short")
    ap.add_argument("--topic", required=True, help="文法項目や単語")
    ap.add_argument("--series", help="左上のバッジ（既定: 気合の文法 / 気合の英単語）")
    ap.add_argument("--model")
    a = ap.parse_args()

    out = EP_DIR / f"{a.id}.json"
    if out.exists():
        raise SystemExit(f"{out} は作成済みです。作り直すなら消してください。")
    load_dotenv()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = a.model or os.getenv("EDU_MODEL", "claude-opus-5-5")

    prompt = f"種類: {KIND[a.kind]}\n{RULES[a.format]}\n\n題材: {a.topic}"
    print(f"✍️  台本を書いています（{model}）")
    # Opus 5.5 はツールの強制（tool_choice: tool）を受け付けないので auto にし、指示で使わせる。
    # 長尺は出力が長く、一括の応答だと時間切れになるのでストリームで受ける
    with client.messages.stream(
            model=model, max_tokens=32000 if a.format == "long" else 8000,
            system=SYSTEM + "\n\n台本は必ず write_episode ツールで返すこと。",
            messages=[{"role": "user", "content": prompt}],
            tools=[TOOL], tool_choice={"type": "auto"}) as st:
        r = st.get_final_message()
    data = tool_input(r)
    if not data.get("beats"):
        raise SystemExit(f"台本が返りませんでした（stop_reason={r.stop_reason}）")
    probs = check(data)
    if probs:
        print("⚠ 直す必要がある点:\n  " + "\n  ".join(probs))

    ep = {"id": a.id, "format": a.format, "kind": a.kind, "title": data["title"],
          "youtube_title": data.get("youtube_title", data["title"]), "topic": a.topic,
          "beats": data["beats"]}
    if a.series:
        ep["series"] = a.series
    EP_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ep, ensure_ascii=False, indent=1), encoding="utf-8")
    secs = sum(len(b["line"]) / 7 + (len(b.get("en", "").split()) / 2.5) + 0.3 + b.get("think", 0)
               for b in ep["beats"])
    print(f"✅ {len(ep['beats'])}ビート・約{round(secs)}秒（見積もり） → {out}")
    for b in ep["beats"]:
        v = (b.get("visual") or {}).get("kind", "")
        print(f"  {b['id']} {b['who']:<11} {('['+v+']') if v else '':<11} {b['line']}{'  / ' + b['en'] if b.get('en') else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
