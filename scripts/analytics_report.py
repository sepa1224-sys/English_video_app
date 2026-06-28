#!/usr/bin/env python3
"""
analytics_report.py
YouTube Analytics API で「なぜ伸びるか」を分析する。
  - 動画別: 視聴維持率(averageViewPercentage)・平均視聴時間・視聴時間
  - 大学別: 維持率の比較
  - 流入元(trafficSource)・検索キーワード(特に伸びている京大)
※ 要 yt-analytics.readonly スコープ + GCPでYouTube Analytics API有効化。
   未付与なら403 → oauth_setup.py を再実行して再認証。
※ サムネのインプレッション/CTRはAPI非対応（YouTube Studioのみ）。

使い方: py scripts/analytics_report.py
"""
import os, sys, json, socket, re, datetime

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_o = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [r for r in _o(h, *a, **k) if r[0] == socket.AF_INET] or _o(h, *a, **k)

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(BASE)
from dotenv import load_dotenv
load_dotenv()
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.path.join(BASE, "config", "token.json")
JST = datetime.timezone(datetime.timedelta(hours=9))
START = "2026-01-01"
END = datetime.datetime.now(JST).strftime("%Y-%m-%d")


def creds():
    td = json.load(open(TOKEN, encoding="utf-8"))
    return Credentials(token=td["token"], refresh_token=td.get("refresh_token"),
                       token_uri=td["token_uri"], client_id=td["client_id"],
                       client_secret=td["client_secret"], scopes=td["scopes"])


def lab(t):
    for k in ("東大", "京大", "阪大"):
        if k in t and "リスニング" in t:
            return k
    return None


def part(t):
    m = re.search(r"No\.?\s*(\d+)", t) or re.search(r"第\s*(\d+)\s*回", t)
    return int(m.group(1)) if m else None


def main():
    c = creds()
    yt = build("youtube", "v3", credentials=c)
    ya = build("youtubeAnalytics", "v2", credentials=c)

    # 公開リスニング動画の一覧
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    up = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = []
    tok = None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=up, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    vids = {}
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,status", id=",".join(ids[i:i + 50])).execute()
        for v in r["items"]:
            t = v["snippet"]["title"]
            if lab(t) and v["status"]["privacyStatus"] == "public":
                vids[v["id"]] = {"uni": lab(t), "part": part(t), "title": t}

    if not vids:
        print("公開リスニング動画が見つかりません。")
        return

    vid_list = list(vids.keys())

    def q(**kw):
        kw.setdefault("ids", "channel==MINE")
        kw.setdefault("startDate", START)
        kw.setdefault("endDate", END)
        return ya.reports().query(**kw).execute()

    try:
        # --- 動画別 維持率 ---
        rep = q(metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage",
                dimensions="video", filters="video==" + ",".join(vid_list))
    except Exception as e:
        msg = str(e)
        if "403" in msg or "insufficient" in msg.lower() or "scope" in msg.lower():
            print("[NG] Analytics権限がありません。")
            print("  1) GCPで『YouTube Analytics API』を有効化")
            print("  2) mv config/token.json config/token.json.bak && py scripts/oauth_setup.py で再認証")
            return
        raise

    rows = {r[0]: r[1:] for r in rep.get("rows", [])}  # video -> [views, mins, avgDur, avgPct]
    data = []
    for vid, info in vids.items():
        m = rows.get(vid)
        if not m:
            continue
        data.append({**info, "views": int(m[0]), "mins": int(m[1]), "avg_dur": int(m[2]), "avg_pct": float(m[3])})

    print(f"==== 動画別 視聴維持率（{START}〜{END}）====")
    print(f'{"大学":4} {"No":>3} {"再生":>5} {"維持率":>6} {"平均視聴":>7}')
    for d in sorted(data, key=lambda x: -x["avg_pct"]):
        print(f'{d["uni"]:4} {str(d["part"]):>3} {d["views"]:>5} {d["avg_pct"]:>5.1f}% {d["avg_dur"]//60}:{d["avg_dur"]%60:02d}')

    print("\n==== 大学別 平均維持率 ====")
    for u in ("東大", "京大", "阪大"):
        g = [d for d in data if d["uni"] == u]
        if g:
            print(f'{u}: 維持率 {sum(d["avg_pct"] for d in g)/len(g):5.1f}% / 平均視聴 {sum(d["avg_dur"] for d in g)//len(g)}秒 ({len(g)}本)')

    # --- 流入元（全リスニング動画） ---
    try:
        ts = q(metrics="views", dimensions="insightTrafficSourceType",
               filters="video==" + ",".join(vid_list), sort="-views")
        print("\n==== 流入元（リスニング全体）====")
        for r in ts.get("rows", []):
            print(f"  {r[0]:24} {r[1]:>6} views")
    except Exception as e:
        print(f"  流入元取得スキップ: {str(e)[:80]}")

    # --- 京大の検索キーワード ---
    kyoto_ids = [vid for vid, i in vids.items() if i["uni"] == "京大"]
    if kyoto_ids:
        try:
            kw = q(metrics="views", dimensions="insightTrafficSourceDetail",
                   filters="video==" + ",".join(kyoto_ids) + ";insightTrafficSourceType==YT_SEARCH",
                   sort="-views", maxResults=15)
            print("\n==== 京大の流入検索キーワード（YouTube検索）====")
            rows_kw = kw.get("rows", [])
            if rows_kw:
                for r in rows_kw:
                    print(f"  {r[1]:>5} views | {r[0]}")
            else:
                print("  (検索流入データなし／まだ少ない)")
        except Exception as e:
            print(f"  検索KW取得スキップ: {str(e)[:80]}")


if __name__ == "__main__":
    main()
