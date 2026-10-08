"""python -m studio doctor: is this PC ready to make videos? Every line says what is wrong and what to do about it.

Nothing is changed, nothing is sent anywhere, no key is ever printed (only which ones are set). Exit code 1 only when
something that stops the studio is wrong (a [FAIL]); warnings (a [warn]) are things worth knowing.
"""
import importlib
import os
import shutil
import socket
import subprocess
import sys

from . import config

OK, WARN, FAIL, INFO = "ok", "warn", "FAIL", "info"
TAG = {OK: "[ ok ]", WARN: "[warn]", FAIL: "[FAIL]", INFO: "[info]"}
REQUIRED = [("numpy", "numpy"), ("PIL", "pillow"), ("soundfile", "soundfile"), ("fastapi", "fastapi"), ("uvicorn", "uvicorn"),
            ("jsonschema", "jsonschema"), ("httpx", "httpx"), ("shapely", "shapely")]


def _first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def check_python():
    v = sys.version_info
    if v < (3, 10):
        return FAIL, "Python", f"{sys.version.split()[0]} is too old", "install Python 3.11 from python.org (tick 'Add to PATH'), then run start.bat again"
    if v >= (3, 13):
        return WARN, "Python", f"{sys.version.split()[0]}: newer than the studio was tested with (3.11)", "if something fails to install, use Python 3.11"
    return OK, "Python", sys.version.split()[0], ""


def check_location():
    root = config.ROOT
    notes = []
    if "onedrive" in root.lower():
        notes.append("inside OneDrive (it syncs the .venv and files can be locked or blocked)")
    if len(root) > 80:
        notes.append(f"a long path ({len(root)} characters; Windows stops at 260 and packages can fail to install)")
    if notes:
        return WARN, "Install folder", root + ": " + "; ".join(notes), "move the folder to something short outside OneDrive, like C:\\StickyAI, delete .venv, run start.bat"
    return OK, "Install folder", root, ""


def check_packages():
    missing = []
    for mod, pip_name in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception as e:                      # ImportError, or a DLL that Windows blocked
            missing.append(f"{pip_name} ({type(e).__name__})")
    if missing:
        return FAIL, "Python packages", "missing or blocked: " + ", ".join(missing), "run start.bat (it installs them), or: python -m pip install -r requirements.txt"
    return OK, "Python packages", f"{len(REQUIRED)} required packages load", ""


def check_dsp():
    try:
        from .engine import dsp
    except Exception as e:
        return FAIL, "Audio filters", f"could not load: {e}", "python -m pip install -r requirements.txt"
    if dsp.BACKEND == "scipy":
        return OK, "Audio filters", "scipy", ""
    return INFO, "Audio filters", f"using {dsp.BACKEND} (a Windows security policy blocked part of scipy)", "nothing to do: the studio has its own fallback, the sound is the same to the ear"


def check_ffmpeg():
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ff or not fp:
        return FAIL, "ffmpeg", "ffmpeg and ffprobe were not found on PATH", "Windows: winget install ffmpeg (then open a new window) | Debian/Ubuntu: sudo apt install ffmpeg | Mac: brew install ffmpeg"
    try:
        enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        enc = ""
    if "libx264" not in enc:
        return FAIL, "ffmpeg", "this ffmpeg has no libx264 encoder", "install a full build of ffmpeg (winget install ffmpeg)"
    return OK, "ffmpeg", _first_line(["ffmpeg", "-version"])[:70], ""


def check_encoders(deep):
    from .engine import encoders as EN
    if not deep:
        return INFO, "Graphics-card encoder", "skipped (--quick)", ""
    found = EN.detect(refresh=True)
    setting = config.load_settings().get("video_encoder", "cpu")
    if found:
        return INFO, "Graphics-card encoder", f"works here: {', '.join(found)} (Settings > Video encoder is '{setting}')", \
            "set Settings > Video encoder to 'auto' to use it (switching re-renders the scenes)" if setting == "cpu" else ""
    return INFO, "Graphics-card encoder", f"none works here, the CPU encodes (Settings > Video encoder is '{setting}')", ""


def check_disk():
    path = config.DATA_DIR if os.path.isdir(config.DATA_DIR) else config.ROOT
    free = shutil.disk_usage(path).free / 1e9
    if free < 1:
        return FAIL, "Disk space", f"{free:.1f} GB free", "free some space: a 10-minute video needs a few GB while it renders"
    if free < 8:
        return WARN, "Disk space", f"{free:.1f} GB free", "a 10-minute video needs a few GB while it renders"
    return OK, "Disk space", f"{free:.0f} GB free", ""


def check_writable():
    try:
        config.ensure_dirs()
        probe = os.path.join(config.DATA_DIR, ".doctor")
        with open(probe, "w") as f:
            f.write("x")
        os.remove(probe)
        os.makedirs(config.PROJECTS_DIR, exist_ok=True)
    except OSError as e:
        return FAIL, "Folders", f"cannot write to {config.DATA_DIR}: {e}", "pick a folder you own, or move the studio out of Program Files / a read-only drive"
    return OK, "Folders", f"data: {config.DATA_DIR}", ""


def check_web():
    idx = os.path.join(config.WEB_DIST, "index.html")
    if not os.path.isfile(idx):
        return FAIL, "Website files", "web/dist/index.html is missing", "download the studio again (the built website is part of the download), or: cd web && npm install && npm run build"
    return OK, "Website files", "built dashboard found", ""


def check_keys():
    try:
        st = config.secrets_status()
    except Exception as e:
        return WARN, "API keys", f"could not read: {e}", ""
    have = sorted(v["label"] for v in st.values() if v["set"])
    return INFO, "API keys", ("set: " + ", ".join(have)) if have else "none set: the free studio needs none", \
        "keys live only in the git-ignored .env file; add one only if you want that paid service"


def check_claude():
    if shutil.which("claude"):
        return OK, "Claude Code (the free writer)", _first_line(["claude", "--version"])[:60] or "found", ""
    return INFO, "Claude Code (the free writer)", "the 'claude' command was not found", "install Claude Code and sign in to write scripts on your plan, or use another writer in Settings"


def check_props():
    from .engine import prop_library as PL
    from .knowledge import propindex as PX
    st = PX.stats()
    if PL.ERRORS:
        return WARN, "Prop library", f"{st['shipped']} shipped + {st['drawn']} drawn; unreadable: {'; '.join(PL.ERRORS[:3])}", "delete or fix the files named in data/prop_library/"
    return OK, "Prop library", f"{st['builtin']} drawn in code, {st['shipped']} hand-drawn, {st['drawn']} drawn for earlier videos; {st['gaps']} objects wanted but missing", ""


def check_port():
    port = int(config.load_settings().get("port") or 8765)
    s = socket.socket()
    s.settimeout(0.3)
    try:
        busy = s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()
    if busy:
        return INFO, "Port", f"{port} is in use: the studio may already be running (open http://localhost:{port})", ""
    return OK, "Port", f"{port} is free", ""


def check_leftovers():
    n = 0
    for dp, _, files in os.walk(config.PROJECTS_DIR):
        n += sum(1 for f in files if f.endswith(".part.mp4"))
    if n:
        return INFO, "Unfinished renders", f"{n} half-written scene file(s) from an interrupted render", "harmless: the next Render redraws those scenes"
    return OK, "Unfinished renders", "none", ""


def run(deep=True, out=print):
    from . import providers as P
    checks = [check_python, check_location, check_packages, check_dsp, check_ffmpeg, lambda: check_encoders(deep), check_disk,
              check_writable, check_web, check_keys, check_claude, check_props, check_port, check_leftovers]
    rows, bad = [], 0
    for fn in checks:
        try:
            rows.append(fn())
        except Exception as e:                                # a broken check must not hide the others
            rows.append((WARN, getattr(fn, "__name__", "check"), f"could not run: {type(e).__name__}: {e}", ""))
    for status, name, detail, fix in rows:
        out(f"{TAG[status]} {name}: {detail}")
        if fix and status != OK:
            out(f"         -> {fix}")
        bad += status == FAIL
    out("")
    try:
        for stage, items in P.catalog().items():
            out(f"{P.STAGE_LABELS.get(stage, stage)}:")
            for p in items:
                out(f"  {'OK ' if p['available'] else '-- '} {p['label']}" + ("" if p["available"] else f"   ({p['reason']})"))
    except Exception as e:
        out(f"(could not list the providers: {e})")
    out("")
    out("Everything the studio needs is in place." if not bad else f"{bad} problem(s) stop the studio: fix the [FAIL] lines first.")
    return rows, bad
