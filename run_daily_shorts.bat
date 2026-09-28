@echo off
REM Shorts: keep 7 days of scheduled 3-second-quiz Shorts (19:00 JST).
REM Generates more Shorts when stock runs low, then uploads with publishAt.
REM Register in Windows Task Scheduler (e.g. EnglishVideoApp_DailyShorts, 05:00).
REM Run on ONE machine only: data\shorts_ledger.json prevents double uploads per machine.
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
echo ==== %DATE% %TIME% : start >> "logs\shorts_schedule.log"
py shorts_schedule.py --auto-generate >> "logs\shorts_schedule.log" 2>&1
echo ==== %DATE% %TIME% : end (exit %ERRORLEVEL%) >> "logs\shorts_schedule.log"
