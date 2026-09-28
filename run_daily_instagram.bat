@echo off
REM Post Shorts that went public on YouTube to Instagram Reels (@kiai_english).
REM Instagram API has no scheduled publish, so run this right after the YouTube slot.
REM Register in Windows Task Scheduler (e.g. EnglishVideoApp_InstagramReels, 19:10 JST).
REM Needs IG_USER_ID and IG_ACCESS_TOKEN in .env. Run on the same machine as run_daily_shorts.bat (shared ledger).
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
echo ==== %DATE% %TIME% : start >> "logs\instagram_reels.log"
py instagram_reels.py >> "logs\instagram_reels.log" 2>&1
echo ==== %DATE% %TIME% : end (exit %ERRORLEVEL%) >> "logs\instagram_reels.log"
