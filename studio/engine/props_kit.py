"""Small drawing kit for detailed props.

`Sk` draws in a prop's own coordinates: 1 unit = 1 px at scale 1, origin = the prop's anchor point (bottom-center
for things standing on the ground, the middle for "center" props), y grows downward. It can rotate and mirror the
whole drawing, and outline widths shrink and grow with the prop's scale so small props stay crisp.
"""
import math

from .palette import INK, WHITE, darker, lighter

# shared colors
STONE = (226, 214, 188)
STONE_D = (186, 172, 146)
MARBLE = (246, 244, 238)
MARBLE_D = (214, 216, 226)
WOOD = (176, 122, 78)
WOOD_D = (128, 86, 54)
WOOD_L = (206, 160, 112)
IRON = (96, 100, 112)
IRON_D = (62, 64, 74)
STEEL = (178, 184, 196)
GOLD = (236, 190, 64)
GOLD_D = (190, 140, 40)
BRICK = (192, 84, 64)
SLATE = (66, 78, 98)
COPPER = (112, 182, 164)
COPPER_D = (78, 140, 124)
GLASS = (172, 214, 238)
LEAF = (104, 168, 84)
LEAF_D = (66, 128, 62)
SAND = (232, 200, 140)
SAND_D = (200, 162, 104)
SNOW = (246, 250, 255)
ICE = (196, 230, 246)
WATER = (120, 186, 222)
FLAME = (246, 150, 50)
FLAME_Y = (252, 222, 90)
DARKWIN = (70, 74, 92)
CREAM = (252, 246, 228)


class Sk:
    def __init__(self, p, x, y, s=1.0, rot=0.0, flip=False, wob=0.5):
        self.p, self.x, self.y, self.s = p, x, y, s
        self.rot = rot
        self.ca, self.sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        self.fx = -1 if flip else 1
        self.wob = wob

    # ---------- coordinates
    def pt(self, a, b):
        a *= self.fx
        a, b = a * self.ca - b * self.sa, a * self.sa + b * self.ca
        return (self.x + a * self.s, self.y + b * self.s)

    def P(self, pts):
        return [self.pt(a, b) for a, b in pts]

    def lw(self, w):
        return max(1.2, w * self.s) if w else 0

    # ---------- shapes
    def poly(self, pts, fill=None, w=5, col=INK, close=True):
        if len(pts) >= 2:
            self.p.poly(self.P(pts), fill, self.lw(w), col, self.wob, close)

    def line(self, pts, w=5, col=INK):
        if len(pts) >= 2:
            self.p.line(self.P(pts), self.lw(w), col, self.wob)

    def rect(self, x0, y0, x1, y1, fill=None, w=5, col=INK, r=0):
        if r and not self.rot:
            a, b = self.pt(x0, y0), self.pt(x1, y1)
            self.p.rect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]), abs(b[1] - a[1]), fill, self.lw(w), col,
                        r=r * self.s)
        elif r:
            self.poly(rounded(x0, y0, x1, y1, r), fill, w, col)
        else:
            self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, w, col)

    def circ(self, cx, cy, r, fill=None, w=5, col=INK):
        X, Y = self.pt(cx, cy)
        self.p.circ(X, Y, r * self.s, fill, self.lw(w), col)

    def ell(self, cx, cy, rx, ry, fill=None, w=5, col=INK):
        if self.rot:
            self.poly(ellipse(cx, cy, rx, ry, 28), fill, w, col)
        else:
            X, Y = self.pt(cx, cy)
            self.p.ell(X, Y, rx * self.s, ry * self.s, fill, self.lw(w), col)

    def arc(self, cx, cy, rx, ry, a0, a1, w=5, col=INK, n=18):
        self.line(arc_pts(cx, cy, rx, ry, a0, a1, n), w, col)

    def text(self, t, cx, cy, size, col=INK, stroke=0, scol=WHITE, f="bold"):
        X, Y = self.pt(cx, cy)
        self.p.text(str(t), X, Y, size * self.s, col, stroke=stroke * self.s, scol=scol, f=f)

    # ---------- details
    def flame(self, cx, by, w=60, h=100, lit=True):
        """A two-tone flame standing on (cx, by)."""
        self.poly([(cx - w / 2, by), (cx - w * 0.42, by - h * 0.45), (cx - w * 0.18, by - h * 0.62),
                   (cx - w * 0.1, by - h * 0.4), (cx + w * 0.05, by - h), (cx + w * 0.3, by - h * 0.55),
                   (cx + w * 0.42, by - h * 0.7), (cx + w / 2, by - h * 0.3), (cx + w * 0.4, by)], FLAME, 4)
        self.poly([(cx - w * 0.25, by), (cx - w * 0.15, by - h * 0.35), (cx + w * 0.02, by - h * 0.62),
                   (cx + w * 0.18, by - h * 0.3), (cx + w * 0.22, by)], FLAME_Y, 0)

    def wheel(self, cx, cy, r, fill=WOOD, spokes=8, hub=None):
        self.circ(cx, cy, r, fill, 6)
        self.circ(cx, cy, r * 0.78, None, 3, darker(fill, 0.6))
        for i in range(spokes):
            a = 2 * math.pi * i / spokes
            self.line([(cx, cy), (cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r * 0.8)], 4, darker(fill, 0.55))
        self.circ(cx, cy, r * 0.18, hub or darker(fill, 0.7), 3)

    def windows(self, x0, y0, x1, y1, cols, rows, fill=GLASS, pad=0.28, w=3, lit=None):
        cw, rh = (x1 - x0) / cols, (y1 - y0) / rows
        for i in range(cols):
            for j in range(rows):
                f = fill
                if lit and (i * 7 + j * 3) % 5 == 0:
                    f = lit
                self.rect(x0 + cw * (i + pad / 2), y0 + rh * (j + pad / 2), x0 + cw * (i + 1 - pad / 2),
                          y0 + rh * (j + 1 - pad / 2), f, w)

    def crenels(self, x0, x1, top, size=18, fill=STONE, w=4):
        """Battlements: merlons standing on the line y = top between x0 and x1."""
        n = max(2, int((x1 - x0) / (size * 1.8)))
        step = (x1 - x0) / n
        for i in range(n):
            a = x0 + i * step + step * 0.12
            self.rect(a, top - size, a + step * 0.62, top + 2, fill, w)

    def stripes(self, profile, cx, base, w, h, colors, n=6, twist=0.0):
        """Vertical (or twisted) stripes over a dome described by `profile` (see onion())."""
        prof = [(px, py) for px, py in profile if px <= 0]
        prof.sort(key=lambda q: -q[1])
        for k in range(n):
            if k % 2 == 0:
                continue
            u0, u1 = -1 + 2 * k / n, -1 + 2 * (k + 1) / n
            left, right = [], []
            for px, py in prof:
                t = -py
                r = -px * w
                sh = twist * t
                a = max(-1.0, min(1.0, u0 + sh))
                b = max(-1.0, min(1.0, u1 + sh))
                left.append((cx + r * a, base + py * h))
                right.append((cx + r * b, base + py * h))
            self.poly(left + right[::-1], colors[k % len(colors)], 0)


# ---------- point helpers (all in local units)
def arc_pts(cx, cy, rx, ry, a0, a1, n=18):
    """Degrees, 0 = right, 90 = down (screen convention)."""
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def ellipse(cx, cy, rx, ry, n=24):
    return arc_pts(cx, cy, rx, ry, 0, 360, n)[:-1]


def rounded(x0, y0, x1, y1, r, n=5):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = []
    for cx, cy, a in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        pts += arc_pts(cx, cy, r, r, a, a + 90, n)
    return pts


def arch(cx, bottom, w, spring, kind="round", n=12):
    """An arch opening: straight sides from `bottom` up to y = spring, then a round / pointed top."""
    hw = w / 2
    pts = [(cx - hw, bottom), (cx - hw, spring)]
    if kind == "pointed":
        for i in range(1, n + 1):
            t = i / n
            pts.append((cx - hw + hw * t, spring - hw * 1.25 * math.sin(t * math.pi / 2) ** 0.8))
        top = pts[-1]
        right = [(2 * cx - px, py) for px, py in pts[2:-1]][::-1]
        pts = pts[:-1] + [top] + right
    else:
        pts += arc_pts(cx, spring, hw, hw, 180, 360, n)[1:-1]
    pts += [(cx + hw, spring), (cx + hw, bottom)]
    return pts


ONION = [(-0.5, 0), (-0.6, -0.12), (-0.66, -0.28), (-0.62, -0.46), (-0.48, -0.62), (-0.3, -0.76), (-0.14, -0.88),
         (-0.05, -0.96), (0, -1.0)]
DOME = [(-0.5, 0), (-0.5, -0.12), (-0.47, -0.3), (-0.4, -0.48), (-0.3, -0.62), (-0.17, -0.72), (0, -0.76)]


def profile_pts(profile, cx, base, w, h):
    left = [(cx + px * w, base + py * h) for px, py in profile]
    right = [(cx - px * w, base + py * h) for px, py in profile[::-1][1:]]
    return left + right


def star_pts(cx, cy, r, inner=0.45, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else r * inner
        a = math.radians(rot + 180 * i / n)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def shade(col, k=0.82):
    return darker(col, k)


def light(col, k=0.35):
    return lighter(col, k)
