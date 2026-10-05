"""Scene: a background plus animated layers, rendered frame by frame.

Each layer is drawn once at 2x, downsampled with LANCZOS (premultiplied alpha), cropped to its bounding
box, and then composited per frame with its enter / idle / move / exit animation. The camera is a float
affine transform (bilinear), clamped so a zoom never shows black edges.
"""
import math
import random
from contextlib import contextmanager

from PIL import Image

from .doodle import W, H, SS
from .palette import INK, PAPER, SEA, SEA2, LAND, RED, NAVY, WHITE, SUN, DARK, color as to_color, darker
from .pen import Pen
from .geo import View, geom_polys
from .timing import WordTimer, LEAD, TAIL

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


class Scene:
    def __init__(self, idx, dur, mood, text, timer=None, lead=LEAD, tail=TAIL):
        self.idx, self.dur, self.mood, self.text = idx, float(dur), mood, text
        self.timer = timer or WordTimer(text, dur, lead, tail)
        self.bg = None
        self.layers = []
        self.cam = dict(z0=1.0, z1=1.035, cx0=W / 2, cy0=H / 2, cx1=W / 2, cy1=H / 2)
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
             sfx="auto", **pose):
        cx = min(max(x, 130 * s), W - 130 * s)
        cy = min(max(y, 375 * s + 12), H - 15)
        if abs(cx - x) > 1 or abs(cy - y) > 1:
            self.warn(f"character '{kind}' moved on-screen ({x:.0f},{y:.0f}) -> ({cx:.0f},{cy:.0f})")
        imgs = []
        for blink in (False, True):
            p = Pen(self.seed + 991, rgba=True)
            p.stick(cx, cy, s, kind, blink=blink, **pose)
            imgs.append(self._finish(p))
        (img, off), (alt, off2) = imgs
        if img is None:
            self.warn(f"character '{kind}' is completely off-screen")
            return
        if pose.get("eyes") in ("closed", "happy", "dead"):
            alt = None
        self._add(img, off, enter, at, 0.42, idle, (cx, cy), exit_at, sfx, move, z, alt)

    def label(self, text, x, y, size=70, col=INK, f="bold", enter="pop", at=0.0, stroke=9, scol=WHITE,
              idle=None, exit_at=None, sfx="auto", z=3, anchor="mm", move=None, edur=0.38):
        with self.layer(enter, at, edur=edur, idle=idle, exit_at=exit_at, sfx=sfx, z=z, move=move) as p:
            p.text(text, x, y, size, col, anchor=anchor, stroke=stroke, scol=scol, f=f)

    def camera(self, z0=1.0, z1=1.04, c0=None, c1=None):
        c0 = c0 or (W / 2, H / 2)
        c1 = c1 or c0
        self.cam = dict(z0=z0, z1=z1, cx0=c0[0], cy0=c0[1], cx1=c1[0], cy1=c1[1])

    # ---------------- maps ----------------
    def map_bg(self, view, base_terr=(), sea=(156, 205, 230), land=(238, 214, 160), labels=()):
        from . import geo
        self.view = view
        with self.background(sea) as p:
            r = random.Random(self.idx)
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
                        p.poly(pts, land, 3, (90, 80, 70), 0.35)
            for g, col in base_terr:
                self._draw_terr(p, view.in_view(g), col)
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
        with self.layer(enter, at, z=2, exit_at=exit_at) as p:
            if dot:
                p.circ(x, y, 11, WHITE, 5)
                p.circ(x, y, 5, col, 0)
            if name:
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
        q = ease_io(t / max(self.dur, 1e-3))
        z = max(1.0, c["z0"] + (c["z1"] - c["z0"]) * q)
        cx = c["cx0"] + (c["cx1"] - c["cx0"]) * q
        cy = c["cy0"] + (c["cy1"] - c["cy0"]) * q
        hw, hh = W / (2 * z), H / (2 * z)
        cx = min(max(cx, hw), W - hw)
        cy = min(max(cy, hh), H - hh)
        if abs(z - 1) > 1e-4 or cx != W / 2 or cy != H / 2:
            fr = fr.transform((W, H), Image.AFFINE, (1 / z, 0, cx - W / 2 / z, 0, 1 / z, cy - H / 2 / z), Image.BILINEAR)
        for (c0, c1, cimg) in captions:
            if c0 <= t < c1:
                fr.paste(cimg, ((W - cimg.width) // 2, H - 70 - cimg.height), cimg)
                break
        return fr
