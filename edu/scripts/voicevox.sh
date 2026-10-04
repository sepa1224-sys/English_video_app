#!/bin/bash
# VOICEVOX ENGINE を起動する（声を作る前に一度だけ）。すでに動いていれば何もしない。
#   bash scripts/voicevox.sh
# エンジンは ~/tools/voicevox に置いてある（GitHub の VOICEVOX/voicevox_engine の macOS 版）。
URL="${VOICEVOX_URL:-http://127.0.0.1:50021}"
if curl -s "$URL/version" >/dev/null 2>&1; then
  echo "VOICEVOX ENGINE は起動済み（$(curl -s "$URL/version")）"
  exit 0
fi
RUN=$(find "$HOME/tools/voicevox" -maxdepth 3 -type f -name run -perm -u+x | head -1)
if [ -z "$RUN" ]; then
  echo "VOICEVOX ENGINE が見つかりません（~/tools/voicevox に展開してください）" >&2
  exit 1
fi
echo "起動します: $RUN"
nohup "$RUN" --host 127.0.0.1 --port 50021 > "$HOME/tools/voicevox/engine.log" 2>&1 &
# 立ち上がるまで待つ（初回はモデルの読み込みで30秒ほどかかる）
for i in $(seq 1 90); do
  if curl -s "$URL/version" >/dev/null 2>&1; then
    echo "VOICEVOX ENGINE 起動（$(curl -s "$URL/version")）"
    exit 0
  fi
  sleep 1
done
echo "起動に失敗しました。~/tools/voicevox/engine.log を見てください" >&2
exit 1
