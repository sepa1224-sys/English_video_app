#!/bin/zsh
# 稽古1〜10 がそろったら、まとめ版（1〜5・6〜10・1〜10 の通し）を作って上げ、公開する。
# 2026-10-25 坂本さん「稽古1-10の通し動画」「基本的に全て収益オン」。上げる上限（1日6本ほど）に当たったら6時間おきにやり直す。
#   launchctl submit -l com.kiai.tango.after -- /bin/zsh -lc "cd ~/English_video_app && scripts/tango_after_batch.sh >> .tmp/tango_after.log 2>&1; launchctl remove com.kiai.tango.after"
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
up() { python3 -c "import json,sys;d=json.load(open('data/tango_uploaded.json'));sys.exit(0 if '$1' in d else 1)"; }
until up keiko10_listen && ! launchctl list | grep -q com.kiai.tango.batch; do sleep 1800; done
log "稽古10までそろった。まとめ版を作る"
jobs=("1 5 exercise" "6 10 exercise" "1 5 listen" "6 10 listen" "1 10 exercise" "1 10 listen")
while true; do
  left=0
  for j in $jobs; do
    set -- ${=j}; name="compile$1-$2"; [ "$3" = listen ] && name="${name}_listen"
    up $name && continue
    left=1
    log "$name を作って上げる"
    if /usr/bin/caffeinate -i python3 scripts/tango_compile.py $1 $2 --kind $3; then
      rm -f output/tango/$name.mp4
      python3 scripts/tango_publish.py $name
    else
      log "$name は失敗（上限なら6時間後にやり直す）"; break
    fi
  done
  [ $left = 0 ] && { log "おわり"; break; }
  up compile1-10_listen || sleep 21600
done
