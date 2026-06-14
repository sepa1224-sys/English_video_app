"""
Auto-upload a Todai listening video to YouTube, set the "Part N" thumbnail,
and add it to the Todai listening playlist.

Auth (new JSON method, matches scripts/upload_video.py):
  1. Put config/client_secret.json   (GCP project: englishpodcast)
  2. Run: py scripts/oauth_setup.py   -> creates config/token.json
Thumbnail base:
  assets/thumbnail_base_todai.png     (gate + catch copy, WITHOUT the "Part N")

Usage:
  py auto_upload.py "output/exam/todai/Todai_Listening_XXXX.mp4"   # upload existing
  py auto_upload.py --generate                                      # generate then upload
  py auto_upload.py --privacy public "<file>"                       # override privacy
"""
import os
import sys
import re
import json
import socket

# UTF-8 console (Windows cp932 safety)
for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Force IPv4: httplib2 (used by google-api-python-client) hangs on connect when
# IPv6 routing is broken here (curl works because it falls back to IPv4).
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(host, *args, **kwargs):
    res = _orig_getaddrinfo(host, *args, **kwargs)
    v4 = [r for r in res if r[0] == socket.AF_INET]
    return v4 or res
socket.getaddrinfo = _ipv4_only_getaddrinfo

from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(BASE_DIR, "config", "token.json")
MASTER_FILE = os.path.join(BASE_DIR, "data", "channel_analysis", "genre_master.json")
PART_FILE = os.path.join(BASE_DIR, "data", "todai_publish_part.txt")
THUMB_BASE = os.path.join(BASE_DIR, "assets", "thumbnail_base_todai.png")
GENRE = "listening_todai"
DEFAULT_TAGS = ["東大リスニング", "大学受験", "英語リスニング", "東大英語", "リスニング対策"]


def read_part() -> int:
    try:
        return int(open(PART_FILE, encoding="utf-8").read().strip())
    except Exception:
        return 4


def bump_part(n: int):
    with open(PART_FILE, "w", encoding="utf-8") as f:
        f.write(str(n + 1))


def get_credentials():
    if not os.path.exists(TOKEN_FILE):
        raise FileNotFoundError(
            f"{TOKEN_FILE} がありません。config/client_secret.json を置いてから "
            f"`py scripts/oauth_setup.py` を実行してください。"
        )
    td = json.load(open(TOKEN_FILE, encoding="utf-8"))
    creds = Credentials(
        token=td["token"], refresh_token=td.get("refresh_token"),
        token_uri=td["token_uri"], client_id=td["client_id"],
        client_secret=td["client_secret"], scopes=td["scopes"],
    )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        td["token"] = creds.token
        json.dump(td, open(TOKEN_FILE, "w"), indent=2)
        print("  - token refreshed")
    return creds


def _desc_path_for(video_path: str) -> str:
    return os.path.splitext(video_path)[0] + "_description.txt"


def prepare(video_path: str, part: int):
    """Return (title, description, thumbnail_path) with the part number forced to N."""
    dp = _desc_path_for(video_path)
    if not os.path.exists(dp):
        raise FileNotFoundError(f"Description not found: {dp}")
    desc = open(dp, encoding="utf-8").read()
    desc = re.sub(r"第\d+回", f"第{part}回", desc, count=1)
    title = desc.splitlines()[0].strip() if desc.strip() else f"【東大リスニング】第{part}回"

    # YouTube descriptions are capped at 5000 chars. Trim the (long) Script tail
    # but preserve the trailing hashtag line for discovery.
    LIMIT = 4900
    if len(desc) > LIMIT:
        lines = desc.rstrip().splitlines()
        tail = ""
        if lines and lines[-1].lstrip().startswith("#"):
            tail = "\n\n" + lines[-1].strip()
        keep = max(0, LIMIT - len(tail) - 30)
        desc = desc[:keep].rstrip() + "\n\n…(全文は動画内をご覧ください)" + tail
        print(f"  - Description trimmed to {len(desc)} chars (YouTube 5000 limit)")

    thumb = None
    if os.path.exists(THUMB_BASE):
        try:
            import thumbnail_gen
            thumb = thumbnail_gen.generate_exam_thumbnail(
                part, THUMB_BASE,
                os.path.join(BASE_DIR, "output", "exam", "todai", f"thumb_part{part}.png"),
            )
            print(f"  - Thumbnail: {thumb}")
        except Exception as e:
            print(f"  ! Thumbnail failed (continuing without): {e}")
    else:
        print(f"  ! Thumbnail base missing ({THUMB_BASE}); uploading without a custom thumbnail.")
    return title, desc, thumb


def _playlist_id() -> str:
    try:
        m = json.load(open(MASTER_FILE, encoding="utf-8"))
        return m["genres"].get(GENRE, {}).get("playlist_id", "")
    except Exception:
        return ""


def main():
    args = sys.argv[1:]
    privacy = "unlisted"
    if "--privacy" in args:
        i = args.index("--privacy")
        privacy = args[i + 1]
        del args[i:i + 2]
    generate = "--generate" in args
    video_path = next((a for a in args if not a.startswith("--")), None)

    part = read_part()

    if generate or not video_path:
        # day_number == part number -> each part uses a fresh 鉄壁 10-word block
        # (Part5 -> 鉄壁 41-50, Part6 -> 51-60, ...). No repeats across parts.
        print(f"=== Generating new Todai video (Part {part}, 鉄壁 block {part} = ID {(part-1)*10+1}-{(part-1)*10+10}) ===")
        import main as pipeline
        r = pipeline.run_podcast_generation(
            topic="", level="英単語帳鉄壁", day_number=part,
            mode="university_listening", university="todai", generate_thumb=False,
        )
        video_path = r[0] if isinstance(r, tuple) else r

    if not video_path or not os.path.exists(video_path):
        print(f"! Video not found: {video_path}")
        sys.exit(1)

    print(f"=== Upload as Part {part} (privacy={privacy}) ===")
    title, description, thumb = prepare(video_path, part)
    print(f"  - Title: {title}")

    creds = get_credentials()
    yt = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title, "description": description, "tags": DEFAULT_TAGS,
            "categoryId": "27", "defaultLanguage": "ja",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    # Non-resumable single-request upload (stays on www.googleapis.com; the
    # resumable flow redirects to a regional upload host that times out here).
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=False)
    print("  - Uploading (single request, please wait)...")
    resp = yt.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    vid = resp["id"]
    print(f"  - Uploaded: https://youtu.be/{vid}")

    if thumb and os.path.exists(thumb):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb)).execute()
            print("  - Thumbnail set")
        except Exception as e:
            print(f"  ! Thumbnail set failed: {e}")

    pid = _playlist_id()
    if pid:
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": pid,
                "resourceId": {"kind": "youtube#video", "videoId": vid},
            }}).execute()
            print(f"  - Added to playlist {pid}")
        except Exception as e:
            print(f"  ! Playlist add failed: {e}")

    bump_part(part)
    print(f"=== Done. Next part = {part + 1} ===")


if __name__ == "__main__":
    main()
