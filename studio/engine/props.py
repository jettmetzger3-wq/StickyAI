"""Helper props that take a Pen as first argument (ported from the first video), plus pose constants."""
import math

from .doodle import SS
from .palette import INK, RED, NAVY, YELLOW, BROWN, WHITE, GRAY, ORANGE, PAPER
from .pen import ARMS, LEGS

AD, UP, CHEER, SHRUG = ARMS["down"], ARMS["up"], ARMS["cheer"], ARMS["shrug"]
HIPS, CROSS, POINT_R, POINT_L = ARMS["hips"], ARMS["cross"], ARMS["point_right"], ARMS["point_left"]
WAVE_R, THINK, HOLD_R = ARMS["wave"], ARMS["think"], ARMS["hold"]
STAND, WALK, RUN, WIDE = LEGS["stand"], LEGS["walk"], LEGS["run"], LEGS["wide"]


def _lines(text):
    return str(text).split("\n")


def bubble(p, x, y, w, h, text, size=44, tail=(-60, 70), f="bold", col=INK, fill=WHITE):
    p.rect(x - w / 2, y - h / 2, w, h, fill, 6, r=min(40, h / 2.2))
    tx, ty = x + tail[0], y + h / 2 + tail[1]
    p.poly([(x + tail[0] * 0.3 - 26, y + h / 2 - 6), (tx, ty), (x + tail[0] * 0.3 + 26, y + h / 2 - 6)], fill, 0, wob=0)
    p.line([(x + tail[0] * 0.3 - 26, y + h / 2 - 3), (tx, ty), (x + tail[0] * 0.3 + 26, y + h / 2 - 3)], 6, INK, 0.3)
    lines = _lines(text)
    for i, ln in enumerate(lines):
        p.text(ln, x, y + (i - (len(lines) - 1) / 2) * size * 1.15, size, col, f=f)


def sign(p, x, y, w, h, text, size=48, col=INK, board=(236, 205, 150)):
    p.rect(x - 9, y, 18, 170, BROWN, 5)
    p.rect(x - w / 2, y - h, w, h, board, 6, r=10)
    lines = _lines(text)
    for i, ln in enumerate(lines):
        p.text(ln, x, y - h / 2 + (i - (len(lines) - 1) / 2) * size * 1.1, size, col, f="bold")


def table(p, x, y, w, col=BROWN):
    p.rect(x - w / 2, y, w, 26, col, 6, r=6)
    p.rect(x - w / 2 + 30, y + 26, 20, 120, col, 5)
    p.rect(x + w / 2 - 50, y + 26, 20, 120, col, 5)


def door(p, x, y, w=220, h=380, col=(150, 108, 74)):
    p.rect(x - w / 2, y - h, w, h, col, 7, r=6)
    p.circ(x + w / 2 - 34, y - h / 2, 12, YELLOW, 4)


def clock(p, x, y, r, frac=0.25, col=WHITE):
    p.circ(x, y, r, col, 8)
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.line([(x + math.sin(a) * r * 0.82, y - math.cos(a) * r * 0.82), (x + math.sin(a) * r * 0.92, y - math.cos(a) * r * 0.92)], 5, INK, 0.2)
    a = 2 * math.pi * frac
    p.line([(x, y), (x + math.sin(a) * r * 0.75, y - math.cos(a) * r * 0.75)], 9, INK, 0.2)
    p.line([(x, y), (x + math.sin(a * 12) * r * 0.5, y - math.cos(a * 12) * r * 0.5)], 11, INK, 0.2)
    p.circ(x, y, 10, RED, 0)


def gauge(p, x, y, r, frac, low="E", high="F"):
    p.d.pieslice([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], 180, 360, fill=WHITE, outline=INK, width=8 * SS)
    p.d.pieslice([(x - r * 0.9) * SS, (y - r * 0.9) * SS, (x + r * 0.9) * SS, (y + r * 0.9) * SS], 180, 210, fill=(240, 120, 110))
    p.text(low, x - r * 0.72, y - r * 0.22, r * 0.25, RED)
    p.text(high, x + r * 0.72, y - r * 0.22, r * 0.25, INK)
    a = math.pi * (1 - frac)
    p.line([(x, y), (x + math.cos(a) * r * 0.8, y - math.sin(a) * r * 0.8)], 10, RED, 0.2)
    p.circ(x, y, 16, INK, 0)


def pie(p, x, y, r, frac, c1=NAVY, c2=(225, 225, 230)):
    frac = min(max(float(frac), 0.0), 1.0)
    p.d.pieslice([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], -90, -90 + 360 * frac, fill=c1, outline=INK, width=7 * SS)
    p.d.pieslice([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS], -90 + 360 * frac, 270, fill=c2, outline=INK, width=7 * SS)


def bike(p, x, y, s=1):
    for dx in (-70, 70):
        p.circ(x + dx * s, y - 50 * s, 48 * s, None, 7 * s)
        p.circ(x + dx * s, y - 50 * s, 6 * s, INK, 0)
    p.line([(x - 70 * s, y - 50 * s), (x - 10 * s, y - 120 * s), (x + 50 * s, y - 120 * s), (x + 70 * s, y - 50 * s)], 7 * s, RED, 0.3)
    p.line([(x - 10 * s, y - 120 * s), (x + 5 * s, y - 50 * s), (x - 70 * s, y - 50 * s)], 7 * s, RED, 0.3)
    p.line([(x + 50 * s, y - 120 * s), (x + 45 * s, y - 150 * s)], 6 * s, INK, 0.2)


def mousetrap(p, x, y, s=1):
    p.rect(x - 160 * s, y - 40 * s, 320 * s, 40 * s, (225, 190, 130), 6 * s, r=8 * s)
    p.line([(x - 120 * s, y - 40 * s), (x - 120 * s, y - 110 * s), (x + 110 * s, y - 110 * s), (x + 110 * s, y - 40 * s)], 8 * s, (160, 160, 170), 0.3)
    p.poly([(x - 40 * s, y - 42 * s), (x + 60 * s, y - 42 * s), (x + 40 * s, y - 100 * s)], YELLOW, 5 * s)
    for cx, cy in ((x + 10 * s, y - 60 * s), (x + 32 * s, y - 72 * s)):
        p.circ(cx, cy, 6 * s, (230, 190, 50), 0)


def subscribe(p, x, y, s=1):
    p.rect(x - 230 * s, y - 60 * s, 460 * s, 120 * s, (225, 40, 40), 7 * s, r=26 * s)
    p.text("SUBSCRIBE", x, y, 62 * s, WHITE, f="bold")


def note(p, x, y, text, size=46, w=300, h=200):
    p.rect(x - w / 2, y - h / 2, w, h, (255, 236, 120), 5)
    p.circ(x, y - h / 2 + 14, 12, RED, 4)
    lines = _lines(text)
    for i, ln in enumerate(lines):
        p.text(ln, x, y + 10 + (i - (len(lines) - 1) / 2) * size * 1.05, size, INK, f="hand")


def board(p, x, y, w, h, title="", lines=(), size=52, title_col=RED, fill=(255, 255, 250)):
    """A whiteboard/list: title on top, handwritten lines below. (x, y) = center."""
    p.rect(x - w / 2, y - h / 2, w, h, fill, 7, r=12)
    top = y - h / 2
    if title:
        p.text(title, x, top + size * 0.95, size * 1.15, title_col)
        top += size * 1.7
    n = max(1, len(lines))
    avail = (y + h / 2 - 20) - top
    step = min(size * 1.45, avail / n)
    for i, ln in enumerate(lines):
        p.text(ln, x - w / 2 + 40, top + step * (i + 0.5), size, INK, anchor="lm", f="hand")


def xmark(p, x, y, r=60, w=18):
    p.line([(x - r, y - r), (x + r, y + r)], w, RED, 0.5)
    p.line([(x + r, y - r), (x - r, y + r)], w, RED, 0.5)


def check(p, x, y, r=50, w=18):
    p.line([(x - r, y), (x - r * 0.3, y + r * 0.7), (x + r, y - r * 0.8)], w, (60, 170, 80), 0.4)


def boom(p, x, y, r=110, c1=(255, 210, 80), c2=ORANGE):
    pts = []
    for i in range(22):
        a = 2 * math.pi * i / 22
        rr = r if i % 2 == 0 else r * 0.55
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    p.poly(pts, c2, 6)
    pts2 = [(x + (px - x) * 0.6, y + (py - y) * 0.6) for px, py in pts]
    p.poly(pts2, c1, 0)


def chart(p, x, y, w, h, pts, col=RED):
    """Line chart. (x, y) = origin (bottom-left); pts = [(0..1, 0..1), ...]."""
    p.line([(x, y - h), (x, y), (x + w, y)], 7, INK, 0.3)
    P = [(x + w * a, y - h * b) for a, b in pts]
    if len(P) < 2:
        return
    p.line(P, 12, col, 0.5)
    (xa, ya), (xb, yb) = P[-2], P[-1]
    a = math.atan2(yb - ya, xb - xa)
    p.poly([(xb + math.cos(a) * 26, yb + math.sin(a) * 26), (xb + math.cos(a + 2.4) * 34, yb + math.sin(a + 2.4) * 34),
            (xb + math.cos(a - 2.4) * 34, yb + math.sin(a - 2.4) * 34)], col, 4)


def car(p, x, y, s=1, col=(220, 70, 60)):
    p.poly([(x - 120 * s, y - 30 * s), (x - 110 * s, y - 70 * s), (x - 60 * s, y - 75 * s), (x - 35 * s, y - 115 * s),
            (x + 50 * s, y - 115 * s), (x + 80 * s, y - 75 * s), (x + 120 * s, y - 68 * s), (x + 125 * s, y - 30 * s)], col, 6 * s)
    p.rect(x - 25 * s, y - 105 * s, 40 * s, 28 * s, (180, 220, 240), 4 * s)
    p.rect(x + 22 * s, y - 105 * s, 40 * s, 28 * s, (180, 220, 240), 4 * s)
    for dx in (-70, 70):
        p.circ(x + dx * s, y - 28 * s, 26 * s, (50, 50, 56), 6 * s)
        p.circ(x + dx * s, y - 28 * s, 9 * s, GRAY, 0)


def tv(p, x, y, s=1):
    p.rect(x - 90 * s, y - 150 * s, 180 * s, 130 * s, (140, 110, 80), 6 * s, r=14 * s)
    p.rect(x - 70 * s, y - 135 * s, 120 * s, 100 * s, (170, 215, 235), 5 * s, r=12 * s)
    p.circ(x + 68 * s, y - 110 * s, 7 * s, INK, 0)
    p.line([(x - 20 * s, y - 150 * s), (x - 50 * s, y - 200 * s)], 5 * s, INK, 0.2)
    p.line([(x + 10 * s, y - 150 * s), (x + 40 * s, y - 200 * s)], 5 * s, INK, 0.2)


def ballot(p, x, y, s=1):
    p.rect(x - 90 * s, y - 140 * s, 180 * s, 140 * s, (230, 230, 240), 6 * s, r=8 * s)
    p.rect(x - 50 * s, y - 145 * s, 100 * s, 12 * s, INK, 0)
    p.rect(x - 30 * s, y - 210 * s, 60 * s, 80 * s, WHITE, 5 * s)
    p.line([(x - 15 * s, y - 175 * s), (x - 3 * s, y - 160 * s), (x + 18 * s, y - 192 * s)], 6 * s, (60, 170, 80), 0.2)


def dove(p, x, y, s=1):
    p.ell(x, y, 70 * s, 34 * s, WHITE, 6 * s)
    p.circ(x + 64 * s, y - 24 * s, 24 * s, WHITE, 6 * s)
    p.poly([(x + 84 * s, y - 26 * s), (x + 108 * s, y - 18 * s), (x + 84 * s, y - 14 * s)], YELLOW, 4 * s)
    p.poly([(x - 20 * s, y - 10 * s), (x + 10 * s, y - 100 * s), (x + 30 * s, y - 10 * s)], WHITE, 6 * s)
    p.circ(x + 70 * s, y - 28 * s, 4 * s, INK, 0)
    p.line([(x + 100 * s, y - 14 * s), (x + 150 * s, y + 10 * s)], 6 * s, (90, 150, 70), 0.3)


def puppet(p, x, y, s=1, kind="china"):
    p.stick(x, y, s, kind, arms=((80, 40), (80, 40)), legs=((20, 10), (20, 10)), mouth="flat", eyes="dot", shadow=False)
    for hx in (x - 100 * s, x + 100 * s, x):
        p.line([(hx, y - (480 if hx == x else 220) * s), (hx, -50)], 3, (90, 90, 100), 0.2)


def bars(p, x, y, n, per_row, icon, gap, s):
    for i in range(n):
        icon(p, x + (i % per_row) * gap, y - (i // per_row) * gap * 0.7, s)


def mini_carrier(p, x, y, s):
    p.poly([(x - 30 * s, y), (x + 30 * s, y), (x + 24 * s, y + 8 * s), (x - 24 * s, y + 8 * s)], (150, 160, 170), 2.5)
    p.rect(x - 30 * s, y - 3 * s, 60 * s, 3 * s, (95, 100, 110), 1.5)
    p.rect(x + 8 * s, y - 11 * s, 8 * s, 8 * s, WHITE, 1.5)


def palace(p, x, y, s=1):
    p.rect(x - 260 * s, y - 160 * s, 520 * s, 160 * s, (240, 236, 225), 6 * s)
    p.poly([(x - 320 * s, y - 160 * s), (x + 320 * s, y - 160 * s), (x + 240 * s, y - 250 * s), (x - 240 * s, y - 250 * s)], (70, 80, 90), 6 * s)
    p.poly([(x - 180 * s, y - 250 * s), (x + 180 * s, y - 250 * s), (x + 120 * s, y - 320 * s), (x - 120 * s, y - 320 * s)], (70, 80, 90), 6 * s)
    for i in range(5):
        p.rect(x - 220 * s + i * 100 * s, y - 120 * s, 50 * s, 120 * s, (150, 110, 80), 4 * s)


def screen(p, x, y, w=420, h=360):
    for i in range(4):
        p.poly([(x - w / 2 + i * w / 4, y - h + (i % 2) * 14), (x - w / 2 + (i + 1) * w / 4, y - h + ((i + 1) % 2) * 14),
                (x - w / 2 + (i + 1) * w / 4, y), (x - w / 2 + i * w / 4, y)], (240, 222, 180), 6)
        p.circ(x - w / 2 + i * w / 4 + w / 8, y - h * 0.55, 24, (225, 180, 70), 3)


def rewind(p, x, y, label=""):
    p.rect(x - 150, y - 70, 300, 140, INK, 0, r=24)
    p.poly([(x - 90, y), (x - 20, y - 50), (x - 20, y + 50)], WHITE, 0)
    p.poly([(x - 10, y), (x + 60, y - 50), (x + 60, y + 50)], WHITE, 0)
    if label:
        p.text(label, x, y + 120, 52, INK)
