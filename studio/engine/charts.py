"""Infographics that animate: bar charts that grow (with numbers ticking up), horizontal "ranking" bars, line
charts that draw themselves, a timeline with year markers and a travelling "you are here" marker, size
comparisons (circles whose area matches the numbers) and then-vs-now split screens.

Static parts (axes, labels, the finished line) are drawn once with the anti-aliased pen; each frame only adds
the moving bits, so charts stay fast and light on memory.
"""
import math

from PIL import Image, ImageDraw

from .pen import Pen
from .palette import INK, WHITE, RED, NAVY, color as C, darker
from . import warmap as WM

SERIES = ((214, 62, 52), (48, 76, 150), (70, 150, 82), (236, 150, 50), (128, 84, 160), (40, 150, 160),
          (190, 160, 60), (110, 110, 120))


def _finish(p, w, h):
    return p.im.convert("RGBa").resize((int(w), int(h)), Image.LANCZOS).convert("RGBA")


def blank(w=1, h=1):
    return Image.new("RGBA", (max(1, int(w)), max(1, int(h))), (0, 0, 0, 0))


def ease_out(q):
    q = min(max(q, 0.0), 1.0)
    return 1 - (1 - q) ** 3


def fmt(v, prefix="", suffix="", decimals=0):
    return WM.fmt_count(v, "number", prefix, suffix, decimals)


class TextCache:
    """Small text sprites (value labels that tick), drawn once per distinct string."""

    def __init__(self, size, col, scol):
        self.size, self.col, self.scol = size, col, scol
        self.cache = {}

    def get(self, txt):
        im = self.cache.get(txt)
        if im is None:
            w, h = int(self.size * (0.62 * len(txt) + 1.2)), int(self.size * 1.6)
            p = Pen(2, rgba=True, size=(w, h))
            p.text(txt, w / 2, h / 2, self.size, self.col, stroke=max(4, self.size / 9), scol=self.scol)
            im = _finish(p, w, h)
            if len(self.cache) > 400:
                self.cache.clear()
            self.cache[txt] = im
        return im


class Chart:
    """style: bar (columns), hbar (horizontal bars, good for rankings) or line. data: [(label, value, color)]."""

    def __init__(self, style, data, x, y, w, h, title="", t0=0.0, dur=1.6, prefix="", suffix="", decimals=0,
                 vmax=None, dark=False):
        self.style, self.data = style, data
        self.t0, self.dur = t0, max(0.4, dur)
        self.prefix, self.suffix, self.decimals = prefix, suffix, decimals
        self.box = (x - w / 2, y - h / 2, w, h)
        self.w, self.h = w, h
        ink = (238, 240, 246) if dark else INK
        halo = (24, 26, 36) if dark else WHITE
        self.ink, self.halo = ink, halo
        vals = [v for _, v, _ in data] or [1.0]
        self.vmax = float(vmax) if vmax else max(max(vals), 1e-9) * 1.08
        self.vmin = min(0.0, min(vals))
        top = 70 if title else 16
        n = len(data)
        self.text = TextCache(46 if n <= 5 else 38 if n <= 8 else 32, ink, halo)
        p = Pen(7, rgba=True, size=(w, h))
        if title:
            p.text(title, w / 2, 36, 60, ink, stroke=9, scol=halo)
        if style == "hbar":
            lab_w = min(320, max(len(l) for l, _, _ in data) * 26 + 30) if data else 200
            self.plot = (lab_w, top + 10, w - lab_w - 150, h - top - 20)
            px, py, pw, ph = self.plot
            p.line([(px, py - 6), (px, py + ph + 6)], 6, ink, 0.2)
            slot = ph / max(1, n)
            self.bar_t = slot * 0.62
            for i, (lab, v, col) in enumerate(data):
                cy = py + slot * (i + 0.5)
                p.text(lab[:18], px - 16, cy, min(46, slot * 0.5), ink, anchor="rm", stroke=6, scol=halo)
        else:
            self.plot = (60, top + 50, w - 100, h - top - 50 - 64)
            px, py, pw, ph = self.plot
            p.line([(px, py - 10), (px, py + ph), (px + pw + 10, py + ph)], 6, ink, 0.2)
            slot = pw / max(1, n)
            for i, (lab, v, col) in enumerate(data):
                cx = px + slot * (i + 0.5)
                p.text(lab[:14], cx, py + ph + 38, min(44, max(24, slot * 0.24)), ink, stroke=6, scol=halo)
            if style == "line":
                pts = [self._pt(i, v) for i, (_, v, _) in enumerate(data)]
                line_col = data[0][2] if data else RED
                p2 = Pen(8, rgba=True, size=(w, h))
                if len(pts) >= 2:
                    p2.line(pts, 18, halo, 0.3)
                    p2.line(pts, 11, line_col, 0.3)
                for (qx, qy) in pts:
                    p2.circ(qx, qy, 11, WHITE, 5, line_col)
                self.line_img = _finish(p2, w, h)
                self.pts = pts
        self.base = _finish(p, w, h)
        self._still = None

    def _pt(self, i, v):
        px, py, pw, ph = self.plot
        slot = pw / max(1, len(self.data))
        return px + slot * (i + 0.5), py + ph - ph * (v - self.vmin) / (self.vmax - self.vmin)

    def frame(self, t):
        tl = t - self.t0
        n = len(self.data)
        stagger = min(0.3, 1.2 / max(1, n))
        end = self.dur + stagger * n + 0.1
        if tl >= end and self._still is not None:
            return self._still
        out = self.base.copy()
        if self.style == "line":
            self._line(out, tl)
        else:
            d = ImageDraw.Draw(out)
            for i, (lab, v, col) in enumerate(self.data):
                q = ease_out((tl - i * stagger) / self.dur)
                if q <= 0:
                    continue
                self._bar(out, d, i, v * q, col)
        if tl >= end:
            self._still = out
        return out

    def _bar(self, out, d, i, v, col):
        px, py, pw, ph = self.plot
        n = len(self.data)
        lab = self.text.get(fmt(v, self.prefix, self.suffix, self.decimals))
        if self.style == "hbar":
            slot = ph / max(1, n)
            cy = py + slot * (i + 0.5)
            L = pw * max(0.0, v) / self.vmax
            if L > 2:
                d.rounded_rectangle([px, cy - self.bar_t / 2, px + L, cy + self.bar_t / 2], radius=8, fill=col,
                                    outline=self.ink, width=5)
            out.alpha_composite(lab, (int(min(px + L + 10, self.w - lab.width)), int(cy - lab.height / 2)))
        else:
            slot = pw / max(1, n)
            bw = slot * 0.6
            cx = px + slot * (i + 0.5)
            top = py + ph - ph * max(0.0, v) / self.vmax
            if py + ph - top > 2:
                d.rounded_rectangle([cx - bw / 2, top, cx + bw / 2, py + ph], radius=8, fill=col, outline=self.ink,
                                    width=5)
            out.alpha_composite(lab, (int(cx - lab.width / 2), int(max(0, top - lab.height - 2))))

    def _line(self, out, tl):
        q = ease_out(tl / self.dur)
        if q <= 0:
            return
        px, py, pw, ph = self.plot
        x_end = self.pts[0][0] + (self.pts[-1][0] - self.pts[0][0]) * q if len(self.pts) > 1 else self.pts[0][0]
        mask = Image.new("L", out.size, 0)
        ImageDraw.Draw(mask).rectangle([0, 0, x_end + 12, out.height], fill=255)
        out.paste(self.line_img, (0, 0), Image.composite(self.line_img.getchannel("A"), mask, mask))
        # value at the tip
        k = min(len(self.pts) - 1, max(0, int(q * (len(self.pts) - 1) + 1e-6)))
        if len(self.pts) > 1:
            seg = q * (len(self.pts) - 1)
            i = min(int(seg), len(self.pts) - 2)
            f = seg - i
            v = self.data[i][1] + (self.data[i + 1][1] - self.data[i][1]) * f
            tx = self.pts[i][0] + (self.pts[i + 1][0] - self.pts[i][0]) * f
            ty = self.pts[i][1] + (self.pts[i + 1][1] - self.pts[i][1]) * f
        else:
            v, (tx, ty) = self.data[0][1], self.pts[0]
        lab = self.text.get(fmt(v, self.prefix, self.suffix, self.decimals))
        out.alpha_composite(lab, (int(min(max(0, tx - lab.width / 2), self.w - lab.width)), int(max(0, ty - lab.height - 16))))


# ------------------------------------------------------------------ timeline
class Timeline:
    """A horizontal time axis; events pop in as markers with labels; a marker travels to the current event."""

    def __init__(self, x0, x1, y, y_from, y_to, events, col, dark=False):
        self.x0, self.x1, self.y = x0, x1, y
        self.y_from, self.y_to = y_from, max(y_to, y_from + 1)
        self.events = events                 # [(t, year, label)]
        self.col = col
        self.ink = (238, 240, 246) if dark else INK
        self.halo = (24, 26, 36) if dark else WHITE
        self.box = (x0 - 80, y - 60, x1 - x0 + 160, 120)

    def xof(self, year):
        return self.x0 + (self.x1 - self.x0) * (year - self.y_from) / (self.y_to - self.y_from)

    def draw_axis(self, p, ticks):
        p.line([(self.x0, self.y), (self.x1, self.y)], 12, self.ink, 0.2)
        p.poly([(self.x1 + 34, self.y), (self.x1 + 2, self.y - 20), (self.x1 + 2, self.y + 20)], self.ink, 0)
        for yr in ticks:
            x = self.xof(yr)
            p.line([(x, self.y - 16), (x, self.y + 16)], 6, self.ink, 0.2)
            p.text(WM.fmt_count(yr, "year"), x, self.y + 48, 36, self.ink, stroke=6, scol=self.halo)


def nice_ticks(a, b, n=6):
    span = max(1, b - a)
    step = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 5, 10):
        if span / (step * m) <= n:
            step *= m
            break
    first = math.ceil(a / step) * step
    out = []
    v = first
    while v <= b + 1e-9:
        out.append(int(v))
        v += step
    return out


def marker(p, x, y, col, r=16):
    p.poly([(x, y - r * 2.6), (x - r, y - r * 1.2), (x + r, y - r * 1.2)], col, 4, INK, 0.2)
    p.circ(x, y - r * 2.2, r, col, 5, INK)


# ------------------------------------------------------------------ then vs now
class SplitTint:
    """The "then" half of a then-vs-now split screen in old-photo sepia."""

    def __init__(self, side="left", strength=0.55):
        self.side, self.k = side, strength
        self._solid = None

    def apply(self, fr, t):
        w, h = fr.size
        x0, x1 = (0, w // 2) if self.side == "left" else (w // 2, w)
        half = fr.crop((x0, 0, x1, h))
        g = half.convert("L").convert("RGB")
        if self._solid is None or self._solid.size != g.size:
            self._solid = Image.new("RGB", g.size, (176, 140, 96))
        sep = Image.blend(g, self._solid, 0.32)
        half = Image.blend(half.convert("RGB"), sep, self.k)
        fr.paste(half.convert(fr.mode), (x0, 0))
        return fr
