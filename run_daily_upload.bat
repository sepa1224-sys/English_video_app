@echo off
REM Daily university listening video on a weekday rotation:
REM   Mon/Thu/Sun=todai, Tue/Fri=kyoto, Wed/Sat=osaka (no rest day).
REM Picks the university via daily_dispatch.py, then generate -> upload -> playlist.
REM Scheduled via Windows Task Scheduler (EnglishVideoApp_DailyUpload, 06:00).
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

for /f "delims=" %%u in ('py scripts\daily_dispatch.py') do set UNI=%%u

REM Use goto labels (NOT a parenthesized if-block): the literal "(" / ")" in log
REM messages would otherwise terminate an if(...) block early and break the script.
if "%UNI%"=="skip" goto skipday

echo ==== %DATE% %TIME% : start (%UNI%) >> "logs\auto_upload.log"
py auto_upload.py --generate --university %UNI% >> "logs\auto_upload.log" 2>&1
echo ==== %DATE% %TIME% : end (exit %ERRORLEVEL%) >> "logs\auto_upload.log"

REM After upload: refresh dashboard status.json and redeploy
call "%~dp0scripts\update_dashboard.bat"
goto :eof

:skipday
echo ==== %DATE% %TIME% : skip day (no upload) >> "logs\auto_upload.log"
