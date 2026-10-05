"""Doodle drawing primitives and props.

Everything is drawn at 2x (SS) and later downsampled with LANCZOS, which gives smooth lines.
Coordinates passed to these methods are always in 1920x1080 screen pixels.
Most props take (x, y) = bottom-center, plus a scale `s`.
"""
import math
import random

from PIL import Image, ImageDraw

from .fonts import font
from .palette import (INK, PAPER, SEA, SEA2, LAND, RED, NAVY, GREEN, GRAY, DGRAY, ORANGE, SKIN, BROWN,
                      YELLOW, WHITE, darker, lighter)

W, H, SS = 1920, 1080, 2


class Canvas:
    def __init__(self, seed=1, bg=PAPER):
        self.rnd = random.Random(seed)
        self.im = Image.new("RGB", (W * SS, H * SS), bg)
        self.d = ImageDraw.Draw(self.im)

    # ---------- primitives ----------
    def j(self, a=2.0):
        return self.rnd.uniform(-a, a) * SS

    def line(self, pts, w=6, col=INK, wob=1.5):
        P = [(x * SS + self.j(wob), y * SS + self.j(wob)) for x, y in pts]
        self.d.line(P, fill=col, width=max(1, int(w * SS)), joint="curve")
        for x, y in (P[0], P[-1]):
            r = w * SS / 2
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=col)

    def poly(self, pts, fill=None, w=6, col=INK, wob=1.5, close=True):
        P = [(x * SS + self.j(wob), y * SS + self.j(wob)) for x, y in pts]
        if fill:
            self.d.polygon(P, fill=fill)
        if w:
            Q = P + [P[0]] if close else P
            self.d.line(Q, fill=col, width=max(1, int(w * SS)), joint="curve")

    def rect(self, x, y, w_, h_, fill=None, w=6, col=INK, r=0):
        if w_ < 0:
            x, w_ = x + w_, -w_
        if h_ < 0:
            y, h_ = y + h_, -h_
        if r:
            r = min(r, w_ / 2, h_ / 2)
            self.d.rounded_rectangle([x * SS, y * SS, (x + w_) * SS, (y + h_) * SS], radius=max(0, r * SS),
                                     fill=fill, outline=col if w else None, width=int(w * SS))
        else:
            self.poly([(x, y), (x + w_, y), (x + w_, y + h_), (x, y + h_)], fill, w, col, 1.2)

    def circ(self, x, y, r, fill=None, w=6, col=INK):
        self.d.ellipse([(x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS],
                       fill=fill, outline=col if w else None, width=int(w * SS))

    def ell(self, x, y, rx, ry, fill=None, w=6, col=INK):
        self.d.ellipse([(x - rx) * SS, (y - ry) * SS, (x + rx) * SS, (y + ry) * SS],
                       fill=fill, outline=col if w else None, width=int(w * SS))

    def chord(self, x0, y0, x1, y1, a0, a1, fill, w=6, col=INK):
        self.d.chord([x0 * SS, y0 * SS, x1 * SS, y1 * SS], a0, a1, fill=fill, outline=col, width=int(w * SS))

    def blob(self, cx, cy, rx, ry, fill, w=6, col=INK, n=14, rough=0.22, seed=0):
        r = random.Random(seed or int(cx * 7 + cy * 3))
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n
            k = 1 + r.uniform(-rough, rough)
            pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
        self.poly(pts, fill, w, col, 1.0)

    def text(self, s, x, y, size=60, col=INK, anchor="mm", stroke=0, scol=WHITE, f="bold"):
        self.d.text((x * SS, y * SS), s, font=font(f, size * SS), fill=col, anchor=anchor,
                    stroke_width=int(stroke * SS), stroke_fill=scol)

    # ---------- backgrounds ----------
    def sea(self, y=0, col=SEA):
        self.d.rectangle([0, y * SS, W * SS, H * SS], fill=col)
        for i in range(26):
            x = self.rnd.randint(0, W)
            yy = self.rnd.randint(max(y, 0) + 30, H)
            self.line([(x, yy), (x + 40, yy - 8), (x + 80, yy)], 4, SEA2, 1)

    def sunburst(self, x, y, r=200, col=(255, 236, 170)):
        for i in range(16):
            a = 2 * math.pi * i / 16
            self.poly([(x, y), (x + 1500 * math.cos(a - 0.08), y + 1500 * math.sin(a - 0.08)),
                       (x + 1500 * math.cos(a + 0.08), y + 1500 * math.sin(a + 0.08))], col, 0, wob=0)

    # ================================================================ props
    def cloud(self, x, y, s=1, col=WHITE):
        for dx, dy, r in [(-50, 10, 40), (0, -10, 55), (55, 8, 42), (20, 25, 40), (-20, 25, 40)]:
            self.circ(x + dx * s, y + dy * s, r * s, col, 0)
        self.line([(x - 90 * s, y + 45 * s), (x + 95 * s, y + 45 * s)], 4, (210, 215, 225), 0)

    def smoke(self, x, y, s=1, col=DGRAY):
        for i, r in enumerate([22, 30, 38, 46]):
            self.circ(x + i * 10 * s, y - i * 38 * s, r * s, col, 5, INK)

    def flame(self, x, y, s=1):
        self.poly([(x - 30 * s, y), (x - 18 * s, y - 55 * s), (x, y - 25 * s), (x + 10 * s, y - 85 * s),
                   (x + 28 * s, y - 30 * s), (x + 36 * s, y)], ORANGE, 5)
        self.poly([(x - 12 * s, y), (x, y - 38 * s), (x + 8 * s, y - 15 * s), (x + 18 * s, y)], YELLOW, 0)

    def ship(self, x, y, s=1, col=GRAY, flag=None, tilt=0, sunk=0):
        y += sunk * 30
        self.poly([(x - 120 * s, y), (x + 130 * s, y), (x + 95 * s, y + 45 * s), (x - 90 * s, y + 45 * s)], col, 6)
        self.rect(x - 55 * s, y - 40 * s, 110 * s, 40 * s, (225, 225, 232), 5)
        self.rect(x - 15 * s, y - 80 * s, 36 * s, 40 * s, (205, 205, 215), 5)
        self.rect(x + 40 * s, y - 28 * s, 50 * s, 8 * s, DGRAY, 4)
        self.line([(x - 100 * s, y + 55 * s), (x - 60 * s, y + 48 * s), (x - 20 * s, y + 55 * s),
                   (x + 20 * s, y + 48 * s), (x + 60 * s, y + 55 * s), (x + 100 * s, y + 48 * s)], 4, WHITE, 1)
        if flag:
            self.line([(x + 3 * s, y - 80 * s), (x + 3 * s, y - 130 * s)], 4, INK, 0.3)
            self.poly([(x + 3 * s, y - 130 * s), (x + 50 * s, y - 120 * s), (x + 3 * s, y - 108 * s)], flag, 3)

    def carrier(self, x, y, s=1, hit=False):
        self.poly([(x - 150 * s, y), (x + 150 * s, y), (x + 120 * s, y + 38 * s), (x - 120 * s, y + 38 * s)], (150, 160, 170), 6)
        self.rect(x - 150 * s, y - 14 * s, 300 * s, 14 * s, (95, 100, 110), 5)
        self.rect(x + 40 * s, y - 55 * s, 40 * s, 41 * s, (215, 215, 225), 5)
        if hit:
            self.smoke(x - 60 * s, y - 20 * s, s * 0.9)
            self.flame(x - 20 * s, y - 14 * s, s * 0.8)

    def plane(self, x, y, s=1, ang=0, col=(215, 218, 226)):
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))

        def T(px, py):
            return (x + (px * ca - py * sa) * s, y + (px * sa + py * ca) * s)
        self.poly([T(-70, -12), T(60, -12), T(85, 0), T(60, 12), T(-70, 12), T(-95, -8)], col, 5, wob=0.8)
        self.poly([T(-10, -2), T(-35, -62), T(10, -62), T(25, -2)], col, 5, wob=0.8)
        self.poly([T(-10, 2), T(-35, 62), T(10, 62), T(25, 2)], col, 5, wob=0.8)
        self.poly([T(-80, -4), T(-100, -32), T(-78, -30)], col, 5, wob=0.8)
        px, py = T(88, 0)
        self.circ(px, py, 7 * s, RED, 3)
        self.line([T(90, -30), T(90, 30)], 4, DGRAY, 0.3)

    def barrel(self, x, y, s=1, empty=False):
        self.rect(x - 45 * s, y - 60 * s, 90 * s, 120 * s, BROWN, 6, r=22 * s)
        for dy in (-30, 25):
            self.line([(x - 44 * s, y + dy * s), (x + 44 * s, y + dy * s)], 5, (80, 55, 38), 0.5)
        if not empty:
            self.poly([(x, y - 22 * s), (x - 14 * s, y + 4 * s), (x, y + 18 * s), (x + 14 * s, y + 4 * s)], (30, 30, 36), 3)
        else:
            self.line([(x - 18 * s, y - 15 * s), (x + 18 * s, y + 20 * s)], 5, RED, 0.5)
            self.line([(x + 18 * s, y - 15 * s), (x - 18 * s, y + 20 * s)], 5, RED, 0.5)

    def land(self, cx, cy, rx, ry, col=LAND, seed=0, n=14, rough=0.25):
        self.blob(cx, cy, rx, ry, col, 7, INK, n, rough, seed)

    def island(self, x, y, s=1, col=GREEN):
        self.blob(x, y, 110 * s, 38 * s, (240, 215, 150), 6, seed=int(x))
        self.blob(x, y - 10 * s, 70 * s, 22 * s, col, 0, seed=int(x) + 1)
        self.line([(x + 20 * s, y - 20 * s), (x + 30 * s, y - 85 * s)], 6, BROWN, 1)
        for a in (-60, -20, 25, 65):
            ex = x + 30 * s + math.sin(math.radians(a)) * 55 * s
            ey = y - 85 * s + math.cos(math.radians(a)) * 20 * s
            self.line([(x + 30 * s, y - 85 * s), (ex, ey)], 6, (60, 140, 70), 1)

    def hourglass(self, x, y, s=1, fill=0.2, col=(30, 30, 36)):
        self.poly([(x - 55 * s, y - 100 * s), (x + 55 * s, y - 100 * s), (x + 8 * s, y), (x + 55 * s, y + 100 * s),
                   (x - 55 * s, y + 100 * s), (x - 8 * s, y)], (240, 245, 250), 7)
        self.poly([(x - 40 * s, y + 92 * s), (x + 40 * s, y + 92 * s), (x + 25 * s, y + (92 - 90 * (1 - fill)) * s),
                   (x - 25 * s, y + (92 - 90 * (1 - fill)) * s)], col, 0)
        if fill < 0.9:
            self.poly([(x - 36 * s, y - 92 * s), (x + 36 * s, y - 92 * s), (x + 4 * s, y - 14 * s - 60 * s * fill),
                       (x - 4 * s, y - 14 * s - 60 * s * fill)], col, 0)
        self.line([(x, y - 14 * s), (x, y + 60 * s)], 4, col, 0)
        self.rect(x - 65 * s, y - 112 * s, 130 * s, 14 * s, BROWN, 6)
        self.rect(x - 65 * s, y + 98 * s, 130 * s, 14 * s, BROWN, 6)

    def doc(self, x, y, w=140, h=190, lines=5, rot=0):
        self.rect(x, y, w, h, (255, 255, 250), 5)
        for i in range(lines):
            yy = y + 28 + i * (h - 50) / max(lines, 1)
            self.line([(x + 18, yy), (x + w - 18 - (i % 2) * 30, yy)], 4, (150, 150, 160), 0.5)

    def lock(self, x, y, s=1):
        self.line([(x - 30 * s, y - 25 * s), (x - 30 * s, y - 65 * s), (x - 15 * s, y - 90 * s), (x + 15 * s, y - 90 * s),
                   (x + 30 * s, y - 65 * s), (x + 30 * s, y - 25 * s)], 12, DGRAY, 0.6)
        self.rect(x - 52 * s, y - 25 * s, 104 * s, 80 * s, YELLOW, 6, r=12 * s)
        self.circ(x, y + 12 * s, 9 * s, INK, 0)

    def candle(self, x, y, s=1):
        self.rect(x - 14 * s, y - 70 * s, 28 * s, 70 * s, (255, 250, 235), 5)
        self.flame(x, y - 70 * s, 0.35 * s)

    def lantern(self, x, y, s=1, lit=False):
        self.ell(x, y, 26 * s, 34 * s, YELLOW if lit else (225, 220, 205), 5)
        self.line([(x, y - 34 * s), (x, y - 52 * s)], 4)
        self.line([(x - 14 * s, y - 28 * s), (x + 14 * s, y - 28 * s)], 3)

    def mushroom(self, x, y, s=1):
        self.rect(x - 28 * s, y - 140 * s, 56 * s, 140 * s, (235, 225, 205), 6)
        for dx, dy, r in [(0, -190, 90), (-80, -150, 55), (80, -150, 55), (-35, -240, 55), (45, -235, 55)]:
            self.circ(x + dx * s, y + dy * s, r * s, (248, 232, 215), 6)

    def city(self, x, y, n=7, burn=False, s=1):
        r = random.Random(int(x))
        cx = x
        for i in range(n):
            w_ = r.randint(60, 100) * s
            h_ = r.randint(90, 210) * s
            self.rect(cx, y - h_, w_, h_, (205, 195, 180), 5)
            for wy in range(int(y - h_ + 20 * s), int(y - 25 * s), max(1, int(44 * s))):
                self.rect(cx + 14 * s, wy, 18 * s, 22 * s, YELLOW if not burn else ORANGE, 3)
            if burn and i % 2 == 0:
                self.flame(cx + w_ / 2, y - h_, 0.9 * s)
            cx += w_ + 8 * s

    def fort(self, x, y, s=1):
        self.rect(x - 160 * s, y - 140 * s, 320 * s, 140 * s, (210, 195, 170), 6)
        for i in range(6):
            self.rect(x - 160 * s + i * 56 * s, y - 170 * s, 36 * s, 30 * s, (210, 195, 170), 5)
        self.rect(x - 40 * s, y - 80 * s, 80 * s, 80 * s, (90, 70, 55), 5)

    def cannon(self, x, y, s=1, flip=1):
        if flip >= 0:
            self.rect(x - 70 * s, y - 20 * s, 140 * s, 36 * s, DGRAY, 6, r=14 * s)
        else:
            self.rect(x - 70 * s, y - 20 * s, 140 * s, 36 * s, DGRAY, 6, r=14 * s)
        self.circ(x - 30 * s * (1 if flip >= 0 else -1), y + 30 * s, 28 * s, BROWN, 6)

    def factory(self, x, y, s=1):
        self.rect(x - 200 * s, y - 130 * s, 400 * s, 130 * s, (190, 100, 85), 6)
        for i in range(3):
            self.rect(x - 160 * s + i * 120 * s, y - 280 * s + i * 20 * s, 44 * s, 150 * s - i * 20 * s, (160, 80, 70), 6)
            self.smoke(x - 138 * s + i * 120 * s, y - 290 * s + i * 20 * s, 0.7 * s)
        for i in range(5):
            self.rect(x - 170 * s + i * 76 * s, y - 90 * s, 44 * s, 40 * s, YELLOW, 4)

    def bomb(self, x, y, s=1, ang=0):
        self.ell(x, y, 22 * s, 34 * s, DGRAY, 5)
        self.poly([(x - 14 * s, y - 38 * s), (x + 14 * s, y - 38 * s), (x + 22 * s, y - 62 * s), (x - 22 * s, y - 62 * s)], DGRAY, 4)

    def helmet(self, x, y, s=1):
        self.poly([(x - 55 * s, y), (x - 50 * s, y - 38 * s), (x, y - 60 * s), (x + 50 * s, y - 38 * s), (x + 55 * s, y)], BROWN, 6)
        self.circ(x - 6 * s, y - 14 * s, 22 * s, (225, 225, 235), 5)
        self.line([(x - 60 * s, y), (x + 60 * s, y)], 7)

    def radio(self, x, y, s=1):
        self.rect(x - 80 * s, y - 55 * s, 160 * s, 110 * s, BROWN, 6, r=14 * s)
        self.circ(x - 35 * s, y, 30 * s, (235, 225, 190), 5)
        self.circ(x + 40 * s, y - 15 * s, 8 * s, INK, 0)
        self.circ(x + 40 * s, y + 15 * s, 8 * s, INK, 0)
        self.line([(x + 50 * s, y - 55 * s), (x + 85 * s, y - 120 * s)], 5)

    def crowd(self, x, y, n=6, s=1, hats=False):
        for i in range(n):
            fx = x + i * 70 * s + (i % 2) * 12
            self.circ(fx, y - 70 * s, 22 * s, SKIN, 5)
            self.line([(fx, y - 48 * s), (fx, y)], 5)
            self.line([(fx, y), (fx - 14 * s, y + 38 * s)], 5)
            self.line([(fx, y), (fx + 14 * s, y + 38 * s)], 5)
            self.line([(fx, y - 38 * s), (fx - 22 * s, y - 10 * s)], 5)
            self.line([(fx, y - 38 * s), (fx + 22 * s, y - 10 * s)], 5)

    def calendar(self, x, y, s=1, circled=3):
        self.rect(x, y, 200 * s, 220 * s, (255, 255, 250), 6)
        self.rect(x, y, 200 * s, 52 * s, RED, 6)
        for r in range(4):
            for c in range(4):
                cx_, cy_ = x + 30 * s + c * 46 * s, y + 85 * s + r * 34 * s
                self.circ(cx_, cy_, 6 * s, INK, 0)
        for k in range(circled):
            self.circ(x + 30 * s + k * 46 * s, y + 85 * s, 17 * s, None, 5, RED)

    def railway(self, x1, x2, y):
        self.line([(x1, y), (x2, y)], 8)
        self.line([(x1, y + 26), (x2, y + 26)], 8)
        for x in range(int(x1), int(x2), 44):
            self.line([(x, y - 6), (x, y + 32)], 6, BROWN, 0.6)

    def train(self, x, y, s=1):
        self.poly([(x - 170 * s, y), (x + 120 * s, y), (x + 200 * s, y + 55 * s), (x + 205 * s, y + 70 * s), (x - 170 * s, y + 70 * s)], (245, 248, 252), 6)
        self.line([(x - 170 * s, y + 42 * s), (x + 190 * s, y + 42 * s)], 8, NAVY, 0.5)
        for i in range(7):
            self.rect(x - 150 * s + i * 38 * s, y + 10 * s, 24 * s, 18 * s, SEA, 3)

    def pipe(self, x1, y1, x2, y2):
        self.line([(x1, y1), (x2, y2)], 26, DGRAY, 0.5)
        self.line([(x1, y1), (x2, y2)], 14, (200, 200, 210), 0.5)

    def bear(self, x, y, s=1):
        self.ell(x, y, 80 * s, 100 * s, BROWN, 6)
        self.circ(x, y - 120 * s, 56 * s, BROWN, 6)
        self.circ(x - 42 * s, y - 165 * s, 18 * s, BROWN, 6)
        self.circ(x + 42 * s, y - 165 * s, 18 * s, BROWN, 6)
        self.rect(x - 52 * s, y - 190 * s, 104 * s, 40 * s, (110, 80, 60), 6, r=14 * s)
        self.circ(x - 18 * s, y - 125 * s, 6 * s, INK, 0)
        self.circ(x + 18 * s, y - 125 * s, 6 * s, INK, 0)
        self.ell(x, y - 105 * s, 16 * s, 10 * s, INK, 0)

    def scroll(self, x, y, s=1):
        self.rect(x - 90 * s, y - 55 * s, 180 * s, 110 * s, (255, 250, 232), 6, r=18 * s)
        for i in range(3):
            self.line([(x - 60 * s, y - 22 * s + i * 22 * s), (x + 60 * s, y - 22 * s + i * 22 * s)], 4, (150, 140, 120), 0.5)

    def sword(self, x, y, s=1, ang=-30):
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        T = lambda px, py: (x + (px * ca - py * sa) * s, y + (px * sa + py * ca) * s)
        self.line([T(0, 0), T(0, -150)], 12, (225, 228, 236), 0.4)
        self.line([T(-24, 0), T(24, 0)], 10, YELLOW, 0.4)
        self.line([T(0, 0), T(0, 40)], 12, BROWN, 0.4)

    def magnifier(self, x, y, s=1):
        self.circ(x, y, 50 * s, (230, 245, 252), 8)
        self.line([(x + 36 * s, y + 36 * s), (x + 90 * s, y + 92 * s)], 14, BROWN, 0.4)

    def periscope(self, x, y, s=1):
        self.rect(x - 8 * s, y - 80 * s, 16 * s, 80 * s, DGRAY, 5)
        self.rect(x - 8 * s, y - 88 * s, 36 * s, 16 * s, DGRAY, 5)

    def tank_ship(self, x, y, s=1):
        self.poly([(x - 150 * s, y), (x + 140 * s, y), (x + 105 * s, y + 42 * s), (x - 115 * s, y + 42 * s)], (120, 120, 132), 6)
        self.rect(x - 110 * s, y - 28 * s, 140 * s, 28 * s, BROWN, 5)
        self.rect(x + 50 * s, y - 52 * s, 50 * s, 52 * s, (215, 215, 225), 5)

    def arrow(self, x1, y1, x2, y2, col=RED, w=8):
        self.line([(x1, y1), (x2, y2)], w, col, 1)
        a = math.atan2(y2 - y1, x2 - x1)
        for da in (2.6, -2.6):
            self.line([(x2, y2), (x2 + 36 * math.cos(a + da), y2 + 36 * math.sin(a + da))], w, col, 0.5)

    def dotted(self, pts, col=RED):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            n = int(math.hypot(x2 - x1, y2 - y1) / 34)
            for i in range(n):
                t = i / max(n, 1)
                self.circ(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, 7, col, 0)

    def speed(self, x, y, n=4, length=140):
        for i in range(n):
            yy = y + i * 34
            self.line([(x, yy), (x - length + (i % 2) * 40, yy)], 6, (150, 150, 165), 1)

    def sweat(self, x, y, s=1):
        self.poly([(x, y - 22 * s), (x - 12 * s, y + 6 * s), (x, y + 18 * s), (x + 12 * s, y + 6 * s)], (170, 215, 245), 4)

    # ---------------- props added for any era ----------------
    def castle(self, x, y, s=1, col=(208, 198, 178), roof=RED):
        for dx in (-170, 170):
            tx = x + dx * s
            self.rect(tx - 45 * s, y - 300 * s, 90 * s, 300 * s, col, 6)
            self.poly([(tx - 58 * s, y - 296 * s), (tx + 58 * s, y - 296 * s), (tx, y - 400 * s)], roof, 6)
            self.rect(tx - 13 * s, y - 240 * s, 26 * s, 44 * s, (60, 60, 72), 4, r=10 * s)
        self.rect(x - 125 * s, y - 230 * s, 250 * s, 230 * s, col, 6)
        for i in range(5):
            self.rect(x - 125 * s + i * 55 * s, y - 262 * s, 30 * s, 34 * s, col, 5)
        self.rect(x - 42 * s, y - 115 * s, 84 * s, 115 * s, BROWN, 5, r=34 * s)
        self.line([(x, y - 262 * s), (x, y - 350 * s)], 5, INK, 0.3)
        self.poly([(x, y - 350 * s), (x + 62 * s, y - 334 * s), (x, y - 318 * s)], roof, 4)

    def pyramid(self, x, y, s=1, col=(232, 200, 130)):
        self.poly([(x - 230 * s, y), (x + 230 * s, y), (x, y - 300 * s)], col, 0, wob=0.6)
        self.poly([(x, y - 300 * s), (x + 230 * s, y), (x + 55 * s, y)], darker(col, 0.86), 0, wob=0.4)
        for k in range(1, 5):
            yy = y - 60 * s * k
            half = 230 * s * (1 - k / 5)
            self.line([(x - half, yy), (x + half, yy)], 3, (170, 140, 90), 0.5)
        self.poly([(x - 230 * s, y), (x + 230 * s, y), (x, y - 300 * s)], None, 6, wob=0.6)

    def temple(self, x, y, s=1, col=(240, 236, 224)):
        self.rect(x - 230 * s, y - 30 * s, 460 * s, 30 * s, col, 6)
        self.rect(x - 210 * s, y - 55 * s, 420 * s, 25 * s, col, 6)
        for i in range(6):
            cx = x - 175 * s + i * 70 * s
            self.rect(cx - 17 * s, y - 245 * s, 34 * s, 190 * s, col, 5)
            for k in (-7, 7):
                self.line([(cx + k * s, y - 235 * s), (cx + k * s, y - 65 * s)], 3, (190, 186, 176), 0.3)
        self.rect(x - 220 * s, y - 280 * s, 440 * s, 35 * s, col, 6)
        self.poly([(x - 235 * s, y - 280 * s), (x + 235 * s, y - 280 * s), (x, y - 370 * s)], col, 6)

    def house(self, x, y, s=1, col=(238, 214, 170), roof=(190, 80, 60)):
        self.rect(x - 110 * s, y - 160 * s, 220 * s, 160 * s, col, 6)
        self.poly([(x - 135 * s, y - 156 * s), (x + 135 * s, y - 156 * s), (x, y - 270 * s)], roof, 6)
        self.rect(x - 30 * s, y - 95 * s, 60 * s, 95 * s, BROWN, 5)
        self.rect(x + 50 * s, y - 120 * s, 42 * s, 42 * s, (170, 210, 235), 4)

    def tree(self, x, y, s=1, col=(110, 170, 90)):
        self.rect(x - 16 * s, y - 120 * s, 32 * s, 120 * s, BROWN, 5)
        self.blob(x, y - 190 * s, 105 * s, 95 * s, col, 6, seed=int(x) + 3)

    def mountain(self, x, y, s=1, col=(150, 150, 165)):
        self.poly([(x - 260 * s, y), (x + 260 * s, y), (x, y - 330 * s)], col, 6, wob=0.6)
        self.poly([(x - 72 * s, y - 238 * s), (x, y - 330 * s), (x + 72 * s, y - 238 * s), (x + 30 * s, y - 220 * s),
                   (x, y - 245 * s), (x - 30 * s, y - 220 * s)], WHITE, 5, wob=0.4)

    def sailboat(self, x, y, s=1, col=BROWN, sail=(250, 246, 235), flag=None):
        self.poly([(x - 170 * s, y - 50 * s), (x + 170 * s, y - 50 * s), (x + 120 * s, y + 25 * s), (x - 130 * s, y + 25 * s)], col, 6)
        self.line([(x - 140 * s, y - 20 * s), (x + 140 * s, y - 20 * s)], 4, darker(col, 0.7), 0.4)
        for mx, hgt in ((-60, 230), (60, 290)):
            self.line([(x + mx * s, y - 50 * s), (x + mx * s, y - hgt * s)], 7, BROWN, 0.3)
            self.poly([(x + mx * s - 70 * s, y - (hgt - 25) * s), (x + mx * s + 70 * s, y - (hgt - 25) * s),
                       (x + mx * s + 60 * s, y - 85 * s), (x + mx * s - 60 * s, y - 85 * s)], sail, 5)
        if flag:
            self.poly([(x + 60 * s, y - 290 * s), (x + 120 * s, y - 280 * s), (x + 60 * s, y - 266 * s)], flag, 4)

    def tank(self, x, y, s=1, col=(122, 128, 74)):
        self.rect(x - 160 * s, y - 60 * s, 320 * s, 60 * s, (80, 80, 88), 6, r=30 * s)
        for i in range(6):
            self.circ(x - 125 * s + i * 50 * s, y - 30 * s, 17 * s, (150, 150, 160), 4)
        self.rect(x - 150 * s, y - 115 * s, 300 * s, 58 * s, col, 6, r=14 * s)
        self.rect(x - 70 * s, y - 170 * s, 140 * s, 60 * s, col, 6, r=22 * s)
        self.rect(x + 65 * s, y - 152 * s, 150 * s, 18 * s, darker(col, 0.8), 5)

    def flag(self, x, y, s=1, col=RED, col2=None):
        self.line([(x, y), (x, y - 280 * s)], 8, BROWN, 0.3)
        self.circ(x, y - 284 * s, 9 * s, YELLOW, 3)
        self.rect(x, y - 270 * s, 170 * s, 110 * s, col, 6)
        if col2:
            self.rect(x + 57 * s, y - 270 * s, 57 * s, 110 * s, col2, 0)
            self.rect(x, y - 270 * s, 170 * s, 110 * s, None, 6)

    def book(self, x, y, s=1, col=(170, 60, 60)):
        self.rect(x - 95 * s, y - 130 * s, 190 * s, 130 * s, col, 6, r=10 * s)
        self.rect(x - 85 * s, y - 20 * s, 175 * s, 14 * s, (250, 246, 235), 4)
        self.line([(x - 60 * s, y - 90 * s), (x + 60 * s, y - 90 * s)], 6, YELLOW, 0.3)
        self.line([(x - 40 * s, y - 64 * s), (x + 40 * s, y - 64 * s)], 5, YELLOW, 0.3)

    def moneybag(self, x, y, s=1, col=(215, 190, 120)):
        self.blob(x, y - 75 * s, 85 * s, 75 * s, col, 6, rough=0.08, seed=5)
        self.poly([(x - 30 * s, y - 145 * s), (x + 30 * s, y - 145 * s), (x + 45 * s, y - 185 * s), (x - 45 * s, y - 185 * s)], col, 5)
        self.line([(x - 34 * s, y - 145 * s), (x + 34 * s, y - 145 * s)], 7, BROWN, 0.3)
        self.text("$", x, y - 72 * s, 90 * s, (60, 130, 70))

    def coin(self, x, y, s=1, col=(240, 200, 70)):
        self.circ(x, y - 55 * s, 55 * s, col, 6)
        self.circ(x, y - 55 * s, 40 * s, None, 3, darker(col, 0.75))
        self.text("$", x, y - 55 * s, 56 * s, darker(col, 0.6))

    def crown(self, x, y, s=1, col=(240, 200, 70)):
        self.poly([(x - 90 * s, y), (x + 90 * s, y), (x + 100 * s, y - 110 * s), (x + 50 * s, y - 55 * s),
                   (x, y - 125 * s), (x - 50 * s, y - 55 * s), (x - 100 * s, y - 110 * s)], col, 6)
        for dx in (-45, 0, 45):
            self.circ(x + dx * s, y - 25 * s, 10 * s, RED, 3)

    def gravestone(self, x, y, s=1, label="RIP"):
        self.rect(x - 70 * s, y - 180 * s, 140 * s, 180 * s, (175, 175, 185), 6, r=60 * s)
        if label:
            self.text(label, x, y - 105 * s, 40 * s, (90, 90, 100))
        self.line([(x - 100 * s, y), (x + 100 * s, y)], 6, (110, 150, 90), 0.5)

    def tent(self, x, y, s=1, col=(220, 200, 150)):
        self.poly([(x - 140 * s, y), (x + 140 * s, y), (x, y - 190 * s)], col, 6)
        self.poly([(x - 30 * s, y), (x + 30 * s, y), (x, y - 110 * s)], darker(col, 0.6), 4)
        self.line([(x, y - 190 * s), (x, y - 225 * s)], 5, BROWN, 0.3)

    def wall(self, x, y, w=400, h=160, col=(200, 120, 90)):
        self.rect(x - w / 2, y - h, w, h, col, 6)
        rows = max(1, int(h // 40))
        for r in range(1, rows):
            yy = y - h + r * h / rows
            self.line([(x - w / 2, yy), (x + w / 2, yy)], 3, darker(col, 0.7), 0.3)
        for r in range(rows):
            off = 0 if r % 2 == 0 else 40
            yy0, yy1 = y - h + r * h / rows, y - h + (r + 1) * h / rows
            for bx in range(int(x - w / 2 + 40 + off), int(x + w / 2), 80):
                self.line([(bx, yy0), (bx, yy1)], 3, darker(col, 0.7), 0.3)

    def globe(self, x, y, s=1):
        cy = y - 100 * s
        self.circ(x, cy, 95 * s, (150, 200, 230), 6)
        self.blob(x - 30 * s, cy - 25 * s, 40 * s, 30 * s, (130, 190, 110), 0, seed=11)
        self.blob(x + 35 * s, cy + 30 * s, 32 * s, 26 * s, (130, 190, 110), 0, seed=12)
        self.ell(x, cy, 95 * s, 30 * s, None, 3)
        self.ell(x, cy, 35 * s, 95 * s, None, 3)

    def lightbulb(self, x, y, s=1, lit=True):
        self.circ(x, y - 105 * s, 55 * s, YELLOW if lit else (235, 235, 235), 6)
        self.rect(x - 22 * s, y - 55 * s, 44 * s, 45 * s, GRAY, 5)
        if lit:
            for a in range(-150, -20, 32):
                r0, r1 = 70 * s, 100 * s
                ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
                self.line([(x + ca * r0, y - 105 * s + sa * r0), (x + ca * r1, y - 105 * s + sa * r1)], 5, ORANGE, 0.3)

    def trophy(self, x, y, s=1, col=(240, 200, 70)):
        self.rect(x - 60 * s, y - 30 * s, 120 * s, 30 * s, BROWN, 5)
        self.rect(x - 14 * s, y - 80 * s, 28 * s, 52 * s, col, 5)
        self.chord(x - 75 * s, y - 230 * s, x + 75 * s, y - 70 * s, 0, 180, col, 6)
        self.rect(x - 75 * s, y - 160 * s, 150 * s, 10 * s, col, 0)
        self.line([(x - 75 * s, y - 155 * s), (x + 75 * s, y - 155 * s)], 6, INK, 0.2)
        for k in (-1, 1):
            self.d.arc([(x + k * 75 * s - 30 * s) * SS, (y - 165 * s) * SS, (x + k * 75 * s + 30 * s) * SS, (y - 105 * s) * SS],
                       270 if k > 0 else 90, 90 if k > 0 else 270, fill=INK, width=int(6 * SS))

    def bar_chart(self, x, y, w=420, h=300, values=(0.3, 0.6, 0.9), colors=None):
        self.line([(x - w / 2, y - h), (x - w / 2, y), (x + w / 2, y)], 7, INK, 0.3)
        n = max(1, len(values))
        bw = w / n * 0.62
        for i, v in enumerate(values):
            c = (colors[i % len(colors)] if colors else [NAVY, RED, GREEN, ORANGE][i % 4])
            bx = x - w / 2 + (i + 0.5) * w / n
            bh = max(4, min(1.0, float(v)) * (h - 20))
            self.rect(bx - bw / 2, y - bh, bw, bh, c, 5)

    def rocket(self, x, y, s=1, col=(235, 235, 242)):
        self.poly([(x - 40 * s, y - 60 * s), (x + 40 * s, y - 60 * s), (x + 40 * s, y - 250 * s), (x, y - 330 * s),
                   (x - 40 * s, y - 250 * s)], col, 6)
        self.circ(x, y - 210 * s, 18 * s, (170, 210, 235), 5)
        for k in (-1, 1):
            self.poly([(x + k * 40 * s, y - 60 * s), (x + k * 85 * s, y - 20 * s), (x + k * 40 * s, y - 130 * s)], RED, 5)
        self.flame(x, y - 10 * s, 0.9 * s)

    def derrick(self, x, y, s=1):
        self.poly([(x - 80 * s, y), (x - 12 * s, y - 330 * s), (x + 12 * s, y - 330 * s), (x + 80 * s, y)], None, 7)
        for k in range(1, 5):
            yy = y - k * 66 * s
            half = 80 * s - (68 * s) * k / 5
            self.line([(x - half, yy), (x + half, yy)], 5, INK, 0.3)
        self.rect(x - 110 * s, y - 20 * s, 220 * s, 20 * s, BROWN, 5)

    def throne(self, x, y, s=1, col=(190, 50, 60), gold=(232, 186, 60)):
        self.rect(x - 85 * s, y - 330 * s, 170 * s, 230 * s, gold, 6, r=40 * s)
        self.rect(x - 60 * s, y - 300 * s, 120 * s, 190 * s, col, 4, r=26 * s)
        self.rect(x - 105 * s, y - 120 * s, 210 * s, 50 * s, col, 6, r=12 * s)
        for k in (-1, 1):
            self.rect(x + k * 80 * s - 12 * s, y - 75 * s, 24 * s, 75 * s, gold, 5)


def caption_band(im, text, size=46):
    """Simple fallback caption band (not used by the main renderer)."""
    d = ImageDraw.Draw(im)
    f = font("bold", size)
    d.text((W // 2, H - 80), text, font=f, fill=WHITE, anchor="mm", stroke_width=4, stroke_fill=(20, 20, 30))
    return im


__all__ = ["Canvas", "W", "H", "SS", "INK", "PAPER", "SEA", "SEA2", "LAND", "RED", "NAVY", "GREEN", "GRAY", "DGRAY",
           "ORANGE", "SKIN", "BROWN", "YELLOW", "WHITE", "lighter", "darker"]
