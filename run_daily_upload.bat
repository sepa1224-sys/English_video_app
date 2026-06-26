@echo off
REM Daily Todai listening video: generate -> upload (unlisted) -> playlist.
REM Scheduled via Windows Task Scheduler (EnglishVideoApp_DailyUpload, 06:00).
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
echo ==== %DATE% %TIME% : start >> "logs\auto_upload.log"
py auto_upload.py --generate >> "logs\auto_upload.log" 2>&1
echo ==== %DATE% %TIME% : end (exit %ERRORLEVEL%) >> "logs\auto_upload.log"

REM After upload: refresh dashboard status.json and redeploy
call "%~dp0scripts\update_dashboard.bat"
