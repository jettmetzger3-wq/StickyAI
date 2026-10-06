"""Hats sit on the stickman's head: no background showing between head and hat, and the speech-bubble math
knows how tall each hat is."""
import math

import pytest

from studio.engine.pen import Pen, HATS, HAT_TOP, SS, hat_top
from studio.engine.schema import say_bubbles

X, FY, S = 300, 760, 1.0
HY = FY - 300 * S                       # head center for a standing stickman
OPEN = ("none", "civ", "glasses", "japan", "headband", "laurel", "headphones")


def drawn(kind, flip=False):
    p = Pen(1, rgba=True, size=(600, 800))
    p.stick(X, FY, S, kind, flip=flip, shadow=False)
    return p.im.getchannel("A")


def column_alpha(alpha, y0, y1, x=X):
    return [alpha.getpixel((int(x * SS), int(y * SS))) for y in range(int(y0), int(y1))]


@pytest.mark.parametrize("kind", [h for h in HATS if h not in OPEN])
@pytest.mark.parametrize("flip", [False, True])
def test_hat_covers_head_top_without_gap(kind, flip):
    a = drawn(kind, flip)
    # from just inside the head's top edge (64 units above its center) to just above it: all painted, no see-through
    gaps = [v for v in column_alpha(a, HY - 72 * S, HY - 58 * S) if v < 200]
    assert not gaps, f"{kind}: background shows between head and hat"


@pytest.mark.parametrize("kind", [h for h in HATS if h not in OPEN])
@pytest.mark.parametrize("f", [1, -1])
def test_hat_wraps_the_top_of_the_skull(kind, f):
    """Drawn alone, the hat must cover the head's outline from the crown down to the forehead (40 degrees either
    side of the top), so it fits around the head instead of perching on it."""
    p = Pen(1, rgba=True, size=(600, 800))
    p._hat(kind, X, HY, 64 * S, S, f)
    a = p.im.getchannel("A")
    bare = []
    for deg in range(-40, 41, 5):
        r = math.radians(deg)
        px, py = X + 64 * S * math.sin(r), HY - 64 * S * math.cos(r)
        if a.getpixel((int(px * SS), int(py * SS))) < 200:
            bare.append(deg)
    assert not bare, f"{kind}: head outline shows at {bare} degrees"


@pytest.mark.parametrize("kind", [h for h in HATS if h != "none"])
def test_hat_top_table_matches_drawing(kind):
    a = drawn(kind)
    top = a.getbbox()[1] / SS
    want = HY - hat_top(kind) * S
    assert abs(top - want) < 16, f"{kind}: drawn top {top:.0f}, table says {want:.0f}"


def test_every_hat_has_a_height():
    missing = [h for h in HATS if h not in HAT_TOP and h not in OPEN and h != "astronaut"]
    assert not missing


def test_bubble_tip_clears_tall_hats():
    from studio.engine.compiler import bubble_size
    for kind in ("wizard", "bearskin", "tophat", "pirate", "viking", "army"):
        el = {"type": "char", "kind": kind, "x": 900, "y": 950, "scale": 0.9}
        b = say_bubbles(el, "Forward!", safe=(0, 0, 1920, 1080))[0]
        bottom = b["y"] + bubble_size(b)[1] / 2
        tip = bottom + b["tail"][1] if isinstance(b["tail"], list) else bottom
        assert tip < 950 - (300 + hat_top(kind)) * 0.9, kind
