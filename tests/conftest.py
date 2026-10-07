import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# keep tests away from your real projects/settings
_tmp = tempfile.mkdtemp(prefix="studio_test_")
os.environ.setdefault("STUDIO_DATA_DIR", os.path.join(_tmp, "data"))
os.environ.setdefault("STUDIO_PROJECTS_DIR", os.path.join(_tmp, "projects"))


import pytest


@pytest.fixture(autouse=True)
def strict_composer(monkeypatch):
    """A bug in a scene layout must fail a test, not quietly fall back to another scene."""
    from studio.knowledge import composer
    monkeypatch.setattr(composer, "STRICT", True)
