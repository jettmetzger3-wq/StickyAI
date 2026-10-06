"""History, military, vehicles and everyday objects, plus detailed versions of the first, simpler props."""
import math

from .palette import color as C, INK, RED, WHITE, darker, lighter
from .props_kit import (Sk, arc_pts, ellipse, rounded, star_pts, arch, WOOD, WOOD_D, WOOD_L, IRON, IRON_D, STEEL,
                        GOLD, GOLD_D, GLASS, CREAM, LEAF, LEAF_D, DARKWIN, FLAME, FLAME_Y, SNOW, STONE)


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
    g.line(pts, w + 6, INK)
    g.line(pts, w, col)


PAPER = (255, 250, 236)
PARCH = (240, 222, 178)
OLIVE = (112, 120, 76)


# ------------------------------------------------------------------ war & history
def catapult(p, x, y, s, c, k):
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    g.line([(-30, -60), (0, -186)], 10, WOOD_D)
    g.line([(30, -60), (0, -186)], 10, WOOD_D)
    g.line([(-22, -150), (22, -150)], 8, WOOD_D)
    tube(g, [(30, -72), (-140, -236)], 12, WOOD)
    g.poly(arc_pts(-150, -236, 34, 24, 0, 180, 10), WOOD_D, 4)
    g.circ(-150, -250, 22, (150, 150, 160), 4)
    g.rect(-160, -64, 160, -38, WOOD, 5)
    g.circ(30, -72, 12, (196, 160, 104), 4)
    for wx in (-112, 112):
        g.wheel(wx, -34, 34, WOOD, 6)


def chariot(p, x, y, s, c, k):
    col = _c(c, (196, 60, 52))
    f = _flip(k)
    g = Sk(p, x, y, s, flip=f, wob=0.4)
    from .props_life import horse
    hx, hy = g.pt(130, 0)
    horse(p, hx, hy, s * 0.66, None, {"saddle": False, "flip": f})
    g.line([(-90, -96), (90, -150)], 7, WOOD_D)
    g.poly([(-190, -170), (-80, -170), (-70, -64), (-170, -64)], col, 6)
    g.line([(-186, -150), (-82, -150)], 5, GOLD)
    g.poly([(-150, -130), (-110, -130), (-110, -96), (-150, -96)], GOLD, 3)
    g.wheel(-130, -56, 56, WOOD, 8)


def guillotine(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-120, -24, 120, 0, WOOD_D, 5)
    for xx in (-76, 60):
        g.rect(xx, -450, xx + 16, -24, WOOD, 5)
    g.rect(-98, -472, 98, -446, WOOD, 5)
    g.line([(0, -446), (0, -396)], 3, (196, 170, 120))
    g.poly([(-60, -396), (60, -396), (60, -340), (-60, -320)], STEEL, 5)
    g.line([(-56, -326), (56, -346)], 3, WHITE)
    g.rect(-60, -150, 60, -110, WOOD, 5)
    g.circ(0, -130, 16, (60, 50, 44), 3)
    g.rect(-118, -110, -60, -94, WOOD_D, 4)


def barricade(p, x, y, s, c, k):
    flag = _c(c, RED)
    g = Sk(p, x, y, s, wob=0.6)
    g.line([(30, -150), (40, -330)], 6, WOOD_D)
    g.poly([(40, -330), (130, -316), (124, -270), (38, -282)], flag, 4)
    g.rect(-200, -90, -80, 0, (196, 150, 98), 5)
    g.line([(-200, -90), (-80, 0)], 3, WOOD_D)
    g.rect(80, -120, 190, 0, (186, 138, 90), 5)
    g.line([(80, -60), (190, -60)], 3, WOOD_D)
    g.poly([(-150, -100), (120, -200), (130, -180), (-140, -80)], WOOD_L, 4)
    g.poly([(-60, -60), (60, -150), (70, -130), (-50, -40)], WOOD, 4)
    g.wheel(-60, -110, 62, WOOD, 8)
    g.rect(-10, -80, 60, 0, (120, 84, 56), 5, r=14)
    for yy in (-60, -20):
        g.line([(-10, yy), (60, yy)], 3, IRON_D)
    g.line([(120, -120), (160, -190), (200, -120)], 6, WOOD_D)


def sandbags(p, x, y, s, c, k):
    col = _c(c, (196, 178, 128))
    g = Sk(p, x, y, s, wob=0.6)
    rows = ((0, 5, -190), (-40, 4, -150), (-80, 3, -110))
    for yb, n, x0 in rows:
        for i in range(n):
            bx = x0 + i * 80
            g.rect(bx - 2, yb - 44, bx + 78, yb, col, 5, r=18)
            g.line([(bx + 10, yb - 22), (bx + 20, yb - 24)], 2.4, darker(col, 0.7))


def wagon(p, x, y, s, c, k):
    cover = _c(c, (246, 238, 214))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    g.line([(150, -60), (250, -40)], 6, WOOD_D)
    g.rect(-160, -110, 150, -56, WOOD, 6)
    g.line([(-160, -84), (150, -84)], 3, WOOD_D)
    g.poly([(-170, -110), (-150, -220), (-60, -246), (40, -246), (130, -222), (160, -110)], cover, 6)
    for xx in (-90, -10, 70):
        g.arc(xx, -110, 50, 136, 210, 330, 3, darker(cover, 0.82))
    g.wheel(-110, -50, 50, WOOD, 10)
    g.wheel(110, -40, 40, WOOD, 8)


def musket(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", -10), flip=_flip(k), wob=0.3)
    g.poly([(-190, 6), (-190, 34), (-120, 18), (-60, 10), (-60, -4), (-120, 0)], WOOD, 5)
    g.rect(-60, -6, 180, 8, IRON_D, 4)
    g.rect(-100, -12, -64, 6, IRON, 3)
    g.line([(-88, -12), (-96, -26)], 4, IRON_D)
    g.line([(-90, 10), (-80, 26), (-70, 12)], 3, IRON_D)
    if k.get("bayonet", True) is not False:
        g.poly([(176, 10), (250, 2), (176, -4)], STEEL, 3)


def shield(p, x, y, s, c, k):
    col = _c(c, (52, 86, 170))
    c2 = _c(k.get("color2"), GOLD)
    g = Sk(p, x, y, s, wob=0.35)
    pts = [(-84, -96), (84, -96), (84, 4), (46, 70), (0, 104), (-46, 70), (-84, 4)]
    g.poly(pts, col, 7)
    g.poly([(-14, -92), (14, -92), (14, 96), (-14, 96)], c2, 0)
    g.poly([(-80, -36), (80, -36), (80, -8), (-80, -8)], c2, 0)
    g.poly(pts, None, 7)
    g.poly([(-70, -84), (70, -84), (70, 0), (38, 58), (0, 88), (-38, 58), (-70, 0)], None, 2.4, darker(col, 0.6))


def spear(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", 0), wob=0.3)
    g.line([(0, 160), (0, -130)], 9, WOOD)
    g.poly([(0, -200), (16, -150), (0, -126), (-16, -150)], STEEL, 4)
    g.rect(-7, -130, 7, -118, IRON_D, 3)


def axe(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", 20), flip=_flip(k), wob=0.3)
    g.line([(0, 120), (0, -110)], 11, WOOD)
    g.poly([(6, -110), (60, -140), (80, -90), (64, -40), (6, -70)], STEEL, 5)
    g.line([(62, -134), (76, -88), (62, -46)], 3, WHITE)


def drum(p, x, y, s, c, k):
    col = _c(c, (52, 86, 170))
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-80, -130, 80, -20, col, 6)
    pts = []
    for i in range(9):
        pts.append((-80 + i * 20, -112 if i % 2 == 0 else -38))
    g.line(pts, 3.5, WHITE)
    g.ell(0, -20, 80, 16, RED, 5)
    g.ell(0, -132, 80, 16, (246, 240, 226), 5)
    g.rect(-82, -142, 82, -124, RED, 4)
    g.line([(-60, -150), (50, -210)], 6, WOOD_L)
    g.line([(60, -150), (-50, -210)], 6, WOOD_L)


def medal(p, x, y, s, c, k):
    col = _c(c, GOLD)
    g = Sk(p, x, y, s, wob=0.3)
    stripes = [(214, 60, 55), WHITE, (52, 86, 170), WHITE, (214, 60, 55)]
    for i, sc in enumerate(stripes):
        x0 = -40 + i * 16
        g.poly([(x0, -110), (x0 + 16, -110), (x0 + 16 + (8 - i * 4), 0), (x0 + (8 - i * 4), 0)], sc, 0)
    g.poly([(-40, -110), (40, -110), (24, 0), (-24, 0)], None, 4)
    g.circ(0, 46, 50, col, 6)
    g.circ(0, 46, 38, None, 3, darker(col, 0.75))
    g.poly(star_pts(0, 46, 26), lighter(col, 0.4), 3, darker(col, 0.75))


def zeppelin(p, x, y, s, c, k):
    col = _c(c, (196, 200, 210))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    for f in (1, -1):
        g.poly([(-190, -20 * f), (-250, -66 * f), (-260, -20 * f)], d, 4)
    g.poly(ellipse(0, 0, 260, 68, 32), col, 6)
    for xx in (-180, -120, -60, 0, 60, 120, 180):
        hh = 68 * math.sqrt(max(0, 1 - (xx / 260) ** 2))
        g.line([(xx, -hh + 4), (xx + 4, hh - 4)], 2.4, d)
    g.rect(-30, 60, 60, 90, d, 4, r=8)
    for i in range(4):
        g.rect(-20 + i * 20, 68, -10 + i * 20, 80, GLASS, 0)
    if k.get("label"):
        g.text(str(k["label"])[:10].upper(), 20, 0, 40, (60, 60, 70))


def biplane(p, x, y, s, c, k):
    col = _c(c, (206, 52, 48))
    g = Sk(p, x, y, s, rot=_num(k, "angle", 0), flip=_flip(k), wob=0.3)
    g.rect(-40, -66, 100, -52, col, 4, r=6)
    for xx in (-20, 80):
        g.line([(xx, -52), (xx, 0)], 3)
    g.poly([(-150, -20), (-170, -64), (-140, -60), (-120, -16)], col, 4)
    g.poly([(-150, 4), (130, -14), (150, 0), (130, 16), (-140, 14)], col, 5)
    g.circ(50, -24, 16, (60, 60, 70), 3)
    g.rect(-40, 6, 100, 20, darker(col, 0.8), 4, r=6)
    blade = (50, 28, 8)[int(round(_num(k, "t", 0) * 12)) % 3]       # a spinning propeller
    g.line([(152, -blade), (152, blade)], 6, (120, 90, 60))
    g.ell(152, 0, 4, 48, None, 1.5, (150, 150, 160))
    g.line([(30, 20), (20, 50)], 3)
    g.line([(70, 20), (80, 50)], 3)
    g.circ(20, 54, 9, (60, 60, 70), 3)
    g.circ(80, 54, 9, (60, 60, 70), 3)


def hot_air_balloon(p, x, y, s, c, k):
    col = _c(c, (226, 70, 60))
    alt = (250, 206, 70)
    g = Sk(p, x, y, s, wob=0.3)
    env = [(0, -230)] + [(math.sin(t) * 110 * (1 - 0.35 * max(0, (t - 1.6))), -110 - math.cos(t) * 120)
                         for t in [i * 0.2 for i in range(1, 16)]]
    left = [(-a, b) for a, b in env[::-1]]
    outline = left + env[1:]
    g.poly(outline, col, 0)
    for f in (-0.5, 0.5):
        g.poly([(a * f + (0 if f < 0 else 0), b) for a, b in env] + [(a * f * 0.2, b) for a, b in env[::-1]], alt, 0)
    g.poly(outline, None, 6)
    for f in (1, -1):
        g.line([(30 * f, 20), (20 * f, 60)], 3)
    g.rect(-28, 60, 28, 100, WOOD, 5)
    g.line([(-28, 74), (28, 74)], 2.4, WOOD_D)


def helicopter(p, x, y, s, c, k):
    col = _c(c, (104, 118, 84))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    rotor = (170, 100, 40)[int(round(_num(k, "t", 0) * 12)) % 3]      # a spinning rotor
    g.line([(-rotor, -76), (rotor, -76)], 6)
    g.line([(0, -76), (0, -54)], 6)
    g.rect(-200, -30, -20, -10, col, 4)
    g.poly([(-210, -60), (-190, -60), (-180, -24), (-206, -24)], col, 4)
    g.circ(-206, -40, 22, None, 3, (90, 90, 100))
    g.poly(ellipse(30, -16, 84, 46, 22), col, 6)
    g.poly(arc_pts(66, -16, 46, 40, 270, 360, 8) + [(66, -16)], GLASS, 4)
    for xx in (-20, 80):
        g.line([(xx, 28), (xx - 6, 46)], 4)
    g.line([(-60, 48), (120, 48)], 5)


def dynamite(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=-12, wob=0.3)
    for xx in (-34, 0, 34):
        g.rect(xx - 17, -60, xx + 17, 80, (214, 56, 52), 5, r=8)
    g.rect(-54, -10, 54, 14, (60, 60, 66), 4)
    g.line([(0, -60), (10, -96), (40, -110), (50, -136)], 4, (90, 80, 70))
    fl = 1 + 0.3 * math.sin(2 * math.pi * _num(k, "t", 0) / 0.3)
    g.poly(star_pts(54, -144, 20 * fl, 0.4, 6), (252, 210, 60), 3)


def barbed_wire(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.4)
    for px in (-200, 0, 200):
        g.line([(px - 30, 0), (px + 20, -110)], 6, WOOD_D)
        g.line([(px + 30, 0), (px - 20, -110)], 6, WOOD_D)
    for i in range(22):
        cx = -210 + i * 20
        g.ell(cx, -60, 18, 36, None, 2.6, (110, 110, 120))
    for i in range(14):
        cx = -200 + i * 30
        g.line([(cx - 5, -100 + (i % 3) * 30), (cx + 5, -90 + (i % 3) * 30)], 2.6, (80, 80, 90))


def satellite(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)
    if str(k.get("style", "")).lower() == "modern":
        for f in (1, -1):
            g.rect(50 * f, -24, 190 * f, 24, (60, 90, 170), 4)
            for i in range(1, 4):
                g.line([(50 * f + i * 35 * f, -24), (50 * f + i * 35 * f, 24)], 2, (140, 170, 230))
        g.rect(-50, -50, 50, 50, GOLD, 5)
        g.line([(0, -50), (0, -90)], 4)
        g.circ(0, -96, 10, STEEL, 3)
        return
    for a in (150, 165, 195, 210):
        ra = math.radians(a)
        g.line([(math.cos(ra) * 40, math.sin(ra) * 40), (math.cos(ra) * 220, math.sin(ra) * 120)], 3.5, IRON_D)
    g.circ(0, 0, 50, STEEL, 6)
    g.circ(-16, -16, 14, WHITE, 0)
    g.line([(-50, 0), (50, 0)], 2.4, darker(STEEL, 0.8))


# ------------------------------------------------------------------ everyday objects
def quill(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)
    g.poly([(10, -10), (60, -150), (90, -190), (100, -170), (70, -110), (24, -4)], (250, 248, 240), 4)
    for i in range(6):
        t = 0.25 + i * 0.12
        g.line([(10 + 60 * t, -10 - 150 * t), (40 + 60 * t, -16 - 150 * t)], 2, (200, 200, 210))
    g.line([(14, 10), (90, -186)], 3)
    g.rect(-50, -40, 40, 60, (60, 70, 100), 5, r=14)
    g.rect(-30, -60, 20, -36, (60, 70, 100), 4)
    g.line([(-36, -24), (-36, 44)], 4, lighter((60, 70, 100), 0.5))


def envelope(p, x, y, s, c, k):
    col = _c(c, (250, 244, 226))
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-110, -70, 110, 70, col, 6, r=6)
    g.line([(-108, -68), (0, 10), (108, -68)], 4)
    g.line([(-108, 68), (-30, -6)], 2.6, darker(col, 0.8))
    g.line([(108, 68), (30, -6)], 2.6, darker(col, 0.8))
    g.circ(0, 12, 20, (190, 40, 50), 4)
    g.poly(star_pts(0, 12, 9, 0.5), (230, 90, 100), 0)


def newspaper(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=-4, wob=0.3)
    g.rect(-130, -100, 130, 100, (246, 244, 236), 6)
    g.text(str(k.get("title", "THE DAILY NEWS"))[:18].upper(), 0, -80, 18, (60, 60, 70))
    g.line([(-120, -66), (120, -66)], 3)
    g.text(str(k.get("label", "EXTRA!"))[:12].upper(), 0, -38, 40, INK)
    g.rect(-118, -12, -10, 70, (200, 200, 208), 3)
    g.circ(-64, 24, 18, (160, 160, 170), 0)
    for i in range(6):
        g.line([(4, -6 + i * 14), (116 - (i % 2) * 20, -6 + i * 14)], 3, (150, 150, 160))
    g.line([(-118, 86), (116, 86)], 3, (150, 150, 160))


def gold_bars(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)

    def bar(cx, by):
        g.poly([(cx - 56, by), (cx + 56, by), (cx + 42, by - 40), (cx - 42, by - 40)], GOLD, 5)
        g.poly([(cx - 34, by - 34), (cx + 30, by - 34), (cx + 24, by - 26), (cx - 30, by - 26)], lighter(GOLD, 0.5), 0)

    for cx in (-118, 0, 118):
        bar(cx, 0)
    for cx in (-59, 59):
        bar(cx, -40)
    bar(0, -80)
    for cx, cy, r in ((-80, -100, 14), (70, -120, 10)):
        g.poly(star_pts(cx, cy, r, 0.3, 4), WHITE, 0)


def torch(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", 0), wob=0.3)
    g.poly([(-12, 110), (12, 110), (18, -40), (-18, -40)], WOOD, 5)
    g.rect(-24, -64, 24, -36, (150, 120, 90), 4)
    g.line([(-24, -50), (24, -50)], 2.4, (110, 86, 60))
    ph = 2 * math.pi * _num(k, "t", 0) / 0.5
    g.flame(2 * math.sin(ph * 2), -60, 70 * (1 + 0.05 * math.cos(ph)), 110 * (1 + 0.1 * math.sin(ph)))


def telescope(p, x, y, s, c, k):
    col = _c(c, (196, 150, 64))
    g = Sk(p, x, y, s, wob=0.35)
    for a, b in (((-80, 0), (0, -150)), ((80, 0), (0, -150)), ((10, 0), (0, -150))):
        g.line([a, b], 6, WOOD_D)
    tg = Sk(p, *g.pt(0, -160), s, rot=-24, wob=0.3)
    tg.rect(-110, -18, 40, 18, col, 5, r=6)
    tg.rect(40, -24, 130, 24, col, 5, r=6)
    tg.rect(-140, -12, -110, 12, darker(col, 0.8), 4)
    tg.ell(130, 0, 6, 24, GLASS, 3)
    for xx in (-60, 0, 80):
        tg.line([(xx, -20), (xx, 20)], 3, darker(col, 0.75))


def compass(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)
    g.circ(0, -96, 14, None, 6, GOLD_D)
    g.circ(0, 0, 84, GOLD, 6)
    g.circ(0, 0, 68, CREAM, 4)
    for i in range(8):
        a = math.radians(i * 45)
        g.line([(math.cos(a) * 54, math.sin(a) * 54), (math.cos(a) * 64, math.sin(a) * 64)], 3)
    g.poly([(0, -56), (12, 0), (0, 56), (-12, 0)], WHITE, 3)
    g.poly([(0, -56), (12, 0), (-12, 0)], RED, 3)
    g.circ(0, 0, 6, INK, 0)
    g.text("N", 0, -40, 18, INK)


def treasure_map(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=-3, wob=0.8)
    pts = [(-140, -96), (-80, -104), (-20, -94), (40, -104), (100, -96), (142, -100), (136, -40), (144, 20),
           (138, 96), (80, 102), (20, 94), (-40, 104), (-100, 96), (-142, 100), (-136, 40), (-144, -20)]
    g.poly(pts, PARCH, 6)
    g.poly(ellipse(-30, 10, 80, 56, 14), (196, 220, 150), 3)
    g.line([(-100, 60), (-80, 30), (-50, 34), (-30, 0), (0, -10), (30, 10)], 4, (200, 60, 50))
    for cx in (-70, -20):
        g.poly([(cx - 16, -10), (cx, -36), (cx + 16, -10)], (160, 140, 110), 3)
    g.line([(40, -10), (62, 14)], 7, RED)
    g.line([(62, -10), (40, 14)], 7, RED)
    g.poly(star_pts(100, -60, 22, 0.35, 4), None, 3)
    g.text("N", 100, -92, 16, INK)


def key(p, x, y, s, c, k):
    col = _c(c, GOLD)
    g = Sk(p, x, y, s, rot=_num(k, "angle", 0), wob=0.3)
    g.circ(-74, 0, 30, None, 16, INK)
    g.circ(-74, 0, 30, None, 10, col)
    g.rect(-46, -9, 90, 9, col, 4)
    g.rect(52, 6, 66, 34, col, 4)
    g.rect(74, 6, 90, 26, col, 4)


def telephone(p, x, y, s, c, k):
    col = _c(c, (40, 40, 48))
    g = Sk(p, x, y, s, wob=0.35)
    g.poly([(-90, 0), (90, 0), (66, -90), (-66, -90)], col, 6)
    g.circ(0, -46, 34, lighter(col, 0.85), 4)
    for i in range(10):
        a = math.radians(-60 + i * 30)
        g.circ(math.cos(a) * 24, -46 + math.sin(a) * 24, 4.5, col, 0)
    g.poly([(-100, -100), (-80, -130), (80, -130), (100, -100), (70, -96), (56, -112), (-56, -112), (-70, -96)],
           col, 5)
    g.line([(-90, -40), (-130, -20), (-110, 10)], 3, col)


def computer(p, x, y, s, c, k):
    col = _c(c, (226, 218, 196))
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-100, -240, 100, -70, col, 6, r=12)
    g.rect(-80, -222, 80, -104, (40, 60, 50), 4, r=6)
    for i, wdt in enumerate((100, 70, 120, 50)):
        g.line([(-66, -200 + i * 22), (-66 + wdt, -200 + i * 22)], 4, (120, 230, 140))
    g.rect(-40, -70, 40, -44, darker(col, 0.85), 4)
    g.poly([(-130, 0), (130, 0), (110, -40), (-110, -40)], col, 5)
    for j in range(2):
        for i in range(9):
            g.rect(-98 + i * 22, -34 + j * 14, -84 + i * 22, -24 + j * 14, darker(col, 0.8), 0)


def microphone(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)
    g.ell(0, -8, 70, 14, (60, 60, 70), 5)
    g.line([(0, -10), (0, -220)], 7, (90, 90, 100))
    g.rect(-30, -330, 30, -220, (190, 194, 204), 6, r=28)
    for yy in range(-312, -232, 14):
        g.line([(-24, yy), (24, yy)], 2.4, (120, 124, 136))
    g.rect(-34, -240, 34, -226, (90, 90, 100), 3)


def podium(p, x, y, s, c, k):
    col = _c(c, WOOD)
    g = Sk(p, x, y, s, wob=0.35)
    g.line([(30, -250), (40, -290), (20, -310)], 4, (90, 90, 100))
    g.rect(6, -326, 30, -300, (60, 60, 70), 3, r=8)
    g.poly([(-110, -240), (110, -240), (90, 0), (-90, 0)], col, 6)
    g.rect(-124, -260, 124, -236, darker(col, 0.8), 5)
    g.circ(0, -130, 42, GOLD, 5)
    if k.get("label"):
        g.text(str(k["label"])[:4].upper(), 0, -130, 34, (90, 60, 30))
    else:
        g.poly(star_pts(0, -130, 26), lighter(GOLD, 0.5), 3)


def megaphone(p, x, y, s, c, k):
    col = _c(c, (226, 70, 60))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.poly([(-80, -20), (60, -60), (60, 60), (-80, 20)], col, 6)
    g.ell(60, 0, 14, 60, WHITE, 5)
    g.rect(-100, -18, -78, 18, (60, 60, 70), 4)
    g.line([(-40, 18), (-46, 56)], 8, (60, 60, 70))


def camera(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-90, -50, 90, 60, (60, 60, 70), 6, r=10)
    g.rect(-60, -76, -10, -50, (60, 60, 70), 4)
    g.circ(10, 6, 40, (150, 150, 160), 5)
    g.circ(10, 6, 24, (40, 50, 80), 4)
    g.circ(2, -2, 7, WHITE, 0)
    g.rect(52, -40, 80, -24, (250, 240, 180), 3)


def pickaxe(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", -30), wob=0.3)
    g.line([(0, 120), (0, -100)], 10, WOOD)
    g.poly([(-110, -60), (-40, -112), (0, -118), (40, -112), (110, -60), (40, -96), (0, -100), (-40, -96)], STEEL, 5)


def hammer(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", -30), wob=0.3)
    g.line([(0, 120), (0, -90)], 12, WOOD)
    g.rect(-60, -130, 60, -84, IRON, 5, r=6)


def bell(p, x, y, s, c, k):
    col = _c(c, (196, 150, 70))
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-110, -150, 110, -128, WOOD_D, 5)
    g.poly([(-30, -130), (30, -130), (40, -110), (56, -40), (90, 30), (-90, 30), (-56, -40), (-40, -110)], col, 6)
    g.rect(-96, 26, 96, 44, darker(col, 0.8), 5, r=8)
    g.line([(-50, -50), (50, -50)], 3, darker(col, 0.75))
    if k.get("cracked"):
        g.line([(-20, 26), (-10, -10), (-24, -40), (-14, -70)], 4)
    g.circ(0, 52, 12, darker(col, 0.7), 3)


def briefcase(p, x, y, s, c, k):
    col = _c(c, (110, 74, 50))
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-40, -150, 40, -118, None, 9, INK)
    g.rect(-40, -150, 40, -118, None, 4, col)
    g.rect(-100, -124, 100, 0, col, 6, r=12)
    g.line([(-100, -84), (100, -84)], 3, darker(col, 0.7))
    for xx in (-60, 60):
        g.rect(xx - 10, -92, xx + 10, -76, GOLD, 3)


def atom(p, x, y, s, c, k):
    col = _c(c, (60, 120, 210))
    for a in (0, 60, 120):
        g2 = Sk(p, x, y, s, rot=a, wob=0.3)
        g2.poly(ellipse(0, 0, 120, 40, 30), None, 5, col)
        g2.circ(120 if a != 60 else -120, 0, 11, (250, 206, 60), 3)
    g = Sk(p, x, y, s)
    g.circ(0, 0, 24, (226, 70, 60), 5)


def flask(p, x, y, s, c, k):
    col = _c(c, (110, 210, 120))
    g = Sk(p, x, y, s, wob=0.3)
    for cx, cy, r in ((10, -220, 10), (-12, -250, 7), (16, -270, 5)):
        g.circ(cx, cy, r, lighter(col, 0.5), 2.4)
    g.poly([(-80, 0), (80, 0), (60, -50), (20, -110), (-20, -110), (-60, -50)], col, 0)
    g.poly([(-90, 0), (90, 0), (24, -130), (24, -190), (-24, -190), (-24, -130)], None, 6)
    g.rect(-30, -204, 30, -188, GLASS, 4)
    for cx, cy in ((-20, -40), (24, -64), (0, -20)):
        g.circ(cx, cy, 6, lighter(col, 0.6), 0)
    g.line([(-50, -20), (-16, -96)], 4, WHITE)


def gear(p, x, y, s, c, k):
    col = _c(c, (150, 156, 170))
    g = Sk(p, x, y, s, wob=0.3)
    pts = []
    for i in range(12):
        a0 = math.radians(i * 30 - 9)
        a1 = math.radians(i * 30 + 9)
        a2 = math.radians(i * 30 + 15)
        a3 = math.radians(i * 30 - 15)
        pts += [(math.cos(a3) * 80, math.sin(a3) * 80), (math.cos(a0) * 104, math.sin(a0) * 104),
                (math.cos(a1) * 104, math.sin(a1) * 104), (math.cos(a2) * 80, math.sin(a2) * 80)]
    g.poly(pts, col, 6)
    g.circ(0, 0, 34, lighter(col, 0.5), 5)
    g.circ(0, 0, 14, (60, 60, 70), 3)


def chess_piece(p, x, y, s, c, k):
    col = _c(c, (250, 246, 236))
    piece = str(k.get("piece", "king")).lower()
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-60, -30, 60, 0, col, 5, r=8)
    g.poly([(-46, -30), (46, -30), (24, -60), (-24, -60)], col, 5)
    if piece == "knight":
        g.poly([(-30, -60), (34, -60), (40, -130), (20, -190), (-20, -210), (-60, -170), (-56, -146), (-20, -150),
                (-34, -110)], col, 5)
        g.circ(-6, -176, 5, INK, 0)
    elif piece == "pawn":
        g.poly([(-22, -60), (22, -60), (14, -120), (-14, -120)], col, 5)
        g.circ(0, -140, 30, col, 5)
    else:
        g.poly([(-30, -60), (30, -60), (20, -170), (-20, -170)], col, 5)
        g.ell(0, -178, 34, 12, col, 5)
        g.poly(arc_pts(0, -186, 28, 30, 180, 360, 10), col, 5)
        g.rect(-5, -250, 5, -210, col, 3)
        g.rect(-16, -238, 16, -228, col, 3)


def amphora(p, x, y, s, c, k):
    col = _c(c, (206, 110, 60))
    g = Sk(p, x, y, s, wob=0.35)
    for f in (1, -1):
        g.arc(36 * f, -200, 24, 34, 90 if f < 0 else -90, 270 if f < 0 else 90, 12, INK)
        g.arc(36 * f, -200, 24, 34, 90 if f < 0 else -90, 270 if f < 0 else 90, 6, col)
    g.poly([(-20, 0), (20, 0), (40, -40), (66, -120), (56, -180), (24, -220), (28, -250), (-28, -250), (-24, -220),
            (-56, -180), (-66, -120), (-40, -40)], col, 6)
    g.poly([(-64, -150), (64, -150), (66, -110), (-66, -110)], (40, 36, 34), 0)
    pts = []
    for i in range(9):
        xx = -56 + i * 14
        pts += [(xx, -144), (xx, -118), (xx + 7, -118), (xx + 7, -134)]
    g.line(pts, 2.4, col)


def piggy_bank(p, x, y, s, c, k):
    from .props_life import pig
    pig(p, x, y, s, c, k)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.rect(-20, -158, 20, -148, (60, 40, 40), 0)
    g.circ(0, -184, 18, GOLD, 4)
    g.text("$", 0, -184, 20, GOLD_D)


def cash(p, x, y, s, c, k):
    col = _c(c, (120, 180, 110))
    g = Sk(p, x, y, s, wob=0.3)
    for i in range(5):
        yb = -i * 16
        g.rect(-110 + (i % 2) * 6, yb - 30, 110 + (i % 2) * 6, yb, col, 4)
    g.rect(-30, -104, 30, -76, WHITE, 3)
    g.text("$", -70, -90, 24, darker(col, 0.5))
    g.text("$", 70, -90, 24, darker(col, 0.5))
    g.rect(-20, -110, 20, -70, (230, 200, 120), 3)


def keg(p, x, y, s, c, k):
    col = _c(c, WOOD)
    g = Sk(p, x, y, s, wob=0.35)
    g.poly([(-56, 0), (-70, -50), (-74, -86), (-70, -122), (-56, -172), (56, -172), (70, -122), (74, -86), (70, -50),
            (56, 0)], col, 6)
    for xx in (-36, -12, 12, 36):
        g.line([(xx * 0.9, -6), (xx * 1.1, -86), (xx * 0.9, -166)], 2.4, darker(col, 0.7))
    for yy, hw in ((-30, 64), (-142, 64)):
        g.line([(-hw, yy), (hw, yy)], 7, IRON_D)
    if k.get("label"):
        g.text(str(k["label"])[:8].upper(), 0, -86, 26, (60, 40, 30), stroke=4, scol=(236, 214, 170))


# ------------------------------------------------------------------ detailed versions of the first props
def oil_barrel(p, x, y, s, c, k):
    col = _c(c, (52, 72, 110))
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-62, -170, 62, 0, col, 6, r=10)
    for yy in (-120, -56):
        g.line([(-62, yy), (62, yy)], 6, darker(col, 0.65))
    g.ell(0, -166, 58, 8, lighter(col, 0.3), 3)
    g.line([(-44, -150), (-44, -16)], 5, lighter(col, 0.35))
    if k.get("empty"):
        g.line([(-34, -110), (34, -30)], 9, RED)
        g.line([(34, -110), (-34, -30)], 9, RED)
    else:
        g.poly([(0, -112), (-16, -78), (-12, -66), (0, -60), (12, -66), (16, -78)], (30, 30, 36), 3, WHITE)


def bomb(p, x, y, s, c, k):
    col = _c(c, (90, 96, 86))
    g = Sk(p, x, y, s, rot=_num(k, "angle", 0), wob=0.3)
    g.poly([(-30, -70), (-46, -112), (46, -112), (30, -70)], darker(col, 0.8), 5)
    g.line([(0, -70), (0, -112)], 4)
    g.poly(ellipse(0, 0, 36, 76, 22), col, 6)
    g.rect(-34, -36, 34, -24, (240, 200, 60), 0)
    g.line([(-24, -50), (-24, 40)], 4, lighter(col, 0.4))


def helmet(p, x, y, s, c, k):
    col = _c(c, OLIVE)
    g = Sk(p, x, y, s, wob=0.35)
    g.poly(arc_pts(0, -16, 76, 86, 180, 360, 18), col, 6)
    g.rect(-92, -22, 92, -6, darker(col, 0.8), 5, r=6)
    g.arc(-10, -40, 50, 50, 210, 270, 6, lighter(col, 0.35))
    g.line([(-60, -8), (-40, 12), (40, 12), (60, -8)], 3, (110, 90, 60))


def sword(p, x, y, s, c, k):
    g = Sk(p, x, y, s, rot=_num(k, "angle", -30) + 0, wob=0.25)
    g.poly([(-12, -30), (12, -30), (10, -230), (0, -262), (-10, -230)], (226, 230, 238), 5)
    g.line([(0, -40), (0, -226)], 2.6, (170, 176, 190))
    g.rect(-50, -38, 50, -24, GOLD, 4, r=6)
    g.rect(-8, -24, 8, 36, (110, 70, 44), 4)
    for yy in (-12, 4, 20):
        g.line([(-8, yy), (8, yy + 6)], 2, (70, 44, 30))
    g.circ(0, 44, 12, GOLD, 4)


def cannon(p, x, y, s, c, k):
    col = _c(c, IRON_D)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    for cx, cy in ((-150, -14), (-122, -14), (-136, -38)):
        g.circ(cx, cy, 14, (60, 62, 72), 3)
    g.poly([(-100, 0), (-60, 0), (40, -60), (20, -84)], WOOD_D, 5)
    bg = Sk(p, *g.pt(10, -84), s, rot=(-12 if not _flip(k) else 12), flip=_flip(k), wob=0.3)
    bg.poly([(-60, -26), (150, -16), (150, 16), (-60, 26)], col, 6)
    bg.ell(-62, 0, 12, 26, col, 5)
    bg.rect(140, -22, 162, 22, col, 5, r=4)
    bg.line([(0, -24), (0, 24)], 3, lighter(col, 0.3))
    bg.line([(90, -18), (90, 18)], 3, lighter(col, 0.3))
    g.wheel(20, -50, 50, WOOD, 10)


def candle(p, x, y, s, c, k):
    col = _c(c, (252, 248, 236))
    g = Sk(p, x, y, s, wob=0.3)
    ph = 2 * math.pi * _num(k, "t", 0) / 0.7
    glow = 1 + 0.08 * math.sin(ph)
    g.circ(0, -190, 44 * glow, (255, 244, 200), 0)
    g.circ(0, -190, 28 * glow, (255, 232, 160), 0)
    g.ell(0, -8, 54, 12, GOLD, 5)
    g.rect(-24, -150, 24, -10, col, 5)
    g.poly([(-24, -150), (-24, -120), (-18, -126), (-16, -150)], darker(col, 0.92), 0)
    g.poly([(10, -150), (12, -110), (18, -116), (20, -150)], darker(col, 0.92), 0)
    g.line([(0, -150), (0, -160)], 3)
    g.flame(1.5 * math.sin(ph * 2), -158, 28, 52 * (1 + 0.1 * math.sin(ph)))


def coin(p, x, y, s, c, k):
    col = _c(c, (240, 196, 64))
    g = Sk(p, x, y, s, wob=0.3)
    g.circ(0, -62, 62, darker(col, 0.85), 6)
    g.circ(-4, -64, 54, col, 4)
    g.circ(-4, -64, 42, None, 3, darker(col, 0.75))
    label = str(k.get("label", ""))[:2]
    if label:
        g.text(label, -4, -64, 44, darker(col, 0.6))
    else:
        g.poly(star_pts(-4, -66, 26), lighter(col, 0.35), 3, darker(col, 0.7))
    g.arc(-4, -64, 46, 46, 200, 250, 5, lighter(col, 0.6))


def scroll(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-100, -80, 100, 90, PARCH, 5)
    for i in range(5):
        g.line([(-70, -44 + i * 24), (70 - (i % 2) * 30, -44 + i * 24)], 3.5, (150, 130, 100))
    for yy in (-86, 92):
        g.rect(-116, yy - 16, 116, yy + 16, darker(PARCH, 0.9), 5, r=16)
        g.circ(-116, yy, 12, (170, 120, 70), 4)
        g.circ(116, yy, 12, (170, 120, 70), 4)
    g.poly([(40, 66), (50, 112), (60, 90), (70, 112), (80, 66)], (190, 40, 50), 3)
    g.circ(60, 62, 18, (190, 40, 50), 4)


def document(p, x, y, s, c, k):
    n = int(_num(k, "lines", 5))
    g = Sk(p, x, y, s, wob=0.3)
    g.rect(-74, -98, 74, 98, (255, 255, 250), 5)
    g.poly([(40, -98), (74, -64), (40, -64)], (226, 226, 232), 4)
    g.line([(-52, -70), (20, -70)], 6, (90, 90, 110))
    for i in range(max(1, min(n, 7))):
        yy = -42 + i * 18
        g.line([(-52, yy), (52 - (i % 3) * 16, yy)], 3, (160, 160, 172))
    g.line([(-50, 72), (-30, 60), (-14, 76), (6, 62)], 3, (40, 60, 140))
    g.circ(40, 70, 14, (190, 40, 50), 3)


def crown(p, x, y, s, c, k):
    col = _c(c, (240, 200, 70))
    g = Sk(p, x, y, s, wob=0.3)
    g.poly([(-80, -40), (-70, -110), (70, -110), (80, -40)], (190, 40, 60), 0)
    pts = [(-90, 0), (-96, -110), (-50, -64), (-30, -130), (0, -76), (30, -130), (50, -64), (96, -110), (90, 0)]
    g.poly(pts, col, 6)
    g.rect(-92, -36, 92, 0, col, 5)
    for xx, gc in ((-56, (60, 110, 220)), (0, (220, 50, 70)), (56, (60, 180, 100))):
        g.poly([(xx, -30), (xx + 11, -18), (xx, -6), (xx - 11, -18)], gc, 3)
    for xx, yy in ((-96, -112), (-30, -132), (30, -132), (96, -112)):
        g.circ(xx, yy, 8, (250, 248, 240), 3)
    g.line([(-60, -50), (-40, -90)], 4, lighter(col, 0.5))


def campfire(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    tt = _num(k, "t", 0)
    ph = 2 * math.pi * tt / 0.75
    for i, cx in enumerate((-80, 70, -30, 40)):
        rise = ((tt / 0.75 + i / 4) % 1.0)
        g.circ(cx + 10 * math.sin(ph + i), -40 - rise * 160, 5 * (1 - rise * 0.6), FLAME_Y, 0)
    g.flame(4 * math.sin(ph * 2), -24, 150 * (1 + 0.04 * math.cos(ph)), 190 * (1 + 0.09 * math.sin(ph)))
    g.flame(-30, -24, 60, 90 * (1 + 0.15 * math.sin(ph * 2 + 1)))
    g.line([(-90, -10), (80, -30)], 18, INK)
    g.line([(-90, -10), (80, -30)], 12, WOOD)
    g.line([(-80, -30), (90, -6)], 18, INK)
    g.line([(-80, -30), (90, -6)], 12, WOOD_L)
    for i in range(7):
        a = math.pi * (0.95 + i * 0.18)
        g.ell(math.cos(a) * 100, -6, 18, 12, (150, 150, 160), 3)


def island(p, x, y, s, c, k):
    from .props_nature import palm_tree
    g = Sk(p, x, y, s, wob=0.4)
    g.poly(ellipse(0, -30, 230, 46, 26), (190, 226, 240), 0)
    g.poly(ellipse(0, -36, 170, 36, 22), (240, 214, 150), 6)
    g.poly(ellipse(-10, -46, 110, 22, 18), _c(c, (130, 190, 100)), 0)
    for (px, sc, fl) in ((-40, 0.62, False), (40, 0.48, True)):
        X, Y = g.pt(px, -42)
        palm_tree(p, X, Y, s * sc, None, {"flip": fl})
    g.ell(110, -36, 24, 12, (150, 150, 160), 3)


def tree(p, x, y, s, c, k):
    col = _c(c, (110, 172, 90))
    g = Sk(p, x, y, s, wob=0.5)
    trunk = (150, 104, 68)
    g.poly([(-22, 0), (22, 0), (16, -150), (40, -200), (28, -206), (8, -176), (-6, -210), (-20, -204), (-12, -160)],
           trunk, 5)
    blobs = ((-70, -230, 66), (60, -236, 70), (0, -290, 82), (-40, -330, 56), (50, -320, 58), (0, -210, 60))
    for cx, cy, r in blobs:
        g.circ(cx, cy, r, darker(col, 0.85), 5)
    for cx, cy, r in blobs:
        g.circ(cx - 4, cy - 6, r - 10, col, 0)
    for cx, cy, r in ((-40, -300, 18), (30, -270, 14), (-70, -240, 12)):
        g.circ(cx, cy, r, lighter(col, 0.3), 0)
    if k.get("apples"):
        for cx, cy in ((-60, -220), (40, -250), (10, -320), (70, -300)):
            g.circ(cx, cy, 9, (214, 50, 50), 2.4)


def mountain(p, x, y, s, c, k):
    col = _c(c, (150, 150, 168))
    g = Sk(p, x, y, s, wob=0.5)
    for cx, h, w, cc in ((-150, 230, 190, darker(col, 0.9)), (160, 260, 210, darker(col, 0.92)), (0, 350, 260, col)):
        g.poly([(cx - w, 0), (cx, -h), (cx + w, 0)], cc, 6)
        g.poly([(cx, -h), (cx + w * 0.5, -h * 0.5), (cx + w, 0), (cx + w * 0.2, 0)], darker(cc, 0.88), 0)
        g.poly([(cx - w, 0), (cx, -h), (cx + w, 0)], None, 6)
        sw = w * 0.3
        g.poly([(cx - sw, -h * 0.7), (cx, -h), (cx + sw, -h * 0.7), (cx + sw * 0.4, -h * 0.64), (cx, -h * 0.74),
                (cx - sw * 0.4, -h * 0.64)], WHITE, 4)


def flag(p, x, y, s, c, k):
    """A flag on a pole that waves (params.t = seconds, loops every 1.2 s)."""
    col = _c(c, RED)
    c2 = C(k["color2"]) if k.get("color2") else None
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    ph = 2 * math.pi * _num(k, "t", 0) / 1.2
    n = 10

    def edge(u, base):
        return (170 * u, base + 11 * u * math.sin(2 * math.pi * u * 1.1 - ph))

    top = [edge(i / n, -270) for i in range(n + 1)]
    bot = [edge(i / n, -160) for i in range(n + 1)]
    g.line([(0, 0), (0, -280)], 8, WOOD_D)
    g.circ(0, -284, 9, GOLD, 3)
    g.poly(top + bot[::-1], col, 0)
    if c2:
        a, b = int(n / 3), int(2 * n / 3 + 0.5)
        g.poly(top[a:b + 1] + bot[a:b + 1][::-1], c2, 0)
    for i in range(1, n, 3):
        u = i / n
        slope = math.cos(2 * math.pi * u * 1.1 - ph)
        if slope < -0.3:
            (x0, y0), (x1, y1) = top[i], bot[i]
            g.line([(x0, y0 + 6), (x1, y1 - 6)], 6, darker(c2 if (c2 and n / 3 <= i <= 2 * n / 3) else col, 0.85))
    g.poly(top + bot[::-1], None, 5)


def smoke(p, x, y, s, c, k):
    """Rising puffs of smoke (params.t = seconds, loops every 2 s)."""
    col = _c(c, (140, 140, 150))
    g = Sk(p, x, y, s, wob=0.4)
    tt = _num(k, "t", 0)
    puffs = []
    for i in range(4):
        q = (tt / 2.0 + i / 4) % 1.0
        puffs.append((q, 10 * math.sin(q * 5 + i), -20 - q * 190, 20 + q * 28))
    for q, cx, cy, r in sorted(puffs, key=lambda v: -v[0]):
        g.circ(cx, cy, r, col if q < 0.75 else lighter(col, 0.3), 5)


THINGS = {
    "catapult": ("bottom", catapult, "siege catapult / trebuchet (sieges, medieval, ancient war). params: flip"),
    "chariot": ("bottom", chariot, "war chariot pulled by a horse (Rome, Egypt, ancient war). color, params: flip"),
    "guillotine": ("bottom", guillotine, "guillotine (French Revolution, the Terror). somber"),
    "barricade": ("bottom", barricade, "street barricade with a flag (revolution, uprising). color = flag"),
    "sandbags": ("bottom", sandbags, "wall of sandbags (trenches, WW1, WW2, defense)"),
    "wagon": ("bottom", wagon, "covered wagon (pioneers, Wild West, migrations, supply trains). params: flip"),
    "musket": ("center", musket, "musket with bayonet (1600s-1800s armies, revolutions). params: angle, bayonet"),
    "shield": ("center", shield, "knight's shield. color, params: color2 (cross)"),
    "spear": ("center", spear, "spear (ancient armies, tribes). params: angle"),
    "axe": ("center", axe, "battle axe (Vikings). params: angle"),
    "drum": ("bottom", drum, "military marching drum (armies, war declared). color"),
    "medal": ("center", medal, "medal on a ribbon (honor, heroes, awards). color"),
    "zeppelin": ("center", zeppelin, "zeppelin airship (Germany, WW1, Hindenburg). params: label, flip"),
    "biplane": ("center", biplane, "WW1 biplane (Red Baron, early flight). color, params: angle, flip"),
    "hot_air_balloon": ("center", hot_air_balloon, "hot air balloon (exploration, 1700s-1800s France). color"),
    "helicopter": ("center", helicopter, "helicopter (Vietnam, rescue, modern war). color, params: flip"),
    "dynamite": ("center", dynamite, "dynamite with lit fuse (explosive plan, mining, sabotage)"),
    "barbed_wire": ("bottom", barbed_wire, "barbed wire fence (WW1 trenches, borders, prison camps)"),
    "satellite": ("center", satellite, "Sputnik satellite (Space Race). params: style ('modern' for solar panels)"),
    "quill": ("center", quill, "quill pen in an inkpot (writing laws, letters, signing)"),
    "envelope": ("center", envelope, "sealed letter envelope (messages, telegrams, secret letters)"),
    "newspaper": ("center", newspaper, "newspaper. params: label (headline, e.g. 'WAR!'), title"),
    "gold_bars": ("bottom", gold_bars, "stack of gold bars (wealth, reserves, treasure)"),
    "torch": ("center", torch, "burning torch (exploring, angry mobs, light). params: angle"),
    "telescope": ("bottom", telescope, "brass telescope on a tripod (astronomy, Galileo, lookouts). color"),
    "compass": ("center", compass, "navigation compass (explorers, direction)"),
    "treasure_map": ("center", treasure_map, "old treasure map with an X (exploration, pirates, plans)"),
    "key": ("center", key, "old golden key (secrets, solutions, unlocking). params: angle"),
    "telephone": ("bottom", telephone, "rotary telephone (hotline, calls, Cold War). color"),
    "computer": ("bottom", computer, "retro computer (tech, internet, codebreaking). color"),
    "microphone": ("bottom", microphone, "vintage microphone on a stand (speeches, radio, singing)"),
    "podium": ("bottom", podium, "speaker's podium with a mic (speeches, presidents, debates). params: label"),
    "megaphone": ("center", megaphone, "megaphone (protests, announcements). params: flip"),
    "camera": ("center", camera, "old camera (photos, press, evidence)"),
    "pickaxe": ("center", pickaxe, "pickaxe (gold rush, mining, labor). params: angle"),
    "hammer": ("center", hammer, "hammer (building, industry, workers). params: angle"),
    "bell": ("bottom", bell, "big bronze bell (Liberty Bell, alarm, church). params: cracked (bool)"),
    "briefcase": ("bottom", briefcase, "briefcase (diplomats, business, secret documents). color"),
    "atom": ("center", atom, "atom symbol (science, nuclear, physics)"),
    "flask": ("bottom", flask, "bubbling chemistry flask (science, invention, poison). color"),
    "gear": ("center", gear, "gear / cog (industry, machines, systems). color"),
    "chess_piece": ("bottom", chess_piece, "chess piece (strategy, master plan). params: piece king|knight|pawn"),
    "amphora": ("bottom", amphora, "ancient Greek vase (Greece, trade, wine, olive oil)"),
    "piggy_bank": ("bottom", piggy_bank, "piggy bank with a coin (savings, budget, economy)"),
    "cash": ("bottom", cash, "stack of banknotes (money, bribes, wages)"),
    "keg": ("bottom", keg, "wooden keg (gunpowder, beer, supplies). params: label"),
}

UPGRADES = {
    "flag": ("bottom", flag, "flag on a pole, waving. color + params: color2 (middle stripe)"),
    "smoke": ("bottom", smoke, "rising smoke. color"),
    "barrel": ("bottom", oil_barrel, "oil barrel / steel drum. color, params: empty (bool, crossed out)"),
    "bomb": ("center", bomb, "falling aerial bomb, nose down. params: angle"),
    "helmet": ("bottom", helmet, "soldier helmet on the ground. color"),
    "sword": ("center", sword, "sword. params: angle"),
    "cannon": ("bottom", cannon, "old cannon on a wheel with cannonballs. params: flip"),
    "candle": ("bottom", candle, "memorial candle (somber)"),
    "coin": ("bottom", coin, "gold coin standing on its edge. params: label (1-2 characters like $)"),
    "scroll": ("center", scroll, "rolled parchment scroll with a wax seal (treaty, decree, law)"),
    "document": ("center", document, "signed sheet of paper (law, letter, contract). params: lines"),
    "crown": ("bottom", crown, "jeweled crown (power, monarchy). color"),
    "fire": ("bottom", campfire, "campfire / big fire with logs"),
    "island": ("bottom", island, "small tropical island with palm trees. color = grass"),
    "tree": ("bottom", tree, "leafy tree. color, params: apples (bool)"),
    "mountain": ("bottom", mountain, "snowy mountain range (Alps, Himalayas, crossing mountains). color"),
}
