#!/bin/zsh
# 「イメージで英単語エクササイズ」と「英単語 聞き流し」を、稽古ごとに作って非公開で上げる。
#   scripts/tango_batch.sh 2 10      … 稽古2〜10
# セッションが切れても止まらないよう launchd で動かす：
#   launchctl submit -l com.kiai.tango.batch -- /bin/zsh -lc "cd <repo> && scripts/tango_batch.sh 2 10 >> .tmp/tango_batch.log 2>&1; launchctl remove com.kiai.tango.batch"
# 作り終えた動画・上げ終えた動画は飛ばすので、止まったら同じコマンドで続きから動く。
# YouTube の上限（1日に6本ほど）に達したら上げるのは飛ばして作るほうを続ける。上げ残しは翌日もう一度動かせば上がる。
cd "$(dirname "$0")/.."
from=${1:-2}; to=${2:-10}
export PYTHONUNBUFFERED=1
log() { echo "[$(date '+%m-%d %H:%M')] $*"; }
for k in $(seq $from $to); do
  for kind in exercise listen; do
    for try in 1 2; do  # 書き出しが止まったら（ディスク不足など）1分待って1回だけやり直す。できた区切りは使い回す
      log "稽古$k $kind を作る（$try 回目）"
      if /usr/bin/caffeinate -i python3 tango_exercise.py $k --kind $kind; then break; fi
      log "稽古$k $kind の作成に失敗"; sleep 60
    done
    log "稽古$k $kind を非公開で上げる"
    python3 tango_exercise.py $k --kind $kind --upload --privacy private 2>&1 | grep -v "アップロード [0-9]"
  done
done
log "おわり"
