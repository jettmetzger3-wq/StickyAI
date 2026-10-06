"""Painted places: themed backgrounds (streets, palaces, harbors, underwater, space...) and city skylines with
real landmarks. Each paint_* function draws one full background onto the Scene, the same way core.bg_* do."""
import math
import random

import numpy as np
from PIL import Image

from .doodle import W, H, SS
from .palette import INK, WHITE, darker, lighter
from .pen import Pen

SKYLINES = {  # city -> landmarks (prop, x, scale) standing on the skyline's ground line
    "paris": [("arc_de_triomphe", 330, 0.6), ("cathedral", 760, 0.5), ("eiffel_tower", 1400, 0.95)],
    "london": [("cathedral", 480, 0.5), ("bridge", 900, 0.6), ("big_ben", 1380, 0.78)],
    "newyork": [("statue_of_liberty", 260, 0.72), ("skyscraper", 820, 0.75), ("skyscraper", 1150, 1.0),
                ("skyscraper", 1500, 0.85)],
    "washington": [("white_house", 330, 0.55), ("obelisk", 760, 1.0), ("capitol", 1350, 0.85)],
    "moscow": [("kremlin", 480, 0.8), ("onion_domes", 1380, 0.85)],
    "rome": [("temple", 400, 0.65), ("aqueduct", 860, 0.55), ("colosseum", 1400, 0.85)],
    "athens": [("temple", 1250, 0.95)],
    "cairo": [("mosque", 360, 0.65), ("obelisk", 800, 0.6), ("pyramid", 1300, 1.0), ("pyramid", 1660, 0.75)],
    "istanbul": [("mosque", 420, 0.6), ("mosque", 1250, 1.0)],
    "delhi": [("mosque", 380, 0.55), ("taj_mahal", 1300, 0.9)],
    "tokyo": [("torii", 380, 0.7), ("pagoda", 1250, 0.8), ("skyscraper", 1650, 0.65)],
    "beijing": [("pagoda", 420, 0.7), ("palace", 1300, 1.0)],
    "berlin": [("church", 400, 0.6), ("brandenburg_gate", 1250, 0.85)],
    "pisa": [("cathedral", 560, 0.5), ("leaning_tower", 1300, 0.9)],
    "amsterdam": [("church", 480, 0.6), ("windmill", 1380, 0.85)],
    "sydney": [("suspension_bridge", 420, 0.6), ("opera_house", 1250, 0.95)],
    "sanfrancisco": [("suspension_bridge", 1100, 1.2)],
}
SKYLINE_ALIASES = {"new_york": "newyork", "nyc": "newyork", "new york": "newyork", "dc": "washington",
                   "constantinople": "istanbul", "peking": "beijing", "san_francisco": "sanfrancisco",
                   "san francisco": "sanfrancisco", "new_delhi": "delhi", "agra": "delhi", "giza": "cairo",
                   "petersburg": "moscow", "st_petersburg": "moscow", "venice": "rome", "florence": "rome",
                   "kyoto": "tokyo", "osaka": "tokyo", "shanghai": "beijing", "munich": "berlin", "vienna": "berlin",
                   "jerusalem": "istanbul", "baghdad": "istanbul", "mecca": "istanbul", "bombay": "delhi",
                   "mumbai": "delhi", "philadelphia": "washington", "boston": "washington"}
STREET_STYLES = ("europe", "medieval", "asia", "arab", "western")


def skyline_key(v):
    s = str(v or "").strip().lower()
    s = SKYLINE_ALIASES.get(s, s).replace(" ", "").replace("_", "")
    return s if s in SKYLINES else None


def far_prop(p, name, x, y, s, haze, k=0.35, params=None):
    """Draw a prop into a background with its bottom-center at (x, y), faded toward the haze color (distance)."""
    from .registry import PROPS, prop_bounds
    if name not in PROPS or s <= 0:
        return
    _, fn, _ = PROPS[name]
    x0, y0, x1, y1 = prop_bounds(name)
    w, h = (x1 - x0) * s + 24, (y1 - y0) * s + 24
    q = Pen(1, rgba=True, size=(w, h))
    fn(q, -x0 * s + 12, -y0 * s + 12, s, None, params or {})
    arr = np.asarray(q.im).astype(np.float32)
    arr[..., :3] = arr[..., :3] * (1 - k) + np.array(haze, np.float32) * k
    im = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
    left, top = x - (x1 - x0) * s / 2 - 12, y - (y1 - y0) * s - 12
    p.im.paste(im, (int(left * SS), int(top * SS)), im)


def _wavy(p, y, col, amp=8, step=60, w=4, x0=-20, x1=W + 20, phase=0.0):
    pts = [(x, y + amp * math.sin(x / step + phase)) for x in range(int(x0), int(x1) + 20, 20)]
    p.line(pts, w, col, 0.3)


# ------------------------------------------------------------------ streets
def _facade(p, r, x, w, gy, style, time):
    night = time == "night"
    win_lit = (255, 222, 140)
    if style == "medieval":
        h = r.randint(300, 400)
        wall = (240, 232, 214)
        p.rect(x, gy - h, w, h, wall, 5)
        beam = (110, 74, 48)
        for k in range(1, 3):
            p.line([(x, gy - h * k / 3), (x + w, gy - h * k / 3)], 7, beam, 0.4)
        p.line([(x + 8, gy - h + 8), (x + w - 8, gy - h / 3 - 8)], 6, beam, 0.4)
        p.poly([(x - 14, gy - h), (x + w / 2, gy - h - 150), (x + w + 14, gy - h)], (150, 70, 52), 5)
    elif style == "asia":
        h = r.randint(230, 320)
        wall = r.choice([(206, 160, 110), (190, 74, 56), (226, 196, 150)])
        p.rect(x, gy - h, w, h, wall, 5)
        p.poly([(x - 30, gy - h + 10), (x - 10, gy - h - 6), (x + w + 10, gy - h - 6), (x + w + 30, gy - h + 10),
                (x + w - 10, gy - h - 50), (x + 10, gy - h - 50)], (52, 58, 74), 5)
        for lx in (x + w * 0.3, x + w * 0.7):
            p.line([(lx, gy - h + 10), (lx, gy - h + 34)], 3, INK, 0.2)
            p.ell(lx, gy - h + 56, 16, 22, (226, 60, 50), 4)
    elif style == "arab":
        h = r.randint(240, 340)
        wall = r.choice([(232, 206, 160), (222, 190, 140), (240, 224, 196)])
        p.rect(x, gy - h, w, h, wall, 5)
        p.rect(x - 6, gy - h - 16, w + 12, 18, darker(wall, 0.9), 4)
        if r.random() < 0.4:
            p.d.chord([int((x + w * 0.2) * SS), int((gy - h - 90) * SS), int((x + w * 0.8) * SS), int((gy - h + 60) * SS)],
                      180, 360, fill=(90, 150, 190), outline=INK, width=5 * SS)
    elif style == "western":
        h = r.randint(220, 300)
        wall = r.choice([(176, 128, 84), (196, 150, 104), (160, 112, 74)])
        p.rect(x, gy - h - 70, w, h + 70, wall, 5)
        for k in range(1, 6):
            p.line([(x, gy - h - 70 + k * (h + 70) / 6), (x + w, gy - h - 70 + k * (h + 70) / 6)], 2, darker(wall, 0.8), 0.3)
        sign = r.choice(["SALOON", "BANK", "HOTEL", "STORE", "SHERIFF", "BARBER"])
        p.rect(x + 16, gy - h - 50, w - 32, 46, (240, 226, 190), 4)
        p.text(sign, x + w / 2, gy - h - 27, min(34, (w - 40) / len(sign) * 1.7), (110, 60, 40))
        p.rect(x - 10, gy - 150, w + 20, 14, darker(wall, 0.7), 4)
    else:  # europe
        h = r.randint(300, 420)
        wall = r.choice([(240, 214, 176), (236, 196, 170), (214, 222, 230), (246, 236, 214), (226, 200, 150)])
        p.rect(x, gy - h, w, h, wall, 5)
        p.poly([(x - 8, gy - h), (x + 14, gy - h - 60), (x + w - 14, gy - h - 60), (x + w + 8, gy - h)], (90, 100, 120), 5)
        for k in range(int(w / 70)):
            p.rect(x + 22 + k * 70, gy - h - 48, 26, 30, (226, 230, 240), 3)
    # windows and door
    cols = max(1, int(w / 70))
    rows = max(1, int((h - 130) / 90))
    for i in range(cols):
        for j in range(rows):
            wx = x + (i + 0.5) * w / cols - 16
            wy = gy - h + 40 + j * 90
            lit = night and r.random() < 0.5
            glass = win_lit if lit else ((60, 70, 96) if night else (170, 206, 230))
            if style == "arab":
                p.d.rounded_rectangle([int(wx * SS), int(wy * SS), int((wx + 32) * SS), int((wy + 50) * SS)],
                                      radius=16 * SS, fill=glass, outline=INK, width=4 * SS)
            else:
                p.rect(wx, wy, 32, 48, glass, 4)
                if style == "europe":
                    p.rect(wx - 10, wy, 9, 48, (90, 130, 110), 3)
                    p.rect(wx + 33, wy, 9, 48, (90, 130, 110), 3)
    dx = x + w / 2 - 26
    p.rect(dx, gy - 96, 52, 96, (120, 80, 56) if style != "asia" else (150, 50, 40), 5)
    p.circ(dx + 42, gy - 48, 4, (240, 200, 70), 0)


def paint_street(sc, bg):
    style = bg.get("style") if bg.get("style") in STREET_STYLES else "europe"
    time = bg.get("time") or "day"
    gy = 780
    sky_bot = {"night": (40, 46, 84)}.get(time, (220, 236, 246))
    with sc.background(sky_bot) as p:
        sc._sky(p, time, gy)
        r = random.Random(sc.idx * 31 + 7)
        x = -40
        while x < W:
            w = r.randint(170, 260)
            _facade(p, r, x, w, gy, style, time)
            x += w + (r.randint(0, 14) if style in ("western", "arab") else 0)
        road = (196, 186, 170) if style != "western" else (206, 176, 128)
        p.rect(-10, gy, W + 20, 40, darker(road, 0.92), 5)
        p.d.rectangle([0, int((gy + 40) * SS), W * SS, H * SS], fill=road)
        if style != "western":
            for j in range(9):
                yy = gy + 60 + j * 34
                off = (j % 2) * 30
                for i in range(-1, 34):
                    xx = i * 62 + off
                    p.d.rounded_rectangle([int(xx * SS), int(yy * SS), int((xx + 52) * SS), int((yy + 24) * SS)],
                                          radius=8 * SS, outline=darker(road, 0.82), width=2 * SS)
        else:
            for i in range(14):
                yy = gy + 80 + r.randint(0, 260)
                xx = r.randint(0, W)
                p.line([(xx, yy), (xx + 60, yy)], 3, darker(road, 0.85), 0.5)
        if style in ("europe", "medieval") and time in ("night", "dusk"):
            for lx in (300, 1000, 1700):
                p.line([(lx, gy + 40), (lx, gy - 230)], 7, (50, 50, 60), 0.2)
                p.circ(lx, gy - 244, 20, (255, 226, 140), 4)


# ------------------------------------------------------------------ palace interior
def paint_palace(sc, bg):
    from .palette import color as C
    wall = C(bg.get("wall"), (232, 214, 186))
    gold = (226, 182, 72)
    gy = 760
    with sc.background(wall) as p:
        for k in range(5):
            x0 = 120 + k * 360
            p.rect(x0, 150, 240, 440, lighter(wall, 0.25), 5, gold)
            p.rect(x0 + 18, 168, 204, 404, None, 3, gold)
        for cx in (60, 1860, 540, 1380):
            p.rect(cx - 34, 80, 68, gy - 80, (246, 242, 234), 5)
            p.rect(cx - 48, 60, 96, 30, gold, 4)
            p.rect(cx - 48, gy - 30, 96, 30, gold, 4)
            for xx in (-16, 0, 16):
                p.line([(cx + xx, 100), (cx + xx, gy - 40)], 2, (214, 210, 200), 0.2)
        p.rect(820, 170, 280, 330, gold, 8)
        p.rect(844, 194, 232, 282, (160, 120, 90), 4)
        p.circ(960, 290, 50, (240, 220, 190), 4)
        p.line([(900, 420), (960, 350), (1020, 420)], 6, INK, 0.3)
        p.rect(0, 0, W, 70, darker(wall, 0.85), 0)
        p.line([(0, 70), (W, 70)], 6, gold, 0.3)
        p.line([(960, 0), (960, 70)], 4, (90, 80, 70), 0.2)
        for k in range(7):
            a = math.pi * (0.1 + 0.8 * k / 6)
            p.line([(960, 110), (960 + math.cos(a) * 110, 110 + math.sin(a) * 50)], 4, gold, 0.2)
            p.circ(960 + math.cos(a) * 110, 104 + math.sin(a) * 50, 9, (255, 236, 160), 3)
        p.ell(960, 110, 40, 22, gold, 4)
        # checkered marble floor in perspective
        p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=(240, 236, 228))
        dark = (70, 66, 74)
        rows = 7
        for j in range(rows):
            ya, yb = gy + (H - gy) * (j / rows) ** 1.4, gy + (H - gy) * ((j + 1) / rows) ** 1.4
            for i in range(-10, 11):
                if (i + j) % 2 == 0:
                    continue
                k0, k1 = 0.55 + 0.45 * (j / rows), 0.55 + 0.45 * ((j + 1) / rows)
                xa, xb = 960 + i * 120 * k0 * 1.6, 960 + (i + 1) * 120 * k0 * 1.6
                xc, xd = 960 + (i + 1) * 120 * k1 * 1.6, 960 + i * 120 * k1 * 1.6
                p.poly([(xa, ya), (xb, ya), (xc, yb), (xd, yb)], dark, 0, wob=0)
        p.line([(0, gy), (W, gy)], 6, INK, 0.3)
        for side in (-1, 1):
            x0 = 0 if side < 0 else W
            pts = [(x0, 0), (x0 - side * 300, 0), (x0 - side * 230, 400), (x0 - side * 280, gy + 120), (x0, gy + 120)]
            p.poly(pts, (170, 36, 46), 6)
            for k in range(1, 4):
                p.line([(x0 - side * 70 * k, 10), (x0 - side * 60 * k, gy + 100)], 3, (130, 24, 34), 0.5)
            p.line([(x0 - side * 300, 300), (x0 - side * 230, 400)], 8, gold, 0.3)


# ------------------------------------------------------------------ harbor, beach, underwater
def paint_harbor(sc, bg):
    time = bg.get("time") or "day"
    horizon, quay = 520, 840
    with sc.background((200, 228, 246)) as p:
        sc._sky(p, time, horizon)
        haze = (196, 214, 230) if time != "night" else (50, 60, 96)
        r = random.Random(sc.idx + 41)
        x = -20
        while x < W:
            w = r.randint(50, 110)
            h = r.randint(40, 120)
            p.d.rectangle([int(x * SS), int((horizon - h) * SS), int((x + w) * SS), int(horizon * SS)],
                          fill=darker(haze, 0.86))
            x += w
        sea = (92, 152, 200) if time != "night" else (30, 48, 86)
        p.d.rectangle([0, horizon * SS, W * SS, H * SS], fill=sea)
        for j in range(14):
            _wavy(p, horizon + 24 + j * 22, lighter(sea, 0.25), 3, 30 + j * 3, 3, phase=j)
        far_prop(p, "galleon", 420, horizon + 120, 0.42, haze, 0.25, {"flag": "red"})
        far_prop(p, "galleon", 1500, horizon + 150, 0.5, haze, 0.15, {"flip": True})
        far_prop(p, "rowboat", 980, horizon + 230, 0.5, haze, 0.1)
        wood = (150, 104, 66)
        p.d.rectangle([0, quay * SS, W * SS, H * SS], fill=wood)
        for k in range(1, 6):
            yy = quay + k * (H - quay) / 6
            p.line([(0, yy), (W, yy)], 3, darker(wood, 0.75), 0.4)
        p.line([(0, quay), (W, quay)], 7, INK, 0.3)
        for bx in (220, 980, 1700):
            p.rect(bx - 18, quay - 34, 36, 40, (60, 60, 70), 4)
            p.rect(bx - 24, quay - 40, 48, 12, (60, 60, 70), 3)
        far_prop(p, "crate", 1480, quay + 4, 0.55, haze, 0.0)
        far_prop(p, "keg", 1590, quay + 4, 0.5, haze, 0.0)


def paint_beach(sc, bg):
    time = bg.get("time") or "day"
    horizon, shore = 500, 690
    with sc.background((200, 228, 246)) as p:
        sc._sky(p, time, horizon)
        sea = (70, 160, 206) if time != "night" else (30, 48, 86)
        p.im.paste(Image.new("RGB", (W * SS, (shore - horizon) * SS + SS), sea), (0, horizon * SS))
        for j in range(8):
            _wavy(p, horizon + 20 + j * 22, lighter(sea, 0.3), 3, 40, 3, phase=j * 1.3)
        sand = (240, 214, 150) if time != "night" else (120, 110, 96)
        p.d.rectangle([0, shore * SS, W * SS, H * SS], fill=sand)
        pts = [(x, shore + 10 * math.sin(x / 90)) for x in range(-20, W + 40, 20)]
        p.poly(pts + [(W + 20, shore - 20), (-20, shore - 20)], (250, 250, 252), 0, wob=0.2)
        p.line(pts, 4, (210, 230, 240), 0.2)
        r = random.Random(sc.idx + 43)
        for _ in range(20):
            x, y = r.randint(0, W), r.randint(shore + 60, H - 10)
            p.ell(x, y, 8, 5, darker(sand, 0.85), 0)
        far_prop(p, "palm_tree", 120, H - 60, 0.95, (255, 255, 255), 0.0)
        far_prop(p, "palm_tree", 1800, H - 90, 0.8, (255, 255, 255), 0.0, {"flip": True})
        far_prop(p, "sailboat", 1250, horizon + 40, 0.3, (200, 228, 246), 0.3)


def paint_underwater(sc, bg):
    from .core import gradient
    floor = 890
    with sc.background((30, 90, 150), noise=True) as p:
        p.im.paste(gradient((W * SS, H * SS), (70, 160, 210), (12, 40, 86)), (0, 0))
        for k in range(6):
            x = 200 + k * 320
            p.poly([(x, 0), (x + 90, 0), (x + 260, floor), (x + 160, floor)], (96, 176, 220), 0, wob=0)
        r = random.Random(sc.idx + 47)
        sand = (196, 176, 130)
        pts = [(x, floor + 20 * math.sin(x / 160 + 1)) for x in range(-20, W + 40, 30)]
        p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], sand, 5, INK, 0.3)
        for name, x, s, k in (("seaweed", 120, 1.1, {}), ("coral", 330, 0.9, {}), ("seaweed", 1650, 0.9, {}),
                              ("coral", 1810, 0.8, {"color": None}), ("rocks", 1450, 0.6, {})):
            far_prop(p, name, x, floor + 30, s, (12, 40, 86), 0.12)
        for _ in range(4):
            far_prop(p, "fish", r.randint(300, 1600), r.randint(200, 600), r.uniform(0.35, 0.6), (30, 90, 150), 0.45,
                     {"flip": r.random() < 0.5})
        for _ in range(28):
            x, y = r.randint(0, W), r.randint(60, floor - 40)
            p.circ(x, y, r.choice((5, 7, 10)), None, 2.5, (200, 236, 250))


# ------------------------------------------------------------------ space, jungle, mountains, trench
def paint_space(sc, bg):
    from .core import gradient
    with sc.background((12, 14, 34), noise=False) as p:
        p.im.paste(gradient((W * SS, H * SS), (10, 12, 32), (30, 26, 70)), (0, 0))
        r = random.Random(sc.idx + 53)
        for _ in range(160):
            p.circ(r.randint(0, W), r.randint(0, H), r.choice((1.5, 2, 2, 3, 4)), (250, 246, 220), 0)
        p.circ(1700, 1240, 520, (70, 130, 210), 8, (20, 30, 60))
        for cx, cy, rx, ry in ((1480, 850, 120, 60), (1760, 790, 90, 50), (1600, 960, 140, 50)):
            p.blob(cx, cy, rx, ry, (110, 180, 100), 0, seed=cx)
        p.circ(1700, 1240, 528, None, 14, (140, 190, 250))
        p.circ(260, 220, 90, (226, 226, 230), 6)
        for cx, cy, rr in ((230, 200, 18), (290, 250, 12), (250, 270, 9)):
            p.circ(cx, cy, rr, (196, 196, 204), 3)


def paint_jungle(sc, bg):
    time = bg.get("time") or "day"
    gy = 820
    with sc.background((150, 200, 150)) as p:
        sc._sky(p, time, 600)
        r = random.Random(sc.idx + 59)
        for k, col in enumerate(((84, 140, 80), (62, 120, 66), (44, 100, 56))):
            for _ in range(26):
                x = r.randint(-60, W + 60)
                y = r.randint(200 + k * 120, 520 + k * 120)
                p.circ(x, y, r.randint(70, 140), col, 0)
        for x in (180, 640, 1180, 1620):
            p.rect(x - 22, 200, 44, gy - 200, (110, 80, 54), 5)
        for _ in range(9):
            x = r.randint(0, W)
            pts = [(x + 14 * math.sin(t / 60), t) for t in range(0, r.randint(200, 500), 20)]
            p.line(pts, 5, (60, 110, 60), 0.3)
        p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=(70, 110, 56))
        p.line([(0, gy), (W, gy)], 5, INK, 0.4)
        for side in (0, 1):
            for j in range(6):
                cx = (60 if side == 0 else W - 60) + (j % 3) * (50 if side == 0 else -50)
                cy = 160 + j * 140
                a = (-0.5 if side == 0 else math.pi + 0.5) + r.uniform(-0.4, 0.4)
                pts = []
                for t in range(9):
                    u = t / 8
                    pts.append((cx + math.cos(a) * 260 * u, cy + math.sin(a) * 260 * u + 60 * u * u))
                left = [(px - math.sin(a) * 60 * math.sin(math.pi * u), py + math.cos(a) * 60 * math.sin(math.pi * u))
                        for (px, py), u in zip(pts, [t / 8 for t in range(9)])]
                right = [(px + math.sin(a) * 60 * math.sin(math.pi * u), py - math.cos(a) * 60 * math.sin(math.pi * u))
                         for (px, py), u in zip(pts, [t / 8 for t in range(9)])]
                p.poly(left + right[::-1], (50, 130, 70), 4, INK, 0.3)
                p.line(pts, 3, (30, 90, 50), 0.2)


def paint_mountains(sc, bg):
    time = bg.get("time") or "day"
    gy = 760
    with sc.background((200, 226, 244)) as p:
        sc._sky(p, time, gy)
        r = random.Random(sc.idx + 61)
        night = time == "night"
        for k, (col, base, hmin, hmax) in enumerate((((176, 190, 214), gy - 60, 260, 420),
                                                       ((136, 150, 176), gy, 180, 320))):
            col = darker(col, 0.45) if night else col
            x = -200
            while x < W + 200:
                w, h = r.randint(260, 420), r.randint(hmin, hmax)
                p.poly([(x - w / 2, base + 4), (x, base - h), (x + w / 2, base + 4)], col, 4, darker(col, 0.7), 0.4)
                sw = w * 0.16
                p.poly([(x - sw, base - h * 0.78), (x, base - h), (x + sw, base - h * 0.78), (x + sw * 0.3, base - h * 0.72),
                        (x - sw * 0.3, base - h * 0.74)], (250, 250, 255) if not night else (180, 186, 210), 0, wob=0.2)
                x += w * 0.6
        sc._ground(p, None, gy, (120, 170, 96) if not night else (40, 66, 46), tuft=(90, 140, 76))
        for x in (90, 240, 1650, 1820):
            far_prop(p, "pine_tree", x, gy + r.randint(20, 90), r.uniform(0.7, 1.0), (200, 226, 244), 0.05)


def paint_trench(sc, bg):
    gy = 520
    with sc.background((170, 168, 162)) as p:
        sc._sky(p, "storm", gy)
        mud = (122, 100, 74)
        p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=mud)
        for k in range(8):
            yy = gy + 30 + k * 40
            p.rect(-10, yy, W + 20, 34, (146, 112, 76), 3)
        for x in range(60, W, 260):
            p.rect(x, gy, 24, 360, (110, 80, 54), 4)
        p.d.rectangle([0, 880 * SS, W * SS, H * SS], fill=darker(mud, 0.8))
        for i in range(12):
            p.rect(i * 170 - 20, 880, 150, 26, (150, 116, 80), 3)
        far_prop(p, "sandbags", 360, gy + 6, 0.8, (170, 168, 162), 0.1)
        far_prop(p, "sandbags", 1500, gy + 6, 0.8, (170, 168, 162), 0.1)
        far_prop(p, "barbed_wire", 960, gy - 6, 0.9, (170, 168, 162), 0.25)


PAINTERS = {"street": paint_street, "palace": paint_palace, "harbor": paint_harbor, "beach": paint_beach,
            "underwater": paint_underwater, "space": paint_space, "jungle": paint_jungle,
            "mountains": paint_mountains, "trench": paint_trench}


def skyline_landmarks(p, key, gy, time):
    haze = (196, 210, 228) if time != "night" else (44, 52, 86)
    for name, x, s in SKYLINES.get(key, []):
        far_prop(p, name, x, gy + 2, s, haze, 0.15 if time != "night" else 0.5)
