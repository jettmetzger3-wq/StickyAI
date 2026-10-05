#!/usr/bin/env bash
# Stickman Studio launcher for Linux (Debian/Ubuntu) and macOS.
# First run: creates .venv, installs Python packages, builds the dashboard if needed. Then opens the browser.
#   ./start.sh          the studio on this computer (http://localhost:8765)
#   ./start.sh online   the same, plus a free https link so you can use it from your phone (needs cloudflared)
set -e
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is missing. Install it with:"
  echo "    sudo apt install ffmpeg        (Debian/Ubuntu)"
  echo "    brew install ffmpeg            (macOS)"
  exit 1
fi

PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
  echo "Python 3.11 or newer is required (found: $("$PY" --version 2>&1))."
  echo "    sudo apt install python3 python3-venv"
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  echo "Creating the Python environment (.venv)..."
  "$PY" -m venv .venv || { echo "Could not create a venv. Try: sudo apt install python3-venv"; exit 1; }
fi
# shellcheck disable=SC1091
. .venv/bin/activate

if ! cmp -s requirements.txt .venv/.installed-requirements.txt; then
  echo "Installing Python packages (first run takes a few minutes)..."
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt
  cp requirements.txt .venv/.installed-requirements.txt
fi

if [ ! -f web/dist/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Building the dashboard..."
    (cd web && npm install --no-fund --no-audit && npm run build)
  else
    echo "Note: web/dist is missing and npm isn't installed; the API will run but the dashboard won't."
  fi
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "Tip: the free writer uses Claude Code. Install it (npm install -g @anthropic-ai/claude-code) and run 'claude' once to log in."
fi

PORT="$(python -c 'from studio.config import load_settings; print(load_settings()["port"])')"
if [ "${1:-}" = "online" ]; then
  exec python -m studio online --port "$PORT"
fi
URL="http://localhost:${PORT}"
echo "Stickman Studio: ${URL}   (Ctrl+C to stop)"
( sleep 2; (command -v xdg-open >/dev/null && xdg-open "$URL") || (command -v open >/dev/null && open "$URL") ) >/dev/null 2>&1 &
exec python -m studio serve --port "$PORT"
