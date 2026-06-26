@echo off
REM Rebuild status.json and redeploy kiai-dashboard to Vercel.
REM Run standalone or called from run_daily_upload.bat.
set REPO=C:\Users\PC_User\english_video_app
set DASH=C:\Users\PC_User\kiai-dashboard
set LOG=%REPO%\logs\auto_upload.log
set PYTHONUTF8=1

cd /d "%REPO%"
echo ==== %DATE% %TIME% : dashboard build >> "%LOG%"
py scripts\build_status.py --out "%DASH%\public\status.json" >> "%LOG%" 2>&1

cd /d "%DASH%"
echo ==== %DATE% %TIME% : dashboard deploy >> "%LOG%"
call npx --yes vercel --prod --yes >> "%LOG%" 2>&1
echo ==== %DATE% %TIME% : dashboard done (exit %ERRORLEVEL%) >> "%LOG%"
