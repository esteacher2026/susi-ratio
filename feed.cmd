@echo off
rem Domestic feed uploader (run by Windows Task Scheduler every 30 min)
rem  1) collect jinhakapply universities only -> _feed\feed.json
rem  2) overwrite the single-file branch "jinhak-feed" and force-push
rem  -> the GitHub Actions workflow downloads and merges this file
setlocal
set ROOT=%~dp0
set FEED=%ROOT%_feed
set LOG=%ROOT%_feed.log
set PYTHONIOENCODING=utf-8
cd /d "%ROOT%"

if not exist "%FEED%\.git" (
  echo [feed] _feed clone missing >> "%LOG%"
  exit /b 1
)

python collect.py --vendor jinhakapply --out "%FEED%\feed.json" --workers 6 >> "%LOG%" 2>&1
if errorlevel 1 (
  echo [feed] collect failed >> "%LOG%"
  exit /b 1
)

cd /d "%FEED%"
git add feed.json
git -c user.name=esteacher2026 -c user.email=cnejinhak2025@gmail.com commit -q --amend -m "jinhak feed %date% %time%" >> "%LOG%" 2>&1
git push -q --force origin jinhak-feed >> "%LOG%" 2>&1
echo [feed] %date% %time% push exit=%errorlevel% >> "%LOG%"
endlocal
