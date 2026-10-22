"""動画工場：kiai-coaching-app（収益会議）の仕事を取りに行き、作って、結果を返す。

  python3 scripts/factory_poll.py               … 1回だけ取りに行く（launchd com.kiai.media-factory が10分ごとに動かす）
  FACTORY_DRY=1 python3 scripts/factory_poll.py … 試し：mp4 は作るが上げない（結果は「（試し）」で始まり、行は failed になる）

サーバーのアドレスと合言葉は ~/English_video_app/.env の KIAI_APP_URL／KIAI_FACTORY_SECRET（環境変数があればそちらを使う）。
  GET  {KIAI_APP_URL}/api/media/factory → { jobs: [{ id, kind, payload, detail }] }（返した仕事はサーバー側で running になる）
  POST {KIAI_APP_URL}/api/media/factory   { id, ok, result, videoId? }
作れる仕事は payload { type: 'tango_compilation', from, to, kind } だけ。それ以外は「手で作る」と返す（翌朝の会議が読む）。
"""
from __future__ import annotations
import os, sys, time, traceback
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

NOT_YET = "動画工場ではまだ作れない仕事（手で作る）"
RESULT_UNITS = 1900  # サーバーは result を2000字まで（JS の文字数＝UTF-16 の単位）


def clip(s: str, units: int = RESULT_UNITS) -> str:
    """UTF-16 の単位で units 以内に切る（絵文字などは2単位）"""
    out, n = [], 0
    for ch in s:
        n += 2 if ord(ch) > 0xFFFF else 1
        if n > units:
            break
        out.append(ch)
    return "".join(out)


def env() -> dict[str, str]:
    vals: dict[str, str] = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("KIAI_APP_URL", "KIAI_FACTORY_SECRET"):
        if os.environ.get(k):
            vals[k] = os.environ[k]
    return vals


def run_job(job: dict, dry: bool) -> dict:
    """1件作る。返り値は POST する { ok, result, videoId? }"""
    p = job.get("payload") or {}
    if not isinstance(p, dict) or p.get("type") != "tango_compilation":
        return {"ok": False, "result": NOT_YET}
    import tango_compile as tc
    import tango_exercise as te
    a, b, kind = p.get("from"), p.get("to"), p.get("kind")
    if type(a) is not int or type(b) is not int or kind not in ("exercise", "listen"):  # True/False は int として通さない
        return {"ok": False, "result": f"仕事の形がちがう：{p}"}
    out = te.OUT / f"{tc.name_of(a, b, kind)}.mp4"
    existed = out.exists()  # 前からあった mp4 は消さない
    try:
        out, meta = tc.build(a, b, kind)
        if dry:
            # 試しでは本物の仕事を「済」にしない（failed で「（試し）」と残す）
            return {"ok": False, "result": f"（試し）{meta['title']} をつないだ（{te.ts(int(meta['seconds'] * te.FPS))}）。上げていない"}
        vid = tc.upload(a, b, kind, out, meta)
        return {"ok": True, "result": f"{meta['title']} を非公開で上げた（再生リスト「{meta['playlist']}」）", "videoId": vid}
    except tc.CompileError as e:
        return {"ok": False, "result": str(e)}
    except te.QuotaExceeded as e:
        return {"ok": False, "result": f"YouTube の1日の上限で上げられなかった：{e}"}
    except tc.UploadedButIncomplete as e:
        return {"ok": False, "videoId": e.video_id,
                "result": f"非公開の動画は上がった（{e.video_id}）が、そのあと（記録・サムネ・再生リスト）で失敗：{e}"}
    finally:
        # ディスクが少ないので、この仕事でつないだ mp4 は残さない（稽古の mp4 があればいつでも作り直せる）
        if not existed:
            out.unlink(missing_ok=True)


def post_result(api: str, headers: dict, body: dict) -> bool:
    """結果を返す。失敗したら2回までやり直す（返せなかった行は、サーバーが6時間後に failed にする）"""
    for i in range(3):
        try:
            pr = requests.post(api, headers=headers, json=body, timeout=30)
            if pr.status_code == 200:
                return True
            print(f"  ✖ 返事が {pr.status_code}：{pr.text[:200]}")
            if 400 <= pr.status_code < 500:
                return False  # 形がちがう・running でない はやり直しても同じ
        except requests.RequestException as e:
            print(f"  ✖ 返せなかった：{e}")
        if i < 2:
            time.sleep(5 * (i + 1))
    return False


def main() -> int:
    cfg = env()
    url, secret = cfg.get("KIAI_APP_URL", "").rstrip("/"), cfg.get("KIAI_FACTORY_SECRET", "")
    if not url or not secret:
        print("✖ .env に KIAI_APP_URL と KIAI_FACTORY_SECRET がありません")
        return 2
    dry = os.environ.get("FACTORY_DRY") == "1"
    api, headers = f"{url}/api/media/factory", {"Authorization": f"Bearer {secret}"}
    r = requests.get(api, headers=headers, timeout=30)
    r.raise_for_status()
    jobs = r.json().get("jobs", [])
    for job in jobs:
        print(f"▶ 仕事 #{job['id']}（{job.get('kind')}）{job.get('payload')}")
        try:
            res = run_job(job, dry)
        except Exception as e:  # 作る途中で落ちても、running のまま残さず failed で返す
            traceback.print_exc()
            res = {"ok": False, "result": f"動画工場で失敗：{type(e).__name__}: {e}"}
        res["result"] = clip(res["result"])
        sent = post_result(api, headers, {"id": job["id"], **res})
        print(f"  {'✅' if res['ok'] else '✖'} {res['result']}（{'返した' if sent else '返せなかった'}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
