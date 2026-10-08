"""python -m studio doctor and update: they tell the truth, never print a key, and never touch the user's own files."""
import os
import zipfile

import pytest

from studio import config, doctor, updater


# ---------------------------------------------------------------- doctor
def test_doctor_reports_every_check_and_counts_only_failures(monkeypatch):
    lines = []
    rows, bad = doctor.run(deep=False, out=lines.append)
    assert len(rows) >= 12 and all(len(r) == 4 and r[0] in (doctor.OK, doctor.WARN, doctor.FAIL, doctor.INFO) for r in rows)
    assert bad == sum(1 for r in rows if r[0] == doctor.FAIL)
    text = "\n".join(lines)
    assert "Prop library" in text and "Writer" in text and "Voice" in text


def test_doctor_never_prints_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "sk-this-is-a-secret-value-12345")
    lines = []
    doctor.run(deep=False, out=lines.append)
    assert "sk-this-is-a-secret-value-12345" not in "\n".join(lines)


def test_doctor_warns_about_onedrive_and_long_paths_and_fails_on_a_missing_package(monkeypatch):
    monkeypatch.setattr(config, "ROOT", "C:\\Users\\Someone\\OneDrive\\Desktop\\StickyAI\\StickyAI-claude-stickman-video-generator-ox3n1n")
    status, name, detail, fix = doctor.check_location()
    assert status == doctor.WARN and "OneDrive" in detail and "long path" in detail and "C:\\StickyAI" in fix
    real = doctor.importlib.import_module

    def fake(name, *a, **k):
        if name == "numpy":
            raise ImportError("DLL load failed: blocked")
        return real(name, *a, **k)
    monkeypatch.setattr(doctor.importlib, "import_module", fake)
    status, name, detail, fix = doctor.check_packages()
    assert status == doctor.FAIL and "numpy" in detail and "start.bat" in fix


def test_doctor_checks_that_cannot_run_do_not_hide_the_others(monkeypatch):
    monkeypatch.setattr(doctor, "check_disk", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    rows, bad = doctor.run(deep=False, out=lambda m: None)
    assert any("could not run" in r[2] for r in rows) and len(rows) >= 12


# ---------------------------------------------------------------- update
def make_zip(path, entries, top="StickyAI-claude-branch/"):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr((top or "") + name, data)
    return str(path)


@pytest.fixture
def install(tmp_path):
    root = tmp_path / "StickyAI"
    files = {"studio/__init__.py": b"", "studio/a.py": b"old = 1\n", "studio/same.py": b"same\n", "start.bat": b"@echo off\r\nold\r\n",
             "requirements.txt": b"numpy\n", "data/settings.json": b'{"mine": true}', ".env": b"ANTHROPIC_API_KEY=keep-me\n",
             "projects/video/meta.json": b'{"title": "my video"}'}
    for rel, data in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    return root


NEW = {"studio/__init__.py": b"", "studio/a.py": b"new = 2\n", "studio/b.py": b"added\n", "studio/same.py": b"same\n",
       "start.bat": b"@echo off\r\nnew\r\n", "requirements.txt": b"numpy\npillow\n", "data/settings.json": b'{"theirs": 1}',
       ".env": b"ANTHROPIC_API_KEY=overwritten\n", "projects/video/meta.json": b"{}"}


def test_update_from_a_zip_changes_studio_files_and_never_your_own(tmp_path, install):
    z = make_zip(tmp_path / "new.zip", NEW)
    check = updater.apply_zip(z, str(install), dry_run=True)
    assert sorted(check["changed"]) == ["requirements.txt", "start.bat", "studio/a.py"] and check["added"] == ["studio/b.py"]
    assert (install / "studio/a.py").read_bytes() == b"old = 1\n"                      # a dry run changes nothing
    r = updater.apply_zip(z, str(install))
    assert r["same"] == 2 and r["requirements"] and r["batch"] == ["start.bat"]
    assert (install / "studio/a.py").read_bytes() == b"new = 2\n" and (install / "studio/b.py").read_bytes() == b"added\n"
    assert (install / "start.bat").read_bytes() == b"@echo off\r\nnew\r\n"             # line endings kept exactly
    assert (install / "data/settings.json").read_bytes() == b'{"mine": true}'
    assert (install / ".env").read_bytes() == b"ANTHROPIC_API_KEY=keep-me\n"
    assert (install / "projects/video/meta.json").read_bytes() == b'{"title": "my video"}'
    assert {"data/settings.json", ".env", "projects/video/meta.json"} <= set(r["kept"])
    assert not [p for p in install.rglob("*.new")]                                      # no temp files left
    assert updater.apply_zip(z, str(install))["changed"] == []                          # running it again is a no-op


def test_a_zip_without_the_top_folder_works_too(tmp_path, install):
    z = make_zip(tmp_path / "flat.zip", NEW, top="")
    assert updater.apply_zip(z, str(install))["changed"]
    assert (install / "studio/a.py").read_bytes() == b"new = 2\n"


def test_nothing_is_written_when_the_zip_is_unsafe_or_not_the_studio(tmp_path, install):
    bad = make_zip(tmp_path / "evil.zip", dict(NEW, **{"../evil.txt": b"x"}))
    with pytest.raises(updater.UpdateError):
        updater.apply_zip(bad, str(install))
    assert (install / "studio/a.py").read_bytes() == b"old = 1\n" and not (tmp_path / "evil.txt").exists()
    other = make_zip(tmp_path / "other.zip", {"readme.md": b"hi"})
    with pytest.raises(updater.UpdateError, match="does not look like Stickman Studio"):
        updater.apply_zip(other, str(install))
    notzip = tmp_path / "x.zip"
    notzip.write_bytes(b"not a zip")
    with pytest.raises(updater.UpdateError):
        updater.apply_zip(str(notzip), str(install))
    with pytest.raises(updater.UpdateError):
        updater.apply_zip(str(tmp_path / "missing.zip"), str(install))


def test_a_folder_that_is_not_a_git_checkout_says_how_to_update(tmp_path):
    with pytest.raises(updater.UpdateError, match="--zip"):
        updater.git_update(str(tmp_path))


def test_the_update_command_prints_a_plain_report(tmp_path, install, capsys):
    from studio import __main__ as M
    z = make_zip(tmp_path / "new.zip", NEW)
    a = type("A", (), dict(zip=z, check=True, no_install=True))()
    assert M.cmd_update(a) == 0
    out = capsys.readouterr().out
    assert "would change" in out or "updated" in out
    a = type("A", (), dict(zip=str(tmp_path / "nope.zip"), check=False, no_install=True))()
    assert M.cmd_update(a) == 1 and "Could not update" in capsys.readouterr().out
