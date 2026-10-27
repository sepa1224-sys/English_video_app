#!/bin/zsh
# 動画づくりの順番待ち。Mac が再起動しても launchd（com.kiai.video-queue）が最初から流し直す。
# どの段も「作り終えた・上げ終えた分は飛ばす」ので、何度動かしても同じ結果になる。毎朝3時にも流し直す（上限で上げ残した分）。
#   1. 稽古4〜10（tango_batch.sh）
#   2. 大学群の動画（GMARCH・早慶・関関同立・国公立大 × エクササイズ・聞き流し。上がったら公開）
#   3. 稽古1〜10 がそろったら、まとめ版（tango_after_batch.sh）
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
up() { python3 -c "import json,sys;d=json.load(open('data/tango_uploaded.json'));sys.exit(0 if '$1' in d else 1)"; }
log "順番待ちを始める"
scripts/tango_batch.sh 4 10 >> .tmp/tango_batch.log 2>&1
# ショート「3秒で意味言える？」Part.1〜10（上がったら公開。2026-10-27 坂本さん OK）
for n in $(seq 1 10); do
  name="shorts$n"
  if up $name; then python3 scripts/tango_publish.py $name >/dev/null 2>&1; continue; fi
  log "$name を作って上げる"
  python3 scripts/tango_shorts.py --part $n --upload >> .tmp/tango_shorts.log 2>&1 || { log "$name は失敗（次に流し直すとき続ける）"; break; }
  up $name && python3 scripts/tango_publish.py $name
done
for g in GMARCH 早慶 関関同立 国公立大; do
  for k in exercise listen; do
    name="group_$g"; [ $k = listen ] && name="${name}_listen"
    if up $name; then python3 scripts/tango_publish.py $name >/dev/null 2>&1; continue; fi
    log "$name を作って上げる"
    /usr/bin/caffeinate -i python3 scripts/tango_group.py $g --kind $k --upload >> .tmp/tango_group.log 2>&1 || log "$name は失敗（次に流し直すとき続ける）"
    up $name && { rm -f output/tango/$name.mp4; python3 scripts/tango_publish.py $name; }  # 上がったら公開（2026-10-26 坂本さん OK）
  done
done
up keiko10_listen && scripts/tango_after_batch.sh >> .tmp/tango_after.log 2>&1
# 単語帳の案内コメント（1日60件まで。2026-10-27 坂本さん「全部やろう」）
python3 scripts/add_book_link.py --apply >> .tmp/book_link.log 2>&1
python3 scripts/book_comment.py --apply --limit 60 >> .tmp/book_comment.log 2>&1
log "順番待ちおわり"
