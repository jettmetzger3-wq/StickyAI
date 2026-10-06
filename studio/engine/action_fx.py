"""Action moments: props that DO something at a moment in the narration.

  fire      a cannon / tank recoils with a muzzle flash and a puff of smoke (ships fire a broadside); with a
            target the cannonball flies there and explodes
  explode   the prop blows apart: flash, fireball, pieces flying, black smoke
  collapse  a wall, tower or building shakes, breaks into chunks that fall into a dust cloud and a rubble pile
  sink      a ship tilts and slides under the waterline, bubbles rise
  shake     the prop trembles (an earthquake, a cannonball hitting a fort)

Plus the "explosion" prop bursts in (flash, fireball, debris, smoke) before it settles, and sword clash sparks.
Everything is composed from small pre-drawn sprites each frame, so it stays fast and uses little memory.
"""
import math
import random

from PIL import Image

from .doodle import W, H, SS
from .pen import Pen
from .palette import INK, ORANGE

PROP_ACTS = ("fire", "explode", "collapse", "sink", "shake")
PROP_ACT_ALIASES = {"shoot": "fire", "fires": "fire", "shot": "fire", "blast": "fire", "broadside": "fire",
                    "volley": "fire", "salvo": "fire", "launch": "fire", "bombard": "fire",
                    "blow_up": "explode", "blows_up": "explode", "explodes": "explode", "boom": "explode",
                    "destroy": "explode", "destroyed": "explode", "bombed": "explode", "detonate": "explode",
                    "crumble": "collapse", "crumbles": "collapse", "fall": "collapse", "falls": "collapse",
                    "topple": "collapse", "demolish": "collapse", "fall_down": "collapse", "collapses": "collapse",
                    "sinks": "sink", "sunk": "sink", "torpedoed": "sink", "go_down": "sink", "capsize": "sink",
                    "tremble": "shake", "rumble": "shake", "quake": "shake", "shakes": "shake", "wobble": "shake"}
ACT_DUR = {"fire": 1.8, "explode": 2.6, "collapse": 3.0, "sink": 3.6, "shake": 1.2}
ACT_SFX = {"fire": "boom", "explode": "boom", "collapse": "rumble", "sink": "splash"}

# where shots come out (prop units, facing right, feet at 0,0)
MUZZLES = {"cannon": [(173, -101)], "tank": [(217, -144)]}
SHIPS = ("ship", "galleon", "warship", "battleship", "frigate", "steamship", "titanic", "longship", "trireme",
         "junk", "submarine", "carrier", "aircraft_carrier", "u_boat", "uboat")


def resolve_prop_act(v):
    k = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    k = PROP_ACT_ALIASES.get(k, k)
    return k if k in PROP_ACTS else None


# ------------------------------------------------------------------ sprites
def sprite(draw, w, h, seed=1):
    p = Pen(seed, rgba=True, size=(w, h))
    draw(p)
    return p.im.convert("RGBa").resize((int(w), int(h)), Image.LANCZOS).convert("RGBA")


def _puff(p, col, line):
    for cx, cy, r in ((70, 92, 44), (112, 78, 50), (154, 96, 40), (100, 112, 46), (136, 118, 38)):
        p.circ(cx, cy, r, col, 5, line)


_SPRITES = {}


def sprites():
    if _SPRITES:
        return _SPRITES
    _SPRITES["smoke"] = sprite(lambda p: _puff(p, (232, 232, 236), (160, 160, 170)), 220, 170)
    _SPRITES["black"] = sprite(lambda p: _puff(p, (96, 94, 100), (58, 56, 62)), 220, 170)
    _SPRITES["dust"] = sprite(lambda p: _puff(p, (214, 196, 168), (160, 140, 112)), 220, 170)

    def flash(p):
        pts = []
        for i in range(16):
            a = 2 * math.pi * i / 16
            rr = 92 if i % 2 == 0 else 46
            pts.append((100 + math.cos(a) * rr, 100 + math.sin(a) * rr))
        p.poly(pts, (255, 214, 70), 5, ORANGE)
        p.circ(100, 100, 34, (255, 252, 230), 0)
    _SPRITES["flash"] = sprite(flash, 200, 200)

    def burst(p):
        from .props import boom
        boom(p, 160, 160, 140)
        p.circ(160, 160, 44, (255, 246, 210), 0)
    _SPRITES["burst"] = sprite(burst, 320, 320)
    _SPRITES["ball"] = sprite(lambda p: (p.circ(20, 20, 14, (50, 52, 60), 4), p.circ(15, 15, 4, (140, 144, 156), 0)), 40, 40)
    _SPRITES["bubble"] = sprite(lambda p: (p.circ(14, 14, 9, (220, 238, 250), 3, (250, 252, 255)),
                                           p.circ(11, 11, 3, (255, 255, 255), 0)), 28, 28)
    chunks = []
    r = random.Random(4)
    for k in range(8):
        def chunk(p, k=k):
            pts = [(30 + math.cos(a) * r.uniform(10, 24), 30 + math.sin(a) * r.uniform(10, 24))
                   for a in [i * 2 * math.pi / 6 + r.uniform(-0.3, 0.3) for i in range(6)]]
            p.poly(pts, ((84, 76, 70), (120, 110, 96), (60, 60, 66))[k % 3], 4)
        chunks.append(sprite(chunk, 60, 60, seed=k + 3))
    _SPRITES["chunks"] = chunks

    def rubble(p):
        p.poly([(10, 118), (60, 70), (120, 48), (190, 60), (250, 86), (290, 118)], (150, 136, 118), 5)
        for x, y, w, h, c in ((60, 92, 44, 22, (176, 160, 140)), (130, 70, 50, 26, (128, 116, 102)),
                              (190, 88, 46, 24, (166, 150, 128)), (100, 100, 40, 18, (140, 126, 108)),
                              (226, 98, 36, 18, (120, 110, 98))):
            p.rect(x, y, w, h, c, 4, r=4)
    _SPRITES["rubble"] = sprite(rubble, 300, 124)
    return _SPRITES


def faded(img, a):
    if a >= 0.995:
        return img
    im = img.copy()
    im.putalpha(img.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return im


def scaled(img, k):
    if abs(k - 1) < 0.02:
        return img
    return img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.BILINEAR)


def put(canvas, img, cx, cy, k=1.0, a=1.0, rot=0.0):
    """Paste a sprite centered at (cx, cy) on the canvas, scaled, faded and rotated."""
    if a <= 0.01 or k <= 0.01:
        return
    im = scaled(img, k)
    if rot:
        im = im.rotate(rot, resample=Image.BILINEAR, expand=True)
    im = faded(im, a)
    canvas.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2))) \
        if 0 <= int(cx - im.width / 2) and 0 <= int(cy - im.height / 2) and \
        int(cx - im.width / 2) + im.width <= canvas.width and int(cy - im.height / 2) + im.height <= canvas.height \
        else canvas.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def ease_out(q):
    q = min(max(q, 0.0), 1.0)
    return 1 - (1 - q) ** 2


def back(q):
    q = min(max(q, 0.0), 1.0)
    c = 1.9
    return 1 + (c + 1) * (q - 1) ** 3 + c * (q - 1) ** 2


# ------------------------------------------------------------------ a prop that does things
class PropFX:
    """base: the prop's RGBA image with its top-left (bx, by) on screen; anchor (ax, ay): its feet (or center).
    events: [dict(act, t0, dur, target?)] with times in seconds."""

    def __init__(self, name, base, bx, by, s, flip, events, seed=1, burst_in=None):
        self.name, self.base, self.s, self.flip = name, base, s, flip
        self.events = sorted(events, key=lambda e: e["t0"])
        self.burst_in = burst_in            # time the "explosion" prop bursts in
        self.f = -1 if flip else 1
        bw, bh = base.size
        m = int(max(bw, bh) * 0.9 + 160 * s)
        up = int(bh * 0.8 + 200 * s)
        self.box = (bx - m, by - up, bw + 2 * m, bh + up + int(60 * s))
        self.ox, self.oy = m, up                       # base top-left inside the box
        self.r = random.Random(seed)
        self.sp = sprites()
        self._pieces = None
        self._last = (None, None)
        self._still = {}
        self.sounds = [(e["t0"], ACT_SFX[e["act"]]) for e in self.events if ACT_SFX.get(e["act"])]
        if burst_in is not None:
            self.sounds.append((burst_in, "boom"))

    # local geometry
    @property
    def cx(self):
        return self.ox + self.base.width / 2

    @property
    def bottom(self):
        return self.oy + self.base.height

    def pieces(self):
        """The base cut into chunks (for collapse / explode), each with its own random motion."""
        if self._pieces is None:
            bw, bh = self.base.size
            cols = 4 if bw > bh * 0.6 else 3
            rows = 4 if bh > bw * 0.6 else 3
            out = []
            a = self.base.getchannel("A")
            for i in range(cols):
                for j in range(rows):
                    x0, y0 = int(bw * i / cols), int(bh * j / rows)
                    x1, y1 = int(bw * (i + 1) / cols), int(bh * (j + 1) / rows)
                    if a.crop((x0, y0, x1, y1)).getbbox() is None:
                        continue
                    pc = self.base.crop((x0, y0, x1, y1))
                    bb = pc.getbbox()
                    if not bb:
                        continue
                    pc = pc.crop(bb)
                    out.append(dict(img=pc, x=self.ox + x0 + bb[0] + pc.width / 2, y=self.oy + y0 + bb[1] + pc.height / 2,
                                    row=j, rows=rows, vx=self.r.uniform(-90, 90), spin=self.r.uniform(-160, 160),
                                    delay=self.r.uniform(0.0, 0.25), up=self.r.uniform(350, 750)))
            self._pieces = out
        return self._pieces

    def frame(self, t):
        if self._last[0] == round(t, 3):
            return self._last[1]
        # between and after the action moments nothing changes: reuse the drawing
        state = tuple("before" if t < e["t0"] else "after" if t - e["t0"] > max(e["dur"] + 1.6, 3.7) else None
                      for e in self.events)
        busy = None in state or (self.burst_in is not None and 0 <= t - self.burst_in < 0.5)
        if not busy:
            key = (state, self.burst_in is not None and t >= self.burst_in)
            hit = self._still.get(key)
            if hit is None:
                hit = self._still[key] = self._draw(t)
            return hit
        out = self._draw(t)
        self._last = (round(t, 3), out)
        return out

    def _draw(self, t):
        s, f = self.s, self.f
        canvas = Image.new("RGBA", (int(self.box[2]), int(self.box[3])), (0, 0, 0, 0))
        dx = dy = rot = 0.0
        show, clip, pulse = True, None, 1.0
        later = []                                          # drawn on top of the base
        for e in self.events:
            te = t - e["t0"]
            if te < 0:
                continue
            act, d = e["act"], e["dur"]
            if act == "shake":
                if te < d:
                    k = 1 - te / d
                    dx += 7 * s * k * math.sin(te * 70)
                    dy += 3 * s * k * math.sin(te * 53 + 1)
            elif act == "fire":
                later.append((self._fire, e, te))
                if te < 0.6:
                    dx += -f * 24 * s * (math.exp(-te * 7) * (1 - math.exp(-te * 60)))
            elif act == "sink":
                q = min(1.0, te / d)
                rot += f * 20 * ease_out(min(1.0, q * 1.6))
                dy += (self.base.height * 1.25) * q * q
                clip = self.bottom - self.base.height * 0.2
                later.append((self._bubbles, e, te))
            elif act == "collapse":
                if te < 0.35:
                    dx += 6 * s * math.sin(te * 80)
                else:
                    show = False
                    later.append((self._collapse, e, te))
            elif act == "explode":
                if te >= 0.04:
                    show = False
                later.append((self._explode, e, te))
        if self.burst_in is not None:
            tb = t - self.burst_in
            if tb < 0.5:
                pulse = back(tb / 0.45)
                later.append((self._burst_in, None, tb))
        if show:
            im = self.base
            if abs(pulse - 1) > 0.01:
                im = scaled(im, max(0.02, pulse))
            if rot:
                im = im.rotate(rot, resample=Image.BILINEAR, expand=True)
            x = self.cx + dx - im.width / 2
            y = self.oy + self.base.height / 2 + dy - im.height / 2
            canvas.paste(im, (int(x), int(y)), im)
            if clip is not None:
                canvas.paste((0, 0, 0, 0), (0, int(clip), canvas.width, canvas.height))
        for fn, e, te in later:
            fn(canvas, e, te)
        return canvas

    # ---------------------------------------------------------------- effects
    def _muzzles(self):
        base = self.name
        s, f = self.s, self.f
        if base in MUZZLES:
            pts = MUZZLES[base]
        elif base in SHIPS:
            w = self.base.width / s
            pts = [(k * w * 0.22, -min(0.3 * self.base.height / s, 100)) for k in (-1, 0, 1)]
        else:
            pts = [(self.base.width / s / 2, -self.base.height / s * 0.6)]
        return [(self.cx + f * px * s, self.bottom + py * s) for px, py in pts]

    def _fire(self, canvas, e, te):
        s, f = self.s, self.f
        sp = self.sp
        for k, (mx, my) in enumerate(self._muzzles()):
            tk = te - k * 0.12
            if tk < 0:
                continue
            if tk < 0.14:
                put(canvas, sp["flash"], mx + f * 30 * s, my, (0.7 + tk * 3) * s, 1.0)
            for j in range(3):
                tj = tk - 0.04 - j * 0.07
                if 0 <= tj < 1.8:
                    q = tj / 1.8
                    put(canvas, sp["smoke"], mx + f * (40 + 160 * ease_out(q) + j * 30) * s,
                        my - (20 * j + 90 * q) * s, (0.35 + 0.9 * ease_out(q)) * s, 1 - q ** 1.5)

    def _bubbles(self, canvas, e, te):
        q = te / e["dur"]
        if q < 0.25 or te > e["dur"] + 1.5:
            return
        wl = self.bottom - self.base.height * 0.2
        for k in range(10):
            ph = (te * 0.9 + k * 0.37) % 1.4
            if ph > 1.0:
                continue
            x = self.cx + (k - 4.5) * self.base.width * 0.06 + 10 * math.sin(te * 3 + k)
            y = wl + 160 * self.s * (1 - ph)
            put(canvas, self.sp["bubble"], x, y, (0.6 + 0.6 * (k % 3) / 2) * self.s * 1.4, min(1.0, (1 - ph) * 3))

    def _collapse(self, canvas, e, te):
        s = self.s
        tl = te - 0.35
        g = 2400 * s
        ground = self.bottom
        for pc in self.pieces():
            tp = tl - pc["delay"] * (1 - pc["row"] / max(1, pc["rows"]))
            if tp < 0:
                canvas.paste(pc["img"], (int(pc["x"] - pc["img"].width / 2), int(pc["y"] - pc["img"].height / 2)), pc["img"])
                continue
            y = pc["y"] + 0.5 * g * tp * tp
            x = pc["x"] + pc["vx"] * s * tp
            a = 1.0 if y < ground - pc["img"].height * 0.2 else max(0.0, 1 - (y - ground + pc["img"].height * 0.2) / 60)
            if a <= 0:
                continue
            put(canvas, pc["img"], x, y, 1.0, a, pc["spin"] * tp)
        # rubble pile and dust
        q = min(1.0, max(0.0, (tl - 0.15) / 0.5))
        if q > 0:
            rw = self.base.width * 0.9 / 300
            put(canvas, self.sp["rubble"], self.cx, ground - 50 * rw * q + 12 * s, rw, 1.0)
        for k in range(6):
            tk = tl - 0.05 * k
            if 0 <= tk < 2.8:
                qq = tk / 2.8
                x = self.cx + (k - 2.5) * self.base.width * 0.2 * (1 + qq * 0.6)
                put(canvas, self.sp["dust"], x, ground - (40 + 90 * qq) * s, (0.4 + 1.3 * ease_out(qq)) * s * 1.2,
                    1 - qq ** 1.4)

    def _explode(self, canvas, e, te):
        s = self.s
        cx, cy = self.cx, self.oy + self.base.height * 0.55
        sp = self.sp
        if te < 0.16:
            put(canvas, sp["flash"], cx, cy, (1.5 + te * 6) * s, 1.0)
        if te < 0.8:
            put(canvas, sp["burst"], cx, cy, back(te / 0.25) * s * max(0.6, self.base.width / 360),
                1.0 if te < 0.5 else 1 - (te - 0.5) / 0.3)
        g = 1700 * s
        for pc in self.pieces():
            vx = (pc["x"] - cx) * 2.2 + pc["vx"] * s
            vy = -pc["up"] * s + (pc["y"] - cy) * 1.2
            x, y = pc["x"] + vx * te, pc["y"] + vy * te + 0.5 * g * te * te
            a = 1.0 if te < 1.0 else max(0.0, 1 - (te - 1.0) / 0.5)
            if a > 0:
                put(canvas, pc["img"], x, y, max(0.3, 1 - te * 0.25), a, pc["spin"] * 2 * te)
        for k in range(5):
            tk = te - 0.15 - 0.1 * k
            if 0 <= tk < 3.0:
                q = tk / 3.0
                put(canvas, sp["black"], cx + (k - 2) * 50 * s * (1 + q), cy - (30 + 260 * q) * s,
                    (0.5 + 1.2 * ease_out(q)) * s * max(0.7, self.base.width / 400), 1 - q ** 1.3)

    def _burst_in(self, canvas, e, tb):
        s = self.s
        cx, cy = self.cx, self.oy + self.base.height / 2
        if tb < 0.15:
            put(canvas, self.sp["flash"], cx, cy, (1.6 + tb * 6) * s, 1.0)
        for k, ch in enumerate(self.sp["chunks"]):
            a = 2 * math.pi * k / len(self.sp["chunks"]) + 0.3
            sp_ = (520 + 80 * (k % 3)) * s
            x = cx + math.cos(a) * sp_ * tb
            y = cy + math.sin(a) * sp_ * tb - 300 * s * tb + 0.5 * 1800 * s * tb * tb
            put(canvas, ch, x, y, s * 0.9, 1 - tb / 0.5, 300 * tb * (1 if k % 2 else -1))


def burst_at(x, y, s, t0, seed=1):
    """A standalone explosion (a cannonball landing, a bomb): flash, fireball, debris and smoke, then nothing."""
    blank = Image.new("RGBA", (int(220 * s), int(220 * s)), (0, 0, 0, 0))
    fx = PropFX("burst", blank, x - blank.width / 2, y - blank.height / 2, s, False,
                [dict(act="explode", t0=t0, dur=2.6)], seed)
    fx._pieces = []
    return fx


# ------------------------------------------------------------------ sword fights
def spark_sprite():
    sp = sprites()
    if "spark" not in sp:
        def spark(p):
            for i in range(8):
                a = 2 * math.pi * i / 8 + 0.2
                p.line([(60 + math.cos(a) * 12, 60 + math.sin(a) * 12), (60 + math.cos(a) * (40 + 14 * (i % 2)),
                                                                          60 + math.sin(a) * (40 + 14 * (i % 2)))],
                       7, (255, 214, 70), 0.2)
            p.circ(60, 60, 14, (255, 252, 220), 0)
        sp["spark"] = sprite(spark, 120, 120)
    return sp["spark"]


SLASH_CYCLE = 0.42          # one raise-and-strike of a sword (see puppet.py "slash")


def strike_times(t0, dur):
    out, k = [], 0
    while True:
        t = t0 + SLASH_CYCLE * (0.45 + k) + 0.03
        if t >= t0 + dur:
            return out
        out.append(t)
        k += 1
