@echo off
REM Stickman Studio launcher for Windows 10/11.
REM First run: creates .venv, installs Python packages, builds the dashboard if needed. Then opens the browser.
REM   start.bat          the studio on this computer (http://localhost:8765)
REM   start.bat online   the same, plus a free https link so you can use it from your phone (needs cloudflared)
setlocal
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is missing. Install it with:
  echo     winget install --id Gyan.FFmpeg -e
  echo Then close this window, open a NEW terminal and run start.bat again.
  pause
  exit /b 1
)

REM A deep folder (or one inside OneDrive) makes Windows file paths too long (260 characters) for some packages, and OneDrive
REM tries to sync the tens of thousands of files in .venv. Say so before anything is installed.
set "HERE=%cd%"
set "LONGCHK=%HERE%"
if not "%LONGCHK:~70,1%"=="" set "DEEP=1"
echo "%HERE%" | find /i "OneDrive" >nul && set "DEEP=1"
if defined DEEP (
  echo.
  echo NOTE: this folder is deep or inside OneDrive:
  echo     "%HERE%"
  echo Windows limits file paths to 260 characters and OneDrive tries to sync the .venv folder. If a package fails to
  echo install, or the studio is slow to start, move the whole folder to a short path such as C:\StickyAI and run start.bat there.
  echo.
)

set "PY=python"
where py >nul 2>nul
if not errorlevel 1 set "PY=py -3"

if not exist ".venv\Scripts\python.exe" (
  echo Creating the Python environment ^(.venv^)...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Python 3.11 or newer is required. Install it with:
    echo     winget install --id Python.Python.3.12 -e
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
  echo Python 3.11 or newer is required. Delete the .venv folder, install it with
  echo     winget install --id Python.Python.3.12 -e
  echo and run start.bat again.
  pause
  exit /b 1
)

fc /b requirements.txt .venv\installed-requirements.txt >nul 2>nul
if errorlevel 1 (
  echo Installing Python packages ^(first run takes a few minutes^)...
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Package install failed. Check the messages above.
    echo   - If they mention "Long Path" or "No such file or directory" with a very long file name, the folder is too deep:
    echo     move the studio to a short path such as C:\StickyAI, delete the .venv folder, and run start.bat again.
    echo   - If they mention "Application Control" or "blocked", see Troubleshooting in README.md.
    pause
    exit /b 1
  )
  copy /y requirements.txt .venv\installed-requirements.txt >nul
)

if not exist "web\dist\index.html" (
  where npm >nul 2>nul
  if not errorlevel 1 (
    echo Building the dashboard...
    pushd web
    call npm install --no-fund --no-audit
    call npm run build
    popd
  ) else (
    echo Note: web\dist is missing and npm isn't installed; the API will run but the dashboard won't.
  )
)

where claude >nul 2>nul
if errorlevel 1 echo Tip: the free writer uses Claude Code. Install it ^(npm install -g @anthropic-ai/claude-code^) and run "claude" once to log in.

for /f "delims=" %%p in ('python -c "from studio.config import load_settings; print(load_settings()['port'])"') do set "PORT=%%p"
if /i "%~1"=="online" (
  python -m studio online --port %PORT%
  pause
  exit /b
)
echo Stickman Studio: http://localhost:%PORT%   (close this window to stop)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%"
python -m studio serve --port %PORT%
