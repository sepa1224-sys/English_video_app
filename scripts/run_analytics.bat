@echo off
REM Run the YouTube Analytics deep-dive and save the report to logs.
REM Triggered by a one-time Windows scheduled task (EnglishVideoApp_Analytics_0701).
cd /d "C:\Users\PC_User\english_video_app"
set PYTHONUTF8=1
py scripts\analytics_report.py > "logs\analytics_report_latest.txt" 2>&1
