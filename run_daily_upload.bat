@echo off
REM Daily university listening video on a weekday rotation:
REM   Mon/Thu=todai, Tue/Fri=kyoto, Wed/Sat=osaka, Sun=skip.
REM Picks the university via daily_dispatch.py, then generate -> upload -> playlist.
REM Scheduled via Windows Task Scheduler (EnglishVideoApp_DailyUpload, 06:00).
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

for /f "delims=" %%u in ('py scripts\daily_dispatch.py') do set UNI=%%u

if "%UNI%"=="skip" (
  echo ==== %DATE% %TIME% : skip day (no upload) >> "logs\auto_upload.log"
  goto :eof
)

echo ==== %DATE% %TIME% : start (%UNI%) >> "logs\auto_upload.log"
py auto_upload.py --generate --university %UNI% >> "logs\auto_upload.log" 2>&1
echo ==== %DATE% %TIME% : end (exit %ERRORLEVEL%) >> "logs\auto_upload.log"

REM After upload: refresh dashboard status.json and redeploy
call "%~dp0scripts\update_dashboard.bat"
