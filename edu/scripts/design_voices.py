"""ElevenLabs のボイスデザインで、キャラの見た目・性格に合う声の候補を作る。

1つの声で日本語のセリフも英語の例文も読ませるので、試し読みの文に両方を入れる。
候補（各3つ）は output/voices/design/<キャラ>_<番号>.mp3 に保存し、
選んだら save で自分のボイスとして登録する（cast.json に書く voice_id が返る）。

  python3 scripts/design_voices.py preview [キャラ...]   # 候補を作る（キャラ省略で全員）
  python3 scripts/design_voices.py save sennin 2         # 仙人の2番を登録
"""
from __future__ import annotations
import base64, json, os, sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT.parent / "output" / "voices" / "design"
API = "https://api.elevenlabs.io/v1"


def key() -> str:
    for line in (ROOT.parent / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("ELEVENLABS_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("ELEVENLABS_API_KEY がありません")


BOTH = "Speaks natural native Japanese, and reads English sentences in clear, natural English with the same voice."

CHARS = {
    "sennin": ("A very old Japanese hermit martial arts master in his nineties, long white beard. Raspy, airy, "
               "slightly trembling elderly male voice, slow and wise, with a playful mischievous chuckle. Warm and comical. " + BOTH,
               "ふぉっふぉっ、焦るでない。英語は、一歩ずつじゃ。よいか、例文をよく聞くのじゃ。 I have lived here for ten years. どうじゃ、分かったかの？"),
    "nekketsu": ('An adult Japanese voice actress performing the brash, mischievous underdog boy hero of a ninja-style action anime. Loud, scrappy and energetic boyish voice with a slightly raspy, husky edge, cheeky and stubborn, never gives up, cheerful and heroic, full of fighting spirit. ' + BOTH,
               'よっしゃあ！今日こそ完璧に覚えてやるぜ！見てろよ、オレは絶対に諦めねえからな！ I have known him since 2019! へへっ、どうだ、すげえだろ！'),
    "megane": ('An adult Japanese voice actress performing a tiny comical sidekick character in a cartoon who wears glasses and constantly grumbles. Extremely high-pitched, thin, squeaky, cartoonish and nasal voice, almost like a little mascot, whiny with drawn-out vowels, pitiful and funny. ' + BOTH,
               'えぇ〜、また間違えたんですかぁ？だから言ったじゃないですかぁ。もう、勘弁してくださいよぉ。 I have studied English for three years. はぁ〜、ぼくばっかり損してる気がしますぅ。'),
    "ikemen": ("A cocky handsome Japanese young man, about twenty. Low, smooth, husky voice, laid-back swagger, "
               "a little flirty and confident. " + BOTH,
               "フッ、英語なんてノリでなんとかなるだろ？ま、オレに任せとけって。 Trust me, I've got this. 細かいことは気にすんなよ。"),
    "tsundere": ("A tsundere Japanese teenage girl, about sixteen, with twin tails. High-pitched, sharp and bratty, "
                 "pouty and easily flustered, secretly caring. " + BOTH,
                 "べ、別にあんたのために覚えたわけじゃないんだからね！ほら、ちゃんと聞きなさいよ。 I can't afford to lose to you! ……ふん、今のはたまたまなんだから。"),
    "osananajimi": ('A young Japanese woman around eighteen, a close friend and classmate with a confident, playful personality who enjoys light-hearted joking. Clear, crisp and articulate, calm and composed, with a cheerful mischievous tone and soft laughter. ' + BOTH,
               'ねえねえ、ここ、どうしてこうなるか分かる？ふふ、分からないんだ。じゃあ、教えてあげよっか。 We have been friends for a long time. ほら、ちゃんと聞いてた？'),
    "spartan": ('A Japanese female karate instructor with a haughty, regal queen-like personality, like an arrogant aristocratic villainess in an anime. Rich, elegant, commanding mid-low voice, slow and confident, condescending, imperious, with a grand haughty laugh. ' + BOTH,
               'おーっほっほっほ！言い訳は聞きませんわ。もう一度、最初からおやりなさい。この私の前でひれ伏しなさい！ You must practice every single day. 分かりましたわね？'),
}


def preview(names: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    k = key()
    for name in names:
        desc, text = CHARS[name]
        # 試し読みは100文字以上が必要。短ければ同じ文をくり返す
        base = text
        while len(text) < 110:
            text += " " + base
        r = requests.post(f"{API}/text-to-voice/design", timeout=300,
                          headers={"xi-api-key": k, "Content-Type": "application/json"},
                          json={"voice_description": desc, "text": text, "model_id": "eleven_ttv_v3"})
        if not r.ok:
            print(name, r.status_code, r.text[:300])
            continue
        pv = r.json().get("previews", [])
        ids = []
        for i, p in enumerate(pv, 1):
            (OUT / f"{name}_{i}.mp3").write_bytes(base64.b64decode(p["audio_base_64"]))
            ids.append(p["generated_voice_id"])
        (OUT / f"{name}_ids.json").write_text(json.dumps({"description": desc, "ids": ids}), encoding="utf-8")
        print(f"{name}: {len(ids)}案")


def save(name: str, n: int) -> None:
    meta = json.loads((OUT / f"{name}_ids.json").read_text(encoding="utf-8"))
    r = requests.post(f"{API}/text-to-voice", timeout=120,
                      headers={"xi-api-key": key(), "Content-Type": "application/json"},
                      json={"voice_name": f"kiai_{name}", "voice_description": meta["description"],
                            "generated_voice_id": meta["ids"][n - 1]})
    r.raise_for_status()
    print(name, r.json()["voice_id"])


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:] or ["preview"]
    if cmd == "preview":
        preview(rest or list(CHARS))
    elif cmd == "save":
        save(rest[0], int(rest[1]))
