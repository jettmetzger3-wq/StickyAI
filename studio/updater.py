"""python -m studio update: bring the studio files up to date without touching anything of yours.

Two ways, both safe for your videos:
  * a git checkout        `update` fetches the branch and fast-forwards it (never discards local changes);
  * a downloaded ZIP      `update --zip <the new branch ZIP>` copies the changed files over the install.

Never touched, never deleted: data/ (settings, caches, the prop library), projects/, .env (your keys), .venv/, venv/,
node_modules/. Nothing is ever deleted: a file that no longer exists in the new version stays where it is (harmless).
When requirements.txt changed the update says so and (unless --no-install) runs pip for you.
"""
import os
import posixpath
import subprocess
import sys
import zipfile

from . import config

KEEP = ("data", "projects", ".env", ".venv", "venv", "node_modules", ".git", "__pycache__")
MAX_UNPACKED = 600 * 1024 * 1024


class UpdateError(Exception):
    pass


def _top(names):
    """The single folder GitHub puts everything in ('StickyAI-claude-branch/'), or '' when the ZIP has none."""
    tops = {n.split("/", 1)[0] for n in names if n.strip("/")}
    if len(tops) == 1:
        only = next(iter(tops))
        if all(n == only + "/" or n.startswith(only + "/") for n in names):
            return only + "/"
    return ""


def _safe_target(root, rel):
    """The path inside `root` for a ZIP entry, or None when it would land outside it (a '..' trick) or in a kept folder."""
    rel = posixpath.normpath(rel.replace("\\", "/"))
    if rel.startswith(("/", "../")) or rel == ".." or ":" in rel.split("/")[0]:
        raise UpdateError(f"the ZIP has an unsafe path ({rel}); not applying it")
    if rel.split("/")[0] in KEEP:
        return None
    full = os.path.realpath(os.path.join(root, *rel.split("/")))
    if not full.startswith(os.path.realpath(root) + os.sep):
        raise UpdateError(f"the ZIP has an unsafe path ({rel}); not applying it")
    return full


def apply_zip(zip_path, root=None, dry_run=False):
    """Copy the files of a new version over the install at `root`. Returns dict(changed, added, same, kept, requirements,
    batch) with file lists; changes nothing when dry_run."""
    root = root or config.ROOT
    if not os.path.isfile(zip_path):
        raise UpdateError(f"{zip_path} is not a file")
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise UpdateError(f"{zip_path} is not a ZIP file")
    with z:
        infos = [i for i in z.infolist()]
        if sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise UpdateError("the ZIP is much bigger than the studio should be; not applying it")
        top = _top([i.filename for i in infos])
        if not any(i.filename[len(top):] == "studio/__init__.py" for i in infos):
            raise UpdateError("this ZIP does not look like Stickman Studio (no studio/__init__.py inside)")
        out = dict(changed=[], added=[], same=0, kept=[], requirements=False, batch=[])
        plan = []
        for i in infos:
            if i.is_dir():
                continue
            rel = i.filename[len(top):]
            if not rel:
                continue
            target = _safe_target(root, rel)
            if target is None:
                out["kept"].append(rel)
                continue
            data = z.read(i)
            if os.path.exists(target):
                with open(target, "rb") as f:
                    if f.read() == data:
                        out["same"] += 1
                        continue
                out["changed"].append(rel)
            else:
                out["added"].append(rel)
            if rel == "requirements.txt":
                out["requirements"] = True
            if rel.lower().endswith((".bat", ".cmd")):
                out["batch"].append(rel)
            plan.append((target, data))
        if not dry_run:
            for target, data in plan:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                tmp = target + ".new"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, target)
    return out


def git_update(root=None, check_only=False):
    """Fast-forward a git checkout. Returns a plain-text report. Refuses (says why) when it cannot be done without losing work."""
    root = root or config.ROOT

    def git(*a):
        r = subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr).strip()

    if not os.path.isdir(os.path.join(root, ".git")):
        raise UpdateError("this install is not a git checkout; download the new ZIP and run: python -m studio update --zip <file>")
    rc, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if rc != 0:
        raise UpdateError("git could not read this folder: " + branch[-200:])
    rc, out = git("fetch", "origin", branch)
    if rc != 0:
        raise UpdateError("could not reach the server: " + out[-200:])
    rc, counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{branch}")
    ahead, behind = (counts.split() + ["0", "0"])[:2] if rc == 0 else ("0", "0")
    if check_only:
        return f"branch {branch}: {behind} new change(s) available, {ahead} of yours not on the server"
    if int(behind) == 0:
        return f"already up to date (branch {branch})"
    rc, out = git("merge", "--ff-only", f"origin/{branch}")
    if rc != 0:
        raise UpdateError("could not fast-forward (you have changes of your own in the studio files). Nothing was changed. "
                          + out[-200:])
    return f"updated branch {branch}: {behind} change(s) applied"


def install_requirements(root=None):
    root = root or config.ROOT
    req = os.path.join(root, "requirements.txt")
    if not os.path.isfile(req):
        return True
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req])
    return r.returncode == 0
