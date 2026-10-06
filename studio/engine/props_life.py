"""Animals and food. Animals face right; params.flip makes them face left."""
import math

from .palette import color as C, INK, RED, WHITE, darker, lighter
from .props_kit import Sk, arc_pts, ellipse, rounded, star_pts, GOLD, GOLD_D, WOOD, WOOD_D, CREAM, LEAF, LEAF_D, GLASS


def _c(c, default):
    return C(c, default) if c is not None else default


def _flip(k):
    return bool(k.get("flip")) or str(k.get("facing", "")).lower() == "left"


def tube(g, pts, w, col):
    g.line(pts, w + 6, INK)
    g.line(pts, w, col)


def eye(g, cx, cy, r=6):
    g.circ(cx, cy, r, INK, 0)
    g.circ(cx + r * 0.35, cy - r * 0.35, r * 0.35, WHITE, 0)


# ------------------------------------------------------------------ animals
def horse(p, x, y, s, c, k):
    col = _c(c, (150, 98, 62))
    dark = darker(col, 0.55)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    tube(g, [(-128, -196), (-160, -150), (-170, -96)], 16, dark)
    for lx, kx in ((-104, -112), (84, 92)):
        tube(g, [(lx + 10, -150), (kx + 6, -80), (lx + 4, -10)], 15, darker(col, 0.85))
    g.poly(ellipse(-10, -184, 134, 56, 26), col, 6)
    for lx, kx in ((-84, -96), (106, 116)):
        tube(g, [(lx, -150), (kx, -80), (lx + 8, -10)], 16, col)
    for hx in (-112, -88, 96, 114):
        g.rect(hx - 10, -14, hx + 12, 0, (60, 50, 46), 3)
    g.poly([(70, -220), (106, -300), (130, -330), (152, -326), (128, -270), (114, -180)], col, 5)
    g.poly([(118, -334), (150, -342), (210, -282), (204, -262), (178, -258), (128, -284)], col, 5)
    g.poly([(122, -330), (128, -352), (138, -334)], col, 3)
    g.poly([(64, -222), (96, -298), (124, -340), (110, -296), (82, -224)], dark, 3)
    eye(g, 150, -316, 5)
    g.circ(196, -276, 3, INK, 0)
    if k.get("saddle", True) is not False:
        g.poly([(-60, -236), (40, -236), (30, -170), (-50, -170)], (196, 56, 52), 4)
        g.poly([(-44, -246), (24, -246), (16, -230), (-36, -230)], (110, 70, 44), 4)


def cow(p, x, y, s, c, k):
    bull = bool(k.get("bull"))
    col = _c(c, (70, 52, 44) if bull else (250, 250, 246))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    hoof = (60, 56, 56)
    tube(g, [(-126, -160), (-142, -110), (-138, -76)], 6, col)
    g.circ(-138, -70, 9, (60, 50, 46), 3)
    for lx in (-100, -66, 54, 86):
        g.rect(lx - 11, -86, lx + 11, -8, col, 4)
        g.rect(lx - 11, -12, lx + 11, 0, hoof, 3)
    g.rect(-128, -176, 106, -74, col, 6, r=40)
    if not bull:
        for cx, cy, rx, ry in ((-70, -140, 30, 22), (10, -110, 26, 20), (60, -150, 20, 16)):
            g.poly(ellipse(cx, cy, rx, ry, 10), (40, 40, 46), 0)
        g.ell(-20, -72, 22, 12, (246, 170, 180), 3)
    g.poly([(90, -170), (150, -196), (176, -160), (170, -116), (120, -110)], col, 5)
    g.ell(166, -122, 24, 18, (246, 180, 180) if not bull else (120, 96, 86), 4)
    g.circ(160, -124, 3, INK, 0)
    g.circ(174, -122, 3, INK, 0)
    eye(g, 140, -168, 4.5)
    g.poly([(112, -180), (90, -196), (106, -172)], col, 3)
    horn = (240, 232, 210)
    hl = 34 if bull else 18
    g.poly([(140, -194), (150, -194 - hl), (156, -192)], horn, 3)
    if bull:
        g.circ(176, -108, 9, None, 3, GOLD)


def sheep(p, x, y, s, c, k):
    wool = _c(c, (248, 246, 236))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    for lx in (-60, -30, 36, 62):
        g.line([(lx, -60), (lx, 0)], 9, (50, 50, 56))
    pts = []
    for i in range(16):
        a = 2 * math.pi * i / 16
        r = 1 + (0.12 if i % 2 else 0)
        pts.append((math.cos(a) * 100 * r, -100 + math.sin(a) * 56 * r))
    g.poly(pts, wool, 6)
    g.poly(ellipse(108, -124, 30, 22, 14), (60, 60, 66), 5)
    g.poly([(86, -136), (66, -146), (84, -124)], (60, 60, 66), 3)
    g.circ(118, -130, 4, WHITE, 0)
    g.circ(84, -150, 16, wool, 4)


def chicken(p, x, y, s, c, k, rooster=False):
    col = _c(c, (210, 110, 50) if rooster else (252, 250, 244))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    leg = (246, 170, 60)
    for lx in (-14, 14):
        g.line([(lx, -44), (lx, 0)], 5, leg)
        g.line([(lx - 12, 0), (lx + 14, 0)], 4, leg)
    if rooster:
        for i, cc in enumerate(((30, 50, 60), (40, 90, 80), (40, 70, 140), (40, 90, 80))):
            tube(g, [(-40, -86), (-62 - i * 6, -150 + i * 12), (-96 - i * 4, -150 + i * 16),
                     (-110 - i * 2, -100 + i * 14)], 9, cc)
    else:
        g.poly([(-50, -80), (-80, -120), (-70, -70)], col, 4)
    g.poly(ellipse(0, -76, 56, 40, 18), col, 6)
    g.poly(ellipse(34, -132 if rooster else -120, 26, 30, 14), (236, 186, 70) if rooster else col, 5)
    comb = [(18, -158), (24, -180), (34, -166), (42, -184), (50, -164), (56, -150)] if rooster else \
        [(22, -146), (28, -160), (36, -150), (44, -160), (48, -142)]
    g.poly(comb, (224, 50, 50), 3)
    g.poly([(58, -128 if rooster else -116), (78, -122 if rooster else -110), (58, -116 if rooster else -104)],
           (246, 170, 60), 3)
    g.ell(56, -106 if rooster else -96, 7, 11, (224, 50, 50), 2.4)
    eye(g, 42, -136 if rooster else -124, 4)
    g.arc(-6, -76, 30, 20, 200, 340, 3, darker(col, 0.8))


def rooster(p, x, y, s, c, k):
    chicken(p, x, y, s, c, k, rooster=True)


def pig(p, x, y, s, c, k):
    col = _c(c, (246, 176, 182))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    for lx in (-60, -34, 40, 66):
        g.rect(lx - 10, -50, lx + 10, 0, col, 4)
    g.arc(-118, -110, 16, 16, 90, 400, 4, d)
    g.poly(ellipse(0, -96, 112, 58, 24), col, 6)
    g.poly([(70, -140), (60, -176), (96, -150)], col, 4)
    g.ell(118, -96, 18, 22, d, 4)
    g.circ(112, -98, 3, INK, 0)
    g.circ(124, -98, 3, INK, 0)
    eye(g, 88, -122, 4.5)
    g.arc(90, -78, 14, 8, 20, 160, 3)


def dog(p, x, y, s, c, k, wolf=False):
    col = _c(c, (130, 130, 140) if wolf else (186, 130, 80))
    d = darker(col, 0.7)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    if wolf:
        g.poly([(-90, -120), (-150, -70), (-146, -50), (-90, -90)], col, 5)
    else:
        tube(g, [(-90, -120), (-120, -160), (-112, -190)], 10, col)
    for lx in (-70, -44, 50, 74):
        g.rect(lx - 10, -84, lx + 10, 0, col, 4)
    g.rect(-100, -150, 96, -72, col, 6, r=36)
    head = [(70, -150), (90, -196), (130, -206), (164 if wolf else 150, -184), (196 if wolf else 176, -168),
            (190 if wolf else 172, -150), (120, -140)]
    g.poly(head, col, 5)
    if wolf:
        g.poly([(96, -196), (100, -236), (118, -204)], col, 4)
        g.poly([(116, -204), (130, -238), (140, -200)], col, 4)
    else:
        g.poly([(100, -200), (82, -164), (98, -150), (112, -194)], d, 4)
    g.circ(194 if wolf else 174, -164, 6, INK, 0)
    eye(g, 136, -184, 4.5)
    g.line([(150, -152), (176 if wolf else 160, -150)], 3)
    g.ell(-10, -84, 60, 10, lighter(col, 0.3), 0)


def wolf(p, x, y, s, c, k):
    dog(p, x, y, s, c, k, wolf=True)


def cat(p, x, y, s, c, k):
    col = _c(c, (238, 152, 72))
    d = darker(col, 0.75)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    tube(g, [(-40, -10), (-80, -20), (-90, -60), (-70, -80)], 12, col)
    g.poly([(-50, 0), (-46, -60), (-26, -110), (26, -110), (46, -60), (50, 0)], col, 6)
    for xx in (-20, 20):
        g.line([(xx, -40), (xx, 0)], 3, d)
    g.circ(0, -140, 44, col, 6)
    for f in (1, -1):
        g.poly([(-40 * f, -156), (-34 * f, -200), (-12 * f, -178)], col, 4)
        g.line([(-14 * f, -128), (-56 * f, -134)], 2, INK)
        g.line([(-14 * f, -122), (-56 * f, -116)], 2, INK)
    eye(g, -16, -146, 5)
    eye(g, 16, -146, 5)
    g.poly([(-5, -130), (5, -130), (0, -124)], (240, 140, 150), 2)
    for xx in (-24, 0, 24):
        g.line([(xx - 4, -110 + abs(xx) * 0.1), (xx + 4, -102)], 2.6, d)


def rat(p, x, y, s, c, k):
    col = _c(c, (150, 146, 150))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    g.line([(-60, -24), (-110, -20), (-140, -40), (-160, -30)], 5, (230, 160, 170))
    for lx in (-30, 30):
        g.line([(lx, -20), (lx + 6, 0)], 4, (230, 160, 170))
    g.poly([(-70, -10), (-60, -50), (-10, -66), (40, -60), (86, -34), (100, -24), (80, -12), (20, -6)], col, 5)
    g.circ(40, -66, 16, col, 4)
    g.circ(40, -66, 8, (240, 170, 180), 0)
    g.circ(100, -26, 5, (240, 140, 150), 0)
    eye(g, 70, -40, 4)
    for dy in (-6, 2):
        g.line([(96, -24 + dy), (122, -30 + dy * 2)], 1.6, INK)


def camel(p, x, y, s, c, k):
    col = _c(c, (218, 176, 116))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    for lx in (-80, 70):
        tube(g, [(lx + 14, -150), (lx + 20, -80), (lx + 12, -6)], 13, d)
    tube(g, [(-118, -190), (-140, -150), (-134, -110)], 6, col)
    g.poly([(-120, -150), (-124, -200), (-80, -220), (-50, -300), (10, -310), (50, -230), (90, -220), (110, -170),
            (100, -130), (-100, -128)], col, 6)
    for lx in (-60, 92):
        tube(g, [(lx, -150), (lx + 6, -80), (lx - 2, -6)], 14, col)
    g.poly([(90, -200), (126, -270), (146, -320), (176, -330), (210, -312), (206, -296), (170, -290), (146, -250),
            (120, -170)], col, 5)
    eye(g, 180, -316, 4)
    g.poly([(166, -334), (170, -346), (178, -332)], col, 3)
    g.line([(196, -300), (206, -302)], 2.6)


def elephant(p, x, y, s, c, k):
    col = _c(c, (156, 160, 172))
    d = darker(col, 0.8)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    tube(g, [(-150, -220), (-168, -180), (-170, -140)], 5, col)
    for lx in (-120, 60):
        g.rect(lx, -130, lx + 44, 0, d, 5, r=8)
    g.poly(ellipse(-20, -200, 150, 100, 28), col, 6)
    for lx in (-80, 100):
        g.rect(lx, -130, lx + 46, 0, col, 5, r=8)
        for tx in (lx + 10, lx + 22, lx + 34):
            g.arc(tx, -2, 5, 5, 180, 360, 2, d)
    g.poly(ellipse(120, -240, 76, 70, 24), col, 6)
    g.poly([(160, -230), (200, -200), (210, -140), (200, -80), (224, -60), (236, -78), (226, -86), (220, -140),
            (216, -200), (190, -250)], col, 5)
    for yy in (-170, -140, -110):
        g.line([(200, yy), (218, yy + 4)], 2.4, d)
    g.poly([(170, -196), (200, -170), (210, -150), (186, -170)], CREAM, 3)
    g.poly(ellipse(84, -232, 50, 62, 18), d, 5)
    eye(g, 150, -262, 5)


def eagle(p, x, y, s, c, k):
    col = _c(c, (110, 76, 52))
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    for f in (1, -1):
        pts = [(-20 * f, -10), (-70 * f, -60), (-130 * f, -110), (-190 * f, -120)]
        for i in range(5):
            fx = -190 * f + i * 26 * f
            pts += [(fx - 8 * f, -96 + i * 12), (fx + 8 * f, -84 + i * 16)]
        pts += [(-60 * f, 10), (-20 * f, 20)]
        g.poly(pts, col, 5)
        for i in range(3):
            g.line([(-50 * f - i * 34 * f, -30 - i * 14), (-90 * f - i * 30 * f, -70 - i * 10)], 2.4, darker(col, 0.7))
    g.poly([(-30, 50), (0, 100), (30, 50)], WHITE, 4)
    g.poly(ellipse(0, 10, 36, 56, 18), col, 5)
    g.circ(0, -56, 26, WHITE, 5)
    g.poly([(18, -60), (44, -52), (30, -36), (16, -44)], (246, 190, 60), 3)
    eye(g, 8, -62, 4)
    for f in (1, -1):
        g.line([(10 * f, 60), (14 * f, 80)], 5, (246, 190, 60))


def lion(p, x, y, s, c, k):
    col = _c(c, (228, 172, 92))
    mane = darker(col, 0.72)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.4)
    tube(g, [(-120, -130), (-160, -160), (-170, -200)], 6, col)
    g.circ(-172, -206, 12, mane, 4)
    for lx in (-96, -66, 60, 88):
        g.rect(lx - 12, -96, lx + 12, 0, col, 4)
    g.rect(-128, -170, 110, -84, col, 6, r=42)
    pts = []
    for i in range(18):
        a = 2 * math.pi * i / 18
        r = 82 if i % 2 else 66
        pts.append((110 + math.cos(a) * r, -176 + math.sin(a) * r))
    g.poly(pts, mane, 5)
    g.circ(118, -170, 46, col, 5)
    g.poly([(116, -150), (140, -150), (128, -138)], (110, 70, 60), 2.4)
    eye(g, 104, -182, 5)
    eye(g, 136, -182, 5)
    g.arc(128, -130, 12, 8, 20, 160, 3)


def dragon(p, x, y, s, c, k):
    col = _c(c, (206, 60, 56))
    wing = darker(col, 0.75)
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.35)
    g.poly([(-40, -40), (-90, -150), (-30, -120), (0, -170), (20, -110), (60, -150), (30, -40)], wing, 5)
    tube(g, [(-60, 0), (-120, 20), (-170, 0), (-190, -30)], 18, col)
    g.poly([(-190, -30), (-214, -60), (-182, -52), (-196, -20)], col, 4)
    g.poly(ellipse(0, 0, 80, 44, 22), col, 6)
    for lx in (-40, 40):
        tube(g, [(lx, 30), (lx + 6, 66)], 14, col)
    g.poly([(60, -20), (100, -80), (130, -90), (170, -80), (176, -60), (140, -56), (110, -40), (80, 10)], col, 5)
    g.poly([(120, -88), (110, -120), (134, -92)], (240, 220, 180), 3)
    eye(g, 140, -76, 5)
    for i in range(5):
        g.poly([(-60 + i * 30, -40), (-48 + i * 30, -60), (-36 + i * 30, -40)], (250, 210, 80), 2.4)
    if k.get("fire"):
        g.poly([(178, -66), (260, -100), (240, -66), (290, -60), (240, -46), (262, -20)], (246, 150, 50), 4)
        g.poly([(184, -64), (236, -78), (228, -60), (246, -52), (196, -54)], (252, 222, 90), 0)


def panda(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    blk = (40, 40, 46)
    for f in (1, -1):
        g.ell(-40 * f, -20, 30, 22, blk, 4)
    g.poly(ellipse(0, -76, 66, 72, 22), WHITE, 6)
    for f in (1, -1):
        tube(g, [(-50 * f, -110), (-70 * f, -70), (-40 * f, -60)], 22, blk)
        g.circ(-34 * f, -194, 18, blk, 4)
    g.circ(0, -160, 48, WHITE, 6)
    for f in (1, -1):
        g.poly(ellipse(-18 * f, -166, 13, 17, 10), blk, 0)
        g.circ(-18 * f, -168, 4, WHITE, 0)
    g.ell(0, -146, 9, 6, blk, 0)
    g.arc(0, -138, 9, 6, 20, 160, 2.6)


def penguin(p, x, y, s, c, k):
    g = Sk(p, x, y, s, flip=_flip(k), wob=0.3)
    blk = (40, 44, 56)
    for f in (1, -1):
        g.ell(-16 * f, -4, 18, 7, (246, 160, 50), 3)
    g.poly(ellipse(0, -76, 46, 76, 22), blk, 6)
    g.poly(ellipse(6, -66, 30, 60, 18), WHITE, 0)
    g.poly([(-40, -100), (-62, -50), (-40, -60)], blk, 4)
    g.circ(0, -150, 32, blk, 5)
    g.poly(ellipse(8, -146, 18, 18, 12), WHITE, 0)
    g.poly([(24, -150), (46, -144), (24, -138)], (246, 160, 50), 3)
    eye(g, 12, -152, 4)


# ------------------------------------------------------------------ food
def baguette(p, x, y, s, c, k):
    col = _c(c, (222, 168, 92))
    g = Sk(p, x, y, s, rot=-18, wob=0.35)
    g.rect(-170, -30, 170, 30, col, 6, r=30)
    for xx in (-110, -50, 10, 70, 130):
        g.line([(xx - 20, 14), (xx + 18, -16)], 6, lighter(col, 0.5))
        g.line([(xx - 18, 18), (xx + 20, -12)], 2.4, darker(col, 0.7))


def cheese(p, x, y, s, c, k):
    col = _c(c, (250, 206, 80))
    d = darker(col, 0.85)
    g = Sk(p, x, y, s, wob=0.35)
    g.poly([(-110, 0), (110, 0), (110, -80), (-110, -40)], d, 6)
    g.poly([(-110, -40), (110, -80), (60, -120), (-110, -40)], col, 6)
    for cx, cy, r in ((-60, -20, 12), (30, -30, 16), (80, -16, 9), (-10, -50, 8)):
        g.circ(cx, cy, r, darker(col, 0.72), 3)
    for cx, cy, r in ((20, -84, 10), (60, -96, 6)):
        g.ell(cx, cy, r, r * 0.5, darker(col, 0.8), 2.4)


def wine(p, x, y, s, c, k):
    col = _c(c, (60, 110, 70))
    red = (150, 30, 50)
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-80, -190, -16, 0, col, 6, r=20)
    g.rect(-62, -270, -34, -186, col, 5)
    g.rect(-64, -284, -32, -266, (150, 30, 50), 4)
    g.rect(-76, -120, -20, -60, CREAM, 3)
    g.line([(-66, -100), (-30, -100)], 3, red)
    g.line([(-62, -82), (-34, -82)], 2.4, (150, 140, 120))
    g.line([(-34, -180), (-30, -30)], 4, lighter(col, 0.5))
    g.line([(50, -80), (50, -14)], 5)
    g.ell(50, -8, 30, 8, GLASS, 4)
    g.poly(arc_pts(50, -136, 40, 60, 0, 180, 14), GLASS, 4)
    g.poly(arc_pts(50, -120, 34, 42, 0, 180, 12), red, 0)
    g.line([(12, -136), (88, -136)], 4)


def croissant(p, x, y, s, c, k):
    col = _c(c, (228, 160, 72))
    g = Sk(p, x, y, s, wob=0.35)
    segs = [(-80, 18, 22, 26), (-46, -6, 30, 34), (0, -18, 36, 40), (46, -6, 30, 34), (80, 18, 22, 26)]
    for cx, cy, rx, ry in segs:
        g.poly(ellipse(cx, cy, rx, ry, 16), col, 5)
    for cx, cy, rx, ry in segs[1:-1]:
        g.arc(cx, cy, rx * 0.6, ry * 0.7, 200, 340, 3, darker(col, 0.75))
    g.circ(-6, -34, 8, lighter(col, 0.5), 0)


def beer(p, x, y, s, c, k):
    col = _c(c, (246, 190, 60))
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(40, -140, 84, -50, None, 14, INK)
    g.rect(40, -140, 84, -50, None, 8, GLASS)
    g.rect(-60, -160, 50, 0, col, 6, r=10)
    for xx in (-30, 0, 30):
        g.line([(xx, -130), (xx, -20)], 3, lighter(col, 0.45))
    for cx, cy, r in ((-46, -164, 24), (-14, -174, 28), (22, -168, 26), (44, -156, 18)):
        g.circ(cx, cy, r, WHITE, 5)
    for cx, cy, r in ((-46, -164, 24), (-14, -174, 28), (22, -168, 26), (44, -156, 18)):
        g.circ(cx, cy, r - 5, WHITE, 0)
    g.rect(-55, -150, 45, -140, WHITE, 0)


def teapot(p, x, y, s, c, k):
    col = _c(c, (250, 250, 246))
    d = (60, 110, 190)
    g = Sk(p, x, y, s, wob=0.35)
    tube(g, [(80, -90), (120, -120), (140, -150)], 14, col)
    g.arc(-90, -90, 34, 40, 90, 270, 14, INK)
    g.arc(-90, -90, 34, 40, 90, 270, 8, col)
    g.poly(ellipse(0, -84, 96, 76, 26), col, 6)
    g.poly(arc_pts(0, -152, 46, 18, 180, 360, 12), col, 5)
    g.circ(0, -176, 10, d, 4)
    for xx in (-40, 0, 40):
        g.circ(xx, -90, 12, d, 0)
    g.line([(-80, -40), (80, -40)], 4, d)
    g.ell(0, -8, 60, 8, darker(col, 0.85), 4)


def coffee(p, x, y, s, c, k):
    col = _c(c, (250, 250, 246))
    g = Sk(p, x, y, s, wob=0.35)
    for sx in (-20, 10):
        g.line([(sx, -150), (sx + 12, -180), (sx - 4, -206), (sx + 8, -236)], 4, (190, 190, 200))
    g.arc(56, -80, 26, 30, -90, 90, 12, INK)
    g.arc(56, -80, 26, 30, -90, 90, 6, col)
    g.poly([(-60, -130), (60, -130), (48, -20), (-48, -20)], col, 6)
    g.ell(0, -130, 60, 12, (110, 70, 44), 4)
    g.ell(0, -10, 96, 14, col, 5)


def sushi(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    g.rect(-140, -26, 140, 0, (60, 60, 70), 5, r=8)
    for cx in (-80, 20):
        g.rect(cx - 40, -70, cx + 40, -26, WHITE, 5, r=18)
        g.poly([(cx - 46, -64), (cx - 30, -92), (cx + 40, -96), (cx + 50, -70)], (246, 140, 100), 5)
        for i in range(3):
            g.line([(cx - 20 + i * 22, -70), (cx - 10 + i * 22, -92)], 3, WHITE)
    g.rect(78, -76, 128, -26, (40, 56, 46), 5, r=10)
    g.circ(103, -66, 18, WHITE, 3)
    g.circ(103, -66, 8, (246, 140, 100), 0)


def pizza(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    g.circ(0, 0, 110, (226, 170, 90), 6)
    g.circ(0, 0, 92, (250, 210, 100), 0)
    for i in range(4):
        a = math.radians(i * 45)
        g.line([(math.cos(a) * 110, math.sin(a) * 110), (-math.cos(a) * 110, -math.sin(a) * 110)], 3, (200, 140, 70))
    for cx, cy in ((-40, -40), (30, -60), (50, 20), (-20, 50), (-60, 10), (10, 0)):
        g.circ(cx, cy, 14, (200, 60, 50), 3)


def burger(p, x, y, s, c, k):
    g = Sk(p, x, y, s, wob=0.35)
    bun = (226, 160, 80)
    g.rect(-100, -40, 100, 0, bun, 6, r=18)
    g.rect(-108, -70, 108, -40, (120, 70, 46), 6, r=14)
    g.poly([(-110, -70), (110, -70), (100, -84), (60, -76), (20, -88), (-20, -76), (-60, -88), (-100, -80)],
           (250, 200, 60), 4)
    g.poly([(-110, -84), (110, -84), (100, -98), (40, -90), (0, -100), (-40, -90), (-100, -98)], LEAF, 4)
    g.poly(arc_pts(0, -96, 104, 80, 180, 360, 18), bun, 6)
    for cx, cy in ((-40, -140), (0, -156), (40, -138), (-10, -126), (60, -120)):
        g.ell(cx, cy, 6, 3, (252, 240, 200), 0)


def apple(p, x, y, s, c, k):
    col = _c(c, (214, 50, 50))
    g = Sk(p, x, y, s, wob=0.35)
    g.line([(0, -110), (6, -140)], 6, (110, 76, 50))
    g.poly([(6, -128), (50, -150), (30, -118)], LEAF, 3)
    g.poly([(-4, -110), (-50, -116), (-76, -80), (-74, -30), (-40, 0), (0, -10), (40, 0), (74, -30), (76, -80),
            (50, -116), (4, -110)], col, 6)
    g.ell(-40, -70, 10, 18, lighter(col, 0.5), 0)


def potato(p, x, y, s, c, k):
    col = _c(c, (196, 150, 96))
    g = Sk(p, x, y, s, rot=-10, wob=0.8)
    g.poly(ellipse(0, 0, 90, 58, 18), col, 6)
    for cx, cy in ((-40, -10), (20, -26), (40, 20), (-10, 24)):
        g.arc(cx, cy, 6, 4, 0, 180, 2.6, darker(col, 0.7))


def rice_bowl(p, x, y, s, c, k):
    col = _c(c, (220, 70, 60))
    g = Sk(p, x, y, s, wob=0.35)
    g.line([(-40, -80), (120, -170)], 6, (110, 76, 50))
    g.line([(-30, -70), (130, -150)], 6, (110, 76, 50))
    for cx, cy in ((-50, -80), (-20, -94), (14, -96), (46, -84), (0, -80)):
        g.circ(cx, cy, 22, WHITE, 4)
    g.poly(arc_pts(0, -70, 80, 70, 0, 180, 16), col, 6)
    g.line([(-60, -40), (60, -40)], 3, WHITE)
    g.rect(-30, -8, 30, 0, col, 4)


def matryoshka(p, x, y, s, c, k):
    col = _c(c, (214, 56, 52))
    g = Sk(p, x, y, s, wob=0.35)
    g.poly(ellipse(0, -80, 64, 80, 24), col, 6)
    g.circ(0, -178, 46, col, 6)
    g.circ(0, -172, 30, (252, 232, 214), 4)
    g.circ(-10, -176, 3, INK, 0)
    g.circ(10, -176, 3, INK, 0)
    g.circ(-16, -164, 5, (246, 150, 150), 0)
    g.circ(16, -164, 5, (246, 150, 150), 0)
    g.arc(0, -162, 7, 4, 20, 160, 2.4)
    g.poly(ellipse(0, -76, 40, 48, 16), (252, 230, 180), 4)
    for cx, cy, cc in ((0, -86, (60, 120, 200)), (-16, -66, (250, 200, 60)), (16, -66, (250, 200, 60))):
        g.circ(cx, cy, 10, cc, 3)
    g.line([(0, -76), (0, -40)], 3, LEAF_D)


ANIMALS = {
    "horse": ("bottom", horse, "horse (cavalry, travel, knights). color, params: saddle (bool), flip"),
    "cow": ("bottom", cow, "dairy cow (farming). params: flip"),
    "bull": ("bottom", lambda p, x, y, s, c, k: cow(p, x, y, s, c, dict(k, bull=True)), "bull (Spain, Wall Street)"),
    "sheep": ("bottom", sheep, "sheep (farming, wool, Britain, New Zealand)"),
    "chicken": ("bottom", chicken, "chicken (farm, food, cowardice)"),
    "rooster": ("bottom", rooster, "rooster (symbol of France, morning)"),
    "pig": ("bottom", pig, "pig (farm, greed)"),
    "dog": ("bottom", dog, "dog. color"),
    "wolf": ("bottom", wolf, "wolf (Rome's she-wolf, danger, wilderness)"),
    "cat": ("bottom", cat, "sitting cat (Egypt, pets). color"),
    "rat": ("bottom", rat, "rat (plague, disease, sieges, traitor)"),
    "camel": ("bottom", camel, "camel (desert, Silk Road, Arabia, caravans)"),
    "elephant": ("bottom", elephant, "elephant (Hannibal, India, Africa, war elephants)"),
    "eagle": ("center", eagle, "eagle with spread wings (USA, Rome, empire symbol). color"),
    "lion": ("bottom", lion, "lion (Britain, Africa, kings, bravery)"),
    "dragon": ("center", dragon, "dragon (China, Wales, legends). color, params: fire (bool)"),
    "panda": ("bottom", panda, "panda (China)"),
    "penguin": ("bottom", penguin, "penguin (Antarctica)"),
}

FOOD = {
    "baguette": ("center", baguette, "French baguette bread"),
    "cheese": ("bottom", cheese, "wedge of cheese (France, Switzerland, Netherlands)"),
    "wine": ("bottom", wine, "wine bottle and glass (France, Italy, celebrations). color = bottle"),
    "croissant": ("center", croissant, "croissant (France, breakfast)"),
    "beer": ("bottom", beer, "mug of beer (Germany, Oktoberfest, pubs)"),
    "teapot": ("bottom", teapot, "teapot (Britain, China, tea trade, Boston Tea Party). color"),
    "coffee": ("bottom", coffee, "steaming cup of coffee (trade, cafes, work)"),
    "sushi": ("bottom", sushi, "sushi plate (Japan)"),
    "pizza": ("center", pizza, "pizza (Italy)"),
    "burger": ("bottom", burger, "hamburger (USA, fast food)"),
    "apple": ("bottom", apple, "apple (Newton, food, knowledge). color"),
    "potato": ("center", potato, "potato (Ireland, famine, farming)"),
    "rice_bowl": ("bottom", rice_bowl, "bowl of rice with chopsticks (China, Japan, Korea, food supply)"),
    "matryoshka": ("bottom", matryoshka, "Russian nesting doll (Russia, secrets within secrets)"),
}
