"""Weather and light over a scene: falling snow, blizzards, rain, thunderstorms with lightning, drifting fog,
ash and embers over burning cities, twinkling night skies with shooting stars, and the light changing during a
scene (day fading to night, a warm dusk, the room going dark).

Everything is drawn straight onto each frame (no big cached images), in front of the world but behind labels
and speech bubbles, so text stays readable.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from .doodle import W, H

WEATHERS = ("snow", "blizzard", "rain", "storm", "fog", "ash")
WEATHER_ALIASES = {"snowing": "snow", "snowfall": "snow", "snowy": "snow", "flurries": "snow", "winter": "snow",
                   "snowstorm": "blizzard", "whiteout": "blizzard", "raining": "rain", "rainy": "rain",
                   "drizzle": "rain", "shower": "rain", "downpour": "storm", "thunderstorm": "storm",
                   "thunder": "storm", "lightning": "storm", "rainstorm": "storm", "mist": "fog", "misty": "fog",
                   "foggy": "fog", "haze": "fog", "embers": "ash", "ashes": "ash", "burning": "ash", "fire": "ash",
                   "fallout": "ash", "none": "none", "clear": "none", "sunny": "none"}
LIGHTS = ("night", "dusk", "dawn", "dark")
LIGHT_ALIASES = {"to_night": "night", "nightfall": "night", "evening": "dusk", "sunset": "dusk", "sunrise": "dawn",
                 "morning": "dawn", "dim": "dark", "darken": "dark", "blackout": "dark", "lights_out": "dark"}
# how each change of light tints the frame: (color, strength at the end)
LIGHT_TINT = {"night": ((16, 22, 56), 0.52), "dusk": ((255, 118, 60), 0.2), "dawn": ((255, 196, 130), 0.16),
              "dark": ((8, 8, 14), 0.5)}
WEATHER_Z = 2.5          # in front of characters and props (z 1-2), behind text (z 3) and bubbles (z 6)

SNOW_LINE = (186, 198, 222)
RAIN_COL = (118, 138, 178)


_solids = {}


def solid(fr, col):
    """A plain image of one color, the same size and mode as the frame (cached)."""
    key = (fr.mode, fr.size, col)
    im = _solids.get(key)
    if im is None:
        im = Image.new(fr.mode, fr.size, col + (255,) if fr.mode == "RGBA" else col)
        if len(_solids) > 16:
            _solids.clear()
        _solids[key] = im
    return im


def norm_weather(v):
    k = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    k = WEATHER_ALIASES.get(k, k)
    return k if k in WEATHERS else None


def norm_light(v):
    k = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    k = LIGHT_ALIASES.get(k, k)
    return k if k in LIGHTS else None


def _ramp(t, t0, t1, fade=0.8):
    """0 -> 1 when the weather starts at t0, back to 0 when it stops at t1."""
    if t < t0:
        return 0.0
    a = min(1.0, (t - t0) / fade) if fade > 0 else 1.0
    if t1 is not None:
        a = min(a, max(0.0, (t1 - t) / fade) if fade > 0 else float(t < t1))
    return a


class Weather:
    def __init__(self, kind, seed=1, amount=1.0, wind=None, t0=0.0, t1=None, dur=10.0):
        self.kind = kind
        self.r = random.Random(seed * 7919 + len(kind))
        self.amount = max(0.2, min(float(amount or 1.0), 2.0))
        default_wind = {"blizzard": 1.4, "storm": 0.6, "rain": 0.25, "snow": 0.2, "ash": 0.3, "fog": 0.5}[kind]
        self.wind = default_wind if wind is None else max(-2.0, min(float(wind), 2.0))
        self.t0, self.t1, self.dur = float(t0), (float(t1) if t1 is not None else None), float(dur)
        self.flakes, self.drops, self.embers = [], [], []
        self.strikes = []
        self.fog = None
        r = self.r
        if kind in ("snow", "blizzard", "ash"):
            n = int((380 if kind == "blizzard" else 150 if kind == "snow" else 110) * self.amount)
            fast = 1.9 if kind == "blizzard" else 0.55 if kind == "ash" else 1.0
            for _ in range(n):
                depth = r.random()
                self.flakes.append(dict(x=r.uniform(0, W), y=r.uniform(-H, H), v=(45 + 90 * depth) * fast,
                                        rad=(2.0 + 4.5 * depth) * (0.9 if kind == "ash" else 1.0),
                                        a=r.uniform(8, 30), f=r.uniform(0.2, 0.7), ph=r.uniform(0, 6.3)))
        if kind == "ash":
            for _ in range(int(45 * self.amount)):
                self.embers.append(dict(x=r.uniform(0, W), y=r.uniform(0, H + 200), v=r.uniform(40, 110),
                                        a=r.uniform(10, 40), f=r.uniform(0.3, 1.0), ph=r.uniform(0, 6.3),
                                        rad=r.uniform(2.5, 5.0)))
        if kind in ("rain", "storm"):
            n = int((340 if kind == "storm" else 210) * self.amount)
            for _ in range(n):
                depth = r.random()
                self.drops.append(dict(x=r.uniform(-200, W + 200), y=r.uniform(-H, H), v=1000 + 600 * depth,
                                       L=22 + 26 * depth, w=1 + int(depth > 0.55)))
        if kind == "storm":
            t = self.t0 + r.uniform(0.6, 1.6)
            end = self.t1 if self.t1 is not None else self.dur
            while t < end - 0.3:
                self.strikes.append((t, self._bolt(r)))
                t += r.uniform(2.6, 5.0)
        if kind == "fog":
            self.fog = self._fog_band(r)

    # ---------------------------------------------------------------- pieces
    def _bolt(self, r):
        x = r.uniform(260, W - 260)
        y = -10.0
        pts = [(x, y)]
        end = r.uniform(380, 640)
        while y < end:
            y += r.uniform(40, 80)
            x += r.uniform(-55, 55)
            pts.append((x, y))
        k = r.randint(2, len(pts) - 2) if len(pts) > 3 else 1
        bx, by = pts[k]
        branch = [(bx, by)]
        for _ in range(3):
            bx += r.uniform(20, 60) * r.choice((-1, 1))
            by += r.uniform(30, 60)
            branch.append((bx, by))
        return pts, branch

    def _fog_band(self, r):
        w, h = W // 4 * 2, 200                   # drawn small and blurred, then scaled up: soft and cheap
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for _ in range(26):
            cx, cy = r.uniform(0, w), r.uniform(h * 0.3, h * 0.85)
            rx, ry = r.uniform(40, 110), r.uniform(18, 40)
            for dx in (-w, 0, w):                # wrap around so the band tiles seamlessly
                d.ellipse([cx + dx - rx, cy - ry, cx + dx + rx, cy + ry], fill=(246, 246, 250, int(r.uniform(90, 150))))
        im = im.filter(ImageFilter.GaussianBlur(14))
        return im.resize((W * 2, int(h * 3.2)), Image.BILINEAR)

    # ---------------------------------------------------------------- draw
    def apply(self, fr, t):
        a = _ramp(t, self.t0, self.t1)
        if a <= 0:
            return fr
        if self.kind == "storm":
            fr = Image.blend(fr, solid(fr, (34, 38, 54)), 0.2 * a)
        if self.kind == "blizzard":
            fr = Image.blend(fr, solid(fr, (226, 230, 238)), 0.32 * a)
        if self.kind == "rain":
            fr = Image.blend(fr, solid(fr, (112, 122, 142)), 0.16 * a)
        if self.kind == "fog":
            return self._draw_fog(fr, t, a)
        d = ImageDraw.Draw(fr)
        if self.flakes:
            self._draw_flakes(d, t, a)
        if self.embers:
            self._draw_embers(d, t, a)
        if self.drops:
            self._draw_rain(d, t, a)
        if self.strikes:
            fr = self._draw_lightning(fr, t)
        return fr

    def _draw_flakes(self, d, t, a):
        ash = self.kind == "ash"
        n = int(len(self.flakes) * a)
        for f in self.flakes[:n]:
            y = (f["y"] + f["v"] * t) % (H + 60) - 30
            x = (f["x"] + self.wind * 90 * t + f["a"] * math.sin(2 * math.pi * f["f"] * t + f["ph"])) % (W + 60) - 30
            rad = f["rad"]
            if ash:
                d.ellipse([x - rad, y - rad * 0.7, x + rad, y + rad * 0.7], fill=(96, 94, 98))
            elif rad >= 4:
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(255, 255, 255), outline=SNOW_LINE, width=1)
            else:
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(250, 251, 255))
        if self.kind == "blizzard":           # wind streaks
            for k in range(int(30 * a)):
                yy = (k * 97 + 40 * t * (1 + k % 3)) % (H - 120)
                xx = (k * 331 + 900 * t * (1 + (k % 4) * 0.2)) % (W + 400) - 200
                d.line([(xx, yy), (xx + 120 + 40 * (k % 3), yy + 6)], fill=(250, 250, 255), width=2)

    def _draw_embers(self, d, t, a):
        n = int(len(self.embers) * a)
        for e in self.embers[:n]:
            y = (e["y"] - e["v"] * t) % (H + 100) - 50
            x = (e["x"] + self.wind * 40 * t + e["a"] * math.sin(2 * math.pi * e["f"] * t + e["ph"])) % W
            glow = 0.5 + 0.5 * math.sin(9 * t + e["ph"] * 3)
            rad = e["rad"] * (0.8 + 0.4 * glow)
            col = (255, int(140 + 80 * glow), int(40 + 40 * glow))
            d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col)

    def _draw_rain(self, d, t, a):
        n = int(len(self.drops) * a)
        sl = 0.12 + 0.22 * self.wind
        for p in self.drops[:n]:
            y = (p["y"] + p["v"] * t) % (H + 120) - 60
            x = (p["x"] + sl * p["v"] * t) % (W + 400) - 200
            L = p["L"]
            d.line([(x, y), (x + sl * L, y + L)], fill=RAIN_COL, width=p["w"] + 1)

    def _draw_lightning(self, fr, t):
        for ts, (pts, branch) in self.strikes:
            dt = t - ts
            if 0 <= dt < 0.32:
                flash = (1 - dt / 0.32) * (0.42 if dt < 0.07 or 0.12 < dt < 0.18 else 0.22)
                fr = Image.blend(fr, solid(fr, (250, 250, 255)), flash)
                if dt < 0.2:
                    d = ImageDraw.Draw(fr)
                    d.line(pts, fill=(255, 236, 140), width=13, joint="curve")
                    d.line(branch, fill=(255, 236, 140), width=8, joint="curve")
                    d.line(pts, fill=(255, 255, 255), width=6, joint="curve")
                    d.line(branch, fill=(255, 255, 255), width=3, joint="curve")
        return fr

    def _draw_fog(self, fr, t, a):
        band = self.fog
        shift = int((self.wind * 30 * t) % W)
        crop = band.crop((shift, 0, shift + W, band.height))
        if a < 0.99:
            crop = crop.copy()
            crop.putalpha(crop.getchannel("A").point(lambda v: int(v * a)))
        y0 = int(H * 0.5)
        fr.paste(crop, (0, y0 - band.height // 3), crop)
        # a second, fainter band higher up drifting the other way
        shift2 = int((-self.wind * 18 * t + W / 2) % W)
        c2 = band.crop((shift2, 0, shift2 + W, band.height))
        c2 = c2.copy()
        c2.putalpha(c2.getchannel("A").point(lambda v: int(v * 0.45 * a)))
        fr.paste(c2, (0, int(H * 0.22)), c2)
        return fr

    def sounds(self):
        """[(seconds, sfx kind)] for thunder after each lightning strike."""
        return [(ts + 0.25, "thunder") for ts, _ in self.strikes]


class Twinkle:
    """A starry night that lives: a few stars sparkle and now and then a shooting star crosses the sky."""

    def __init__(self, seed=1, horizon=600, dur=10.0, bg=None):
        r = random.Random(seed * 31 + 5)

        def sky(x, y):
            """Only sparkle over dark, empty sky (not over buildings, mountains or the moon)."""
            if bg is None:
                return True
            for dx, dy in ((0, 0), (-14, 0), (14, 0), (0, -14), (0, 14)):
                px = bg.getpixel((int(min(max(x + dx, 0), W - 1)), int(min(max(y + dy, 0), H - 1))))
                if sum(px[:3]) / 3 > 95:
                    return False
            return True

        self.stars = []
        for _ in range(60):
            x, y = r.uniform(60, W - 60), r.uniform(30, max(80, horizon * 0.62))
            if sky(x, y):
                self.stars.append((x, y, r.uniform(0, 6.3), r.uniform(0.7, 1.6)))
            if len(self.stars) >= 12:
                break
        self.shooting = []
        t = r.uniform(0.8, 2.5)
        while t < dur - 0.8:
            x = r.uniform(300, W - 500)
            y = r.uniform(40, max(100, horizon * 0.4))
            if sky(x, y) and sky(x + 520, y + 170):
                self.shooting.append((t, x, y))
            t += r.uniform(4.0, 7.0)

    def apply(self, fr, t):
        d = ImageDraw.Draw(fr)
        for x, y, ph, sp in self.stars:
            k = 0.5 + 0.5 * math.sin(t * 2.2 * sp + ph)
            if k < 0.35:
                continue
            s = 3 + 8 * k
            col = (255, 250, 214)
            d.line([(x - s, y), (x + s, y)], fill=col, width=2)
            d.line([(x, y - s), (x, y + s)], fill=col, width=2)
            d.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(255, 255, 240))
        for ts, x, y in self.shooting:
            q = (t - ts) / 0.7
            if 0 <= q < 1:
                hx, hy = x + 520 * q, y + 170 * q
                for k in range(6):
                    f = k / 6
                    d.line([(hx - 150 * (1 - f) * 0.9, hy - 49 * (1 - f) * 0.9), (hx, hy)],
                           fill=(255, 250, 220), width=max(1, 4 - k // 2))
                d.ellipse([hx - 4, hy - 4, hx + 4, hy + 4], fill=(255, 255, 255))
        return fr


class Light:
    """The light changes during the scene: day fading to night, a warm dusk, a room going dark."""

    def __init__(self, to, t0, t1):
        self.col, self.max = LIGHT_TINT[to]
        self.t0, self.t1 = float(t0), max(float(t1), float(t0) + 0.2)
        self.solid = None

    def apply(self, fr, t):
        q = (t - self.t0) / (self.t1 - self.t0)
        if q <= 0:
            return fr
        q = min(1.0, q)
        q = q * q * (3 - 2 * q)
        if self.solid is None or self.solid.size != fr.size or self.solid.mode != fr.mode:
            self.solid = solid(fr, self.col)
        return Image.blend(fr, self.solid, self.max * q)


class Clouds:
    """The sky's clouds drifting slowly (bigger, nearer ones faster). They only show where the background is
    sky, so they pass behind buildings, hills and towers."""

    def __init__(self, specs, bg, sky_ref, seed=1):
        import numpy as np
        from .pen import Pen
        arr = np.asarray(bg.convert("RGB"), dtype=np.int16)
        kind, col, horizon = sky_ref
        rows = np.arange(arr.shape[0], dtype=np.float32)[:, None]
        if kind == "grad":
            top, bot = (np.array(c, dtype=np.float32) for c in col)
            q = np.clip(rows / max(1.0, float(horizon)), 0, 1)[:, :, None]
            want = top + (bot - top) * q
        else:
            want = np.array(col, dtype=np.float32)[None, None, :]
        diff = np.abs(arr - want).sum(axis=2)
        sky = (diff < 30) & (rows < horizon)
        self.mask = Image.fromarray((sky * 255).astype("uint8"), "L").filter(ImageFilter.MinFilter(3))
        r = random.Random(seed * 13 + 1)
        self.items = []
        for x, y, s, c in specs:
            w, h = int(260 * s + 40), int(150 * s + 40)
            p = Pen(3, rgba=True, size=(w, h))
            p.cloud(w / 2, h / 2 - 10 * s, s, c)
            spr = p.im.convert("RGBa").resize((w, h), Image.LANCZOS).convert("RGBA")
            storm = sum(c[:3]) < 600                      # heavy gray storm clouds move faster
            speed = (5 + 9 * s) * (1.8 if storm else 1.0) * r.choice((1, 1, -1))
            self.items.append((spr, x - w / 2, y - h / 2, speed))

    def apply(self, fr, t):
        from PIL import ImageChops
        span = W + 600
        for spr, x0, y0, v in self.items:
            x = int(((x0 + v * t + 300) % span) - 300)
            y = int(y0)
            ax0, ay0 = max(0, x), max(0, y)
            ax1, ay1 = min(W, x + spr.width), min(H, y + spr.height)
            if ax1 <= ax0 or ay1 <= ay0:
                continue
            part = spr.crop((ax0 - x, ay0 - y, ax1 - x, ay1 - y))
            alpha = ImageChops.multiply(part.getchannel("A"), self.mask.crop((ax0, ay0, ax1, ay1)))
            fr.paste(part.convert(fr.mode), (ax0, ay0), alpha)
        return fr
