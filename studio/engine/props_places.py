"""Landmarks and buildings from around the world. All anchored bottom-center (they stand on the ground)."""
import math

from .palette import color as C, INK, RED, WHITE, darker, lighter
from .props_kit import (Sk, arch, arc_pts, profile_pts, star_pts, ONION, DOME, STONE, STONE_D, MARBLE, MARBLE_D,
                        WOOD, WOOD_D, WOOD_L, IRON_D, GOLD, BRICK, SLATE, COPPER, COPPER_D, GLASS, SAND, SAND_D,
                        SNOW, CREAM, DARKWIN, LEAF, LEAF_D, shade)


def _c(c, default):
    return C(c, default) if c is not None else default


def crescent(g, cx, cy, r, fill=GOLD):
    outer = arc_pts(cx, cy, r, r, 60, 300, 16)
    inner = arc_pts(cx + r * 0.42, cy, r * 0.78, r * 0.8, 290, 70, 16)
    g.poly(outer + inner, fill, 3)


def arcade(x0, x1, bottom, top, n, pier, rise):
    """Outline of a wall pierced by n round arches (bridges, aqueducts)."""
    span = (x1 - x0 - pier * (n + 1)) / n
    r = span / 2
    spring = bottom - max(0, rise - r)
    ry = min(r, rise)
    pts = [(x0, top), (x1, top), (x1, bottom)]
    x = x1 - pier
    for i in range(n):
        pts += [(x, bottom), (x, spring)]
        pts += arc_pts(x - r, spring, r, ry, 0, -180, 12)[1:-1]
        pts += [(x - span, spring), (x - span, bottom)]
        x -= span + pier
    pts.append((x0, bottom))
    return pts


# ------------------------------------------------------------------ Europe
def eiffel_tower(p, x, y, s, c, k):
    col = _c(c, (150, 108, 76))
    d = darker(col, 0.68)
    g = Sk(p, x, y, s, wob=0.35)

    def zig(outer, inner, n, w=2.6):
        pts = []
        for i in range(n + 1):
            t = i / n
            a = outer if i % 2 == 0 else inner
            b = (a[0][0] + (a[1][0] - a[0][0]) * t, a[0][1] + (a[1][1] - a[0][1]) * t)
            pts.append(b)
        g.line(pts, w, d)

    for f in (1, -1):
        leg = [(-170, 0), (-142, -62), (-120, -118), (-106, -150), (-58, -150), (-66, -112), (-84, -66), (-104, -26), (-112, 0)]
        g.poly([(a * f, b) for a, b in leg], col, 5)
        zig(((-160 * f, -8), (-104 * f, -146)), ((-114 * f, -8), (-62 * f, -146)), 9)
        mid = [(-100, -168), (-58, -300), (-30, -300), (-54, -168)]
        g.poly([(a * f, b) for a, b in mid], col, 5)
        zig(((-96 * f, -172), (-58 * f, -296)), ((-56 * f, -172), (-32 * f, -296)), 8)
    # arch between the legs
    outer = arc_pts(0, -12, 106, 104, 180, 360, 16)
    inner = arc_pts(0, -12, 92, 88, 360, 180, 16)
    g.poly(outer + inner, col, 4)
    for xx in (-40, 0, 40):
        g.line([(xx * 0.9, -150), (xx, -118 + abs(xx) * 0.3)], 2.6, d)
    g.line([(-50, -190), (48, -250)], 2.4, d)
    g.line([(50, -190), (-48, -250)], 2.4, d)
    g.rect(-128, -170, 128, -148, d, 5)
    for i in range(13):
        g.line([(-118 + i * 19.6, -166), (-118 + i * 19.6, -152)], 2, col)
    g.rect(-66, -322, 66, -300, d, 5)
    # top section
    g.poly([(-42, -322), (-11, -572), (11, -572), (42, -322)], col, 5)
    pts = []
    for i in range(9):
        t = i / 8
        hw = 40 - 29 * t
        pts.append(((-hw if i % 2 == 0 else hw) * 0.92, -322 - 250 * t))
    g.line(pts, 2.4, d)
    for t in (0.35, 0.7):
        hw = 40 - 29 * t
        g.line([(-hw, -322 - 250 * t), (hw, -322 - 250 * t)], 3, d)
    g.rect(-17, -598, 17, -572, d, 4)
    g.poly([(-12, -598), (0, -616), (12, -598)], col, 4)
    g.line([(0, -616), (0, -650)], 4, INK)


def arc_de_triomphe(p, x, y, s, c, k):
    col = _c(c, (236, 224, 196))
    d = darker(col, 0.84)
    dd = darker(col, 0.55)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-180, -372, 180, 0, col, 6)
    g.rect(-190, -372, 190, -316, col, 6)
    g.line([(-190, -334), (190, -334)], 3, d)
    for i in range(10):
        g.circ(-162 + i * 36, -353, 8, d, 2.5)
    g.rect(-194, -316, 194, -300, d, 5)
    g.rect(-186, -22, 186, 0, d, 5)
    g.poly(arch(0, -22, 132, -206), dd, 6)
    g.arc(0, -206, 82, 82, 180, 360, 4, d)
    g.rect(-10, -300, 10, -282, d, 3)
    for f in (1, -1):
        g.line([(-180 * f, -206), (-66 * f, -206)], 4, d)
        g.rect(-164 * f, -186, -84 * f, -48, d, 4)
        g.rect(-164 * f, -288, -84 * f, -226, d, 4)
        for j in range(3):
            cx = -146 * f + j * 26 * f
            g.circ(cx, -150, 6, None, 2.4, dd)
            g.line([(cx, -144), (cx, -112), (cx - 7, -86)], 2.4, dd)
            g.line([(cx, -112), (cx + 7, -86)], 2.4, dd)
            g.line([(cx - 9, -132), (cx + 9, -126)], 2.4, dd)
        g.line([(-160 * f, -258), (-88 * f, -254)], 2.4, dd)


def big_ben(p, x, y, s, c, k):
    col = _c(c, (222, 198, 148))
    d = darker(col, 0.78)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-54, -424, 54, 0, col, 6)
    for xx in (-27, 0, 27):
        g.line([(xx, -410), (xx, -14)], 2.4, d)
    for yy in range(-350, -20, 70):
        g.line([(-54, yy), (54, yy)], 3, d)
        for xx in (-13.5, 13.5):
            g.poly(arch(xx, yy + 50, 12, yy + 22, "pointed", 6), DARKWIN, 2.4)
    g.rect(-66, -534, 66, -424, col, 6)
    g.circ(0, -479, 50, (236, 190, 70), 5)
    g.circ(0, -479, 41, CREAM, 3)
    for i in range(12):
        a = 2 * math.pi * i / 12
        g.line([(math.sin(a) * 33, -479 - math.cos(a) * 33), (math.sin(a) * 38, -479 - math.cos(a) * 38)], 2.4)
    g.line([(0, -479), (0, -508)], 3.5)
    g.line([(0, -479), (18, -470)], 4)
    for f in (1, -1):
        g.poly([(-66 * f, -534), (-74 * f, -534), (-66 * f, -560)], col, 3)
    g.rect(-58, -594, 58, -534, col, 6)
    for xx in (-30, 0, 30):
        g.poly(arch(xx, -542, 18, -568, "pointed", 6), DARKWIN, 2.6)
    g.poly([(-60, -594), (-42, -626), (-16, -672), (0, -700), (16, -672), (42, -626), (60, -594)], SLATE, 5)
    for f in (1, -1):
        g.poly([(-60 * f, -594), (-54 * f, -630), (-48 * f, -594)], SLATE, 3)
    g.line([(0, -700), (0, -722)], 4, GOLD)
    g.circ(0, -724, 4, GOLD, 2)


def leaning_tower(p, x, y, s, c, k):
    col = _c(c, MARBLE)
    d = darker(col, 0.82)
    g = Sk(p, x, y, s, rot=_num(k, "angle", 5), wob=0.3)
    g.rect(-72, -26, 72, 0, d, 5)
    g.rect(-62, -432, 62, -26, col, 6)
    levels = [-26, -110, -168, -226, -284, -342, -400]
    for j, yb in enumerate(levels[:-1]):
        yt = levels[j + 1]
        g.line([(-62, yt), (62, yt)], 3.5, d)
        for i in range(5):
            cx = -48 + i * 24
            g.poly(arch(cx, yb - 6, 14, yt + 22 if j else yb - 46), (190, 186, 172), 2.4)
    g.rect(-42, -474, 42, -432, col, 5)
    for cx in (-22, 0, 22):
        g.poly(arch(cx, -438, 12, -460), (190, 186, 172), 2.4)
    g.rect(-46, -480, 46, -474, d, 3)


def windmill(p, x, y, s, c, k):
    col = _c(c, (236, 228, 210))
    g = Sk(p, x, y, s, wob=0.35)
    g.poly([(-76, 0), (76, 0), (50, -290), (-50, -290)], col, 6)
    g.poly([(-80, 0), (80, 0), (78, -26), (-78, -26)], WOOD_D, 5)
    g.poly(arch(0, 0, 40, -48), WOOD, 4)
    for wy, ww in ((-170, 22), (-232, 18)):
        g.rect(-ww / 2, wy - ww, ww / 2, wy + ww * 0.3, GLASS, 3)
    g.poly([(-58, -288), (58, -288), (48, -320), (20, -342), (-20, -342), (-48, -320)], WOOD_D, 5)
    hx, hy = 0, -318
    a0 = _num(k, "angle", 20) + 36 * _num(k, "t", 0)            # turns 90 degrees every 2.5 s
    for i in range(4):
        a = math.radians(a0 + 90 * i)
        ux, uy = math.cos(a), math.sin(a)
        vx, vy = -uy, ux
        P = lambda r, o: (hx + ux * r + vx * o, hy + uy * r + vy * o)
        g.poly([P(44, 0), P(238, 0), P(238, 50), P(44, 42)], (250, 246, 236), 4)
        for t in (0.25, 0.5, 0.75):
            r = 44 + 194 * t
            g.line([P(r, 0), P(r, 42 + 8 * t)], 2.2, WOOD_D)
        for o in (16, 32):
            g.line([P(44, o * 0.86), P(238, o)], 2, WOOD_D)
        g.line([P(14, 0), P(246, 0)], 7, WOOD_D)
    g.circ(hx, hy, 14, WOOD_D, 4)


def lighthouse(p, x, y, s, c, k):
    stripe = _c(c, (210, 62, 56))
    g = Sk(p, x, y, s, wob=0.35)
    lit = k.get("lit", True) is not False
    if lit:
        sweep = 0.5 + 0.5 * math.cos(2 * math.pi * _num(k, "t", 0) / 3.0)       # the beam swings round every 3 s
        for f, a in ((1, sweep), (-1, 1 - sweep)):
            if a > 0.06:
                half = 8 + 50 * a
                g.poly([(30 * f, -384), ((60 + 240 * a) * f, -384 - half), ((60 + 240 * a) * f, -384 + half)],
                       (255, 242, 176), 0)
    for cx, cy, rx, ry, col in ((-62, -14, 62, 22, (150, 150, 162)), (58, -10, 72, 20, (132, 132, 146)),
                                 (0, -6, 92, 16, (166, 166, 178))):
        g.ell(cx, cy, rx, ry, col, 4)
    hw = lambda yy: 62 - 22 * ((-yy - 20) / 310)
    g.poly([(-62, -20), (62, -20), (40, -330), (-40, -330)], WHITE, 6)
    for j in (1, 3):
        y0, y1 = -20 - 310 * j / 5, -20 - 310 * (j + 1) / 5
        g.poly([(-hw(y0), y0), (hw(y0), y0), (hw(y1), y1), (-hw(y1), y1)], stripe, 4)
    g.poly(arch(0, -20, 30, -56), WOOD_D, 4)
    for wy in (-180, -270):
        g.rect(-8, wy - 14, 8, wy + 6, DARKWIN, 3)
    g.rect(-58, -348, 58, -330, IRON_D, 5)
    g.rect(-34, -410, 34, -348, (255, 234, 140) if lit else GLASS, 5)
    for xx in (-12, 12):
        g.line([(xx, -406), (xx, -352)], 3, IRON_D)
    g.poly(profile_pts(DOME, 0, -410, 80, 56), stripe, 5)
    g.circ(0, -454, 7, IRON_D, 3)
    for xx in range(-50, 51, 20):
        g.line([(xx, -348), (xx, -370)], 2.4, IRON_D)
    g.line([(-58, -370), (58, -370)], 3, IRON_D)


def cathedral(p, x, y, s, c, k):
    col = _c(c, (216, 208, 192))
    d = darker(col, 0.8)
    dark = (84, 86, 104)
    g = Sk(p, x, y, s, wob=0.35)
    g.poly([(-10, -380), (0, -540), (10, -380)], SLATE, 4)
    g.rect(-84, -340, 84, 0, col, 6)
    g.poly([(-84, -340), (0, -404), (84, -340)], col, 6)
    for f in (1, -1):
        g.rect(-206 * f, -446, -84 * f, 0, col, 6)
        g.crenels(min(-206 * f, -84 * f), max(-206 * f, -84 * f), -446, 12, col, 3)
        for xx in (-166, -126):
            g.poly(arch(xx * f, -306, 24, -378, "pointed", 6), dark, 3)
        g.poly(arch(-145 * f, 0, 66, -84, "pointed", 8), dark, 4)
        g.line([(-206 * f, -170), (-84 * f, -170)], 3, d)
        g.line([(-206 * f, -290), (-84 * f, -290)], 3, d)
    g.poly(arch(0, 0, 84, -96, "pointed", 8), dark, 5)
    g.circ(0, -238, 58, (110, 132, 196), 5)
    g.circ(0, -238, 20, (200, 70, 90), 3)
    for i in range(12):
        a = 2 * math.pi * i / 12
        g.line([(math.cos(a) * 20, -238 + math.sin(a) * 20), (math.cos(a) * 56, -238 + math.sin(a) * 56)], 3)
    for i in range(7):
        g.poly(arch(-60 + i * 20, -310, 10, -326), dark, 2)
    g.line([(-84, -170), (84, -170)], 3, d)


def church(p, x, y, s, c, k):
    roof = _c(c, (186, 70, 56))
    g = Sk(p, x, y, s, wob=0.4)
    g.rect(-30, -340, 30, -170, WHITE, 5)
    g.poly(arch(0, -270, 26, -300), DARKWIN, 3)
    g.poly([(-38, -338), (0, -440), (38, -338)], SLATE, 5)
    g.line([(0, -440), (0, -486)], 5)
    g.line([(-14, -468), (14, -468)], 5)
    g.rect(-108, -186, 108, 0, WHITE, 6)
    g.poly([(-124, -180), (0, -262), (124, -180)], roof, 6)
    g.poly(arch(0, 0, 54, -70), WOOD, 5)
    g.line([(0, 0), (0, -96)], 3, WOOD_D)
    g.circ(0, -138, 17, GLASS, 4)
    for xx in (-70, 70):
        g.poly(arch(xx, -60, 22, -110), GLASS, 3)


def stonehenge(p, x, y, s, c, k):
    col = _c(c, (172, 172, 168))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.9)
    g.ell(0, -6, 270, 16, (150, 190, 108), 0)
    g.poly([(150, -4), (240, -6), (246, -36), (156, -40)], d, 5)
    for cx, hgt in ((-180, 190), (-20, 220), (140, 180)):
        for dx in (-40, 40):
            g.poly([(cx + dx - 22, 0), (cx + dx + 22, 0), (cx + dx + 20, -hgt), (cx + dx - 20, -hgt + 6)], col, 5)
            g.line([(cx + dx - 6, -30), (cx + dx - 2, -hgt + 30)], 2.4, d)
        g.poly([(cx - 70, -hgt - 2), (cx + 70, -hgt + 4), (cx + 68, -hgt - 32), (cx - 68, -hgt - 36)], col, 5)
    g.poly([(-250, 0), (-232, -110), (-206, -112), (-212, 0)], col, 5)


def kremlin(p, x, y, s, c, k):
    col = _c(c, BRICK)
    trim = (250, 244, 232)
    g = Sk(p, x, y, s, wob=0.35)
    for f in (1, -1):
        g.rect(-250 * f, -120, -60 * f, 0, col, 5)
        x0, x1 = sorted((-250 * f, -60 * f))
        n = 6
        for i in range(n):
            a = x0 + (x1 - x0) * (i + 0.18) / n
            b = a + (x1 - x0) * 0.62 / n
            m = (a + b) / 2
            g.poly([(a, -118), (a, -146), (m - 3, -136), (m, -142), (m + 3, -136), (b, -146), (b, -118)], col, 3)
    g.rect(-62, -270, 62, 0, col, 6)
    g.poly(arch(0, 0, 50, -70), (60, 46, 50), 4)
    g.line([(-62, -150), (62, -150)], 4, trim)
    g.circ(0, -205, 34, (44, 48, 62), 5)
    for i in range(12):
        a = 2 * math.pi * i / 12
        g.circ(math.sin(a) * 27, -205 - math.cos(a) * 27, 2.4, GOLD, 0)
    g.line([(0, -205), (0, -228)], 3, GOLD)
    g.line([(0, -205), (14, -198)], 3, GOLD)
    g.rect(-50, -336, 50, -270, col, 5)
    for f in (1, -1):
        g.poly([(-50 * f, -270), (-58 * f, -270), (-50 * f, -306)], trim, 3)
        g.poly([(-36 * f, -336), (-44 * f, -336), (-36 * f, -362)], trim, 3)
    g.poly(arch(0, -280, 26, -312, "pointed", 6), (60, 46, 50), 3)
    g.rect(-36, -388, 36, -336, col, 5)
    g.poly([(-40, -388), (0, -508), (40, -388)], (64, 132, 92), 5)
    g.poly(star_pts(0, -530, 26), RED, 4, GOLD)


def onion_domes(p, x, y, s, c, k):
    col = _c(c, BRICK)
    trim = (250, 244, 232)
    g = Sk(p, x, y, s, wob=0.35)
    # central tent
    g.rect(-42, -336, 42, -170, col, 5)
    g.poly([(-46, -336), (0, -470), (46, -336)], (236, 200, 120), 5)
    for j in range(5):
        yy = -350 - j * 24
        hw = 46 * (1 - (j * 24 + 14) / 134)
        g.line([(-hw, yy), (hw, yy)], 2.4, (200, 150, 70))
    g.poly(profile_pts(ONION, 0, -470, 34, 36), GOLD, 4)
    g.line([(0, -506), (0, -528)], 4, GOLD)
    g.line([(-8, -520), (8, -520)], 3, GOLD)
    towers = [(-82, -300, 50, 74, 90, [(240, 200, 70), (70, 150, 90)], 0.0),
              (82, -300, 50, 74, 90, [(200, 60, 60), (70, 150, 90)], 0.0),
              (-152, -256, 56, 88, 112, [(70, 160, 96), (250, 246, 235)], 0.9),
              (152, -256, 56, 88, 112, [(70, 120, 200), (250, 246, 235)], -0.9)]
    for cx, top, dw, w, h, cols, tw in towers:
        g.rect(cx - dw / 2, top, cx + dw / 2, -170, col, 5)
        g.poly(arch(cx, top + 40, dw * 0.5, top + 20), trim, 2.4)
        prof = profile_pts(ONION, cx, top, w, h)
        g.poly(prof, cols[0], 0)
        g.stripes(ONION, cx, top, w, h, cols, n=8, twist=tw)
        g.poly(prof, None, 5)
        g.line([(cx, top - h), (cx, top - h - 26)], 4, GOLD)
        g.line([(cx - 8, top - h - 18), (cx + 8, top - h - 18)], 3, GOLD)
    g.rect(-206, -174, 206, 0, col, 6)
    g.rect(-214, -30, 214, 0, darker(col, 0.8), 5)
    for i in range(7):
        cx = -168 + i * 56
        g.poly(arch(cx, -60, 26, -100), trim, 3)
        g.poly(arch(cx, -66, 16, -94), (60, 46, 50), 0)
    g.line([(-206, -130), (206, -130)], 3, trim)


def colosseum(p, x, y, s, c, k):
    col = _c(c, (230, 208, 168))
    d = darker(col, 0.84)
    hole = (140, 112, 84)
    g = Sk(p, x, y, s, wob=0.35)
    top = [(-262, -292), (40, -292), (66, -262), (92, -252), (116, -214), (150, -202), (190, -170), (230, -160),
           (262, -150)]

    def top_at(xx):
        for (a0, b0), (a1, b1) in zip(top, top[1:]):
            if a0 <= xx <= a1:
                return b0 + (b1 - b0) * (xx - a0) / max(1, a1 - a0)
        return top[-1][1]

    g.poly([(-262, 0)] + top + [(262, 0)], col, 6)
    tiers = ((0, -82), (-88, -164), (-170, -246))
    for yb, yt in tiers:
        for i in range(10):
            cx = -236 + i * 52
            if top_at(cx) < yt - 6:
                g.poly(arch(cx, yb - 6, 30, yt + 20), hole, 3)
            elif top_at(cx) < yb - 30:
                g.poly([(cx - 15, yb - 6), (cx + 15, yb - 6), (cx + 15, top_at(cx) + 8), (cx - 15, top_at(cx) + 14)],
                       hole, 3)
        xs = [xx for xx in range(-262, 263, 4) if top_at(xx) < yt - 2]
        if xs:
            g.line([(-262, yt - 3), (xs[-1], yt - 3)], 4, d)
    for i in range(6):
        cx = -236 + i * 52
        g.rect(cx - 8, -280, cx + 8, -262, hole, 2.4)
    g.rect(-268, -12, 268, 0, d, 4)


# ------------------------------------------------------------------ Middle East, Africa, Asia
def taj_mahal(p, x, y, s, c, k):
    col = _c(c, MARBLE)
    d = darker(col, 0.86)
    g = Sk(p, x, y, s, wob=0.3)
    for xm in (-216, 216):
        g.rect(xm - 12, -330, xm + 12, -34, col, 4)
        for yb in (-120, -210, -290):
            g.rect(xm - 19, yb - 6, xm + 19, yb + 2, d, 3)
        g.poly(profile_pts(DOME, xm, -330, 40, 42), col, 4)
        g.line([(xm, -362), (xm, -380)], 3, GOLD)
    g.rect(-244, -34, 244, 0, d, 5)
    g.rect(-142, -212, 142, -34, col, 6)
    for f in (1, -1):
        g.line([(-96 * f, -212), (-96 * f, -34)], 3, d)
        for yb, yt in ((-44, -90), (-128, -172)):
            g.poly(arch(-119 * f, yb, 30, yt, "pointed", 6), d, 3)
        g.rect(-118 * f - 18, -244, -118 * f + 18, -212, col, 3)
        g.poly(profile_pts(ONION, -118 * f, -244, 50, 52), col, 4)
        g.line([(-118 * f, -296), (-118 * f, -310)], 3, GOLD)
    g.rect(-58, -204, 58, -34, col, 5)
    g.poly(arch(0, -34, 80, -124, "pointed", 8), d, 4)
    g.poly(arch(0, -34, 36, -72, "pointed", 6), (180, 186, 206), 3)
    g.rect(-62, -244, 62, -212, col, 5)
    g.poly(profile_pts(ONION, 0, -244, 150, 170), col, 6)
    g.line([(0, -414), (0, -446)], 4, GOLD)
    g.circ(0, -426, 5, GOLD, 2)


def mosque(p, x, y, s, c, k):
    dome = _c(c, (78, 146, 196))
    col = MARBLE
    d = MARBLE_D
    g = Sk(p, x, y, s, wob=0.3)
    for xm in (-214, 214):
        g.rect(xm - 13, -430, xm + 13, 0, col, 4)
        for yb in (-260, -360):
            g.rect(xm - 21, yb - 6, xm + 21, yb + 4, d, 3)
        g.poly([(xm - 15, -430), (xm, -486), (xm + 15, -430)], dome, 4)
        crescent(g, xm, -500, 9)
    g.rect(-82, -206, 82, -170, col, 5)
    g.poly(profile_pts(DOME, 0, -206, 196, 196), dome, 6)
    g.line([(0, -355), (0, -376)], 4, GOLD)
    crescent(g, 0, -390, 12)
    for f in (1, -1):
        g.poly(profile_pts(DOME, -124 * f, -170, 74, 70), dome, 4)
    g.rect(-170, -174, 170, 0, col, 6)
    g.poly(arch(0, 0, 70, -96, "pointed", 8), (70, 80, 110), 5)
    for f in (1, -1):
        for xx in (-70, -126):
            g.poly(arch(xx * f, -40, 30, -92, "pointed", 6), d, 3)
    g.line([(-170, -140), (170, -140)], 3, d)


def pagoda(p, x, y, s, c, k):
    col = _c(c, (200, 64, 52))
    roof = (52, 58, 74)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-124, -22, 124, 0, STONE, 5)
    yy = -22
    for i in range(5):
        bw, bh = 176 - i * 26, 66 - i * 5
        g.rect(-bw / 2, yy - bh, bw / 2, yy, col, 5)
        g.rect(-bw * 0.18, yy - bh * 0.72, bw * 0.18, yy, (90, 40, 34), 3)
        for f in (1, -1):
            g.line([(bw * 0.32 * f, yy - bh + 6), (bw * 0.32 * f, yy - 4)], 3, darker(col, 0.7))
        rw = bw / 2 + 48 - i * 4
        yb = yy - bh + 4
        g.poly([(-rw - 8, yb - 26), (-rw + 14, yb - 4), (rw - 14, yb - 4), (rw + 8, yb - 26),
                (bw / 2 - 8, yb - 36), (-bw / 2 + 8, yb - 36)], roof, 5)
        yy = yb - 34
    g.line([(0, yy), (0, yy - 96)], 5, GOLD)
    for j in range(5):
        g.ell(0, yy - 18 - j * 15, 12 - j, 4, GOLD, 2.4)
    g.circ(0, yy - 100, 7, GOLD, 3)


def torii(p, x, y, s, c, k):
    col = _c(c, (216, 66, 46))
    blk = (42, 42, 50)
    g = Sk(p, x, y, s, wob=0.3)
    for f in (1, -1):
        g.poly([(-130 * f, 0), (-104 * f, 0), (-108 * f, -310), (-126 * f, -310)], col, 5)
        g.rect(-136 * f, -26, -98 * f, 0, blk, 4)
    g.rect(-164, -252, 164, -232, col, 5)
    g.rect(-170, -310, 170, -290, col, 5)
    g.poly([(-208, -346), (-186, -308), (186, -308), (208, -346), (0, -332)], blk, 5)
    g.rect(-18, -290, 18, -252, blk, 3)
    g.rect(-12, -284, 12, -258, GOLD, 0)


def sphinx(p, x, y, s, c, k):
    col = _c(c, (226, 194, 134))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.5)
    g.poly([(-240, 0), (-246, -50), (-228, -96), (-192, -120), (-120, -128), (0, -130), (84, -140), (124, -128),
            (152, -100), (162, -40), (256, -36), (264, -16), (256, 0)], col, 6)
    g.arc(-170, -40, 74, 74, 200, 330, 4, d)
    g.line([(160, -16), (256, -16)], 3, d)
    for xx in (236, 246):
        g.line([(xx, -34), (xx, -2)], 2.4, d)
    g.poly([(84, -132), (86, -200), (100, -252), (130, -270), (160, -264), (178, -232), (182, -170), (190, -120)],
           col, 5)
    for yy in (-150, -172, -194):
        g.line([(88, yy), (104, yy - 2)], 2.6, d)
        g.line([(168, yy - 2), (184, yy)], 2.6, d)
    g.poly([(118, -250), (150, -254), (166, -226), (164, -186), (152, -164), (126, -164), (114, -190)],
           lighter(col, 0.2), 4)
    g.line([(126, -220), (138, -222)], 3.5)
    g.line([(146, -222), (158, -220)], 3.5)
    g.line([(141, -214), (138, -196), (144, -194)], 2.6, d)
    g.line([(132, -180), (150, -180)], 3, d)
    g.rect(130, -164, 148, -130, d, 3)


def obelisk(p, x, y, s, c, k):
    col = _c(c, SAND)
    d = darker(col, 0.78)
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-70, -40, 70, 0, d, 5)
    g.poly([(-44, -40), (44, -40), (30, -420), (-30, -420)], col, 6)
    g.poly([(-30, -420), (0, -462), (30, -420)], GOLD, 5)
    for j in range(7):
        yy = -80 - j * 46
        g.circ(-8, yy, 5, None, 2.4, d)
        g.line([(6, yy - 8), (6, yy + 8)], 2.4, d)
        g.line([(-10, yy + 18), (10, yy + 18)], 2.4, d)


def step_pyramid(p, x, y, s, c, k):
    col = _c(c, (206, 190, 150))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.4)
    yy = 0
    for i in range(5):
        hw = 220 - i * 34
        g.poly([(-hw, yy), (hw, yy), (hw - 12, yy - 54), (-hw + 12, yy - 54)], col, 5)
        g.line([(-hw + 10, yy - 20), (hw - 10, yy - 20)], 2.4, d)
        yy -= 54
    g.poly([(-34, 0), (34, 0), (24, yy), (-24, yy)], d, 4)
    for j in range(14):
        sy = -j * (-yy / 14)
        hw = 34 - 10 * j / 14
        g.line([(-hw, sy), (hw, sy)], 2, darker(col, 0.6))
    g.rect(-56, yy - 70, 56, yy, col, 5)
    g.poly(arch(0, yy, 34, yy - 40), (70, 60, 50), 3)
    g.rect(-40, yy - 96, 40, yy - 70, d, 4)


def moai(p, x, y, s, c, k):
    col = _c(c, (146, 136, 126))
    d = darker(col, 0.72)
    g = Sk(p, x, y, s, wob=0.6)
    g.poly([(-80, 0), (-86, -140), (-90, -250), (-78, -330), (-30, -350), (40, -348), (78, -320), (82, -240),
            (78, -130), (84, 0)], col, 6)
    g.poly([(-80, -258), (76, -262), (72, -232), (-76, -228)], d, 4)
    g.poly([(-12, -236), (18, -238), (30, -150), (20, -134), (-6, -136), (-14, -150)], lighter(col, 0.12), 4)
    g.line([(-46, -110), (40, -112)], 6, d)
    g.line([(-40, -78), (36, -80)], 3, d)
    for f in (-1, 1):
        g.poly([(64 * f, -220), (88 * f, -214), (90 * f, -130), (70 * f, -130)], d, 4)
    g.line([(-60, -40), (-30, -60), (30, -60), (60, -40)], 3, d)


def great_wall(p, x, y, s, c, k):
    col = _c(c, (210, 194, 162))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.4)
    g.poly([(-330, 0), (-330, -36), (-210, -76), (-90, -124), (30, -184), (130, -232), (230, -252), (330, -244),
            (330, 0)], (148, 190, 106), 5)
    g.poly([(-330, 0), (-200, -40), (-40, -60), (120, -90), (330, -80), (330, 0)], (120, 170, 90), 0)
    path = [(-330, -40), (-210, -80), (-90, -128), (30, -188), (130, -236), (230, -256), (330, -248)]
    top = [(a, b - 46) for a, b in path]
    g.poly(top + path[::-1], col, 5)
    for i in range(len(path) - 1):
        (a0, b0), (a1, b1) = path[i], path[i + 1]
        g.line([(a0, b0 - 22), (a1, b1 - 22)], 2.4, d)
        n = int(abs(a1 - a0) / 26)
        for j in range(n):
            t = (j + 0.3) / n
            mx, my = a0 + (a1 - a0) * t, b0 + (b1 - b0) * t - 46
            g.rect(mx - 7, my - 14, mx + 7, my + 2, col, 3)
    for tx, ty, tw, th in ((-6, -186, 84, 110), (-232, -82, 56, 76)):
        g.rect(tx, ty - th, tx + tw, ty, col, 5)
        g.crenels(tx, tx + tw, ty - th, 14, col, 3)
        g.poly(arch(tx + tw / 2, ty - th * 0.3, tw * 0.3, ty - th * 0.62), DARKWIN, 3)


# ------------------------------------------------------------------ Americas, Oceania
def statue_of_liberty(p, x, y, s, c, k):
    col = _c(c, COPPER)
    d = darker(col, 0.72)
    ped = (216, 202, 174)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-104, -164, 104, 0, ped, 6)
    g.rect(-112, -30, 112, 0, darker(ped, 0.85), 5)
    g.rect(-112, -180, 112, -164, darker(ped, 0.85), 5)
    for xx in (-50, 0, 50):
        g.poly(arch(xx, -60, 22, -110), darker(ped, 0.7), 3)
    g.rect(-76, -238, 76, -180, ped, 5)
    g.rect(-56, -228, 56, -190, darker(ped, 0.9), 3)
    # torch arm (behind the head)
    g.poly([(-24, -414), (-42, -418), (-64, -522), (-48, -526)], col, 5)
    g.rect(-62, -560, -46, -522, d, 4)
    g.poly([(-72, -562), (-36, -562), (-42, -578), (-66, -578)], GOLD, 4)
    g.flame(-54, -578, 40, 56)
    g.poly([(-54, -240), (54, -240), (46, -300), (40, -372), (30, -422), (-30, -422), (-40, -372), (-50, -300)], col, 6)
    for a, b in (((-30, -244), (-20, -400)), ((0, -244), (6, -404)), ((26, -244), (18, -392)), ((-44, -300), (-34, -380))):
        g.line([a, b], 3, d)
    g.poly([(22, -400), (48, -360), (34, -334), (18, -350)], col, 4)
    g.poly([(30, -380), (66, -372), (60, -298), (24, -306)], d, 4)
    for i in range(7):
        a = math.radians(-160 + i * 23.3)
        g.poly([(math.cos(a) * 20 - math.sin(a) * 6, -466 + math.sin(a) * 20 + math.cos(a) * 6),
                (math.cos(a) * 54, -466 + math.sin(a) * 54),
                (math.cos(a) * 20 + math.sin(a) * 6, -466 + math.sin(a) * 20 - math.cos(a) * 6)], col, 3)
    g.circ(0, -446, 27, col, 5)
    g.rect(-27, -472, 27, -460, col, 4)
    g.circ(-9, -448, 2.6, d, 0)
    g.circ(9, -448, 2.6, d, 0)
    g.line([(-6, -432), (6, -432)], 2.4, d)


def capitol(p, x, y, s, c, k):
    col = _c(c, MARBLE)
    d = darker(col, 0.86)
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-272, -122, 272, 0, col, 6)
    g.rect(-278, -136, 278, -122, d, 4)
    for i in range(30):
        xx = -260 + i * 18
        if abs(xx) > 96:
            g.line([(xx, -116), (xx, -8)], 2, d)
    for row in (-90, -46):
        for i in range(8):
            for f in (1, -1):
                xx = (110 + i * 20) * f
                g.rect(xx - 5, row - 12, xx + 5, row + 6, DARKWIN, 0)
    g.rect(-96, -152, 96, 0, col, 6)
    g.poly([(-106, -152), (106, -152), (0, -194)], col, 5)
    for i in range(8):
        g.line([(-80 + i * 23, -146), (-80 + i * 23, -6)], 4, d)
    g.rect(-84, -254, 84, -192, col, 5)
    for i in range(12):
        g.line([(-76 + i * 13.8, -248), (-76 + i * 13.8, -196)], 2.6, d)
    g.rect(-64, -284, 64, -254, col, 5)
    g.poly(arc_pts(0, -284, 68, 92, 180, 360, 20), col, 6)
    for u in (-0.66, -0.33, 0.33, 0.66):
        g.line([(u * 68 * math.cos(math.radians(t)), -284 - 92 * math.sin(math.radians(t))) for t in range(0, 85, 12)],
               2.4, d)
    g.rect(-14, -404, 14, -372, col, 4)
    g.poly(profile_pts(DOME, 0, -404, 30, 20), col, 3)
    g.line([(0, -419), (0, -440)], 4, INK)
    g.circ(0, -444, 5, INK, 0)


def white_house(p, x, y, s, c, k):
    col = _c(c, MARBLE)
    d = darker(col, 0.86)
    g = Sk(p, x, y, s, wob=0.3)
    g.line([(0, -236), (0, -310)], 4)
    g.rect(0, -310, 52, -280, WHITE, 3)
    for j in range(3):
        g.line([(0, -306 + j * 10), (52, -306 + j * 10)], 3, RED)
    g.rect(0, -310, 22, -294, (52, 72, 132), 0)
    for xx in (-150, 150):
        g.rect(xx - 10, -206, xx + 10, -178, d, 3)
    g.rect(-224, -176, 224, 0, col, 6)
    g.rect(-230, -190, 230, -176, d, 4)
    for row in (-130, -60):
        for i in range(4):
            for f in (1, -1):
                xx = (98 + i * 34) * f
                g.rect(xx - 9, row - 16, xx + 9, row + 14, (110, 140, 180), 3)
    g.rect(-74, -192, 74, 0, col, 5)
    g.poly([(-84, -192), (84, -192), (0, -236)], col, 5)
    for i in range(4):
        g.rect(-60 + i * 38, -186, -50 + i * 38, -6, WHITE, 3)
    g.poly(arch(0, 0, 32, -50), (110, 140, 180), 3)


def skyscraper(p, x, y, s, c, k):
    col = _c(c, (172, 192, 212))
    d = darker(col, 0.75)
    g = Sk(p, x, y, s, wob=0.3)
    g.line([(0, -620), (0, -706)], 5)
    for x0, x1, y0, y1, cols in ((-92, 92, -384, 0, 6), (-68, 68, -504, -384, 4), (-42, 42, -584, -504, 3)):
        g.rect(x0, y0, x1, y1, col, 6)
        g.windows(x0 + 8, y0 + 10, x1 - 8, y1 - 10, cols, max(2, int((y1 - y0) / 34)), (70, 92, 130), 0.4, 2,
                  lit=(250, 220, 120))
    g.poly([(-42, -584), (-26, -622), (26, -622), (42, -584)], d, 5)


def statue(p, x, y, s, c, k):
    col = _c(c, (112, 150, 140))
    d = darker(col, 0.7)
    ped = (214, 206, 190)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-76, -150, 76, 0, ped, 6)
    g.rect(-86, -170, 86, -150, darker(ped, 0.85), 5)
    g.rect(-86, -22, 86, 0, darker(ped, 0.85), 5)
    if k.get("label"):
        g.text(str(k["label"])[:12].upper(), 0, -86, 26, (90, 84, 70))
    hip, sh, head = (0, -290), (0, -390), (0, -430)
    g.line([(-34, -170), hip, (30, -170)], 16, col)
    g.line([hip, sh], 18, col)
    g.line([sh, (-40, -330), (-30, -300)], 14, col)
    g.line([sh, (50, -420), (96, -446)], 14, col)
    g.circ(head[0], head[1], 34, col, 6)
    g.line([(-14, -436), (-4, -436)], 3, d)
    g.line([(8, -436), (18, -436)], 3, d)
    g.line([(-34, -170), hip, (30, -170)], 4, d)


def opera_house(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-300, -50, 300, 0, (200, 168, 136), 5)
    shells = [(-240, -50, 150, 160), (-130, -50, 170, 210), (-10, -50, 130, 150), (90, -50, 160, 200), (190, -50, 110, 130)]
    for x0, yb, w, h in shells:
        pts = [(x0, yb)] + [(x0 + w * t, yb - h * math.sin(math.pi * t * 0.72) ** 0.9 - h * 0.25 * t)
                            for t in (0.15, 0.35, 0.55, 0.75)] + [(x0 + w * 0.92, yb - h * 1.0), (x0 + w, yb)]
        g.poly(pts, (250, 250, 246), 5)
        for t in (0.35, 0.65):
            g.line([(x0 + w * t, yb), (x0 + w * 0.85, yb - h * 0.9)], 2, (200, 204, 214))
    g.rect(-300, -62, 300, -50, (226, 200, 170), 4)


def suspension_bridge(p, x, y, s, c, k):
    col = _c(c, (204, 74, 50))
    g = Sk(p, x, y, s, wob=0.3)
    deck = -110
    for tx in (-180, 180):
        g.rect(tx - 16, -380, tx + 16, 0, col, 5)
        for yy in (-360, -280, -200):
            g.line([(tx - 16, yy), (tx + 16, yy)], 5, darker(col, 0.7))
    span = lambda t, x0, x1, ytop, ylow: ylow - (ylow - ytop) * (2 * t - 1) ** 2
    cab = [(-180 + 360 * i / 20, span(i / 20, 0, 0, -370, deck - 20)) for i in range(21)]
    g.line(cab, 5, col)
    g.line([(-180, -370), (-260, deck - 10), (-320, deck)], 5, col)
    g.line([(180, -370), (260, deck - 10), (320, deck)], 5, col)
    for cx, cy in cab[1:-1]:
        g.line([(cx, cy), (cx, deck)], 2, darker(col, 0.8))
    g.rect(-330, deck, 330, deck + 20, col, 5)


# ------------------------------------------------------------------ everywhere
def bridge(p, x, y, s, c, k):
    col = _c(c, STONE)
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.4)
    g.poly(arcade(-300, 300, 0, -150, 3, 26, 104), col, 6)
    g.rect(-306, -176, 306, -150, d, 5)
    for i in range(16):
        g.line([(-290 + i * 38.6, -174), (-290 + i * 38.6, -152)], 2.4, darker(col, 0.6))
    for cx in (-191, 0, 191):
        g.arc(cx, -21, 96, 96, 180, 360, 3, d)


def aqueduct(p, x, y, s, c, k):
    col = _c(c, (222, 196, 150))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, wob=0.4)
    g.poly(arcade(-300, 300, 0, -190, 4, 30, 150), col, 6)
    g.poly(arcade(-300, 300, -190, -300, 8, 16, 86), col, 5)
    g.rect(-306, -322, 306, -300, d, 5)
    g.line([(-300, -194), (300, -194)], 3, d)


def barn(p, x, y, s, c, k):
    col = _c(c, (182, 52, 44))
    g = Sk(p, x, y, s, wob=0.4)
    g.rect(-142, -172, 142, 0, col, 6)
    g.poly([(-152, -168), (-124, -240), (0, -292), (124, -240), (152, -168)], (88, 90, 104), 6)
    g.rect(-62, -130, 62, 0, col, 5)
    g.line([(-62, -130), (62, 0)], 5, WHITE)
    g.line([(62, -130), (-62, 0)], 5, WHITE)
    g.rect(-62, -130, 62, 0, None, 6, WHITE)
    g.rect(-28, -232, 28, -178, (240, 206, 90), 5, WHITE)
    for xx in (-16, 0, 16):
        g.line([(xx, -200), (xx + 6, -184)], 2.4, (200, 160, 60))
    for xx in (-110, 110):
        g.rect(xx - 16, -120, xx + 16, -84, GLASS, 4, WHITE)


def hut(p, x, y, s, c, k):
    roof = _c(c, (226, 190, 104))
    g = Sk(p, x, y, s, wob=0.6)
    g.poly([(-94, 0), (-98, -60), (-92, -112), (92, -112), (98, -60), (94, 0)], (190, 140, 92), 6)
    g.poly(arch(10, 0, 50, -54), (80, 54, 40), 4)
    pts = [(-130, -100)]
    for i in range(13):
        pts.append((-130 + i * 21.6, -100 + (12 if i % 2 else 0)))
    pts += [(130, -100), (0, -246)]
    g.poly(pts, roof, 6)
    for xx in (-70, -30, 10, 50, 90):
        g.line([(xx * 0.9, -108), (xx * 0.25, -220)], 2.4, darker(roof, 0.75))


def igloo(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.4)
    ice = (238, 246, 255)
    line = (160, 196, 220)
    g.poly(arc_pts(0, 0, 146, 128, 180, 360, 24), ice, 6)
    for j, yy in enumerate((-34, -68, -98)):
        rx = 146 * math.sqrt(max(0, 1 - (yy / 128) ** 2))
        g.line([(-rx, yy), (rx, yy)], 2.6, line)
        for i in range(-4, 5):
            xx = i * 34 + (17 if j % 2 else 0)
            if abs(xx) < rx - 10:
                g.line([(xx, yy), (xx, yy + 32 if yy < -34 else 0)], 2.4, line)
    g.poly(arc_pts(100, 0, 58, 62, 180, 360, 14), ice, 5)
    g.poly(arc_pts(110, 0, 28, 36, 180, 360, 10), (60, 74, 100), 3)


def watchtower(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.5)
    for f in (1, -1):
        g.line([(-86 * f, 0), (-56 * f, -270)], 9, WOOD_D)
    for yy, hw in ((-80, 78), (-170, 68)):
        g.line([(-hw, yy), (hw, yy - 60)], 5, WOOD)
        g.line([(hw, yy), (-hw, yy - 60)], 5, WOOD)
    g.rect(-72, -350, 72, -266, WOOD, 6)
    g.rect(-50, -334, 50, -296, (60, 50, 44), 3)
    g.poly([(-90, -346), (0, -410), (90, -346)], WOOD_D, 6)
    g.rect(-80, -270, 80, -256, WOOD_D, 4)


def _num(k, key, default):
    try:
        return float(k.get(key, default))
    except (TypeError, ValueError):
        return default


def brandenburg_gate(p, x, y, s, c, k):
    col = _c(c, (232, 218, 186))
    d = darker(col, 0.82)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-236, -26, 236, 0, d, 5)
    for i in range(6):
        cx = -200 + i * 80
        g.rect(cx - 14, -252, cx + 14, -26, col, 5)
        g.line([(cx, -246), (cx, -32)], 2, d)
    g.rect(-244, -300, 244, -252, col, 6)
    for i in range(16):
        g.line([(-228 + i * 30.4, -292), (-228 + i * 30.4, -262)], 3, d)
    g.rect(-150, -336, 150, -300, col, 5)
    gc, gd = COPPER, COPPER_D
    from .props_life import horse
    for hx, fl in ((-74, True), (-40, True), (40, False), (74, False)):
        X, Y = g.pt(hx, -336)
        horse(p, X, Y, s * 0.17, gc, {"saddle": False, "flip": fl})
    g.poly([(-24, -336), (24, -336), (20, -366), (-20, -366)], gc, 4)
    g.line([(0, -366), (0, -400)], 6, gc)
    g.circ(0, -408, 8, gc, 3)
    g.line([(8, -380), (22, -440)], 3, gd)
    g.circ(24, -446, 9, None, 3, gd)


PLACES = {
    "eiffel_tower": ("bottom", eiffel_tower, "Eiffel Tower (Paris, France)"),
    "arc_de_triomphe": ("bottom", arc_de_triomphe, "Arc de Triomphe (Paris, Napoleon's victories)"),
    "big_ben": ("bottom", big_ben, "Big Ben clock tower (London, Britain)"),
    "leaning_tower": ("bottom", leaning_tower, "Leaning Tower of Pisa (Italy). params: angle"),
    "windmill": ("bottom", windmill, "Dutch windmill (Netherlands, farms). params: angle (sail rotation)"),
    "lighthouse": ("bottom", lighthouse, "lighthouse on rocks (coast, sea). color = stripes. params: lit (bool)"),
    "cathedral": ("bottom", cathedral, "gothic cathedral like Notre-Dame (church, religion, medieval Europe)"),
    "church": ("bottom", church, "small village church with a steeple. color = roof"),
    "stonehenge": ("bottom", stonehenge, "Stonehenge (ancient Britain, prehistory)"),
    "kremlin": ("bottom", kremlin, "Kremlin tower with red star and walls (Moscow, Russia, USSR)"),
    "onion_domes": ("bottom", onion_domes, "colorful onion-dome cathedral like St Basil's (Russia)"),
    "brandenburg_gate": ("bottom", brandenburg_gate, "Brandenburg Gate (Berlin, Germany, Prussia)"),
    "taj_mahal": ("bottom", taj_mahal, "Taj Mahal (India, Mughal empire)"),
    "mosque": ("bottom", mosque, "mosque with dome and minarets (Ottomans, Islam, Middle East). color = domes"),
    "pagoda": ("bottom", pagoda, "five-tier pagoda (Japan, China, East Asia). color = walls"),
    "torii": ("bottom", torii, "Japanese torii gate (Japan, shrine)"),
    "sphinx": ("bottom", sphinx, "Great Sphinx (ancient Egypt)"),
    "obelisk": ("bottom", obelisk, "obelisk (Egypt, monuments, Washington)"),
    "step_pyramid": ("bottom", step_pyramid, "stepped temple pyramid (Aztec, Maya, Mesoamerica, Mesopotamia)"),
    "moai": ("bottom", moai, "Easter Island stone head"),
    "great_wall": ("bottom", great_wall, "Great Wall of China on a hill (China, defense)"),
    "statue_of_liberty": ("bottom", statue_of_liberty, "Statue of Liberty (New York, USA, immigration)"),
    "capitol": ("bottom", capitol, "US Capitol dome (Congress, government, parliament)"),
    "white_house": ("bottom", white_house, "the White House (US president)"),
    "skyscraper": ("bottom", skyscraper, "art-deco skyscraper (New York, modern city, business). color"),
    "statue": ("bottom", statue, "bronze statue of a hero on a pedestal. color, params: label"),
    "opera_house": ("bottom", opera_house, "Sydney Opera House (Australia)"),
    "suspension_bridge": ("bottom", suspension_bridge, "big suspension bridge like the Golden Gate. color"),
    "bridge": ("bottom", bridge, "old stone arch bridge (river crossing). color"),
    "colosseum": ("bottom", colosseum, "the Colosseum (ancient Rome, gladiators, arenas)"),
    "aqueduct": ("bottom", aqueduct, "Roman aqueduct with two rows of arches (Rome, engineering)"),
    "barn": ("bottom", barn, "red farm barn (farming, countryside). color"),
    "hut": ("bottom", hut, "straw-roofed hut (village, tribe, poor farmers)"),
    "igloo": ("bottom", igloo, "igloo (Arctic, Inuit, cold)"),
    "watchtower": ("bottom", watchtower, "wooden watchtower (frontier, border, lookout)"),
}
