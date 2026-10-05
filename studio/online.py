"""Your own studio online, free: `python -m studio online` (or `start.bat online` / `./start.sh online`).

Runs the website on this PC with a login, and opens a free Cloudflare "quick tunnel" so you get a public
https://<random-words>.trycloudflare.com link to use from your phone or any computer. No Cloudflare account,
no server to rent. It works while this PC and the start window are on; the link changes every time you start.

It's just for you: the first account (created on this PC at http://localhost) is the owner, and nobody can
sign up through the link. Your videos still use your own free tools (Claude Code on your plan, Kokoro, ...).
"""
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

from . import config

TUNNEL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

INSTALL = """The free online link needs Cloudflare's small `cloudflared` program (free, no account needed):
    Windows:        winget install --id Cloudflare.cloudflared
                    (then close this window and run start.bat online again)
    Debian/Ubuntu:  curl -L -o cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
                    sudo dpkg -i cloudflared.deb
    macOS:          brew install cloudflared
"""


def find_cloudflared():
    p = shutil.which("cloudflared")
    if p:
        return p
    if os.name == "nt":
        for c in (r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe"):
            if os.path.exists(c):
                return c
    return None


def url_file():
    return os.path.join(config.DATA_DIR, "online_url.txt")


def watch_tunnel(proc, on_url):
    """Read cloudflared's log until it prints the public link."""
    found = False
    for line in proc.stdout:
        m = TUNNEL_RE.search(line)
        if m and not found:
            found = True
            on_url(m.group(0))


def _die_with_parent():
    """Linux: stop cloudflared if this program is killed, so the link never outlives the studio."""
    try:
        import ctypes
        import signal
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)   # PR_SET_PDEATHSIG
    except Exception:
        pass


def start_tunnel(exe, port, on_url):
    extra = dict(preexec_fn=_die_with_parent) if sys.platform.startswith("linux") else {}
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            errors="replace", **extra)
    threading.Thread(target=watch_tunnel, args=(proc, on_url), daemon=True).start()
    return proc


def banner(url):
    line = "=" * 72
    print(f"\n{line}\n  Your Stickman Studio is online:\n\n      {url}\n\n"
          f"  Open it on your phone or any computer and log in. It works while this window is open.\n"
          f"  The link changes each time you start. Don't post it publicly.\n{line}\n", flush=True)


def wait_until_up(port, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main(port=None, open_browser=True):
    port = int(port or os.environ.get("PORT") or config.load_settings().get("port") or 8765)
    exe = find_cloudflared()
    if not exe:
        print(INSTALL)
        return 1
    # hosted mode, private: login required, one owner, no plans or payments
    os.environ["STUDIO_MODE"] = "hosted"
    os.environ["STUDIO_PRIVATE"] = "1"
    os.environ["STUDIO_BIND_HOST"] = "127.0.0.1"
    config.MODE = "hosted"
    config.ensure_dirs()
    try:
        os.remove(url_file())
    except OSError:
        pass

    def on_url(url):
        with open(url_file(), "w", encoding="utf-8") as f:
            f.write(url)
        banner(url)

    proc = start_tunnel(exe, port, on_url)

    def opener():
        if wait_until_up(port) and open_browser:
            from .hosted import accounts
            first = accounts.count_users() == 0
            if first:
                print("First time: create your owner account in the browser window that just opened.", flush=True)
            webbrowser.open(f"http://localhost:{port}/#/" + ("signup" if first else ""))
    threading.Thread(target=opener, daemon=True).start()
    print(f"Starting Stickman Studio online (this PC: http://localhost:{port}) ... getting your link from Cloudflare",
          flush=True)
    try:
        import uvicorn
        uvicorn.run("studio.server.app:app", host="127.0.0.1", port=port, log_level="warning")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            os.remove(url_file())
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
