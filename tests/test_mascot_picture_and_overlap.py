"""The mascot as a YouTube profile picture, and the rule that labels, signs and speech bubbles never cover a
character, their hat or their clothes."""
import io

import numpy as np
import pytest
from PIL import Image

from studio.engine.schema import check_scene, char_box
from studio.pipeline import mascot as M


# ------------------------------------------------------------------ profile picture
def test_profile_picture_is_a_square_png_of_the_requested_size():
    im = M.profile_picture({}, 300)
    assert im.size == (300, 300) and im.mode == "RGB"


def _non_background_rows(im):
    """Rows (top 4% of the image) that hold dark outline pixels: the hat running off the top edge would show up here."""
    a = np.asarray(im).astype(int)
    band = a[: max(2, int(a.shape[0] * 0.02))]
    return int(((band.sum(axis=2)) < 200).sum())


@pytest.mark.parametrize("kind", ["cap", "tophat", "crown", "wizard", "bearskin", "mitre"])
def test_profile_picture_fits_every_hat_inside_the_frame(kind):
    im = M.profile_picture({"mascot": {"kind": kind}}, 400)
    assert _non_background_rows(im) == 0, f"the {kind} is cut off at the top"


def test_profile_picture_shows_the_face_big():
    a = np.asarray(M.profile_picture({}, 400)).astype(int)
    face = (a[..., 0] > 240) & (a[..., 1] > 240) & (a[..., 2] > 225)      # the off-white face fill
    assert face.sum() / face.size > 0.09, "the head should fill a good part of the picture"


def test_profile_picture_follows_the_mascot_settings():
    red = np.asarray(M.profile_picture({}, 200)).astype(int)
    blue = np.asarray(M.profile_picture({"mascot": {"hat_color": "navy"}}, 200)).astype(int)
    assert not np.array_equal(red, blue)
    for backdrop in ("sunburst", "sky", "paper", "dark"):
        assert M.profile_picture({}, 120, backdrop).size == (120, 120)


def test_profile_picture_endpoint():
    from fastapi.testclient import TestClient
    from studio.server.app import app
    c = TestClient(app, base_url="http://localhost")
    r = c.get("/api/mascot/profile-picture?size=256&backdrop=sky")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert Image.open(io.BytesIO(r.content)).size == (256, 256)
    tiny = c.get("/api/mascot/profile-picture?size=5&backdrop=nope&download=true")
    assert tiny.status_code == 200
    assert Image.open(io.BytesIO(tiny.content)).size == (98, 98)            # YouTube's minimum
    assert "attachment" in tiny.headers["content-disposition"]


# ------------------------------------------------------------------ nothing covers a character
def _overlaps(box, a, b):
    return min(box[2], a[2]) > max(box[0], a[0]) and min(box[3], a[3]) > max(box[1], a[1])


def test_labels_and_signs_move_off_a_character():
    scene = {"bg": {"type": "paper"}, "elements": [
        {"type": "char", "kind": "wizard", "who": "Merlin", "x": 960, "y": 900, "scale": 1.0},
        {"type": "text", "text": "MERLIN", "x": 960, "y": 520, "size": 90, "at": 0.2},
        {"type": "sign", "text": "WIZARD", "x": 960, "y": 700}]}
    fixed, fixes, errs = check_scene(scene, "fun", "Merlin cast a spell.")
    assert not errs
    assert any("moved" in f for f in fixes)
    box = char_box(fixed["elements"][0])
    text, sign = fixed["elements"][1], fixed["elements"][2]
    assert text["y"] < box[1] + 40 or text["x"] < box[0] or text["x"] > box[2]
    assert sign["x"] < box[0] + 150 or sign["x"] > box[2] - 150


def test_speech_bubbles_stay_off_the_other_character():
    scene = {"bg": {"type": "paper"}, "elements": [
        {"type": "char", "kind": "wizard", "who": "Merlin", "x": 700, "y": 900, "scale": 1.0, "say": "Behold!"},
        {"type": "char", "kind": "tophat", "who": "Mr Top", "x": 1200, "y": 900, "scale": 1.0, "say": "Impressive."}]}
    fixed, fixes, errs = check_scene(scene, "fun", "Merlin cast a spell.")
    assert not errs
    chars = [e for e in fixed["elements"] if e["type"] == "char"]
    for b in (e for e in fixed["elements"] if e["type"] == "bubble"):
        for ch in chars:
            box = char_box(ch)
            assert not (box[0] < b["x"] < box[2] and box[1] < b["y"] < box[3]), (b, ch["who"])


def test_a_clean_scene_is_left_alone():
    scene = {"bg": {"type": "paper"}, "elements": [
        {"type": "char", "kind": "cap", "who": "A", "x": 700, "y": 900, "scale": 1.0},
        {"type": "text", "text": "1914", "x": 1400, "y": 300, "size": 120, "at": 0.2}]}
    fixed, fixes, errs = check_scene(scene, "fun", "In 1914 a war began.")
    assert not errs and not any("cover a character" in f for f in fixes)
    assert fixed["elements"][1]["x"] == 1400
