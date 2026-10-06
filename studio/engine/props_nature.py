"""Sea, ships and nature props."""
import math

from .palette import color as C, INK, RED, WHITE, darker, lighter
from .props_kit import (Sk, arc_pts, ellipse, rounded, star_pts, WOOD, WOOD_D, WOOD_L, IRON, IRON_D, STEEL, GOLD,
                        GOLD_D, GLASS, LEAF, LEAF_D, SNOW, ICE, WATER, CREAM, DARKWIN, SAND)


def _c(c, default):
    return C(c, default) if c is not None else default


def _num(k, key, default):
    try:
        return float(k.get(key, default))
    except (TypeError, ValueError):
        return default


def _flip(k):
    return bool(k.get("flip")) or str(k.get("facing", "")).lower() == "left"


def tube(g, pts, w, col):
    """A thick outlined line (tentacles, legs, branches)."""
    g.line(pts, w + 6, INK)
    g.line(pts, w, col)


def waterline(g, x0, x1, y, col=(110, 170, 210), w=4):
    pts = []
    n = max(4, int((x1 - x0) / 24))
    for i in range(n + 1):
        pts.append((x0 + (x1 - x0) * i / n, y + (5 if i % 2 else -3)))
    g.line(pts, w, col)


# ------------------------------------------------------------------ sea life
def fish(p, x, y, s, c, k):
    col = _c(c, (246, 150, 60))
    d = darker(col, 0.75)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.poly([(-54, 0), (-98, -36), (-86, 0), (-98, 36)], col, 5)
    g.poly([(-24, -32), (2, -60), (28, -34)], d, 4)
    g.poly([(-4, 30), (12, 52), (24, 30)], d, 4)
    g.poly(ellipse(0, 0, 68, 36, 26), col, 6)
    for cx in (-30, -8, 14):
        for cy in (-12, 10):
            g.arc(cx, cy, 10, 11, -70, 70, 2.4, d)
    g.arc(30, 0, 12, 26, -70, 70, 3.5, d)
    g.circ(46, -8, 9, WHITE, 3)
    g.circ(48, -8, 4, INK, 0)
    g.line([(58, 10), (66, 8)], 3)


def shark(p, x, y, s, c, k):
    col = _c(c, (140, 156, 178))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.poly([(40, -48), (-34, -122), (-42, -44)], col, 5)
    g.poly([(196, 4), (180, -22), (120, -44), (40, -52), (-60, -44), (-150, -20), (-190, -10), (-252, -74),
            (-226, -4), (-248, 44), (-188, 12), (-150, 18), (-60, 34), (40, 40), (120, 34), (172, 22)], col, 6)
    g.poly([(178, 12), (120, 28), (40, 34), (-60, 28), (-140, 14), (-60, 12), (40, 16), (140, 10)], WHITE, 0)
    g.poly([(60, 26), (8, 84), (24, 30)], darker(col, 0.85), 4)
    for xx in (100, 112, 124):
        g.arc(xx - 30, 0, 30, 22, -40, 40, 3, darker(col, 0.7))
    g.circ(150, -16, 6, INK, 0)
    g.circ(152, -18, 2, WHITE, 0)
    g.line([(190, 12), (168, 18), (140, 16)], 3.5)
    for i in range(4):
        tx = 176 - i * 10
        g.poly([(tx - 4, 16), (tx, 23), (tx + 4, 16)], WHITE, 1.5)


def whale(p, x, y, s, c, k):
    col = _c(c, (86, 126, 184))
    belly = lighter(col, 0.65)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    if k.get("spout", True) is not False:
        for a, h in ((-30, 70), (-10, 90), (10, 86), (30, 66)):
            g.line([(120, -78), (120 + a * 0.6, -78 - h * 0.7), (120 + a * 1.4, -78 - h)], 5, (150, 200, 236))
        for dx, dy in ((-30, -160), (36, -150), (0, -176), (60, -130), (-56, -132)):
            g.circ(120 + dx, dy, 6, (190, 226, 246), 2.4, (120, 180, 220))
    g.poly([(-120, -34), (-232, -14), (-268, -60), (-298, -50), (-258, 4), (-296, 44), (-262, 50), (-228, 22),
            (-118, 44)], col, 5)
    g.poly(ellipse(30, 0, 196, 82, 30), col, 6)
    g.poly(arc_pts(40, 6, 180, 74, 15, 165, 14), belly, 0)
    for yy in (34, 48, 62):
        g.line([(-60, yy), (140 - (yy - 34) * 1.5, yy - 6)], 2.4, darker(belly, 0.8))
    g.poly([(70, 52), (24, 112), (100, 64)], darker(col, 0.85), 4)
    g.circ(160, 4, 6, INK, 0)
    g.arc(170, 18, 46, 18, 120, 175, 3.5)


def octopus(p, x, y, s, c, k):
    col = _c(c, (206, 96, 156))
    g = Sk(p, x, y, s, wob=0.3)
    for i in range(6):
        sx = -56 + i * 22.4
        side = -1 if i < 3 else 1
        pts = []
        for j in range(9):
            t = j / 8
            pts.append((sx + side * (60 * t + 22 * math.sin(t * 7 + i)), -10 + 130 * t - 40 * t * t))
        tube(g, pts, 18, col)
        for j in (2, 4, 6):
            px, py = pts[j]
            g.circ(px, py + 4, 3.5, lighter(col, 0.5), 0)
    g.poly(ellipse(0, -70, 82, 92, 28), col, 6)
    for cx in (-28, 28):
        g.circ(cx, -60, 17, WHITE, 4)
        g.circ(cx + 3, -58, 8, INK, 0)
    g.arc(0, -36, 16, 9, 20, 160, 3.5)
    for cx, cy in ((-40, -118), (24, -132), (52, -100)):
        g.circ(cx, cy, 7, lighter(col, 0.3), 0)


def crab(p, x, y, s, c, k):
    col = _c(c, (222, 82, 60))
    g = Sk(p, x, y, s, wob=0.3)
    for f in (1, -1):
        for j in range(3):
            tube(g, [(54 * f, -40 - j * 10), (96 * f + j * 10 * f, -60 + j * 6), (110 * f + j * 12 * f, -2)], 9, col)
        tube(g, [(56 * f, -62), (94 * f, -96), (100 * f, -126)], 12, col)
        g.poly([(100 * f, -120), (130 * f, -150), (140 * f, -122), (118 * f, -118), (138 * f, -100), (106 * f, -104)],
               col, 5)
        g.line([(14 * f, -86), (22 * f, -120)], 5)
        g.circ(22 * f, -126, 12, WHITE, 4)
        g.circ(24 * f, -124, 5, INK, 0)
    g.poly(ellipse(0, -52, 82, 42, 24), col, 6)
    g.arc(0, -48, 18, 10, 20, 160, 3.5)
    for cx in (-40, 40):
        g.circ(cx, -64, 5, lighter(col, 0.4), 0)


def jellyfish(p, x, y, s, c, k):
    col = _c(c, (240, 150, 206))
    g = Sk(p, x, y, s, wob=0.3)
    for i in range(5):
        sx = -44 + i * 22
        pts = [(sx + 10 * math.sin(j * 1.2 + i), -30 + j * 22) for j in range(8)]
        g.line(pts, 5, darker(col, 0.8))
    bottom = []
    for i in range(9):
        bx = 66 - i * 16.5
        bottom.append((bx, -30 + (8 if i % 2 else 0)))
    g.poly(arc_pts(0, -30, 66, 74, 180, 360, 18) + bottom, col, 6)
    for cx, cy in ((-24, -66), (10, -80), (32, -54)):
        g.circ(cx, cy, 8, lighter(col, 0.45), 0)


def anchor(p, x, y, s, c, k):
    col = _c(c, (84, 90, 104))
    g = Sk(p, x, y, s, wob=0.3)
    g.circ(0, -114, 22, None, 18, INK)
    g.circ(0, -114, 22, None, 11, col)
    tube(g, arc_pts(0, 10, 92, 90, 165, 15, 16), 14, col)
    for f in (1, -1):
        g.poly([(-80 * f, 34), (-116 * f, 6), (-100 * f, 58)], col, 5)
    g.rect(-11, -94, 11, 98, col, 5)
    g.rect(-66, -86, 66, -66, col, 5)
    g.circ(-66, -76, 8, col, 4)
    g.circ(66, -76, 8, col, 4)
    if k.get("rope", True) is not False:
        rope = (196, 160, 104)
        tube(g, [(18, -120), (54, -90), (40, -30), (-36, 0), (-30, 50), (30, 70)], 7, rope)


def wave(p, x, y, s, c, k):
    col = _c(c, (66, 128, 196))
    lt = lighter(col, 0.45)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    body = [(-240, 0), (-196, -26), (-150, -60), (-104, -110), (-84, -170), (-92, -228), (-64, -282), (0, -312),
            (84, -302), (152, -252), (202, -162), (232, -64), (246, 0)]
    g.poly(body, col, 6)
    g.poly([(-60, -232), (-30, -262), (30, -270), (90, -240), (130, -180), (150, -100), (160, 0), (120, 0),
            (110, -100), (90, -170), (50, -214), (0, -226)], lt, 0)
    for off in (0, 1, 2):
        g.line([(-170 + off * 40, -10), (-100 + off * 34, -60), (-60 + off * 30, -130), (-40 + off * 26, -190)], 3,
               darker(col, 0.8))
    ph = 2 * math.pi * _num(k, "t", 0) / 2.4
    crest = [(-92, -228), (-70, -270), (-30, -298), (20, -306), (80, -296), (130, -262), (160, -226)]
    for i, (cx, cy) in enumerate(crest):
        g.circ(cx, cy + 5 * math.sin(ph + i * 0.9), 22 - i, WHITE, 4)
    for i, (cx, cy) in enumerate(((-86, -196), (-66, -190), (-104, -180))):
        g.circ(cx, cy + 4 * math.sin(ph + i * 2), 10, WHITE, 3)
    for i, (cx, cy) in enumerate(((-130, -250), (-150, -220), (-112, -282), (-160, -270))):
        g.circ(cx - 8 * math.sin(ph + i), cy - 6 * math.cos(ph + i), 6, WHITE, 2.4)


def iceberg(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.5)
    shape = [(-176, 0), (-150, -62), (-112, -92), (-80, -172), (-42, -150), (0, -262), (42, -200), (72, -222),
             (112, -122), (150, -84), (186, 0)]
    g.poly(shape, SNOW, 6)
    g.poly([(0, -262), (42, -200), (20, -120), (40, -40), (0, 0), (-10, -120)], ICE, 0)
    g.poly([(72, -222), (112, -122), (150, -84), (186, 0), (120, 0), (100, -80)], ICE, 0)
    g.poly([(-80, -172), (-42, -150), (-60, -90), (-80, -40), (-100, -100)], ICE, 0)
    g.poly(shape, None, 6)
    waterline(g, -230, 230, 0, (90, 160, 210), 5)


def submarine(p, x, y, s, c, k):
    col = _c(c, (88, 98, 116))
    d = darker(col, 0.72)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.poly([(-200, -10), (-240, -48), (-228, -6)], d, 4)
    g.poly([(-200, 10), (-240, 48), (-228, 6)], d, 4)
    for dy in (-16, 16):
        g.ell(-246, dy, 6, 14, GOLD, 3)
    g.poly(ellipse(0, 0, 232, 44, 30), col, 6)
    g.line([(-200, 18), (210, 14)], 3, d)
    g.poly([(-24, -40), (-14, -104), (72, -104), (86, -40)], col, 5)
    g.line([(-30, -76), (-6, -76)], 4, d)
    g.line([(40, -104), (40, -150)], 5)
    g.rect(40, -158, 64, -146, d, 3)
    for i in range(7):
        g.circ(-150 + i * 46, 0, 7, GLASS, 3)
    if k.get("label"):
        g.text(str(k["label"])[:6].upper(), 30, -72, 26, WHITE)


def periscope(p, x, y, s, c, k):
    col = _c(c, (88, 98, 116))
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-9, -140, 9, -8, col, 5)
    g.rect(-9, -160, 34, -136, col, 5)
    g.rect(28, -156, 38, -140, GLASS, 3)
    for f in (1, -1):
        g.arc(0, -4, 60, 14, 180 if f < 0 else 0, 270 if f < 0 else -90, 4, WHITE)
    waterline(g, -110, 110, 0, (90, 160, 210), 5)


def buoy(p, x, y, s, c, k):
    col = _c(c, (214, 60, 55))
    g = Sk(p, x, y, s, wob=0.3)
    for f in (1, -1):
        g.line([(-34 * f, -70), (-12 * f, -170)], 5, IRON_D)
    g.line([(0, -70), (0, -170)], 5, IRON_D)
    g.circ(0, -184, 18, (255, 226, 120), 4)
    g.poly(arc_pts(0, -40, 56, 44, 180, 360, 14) + [(56, -16), (-56, -16)], col, 6)
    g.rect(-56, -48, 56, -30, WHITE, 4)
    waterline(g, -110, 110, -10, (90, 160, 210), 5)


def lifebuoy(p, x, y, s, c, k):
    col = _c(c, (220, 64, 56))
    g = Sk(p, x, y, s, wob=0.3)
    g.circ(0, 0, 64, None, 40, INK)
    g.circ(0, 0, 64, None, 32, WHITE)
    for a in (0, 90, 180, 270):
        g.arc(0, 0, 64, 64, a + 20, a + 70, 32, col)
    rope = (200, 170, 120)
    for a in (45, 135, 225, 315):
        g.arc(math.cos(math.radians(a)) * 80, math.sin(math.radians(a)) * 80, 26, 26, a - 70, a + 70, 4, rope)


def treasure_chest(p, x, y, s, c, k):
    col = _c(c, WOOD)
    d = darker(col, 0.7)
    g = Sk(p, x, y, s, wob=0.35)
    is_open = k.get("open", True) is not False
    if is_open:
        g.poly([(-116, -112), (-104, -206), (104, -206), (116, -112)], d, 6)
        g.rect(-74, -204, -58, -114, GOLD, 3)
        g.rect(58, -204, 74, -114, GOLD, 3)
        g.poly(arc_pts(0, -112, 108, 40, 180, 360, 14), GOLD, 5)
        for cx, cy in ((-70, -132), (-36, -146), (0, -150), (36, -144), (70, -130), (-14, -136), (20, -128)):
            g.circ(cx, cy, 13, GOLD, 3, GOLD_D)
        for cx, cy, gc in ((-50, -150, (220, 50, 70)), (48, -152, (60, 110, 220)), (6, -164, (60, 180, 100))):
            g.poly([(cx, cy - 14), (cx + 11, cy), (cx, cy + 12), (cx - 11, cy)], gc, 3)
        for cx, cy, r in ((-90, -190, 16), (92, -176, 12), (20, -196, 10)):
            g.poly(star_pts(cx, cy, r, 0.3, 4, -90), WHITE, 0)
    else:
        g.poly(rounded(-116, -190, 116, -110, 40)[:12] + [(116, -110), (-116, -110)], col, 6)
    g.rect(-112, -112, 112, 0, col, 6)
    for xx in (-74, 58):
        g.rect(xx, -112, xx + 16, 0, GOLD, 3)
    g.line([(-112, -60), (112, -60)], 3, d)
    g.rect(-18, -96, 18, -56, GOLD, 4)
    g.circ(0, -82, 5, INK, 0)
    g.line([(0, -80), (0, -68)], 3)


def palm_tree(p, x, y, s, c, k):
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    trunk = (176, 128, 84)
    n = 9
    pts = [(46 * (i / n) ** 2, -330 * i / n) for i in range(n + 1)]
    for i in range(n):
        (a, b), (c2, d2) = pts[i], pts[i + 1]
        w0, w1 = 20 - i * 1.0, 20 - (i + 1) * 1.0
        g.poly([(a - w0, b), (a + w0, b), (c2 + w1 + 3, d2 - 2), (c2 - w1 - 3, d2 - 2)], trunk, 4)
    cx, cy = pts[-1]
    leaf = _c(c, LEAF)
    for ang, ln in ((-170, 150), (-140, 170), (-100, 120), (-60, 150), (-25, 170), (10, 140), (160, 120)):
        a = math.radians(ang)
        spine = []
        for j in range(9):
            t = j / 8
            spine.append((cx + math.cos(a) * ln * t, cy + math.sin(a) * ln * t + 60 * t * t))
        left, right = [], []
        for j, (sx, sy) in enumerate(spine):
            t = j / 8
            wdt = 26 * math.sin(math.pi * t) * (1 if j % 2 else 0.6)
            nx, ny = -math.sin(a), math.cos(a)
            left.append((sx + nx * wdt, sy + ny * wdt))
            right.append((sx - nx * wdt, sy - ny * wdt))
        g.poly(left + right[::-1], leaf, 4)
        g.line(spine, 2.6, darker(leaf, 0.7))
    for dx, dy in ((-10, 10), (12, 12), (0, 22)):
        g.circ(cx + dx, cy + dy, 13, (120, 80, 50), 4)


def seagull(p, x, y, s, c, k):
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    gray = (176, 182, 196)
    g.poly([(-6, -2), (-30, -34), (-62, -40), (-90, -22), (-52, -22), (-26, -6)], WHITE, 4)
    g.poly([(-62, -40), (-90, -22), (-70, -24)], gray, 0)
    g.poly(ellipse(0, 0, 32, 12, 16), WHITE, 4)
    g.poly([(6, -4), (34, -40), (66, -44), (88, -30), (52, -24), (24, -6)], WHITE, 4)
    g.poly([(66, -44), (88, -30), (72, -30)], gray, 0)
    g.circ(30, -8, 12, WHITE, 4)
    g.poly([(40, -8), (56, -4), (40, -2)], (246, 170, 60), 2.4)
    g.circ(33, -11, 2.4, INK, 0)


def rowboat(p, x, y, s, c, k):
    col = _c(c, WOOD)
    d = darker(col, 0.7)
    g = Sk(p, x, y, s, wob=0.35)
    for f in (1, -1):
        g.line([(-30 * f, -54), (-150 * f, 22)], 6, WOOD_D)
        g.ell(-158 * f, 26, 18, 8, WOOD_L, 3)
    g.poly([(-146, -62), (146, -62), (118, -8), (98, 0), (-100, 0), (-126, -14)], col, 6)
    for yy in (-44, -26):
        g.line([(-136, yy), (134, yy)], 2.6, d)
    g.rect(-150, -70, 150, -60, d, 4)


def galleon(p, x, y, s, c, k):
    pirate = bool(k.get("pirate"))
    hull = _c(c, (124, 80, 50))
    trim = (232, 190, 84)
    sail = (60, 60, 68) if pirate else (250, 244, 226)
    flag = (30, 30, 34) if pirate else _c(k.get("flag"), RED)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    masts = ((-118, -470, 150), (14, -544, 180), (138, -500, 150))
    for mx, top, w in masts:
        g.line([(mx, -120), (mx, top)], 8, WOOD_D)
    g.line([(236, -150), (322, -214)], 7, WOOD_D)
    g.poly([(138, -470), (318, -206), (150, -200)], sail, 4)
    for mx, top, w in masts:
        lower = (top + 70, -170)
        upper = (top + 20, top + 64)
        for (yt, yb), ww in ((upper, w * 0.7), (lower, w)):
            g.poly([(mx - ww / 2, yt), (mx + ww / 2, yt), (mx + ww / 2 + 8, yb), (mx, yb + 16), (mx - ww / 2 - 8, yb)],
                   sail, 5)
            g.line([(mx - ww / 2 - 6, yt), (mx + ww / 2 + 6, yt)], 5, WOOD_D)
            g.line([(mx, yt + 6), (mx, yb + 10)], 2.4, darker(sail, 0.85))
        g.poly([(mx, top), (mx + 46, top + 10), (mx, top + 22)], flag, 3)
    if pirate:
        mx, top = masts[1][0], masts[1][1]
        g.circ(mx + 0, -300, 22, WHITE, 3)
        g.line([(mx - 26, -264), (mx + 26, -240)], 6, WHITE)
        g.line([(mx + 26, -264), (mx - 26, -240)], 6, WHITE)
        g.circ(mx - 8, -302, 5, (60, 60, 68), 0)
        g.circ(mx + 8, -302, 5, (60, 60, 68), 0)
    g.poly([(-264, -184), (-198, -184), (-194, -126), (150, -126), (252, -160), (204, -72), (142, -12), (110, 0),
            (-190, 0), (-244, -52)], hull, 6)
    g.line([(-250, -92), (206, -92)], 5, trim)
    g.line([(-196, -128), (150, -128)], 4, trim)
    for i in range(9):
        gx = -170 + i * 38
        g.rect(gx, -80, gx + 18, -62, (50, 34, 26), 3)
    for i in range(3):
        g.rect(-252 + i * 16, -172, -242 + i * 16, -156, (250, 220, 120), 2.4)
    g.line([(-264, -196), (-198, -196)], 4, WOOD_D)


def viking_ship(p, x, y, s, c, k):
    col = _c(c, WOOD)
    d = darker(col, 0.7)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    g.line([(0, -50), (0, -380)], 9, WOOD_D)
    g.line([(-120, -350), (120, -350)], 7, WOOD_D)
    sail = [(-116, -346), (116, -346), (126, -156), (0, -140), (-126, -156)]
    g.poly(sail, (250, 244, 230), 0)
    for i in range(5):
        if i % 2 == 0:
            x0, x1 = -116 + i * 46.4, -116 + (i + 1) * 46.4
            g.poly([(x0, -346), (x1, -346), (x1 * 1.08, -150 + abs(x1) * 0.1), (x0 * 1.08, -150 + abs(x0) * 0.1)],
                   (206, 56, 52), 0)
    g.poly(sail, None, 5)
    for i in range(6):
        ox = -150 + i * 60
        g.line([(ox, -30), (ox - 40, 30)], 5, WOOD_D)
    g.poly([(-236, -112), (-208, -56), (-150, -16), (-60, 0), (100, 0), (176, -18), (222, -60), (238, -100),
            (214, -80), (170, -58), (100, -52), (-80, -52), (-170, -58), (-210, -80)], col, 6)
    for yy in (-36, -18):
        g.line([(-190, yy - 10), (-60, yy + 10), (100, yy + 10), (200, yy - 16)], 2.4, d)
    tube(g, [(230, -90), (248, -140), (250, -190), (236, -214)], 14, col)
    g.poly([(226, -228), (262, -238), (280, -220), (258, -206), (232, -204)], col, 4)
    g.circ(254, -224, 3, INK, 0)
    g.poly([(238, -232), (230, -252), (246, -238)], col, 3)
    tube(g, [(-230, -104), (-250, -150), (-236, -182), (-214, -170), (-224, -150)], 12, col)
    cols = [(206, 56, 52), (240, 196, 70), (70, 110, 190)]
    for i in range(9):
        sx = -150 + i * 36
        g.circ(sx, -56, 17, cols[i % 3], 4)
        g.circ(sx, -56, 5, IRON, 2)


def dock(p, x, y, s, c, k):
    col = _c(c, WOOD)
    d = darker(col, 0.7)
    g = Sk(p, x, y, s, wob=0.4)
    for i in range(6):
        px = -210 + i * 84
        g.rect(px - 10, -120, px + 10, 0, d, 4)
    waterline(g, -250, 250, -20, (110, 170, 210), 4)
    g.rect(-240, -134, 240, -108, col, 5)
    for i in range(1, 12):
        g.line([(-240 + i * 40, -132), (-240 + i * 40, -110)], 2.4, d)
    g.rect(170, -164, 196, -134, IRON_D, 4)
    g.rect(164, -170, 202, -160, IRON_D, 3)
    tube(g, [(183, -150), (150, -146), (120, -150), (100, -140)], 5, (200, 170, 120))


def bottle(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=-30, wob=0.3)
    glass = _c(c, (186, 226, 206))
    g.rect(-34, -50, 34, 80, glass, 5, r=20)
    g.rect(-13, -92, 13, -48, glass, 5)
    g.rect(-14, -108, 14, -90, (176, 128, 84), 4)
    g.rect(-18, -30, 18, 56, CREAM, 3)
    for yy in (-14, 6, 26, 42):
        g.line([(-10, yy), (10, yy)], 2.4, (160, 150, 130))
    g.line([(22, -40), (22, 50)], 4, WHITE)


def seaweed(p, x, y, s, c, k):
    col = _c(c, (76, 160, 110))
    g = Sk(p, x, y, s, wob=0.4)
    sway = 2 * math.pi * _num(k, "t", 0) / 3.0
    for sx, h, ph in ((-36, 200, 0), (0, 250, 1.5), (34, 180, 3)):
        left, right = [], []
        for j in range(10):
            t = j / 9
            cx = sx + 18 * math.sin(t * 6 + ph) + 14 * t * math.sin(sway + ph)
            w = 14 * (1 - t) + 3
            left.append((cx - w, -h * t))
            right.append((cx + w, -h * t))
        g.poly(left + right[::-1], col, 4)


def coral(p, x, y, s, c, k):
    col = _c(c, (246, 120, 120))
    g = Sk(p, x, y, s, wob=0.4)
    branches = [[(0, 0), (0, -80), (-40, -130), (-50, -180)], [(0, -80), (40, -140), (36, -190)],
                [(-40, -130), (-80, -150)], [(40, -140), (84, -160), (96, -200)], [(0, -60), (-70, -80), (-96, -120)],
                [(0, -100), (10, -170)]]
    for b in branches:
        tube(g, b, 20, col)
    for b in branches:
        g.line(b, 20, col)
    for b in branches:
        bx, by = b[-1]
        g.circ(bx, by, 12, col, 0)


def ocean_liner(p, x, y, s, c, k):
    funnel = _c(c, (232, 170, 80))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.line([(-250, -90), (-250, -250)], 4)
    g.line([(230, -96), (230, -250)], 4)
    g.line([(-250, -250), (230, -250)], 2, (120, 120, 130))
    for fx in (-120, -46, 28, 102):
        g.poly([(fx - 22, -160), (fx + 22, -160), (fx + 30, -262), (fx - 12, -262)], funnel, 5)
        g.poly([(fx - 9, -240), (fx + 28, -240), (fx + 30, -262), (fx - 12, -262)], (40, 40, 48), 0)
    if k.get("smoke"):
        for i, (dx, dy, r) in enumerate(((0, -290, 22), (-20, -320, 28), (-50, -346, 32))):
            g.circ(-112 + dx, dy, r, (150, 150, 160), 4)
    g.rect(-196, -130, 176, -86, WHITE, 5)
    g.rect(-150, -162, 136, -130, WHITE, 5)
    for i in range(24):
        g.circ(-182 + i * 15, -110, 3.5, DARKWIN, 0)
    g.poly([(-292, -86), (292, -92), (270, -10), (242, 0), (-262, 0), (-288, -32)], (40, 40, 48), 6)
    g.poly([(-276, -22), (274, -22), (244, 0), (-262, 0)], (170, 42, 40), 0)
    g.poly([(-292, -86), (292, -92), (270, -10), (242, 0), (-262, 0), (-288, -32)], None, 6)
    for i in range(28):
        g.circ(-240 + i * 17, -54, 3.5, (230, 220, 180), 0)
    if k.get("label"):
        g.text(str(k["label"])[:10].upper(), 200, -66, 18, WHITE)


def warship(p, x, y, s, c, k):
    col = _c(c, (150, 158, 172))
    d = darker(col, 0.75)
    flag = C(k["flag"]) if k.get("flag") else None
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.poly([(-8, -152), (8, -152), (4, -236), (-4, -236)], d, 3)
    g.line([(-40, -200), (40, -200)], 3, d)
    if flag:
        g.poly([(4, -236), (52, -226), (4, -212)], flag, 3)
    g.rect(-70, -152, 60, -76, lighter(col, 0.3), 5)
    g.rect(-40, -186, 30, -152, lighter(col, 0.3), 5)
    g.windows(-36, -180, 26, -160, 4, 1, DARKWIN, 0.4, 2)
    g.rect(74, -146, 112, -76, d, 5)
    g.rect(74, -154, 112, -144, (40, 40, 48), 3)
    for tx, dirn in ((150, 1), (214, 1), (-160, -1)):
        g.line([(tx, -92), (tx + 70 * dirn, -104)], 6, IRON_D)
        g.line([(tx, -84), (tx + 70 * dirn, -94)], 6, IRON_D)
        g.poly([(tx - 30, -76), (tx - 24, -102), (tx + 24, -102), (tx + 32, -76)], col, 4)
    g.poly([(-264, -76), (272, -84), (232, -10), (202, 0), (-232, 0), (-258, -30)], col, 6)
    g.poly([(-250, -18), (246, -18), (202, 0), (-232, 0)], d, 0)
    g.poly([(-264, -76), (272, -84), (232, -10), (202, 0), (-232, 0), (-258, -30)], None, 6)
    for i in range(18):
        g.circ(-200 + i * 22, -50, 3, DARKWIN, 0)


# ------------------------------------------------------------------ land & sky
def pine_tree(p, x, y, s, c, k):
    col = _c(c, (62, 128, 82))
    g = Sk(p, x, y, s, wob=0.4)
    g.rect(-14, -62, 14, 0, (130, 90, 60), 4)
    for i, (yb, hw, h) in enumerate(((-50, 104, 130), (-130, 86, 120), (-206, 66, 110), (-276, 44, 96))):
        pts = [(-hw, yb)]
        for j in range(1, 6):
            pts.append((-hw + 2 * hw * j / 6, yb + (8 if j % 2 else 0)))
        pts += [(hw, yb), (0, yb - h)]
        g.poly(pts, col if i % 2 == 0 else darker(col, 0.9), 5)
    if k.get("snow"):
        for yb, hw, h in ((-130, 86, 120), (-206, 66, 110), (-276, 44, 96)):
            g.poly([(-hw * 0.35, yb - h * 0.62), (0, yb - h), (hw * 0.35, yb - h * 0.62), (0, yb - h * 0.55)], WHITE, 0)


def volcano(p, x, y, s, c, k):
    col = _c(c, (130, 104, 94))
    g = Sk(p, x, y, s, wob=0.5)
    erupt = k.get("erupting", True) is not False
    ph = 2 * math.pi * _num(k, "t", 0) / 2.0
    if erupt:
        for i, (cx, cy, r) in enumerate(((-30, -400, 50), (40, -430, 60), (0, -480, 64), (-70, -460, 44),
                                         (80, -500, 46))):
            g.circ(cx + 6 * math.sin(ph + i), cy - 8 * math.sin(ph + i * 1.3), r * (1 + 0.06 * math.sin(ph + i)),
                   (130, 130, 140), 5)
        for i, (cx, cy, r) in enumerate(((-20, -330, 20), (24, -350, 16), (0, -372, 22), (-40, -360, 12),
                                         (50, -330, 12))):
            g.circ(cx, cy - 14 * (0.5 + 0.5 * math.sin(ph * 2 + i)), r, (246, 120, 40), 4)
    g.poly([(-250, 0), (-96, -284), (-52, -304), (52, -304), (96, -284), (250, 0)], col, 6)
    g.poly([(30, -300), (96, -284), (250, 0), (120, 0), (70, -150)], darker(col, 0.85), 0)
    g.poly([(-250, 0), (-96, -284), (-52, -304), (52, -304), (96, -284), (250, 0)], None, 6)
    if erupt:
        g.poly([(-52, -304), (52, -304), (40, -290), (-40, -290)], (246, 120, 40), 4)
        for pts in ([(-30, -296), (-60, -220), (-50, -150), (-90, -60)], [(24, -296), (50, -230), (40, -160), (90, -90)],
                    [(0, -296), (8, -240), (-6, -200)]):
            tube(g, pts, 14, (246, 120, 40))
            g.line(pts, 5, (252, 210, 80))


def cactus(p, x, y, s, c, k):
    col = _c(c, (96, 168, 96))
    d = darker(col, 0.75)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-92, -190, -50, -100, col, 5, r=20)
    g.rect(-92, -126, -10, -94, col, 5, r=16)
    g.rect(50, -230, 92, -140, col, 5, r=20)
    g.rect(10, -166, 92, -134, col, 5, r=16)
    g.rect(-28, -270, 28, 0, col, 6, r=28)
    for xx in (-12, 0, 12):
        g.line([(xx, -250), (xx, -10)], 2.4, d)
    for xx, yy in ((-28, -200), (28, -100), (-28, -60), (28, -220), (-71, -170), (71, -200)):
        g.line([(xx, yy), (xx + (6 if xx > 0 else -6), yy - 4)], 2, INK)
    if k.get("flower", True) is not False:
        g.circ(0, -272, 10, (246, 110, 150), 3)


def flowers(p, x, y, s, c, k):
    col = _c(c, (226, 60, 70))
    g = Sk(p, x, y, s, wob=0.35)
    for sx, h, cc in ((-44, 130, col), (0, 160, lighter(col, 0.0)), (44, 120, (250, 200, 60) if c is None else col)):
        g.line([(sx * 0.4, 0), (sx, -h)], 5, LEAF_D)
        g.poly([(sx * 0.6, -40), (sx * 0.6 - 26, -80), (sx * 0.6 - 6, -60)], LEAF, 3)
        g.poly([(sx - 18, -h), (sx - 22, -h - 34), (sx - 9, -h - 24), (sx, -h - 40), (sx + 9, -h - 24),
                (sx + 22, -h - 34), (sx + 18, -h)], cc, 4)


def rocks(p, x, y, s, c, k):
    col = _c(c, (156, 156, 164))
    g = Sk(p, x, y, s, wob=0.8)
    for cx, rx, ry, cc in ((-80, 70, 56, darker(col, 0.9)), (70, 80, 64, col), (-6, 96, 82, lighter(col, 0.1))):
        pts = [(cx - rx, 0)] + arc_pts(cx, 0, rx, ry * 1.6, 200, 340, 8) + [(cx + rx, 0)]
        g.poly(pts, cc, 5)
    g.line([(-30, -90), (-10, -60), (-20, -30)], 2.6, darker(col, 0.7))
    g.line([(80, -60), (92, -40)], 2.6, darker(col, 0.7))


def bush(p, x, y, s, c, k):
    col = _c(c, (96, 164, 86))
    g = Sk(p, x, y, s, wob=0.5)
    for cx, cy, r in ((-70, -50, 54), (70, -50, 54), (-20, -86, 66), (34, -90, 60), (0, -46, 62)):
        g.circ(cx, cy, r, col, 5)
    for cx, cy, r in ((-70, -50, 54), (70, -50, 54), (-20, -86, 66), (34, -90, 60), (0, -46, 62)):
        g.circ(cx, cy, r - 5, col, 0)
    g.line([(-120, 0), (120, 0)], 5, darker(col, 0.6))
    if k.get("berries"):
        for cx, cy in ((-40, -90), (20, -110), (60, -60), (-80, -40)):
            g.circ(cx, cy, 7, (220, 50, 60), 2.4)


def sun(p, x, y, s, c, k):
    col = _c(c, (252, 204, 60))
    g = Sk(p, x, y, s, wob=0.3)
    turn = 30 * _num(k, "t", 0) / 4.0                  # the rays turn slowly (one ray every 4 s)
    for i in range(12):
        a = math.radians(i * 30 + turn)
        b = math.radians(i * 30 + 8 + turn)
        b2 = math.radians(i * 30 - 8 + turn)
        g.poly([(math.cos(b2) * 92, math.sin(b2) * 92), (math.cos(a) * 140, math.sin(a) * 140),
                (math.cos(b) * 92, math.sin(b) * 92)], (252, 160, 50), 4)
    g.circ(0, 0, 86, col, 6)
    g.circ(-26, -26, 22, lighter(col, 0.5), 0)


def moon(p, x, y, s, c, k):
    col = _c(c, (250, 236, 170))
    g = Sk(p, x, y, s, wob=0.3)
    outer = arc_pts(0, 0, 80, 80, 60, 300, 20)
    inner = arc_pts(34, -6, 66, 70, 290, 70, 20)
    g.poly(outer + inner, col, 6)
    for cx, cy, r in ((-46, 10, 9), (-30, 44, 6), (-40, -30, 6)):
        g.circ(cx, cy, r, darker(col, 0.88), 2.4)


def star(p, x, y, s, c, k):
    col = _c(c, (250, 206, 60))
    g = Sk(p, x, y, s, wob=0.3)
    g.poly(star_pts(0, 0, 76, 0.45), col, 6)
    g.poly(star_pts(-6, -6, 30, 0.45), lighter(col, 0.45), 0)


def lightning(p, x, y, s, c, k):
    col = _c(c, (252, 214, 60))
    g = Sk(p, x, y, s, wob=0.3)
    g.poly([(10, -130), (-50, 10), (-6, 10), (-30, 130), (56, -24), (10, -24), (40, -130)], col, 6)


def rain_cloud(p, x, y, s, c, k):
    col = _c(c, (150, 156, 172))
    g = Sk(p, x, y, s, wob=0.4)
    fall = (_num(k, "t", 0) / 0.5) % 1.0
    for i in range(7):
        rx = -80 + i * 27
        off = ((fall + (i % 3) / 3) % 1.0) * 40
        g.line([(rx, 30 + off), (rx - 10, 76 + off)], 5, (110, 160, 220))
    for cx, cy, r in ((-60, 0, 46), (0, -26, 62), (60, 0, 48), (24, 20, 44), (-26, 22, 44)):
        g.circ(cx, cy, r, col, 5)
    for cx, cy, r in ((-60, 0, 46), (0, -26, 62), (60, 0, 48), (24, 20, 44), (-26, 22, 44)):
        g.circ(cx, cy, r - 5, col, 0)


def wheat(p, x, y, s, c, k):
    col = _c(c, (226, 180, 80))
    g = Sk(p, x, y, s, wob=0.3)
    for a in (-24, -12, 0, 12, 24):
        tx, ty = math.sin(math.radians(a)) * 220, -math.cos(math.radians(a)) * 220
        g.line([(a * 0.6, 0), (tx, ty)], 4, darker(col, 0.8))
        for j in range(5):
            t = 0.72 + j * 0.06
            gx, gy = tx * t + a * 0.6 * (1 - t), ty * t
            g.ell(gx - 7, gy, 7, 11, col, 2.4)
            g.ell(gx + 7, gy, 7, 11, col, 2.4)
    g.rect(-24, -100, 24, -84, (180, 90, 60), 3)


def planet(p, x, y, s, c, k):
    col = _c(c, (232, 192, 124))
    ring = (206, 176, 130)
    g = Sk(p, x, y, s, rot=-18, wob=0.3)
    g.arc(0, 0, 156, 40, 180, 360, 14, INK)
    g.arc(0, 0, 156, 40, 180, 360, 8, ring)
    g.circ(0, 0, 84, col, 6)
    for yy in (-40, 0, 36):
        g.line(arc_pts(0, yy, math.sqrt(max(0, 84 ** 2 - yy ** 2)) - 6, 8, 180, 0, 10), 4, darker(col, 0.85))
    g.arc(0, 0, 156, 40, 0, 180, 14, INK)
    g.arc(0, 0, 156, 40, 0, 180, 8, ring)


def bamboo(p, x, y, s, c, k):
    col = _c(c, (120, 180, 90))
    g = Sk(p, x, y, s, wob=0.3)
    for sx, h in ((-40, 280), (0, 330), (40, 250)):
        g.rect(sx - 11, -h, sx + 11, 0, col, 4)
        for j in range(1, int(h / 60) + 1):
            g.line([(sx - 13, -j * 60), (sx + 13, -j * 60)], 4, darker(col, 0.65))
        lx, ly = sx + 11, -h + 40
        g.poly([(lx, ly), (lx + 50, ly - 20), (lx + 60, ly - 8)], LEAF, 3)
        g.poly([(sx - 11, ly + 60), (sx - 64, ly + 50), (sx - 60, ly + 62)], LEAF, 3)


SEA_NATURE = {
    "fish": ("center", fish, "fish. color, params: flip (face left)"),
    "shark": ("center", shark, "shark (danger at sea). params: flip"),
    "whale": ("center", whale, "whale with spout. params: spout (bool), flip"),
    "octopus": ("center", octopus, "octopus. color"),
    "crab": ("bottom", crab, "crab. color"),
    "jellyfish": ("center", jellyfish, "jellyfish. color"),
    "anchor": ("center", anchor, "ship's anchor (navy, sailors, ports). params: rope (bool)"),
    "wave": ("bottom", wave, "huge curling ocean wave (storm, tsunami, sea power). params: flip"),
    "iceberg": ("bottom", iceberg, "iceberg in the water (Titanic, Arctic)"),
    "submarine": ("center", submarine, "submarine (U-boat, navy). color, params: label (e.g. U-47), flip"),
    "periscope": ("bottom", periscope, "submarine periscope sticking out of the water"),
    "buoy": ("bottom", buoy, "floating buoy with a light. color"),
    "lifebuoy": ("center", lifebuoy, "life ring (rescue, shipwreck)"),
    "treasure_chest": ("bottom", treasure_chest, "treasure chest full of gold (pirates, riches). params: open (bool)"),
    "palm_tree": ("bottom", palm_tree, "palm tree (tropics, beach, islands). params: flip"),
    "seagull": ("center", seagull, "flying seagull (coast, harbor)"),
    "rowboat": ("bottom", rowboat, "small rowboat with oars (landing, escape, fishing)"),
    "galleon": ("bottom", galleon, "big 3-mast sailing warship (Age of Sail, explorers, Spanish treasure fleet). "
                                   "color = hull. params: flag (color), pirate (bool: black sails, skull), flip"),
    "viking_ship": ("bottom", viking_ship, "Viking longship with dragon head, shields and striped sail. params: flip"),
    "ocean_liner": ("bottom", ocean_liner, "ocean liner with four funnels (Titanic, emigration). color = funnels. "
                                           "params: smoke (bool), label, flip"),
    "dock": ("bottom", dock, "wooden pier / dock (harbor, port)"),
    "bottle": ("center", bottle, "message in a bottle"),
    "seaweed": ("bottom", seaweed, "seaweed / kelp (underwater)"),
    "coral": ("bottom", coral, "coral (underwater, reef). color"),
    "pine_tree": ("bottom", pine_tree, "pine / fir tree (forests, Russia, Scandinavia, winter). params: snow (bool)"),
    "volcano": ("bottom", volcano, "volcano (Pompeii, eruptions). params: erupting (bool)"),
    "cactus": ("bottom", cactus, "saguaro cactus (desert, Mexico, Wild West)"),
    "flowers": ("bottom", flowers, "three tulips (spring, Netherlands, peace, gardens). color"),
    "rocks": ("bottom", rocks, "pile of boulders"),
    "bush": ("bottom", bush, "round bush (hiding spot). params: berries (bool)"),
    "sun": ("center", sun, "bright sun"),
    "moon": ("center", moon, "crescent moon (night, Space Race, Islam)"),
    "star": ("center", star, "five-point star. color"),
    "lightning": ("center", lightning, "lightning bolt (power, shock, storm)"),
    "rain_cloud": ("center", rain_cloud, "gray rain cloud (bad luck, storms, sadness)"),
    "wheat": ("bottom", wheat, "wheat sheaf (farming, harvest, bread, famine)"),
    "planet": ("center", planet, "ringed planet like Saturn (space, science)"),
    "bamboo": ("bottom", bamboo, "bamboo stalks (China, Japan, Vietnam, jungle)"),
}

UPGRADES = {
    "periscope": SEA_NATURE["periscope"],
    "ship": ("bottom", warship, "steel warship with gun turrets (navy, battleship, destroyer). params: flag (color), flip"),
}
