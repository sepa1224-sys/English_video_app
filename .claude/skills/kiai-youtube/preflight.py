#!/usr/bin/env python3
"""
kiai-youtube preflight: 1コマンドで自動アップの前提を点検する。
  - Anthropic API クレジット（台本生成の前提）
  - YouTube OAuth トークンの有効性（アップロードの前提・7日で失効しがち）
  - 各大学の次 Part 番号

使い方:  py .claude/skills/kiai-youtube/preflight.py
出力末尾の "PREFLIGHT: OK" / "PREFLIGHT: NG" で機械判定できる。
"""
import os, sys, json, socket

# cp932 回避
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# httplib2 が IPv6 でハングするため IPv4 を優先（auto_upload.py と同じ）
_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [r for r in _orig(h, *a, **k) if r[0] == socket.AF_INET] or _orig(h, *a, **k)

# .claude/skills/kiai-youtube/ から見たリポジトリルート
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
os.chdir(BASE)

from dotenv import load_dotenv
load_dotenv()

ok = True

# --- 1. Anthropic クレジット ---
try:
    import anthropic
    c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=5,
                      messages=[{"role": "user", "content": "Reply with: OK"}])
    print("[OK ] Anthropic API: クレジット有効（台本生成 可）")
except Exception as e:
    msg = str(e)
    if "credit balance is too low" in msg:
        print("[NG ] Anthropic API: クレジット切れ → Plans & Billing で購入が必要")
    else:
        print(f"[NG ] Anthropic API: {type(e).__name__}: {msg[:120]}")
    ok = False

# --- 2. YouTube トークン ---
TOKEN = os.path.join(BASE, "config", "token.json")
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    td = json.load(open(TOKEN, encoding="utf-8"))
    creds = Credentials(token=td["token"], refresh_token=td.get("refresh_token"),
                        token_uri=td["token_uri"], client_id=td["client_id"],
                        client_secret=td["client_secret"], scopes=td["scopes"])
    yt = build("youtube", "v3", credentials=creds)
    r = yt.channels().list(part="snippet", mine=True).execute()
    name = r["items"][0]["snippet"]["title"] if r.get("items") else "?"
    print(f"[OK ] YouTube トークン: 有効（チャンネル: {name}）")
except FileNotFoundError:
    print(f"[NG ] YouTube トークン: {TOKEN} が無い → 再認証が必要")
    ok = False
except Exception as e:
    msg = str(e)
    if "invalid_grant" in msg or "expired or revoked" in msg:
        print("[NG ] YouTube トークン: 失効（7日ルール）→ 再認証が必要")
        print("      対処: mv config/token.json config/token.json.expired_bak && py scripts/oauth_setup.py（ユーザーがブラウザで実行）")
    else:
        print(f"[NG ] YouTube トークン: {type(e).__name__}: {msg[:120]}")
    ok = False

# --- 3. 各大学の次 Part ---
defaults = {"todai": 6, "kyoto": 1, "osaka": 1}
parts = []
for uni, d in defaults.items():
    p = os.path.join(BASE, "data", f"{uni}_publish_part.txt")
    try:
        n = int(open(p, encoding="utf-8").read().strip())
    except Exception:
        n = d
    parts.append(f"{uni}=Part{n}")
print("[INFO] 次の番号: " + ", ".join(parts))

print("PREFLIGHT: OK" if ok else "PREFLIGHT: NG")
sys.exit(0 if ok else 1)
