"""Measure every prop's bounding box at scale 1 and write prop_bounds.json.

Run after adding or changing a prop:  python -m studio.engine.measure_props
"""
import json

from .doodle import SS
from .pen import Pen
from .registry import PROPS, BOUNDS_FILE

AX, AY = 960, 760


def measure(name):
    anchor, fn, _ = PROPS[name]
    p = Pen(1, rgba=True)
    fn(p, AX, AY, 1.0, None, {})
    bb = p.im.getchannel("A").getbbox()
    if not bb:
        return None
    x0, y0, x1, y1 = (v / SS for v in bb)
    return [round(x0 - AX, 1), round(y0 - AY, 1), round(x1 - AX, 1), round(y1 - AY, 1)]


def main():
    out = {}
    for name in sorted(PROPS):
        b = measure(name)
        if b:
            out[name] = b
            print(f"{name:16s} {b}")
    with open(BOUNDS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("wrote", BOUNDS_FILE)


if __name__ == "__main__":
    main()
