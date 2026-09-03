@echo off
REM 「1日5分 英語で聞く教養」を1本つくり、翌朝7時の予約公開まで通す。
REM Windows タスクスケジューラで前夜(21:00)に実行する想定。
REM   タスク名の例: EnglishVideoApp_DailyKyoyo
REM 大学リスニング(run_daily_upload.bat)とは別枠。時間をずらして動かすこと。
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

if not exist "logs" mkdir "logs"

echo ==== %DATE% %TIME% : start kyoyo >> "logs\daily_kyoyo.log"
py ondoku_daily.py --publish-at 07:00 >> "logs\daily_kyoyo.log" 2>&1
set RC=%ERRORLEVEL%
echo ==== %DATE% %TIME% : end (exit %RC%) >> "logs\daily_kyoyo.log"

REM 失敗した日は、翌朝に公開される動画が無いことになる。
REM ログの末尾に理由が残るので、そこを見て手当てする。
if not "%RC%"=="0" echo !! 失敗しました。logs\daily_kyoyo.log を確認してください >> "logs\daily_kyoyo.log"
