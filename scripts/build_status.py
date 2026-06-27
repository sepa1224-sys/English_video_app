#!/usr/bin/env python3
"""
build_status.py
気合イングリッシュの「今の状況」を1つの status.json にまとめる。
ダッシュボード(kiai-dashboard)が読む唯一のデータソース。

収集内容:
  - チャンネル情報 / 各動画の基本指標(再生回数・高評価・コメント数)
  - 大学別の次Part番号・アップ済み本数・抜け検知
  - YouTube OAuthトークンの残り日数(テスト状態=7日失効ルール)
  - Anthropicクレジットの簡易チェック
  - 簡易評価(再生回数ランキング・カテゴリ別平均)

使い方:
  py scripts/build_status.py [--out ../kiai-dashboard/public/status.json] [--no-anthropic]
出力が無指定なら data/status.json に書く。
"""
import os, sys, re, json, socket, argparse, datetime

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_orig = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [r for r in _orig(h, *a, **k) if r[0] == socket.AF_INET] or _orig(h, *a, **k)

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(BASE)

from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(BASE, "config", "token.json")
MASTER = os.path.join(BASE, "data", "channel_analysis", "genre_master.json")
JST = datetime.timezone(datetime.timedelta(hours=9))

UNIS = {
    "todai": {"label": "東大", "kw": "東大", "genre": "listening_todai", "default_part": 6},
    "kyoto": {"label": "京大", "kw": "京大", "genre": "listening_kyoto", "default_part": 1},
    "osaka": {"label": "阪大", "kw": "阪大", "genre": "listening_osaka", "default_part": 1},
}
OAUTH_PRODUCTION = True  # GCP同意画面を「本番」公開済み(2026-06-27) → リフレッシュトークンは失効しない
TOKEN_TTL_DAYS = 7       # 「テスト」状態だった頃の失効ルール(参考)。OAUTH_PRODUCTION=Falseの時のみ有効


def creds_from_token():
    td = json.load(open(TOKEN, encoding="utf-8"))
    return Credentials(token=td["token"], refresh_token=td.get("refresh_token"),
                       token_uri=td["token_uri"], client_id=td["client_id"],
                       client_secret=td["client_secret"], scopes=td["scopes"])


def read_part(uni):
    p = os.path.join(BASE, "data", f"{uni}_publish_part.txt")
    try:
        return int(open(p, encoding="utf-8").read().strip())
    except Exception:
        return UNIS[uni]["default_part"]


def playlist_id(genre):
    try:
        m = json.load(open(MASTER, encoding="utf-8"))
        return m["genres"].get(genre, {}).get("playlist_id", "")
    except Exception:
        return ""


def part_from_title(title):
    m = re.search(r"No\.?\s*(\d+)", title) or re.search(r"第\s*(\d+)\s*回", title)
    return int(m.group(1)) if m else None


def classify(title):
    for uni, c in UNIS.items():
        if c["kw"] in title:
            return uni
    return None


def list_all_videos(yt):
    """チャンネルのアップロード動画を全件、基本指標つきで返す。"""
    ch = yt.channels().list(part="snippet,contentDetails", mine=True).execute()
    item = ch["items"][0]
    uploads = item["contentDetails"]["relatedPlaylists"]["uploads"]
    channel = {"title": item["snippet"]["title"], "id": item["id"]}

    vids = []
    token = None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=token).execute()
        vids += [it["contentDetails"]["videoId"] for it in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break

    out = []
    for i in range(0, len(vids), 50):
        chunk = vids[i:i + 50]
        r = yt.videos().list(part="snippet,statistics,status", id=",".join(chunk)).execute()
        for v in r["items"]:
            st = v.get("statistics", {})
            out.append({
                "video_id": v["id"],
                "title": v["snippet"]["title"],
                "published_at": v["snippet"]["publishedAt"],
                "privacy": v.get("status", {}).get("privacyStatus", "?"),
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "comments": int(st.get("commentCount", 0)),
            })
    return channel, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "data", "status.json"))
    ap.add_argument("--no-anthropic", action="store_true")
    args = ap.parse_args()

    now = datetime.datetime.now(JST)
    alerts = []

    # --- YouTube ---
    youtube_ok = True
    channel = {"title": "?", "id": ""}
    videos = []
    try:
        yt = build("youtube", "v3", credentials=creds_from_token())
        channel, videos = list_all_videos(yt)
    except Exception as e:
        youtube_ok = False
        msg = str(e)
        if "invalid_grant" in msg or "expired or revoked" in msg:
            alerts.append({"level": "error", "msg": "YouTubeトークンが失効しています。再認証が必要です。"})
        else:
            alerts.append({"level": "error", "msg": f"YouTube取得エラー: {msg[:120]}"})

    # --- トークン残日数（本番公開後は失効しないので警告不要） ---
    token_age_days = token_left = None
    if os.path.exists(TOKEN):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(TOKEN), JST)
        token_age_days = round((now - mtime).total_seconds() / 86400, 1)
        if not OAUTH_PRODUCTION:
            token_left = round(TOKEN_TTL_DAYS - token_age_days, 1)
            if token_left <= 2:
                alerts.append({"level": "warn",
                               "msg": f"YouTubeトークンが残り約{token_left}日で失効します。本番公開で恒久化を推奨。"})

    # --- Anthropic クレジット ---
    anthropic_ok = None
    if not args.no_anthropic:
        try:
            import anthropic
            c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            c.messages.create(model="claude-haiku-4-5-20251001", max_tokens=5,
                              messages=[{"role": "user", "content": "OK"}])
            anthropic_ok = True
        except Exception as e:
            anthropic_ok = False
            if "credit balance is too low" in str(e):
                alerts.append({"level": "error", "msg": "Anthropicクレジット切れ。台本生成ができません。"})

    # --- 大学別に整理 ---
    unis_out = []
    for uni, c in UNIS.items():
        my = []
        for v in videos:
            if classify(v["title"]) == uni:
                vv = dict(v)
                vv["part"] = part_from_title(v["title"])
                my.append(vv)
        my.sort(key=lambda x: (x["part"] is None, x["part"] or 0))
        next_part = read_part(uni)
        # 正規シリーズ(Part番号あり)で期待本数 = next_part-1 をカバーできているか
        parts_present = sorted({v["part"] for v in my if v["part"]})
        expected = list(range(1, next_part))
        missing = [p for p in expected if p not in parts_present]
        if missing:
            alerts.append({"level": "warn",
                           "msg": f"{c['label']}: Part {missing} が未アップの可能性"})
        pid = playlist_id(c["genre"])
        unis_out.append({
            "uni": uni, "label": c["label"],
            "next_part": next_part,
            "uploaded_count": len([v for v in my if v["part"]]),
            "missing_parts": missing,
            "playlist_id": pid,
            "playlist_url": f"https://www.youtube.com/playlist?list={pid}" if pid else "",
            "videos": my,
        })

    # --- 簡易評価: 再生回数ランキング(全体・正規シリーズのみ) ---
    series = [dict(v, uni=classify(v["title"])) for v in videos
             if classify(v["title"]) and part_from_title(v["title"])]
    for v in series:
        v["part"] = part_from_title(v["title"])
    top = sorted(series, key=lambda x: x["views"], reverse=True)[:10]
    evaluation = {
        "total_videos": len(videos),
        "total_views": sum(v["views"] for v in videos),
        "top_by_views": [{"title": v["title"], "uni": v["uni"], "part": v["part"],
                          "views": v["views"], "url": f"https://youtu.be/{v['video_id']}"} for v in top],
        "note": "アップ直後は再生数が少なく評価は参考値。データ蓄積後に傾向が出ます。",
    }

    status = {
        "generated_at": now.isoformat(),
        "channel": channel,
        "health": {
            "youtube_ok": youtube_ok,
            "anthropic_ok": anthropic_ok,
            "token_age_days": token_age_days,
            "token_left_days": token_left,
            "token_ttl_days": TOKEN_TTL_DAYS,
            "oauth_production": OAUTH_PRODUCTION,
        },
        "universities": unis_out,
        "evaluation": evaluation,
        "alerts": alerts,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"[OK] status.json -> {args.out}")
    print(f"  channel={channel['title']} videos={len(videos)} alerts={len(alerts)}")
    for u in unis_out:
        print(f"  {u['label']}: next=Part{u['next_part']} uploaded={u['uploaded_count']} missing={u['missing_parts']}")


if __name__ == "__main__":
    main()
