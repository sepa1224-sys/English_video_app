"""
ondoku_audio.py — 音読動画のナレーション音声とタイミングを作る

文ごとに ElevenLabs で音声を生成し、文字単位アラインメントから
「どのSVOチャンクが何秒に読まれるか」を割り出して timing JSON に落とす。
ハイライトを推定ではなく実測で同期させるための土台。
"""

import os
import json
import time
import argparse
from pathlib import Path
from dotenv import load_dotenv

import requests

from ondoku_align import align

OUTPUT_DIR = Path("output") / "ondoku"
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps"

# ナレーター候補（英語ネイティブのプリメイド音声）
VOICES = {
    "george":  ("JBFqnCBsd6RMkjVDRZzb", "George - 語り部"),
    "alice":   ("Xb7hH8MSUJpSbSDYk0k2", "Alice - 教育者"),
    "brian":   ("nPczCjzI2devNBz1zQrb", "Brian - 深く落ち着いた"),
    "matilda": ("XrExE9yKIg1WjnnlVkGX", "Matilda - 知的"),
}

PAUSE_SENTENCE = 0.45   # 文と文の間
PAUSE_PARAGRAPH = 1.10  # 段落の切れ目
MAX_RETRIES = 3


def _tts_with_timestamps(text: str, vid: str, api_key: str, speed: float) -> dict:
    last = None
    for attempt in range(MAX_RETRIES):
        r = requests.post(
            TTS_URL.format(vid=vid),
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "speed": speed,
                },
            },
            timeout=180,
        )
        if r.ok:
            return r.json()
        last = f"{r.status_code} {r.text[:200]}"
        if r.status_code in (429, 500, 502, 503):
            time.sleep([2, 5, 10][attempt])
            continue
        break
    raise RuntimeError(f"TTS 失敗: {last}")


def _chunk_times(sentence_text: str, chunks: list[dict], alignment: dict) -> list[dict]:
    """文字単位アラインメントを、チャンク単位の開始/終了秒に畳む"""
    chars = alignment["characters"]
    starts = alignment["character_start_times_seconds"]
    ends = alignment["character_end_times_seconds"]

    # 返ってきた文字列と入力がずれることがあるので、返却側を正とする
    returned = "".join(chars)

    out, cursor = [], 0
    for c in chunks:
        w = c["w"]
        i = returned.find(w, cursor)
        if i < 0:                       # 空白の差異などで見つからない場合の保険
            i = returned.find(w.strip(), cursor)
        if i < 0:
            # 見つからなければ直前の終端を引き継ぐ（動画は壊さない）
            t0 = out[-1]["end"] if out else 0.0
            out.append({"w": w, "l": c["l"], "kata": c["kata"],
                        "start": t0, "end": t0})
            continue
        j = i + len(w) - 1
        out.append({
            "w": w, "l": c["l"], "kata": c["kata"],
            "start": float(starts[i]),
            "end": float(ends[min(j, len(ends) - 1)]),
        })
        cursor = j + 1
    return out


def build_audio(material_id: str, voice: str = "george", speed: float = 0.92,
                profile: str | None = None) -> dict:
    load_dotenv(override=True)
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY が設定されていません。")
    if voice not in VOICES:
        raise ValueError(f"voice は次から選んでください: {', '.join(VOICES)}")
    vid, vname = VOICES[voice]

    if profile:
        from ondoku_profiles import paths
        sb_path = paths(material_id, profile)["storyboard"]
    else:
        sb_path = OUTPUT_DIR / f"{material_id}_storyboard.json"
    sb = json.loads(sb_path.read_text(encoding="utf-8"))
    rows = align(material_id, sb["sentences"])

    audio_dir = OUTPUT_DIR / material_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    total_chars = sum(len(r["en"]) for r in rows)
    print(f"🎤 ナレーション生成: {vname} / {len(rows)}文 / 約{total_chars:,}文字")

    timeline, t = [], 0.0
    prev_para = None
    for r in rows:
        if prev_para is not None:
            t += PAUSE_PARAGRAPH if r["para"] != prev_para else PAUSE_SENTENCE
        prev_para = r["para"]

        text = " ".join(c["w"] for c in r["chunks"])
        j = _tts_with_timestamps(text, vid, api_key, speed)

        mp3 = audio_dir / f"s{r['id']:03d}.mp3"
        import base64
        mp3.write_bytes(base64.b64decode(j["audio_base64"]))

        al = j.get("alignment") or j.get("normalized_alignment")
        chunk_times = _chunk_times(text, r["chunks"], al)
        dur = float(al["character_end_times_seconds"][-1])

        timeline.append({
            "id": r["id"],
            "para": r["para"],
            "en": r["en"],
            "ja": r["ja"],
            "audio": str(mp3),
            "start": round(t, 3),
            "duration": round(dur, 3),
            "chunks": [
                {**c, "start": round(t + c["start"], 3), "end": round(t + c["end"], 3)}
                for c in chunk_times
            ],
        })
        t += dur
        print(f"  [{r['id']:2d}/{len(rows)}] {dur:5.2f}秒  {r['en'][:52]}")

    out = {
        "material_id": material_id,
        "voice": voice,
        "voice_name": vname,
        "speed": speed,
        "total_duration": round(t, 3),
        "sentences": timeline,
    }
    path = OUTPUT_DIR / f"{material_id}_timing.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ タイミング保存: {path}")
    print(f"   本文の総尺: {t:.1f}秒 ({int(t//60)}分{int(t%60):02d}秒)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="音読動画のナレーション生成")
    ap.add_argument("--id", required=True, help="教材ID（例: 056）")
    ap.add_argument("--voice", default="george", choices=sorted(VOICES))
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--profile", default=None, help="制作系統")
    a = ap.parse_args()
    build_audio(a.id, a.voice, a.speed, a.profile)
