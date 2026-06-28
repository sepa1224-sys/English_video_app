#!/usr/bin/env python3
"""
daily_dispatch.py
今日(JST)アップすべき大学を1語で出力する。毎日アップ・曜日ローテ:
  月/木/日 = todai, 火/金 = kyoto, 水/土 = osaka
（日曜は最も再生が伸びている東大を追加スロットに。休みなし）
run_daily_upload.bat から呼ばれ、結果を auto_upload.py の --university に渡す。
"""
import datetime

JST = datetime.timezone(datetime.timedelta(hours=9))
wd = datetime.datetime.now(JST).weekday()  # Mon=0 ... Sun=6
ROTATION = {0: "todai", 3: "todai", 6: "todai", 1: "kyoto", 4: "kyoto", 2: "osaka", 5: "osaka"}
print(ROTATION.get(wd, "skip"))
