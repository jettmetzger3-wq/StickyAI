"""Scene: a background plus animated layers, rendered frame by frame.

Each layer is drawn once at 2x, downsampled with LANCZOS (premultiplied alpha), cropped to its bounding
box, and then composited per frame with its enter / idle / move / exit animation. The camera is a float
affine transform (bilinear), clamped so a zoom never shows black edges.
"""
import math
import random
from contextlib import contextmanager

import numpy as np
from PIL import Image, ImageOps

from .doodle import W, H, SS
from .palette import INK, PAPER, SEA, SEA2, LAND, RED, NAVY, WHITE, SUN, DARK, color as to_color, darker
from .pen import Pen
from .geo import View, geom_polys
from .timing import WordTimer, LEAD, TAIL
from .puppet import Puppet

FPS = 30


def ease_out_back(t, s=1.9):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = min(max(t, 0), 1)
    return t * t * (3 - 2 * t)


ENTER_ALIASES = {"slide_left": "slide_l", "slide_right": "slide_r", "slide_up": "slide_u", "slide_down": "slide_d",
                 "wipe_right": "wipe_r", "wipe_left": "wipe_l", "wipe_up": "wipe_u", "wipe_down": "wipe_d",
                 "none": None, "": None, None: None}
AUTO_SFX = {"pop": "pop", "drop": "pop", "grow": "pop", "slide_l": "whoosh", "slide_r": "whoosh", "slide_u": "whoosh",
            "slide_d": "whoosh", "wipe_r": "swish", "wipe_l": "swish", "wipe_u": "swish", "wipe_d": "swish"}


def norm_enter(e):
    if e in ENTER_ALIASES:
        return ENTER_ALIASES[e]
    return e


def motion_blur(img, vx, vy, n=7):
    """Directional blur over the distance the camera moved this frame (whip pans)."""
    length = min(math.hypot(vx, vy), 90)
    ux, uy = vx / (math.hypot(vx, vy) or 1), vy / (math.hypot(vx, vy) or 1)
    a = np.asarray(img, dtype=np.uint16)
    acc = np.zeros(a.shape, dtype=np.uint32)
    for k in range(n):
        f = (k / (n - 1) - 0.5) * length
        acc += np.roll(a, (int(round(f * uy)), int(round(f * ux))), axis=(0, 1))
    return Image.fromarray((acc // n).astype(np.uint8))


SKIES = {  # time of day -> (top, bottom) sky colors
    "day": ((120, 180, 232), (214, 236, 250)), "dawn": ((250, 186, 140), (255, 232, 196)),
    "dusk": ((86, 74, 140), (246, 160, 120)), "night": ((18, 24, 56), (52, 60, 104)),
    "storm": ((92, 98, 110), (160, 164, 170)),
}


def gradient(size, top, bottom):
    g = Image.linear_gradient("L").resize(size)
    return ImageOps.colorize(g, top, bottom)


class Scene:
    def __init__(self, idx, dur, mood, text, timer=None, lead=LEAD, tail=TAIL):
        self.idx, self.dur, self.mood, self.text = idx, float(dur), mood, text
        self.timer = timer or WordTimer(text, dur, lead, tail)
        self.bg = None
        self.layers = []
        self.cam = dict(z0=1.0, z1=1.035, cx0=W / 2, cy0=H / 2, cx1=W / 2, cy1=H / 2)
        self.shots = []          # camera shots: dict(t, z, cx, cy, move) in seconds, sorted
        self.sfx = []
        self.seed = 1000 + idx * 17
        self.view = None
        self.warnings = []

    # ---------------- time helpers ----------------
    def w(self, word, nth=0):
        return self.timer.frac(word, nth, default=0.0)

    def T(self, at):
        return at * self.dur

    def warn(self, msg):
        self.warnings.append(f"scene {self.idx}: {msg}")

    # ---------------- backgrounds ----------------
    @contextmanager
    def background(self, color=PAPER, noise=True):
        p = Pen(self.seed, rgba=False, bg=color)
        yield p
        im = p.im.resize((W, H), Image.LANCZOS)
        if noise:
            n = Image.effect_noise((W, H), 12).convert("RGB")
            im = Image.blend(im, n, 0.03)
        self.bg = im

    def bg_paper(self, col=PAPER):
        with self.background(col):
            pass

    def bg_sunburst(self, col=PAPER, ray=SUN):
        with self.background(col) as p:
            p.sunburst(960, 520, col=ray)

    def bg_ground(self, sky=(198, 228, 245), gnd=(222, 205, 160), gy=860, clouds=True):
        with self.background(sky) as p:
            p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=gnd)
            p.line([(0, gy), (W, gy)], 6, INK, 0.5)
            if clouds:
                p.cloud(300, 180, 0.9)
                p.cloud(1550, 140, 0.7)
        return gy

    def bg_sea(self, sky=(200, 228, 246), sea=SEA, horizon=520, clouds=True):
        with self.background(sky) as p:
            p.d.rectangle([0, horizon * SS, W * SS, H * SS], fill=sea)
            r = random.Random(self.idx)
            for i in range(30):
                x, y = r.randint(0, W), r.randint(horizon + 20, H)
                p.line([(x, y), (x + 30, y - 7), (x + 60, y)], 5, darker(sea, 0.8), 0.5)
            if clouds:
                p.cloud(350, 160, 0.8)
                p.cloud(1500, 210, 0.6)
        return horizon

    def bg_night(self, sky=(30, 36, 70), gnd=(40, 44, 60), gy=880):
        with self.background(sky) as p:
            r = random.Random(self.idx + 5)
            for i in range(70):
                x, y = r.randint(0, W), r.randint(0, gy - 120)
                p.circ(x, y, r.choice((2, 2, 3, 4)), (250, 245, 210), 0)
            p.circ(1600, 190, 70, (250, 244, 214), 0)
            p.circ(1630, 175, 62, sky, 0)
            p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=gnd)

    def bg_dark(self, col=DARK):
        with self.background(col):
            pass

    # ---------------- painted backgrounds (sky gradient, layered scenery) ----------------
    def _sky(self, p, time, horizon):
        top, bot = SKIES.get(time, SKIES["day"])
        p.im.paste(gradient((W * SS, int(horizon * SS)), top, bot), (0, 0))
        r = random.Random(self.idx + 7)
        if time == "night":
            for _ in range(60):
                p.circ(r.randint(0, W), r.randint(0, int(horizon * 0.8)), r.choice((2, 2, 3)), (250, 245, 210), 0)
            p.circ(1620, 170, 58, (250, 244, 214), 0)
        elif time == "dusk" or time == "dawn":
            p.circ(1500, int(horizon) - 40, 80, (255, 214, 140), 0)
        elif time != "storm":
            for k in range(3):
                p.cloud(r.randint(150, 1750), r.randint(90, int(max(140, horizon * 0.45))), r.uniform(0.5, 0.9))
        else:
            for k in range(5):
                p.cloud(r.randint(100, 1800), r.randint(60, 260), r.uniform(0.8, 1.3), (120, 124, 132))

    def _ground(self, p, top, gy, col, tuft=None, n=160):
        p.im.paste(gradient((W * SS, int((H - gy) * SS) + SS), col, darker(col, 0.82)), (0, int(gy * SS)))
        r = random.Random(self.idx + 3)
        if tuft:
            for _ in range(n):
                x, y = r.randint(0, W), r.randint(int(gy) + 8, H - 4)
                k = 0.6 + (y - gy) / (H - gy)
                p.line([(x, y), (x - 4 * k, y - 12 * k)], 3, tuft, 0.3)
                p.line([(x + 6 * k, y), (x + 8 * k, y - 14 * k)], 3, tuft, 0.3)

    def _treeline(self, p, gy, col=(88, 140, 78)):
        r = random.Random(self.idx + 11)
        x = -40
        while x < W + 60:
            rad = r.randint(34, 70)
            p.circ(x, gy - rad * 0.55, rad, col, 0)
            x += r.randint(40, 80)
        p.d.rectangle([0, int((gy - 18) * SS), W * SS, int(gy * SS) + 2], fill=col)

    def bg_field(self, time="day", gy=640, grass=(112, 168, 84)):
        """Sky, a tree line on the horizon and a grassy field (like the battlefield shots in history videos)."""
        with self.background(SKIES.get(time, SKIES["day"])[1], noise=True) as p:
            self._sky(p, time, gy)
            self._treeline(p, gy + 4, darker(grass, 0.7) if time != "night" else (30, 52, 40))
            self._ground(p, None, gy, grass if time != "night" else (40, 66, 46), tuft=darker(grass, 0.75))
        return gy

    def bg_hills(self, time="day", gy=700):
        with self.background(SKIES.get(time, SKIES["day"])[1]) as p:
            self._sky(p, time, gy)
            r = random.Random(self.idx + 5)
            for k, (col, base, amp) in enumerate((((150, 190, 120), gy - 120, 70), ((120, 172, 96), gy - 40, 60),
                                                  ((96, 152, 78), gy + 60, 50))):
                ph = r.uniform(0, 6)
                pts = [(x, base - amp * (0.5 + 0.5 * math.sin(x / (260 + 90 * k) + ph))) for x in range(-20, W + 40, 40)]
                p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], col, 0, col, 0.2)
            for _ in range(5):
                p.tree(r.randint(80, W - 80), gy + r.randint(60, 200), r.uniform(0.5, 0.8))

    def bg_desert(self, time="day", gy=700):
        with self.background((250, 226, 170)) as p:
            self._sky(p, time if time != "day" else "dawn", gy)
            p.circ(1520, 230, 90, (255, 236, 160), 0)
            r = random.Random(self.idx + 9)
            for k, (col, base) in enumerate((((236, 200, 130), gy - 30), ((226, 186, 112), gy + 80), ((214, 170, 98), gy + 220))):
                ph = r.uniform(0, 6)
                pts = [(x, base - 50 * math.sin(x / 300 + ph)) for x in range(-20, W + 40, 40)]
                p.poly(pts + [(W + 20, H + 10), (-20, H + 10)], col, 0, col, 0.2)

    def bg_snow(self, time="day", gy=700):
        with self.background((226, 236, 246)) as p:
            self._sky(p, "storm" if time == "storm" else ("night" if time == "night" else "day"), gy)
            self._treeline(p, gy + 4, (60, 92, 86))
            self._ground(p, None, gy, (244, 248, 252))
            r = random.Random(self.idx + 13)
            for _ in range(140):
                p.circ(r.randint(0, W), r.randint(0, H), r.choice((2, 3, 4)), WHITE, 0)

    def bg_city(self, time="day", gy=820, skyline=None):
        """A city skyline. skyline = a city key from places.SKYLINES (paris, london...) adds its landmarks."""
        from .places import skyline_landmarks
        with self.background(SKIES.get(time, SKIES["day"])[1]) as p:
            self._sky(p, time, gy)
            r = random.Random(self.idx + 17)
            x = -20
            far = (150, 160, 182) if time != "night" else (40, 46, 74)
            near = (108, 116, 140) if time != "night" else (28, 32, 56)
            rows = ((far, 160, 380, 70), (near, 120, 300, 90)) if not skyline else \
                ((far, 120, 260, 70), (near, 90, 190, 90))
            for col, hmin, hmax, wmin in rows:
                x = -30
                while x < W + 40:
                    w_, h_ = r.randint(wmin, wmin + 90), r.randint(hmin, hmax)
                    p.d.rectangle([int(x * SS), int((gy - h_) * SS), int((x + w_) * SS), int(gy * SS)], fill=col)
                    if col == near:
                        lit = (255, 226, 140) if time == "night" else (196, 210, 228)
                        for wy in range(int(gy - h_ + 20), int(gy - 20), 34):
                            for wx in range(int(x + 12), int(x + w_ - 16), 26):
                                if r.random() < (0.55 if time == "night" else 0.9):
                                    p.d.rectangle([wx * SS, wy * SS, (wx + 12) * SS, (wy + 16) * SS], fill=lit)
                    x += w_ + r.randint(-10, 12)
            if skyline:
                skyline_landmarks(p, skyline, gy, time)
            self._ground(p, None, gy, (150, 146, 140))

    def bg_interior(self, wall=(236, 222, 196), floor=(176, 132, 92), gy=780):
        with self.background(wall) as p:
            p.d.rectangle([0, int((gy - 170) * SS), W * SS, int(gy * SS)], fill=darker(wall, 0.9))
            p.line([(0, gy - 170), (W, gy - 170)], 5, darker(wall, 0.7), 0.4)
            p.im.paste(gradient((W * SS, int((H - gy) * SS) + SS), floor, darker(floor, 0.8)), (0, int(gy * SS)))
            for k in range(-2, 14):
                x0 = 160 * k
                p.line([(x0 + 300, gy), (x0 - 200, H)], 3, darker(floor, 0.75), 0.3)
            p.line([(0, gy), (W, gy)], 6, INK, 0.4)
            p.rect(1380, 170, 340, 260, (170, 214, 240), 8, (110, 76, 50))
            p.line([(1550, 170), (1550, 430)], 6, (110, 76, 50), 0.3)
            p.line([(1380, 300), (1720, 300)], 6, (110, 76, 50), 0.3)

    def bg_battlefield(self, time="storm", gy=700):
        with self.background((170, 166, 156)) as p:
            self._sky(p, "storm" if time == "day" else time, gy)
            self._ground(p, None, gy, (128, 110, 82), tuft=(98, 84, 62), n=90)
            r = random.Random(self.idx + 19)
            for _ in range(7):
                x, y = r.randint(60, W - 60), r.randint(gy - 90, gy + 30)
                for k in range(4):
                    p.circ(x + r.randint(-60, 60), y - k * 40, r.randint(40, 80), (196, 192, 186), 0)
            for _ in range(5):
                x, y = r.randint(80, W - 80), r.randint(gy + 80, H - 60)
                p.ell(x, y, 90, 22, (98, 84, 62), 0)

    # ---------------- layers ----------------
    def _finish(self, p):
        im = p.im.convert("RGBa").resize((W, H), Image.LANCZOS).convert("RGBA")
        bb = im.getchannel("A").getbbox()
        if not bb:
            return None, (0, 0)
        return im.crop(bb), (bb[0], bb[1])

    @contextmanager
    def layer(self, enter="pop", at=0.0, edur=0.38, idle=None, anchor="center", exit_at=None,
              sfx="auto", move=None, z=0):
        p = Pen(self.seed + len(self.layers) * 7 + 3, rgba=True)
        yield p
        img, off = self._finish(p)
        if img is None:
            return
        self._add(img, off, enter, at, edur, idle, anchor, exit_at, sfx, move, z, None)

    def _add(self, img, off, enter, at, edur, idle, anchor, exit_at, sfx, move, z, alt):
        enter = norm_enter(enter)
        w_, h_ = img.size
        if anchor == "center":
            ax, ay = off[0] + w_ / 2, off[1] + h_ / 2
        elif anchor == "bottom":
            ax, ay = off[0] + w_ / 2, off[1] + h_
        else:
            ax, ay = anchor
        L = dict(img=img, alt=alt, ox=off[0], oy=off[1], ax=ax, ay=ay, enter=enter, at=self.T(at),
                 edur=max(float(edur or 0), 0.0), idle=idle, exit=self.T(exit_at) if exit_at is not None else None,
                 move=move, z=z, phase=random.Random(len(self.layers) + self.idx).uniform(0, 6))
        self.layers.append(L)
        if sfx == "auto":
            sfx = AUTO_SFX.get(enter)
            if self.mood == "somber" and sfx in ("pop",):
                sfx = None
        if sfx and enter:
            self.sfx.append((self.T(at), sfx))

    def char(self, x, y, s=1.0, kind="japan", enter="pop", at=0.0, idle="bob", exit_at=None, move=None, z=1,
             sfx="auto", actions=(), talk=(), life=True, **pose):
        """An animated stickman (see puppet.py): it breathes, blinks, glances, talks and does `actions`."""
        cx = min(max(x, 130 * s), W - 130 * s)
        cy = min(max(y, 375 * s + 12), H - 15)
        if abs(cx - x) > 1 or abs(cy - y) > 1:
            self.warn(f"character '{kind}' moved on-screen ({x:.0f},{y:.0f}) -> ({cx:.0f},{cy:.0f})")
        n = len(self.layers)
        pz = Puppet(cx, cy, s, dict(pose, kind=kind), actions=actions, talk=talk, life=life,
                    seed=self.seed + n * 31, mood=self.mood)
        img, off = pz.image(pz.state(0.0)[0], kind, self.seed + 991)
        if img is None:
            self.warn(f"character '{kind}' is completely off-screen")
            return
        self._add(img, (cx + off[0], cy + off[1]), enter, at, 0.42, idle if idle not in ("bob",) else None,
                  (cx, cy), exit_at, sfx, move, z, None)
        L = self.layers[-1]
        L.update(puppet=pz, kind=kind, pseed=self.seed + 991)
        return L

    def shot(self, at, zoom=1.0, center=None, move="cut"):
        """A camera shot from `at` (seconds): cut / pan / whip to `center` at `zoom`, then a slow push-in."""
        cx, cy = center or (W / 2, H / 2)
        self.shots.append(dict(t=max(0.0, float(at)), z=max(1.0, min(float(zoom), 3.0)), cx=float(cx), cy=float(cy),
                               move=move if move in ("cut", "pan", "whip") else "cut"))
        self.shots.sort(key=lambda d: d["t"])

    # ---------------- camera ----------------
    MOVE_TIME = {"cut": 0.0, "pan": 0.8, "whip": 0.3}

    def _base_cam(self, t):
        c = self.cam
        q = ease_io(t / max(self.dur, 1e-3))
        return (max(1.0, c["z0"] + (c["z1"] - c["z0"]) * q), c["cx0"] + (c["cx1"] - c["cx0"]) * q,
                c["cy0"] + (c["cy1"] - c["cy0"]) * q)

    def _shot_cam(self, i, t):
        sh = self.shots[i]
        td = self.MOVE_TIME[sh["move"]]
        push = 1 + min(0.06, 0.015 * max(0.0, t - sh["t"] - td))      # slow push-in while the shot holds
        target = (sh["z"] * push, sh["cx"], sh["cy"])
        if td <= 0 or t >= sh["t"] + td:
            return target
        start = self._base_cam(sh["t"]) if i == 0 else self._shot_cam(i - 1, sh["t"])
        q = ease_io((t - sh["t"]) / td)
        return tuple(a + (b - a) * q for a, b in zip(start, target))

    def cam_at(self, t):
        """(zoom, center x, center y) at time t, clamped so we never see past the frame edge."""
        i = -1
        for k, sh in enumerate(self.shots):
            if sh["t"] <= t:
                i = k
        z, cx, cy = self._base_cam(t) if i < 0 else self._shot_cam(i, t)
        z = max(1.0, z)
        hw, hh = W / (2 * z), H / (2 * z)
        return z, min(max(cx, hw), W - hw), min(max(cy, hh), H - hh)

    def label(self, text, x, y, size=70, col=INK, f="bold", enter="pop", at=0.0, stroke=9, scol=WHITE,
              idle=None, exit_at=None, sfx="auto", z=3, anchor="mm", move=None, edur=0.38):
        with self.layer(enter, at, edur=edur, idle=idle, exit_at=exit_at, sfx=sfx, z=z, move=move) as p:
            p.text(text, x, y, size, col, anchor=anchor, stroke=stroke, scol=scol, f=f)

    def camera(self, z0=1.0, z1=1.04, c0=None, c1=None):
        c0 = c0 or (W / 2, H / 2)
        c1 = c1 or c0
        self.cam = dict(z0=z0, z1=z1, cx0=c0[0], cy0=c0[1], cx1=c1[0], cy1=c1[1])

    # ---------------- maps ----------------
    def map_bg(self, view, base_terr=(), sea=(156, 205, 230), land=(238, 214, 160), labels=(), style="paper"):
        """style "paper": light doodle map. style "dark": navy sea, dark land, white borders (like big history
        channels' maps)."""
        from . import geo
        self.view = view
        self.map_style = style
        dark = style == "dark"
        border = (235, 238, 244) if dark else (90, 80, 70)
        with self.background(sea, noise=not dark) as p:
            r = random.Random(self.idx)
            if dark:
                tex = Image.effect_noise((W * SS // 4, H * SS // 4), 40).convert("L").resize((W * SS, H * SS), Image.BICUBIC)
                p.im.paste(Image.blend(Image.new("RGB", p.im.size, sea), ImageOps.colorize(tex, darker(sea, 0.7), sea), 0.6))
            else:
                for i in range(40):
                    x, y = r.randint(0, W), r.randint(0, H)
                    p.line([(x, y), (x + 22, y - 6), (x + 44, y)], 4, darker(sea, 0.86), 0.5)
            bx = view.bbox()
            for name, g in geo.COUNTRIES.items():
                minx, miny, maxx, maxy = g.bounds
                if maxy < bx[1] or miny > bx[3]:
                    continue
                gg = view.in_view(g)
                if gg is None:
                    continue
                for poly in geom_polys(gg.simplify(0.03)):
                    pts = [view.xy(*c) for c in poly.exterior.coords]
                    if len(pts) > 2:
                        p.poly(pts, land, 3 if not dark else 2.5, border, 0.35)
            for g, col in base_terr:
                self._draw_terr(p, view.in_view(g), col, (245, 245, 250) if dark else (120, 30, 30))
            for lab in labels:
                self._map_label(p, *lab)

    def _draw_terr(self, p, g, col, outline=(120, 30, 30)):
        if g is None:
            return
        for poly in geom_polys(g.simplify(0.03)):
            pts = [self.view.xy(*c) for c in poly.exterior.coords]
            if len(pts) > 2:
                p.poly(pts, col, 3.5, outline, 0.35)

    def _map_label(self, p, text, lon, lat, size=40, col=(70, 60, 50), f="bold"):
        x, y = self.view.xy(lon, lat)
        if getattr(self, "map_style", "paper") == "dark":
            p.text(text, x, y, size, (240, 242, 248), stroke=6, scol=(20, 24, 40), f=f)
        else:
            p.text(text, x, y, size, col, stroke=6, scol=(255, 250, 240), f=f)

    def terr(self, g, col=RED, enter="wipe_r", at=0.1, edur=0.9, sfx="auto", outline=(120, 30, 30), exit_at=None):
        if self.view is None or g is None:
            return
        with self.layer(enter, at, edur=edur, sfx=sfx, z=0, exit_at=exit_at) as p:
            self._draw_terr(p, self.view.in_view(g), col, outline)

    def city(self, name, lon, lat, at=0.1, size=40, dx=0, dy=-44, dot=True, col=INK, enter="pop", exit_at=None):
        x, y = self.view.xy(lon, lat)
        if not (-50 <= x <= W + 50 and -50 <= y <= H + 50):
            self.warn(f"city '{name}' is outside the map view")
        dark = getattr(self, "map_style", "paper") == "dark"
        light = sum(to_color(col, INK)[:3]) > 600 if not isinstance(col, tuple) else sum(col[:3]) > 600
        with self.layer(enter, at, z=2, exit_at=exit_at) as p:
            if dot:
                p.circ(x, y, 11, WHITE, 5, (20, 24, 40) if dark else INK)
                p.circ(x, y, 5, (20, 24, 40) if dark and light else col, 0)
            if name:
                if dark or light:
                    p.text(name, x + dx, y + dy, size, WHITE, stroke=7, scol=(20, 24, 40))
                else:
                    p.text(name, x + dx, y + dy, size, col, stroke=7, scol=WHITE)

    def ll(self, lon, lat):
        return self.view.xy(lon, lat)

    def arrow(self, pts, col=RED, w=14, at=0.1, edur=0.7, enter="wipe_r", head=True, z=2, curve=0.0, exit_at=None,
              sfx="auto"):
        pts = [tuple(p) for p in pts]
        if len(pts) == 2 and curve:
            (x1, y1), (x2, y2) = pts
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            nx, ny = -(y2 - y1), (x2 - x1)
            n = math.hypot(nx, ny) or 1
            cx, cy = mx + nx / n * curve, my + ny / n * curve
            pts = [((1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t * t * x2, (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t * t * y2)
                   for t in [i / 24 for i in range(25)]]
        if enter in ("wipe_r", "wipe_right", "wipe_l", "wipe_left") and len(pts) >= 2:
            # wipe in the direction the arrow travels
            enter = "wipe_r" if pts[-1][0] >= pts[0][0] else "wipe_l"
            if abs(pts[-1][1] - pts[0][1]) > abs(pts[-1][0] - pts[0][0]) * 1.5:
                enter = "wipe_d" if pts[-1][1] > pts[0][1] else "wipe_u"
        with self.layer(enter, at, edur=edur, z=z, exit_at=exit_at, sfx=sfx) as p:
            p.line(pts, w + 8, WHITE, 0.4)
            p.line(pts, w, col, 0.4)
            if head and len(pts) >= 2:
                (xa, ya), (xb, yb) = pts[-2], pts[-1]
                a = math.atan2(yb - ya, xb - xa)
                L = w * 3.2
                tri = [(xb + math.cos(a) * L * 0.4, yb + math.sin(a) * L * 0.4),
                       (xb + math.cos(a + 2.5) * L, yb + math.sin(a + 2.5) * L),
                       (xb + math.cos(a - 2.5) * L, yb + math.sin(a - 2.5) * L)]
                p.poly(tri, col, 4, WHITE, 0.3)

    # ---------------- render ----------------
    def render_frames(self, nframes, captions=()):
        for fi in range(nframes):
            yield self.render_at(fi / FPS, captions)

    def render_at(self, t, captions=()):
        if self.bg is None:
            self.bg_paper()
        layers = sorted(self.layers, key=lambda L: L["z"])
        c = self.cam
        fr = self.bg.copy()
        for L in layers:
            if t < L["at"]:
                continue
            pz = L.get("puppet")
            if pz is not None:
                pose, pdx, pdy, rot = pz.state(t)
                img, off = pz.image(pose, L["kind"], L["pseed"], rot)
                if img is None:
                    continue
                L = dict(L, ox=pz.x + pdx + off[0], oy=pz.y + pdy + off[1], ax=pz.x + pdx, ay=pz.y + pdy)
            else:
                img = L["img"]
                if L["alt"] is not None and ((t + L["phase"]) % 3.4) < 0.12:
                    img = L["alt"]
            x, y = L["ox"], L["oy"]
            p = min(1.0, (t - L["at"]) / L["edur"]) if L["edur"] > 0 else 1
            scale, alpha = 1.0, 1.0
            e = L["enter"]
            crop = None
            if p < 1:
                if e in ("pop", "drop"):
                    scale = max(0.02, ease_out_back(p))
                    if e == "drop":
                        y -= (1 - ease_out(p)) * 120
                elif e == "grow":
                    scale = max(0.02, ease_out(p))
                elif e == "fade":
                    alpha = ease_io(p)
                elif e == "slide_l":
                    x -= (1 - ease_out(p)) * (L["ox"] + img.width + 60)
                elif e == "slide_r":
                    x += (1 - ease_out(p)) * (W - L["ox"] + 60)
                elif e == "slide_u":
                    y += (1 - ease_out(p)) * (H - L["oy"] + 60)
                elif e == "slide_d":
                    y -= (1 - ease_out(p)) * (L["oy"] + img.height + 60)
                elif e == "wipe_r":
                    crop = ("r", ease_io(p))
                elif e == "wipe_l":
                    crop = ("l", ease_io(p))
                elif e == "wipe_u":
                    crop = ("u", ease_io(p))
                elif e == "wipe_d":
                    crop = ("d", ease_io(p))
            if L["exit"] is not None and t >= L["exit"]:
                q = (t - L["exit"]) / 0.35
                if q >= 1:
                    continue
                alpha *= 1 - ease_io(q)
            if L["move"]:
                dx, dy, m0, m1 = L["move"]
                q = ease_io((t - self.T(m0)) / max(self.T(m1) - self.T(m0), 1e-3))
                x += dx * q
                y += dy * q
            idle = L["idle"]
            if idle == "bob":
                y += 5 * math.sin(2 * math.pi * t / 1.5 + L["phase"])
            elif idle == "float":
                y += 9 * math.sin(2 * math.pi * t / 3.0 + L["phase"])
            elif idle == "shake":
                if int(t * 15) % 2:
                    x += 3
            elif idle == "pulse":
                scale *= 1 + 0.035 * math.sin(2 * math.pi * t / 1.2 + L["phase"])
            elif idle == "drift":
                x += 14 * t
            elif idle == "nudge" and L.get("nudge"):
                ux, uy = L["nudge"]
                k = 12 * (0.5 + 0.5 * math.sin(2 * math.pi * 1.8 * t + L["phase"]))
                x += ux * k
                y += uy * k
            if crop:
                d, f = crop
                iw, ih = img.size
                if d == "r":
                    img = img.crop((0, 0, max(1, int(iw * f)), ih))
                elif d == "l":
                    cw = max(1, int(iw * f))
                    x += iw - cw
                    img = img.crop((iw - cw, 0, iw, ih))
                elif d == "u":
                    ch = max(1, int(ih * f))
                    y += ih - ch
                    img = img.crop((0, ih - ch, iw, ih))
                elif d == "d":
                    img = img.crop((0, 0, iw, max(1, int(ih * f))))
            if abs(scale - 1) > 1e-3:
                nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
                ax, ay = L["ax"] + (x - L["ox"]), L["ay"] + (y - L["oy"])
                x = ax - (ax - x) * scale
                y = ay - (ay - y) * scale
                img = img.resize((nw, nh), Image.BILINEAR)
            if alpha < 0.999:
                a = img.getchannel("A").point(lambda v: int(v * alpha))
                img = img.copy()
                img.putalpha(a)
            fr.paste(img, (int(round(x)), int(round(y))), img)
        # camera (sub-pixel, smooth, clamped so we never see past the frame edge)
        z, cx, cy = self.cam_at(t)
        if abs(z - 1) > 1e-4 or cx != W / 2 or cy != H / 2:
            fr = fr.transform((W, H), Image.AFFINE, (1 / z, 0, cx - W / 2 / z, 0, 1 / z, cy - H / 2 / z), Image.BILINEAR)
        # whip pans get motion blur along the direction the camera moves
        whip = any(sh["move"] == "whip" and sh["t"] <= t < sh["t"] + self.MOVE_TIME["whip"] + 0.04 for sh in self.shots)
        if whip:
            z2, cx2, cy2 = self.cam_at(max(0.0, t - 1 / 30))
            vx, vy = (cx - cx2) * z, (cy - cy2) * z
            if abs(z - z2) * 400 > 12 and abs(vx) + abs(vy) < 12:
                vx = vy = 0  # zoom-only whips: skip (a radial blur isn't worth it)
            if math.hypot(vx, vy) > 12:
                fr = motion_blur(fr, vx, vy)
        for (c0, c1, cimg) in captions:
            if c0 <= t < c1:
                fr.paste(cimg, ((W - cimg.width) // 2, H - 70 - cimg.height), cimg)
                break
        return fr
