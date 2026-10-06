"""Videos interrupted by a shutdown become resumable; progress keeps moving during long calls."""
import time

from studio.pipeline import new_project, recover_all, cancel, Project
from studio.pipeline.runner import Ctx


def test_interrupted_video_is_paused_and_deletable():
    pr = new_project("Interrupted", "topic", topic="Rome", options={"minutes": 1}, providers={"llm": "offline"})
    def f(m):
        m["status"] = "running"
        m["stages"]["storyboard"].update(status="running", progress=0.4)
    pr.update(f)
    assert recover_all() >= 1
    m = Project(pr.slug).meta()
    assert m["status"] == "paused" and m["stages"]["storyboard"]["status"] == "pending"
    # Stop on a video that isn't really running just unsticks it too
    pr.update(status="running")
    cancel(pr.slug)
    assert Project(pr.slug).meta()["status"] == "paused"
    from fastapi.testclient import TestClient
    from studio.server.app import app
    c = TestClient(app, base_url="http://localhost")
    assert c.delete(f"/api/projects/{pr.slug}", headers={"X-Studio": "1"}).status_code == 200


def test_progress_moves_while_waiting():
    pr = new_project("Heartbeat", "topic", topic="Rome", options={"minutes": 1}, providers={"llm": "offline"})
    ctx = Ctx(pr, "script")
    ctx.progress(0.05, "writing")
    with ctx.working("Claude is writing the script", expect=2, until=0.9):
        time.sleep(2.5)
    st = Project(pr.slug).meta()["stages"]["script"]
    assert st["progress"] > 0.3 and "(0:0" in st["message"]
    pr.delete()
