"""Maps that live: empires that grow and shrink over the years (with the year ticking), capitals marked with a
pulsing star, routes that draw themselves with a ship or caravan riding the tip, and zooming from one map to a
closer one (see render.py "mapzoom").
"""
import math

from PIL import Image, ImageDraw

from .doodle import W, H, SS
from .pen import Pen
from .palette import INK, WHITE, YELLOW
from . import warmap as WM

STEP_FADE = 0.75            # seconds an empire takes to change shape
YEAR_SIZE = 96


def _finish(p, w, h):
    return p.im.convert("RGBa").resize((int(w), int(h)), Image.LANCZOS).convert("RGBA")


def blank(w=1, h=1):
    return Image.new("RGBA", (max(1, int(w)), max(1, int(h))), (0, 0, 0, 0))


# ------------------------------------------------------------------ empires over time
class Empire:
    """steps: [(t seconds, geometry, year or None)]; draws each step once and blends between them."""

    def __init__(self, sc, steps, col, outline, label=None):
        self.steps = steps
        self.bc = any(y is not None and y < 0 for _, _, y in steps)
        imgs = []
        for t, g, year in steps:
            p = Pen(sc.seed + 41, rgba=True, size=(W, H))
            sc._draw_terr(p, sc.view.in_view(g) if g is not None else None, col, outline)
            imgs.append(_finish(p, W, H))
        boxes = [im.getbbox() for im in imgs if im.getbbox()]
        if not boxes:
            self.box = (0, 0, 1, 1)
            self.imgs = [blank() for _ in imgs]
            return
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        self.box = (x0, y0, x1 - x0, y1 - y0)
        self.imgs = [im.crop((x0, y0, x1, y1)) for im in imgs]
        self._mix = {}
        # each change spreads out from the middle of the old borders (the empire's heartland)
        self.centers = []
        for _, g, _ in steps:
            gg = sc.view.in_view(g) if g is not None else None
            c = gg.representative_point() if gg is not None and not gg.is_empty else None
            cx, cy = sc.view.xy(c.x, c.y) if c is not None else (x0 + (x1 - x0) / 2, y0 + (y1 - y0) / 2)
            self.centers.append((cx - x0, cy - y0))
        w, h = x1 - x0, y1 - y0
        self.reach = [max(math.hypot(cx - px, cy - py) for px in (0, w) for py in (0, h)) for cx, cy in self.centers]

    def frame(self, t):
        st = self.steps
        if t < st[0][0]:
            return self.imgs[0]
        for k in range(len(st) - 1):
            ta, tb = st[k][0], st[k + 1][0]
            if t < tb:
                return self.imgs[k]
            if t < tb + STEP_FADE:
                q = (t - tb) / STEP_FADE
                q = q * q * (3 - 2 * q)
                key = (k, round(q * 30))
                im = self._mix.get(key)
                if im is None:
                    # a wave spreading from the old heartland: inside it the new borders, outside the old ones
                    cx, cy = self.centers[k]
                    r = self.reach[k] * key[1] / 30
                    mask = Image.new("L", self.imgs[k].size, 0)
                    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
                    im = Image.composite(self.imgs[k + 1], self.imgs[k], mask)
                    if len(self._mix) > 70:
                        self._mix.clear()
                    self._mix[key] = im
                return im
        return self.imgs[-1]

    def year_at(self, t):
        """The year shown at time t: ticks from one step's year to the next while the shape changes."""
        st = [(t0, y) for t0, _, y in self.steps if y is not None]
        if not st:
            return None
        if t <= st[0][0]:
            return st[0][1]
        for (ta, ya), (tb, yb) in zip(st, st[1:]):
            if t < tb:
                return ya
            if t < tb + STEP_FADE:
                q = (t - tb) / STEP_FADE
                return ya + (yb - ya) * (1 - (1 - q) ** 2)
        return st[-1][1]


class YearLabel:
    """A big year in a corner that ticks along with an empire."""

    def __init__(self, year_at, x, y, size=YEAR_SIZE, dark=False, bc=False):
        self.year_at, self.x, self.y, self.size, self.dark, self.bc = year_at, x, y, size, dark, bc
        w, h = size * 4.6, size * 1.5
        self.box = (x - w / 2, y - h / 2, w, h)
        self._cache = {}

    def frame(self, t):
        v = self.year_at(t)
        if v is None:
            return blank()
        txt = WM.fmt_count(v, "year", suffix=" AD" if self.bc and round(v) > 0 else "")
        im = self._cache.get(txt)
        if im is None:
            w, h = self.box[2], self.box[3]
            p = Pen(3, rgba=True, size=(w, h))
            if self.dark:
                p.text(txt, w / 2, h / 2, self.size, (245, 246, 250), stroke=10, scol=(20, 24, 40))
            else:
                p.text(txt, w / 2, h / 2, self.size, INK, stroke=10, scol=WHITE)
            im = _finish(p, w, h)
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[txt] = im
        return im


# ------------------------------------------------------------------ capitals
def capital_star(p, x, y, r=22, col=YELLOW, line=INK):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    p.poly(pts, col, 5, line, 0.2)


class Ring:
    """A ring that ripples out from a capital when it appears (twice), drawing the eye to it."""

    def __init__(self, x, y, t0, col=(230, 60, 50)):
        self.x, self.y, self.t0, self.col = x, y, t0, col
        self.box = (x - 90, y - 90, 180, 180)

    def frame(self, t):
        q = t - self.t0
        if not 0 <= q < 1.4:
            return blank()
        im = blank(180, 180)
        d = ImageDraw.Draw(im)
        for k in (0.0, 0.45):
            u = (q - k) / 0.9
            if 0 <= u < 1:
                r = 14 + 70 * u
                a = int(255 * (1 - u))
                d.ellipse([90 - r, 90 - r, 90 + r, 90 + r], outline=self.col + (a,), width=6)
        return im


# ------------------------------------------------------------------ routes that draw themselves
class Route:
    """A dashed (or solid) path that draws itself; a prop (ship, camel, horse...) or a little walker rides the tip."""

    def __init__(self, pts, col, width, style, t0, dur, icon=None, icon_scale=1.0, seed=1):
        self.t0, self.dur = t0, max(0.3, dur)
        pts = WM.resample(pts, max(24, int(sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])) / 12)))
        pad = 110 * max(1.0, icon_scale) if icon else 30
        self.box = WM.bbox(pts, pad)
        bx, by = self.box[0], self.box[1]
        self.local = [(x - bx, y - by) for x, y in pts]
        w, h = self.box[2], self.box[3]
        p = Pen(seed, rgba=True, size=(w, h))
        if style == "solid":
            p.line(self.local, width + 6, WHITE, 0.3)
            p.line(self.local, width, col, 0.3)
        else:
            dash, gap = (6, 18) if style == "dotted" else (26, 16)
            self._dashes(p, dash, gap, width, col)
        self.full = _finish(p, w, h)
        self.icon, self.icon_scale = icon, icon_scale
        self.width = width
        self._done = None
        self._icons = {}

    def _dashes(self, p, dash, gap, width, col):
        acc, on, seg = 0.0, True, [self.local[0]]
        for a, b in zip(self.local, self.local[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            pos = 0.0
            while pos < d:
                left = (dash if on else gap) - acc
                step = min(left, d - pos)
                pos += step
                acc += step
                q = pos / d if d else 1
                pt = (a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q)
                if on:
                    seg.append(pt)
                if acc >= (dash if on else gap) - 1e-6:
                    if on and len(seg) > 1:
                        p.line(seg, width + 5, WHITE, 0.2)
                        p.line(seg, width, col, 0.2)
                    on = not on
                    acc = 0.0
                    seg = [pt]
        if on and len(seg) > 1:
            p.line(seg, width + 5, WHITE, 0.2)
            p.line(seg, width, col, 0.2)

    def icon_img(self, left):
        im = self._icons.get(left)
        if im is None:
            from .registry import resolve_prop, PROPS, prop_bounds, prop_anchor
            from .pen import resolve_kind
            target = 110 * self.icon_scale                  # icon size in px
            size = int(target * 1.5 + 40)
            p = Pen(5, rgba=True, size=(size, size))
            prop = resolve_prop(self.icon)
            if prop:
                x0, y0, x1, y1 = prop_bounds(prop, {"flip": left})
                k = target / max(1.0, x1 - x0, y1 - y0)
                cy = size / 2 + ((y1 - y0) * k / 2 if prop_anchor(prop, {}) == "bottom" else 0)
                PROPS[prop][1](p, size / 2, cy, k, None, {"flip": left})
            else:
                k = target / 400
                p.stick(size / 2, size / 2 + 190 * k, k, resolve_kind(self.icon), arms=((25, 15), (25, 15)),
                        flip=left, shadow=False)
            im = _finish(p, size, size)
            self._icons[left] = im
        return im

    def frame(self, t):
        q = (t - self.t0) / self.dur
        if q <= 0:
            return blank()
        if q >= 1 and self._done is not None:
            return self._done
        q = min(1.0, q)
        qq = 1 - (1 - q) ** 1.6
        w, h = self.full.size
        # reveal the drawn path up to qq with a thick mask polyline
        n = max(2, int(len(self.local) * qq) + 1)
        (tx, ty), ang = WM.along(self.local, qq)
        pts = self.local[:n - 1] + [(tx, ty)]
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).line(pts, fill=255, width=int(self.width * 2 + 22), joint="curve")
        out = blank(w, h)
        out.paste(self.full, (0, 0), Image.composite(self.full.getchannel("A"), mask, mask))
        if self.icon:
            left = math.cos(ang) < 0
            ic = self.icon_img(left)
            out.alpha_composite(ic, (int(max(0, min(tx - ic.width / 2, w - ic.width))),
                                     int(max(0, min(ty - ic.height * 0.62, h - ic.height)))))
        if q >= 1.0:
            self._done = out
        return out


def view_zoom(prev_bg, bg):
    """For two map scenes in a row: ('in'|'out', focus x, focus y, factor) when the second is a closer (or wider)
    view of a place inside the first, else None."""
    from .geo import View
    try:
        ca, cb = prev_bg.get("center") or [0, 30], bg.get("center") or [0, 30]
        wa, wb = float(prev_bg.get("width") or 40), float(bg.get("width") or 40)
        va, vb = View(float(ca[0]), float(ca[1]), wa), View(float(cb[0]), float(cb[1]), wb)
    except (TypeError, ValueError):
        return None
    if wa / wb >= 1.6:
        x, y = va.xy(float(cb[0]), float(cb[1]))
        if 0 <= x <= W and 0 <= y <= H:
            return "in", x, y, min(wa / wb, 6.0)
    if wb / wa >= 1.6:
        x, y = vb.xy(float(ca[0]), float(ca[1]))
        if 0 <= x <= W and 0 <= y <= H:
            return "out", x, y, min(wb / wa, 6.0)
    return None


def zoom_frame(im, fx, fy, k):
    """im scaled by k around (fx, fy), the point moving to the center of the frame as k grows."""
    k = max(1.0, k)
    if k < 1.001:
        return im
    # crop a W/k x H/k window that slides from the whole frame toward the focus point
    u = (k - 1) / k
    cx = W / 2 + (fx - W / 2) * min(1.0, u * 1.25)
    cy = H / 2 + (fy - H / 2) * min(1.0, u * 1.25)
    cw, ch = W / k, H / k
    x0 = min(max(cx - cw / 2, 0), W - cw)
    y0 = min(max(cy - ch / 2, 0), H - ch)
    return im.transform((W, H), Image.AFFINE, (cw / W, 0, x0, 0, ch / H, y0), Image.BILINEAR)


def compose_mapzoom(a, b, info, p):
    """Frame p (0..1) of zooming from map a into map b (or out of a into b)."""
    from .core import ease_io
    q = ease_io(p)
    way, fx, fy, k = info
    a, b = a.convert("RGB"), b.convert("RGB")
    if way == "in":
        za = zoom_frame(a, fx, fy, 1 + (k - 1) * q)
        if q < 0.55:
            return za
        return Image.blend(za, b, min(1.0, (q - 0.55) / 0.45))
    zb = zoom_frame(b, fx, fy, k - (k - 1) * q)
    if q < 0.45:
        return Image.blend(a, zb, q / 0.45)
    return zb
