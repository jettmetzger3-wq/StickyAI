"""The free studio starts and works without the paid-provider packages (they are in requirements-paid.txt), and a missing one
says exactly what to install. (On Windows the elevenlabs package can fail to install when the folder is deep: paths over 260.)"""
import os
import re
import subprocess
import sys

import pytest

from studio import providers as P
from studio.providers import base

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAID = ("anthropic", "elevenlabs", "higgsfield-client", "stripe")


def names(path):
    out = []
    for line in open(os.path.join(ROOT, path), encoding="utf-8").read().splitlines():
        line = line.split("#")[0].strip()
        if line:
            out.append(re.split(r"[<>=\[ ;]", line)[0].lower())
    return out


def test_the_default_install_has_no_paid_packages_and_the_paid_file_has_them_all():
    core, paid = names("requirements.txt"), names("requirements-paid.txt")
    assert not [p for p in PAID if p in core]
    assert sorted(paid) == sorted(PAID)
    assert "fastapi" in core and "scipy" in core and "kokoro-onnx" in core          # the free studio is all there
    dock = open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8").read()
    assert "requirements-paid.txt" in dock                                          # the hosted image still gets them


def test_a_missing_paid_package_says_what_to_install(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "x")
    monkeypatch.setattr(base.importlib.util, "find_spec", lambda name, *a, **k: None if name == "elevenlabs" else object())
    for stage in ("voice", "music", "image", "transcript"):
        pv = [p for p in P.REGISTRY[stage] if "elevenlabs" in p.id]
        assert pv, stage
        ok, why = pv[0].available()
        assert not ok and "elevenlabs" in why and "requirements-paid.txt" in why and "C:" in why, (stage, why)


def test_the_hint_for_other_packages_is_a_plain_pip_install():
    assert base.pip_hint("faster_whisper").endswith("pip install faster-whisper")
    assert "requirements-paid.txt" in base.pip_hint("stripe")


def test_the_studio_imports_and_lists_every_provider_with_the_paid_packages_missing():
    prog = """
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in ("elevenlabs", "anthropic", "stripe", "higgsfield_client"):
            raise ImportError("No module named " + name)
sys.meta_path.insert(0, Block())
import studio.server.app
from studio import providers as P
n = sum(len(v) for v in P.REGISTRY.values())
print("providers", n, P.catalog() is not None)
"""
    r = subprocess.run([sys.executable, "-c", prog], cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0 and "providers" in r.stdout, r.stderr[-600:]


def test_start_bat_keeps_windows_line_endings_and_warns_about_deep_or_onedrive_folders():
    raw = open(os.path.join(ROOT, "start.bat"), "rb").read()
    assert raw.count(b"\r\n") == raw.count(b"\n")                                   # every line ends CR LF (batch files need it)
    text = raw.decode("utf-8")
    assert "OneDrive" in text and "C:\\StickyAI" in text and "Long Path" in text
