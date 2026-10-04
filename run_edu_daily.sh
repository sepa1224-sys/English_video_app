#!/bin/zsh
# 解説ショートの毎日の仕事（launchd から呼ぶ）
#   make … 毎朝 1本作って承認待ちに送る
#   sync … 承認済みを YouTube に予約投稿（1時間おき）
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
case "$1" in
  make) python3 edu_make.py ;;
  sync) python3 sns_youtube_sync.py ;;
  *) echo "usage: run_edu_daily.sh make|sync"; exit 1 ;;
esac
