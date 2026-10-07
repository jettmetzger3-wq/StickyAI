"""Places where things happen: a building going up, a working factory, a real battlefield, a farm, a mine, a
classroom, parliament, a courtroom, a prison cell, a market, an army camp and a laboratory.

When the narration says "he built a factory", the whole screen becomes the construction site (scaffolding, a tower
crane lowering steel, walls rising brick by brick while the scene plays) instead of a small factory prop on a plain
page. Each paint_* draws the full background the way core.bg_* do; the busy places also add a few moving parts
that sit behind the characters: the crane's load, the rising walls, hammering workers, chimney smoke, a running
conveyor belt, turning gears, a flickering campfire, bubbling flasks.
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw

from .doodle import W, H, SS
from .palette import INK, WHITE, darker, lighter
from .pen import Pen
from .places import far_prop, _facade

BG_Z = -1.3          # moving parts of a background: above the painted background, below every element


def _rgba(w, h):
    return Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))


def _finish(p, w, h):
    return p.im.convert("RGBa").resize((int(w), int(h)), Image.LANCZOS).convert("RGBA")


def _sprite(draw, w, h, seed=1):
    p = Pen(seed, rgba=True, size=(w, h))
    draw(p)
    return _finish(p, w, h)


def _paste(canvas, im, x, y):
    canvas.alpha_composite(im, (int(x), int(y))) if (0 <= x and 0 <= y and x + im.width <= canvas.width
                                                     and y + im.height <= canvas.height) \
        else canvas.paste(im, (int(x), int(y)), im)


def _ease(q):
    q = min(max(q, 0.0), 1.0)
    return q * q * (3 - 2 * q)


def _moving(sc, frame, box, z=BG_Z):
    """A background part whose picture comes from frame(t) (t = seconds into the scene)."""
    return sc.fx(frame, box, enter=None, at=0.0, edur=0, sfx=None, z=z)


def _looping(sc, draw, box, period, fps=12, z=BG_Z):
    """A small looping drawing (a hammering worker, a flickering fire): draw(pen, t) on a box-sized canvas."""
    return sc.dynamic(draw, box, None, 0.0, edur=0, sfx=None, z=z, fps=fps, period=period)


# ------------------------------------------------------------------ smoke plumes (chimneys, burning villages)
_PUFFS = {}


def _puff(kind):
    if kind not in _PUFFS:
        col, line = {"black": ((92, 90, 96), (64, 62, 68)), "gray": ((150, 150, 156), (112, 112, 120)),
                     "white": ((236, 236, 240), (176, 176, 186)), "steam": ((246, 246, 250), (200, 204, 214))}[kind]

        def draw(p):
            for cx, cy, r in ((52, 70, 34), (84, 58, 40), (116, 72, 32), (76, 86, 36), (104, 90, 30)):
                p.circ(cx, cy, r, col, 4, line)
        _PUFFS[kind] = _sprite(draw, 168, 130, seed=5)
    return _PUFFS[kind]


class Plume:
    """Smoke rising from (x, y): puffs grow, drift with the wind and fade, in a seamless loop."""

    def __init__(self, x, y, kind="black", size=1.0, height=420, wind=60, n=7, period=6.0, seed=1, start=0.0):
        self.x, self.y, self.kind, self.size, self.start = x, y, kind, size, start
        self.height, self.wind, self.n, self.period = height, wind, n, period
        r = random.Random(seed)
        self.offs = [r.uniform(-0.4, 0.4) for _ in range(n)]
        self.box = (int(x - 140 * size - abs(wind) * 0.2), int(y - height - 150 * size),
                    int(280 * size + abs(wind) * 1.4), int(height + 200 * size))

    def frame(self, t):
        x0, y0, w, h = self.box
        cv = _rgba(w, h)
        base = _puff(self.kind)
        t -= self.start
        if t < 0:
            return cv
        for k in range(self.n):
            q = ((t / self.period) + k / self.n) % 1.0
            if self.start > 0 and t < self.period and q > t / self.period:
                continue                     # the first puffs are only just leaving the chimney
            k_size = self.size * (0.35 + 1.0 * q)
            a = min(1.0, q * 6) * (1 - q) ** 0.8
            if a < 0.03:
                continue
            im = base.resize((max(1, int(base.width * k_size)), max(1, int(base.height * k_size))), Image.BILINEAR)
            im.putalpha(im.getchannel("A").point(lambda v, a=a: int(v * a)))
            cx = self.x + self.wind * q ** 1.4 + self.offs[k] * 40 * q - x0
            cy = self.y - self.height * q - y0
            _paste(cv, im, cx - im.width / 2, cy - im.height / 2)
        return cv


def plume(sc, x, y, kind="black", size=1.0, height=420, wind=60, seed=1, z=BG_Z, start=0.0):
    pl = Plume(x, y, kind, size, height, wind, seed=seed + sc.idx, start=start)
    _moving(sc, pl.frame, pl.box, z)


# ------------------------------------------------------------------ construction site
BUILD_WHAT = ("factory", "house", "tower", "castle", "wall", "ship")
BUILD_ALIASES = {"plant": "factory", "mill": "factory", "works": "factory", "foundry": "factory",
                 "steelworks": "factory", "warehouse": "factory", "home": "house", "cottage": "house",
                 "church": "house", "school": "house", "skyscraper": "tower", "office": "tower", "hotel": "tower",
                 "apartment": "tower", "fort": "castle", "fortress": "castle", "palace": "castle",
                 "cathedral": "castle", "great_wall": "wall", "walls": "wall", "dam": "wall", "boat": "ship",
                 "warship": "ship", "battleship": "ship", "titanic": "ship", "liner": "ship", "galleon": "ship"}

BRICK = (182, 86, 62)
STEEL = (92, 108, 134)
CRANE = (244, 190, 40)


def norm_what(v):
    k = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    k = BUILD_ALIASES.get(k, k)
    return k if k in BUILD_WHAT else "factory"


def build_progress(v):
    """How much is built at the start and the end of the scene, as fractions of the full height."""
    if v in ("done", "finished", "complete", True):
        return 1.0, 1.0
    if isinstance(v, (int, float)):
        f = min(max(float(v), 0.0), 1.0)
        return f, f
    if isinstance(v, (list, tuple)) and len(v) == 2:
        try:
            a, b = (min(max(float(x), 0.0), 1.0) for x in v)
            return a, b
        except (TypeError, ValueError):
            pass
    return 0.3, 0.85


def _bricks(p, x0, y0, x1, y1, col=BRICK, bw=44, bh=18):
    """A brick wall in rect (x0, y0)-(x1, y1): fill, mortar lines and staggered joints."""
    p.d.rectangle([int(x0 * SS), int(y0 * SS), int(x1 * SS), int(y1 * SS)], fill=col)
    mortar = lighter(col, 0.35)
    r = random.Random(int(x0 * 3 + y0))
    row = 0
    y = y1
    while y > y0:
        yt = max(y0, y - bh)
        p.d.line([int(x0 * SS), int(yt * SS), int(x1 * SS), int(yt * SS)], fill=mortar, width=2 * SS)
        off = (bw / 2) * (row % 2)
        x = x0 - off
        while x < x1:
            if x > x0:
                p.d.line([int(x * SS), int(yt * SS), int(x * SS), int(y * SS)], fill=mortar, width=2 * SS)
            if r.random() < 0.12 and y - yt > 6:     # a few darker bricks so it doesn't look printed
                xa, xb = max(x0, x) + 2, min(x1, x + bw) - 2
                if xb > xa:
                    p.d.rectangle([int(xa * SS), int((yt + 2) * SS), int(xb * SS), int((y - 2) * SS)],
                                  fill=darker(col, 0.86))
            x += bw
        y -= bh
        row += 1


def _stones(p, x0, y0, x1, y1, col=(196, 186, 166)):
    p.d.rectangle([int(x0 * SS), int(y0 * SS), int(x1 * SS), int(y1 * SS)], fill=col)
    r = random.Random(int(x0 + y0 * 7))
    y = y1
    while y > y0:
        bh = r.randint(34, 46)
        yt = max(y0, y - bh)
        p.d.line([int(x0 * SS), int(yt * SS), int(x1 * SS), int(yt * SS)], fill=darker(col, 0.7), width=3 * SS)
        x = x0 - r.randint(0, 60)
        while x < x1:
            w = r.randint(60, 110)
            if x > x0:
                p.d.line([int(x * SS), int(yt * SS), int(x * SS), int(y * SS)], fill=darker(col, 0.7), width=3 * SS)
            if r.random() < 0.25 and y - yt > 10:
                xa, xb = max(x0, x) + 4, min(x1, x + w) - 4
                if xb > xa:
                    p.d.rectangle([int(xa * SS), int((yt + 4) * SS), int(xb * SS), int((y - 4) * SS)],
                                  fill=lighter(col, 0.12) if r.random() < 0.5 else darker(col, 0.92))
            x += w
        y -= bh


def _planks(p, x0, y0, x1, y1, col=(196, 150, 100), bh=26):
    p.d.rectangle([int(x0 * SS), int(y0 * SS), int(x1 * SS), int(y1 * SS)], fill=col)
    y = y1
    while y > y0:
        p.d.line([int(x0 * SS), int(y * SS), int(x1 * SS), int(y * SS)], fill=darker(col, 0.72), width=3 * SS)
        y -= bh


def _window(p, x, y, w, h, arch=False, night=False, lit=False):
    glass = (255, 222, 140) if lit else ((54, 66, 96) if night else (120, 150, 178))
    if arch:
        p.d.rectangle([int(x * SS), int((y + w / 2) * SS), int((x + w) * SS), int((y + h) * SS)], fill=glass)
        p.d.pieslice([int(x * SS), int(y * SS), int((x + w) * SS), int((y + w) * SS)], 180, 360, fill=glass)
        p.d.arc([int(x * SS), int(y * SS), int((x + w) * SS), int((y + w) * SS)], 180, 360, fill=INK, width=4 * SS)
        p.line([(x, y + w / 2), (x, y + h), (x + w, y + h), (x + w, y + w / 2)], 4, INK, 0.2)
        p.line([(x + w / 2, y + 4), (x + w / 2, y + h)], 3, darker(glass, 0.6), 0.1)
        for k in range(1, 3):
            yy = y + w / 2 + (h - w / 2) * k / 3
            p.line([(x, yy), (x + w, yy)], 3, darker(glass, 0.6), 0.1)
    else:
        p.rect(x, y, w, h, glass, 4)
        p.line([(x + w / 2, y), (x + w / 2, y + h)], 3, darker(glass, 0.6), 0.1)
        p.line([(x, y + h / 2), (x + w, y + h / 2)], 3, darker(glass, 0.6), 0.1)


class Building:
    """What is being built: the drawing of the finished part that rises (walls, roof) and the frame or skeleton
    that stands from the start (steel, timber, ribs)."""

    def __init__(self, what, gy):
        self.what, self.gy = what, gy
        if what == "factory":
            self.x0, self.x1, self.top = 360, 1340, gy - 430
            self.roof = 100         # sawtooth roof height above the walls
            self.chimney = (1385, 1455, 150)
        elif what == "house":
            self.x0, self.x1, self.top, self.roof, self.chimney = 560, 1300, gy - 330, 190, None
        elif what == "tower":
            self.x0, self.x1, self.top, self.roof, self.chimney = 700, 1180, 130, 0, None
        elif what == "castle":
            self.x0, self.x1, self.top, self.roof, self.chimney = 500, 1360, gy - 400, 0, None
        elif what == "wall":
            self.x0, self.x1, self.top, self.roof, self.chimney = 120, 1520, gy - 250, 0, None
        else:  # ship on the slipway
            self.x0, self.x1, self.top, self.roof, self.chimney = 380, 1420, gy - 360, 0, None
        tops = [self.top - self.roof] + ([self.chimney[2]] if self.chimney else [])
        if what == "castle":
            tops.append(self.top - 110)
        self.y_min = min(tops) - 10
        self.box = (self.x0 - 80, self.y_min, self.x1 - self.x0 + 160 + (140 if self.chimney else 0),
                    gy + 6 - self.y_min)

    def bays(self):
        n = max(2, int(round((self.x1 - self.x0) / 136)))
        return [self.x0 + (self.x1 - self.x0) * i / n for i in range(n + 1)]

    # ----- the frame that stands from the start
    def skeleton(self, p):
        gy, top = self.gy, self.top
        if self.what in ("factory", "tower"):
            cols = self.bays()
            floors = list(range(int(gy), int(top) - 1, -(int((gy - top) / max(1, round((gy - top) / 130))))))
            for x in cols:
                p.rect(x - 9, top, 18, gy - top, STEEL, 4)
            for y in floors[1:] + [top]:
                p.rect(self.x0 - 6, y - 8, self.x1 - self.x0 + 12, 16, STEEL, 4)
            for a, b in zip(cols, cols[1:]):        # cross bracing in the end bays
                if a in (cols[0], cols[-2]):
                    p.line([(a + 9, top + 8), (b - 9, gy)], 5, darker(STEEL, 0.8), 0.2)
                    p.line([(b - 9, top + 8), (a + 9, gy)], 5, darker(STEEL, 0.8), 0.2)
            if self.what == "factory":
                n = 4
                tw = (self.x1 - self.x0) / n
                for i in range(n):
                    xa = self.x0 + i * tw
                    p.line([(xa, top), (xa + tw * 0.75, top - self.roof), (xa + tw, top)], 7, STEEL, 0.2)
                    p.line([(xa + tw * 0.75, top - self.roof), (xa + tw * 0.75, top)], 5, STEEL, 0.2)
        elif self.what == "house":
            for x in self.bays():
                p.rect(x - 7, top, 14, gy - top, (176, 130, 84), 4)
            p.rect(self.x0 - 8, top - 10, self.x1 - self.x0 + 16, 16, (176, 130, 84), 4)
            cx = (self.x0 + self.x1) / 2
            p.line([(self.x0 - 30, top), (cx, top - self.roof), (self.x1 + 30, top)], 8, (176, 130, 84), 0.2)
            for k in range(1, 6):
                xa = self.x0 + (cx - self.x0) * k / 6
                p.line([(xa, top), (xa, top - self.roof * k / 6)], 5, (176, 130, 84), 0.2)
                xb = self.x1 - (self.x1 - cx) * k / 6
                p.line([(xb, top), (xb, top - self.roof * k / 6)], 5, (176, 130, 84), 0.2)
        elif self.what == "ship":
            # keel blocks and the ribs of the hull
            for x in range(int(self.x0) + 60, int(self.x1) - 40, 70):
                p.rect(x - 16, gy - 40, 32, 40, (130, 96, 64), 4)
            for k, x in enumerate(range(int(self.x0) + 90, int(self.x1) - 60, 64)):
                yb = self._keel(x)
                p.line([(x, top + 10), (x + 6, (top + yb) / 2), (x + 2, yb)], 6, (150, 104, 66), 0.3)

    def _keel(self, x):
        """Bottom of the ship's hull at x (bow on the right rises)."""
        u = (x - self.x0) / (self.x1 - self.x0)
        return self.gy - 40 - (max(0.0, u - 0.8) / 0.2) ** 2 * 170 - (max(0.0, 0.08 - u) / 0.08) ** 1.5 * 120

    # ----- the finished part that rises
    def finished(self, p, night=False):
        x0, x1, top, gy = self.x0, self.x1, self.top, self.gy
        r = random.Random(7)
        if self.what == "factory":
            _bricks(p, x0, top, x1, gy)
            cols = self.bays()
            for a, b in zip(cols, cols[1:]):
                w = (b - a) * 0.46
                for yy in (top + 50, top + 220):
                    if yy + 130 < gy - 10:
                        _window(p, (a + b) / 2 - w / 2, yy, w, 130, arch=True, night=night, lit=night and r.random() < .4)
            p.rect(x0, top, x1 - x0, gy - top, None, 6)
            n = 4
            tw = (x1 - x0) / n
            for i in range(n):         # sawtooth roof: glass on the steep side
                xa = x0 + i * tw
                p.poly([(xa, top), (xa + tw * 0.75, top - self.roof), (xa + tw * 0.75, top)], (110, 104, 104), 5)
                p.poly([(xa + tw * 0.75, top - self.roof), (xa + tw, top), (xa + tw * 0.75, top)], (150, 186, 210), 5)
            cx0, cx1, ctop = self.chimney
            _bricks(p, cx0, ctop, cx1, gy, darker(BRICK, 0.92), bw=24, bh=14)
            p.rect(cx0, ctop, cx1 - cx0, gy - ctop, None, 5)
            p.rect(cx0 - 8, ctop - 6, cx1 - cx0 + 16, 20, darker(BRICK, 0.7), 5)
            p.rect((x0 + x1) / 2 - 70, gy - 170, 140, 170, (90, 70, 60), 5)
            p.line([((x0 + x1) / 2, gy - 170), ((x0 + x1) / 2, gy)], 4, INK, 0.2)
        elif self.what == "house":
            _planks(p, x0, top, x1, gy, (226, 196, 146))
            for wx in (x0 + 70, x1 - 190):
                _window(p, wx, top + 70, 120, 110, night=night, lit=night)
            p.rect((x0 + x1) / 2 - 50, gy - 170, 100, 170, (140, 84, 56), 5)
            p.rect(x0, top, x1 - x0, gy - top, None, 6)
            cx = (x0 + x1) / 2
            p.poly([(x0 - 40, top + 6), (cx, top - self.roof), (x1 + 40, top + 6)], (180, 72, 56), 6)
            for k in range(1, 5):
                yy = top + 6 - (self.roof + 6) * k / 5
                half = (x1 - x0 + 80) / 2 * (1 - k / 5)
                p.line([(cx - half, yy), (cx + half, yy)], 3, darker((180, 72, 56), 0.75), 0.2)
        elif self.what == "tower":
            panel = (150, 186, 214) if not night else (60, 74, 110)
            p.d.rectangle([int(x0 * SS), int(top * SS), int(x1 * SS), int(gy * SS)], fill=panel)
            for x in self.bays():
                p.line([(x, top), (x, gy)], 6, (70, 80, 96), 0.1)
            y = gy
            while y > top:
                p.line([(x0, y), (x1, y)], 5, (70, 80, 96), 0.1)
                for x in np.arange(x0 + 20, x1 - 20, 34):
                    if night and r.random() < 0.35:
                        p.d.rectangle([int(x * SS), int((y - 40) * SS), int((x + 22) * SS), int((y - 12) * SS)],
                                      fill=(255, 222, 140))
                y -= 52
            p.rect(x0, top, x1 - x0, gy - top, None, 6)
        elif self.what in ("castle", "wall"):
            col = (196, 186, 166) if self.what == "castle" else (206, 190, 160)
            _stones(p, x0, top, x1, gy, col)
            merl = 46
            for x in np.arange(x0, x1 - merl / 2, merl * 2):
                p.rect(x, top - 40, merl, 42, col, 5)
            p.rect(x0, top, x1 - x0, gy - top, None, 6)
            if self.what == "castle":
                for tx in (x0 - 40, x1 - 140):
                    _stones(p, tx, top - 110, tx + 180, gy, darker(col, 0.95))
                    p.rect(tx, top - 110, 180, gy - top + 110, None, 6)
                    for x in np.arange(tx, tx + 180 - 20, 60):
                        p.rect(x, top - 150, 34, 42, darker(col, 0.95), 5)
                    p.rect(tx + 70, top - 40, 40, 70, (40, 40, 52), 4, r=18)
                gx = (x0 + x1) / 2
                p.rect(gx - 90, gy - 200, 180, 200, (80, 62, 50), 6, r=80)
                for k in range(1, 5):
                    p.line([(gx - 90 + 36 * k, gy - 196), (gx - 90 + 36 * k, gy)], 4, INK, 0.2)
        else:  # ship hull, plated from the keel up
            pts_top = [(x, top + 8 * math.sin((x - x0) / (x1 - x0) * math.pi)) for x in np.linspace(x0, x1, 24)]
            pts_bot = [(x, self._keel(x)) for x in np.linspace(x1, x0, 24)]
            p.poly(pts_top + [(x1 + 60, top - 30)] + pts_bot, (60, 64, 74), 6)
            y_line = top + 120
            p.line([(x0 + 10, y_line), (x1 + 20, y_line - 10)], 8, (200, 60, 50), 0.2)
            for x in np.arange(x0 + 120, x1 - 80, 90):
                p.circ(x, top + 60, 14, (200, 214, 226), 4)
            for x in np.arange(x0 + 60, x1, 120):
                p.line([(x, top + 12), (x + 4, self._keel(x) - 6)], 2, (90, 94, 104), 0.2)


class RisingWalls:
    """The finished drawing revealed from the ground up: a ragged top edge of bricks or stones climbing."""

    def __init__(self, bld, prog, dur, night=False):
        self.bld = bld
        self.a, self.b = prog
        self.dur = max(0.1, dur)
        x0, y0, w, h = bld.box
        p = Pen(3, rgba=True, size=(w, h))
        # draw in box coordinates
        p_off = _OffsetPen(p, x0, y0)
        bld.finished(p_off, night)
        self.full = _finish(p, w, h)
        self.alpha = np.asarray(self.full.getchannel("A")).astype(np.uint8)
        self.h = h
        self.last = (None, None)
        # ragged edge: each column of bricks stops a little higher or lower
        cols = np.arange(w)
        self.ragged = (((cols // 44) % 2) * 18).astype(np.int32)

    def height_at(self, t):
        q = _ease(t / self.dur)
        return self.a + (self.b - self.a) * q

    def frame(self, t):
        f = self.height_at(t)
        if f >= 0.999:
            return self.full
        tall = self.bld.gy - self.bld.y_min
        cut = int(round(self.h - 6 - tall * f))       # rows above `cut` are not built yet
        cut = cut - cut % 4
        if self.last[0] == cut:
            return self.last[1]
        rows = np.arange(self.h)[:, None]
        keep = rows >= (cut + self.ragged[None, :])
        a = np.where(keep, self.alpha, 0).astype(np.uint8)
        im = self.full.copy()
        im.putalpha(Image.fromarray(a, "L"))
        self.last = (cut, im)
        return im

    def top_y(self, t):
        """Screen y of the top of the wall at time t (where the crane drops its load)."""
        f = self.height_at(t)
        return self.bld.gy - (self.bld.gy - self.bld.y_min) * f


class _OffsetPen:
    """Draws with screen coordinates onto a pen whose canvas starts at (x0, y0)."""

    def __init__(self, p, x0, y0):
        self.p, self.x0, self.y0 = p, x0, y0
        self.d = _OffsetDraw(p.d, x0 * SS, y0 * SS)

    def _pt(self, pts):
        return [(x - self.x0, y - self.y0) for x, y in pts]

    def line(self, pts, w=6, col=INK, wob=1.5):
        self.p.line(self._pt(pts), w, col, wob)

    def poly(self, pts, fill=None, w=6, col=INK, wob=1.5, close=True):
        self.p.poly(self._pt(pts), fill, w, col, wob, close)

    def rect(self, x, y, w_, h_, fill=None, w=6, col=INK, r=0):
        self.p.rect(x - self.x0, y - self.y0, w_, h_, fill, w, col, r)

    def circ(self, x, y, r, fill=None, w=6, col=INK):
        self.p.circ(x - self.x0, y - self.y0, r, fill, w, col)

    def ell(self, x, y, rx, ry, fill=None, w=6, col=INK):
        self.p.ell(x - self.x0, y - self.y0, rx, ry, fill, w, col)


class _OffsetDraw:
    def __init__(self, d, ox, oy):
        self.d, self.ox, self.oy = d, ox, oy

    def _b(self, box):
        return [box[0] - self.ox, box[1] - self.oy, box[2] - self.ox, box[3] - self.oy]

    def rectangle(self, box, **kw):
        self.d.rectangle(self._b(box), **kw)

    def line(self, xy, **kw):
        pts = [(xy[i] - self.ox, xy[i + 1] - self.oy) for i in range(0, len(xy), 2)] if not isinstance(xy[0], tuple) \
            else [(x - self.ox, y - self.oy) for x, y in xy]
        self.d.line(pts, **kw)

    def pieslice(self, box, a0, a1, **kw):
        self.d.pieslice(self._b(box), a0, a1, **kw)

    def arc(self, box, a0, a1, **kw):
        self.d.arc(self._b(box), a0, a1, **kw)


def _crane(p, mast_x, gy, jib_y, jib_x0, jib_x1):
    """A yellow tower crane: lattice mast, jib with a counter-jib and weights, the operator's cab."""
    hw = 26
    p.rect(mast_x - 60, gy - 30, 120, 34, (140, 140, 150), 4)
    p.line([(mast_x - hw, gy - 30), (mast_x - hw, jib_y + 30)], 7, CRANE, 0.1)
    p.line([(mast_x + hw, gy - 30), (mast_x + hw, jib_y + 30)], 7, CRANE, 0.1)
    y, k = gy - 30, 0
    while y > jib_y + 40:
        y2 = max(jib_y + 30, y - 52)
        p.line([(mast_x - hw if k % 2 == 0 else mast_x + hw, y), (mast_x + hw if k % 2 == 0 else mast_x - hw, y2)],
               4, darker(CRANE, 0.8), 0.1)
        p.line([(mast_x - hw, y2), (mast_x + hw, y2)], 3, darker(CRANE, 0.8), 0.1)
        y, k = y2, k + 1
    # jib (a long triangular truss) and counter-jib
    p.line([(jib_x0, jib_y), (jib_x1, jib_y)], 8, CRANE, 0.1)
    p.line([(jib_x0 + 30, jib_y + 26), (mast_x, jib_y + 26)], 6, CRANE, 0.1)
    x, k = jib_x0 + 30, 0
    while x < mast_x - 20:
        p.line([(x, jib_y + 26), (x + 30, jib_y)], 3, darker(CRANE, 0.8), 0.1)
        p.line([(x + 30, jib_y), (x + 60, jib_y + 26)], 3, darker(CRANE, 0.8), 0.1)
        x += 60
    p.line([(mast_x, jib_y - 110), (jib_x0 + 60, jib_y)], 3, (90, 90, 100), 0.1)
    p.line([(mast_x, jib_y - 110), (jib_x1 - 10, jib_y)], 3, (90, 90, 100), 0.1)
    p.poly([(mast_x - 22, jib_y), (mast_x, jib_y - 112), (mast_x + 22, jib_y)], None, 6, CRANE, 0.1)
    p.rect(jib_x1 - 110, jib_y + 4, 90, 70, (150, 150, 158), 5)
    for k in range(3):
        p.line([(jib_x1 - 110, jib_y + 26 + k * 18), (jib_x1 - 20, jib_y + 26 + k * 18)], 2, (110, 110, 120), 0.1)
    p.rect(mast_x - 70, jib_y + 26, 56, 52, (250, 246, 236), 5)
    p.rect(mast_x - 62, jib_y + 34, 40, 26, (150, 196, 226), 3)


def _scaffold(p, x0, x1, gy, top, levels=None):
    """Poles, planks, braces and a ladder in front of a wall from x0 to x1, up to `top`."""
    pole = (128, 132, 142)
    bay = 96
    xs = list(np.arange(x0, x1 + 1, bay))
    levels = levels or list(np.arange(gy - 120, top - 1, -120))
    for x in xs:
        p.line([(x, gy + 2), (x, top - 30)], 6, pole, 0.2)
    for y in levels:
        p.line([(xs[0] - 10, y + 22), (xs[-1] + 10, y + 22)], 5, pole, 0.2)
        p.rect(xs[0] - 6, y, xs[-1] - xs[0] + 12, 16, (196, 150, 96), 4)
    for a, b in zip(xs, xs[1:]):
        p.line([(a, gy), (b, levels[-1] + 22 if levels else top)], 3, pole, 0.3)
    lx = xs[0] + 30
    p.line([(lx, gy), (lx, levels[0])], 4, (150, 110, 70), 0.2)
    p.line([(lx + 26, gy), (lx + 26, levels[0])], 4, (150, 110, 70), 0.2)
    for y in np.arange(gy - 20, levels[0], -24):
        p.line([(lx, y), (lx + 26, y)], 3, (150, 110, 70), 0.1)
    return levels


def _worker(x, y, s=0.34, kind="hardhat", tool="hammer", flip=False, phase=0.0):
    """A small looping hammering (or digging) worker: draw(pen, t) for sc.dynamic, feet at the box's bottom."""
    w, h = 220 * s * 3, 520 * s * 1.25

    def draw(p, t):
        ph = ((t + phase) % 0.5) / 0.5
        up = ph < 0.55
        if tool == "hammer":
            arms = ((20, 15), (150, 40)) if up else ((20, 15), (72, -36))
        else:
            arms = ((120, 30), (120, 30)) if up else ((55, -30), (55, -30))
        p.stick(w / 2, h - 4, s, kind, arms=arms, mouth="flat", flip=flip, shadow=False, prop=tool,
                lean=(0 if up or tool == "hammer" else 10 * (-1 if flip else 1)))
    return draw, (x - w / 2, y - h + 4, w, h)


def _beam_sprite():
    def draw(p):
        p.rect(6, 6, 300, 16, (170, 70, 52), 4)
        p.rect(6, 30, 300, 16, (170, 70, 52), 4)
        p.rect(20, 18, 272, 16, (140, 56, 44), 3)
    return _sprite(draw, 312, 54, seed=9)


def _pallet_sprite():
    def draw(p):
        p.rect(4, 60, 150, 14, (170, 124, 80), 4)
        for row in range(3):
            for k in range(3):
                p.rect(8 + k * 48 + (row % 2) * 12, 40 - row * 18, 42, 18, BRICK, 3)
    return _sprite(draw, 168, 80, seed=11)


def _hook_sprite():
    def draw(p):
        p.rect(4, 4, 40, 30, (70, 70, 80), 4)
        p.d.arc([12 * SS, 30 * SS, 40 * SS, 58 * SS], 300, 200, fill=INK, width=5 * SS)
    return _sprite(draw, 48, 62, seed=13)


class CraneLoad:
    """The trolley runs along the jib, the hook picks up steel beams (or bricks) from the pile at the crane's foot,
    carries them over the building and lowers them onto the rising walls, then goes back for the next one."""

    PERIOD = 12.0

    def __init__(self, jib_y, x_pick, x_drop, y_pick, walls, bld_what):
        self.jib_y, self.x_pick, self.x_drop, self.y_pick = jib_y, x_pick, x_drop, y_pick
        self.walls = walls
        self.load = _beam_sprite() if bld_what in ("factory", "tower", "ship") else _pallet_sprite()
        self.hook = _hook_sprite()
        self.trolley = _sprite(lambda p: (p.rect(4, 4, 70, 22, (90, 90, 100), 4), p.circ(20, 30, 8, INK, 0),
                                          p.circ(58, 30, 8, INK, 0)), 78, 42, seed=15)
        x0 = min(x_pick, x_drop) - 180
        x1 = max(x_pick, x_drop) + 180
        self.box = (int(x0), int(jib_y - 6), int(x1 - x0), int(y_pick + 60 - jib_y + 6))

    def state(self, t):
        q = t % self.PERIOD
        hi = self.jib_y + 110
        drop = max(hi + 40, min(self.walls.top_y(t) - 40, self.y_pick - 40)) if self.walls else self.y_pick - 200
        keys = [(0.0, self.x_pick, self.y_pick, True), (2.0, self.x_pick, hi, True), (5.0, self.x_drop, hi, True),
                (7.0, self.x_drop, drop, True), (7.8, self.x_drop, drop, False), (9.0, self.x_drop, hi, False),
                (11.0, self.x_pick, hi, False), (12.0, self.x_pick, self.y_pick, False)]
        for (t0, xa, ya, la), (t1, xb, yb, lb) in zip(keys, keys[1:]):
            if t0 <= q <= t1:
                u = _ease((q - t0) / (t1 - t0))
                return xa + (xb - xa) * u, ya + (yb - ya) * u, la, (t0 >= 2.0 and t1 <= 7.0)
        return self.x_pick, self.y_pick, False, False

    def frame(self, t):
        x0, y0, w, h = self.box
        cv = _rgba(w, h)
        x, y, loaded, swinging = self.state(t)
        sway = 10 * math.sin(t * 2.6) if swinging else 0
        d = ImageDraw.Draw(cv)
        tx, hx = x - x0, x - x0 + sway
        d.line([(tx - 6, self.jib_y + 14 - y0), (hx - 6, y - y0)], fill=(40, 40, 46), width=3)
        d.line([(tx + 6, self.jib_y + 14 - y0), (hx + 6, y - y0)], fill=(40, 40, 46), width=3)
        _paste(cv, self.trolley, tx - 39, self.jib_y - 2 - y0)
        _paste(cv, self.hook, hx - 24, y - y0)
        if loaded:
            for dx in (-60, 60):
                d.line([(hx, y + 52 - y0), (hx + dx, y + 92 - y0)], fill=(40, 40, 46), width=2)
            _paste(cv, self.load, hx - self.load.width / 2, y + 86 - y0)
        return cv


def paint_construction(sc, bg):
    """A construction site: the frame stands, the crane works and the walls rise during the scene."""
    what = norm_what(bg.get("what"))
    time = bg.get("time") or "day"
    night = time == "night"
    gy = 770
    bld = Building(what, gy)
    with sc.background((214, 236, 250)) as p:
        sc._sky(p, time, gy)
        haze = (196, 210, 226) if not night else (46, 54, 86)
        # the town behind the site
        r = random.Random(sc.idx + 71)
        x = -30
        while x < W:
            w_, h_ = r.randint(80, 150), r.randint(80, 200)
            p.d.rectangle([int(x * SS), int((gy - 40 - h_) * SS), int((x + w_) * SS), int((gy - 30) * SS)],
                          fill=darker(haze, 0.86))
            x += w_ + r.randint(0, 30)
        if what == "ship":
            p.d.rectangle([int(1500 * SS), int((gy - 60) * SS), int(W * SS), int(gy * SS)], fill=(92, 152, 200))
        dirt = (190, 156, 112) if not night else (80, 70, 60)
        sc._ground(p, None, gy - 40, dirt)
        for _ in range(9):                     # tire ruts and puddles
            yy = r.randint(gy + 40, H - 40)
            xx = r.randint(0, W)
            p.line([(xx, yy), (xx + r.randint(120, 260), yy + r.randint(-10, 10))], 4, darker(dirt, 0.8), 0.6)
        for _ in range(3):
            p.ell(r.randint(100, W - 100), r.randint(gy + 60, H - 60), r.randint(50, 90), r.randint(10, 18),
                  (150, 170, 190) if not night else (60, 70, 96), 0)
        # site fence (striped barriers)
        for bx in (40, 1660):
            p.rect(bx, gy - 70, 220, 26, WHITE, 4)
            for k in range(5):
                p.poly([(bx + 10 + k * 44, gy - 70), (bx + 32 + k * 44, gy - 70), (bx + 12 + k * 44, gy - 44),
                        (bx - 10 + k * 44, gy - 44)], (226, 60, 50), 0, wob=0)
            p.line([(bx + 20, gy - 44), (bx + 20, gy - 6)], 5, INK, 0.2)
            p.line([(bx + 200, gy - 44), (bx + 200, gy - 6)], 5, INK, 0.2)
        bld.skeleton(p)
        jib_y = max(56, min(170, bld.y_min - 70))
        mast_x = 1650 if what != "wall" else 1720
        _crane(p, mast_x, gy, jib_y, max(300, bld.x0 - 40), min(W - 10, mast_x + 300))
        # supplies at the crane's feet and around the site
        for k in range(4):
            p.rect(1460 + (k % 2) * 8, gy - 22 - k * 16, 170, 14, (170, 70, 52), 3)
        p.rect(240, gy - 6, 150, 50, (170, 124, 80), 4)
        for row in range(3):
            for k in range(3):
                p.rect(246 + k * 48 + (row % 2) * 10, gy - 22 - row * 18, 42, 18, BRICK, 3)
        # site cabin, sand pile, cement mixer
        p.rect(30, gy - 190, 250, 150, (236, 236, 226), 5)
        p.rect(30, gy - 204, 250, 20, (90, 110, 140), 4)
        _window(p, 60, gy - 160, 80, 60, night=night, lit=night)
        p.rect(190, gy - 150, 60, 110, (90, 110, 140), 4)
        p.poly([(1500, gy + 60), (1580, gy - 10), (1640, gy - 20), (1730, gy + 60)], (226, 196, 132), 5)
        mx = 1790
        p.circ(mx - 40, gy + 64, 16, INK, 0)
        p.circ(mx + 40, gy + 64, 16, INK, 0)
        p.line([(mx - 70, gy + 44), (mx + 70, gy + 44)], 7, (110, 110, 120), 0.2)
        p.line([(mx, gy + 44), (mx - 10, gy - 20)], 7, (110, 110, 120), 0.2)
        drum = [(mx - 60 + 50 * math.cos(a) * 1.15 - 20 * math.sin(a), gy - 40 + 50 * math.sin(a) * 0.9)
                for a in np.linspace(0, 2 * math.pi, 20)]
        p.poly(drum, (236, 128, 50), 5)
        p.ell(mx - 108, gy - 70, 16, 26, (60, 60, 66), 4)
        for k in range(3):
            p.line([(mx - 90 + k * 26, gy - 84), (mx - 70 + k * 26, gy + 4)], 3, darker((236, 128, 50), 0.8), 0.2)
    prog = build_progress(bg.get("progress"))
    walls = RisingWalls(bld, prog, sc.dur, night)
    _moving(sc, walls.frame, bld.box, z=BG_Z)
    # scaffolding in front of the rising walls, with workers on it
    with sc.layer(None, 0.0, sfx=None, z=BG_Z + 0.05) as p:
        if what in ("factory", "house", "castle", "tower"):
            top = bld.top if what != "tower" else bld.top + 60
            lv = _scaffold(p, bld.x0 - 50, bld.x0 + 190, gy, top)
            rv = _scaffold(p, bld.x1 - 190, bld.x1 + 50, gy, top)
            spots = [(bld.x0 + 90, lv[0]), (bld.x1 - 60, rv[min(1, len(rv) - 1)])]
        elif what == "wall":
            lv = _scaffold(p, bld.x0 + 300, bld.x0 + 590, gy, bld.top)
            spots = [(bld.x0 + 420, lv[0]), (bld.x0 + 900, gy)]
        else:
            lv = _scaffold(p, bld.x0 + 120, bld.x0 + 500, gy, bld.top)
            spots = [(bld.x0 + 300, lv[0]), (bld.x1 - 200, gy)]
    for k, (wx, wy) in enumerate(spots):
        draw, box = _worker(wx, wy, tool="hammer", flip=k % 2 == 1, phase=k * 0.21)
        _looping(sc, draw, box, 0.5, fps=12, z=BG_Z + 0.06)
    if prog[0] < 0.999:
        crane = CraneLoad(jib_y, 1540, (bld.x0 + bld.x1) / 2 - 60, gy - 120, walls, what)
        _moving(sc, crane.frame, crane.box, z=BG_Z + 0.08)
    if what == "factory" and prog[1] >= 0.999:     # finished: the chimney starts to smoke
        start = 0.0 if prog[0] >= 0.999 else sc.dur * 0.9
        plume(sc, (bld.chimney[0] + bld.chimney[1]) / 2, bld.chimney[2] - 10, "gray", 1.0, 300, 220, start=start)


# ------------------------------------------------------------------ shared bits
def _glow(p, x, y, r, col, k=0.6):
    """A soft round light (lanterns, windows, fires) painted onto a background pen."""
    size = max(2, int(2 * r * SS))
    g = Image.radial_gradient("L").resize((size, size))
    m = g.point(lambda v: int(max(0.0, 1.0 - v / 128.0) ** 1.6 * 255 * k))
    p.im.paste(Image.new("RGB", (size, size), col), (int((x - r) * SS), int((y - r) * SS)), m)


def _heads(p, x0, x1, y, n, r_, s=1.0, seed=1, hats=None):
    """A row of seated people seen from behind a bench: heads and shoulders."""
    r = random.Random(seed)
    for k in range(n):
        x = x0 + (x1 - x0) * (k + 0.5) / n + r.uniform(-6, 6)
        p.ell(x, y + 26 * s, 26 * s, 18 * s, r.choice(((60, 60, 70), (90, 80, 70), (50, 60, 90), (110, 60, 60))), 3)
        p.circ(x, y - r_ * 0.2, r_, WHITE, 4)
        if hats and r.random() < 0.5:
            p.rect(x - r_ * 0.8, y - r_ * 1.9, r_ * 1.6, r_ * 0.9, (40, 40, 46), 3)
            p.line([(x - r_ * 1.2, y - r_ * 1.0), (x + r_ * 1.2, y - r_ * 1.0)], 4, (40, 40, 46), 0.1)
        p.circ(x - r_ * 0.3, y - r_ * 0.25, max(1.5, r_ * 0.1), INK, 0)
        p.circ(x + r_ * 0.3, y - r_ * 0.25, max(1.5, r_ * 0.1), INK, 0)


def _wood_wall(p, y0, y1, col=(126, 84, 54)):
    p.d.rectangle([0, int(y0 * SS), W * SS, int(y1 * SS)], fill=col)
    for x in range(0, W, 160):
        p.rect(x + 14, y0 + 20, 132, (y1 - y0) - 40, lighter(col, 0.08), 3, darker(col, 0.7))
    p.line([(0, y1), (W, y1)], 6, INK, 0.3)


def _floor(p, gy, col, boards=True, tiles=False):
    from .core import gradient
    p.im.paste(gradient((W * SS, int((H - gy) * SS) + SS), col, darker(col, 0.8)), (0, int(gy * SS)))
    if boards:
        for k in range(-3, 15):
            x0 = 150 * k
            p.line([(x0 + 260, gy), (x0 - 160, H)], 3, darker(col, 0.75), 0.3)
    if tiles:
        for j in range(6):
            ya = gy + (H - gy) * (j / 6) ** 1.3
            p.line([(0, ya), (W, ya)], 3, darker(col, 0.8), 0.1)
    p.line([(0, gy), (W, gy)], 6, INK, 0.4)


# ------------------------------------------------------------------ battlefield (like the history-channel battles)
BATTLE_STYLES = ("river", "open", "ruins")


def paint_battlefield(sc, bg):
    """A full battlefield: mountains, a village with a church tower, a river with a wooden bridge, trampled
    ground, craters, and black smoke rising over the village. style: river (default), open, ruins."""
    style = bg.get("style") if bg.get("style") in BATTLE_STYLES else "river"
    time = bg.get("time") or "day"
    night = time == "night"
    horizon = 560
    r = random.Random(sc.idx * 13 + 5)
    with sc.background((190, 200, 206)) as p:
        sc._sky(p, time, horizon + 60)
        haze = (196, 202, 210) if not night else (50, 56, 86)
        # far mountains
        mcol = (190, 170, 150) if not night else (60, 62, 86)
        pts = [(x, horizon - 70 - 90 * max(0.0, math.sin(x / 260 + 1.3)) * (0.6 + 0.4 * math.sin(x / 90)))
               for x in range(-20, W + 40, 30)]
        p.poly(pts + [(W + 20, horizon + 40), (-20, horizon + 40)], mcol, 4, darker(mcol, 0.8), 0.4)
        green = (110, 150, 88) if not night else (40, 62, 50)
        p.d.rectangle([0, int((horizon - 10) * SS), W * SS, int((horizon + 120) * SS)], fill=lighter(green, 0.1))
        # the village (or its ruins)
        houses = []
        x = 760 if style != "open" else 1180
        while x < W - 40:
            houses.append((x, horizon + r.randint(-6, 18), r.randint(70, 120), r.randint(50, 80)))
            x += r.randint(80, 140)
        church = houses[len(houses) // 2][0] + 30 if houses else 1300
        for hx, hy, hw, hh in houses:
            wall = (236, 230, 214) if not night else (90, 92, 110)
            if style == "ruins":
                pts = [(hx, hy), (hx, hy - hh * r.uniform(0.4, 1.0)), (hx + hw * 0.3, hy - hh * r.uniform(0.2, 0.9)),
                       (hx + hw * 0.6, hy - hh * r.uniform(0.5, 1.0)), (hx + hw, hy - hh * r.uniform(0.1, 0.6)),
                       (hx + hw, hy)]
                p.poly(pts, darker(wall, 0.8), 4)
                p.rect(hx + hw * 0.3, hy - hh * 0.5, 14, 18, (50, 50, 60), 0)
                continue
            p.rect(hx, hy - hh, hw, hh, wall, 4)
            p.poly([(hx - 8, hy - hh), (hx + hw / 2, hy - hh - 36), (hx + hw + 8, hy - hh)], (170, 82, 60), 4)
            for k in range(int(hw / 34)):
                p.rect(hx + 12 + k * 34, hy - hh + 18, 14, 18, (90, 110, 140), 0)
        if style != "open" and houses:
            tw = (236, 230, 214) if style != "ruins" else (170, 166, 156)
            top = horizon - 190 if style != "ruins" else horizon - 120
            p.rect(church - 30, top, 60, horizon + 10 - top, tw, 5)
            if style != "ruins":
                p.poly([(church - 38, top), (church, top - 70), (church + 38, top)], (90, 80, 90), 5)
                p.rect(church - 12, top + 26, 24, 34, (60, 60, 70), 3, r=12)
        # trees and bushes along the far bank
        for _ in range(16):
            tx = r.randint(-40, W + 40)
            ty = horizon + r.randint(10, 60)
            col = darker(green, r.uniform(0.75, 1.0)) if style != "ruins" else (90, 80, 70)
            if style == "ruins":
                p.line([(tx, ty), (tx + r.randint(-10, 10), ty - r.randint(50, 110))], 6, col, 0.6)
            else:
                p.blob(tx, ty - 30, r.randint(40, 80), r.randint(28, 46), col, 4, darker(col, 0.7), seed=tx + 3)
        ground = (156, 128, 92) if style != "ruins" else (120, 104, 84)
        ground = ground if not night else (56, 50, 50)
        if style == "river":
            near = lambda xx: 770 + 18 * math.sin(xx / 210)
            far_ = lambda xx: horizon + 92 + 10 * math.sin(xx / 170 + 1)
            water = (110, 182, 214) if not night else (36, 56, 96)
            p.poly([(xx, far_(xx)) for xx in range(-20, W + 40, 20)] +
                   [(xx, near(xx)) for xx in range(W + 20, -40, -20)], water, 0, wob=0)
            for j in range(6):
                yy = horizon + 110 + j * 24
                for xx in range(r.randint(0, 120), W, r.randint(200, 300)):
                    p.line([(xx, yy), (xx + 60, yy)], 3, lighter(water, 0.35), 0.3)
            p.line([(xx, far_(xx)) for xx in range(-20, W + 40, 20)], 5, darker(green, 0.7), 0.4)
            # the wooden bridge across the river, from the far bank down to the near one
            bx0, by0, bx1, by1 = 240, far_(240) - 4, 1060, near(1060) + 6
            dk = (150, 110, 70)
            for k in range(1, 16):
                u = k / 16
                xx, yy = bx0 + (bx1 - bx0) * u, by0 + (by1 - by0) * u
                p.line([(xx, yy + 18), (xx, yy + 18 + 26 + 30 * u)], 8, darker(dk, 0.65), 0.3)
            p.poly([(bx0, by0), (bx1, by1), (bx1, by1 + 26), (bx0, by0 + 18)], dk, 5)
            for k in range(0, 33):
                u = k / 32
                xx, yy = bx0 + (bx1 - bx0) * u, by0 + (by1 - by0) * u
                p.line([(xx, yy), (xx, yy - 30 - 12 * u)], 4, darker(dk, 0.75), 0.2)
            p.line([(bx0, by0 - 30), (bx1, by1 - 42)], 6, dk, 0.2)
            p.line([(bx0, by0 - 14), (bx1, by1 - 20)], 4, dk, 0.2)
            gy = 770
        else:
            gy = horizon + 100
        # the near ground: trampled dirt with patches of grass, craters and stones
        pts = [(xx, gy + 14 * math.sin(xx / 210)) for xx in range(-20, W + 40, 20)] if style == "river" else \
            [(xx, gy - 30 * math.sin(xx / 400 + 2)) for xx in range(-20, W + 40, 20)]
        p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], ground, 5, darker(ground, 0.75), 0.4)
        for _ in range(14):
            gx, gyy = r.randint(0, W), r.randint(gy + 30, H - 20)
            p.blob(gx, gyy, r.randint(60, 140), r.randint(14, 26), darker(green, 0.95) if style != "ruins" else
                   darker(ground, 0.9), 0, seed=gx)
        for _ in range(5 if style != "ruins" else 9):
            cx, cy = r.randint(80, W - 80), r.randint(gy + 60, H - 50)
            p.ell(cx, cy, r.randint(60, 110), r.randint(16, 26), darker(ground, 0.7), 4, darker(ground, 0.55))
            p.ell(cx, cy - 6, 40, 10, darker(ground, 0.55), 0)
        for _ in range(30):
            sx, sy = r.randint(0, W), r.randint(gy + 20, H - 10)
            p.ell(sx, sy, r.randint(4, 10), r.randint(3, 6), darker(ground, 0.72), 0)
        if style == "ruins":
            far_prop(p, "barbed_wire", 520, gy + 60, 0.9, haze, 0.0)
            far_prop(p, "barbed_wire", 1500, gy + 40, 0.8, haze, 0.0)
        if style == "open":
            for tx in (300, 470, 640):
                far_prop(p, "tent", tx, horizon + 70, 0.35, haze, 0.35)
    # smoke from the village and the guns, rising and drifting
    srcs = ([(1000, horizon - 10), (1380, horizon - 30), (1720, horizon)] if style != "open"
            else [(1400, horizon), (900, horizon + 40)])
    for k, (sx, sy) in enumerate(srcs):
        plume(sc, sx, sy, "black", 1.1 + 0.2 * (k % 2), 460, 70, seed=k * 7)
    if style != "ruins":
        plume(sc, 260, horizon + 60, "white", 0.8, 220, 50, seed=21)


# ------------------------------------------------------------------ factory (working)
def _sawtooth_hall(p, x0, x1, top, gy, teeth, roof, night, r):
    _bricks(p, x0, top, x1, gy)
    n = max(2, int((x1 - x0) / 150))
    for i in range(n):
        wx = x0 + (i + 0.5) * (x1 - x0) / n - 32
        for yy in (top + 40, top + 40 + 150):
            if yy + 110 < gy - 20:
                _window(p, wx, yy, 64, 110, arch=True, night=night, lit=night and r.random() < 0.6)
    p.rect(x0, top, x1 - x0, gy - top, None, 6)
    tw = (x1 - x0) / teeth
    for i in range(teeth):
        xa = x0 + i * tw
        p.poly([(xa, top), (xa + tw * 0.75, top - roof), (xa + tw * 0.75, top)], (110, 104, 104), 5)
        p.poly([(xa + tw * 0.75, top - roof), (xa + tw, top), (xa + tw * 0.75, top)], (150, 186, 210), 5)


def _chimney(p, x, w, top, gy):
    _bricks(p, x - w / 2, top, x + w / 2, gy, darker(BRICK, 0.92), bw=24, bh=14)
    p.rect(x - w / 2, top, w, gy - top, None, 5)
    p.rect(x - w / 2 - 8, top - 6, w + 16, 20, darker(BRICK, 0.7), 5)


def _gear(p, cx, cy, r_, teeth, ang, col):
    pts = []
    for i in range(teeth * 2):
        a = ang + math.pi * i / teeth
        rr = r_ if i % 2 == 0 else r_ * 0.84
        a2 = ang + math.pi * (i + 1) / teeth
        pts += [(cx + rr * math.cos(a), cy + rr * math.sin(a)), (cx + rr * math.cos(a2), cy + rr * math.sin(a2))]
    p.poly(pts, col, 5, INK, 0.1)
    p.circ(cx, cy, r_ * 0.55, darker(col, 0.85), 4)
    for k in range(4):
        a = ang + k * math.pi / 2
        p.line([(cx + r_ * 0.2 * math.cos(a), cy + r_ * 0.2 * math.sin(a)),
                (cx + r_ * 0.55 * math.cos(a), cy + r_ * 0.55 * math.sin(a))], 6, darker(col, 0.7), 0.1)
    p.circ(cx, cy, r_ * 0.18, (90, 90, 96), 4)


class Conveyor:
    """Crates riding a conveyor belt from left to right."""

    def __init__(self, y, x0=-40, x1=W + 40, speed=110.0, gap=320):
        self.y, self.x0, self.x1, self.speed, self.gap = y, x0, x1, speed, gap
        cols = [(196, 150, 96), (176, 132, 84), (210, 170, 110)]
        self.items = []
        for k in range(3):
            def draw(p, c=cols[k], kind=k):
                p.rect(6, 6, 110, 84, c, 5)
                p.line([(6, 30), (116, 30)], 3, darker(c, 0.7), 0.1)
                if kind == 1:
                    p.line([(30, 50), (90, 80)], 3, darker(c, 0.7), 0.1)
            self.items.append(_sprite(draw, 122, 96, seed=k + 3))
        self.box = (0, int(y - 100), W, 104)

    def frame(self, t):
        cv = _rgba(W, 104)
        off = (t * self.speed) % self.gap
        k = 0
        x = self.x0 - self.gap + off
        while x < self.x1:
            im = self.items[k % 3]
            _paste(cv, im, x, 4)
            x += self.gap
            k += 1
        return cv


def paint_factory(sc, bg):
    """A working factory. style: outside (brick halls, chimneys pouring smoke, a railway) or inside (belts, gears,
    a stamping press)."""
    style = "inside" if str(bg.get("style") or "").lower() in ("inside", "interior", "floor", "assembly") else "outside"
    time = bg.get("time") or "day"
    night = time == "night"
    r = random.Random(sc.idx * 7 + 3)
    if style == "outside":
        gy = 760
        with sc.background((200, 210, 220)) as p:
            sc._sky(p, time, gy)
            haze = (190, 196, 206) if not night else (46, 52, 80)
            x = -20
            while x < W:          # the industrial town behind
                w_, h_ = r.randint(90, 170), r.randint(120, 260)
                p.d.rectangle([int(x * SS), int((gy - h_) * SS), int((x + w_) * SS), int(gy * SS)], fill=darker(haze, 0.85))
                if r.random() < 0.4:
                    p.d.rectangle([int((x + w_ / 2 - 10) * SS), int((gy - h_ - 90) * SS), int((x + w_ / 2 + 10) * SS),
                                   int((gy - h_) * SS)], fill=darker(haze, 0.8))
                x += w_ + r.randint(10, 60)
            _chimney(p, 930, 80, 110, gy)
            _chimney(p, 1780, 70, 170, gy)
            _sawtooth_hall(p, 80, 880, gy - 300, gy, 5, 90, night, r)
            _sawtooth_hall(p, 1000, 1720, gy - 380, gy, 4, 100, night, r)
            _chimney(p, 650, 64, 200, gy - 300)
            p.rect(1300, gy - 200, 160, 200, (80, 66, 60), 5)
            for k in range(1, 6):
                p.line([(1300, gy - 200 + 32 * k), (1460, gy - 200 + 32 * k)], 3, (60, 50, 46), 0.1)
            ground = (150, 146, 140) if not night else (60, 62, 72)
            sc._ground(p, None, gy, ground)
            # railway with freight wagons
            ry = gy + 70
            p.line([(-20, ry), (W + 20, ry)], 6, (110, 100, 96), 0.1)
            p.line([(-20, ry + 22), (W + 20, ry + 22)], 6, (110, 100, 96), 0.1)
            for xx in range(-20, W, 46):
                p.rect(xx, ry - 4, 26, 30, (130, 96, 70), 0)
            p.line([(-20, ry), (W + 20, ry)], 6, (120, 120, 130), 0.1)
            for wx in (60, 360):
                p.rect(wx, ry - 120, 270, 100, (130, 60, 50) if wx == 60 else (80, 90, 110), 5)
                for k in range(1, 6):
                    p.line([(wx + 45 * k, ry - 120), (wx + 45 * k, ry - 20)], 3, INK, 0.1)
                for wh in (wx + 50, wx + 220):
                    p.circ(wh, ry - 10, 22, (60, 60, 66), 4)
            # coal heap and crates
            p.poly([(1520, gy + 40), (1610, gy - 50), (1700, gy - 60), (1800, gy + 40)], (50, 50, 56), 5)
        for k, (cx, top) in enumerate(((930, 110), (1780, 170), (650, 200))):
            plume(sc, cx, top - 6, "black" if k != 2 else "gray", 1.4 - 0.2 * k, 300, 300, seed=k * 5)
        return
    # inside: the factory floor
    gy = 820
    wall = (198, 120, 96)
    with sc.background(wall) as p:
        _bricks(p, 0, 0, W, gy, (196, 128, 104), bw=56, bh=22)
        for k in range(4):            # tall windows with light falling in
            wx = 140 + k * 470
            p.rect(wx, 60, 220, 300, (190, 214, 230) if not night else (50, 60, 90), 6)
            for j in range(1, 4):
                p.line([(wx, 60 + 75 * j), (wx + 220, 60 + 75 * j)], 4, (70, 80, 96), 0.1)
            for j in range(1, 3):
                p.line([(wx + 73 * j, 60), (wx + 73 * j, 360)], 4, (70, 80, 96), 0.1)
        for x in (0, 470, 940, 1410, 1880):     # steel columns and roof beam
            p.rect(x + 8, 0, 34, gy, STEEL, 4)
        p.rect(0, 0, W, 40, STEEL, 4)
        for x in range(20, W, 90):
            p.line([(x, 40), (x + 45, 0)], 3, darker(STEEL, 0.8), 0.1)
        # pipes along the wall
        p.line([(0, 400), (W, 400)], 16, (150, 150, 160), 0.1)
        p.line([(0, 430), (W, 430)], 10, (176, 96, 60), 0.1)
        _floor(p, gy, (150, 150, 150), boards=False, tiles=True)
        # the conveyor belt's frame
        cy = 690
        p.rect(-20, cy, W + 40, 30, (70, 70, 80), 5)
        for x in range(10, W, 60):
            p.circ(x, cy + 15, 11, (150, 150, 160), 3)
        for x in range(60, W, 300):
            p.line([(x, cy + 30), (x, gy + 6)], 10, (70, 70, 80), 0.1)
        # a stamping press frame on the right
        p.rect(1500, 300, 40, cy - 300, (60, 110, 160), 5)
        p.rect(1780, 300, 40, cy - 300, (60, 110, 160), 5)
        p.rect(1480, 270, 360, 60, (60, 110, 160), 5)
        # hanging lamps
        for lx in (380, 960, 1300):
            p.line([(lx, 40), (lx, 150)], 3, INK, 0.1)
            p.chord(lx - 50, 140, lx + 50, 200, 180, 360, (70, 90, 80), 4)
            _glow(p, lx, 190, 110, (255, 236, 180), 0.35)
    gear_box = (120, 450, 330, 230)

    def gears(p, t):
        a = t * 1.2
        _gear(p, 110, 110, 100, 12, a, (180, 160, 110))
        _gear(p, 250, 150, 70, 8, -a * 12 / 8 + 0.2, (160, 166, 176))
    _looping(sc, gears, gear_box, period=2 * math.pi / 12 / 1.2, fps=24)
    conv = Conveyor(690, speed=120.0, gap=330)
    _moving(sc, conv.frame, conv.box)
    ram = _sprite(lambda p: (p.rect(6, 6, 220, 70, (200, 200, 210), 5), p.rect(96, 76, 40, 30, (120, 120, 130), 4)),
                  232, 112, seed=17)

    def press(t):
        cv = _rgba(240, 380)
        q = (t % 1.6) / 1.6
        y = 10 + (200 if q < 0.15 else 200 * (1 - (q - 0.15) / 0.85) if q < 1 else 0) if q >= 0.08 else 10 + 200 * q / 0.08
        d = ImageDraw.Draw(cv)
        d.rectangle([110, 0, 130, int(y + 10)], fill=(90, 90, 100))
        _paste(cv, ram, 4, y)
        return cv
    _moving(sc, press, (1544, 330, 240, 380))


# ------------------------------------------------------------------ farm
def paint_farm(sc, bg):
    time = bg.get("time") or "day"
    night = time == "night"
    gy = 640
    r = random.Random(sc.idx * 3 + 1)
    with sc.background((210, 232, 246)) as p:
        sc._sky(p, time, gy)
        haze = (200, 220, 236) if not night else (46, 54, 86)
        for k, (col, base, amp) in enumerate((((150, 190, 120), gy - 40, 50), ((126, 176, 100), gy + 10, 40))):
            col = col if not night else darker(col, 0.4)
            ph = r.uniform(0, 6)
            pts = [(x, base - amp * (0.5 + 0.5 * math.sin(x / (300 + 80 * k) + ph))) for x in range(-20, W + 40, 40)]
            p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], col, 0, col, 0.2)
        far_prop(p, "windmill", 300, gy - 20, 0.45, haze, 0.3)
        # crop fields in perspective: golden wheat on the left, plowed earth on the right
        wheat = (232, 196, 96) if not night else (110, 100, 70)
        soil = (150, 104, 66) if not night else (70, 56, 46)
        fy = gy + 60
        p.poly([(-20, fy), (900, fy - 10), (760, H + 10), (-20, H + 10)], wheat, 5, darker(wheat, 0.8), 0.3)
        for k in range(14):
            xa = -20 + (900 + 20) * k / 13
            p.line([(xa, fy - 10 * k / 13), (-20 + (780 + 20) * k / 13 - 200 * (1 - k / 13), H + 10)], 3,
                   darker(wheat, 0.8), 0.3)
        p.poly([(900, fy - 10), (W + 20, fy - 20), (W + 20, H + 10), (760, H + 10)], soil, 5, darker(soil, 0.8), 0.3)
        for k in range(12):
            u = k / 11
            p.line([(900 + (W + 20 - 900) * u, fy - 10 - 10 * u), (760 + (W + 20 - 760) * u + 300 * u, H + 10)], 4,
                   darker(soil, 0.78), 0.3)
        # barn and silo
        far_prop(p, "barn", 1380, fy + 10, 1.0, haze, 0.0)
        sx = 1640
        p.rect(sx, fy - 360, 120, 370, (200, 200, 206), 5)
        p.chord(sx, fy - 420, sx + 120, fy - 300, 180, 360, (170, 60, 50), 5)
        for k in range(1, 7):
            p.line([(sx, fy - 360 + 52 * k), (sx + 120, fy - 360 + 52 * k)], 3, (150, 150, 160), 0.1)
        # haystacks and a fence
        for hx, hy, s_ in ((980, fy + 10, 1.0), (1150, fy + 30, 0.8)):
            p.chord(hx - 90 * s_, hy - 140 * s_, hx + 90 * s_, hy + 40 * s_, 180, 360, (236, 206, 110), 5)
            for k in range(5):
                p.line([(hx - 60 * s_ + k * 30 * s_, hy - 40 * s_), (hx - 50 * s_ + k * 26 * s_, hy - 6)], 3,
                       (200, 166, 80), 0.3)
        fence = (176, 130, 84)
        for x in range(-10, W + 40, 120):
            p.line([(x, fy - 30), (x, fy + 50)], 9, fence, 0.3)
        p.line([(-20, fy - 14), (W + 20, fy - 24)], 7, fence, 0.3)
        p.line([(-20, fy + 18), (W + 20, fy + 8)], 7, fence, 0.3)


# ------------------------------------------------------------------ mine
def paint_mine(sc, bg):
    """Inside a mine: timber frames down the tunnel, rails into the dark, a cart full of ore, lanterns."""
    from .core import gradient
    vx, vy = 960, 520
    with sc.background((70, 56, 44), noise=True) as p:
        p.im.paste(gradient((W * SS, H * SS), (96, 76, 58), (52, 42, 34)), (0, 0))
        r = random.Random(sc.idx + 91)
        for _ in range(40):           # rock lumps on the walls
            x, y = r.randint(0, W), r.randint(0, H)
            if abs(x - vx) < 260 and abs(y - vy) < 200:
                continue
            p.blob(x, y, r.randint(30, 80), r.randint(20, 50), darker((96, 78, 60), r.uniform(0.8, 1.05)), 3,
                   (60, 48, 38), seed=x + y)
        for _ in range(9):            # gold veins
            x, y = r.choice((r.randint(40, 600), r.randint(1320, 1880))), r.randint(120, 760)
            for k in range(4):
                p.poly([(x + k * 14, y + k * 8), (x + k * 14 + 12, y + k * 8 - 6), (x + k * 14 + 18, y + k * 8 + 4)],
                       (250, 210, 70), 2, (180, 140, 40))
        p.ell(vx, vy, 160, 120, (20, 18, 16), 0)
        p.ell(vx, vy, 90, 70, (8, 8, 8), 0)
        # timber frames, nearest first, shrinking toward the vanishing point
        timber = (150, 106, 64)
        for k in range(5, -1, -1):
            s_ = 0.22 + 0.78 * (k / 5) ** 1.5
            hw, top, bot = 900 * s_, vy - 520 * s_, vy + 420 * s_
            col = darker(timber, 0.45 + 0.55 * k / 5)
            p.rect(vx - hw - 40 * s_, top, 60 * s_, bot - top, col, max(2, 5 * s_))
            p.rect(vx + hw - 20 * s_, top, 60 * s_, bot - top, col, max(2, 5 * s_))
            p.rect(vx - hw - 60 * s_, top - 30 * s_, 2 * hw + 120 * s_, 60 * s_, col, max(2, 5 * s_))
            if k in (2, 4):
                lx = vx + (hw - 80 * s_) * (1 if k == 4 else -1)
                ly = top + 60 * s_
                p.line([(lx, ly), (lx, ly + 50 * s_)], max(2, 3 * s_), INK, 0.1)
                p.rect(lx - 18 * s_, ly + 50 * s_, 36 * s_, 50 * s_, (255, 220, 120), max(2, 4 * s_))
                _glow(p, lx, ly + 75 * s_, 260 * s_, (255, 214, 140), 0.45)
        # floor and rails into the dark
        p.poly([(0, 860), (vx - 120, vy + 90), (vx + 120, vy + 90), (W, 860), (W, H), (0, H)], (84, 70, 56), 0, wob=0)
        for side in (-1, 1):
            p.line([(vx + side * 30, vy + 90), (vx + side * 420, H)], 8, (150, 150, 160), 0.1)
        for k in range(14):
            u = (k / 13) ** 1.8
            y = vy + 90 + (H - vy - 90) * u
            hw = 30 + 390 * u
            p.line([(vx - hw - 30 * u, y), (vx + hw + 30 * u, y)], max(3, 14 * u), (110, 80, 52), 0.1)
        # the ore cart on the right
        cx, cy = 1520, 900
        p.poly([(cx - 150, cy - 140), (cx + 150, cy - 140), (cx + 120, cy), (cx - 120, cy)], (120, 120, 130), 6)
        for k in range(7):
            p.blob(cx - 120 + k * 40, cy - 150 - (k % 2) * 16, 34, 26, (110, 100, 96), 4, seed=k + 9)
        for k in range(3):
            p.blob(cx - 80 + k * 70, cy - 170, 16, 12, (250, 210, 70), 3, seed=k + 31)
        p.circ(cx - 80, cy + 10, 26, (60, 60, 66), 5)
        p.circ(cx + 80, cy + 10, 26, (60, 60, 66), 5)


# ------------------------------------------------------------------ classroom, lab
def paint_classroom(sc, bg):
    wall = (214, 226, 200)
    gy = 760
    with sc.background(wall) as p:
        p.d.rectangle([0, int((gy - 160) * SS), W * SS, int(gy * SS)], fill=(170, 130, 90))
        p.line([(0, gy - 160), (W, gy - 160)], 6, (120, 84, 56), 0.2)
        # the blackboard with chalk sums
        p.rect(500, 150, 920, 380, (52, 80, 66), 10, (130, 92, 60))
        chalk = (236, 240, 230)
        p.text("2 + 2 = 4", 760, 260, 70, chalk)
        p.poly([(1100, 420), (1250, 220), (1340, 420)], None, 5, chalk, 0.8)
        p.text("a² + b² = c²", 780, 400, 56, chalk)
        p.rect(500, 528, 920, 16, (130, 92, 60), 4)
        p.rect(560, 520, 50, 10, WHITE, 0)
        # clock, map, window
        p.circ(960, 80, 48, WHITE, 6)
        p.line([(960, 80), (960, 50)], 5, INK, 0.1)
        p.line([(960, 80), (984, 92)], 5, INK, 0.1)
        p.rect(80, 170, 330, 230, (200, 226, 240), 8, (150, 110, 70))
        for cx, cy, rx, ry in ((170, 260, 50, 40), (300, 250, 60, 36), (250, 340, 40, 30)):
            p.blob(cx, cy, rx, ry, (150, 196, 120), 3, seed=cx)
        p.rect(1540, 140, 300, 340, (170, 214, 240), 8, (150, 110, 70))
        p.line([(1690, 140), (1690, 480)], 6, (150, 110, 70), 0.2)
        p.line([(1540, 310), (1840, 310)], 6, (150, 110, 70), 0.2)
        _floor(p, gy, (190, 150, 106))
        # teacher's desk with an apple and a globe
        p.rect(1380, 560, 380, 40, (150, 104, 66), 5)
        p.rect(1400, 600, 340, 160, (130, 90, 56), 5)
        p.circ(1450, 540, 22, (210, 50, 50), 4)
        p.line([(1450, 518), (1456, 506)], 4, (90, 60, 40), 0.1)
        p.circ(1660, 490, 52, (90, 160, 220), 5)
        p.blob(1650, 480, 30, 22, (120, 190, 110), 2, seed=3)
        p.line([(1660, 542), (1660, 560)], 6, (120, 84, 56), 0.1)
        # pupils' desks at the sides
        for dx in (40, 1720):
            p.rect(dx, 880, 180, 26, (190, 150, 100), 5)
            p.line([(dx + 20, 906), (dx + 20, 1060)], 8, (90, 90, 100), 0.1)
            p.line([(dx + 160, 906), (dx + 160, 1060)], 8, (90, 90, 100), 0.1)


def paint_lab(sc, bg):
    gy = 780
    with sc.background((226, 236, 240)) as p:
        tile = (226, 236, 240)
        for x in range(0, W, 60):
            p.line([(x, 0), (x, gy)], 2, darker(tile, 0.9), 0.1)
        for y in range(0, gy, 60):
            p.line([(0, y), (W, y)], 2, darker(tile, 0.9), 0.1)
        # shelves with jars
        r = random.Random(sc.idx + 5)
        for sy in (200, 360):
            p.rect(1180, sy, 620, 16, (150, 110, 70), 4)
            x = 1200
            while x < 1760:
                c = r.choice([(120, 200, 120), (220, 120, 200), (120, 170, 230), (240, 200, 90), (230, 110, 90)])
                h_ = r.randint(50, 100)
                p.rect(x, sy - h_, 50, h_, lighter(c, 0.4), 4, r=8)
                p.rect(x + 4, sy - h_ * 0.6, 42, h_ * 0.6 - 4, c, 0)
                x += r.randint(64, 90)
        # a chalkboard of formulas
        p.rect(120, 120, 760, 360, (52, 80, 66), 10, (130, 92, 60))
        p.text("E = mc²", 360, 220, 80, (236, 240, 230))
        p.text("H2O", 700, 340, 70, (236, 240, 230))
        p.circ(320, 380, 18, (236, 240, 230), 0)
        p.ell(320, 380, 80, 26, None, 3, (236, 240, 230))
        p.ell(320, 380, 26, 80, None, 3, (236, 240, 230))
        # the bench
        p.rect(-20, 600, W + 40, 40, (60, 64, 76), 5)
        p.rect(-20, 640, W + 40, gy - 640, (220, 224, 230), 5)
        for x in range(160, W, 360):
            p.rect(x, 660, 300, gy - 680, (236, 240, 244), 4)
            p.circ(x + 150, 700, 8, (120, 120, 130), 0)
        _floor(p, gy, (210, 214, 220), boards=False, tiles=True)
        # microscope
        mx = 1600
        p.rect(mx - 60, 586, 140, 16, (60, 60, 70), 4)
        p.line([(mx + 30, 586), (mx + 30, 470), (mx - 20, 420)], 14, (70, 70, 84), 0.1)
        p.line([(mx - 20, 420), (mx - 40, 380)], 22, (200, 200, 210), 0.1)
        p.rect(mx - 50, 520, 100, 12, (150, 150, 160), 3)
    flasks = [(260, (120, 210, 120), "cone"), (520, (230, 110, 200), "round"), (800, (120, 170, 240), "cone"),
              (1080, (250, 190, 70), "round")]
    for k, (fx, col, shape) in enumerate(flasks):
        def draw(p, t, col=col, shape=shape, k=k):
            cx = 70
            if shape == "cone":
                p.poly([(cx - 22, 20), (cx + 22, 20), (cx + 22, 70), (cx + 60, 160), (cx - 60, 160), (cx - 22, 70)],
                       (236, 244, 250), 5)
                p.poly([(cx - 40, 112), (cx + 40, 112), (cx + 60, 158), (cx - 60, 158)], col, 0, wob=0)
            else:
                p.rect(cx - 18, 20, 36, 70, (236, 244, 250), 5)
                p.circ(cx, 118, 46, (236, 244, 250), 5)
                p.chord(cx - 44, 74, cx + 44, 162, 0, 180, col, 0)
            for b in range(4):
                q = ((t / 1.2) + b / 4 + k * 0.13) % 1.0
                by = 150 - q * 120
                bx = cx + 14 * math.sin(q * 9 + b)
                if q < 0.9:
                    p.circ(bx, by, 5 + 4 * q, lighter(col, 0.5), 2, darker(col, 0.8))
        _looping(sc, draw, (fx - 70, 430, 140, 170), period=1.2, fps=12)


# ------------------------------------------------------------------ parliament, courtroom
def paint_parliament(sc, bg):
    """A debating chamber: tiers of benches packed with members, the Speaker's chair, tall arched windows."""
    from .palette import color as C
    seat = C(bg.get("color"), (70, 130, 86))
    gy = 800
    with sc.background((150, 110, 76)) as p:
        _wood_wall(p, 0, 470, (126, 86, 56))
        for x in range(100, W, 300):          # tall arched windows
            p.rect(x, 60, 120, 260, (180, 200, 220), 5, r=60)
            p.line([(x + 60, 60), (x + 60, 320)], 3, (90, 80, 70), 0.1)
            p.line([(x, 190), (x + 120, 190)], 3, (90, 80, 70), 0.1)
        # three tiers of benches with members
        for k, y in enumerate((470, 560, 650)):
            n = 15 - k
            _heads(p, 20, W - 20, y - 30, n, 26 + k * 3, 1.0 + 0.15 * k, seed=sc.idx + k * 11, hats=False)
            p.rect(-20, y, W + 40, 30, seat, 5)
            p.rect(-20, y + 30, W + 40, 60, darker(seat, 0.75), 5)
        # the Speaker's chair in the middle
        p.rect(860, 300, 200, 300, (100, 64, 40), 6)
        p.poly([(840, 300), (960, 210), (1080, 300)], (110, 70, 44), 6)
        p.rect(890, 340, 140, 200, seat, 5)
        p.circ(960, 260, 24, (226, 182, 72), 4)
        _floor(p, gy, (70, 120, 80), boards=False)
        # the clerks' table with books
        p.rect(760, 690, 400, 30, (130, 90, 56), 5)
        p.rect(780, 720, 360, 80, (110, 74, 46), 5)
        for k, c in enumerate(((170, 60, 60), (60, 90, 150), (200, 170, 80))):
            p.rect(800 + k * 40, 660, 34, 30, c, 4)
        p.line([(1000, 680), (1130, 660)], 10, (226, 182, 72), 0.2)


def paint_courtroom(sc, bg):
    gy = 800
    with sc.background((150, 110, 76)) as p:
        _wood_wall(p, 0, gy, (140, 98, 62))
        # the emblem and flags
        p.circ(960, 100, 72, (226, 182, 72), 6)
        p.line([(960, 50), (960, 150)], 6, INK, 0.1)
        p.line([(905, 75), (1015, 75)], 6, INK, 0.1)
        for sx in (915, 1005):
            p.line([(sx, 75), (sx - 20, 118), (sx + 20, 118), (sx, 75)], 3, INK, 0.1)
            p.chord(sx - 24, 100, sx + 24, 136, 0, 180, (250, 236, 180), 3)
        for fx, col in ((640, (60, 90, 170)), (1280, (190, 60, 60))):
            p.line([(fx, 120), (fx, 440)], 8, (180, 150, 80), 0.1)
            p.poly([(fx, 130), (fx + 90, 150), (fx + 70, 260), (fx, 250)], col, 5)
        # the judge's bench, high in the middle
        p.rect(680, 300, 560, 40, (110, 72, 44), 6)
        p.rect(700, 340, 520, 330, (130, 88, 54), 6)
        for k in range(4):
            p.rect(730 + k * 125, 380, 100, 250, lighter((130, 88, 54), 0.08), 4)
        p.rect(880, 190, 160, 120, (90, 30, 40), 6, r=30)
        p.rect(1080, 282, 60, 16, (100, 64, 40), 4)
        p.line([(1110, 282), (1150, 260)], 8, (100, 64, 40), 0.1)
        # witness stand and jury box
        p.rect(200, 520, 300, 30, (110, 72, 44), 5)
        p.rect(220, 550, 260, 200, (130, 88, 54), 5)
        _heads(p, 1440, 1880, 520, 5, 30, seed=sc.idx + 3)
        p.rect(1420, 560, 480, 30, (110, 72, 44), 5)
        p.rect(1440, 590, 440, 170, (130, 88, 54), 5)
        _floor(p, gy, (150, 108, 70))


# ------------------------------------------------------------------ prison
def paint_prison(sc, bg):
    """Inside a prison cell: stone walls, a high barred window with a shaft of light, a bunk, scratched tally
    marks, and the cell bars at both edges of the picture."""
    gy = 790
    stone = (150, 150, 156)
    with sc.background(stone) as p:
        _stones(p, 0, 0, W, gy, stone)
        # barred window and its light
        p.rect(840, 130, 240, 170, (190, 214, 236), 8, (90, 90, 96))
        for x in range(880, 1060, 40):
            p.line([(x, 130), (x, 300)], 9, (60, 60, 66), 0.1)
        light = Image.new("L", (W * SS, H * SS), 0)
        ImageDraw.Draw(light).polygon([(840 * SS, 300 * SS), (1080 * SS, 300 * SS), (1300 * SS, H * SS),
                                       (760 * SS, H * SS)], fill=60)
        p.im.paste(Image.new("RGB", (W * SS, H * SS), (255, 250, 220)), (0, 0), light)
        # tally marks
        for g in range(4):
            x0 = 240 + g * 90
            for k in range(4):
                p.line([(x0 + k * 16, 300), (x0 + k * 16 + 2, 380)], 4, (70, 70, 76), 0.6)
            p.line([(x0 - 8, 370), (x0 + 60, 310)], 4, (70, 70, 76), 0.6)
        # chains
        for k in range(6):
            p.ell(560, 300 + k * 26, 10, 16, None, 5, (90, 90, 96))
        _floor(p, gy, (128, 126, 124), boards=False, tiles=False)
        # the bunk and a bucket
        p.rect(1360, 600, 420, 30, (110, 110, 120), 5)
        p.rect(1360, 570, 420, 34, (200, 196, 180), 5, r=10)
        p.rect(1380, 560, 90, 30, WHITE, 4, r=10)
        for x in (1370, 1770):
            p.line([(x, 630), (x, gy + 10)], 9, (110, 110, 120), 0.1)
        p.poly([(380, gy - 10), (480, gy - 10), (470, gy + 70), (390, gy + 70)], (130, 120, 110), 5)
        # the bars in front
        for x in list(range(20, 230, 52)) + list(range(1712, 1910, 52)):
            p.rect(x, -10, 18, H + 20, (70, 72, 80), 4)
        for y in (120, 860):
            p.rect(-10, y, 250, 22, (70, 72, 80), 4)
            p.rect(1690, y, 240, 22, (70, 72, 80), 4)


# ------------------------------------------------------------------ market
def paint_market(sc, bg):
    """A busy market: stalls with striped awnings and crates of goods in front of the town's houses."""
    from .places import STREET_STYLES
    style = bg.get("style") if bg.get("style") in STREET_STYLES else "europe"
    time = bg.get("time") or "day"
    gy = 700
    r = random.Random(sc.idx * 17 + 2)
    with sc.background((214, 232, 246)) as p:
        sc._sky(p, time, gy)
        x = -40
        while x < W:
            w_ = r.randint(170, 260)
            _facade(p, r, x, w_, gy, style, time)
            x += w_
        road = (200, 190, 172)
        p.d.rectangle([0, int(gy * SS), W * SS, H * SS], fill=road)
        for j in range(10):
            yy = gy + 20 + j * 38
            for i in range(-1, 34):
                xx = i * 62 + (j % 2) * 30
                p.d.rounded_rectangle([int(xx * SS), int(yy * SS), int((xx + 52) * SS), int((yy + 26) * SS)],
                                      radius=8 * SS, outline=darker(road, 0.82), width=2 * SS)
        # bunting across the street
        for k, y0 in enumerate((120, 200)):
            pts = [(x, y0 + 40 * math.sin(math.pi * x / W)) for x in range(-20, W + 40, 60)]
            p.line(pts, 3, INK, 0.2)
            for i, (bx, by) in enumerate(pts[:-1]):
                p.poly([(bx + 6, by), (bx + 46, by + 2), (bx + 26, by + 40)],
                       ((220, 60, 50), (250, 200, 60), (60, 120, 200), (80, 170, 90))[(i + k) % 4], 3)
        # stalls
        awn = ((210, 60, 50), (60, 110, 190), (60, 150, 90), (230, 160, 40))
        goods = ((220, 50, 50), (250, 150, 40), (120, 190, 70), (240, 220, 80), (150, 80, 160))
        for k, sx in enumerate((60, 520, 980, 1440)):
            col = awn[k % 4]
            p.line([(sx + 10, gy + 120), (sx + 10, gy - 190)], 8, (120, 84, 56), 0.2)
            p.line([(sx + 390, gy + 120), (sx + 390, gy - 190)], 8, (120, 84, 56), 0.2)
            p.poly([(sx - 20, gy - 190), (sx + 420, gy - 190), (sx + 440, gy - 110), (sx - 40, gy - 110)], WHITE, 5)
            for i in range(8):
                xa = sx - 20 + 440 * i / 8
                xb = sx - 40 + 480 * i / 8
                if i % 2 == 0:
                    p.poly([(xa, gy - 190), (xa + 55, gy - 190), (xb + 60, gy - 110), (xb, gy - 110)], col, 0, wob=0)
            for i in range(8):
                xb = sx - 40 + 480 * i / 8
                p.chord(xb, gy - 134, xb + 60, gy - 86, 0, 180, col if i % 2 == 0 else WHITE, 4)
            _heads(p, sx + 60, sx + 340, gy - 30, 2, 26, seed=sc.idx + k)
            p.rect(sx, gy - 10, 400, 30, (170, 124, 80), 5)
            p.rect(sx + 10, gy + 20, 380, 100, (150, 106, 66), 5)
            g = goods[k % 5]
            for i in range(9):
                p.circ(sx + 40 + i * 40, gy - 22 - (i % 2) * 10, 18, g if i % 3 else goods[(k + 2) % 5], 3)


# ------------------------------------------------------------------ army camp
def paint_camp(sc, bg):
    """An army camp: rows of canvas tents, the general's striped tent with flags, stacked muskets, a campfire."""
    time = bg.get("time") or "dusk"
    night = time == "night"
    gy = 640
    r = random.Random(sc.idx * 5 + 9)
    with sc.background((210, 200, 190)) as p:
        sc._sky(p, time, gy)
        haze = (200, 190, 196) if not night else (46, 54, 86)
        hill = (120, 150, 96) if not night else (40, 56, 46)
        pts = [(x, gy - 60 * (0.5 + 0.5 * math.sin(x / 340 + 1))) for x in range(-20, W + 40, 40)]
        p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], lighter(hill, 0.1), 0, wob=0.2)
        sc._ground(p, None, gy + 40, hill if not night else (40, 56, 46))
        canvas = (238, 232, 214) if not night else (130, 126, 130)

        def tent(x, y, s_, col=canvas):
            p.poly([(x - 90 * s_, y), (x, y - 120 * s_), (x + 90 * s_, y)], col, max(2, 5 * s_))
            p.poly([(x - 18 * s_, y), (x, y - 70 * s_), (x + 18 * s_, y)], darker(col, 0.6), max(2, 3 * s_))
            p.line([(x, y - 120 * s_), (x, y - 140 * s_)], max(2, 4 * s_), INK, 0.1)
        for k in range(9):            # far row
            tent(140 + k * 210 + r.randint(-20, 20), gy + 50, 0.5)
        # the general's tent with flags
        gx = 1180
        p.poly([(gx - 200, gy + 150), (gx - 140, gy - 40), (gx + 140, gy - 40), (gx + 200, gy + 150)], canvas, 5)
        for i in range(7):
            if i % 2 == 0:
                xa = gx - 140 + 280 * i / 7
                xb = gx - 200 + 400 * i / 7
                p.poly([(xa, gy - 40), (xa + 40, gy - 40), (xb + 57, gy + 150), (xb, gy + 150)], (60, 90, 170), 0, wob=0)
        p.poly([(gx - 140, gy - 40), (gx, gy - 120), (gx + 140, gy - 40)], canvas, 5)
        p.poly([(gx - 40, gy + 150), (gx, gy + 30), (gx + 40, gy + 150)], darker(canvas, 0.5), 4)
        for fx in (gx - 170, gx + 170):
            p.line([(fx, gy + 150), (fx, gy - 160)], 6, (110, 80, 56), 0.1)
            p.poly([(fx, gy - 160), (fx + 80, gy - 145), (fx, gy - 110)], (200, 50, 50), 4)
        for k, tx in enumerate((240, 520, 1620, 1840)):   # near row
            tent(tx, gy + 200 + (k % 2) * 30, 1.1)
        # stacked muskets
        for sx in (780, 1500):
            for a in (-0.35, 0.0, 0.35):
                p.line([(sx + math.sin(a) * 110, gy + 240), (sx, gy + 110)], 6, (110, 76, 50), 0.1)
        # crates, barrels and the fire pit stones
        p.rect(60, gy + 300, 110, 80, (170, 124, 80), 5)
        far_prop(p, "barrel", 220, gy + 380, 0.5, haze, 0.0)
        for k in range(8):
            a = math.pi * 2 * k / 8
            p.ell(560 + 70 * math.cos(a), gy + 330 + 20 * math.sin(a), 22, 12, (130, 130, 136), 3)
        if night or time == "dusk":
            _glow(p, 560, gy + 280, 300, (255, 190, 110), 0.45 if night else 0.3)

    def fire(p, t):
        k = int(t * 10)
        rr = random.Random(k)
        p.line([(30, 150), (150, 120)], 14, (110, 74, 46), 0.1)
        p.line([(40, 120), (150, 152)], 14, (96, 64, 40), 0.1)
        for col, s_ in (((236, 90, 40), 1.0), ((250, 170, 50), 0.7), ((255, 236, 140), 0.4)):
            pts = []
            for i in range(9):
                a = math.pi * (i / 8)
                rad = 60 * s_ * (1 + rr.uniform(-0.15, 0.15))
                pts.append((90 - math.cos(a) * rad * 0.9, 140 - math.sin(a) * rad * (1.4 if i % 2 else 2.2)))
            p.poly(pts, col, 0, wob=0.4)
    _looping(sc, fire, (470, gy + 160, 180, 180), period=0.6, fps=10)
    plume(sc, 560, gy + 170, "gray", 0.5, 260, 40, seed=3)


WORK_PAINTERS = {"construction": paint_construction, "battlefield": paint_battlefield, "factory": paint_factory,
                 "farm": paint_farm, "mine": paint_mine, "classroom": paint_classroom, "lab": paint_lab,
                 "parliament": paint_parliament, "courtroom": paint_courtroom, "prison": paint_prison,
                 "market": paint_market, "camp": paint_camp}
