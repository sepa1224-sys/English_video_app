#!/bin/bash
# 絵コンテの各シーンからイラストを生成して output/ondoku/<id>/images/ に保存する
set -uo pipefail
ID="$1"
OUT="output/ondoku/$ID/images"
mkdir -p "$OUT"
N=$(python3 -c "import json;print(len(json.load(open('output/ondoku/${ID}_storyboard.json'))['scenes']))")
for i in $(seq 1 "$N"); do
  F=$(printf "%s/s%02d.png" "$OUT" "$i")
  if [ -s "$F" ]; then echo "  [$i/$N] スキップ（生成済み）"; continue; fi
  P=$(python3 -c "
import json;d=json.load(open('output/ondoku/${ID}_storyboard.json'))
print(d['scenes'][$i-1]['prompt_full'])")
  URL=$(higgsfield generate create z_image --prompt "$P" --aspect_ratio 16:9 --wait 2>&1 | grep -oE 'https://[^ ]+\.png' | tail -1)
  if [ -z "$URL" ]; then echo "  [$i/$N] ❌ 生成失敗"; continue; fi
  curl -sL -o "$F" "$URL"
  echo "  [$i/$N] ✅ $(basename "$F") $(du -h "$F" | cut -f1)"
done
echo "完了: $(ls -1 "$OUT"/*.png 2>/dev/null | wc -l | tr -d ' ') / $N 枚"
