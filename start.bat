@echo off
REM Stickman Studio launcher for Windows 10/11.
REM First run: creates .venv, installs Python packages, builds the dashboard if needed. Then opens the browser.
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
    echo Package install failed. Check the messages above.
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
echo Stickman Studio: http://localhost:%PORT%   (close this window to stop)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%"
python -m studio serve --port %PORT%
