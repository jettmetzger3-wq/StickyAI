"""The Pen: a doodle canvas that can also draw stickmen with hats, faces, extras and held props."""
import math
import random

from PIL import Image, ImageDraw

from . import doodle
from .doodle import W, H, SS
from .palette import INK, PAPER, RED, NAVY, YELLOW, ORANGE, BROWN, WHITE, GRAY, DGRAY, color as to_color, darker
from .fonts import font

# ------------------------------------------------------------------ pose presets (arm/leg angles)
ARMS = {
    "down": ((20, 15), (20, 15)),
    "up": ((165, 10), (165, 10)),
    "cheer": ((140, 20), (140, 20)),
    "shrug": ((70, 75), (70, 75)),
    "hips": ((45, -115), (45, -115)),
    "cross": ((35, -135), (35, -135)),
    "point_left": ((95, -5), (20, 15)),
    "point_right": ((20, 15), (95, -5)),
    "wave": ((20, 15), (150, 25)),
    "wave_left": ((150, 25), (20, 15)),
    "think": ((20, 15), (35, -150)),
    "hold": ((20, 15), (60, 40)),
    "hold_both": ((60, 40), (60, 40)),
    "arms_out": ((90, 0), (90, 0)),
    "fight": ((100, 10), (40, 10)),
    "raise_right": ((20, 15), (150, 20)),
    "raise_left": ((150, 20), (20, 15)),
    "angry_fists": ((40, -60), (40, -60)),
    "hand_in_coat": ((20, 15), (25, -150)),      # Napoleon's famous pose
}
LEGS = {
    "stand": ((12, 0), (12, 0)),
    "walk": ((28, 10), (-12, -25)),
    "run": ((45, 60), (-35, -30)),
    "wide": ((24, 0), (24, 0)),
    "jump": ((40, 70), (40, 70)),
    "sit": ((55, 55), (55, 55)),                 # astride a horse
}

# animals and vehicles a character can ride: prop, size relative to the rider, seat (x, y) on the prop at
# scale 1 (y up is negative), whether the rider stands (chariots) instead of sitting
MOUNTS = {
    "horse": dict(prop="horse", k=0.95, seat=(-8, -238), stand=False),
    "camel": dict(prop="camel", k=0.9, seat=(-24, -296), stand=False),
    "elephant": dict(prop="elephant", k=0.85, seat=(-40, -292), stand=False),
    "chariot": dict(prop="chariot", k=0.9, seat=(-130, -66), stand=True),
}
MOUNT_ALIASES = {"pony": "horse", "stallion": "horse", "cavalry": "horse", "war_elephant": "elephant",
                 "dromedary": "camel"}
# hats that come with a uniform's details when the character wears a coat
CROSSBELTS = ("shako", "bearskin", "tricorn")
EPAULETTES = ("bicorne", "crown", "navy", "marine")


def mount_lift(ride, s=1.0):
    """How far above the ground a rider's feet point sits (screen px) and the mount's half width."""
    m = MOUNTS.get(ride)
    if not m:
        return 0.0, 0.0
    ms = s * m["k"]
    lift = -m["seat"][1] * ms - (0 if m["stand"] else 112 * s)
    return lift, 215 * ms

MOUTHS = ("smile", "grin", "open", "scream", "frown", "smirk", "wavy", "flat", "o")
EYES = ("dot", "wide", "happy", "closed", "angry", "sad", "worried", "dead")
EXTRAS = ("sweat", "blush", "tear", "vein", "q", "!", "steam", "mustache", "beard", "glasses", "zzz")
HELD = ("sword", "flag", "whiteflag", "paper", "megaphone", "teacup", "pointer", "can", "bowl", "spear",
        "shield", "torch", "book", "scroll", "money", "hammer", "pickaxe", "shovel")

# hats ("kind"). Many nation names are aliases of a hat.
HATS = ("japan", "headband", "army", "navy", "america", "tophat", "britain", "bowler", "china", "ussr", "furhat",
        "germany", "helmet", "italy", "dutch", "france", "beret", "marine", "student", "pilot", "glasses",
        "headphones", "tophat_gray", "civ", "cap", "crown", "roman", "laurel", "viking", "pirate", "tricorn",
        "bicorne", "cowboy", "knight", "wizard", "pharaoh", "turban", "chef", "graduate", "samurai", "hardhat",
        "astronaut", "mitre", "shako", "bearskin", "none")

# how far each hat reaches above the head's center, in stick units (a bare head's top is 64); speech bubbles use it
HAT_TOP = {"army": 84, "cap": 84, "china": 84, "dutch": 84, "student": 84, "navy": 78, "america": 138, "tophat": 138,
           "tophat_gray": 108, "shako": 182, "bearskin": 200, "britain": 92, "bowler": 92, "ussr": 104, "furhat": 104,
           "germany": 90, "helmet": 90, "marine": 90, "italy": 104, "france": 88, "beret": 88, "pilot": 86,
           "headphones": 78, "crown": 121, "roman": 128, "laurel": 76, "viking": 146, "pirate": 106, "tricorn": 106,
           "bicorne": 100, "cowboy": 124, "knight": 124, "wizard": 196, "pharaoh": 88, "turban": 94, "chef": 148,
           "graduate": 106, "samurai": 148, "hardhat": 90, "astronaut": 90, "mitre": 178}


def hat_top(kind):
    return HAT_TOP.get(resolve_kind(kind), 64)

KIND_ALIASES = {
    "usa": "america", "us": "america", "united_states": "america", "uncle_sam": "america",
    "uk": "britain", "england": "britain", "british": "britain", "gb": "britain",
    "soviet": "ussr", "soviet_union": "ussr", "russia": "ussr", "russian": "ussr",
    "prussia": "germany", "german": "germany", "japanese": "japan", "chinese": "china",
    "netherlands": "dutch", "holland": "dutch", "french": "france", "italian": "italy",
    "rome": "roman", "romans": "roman", "egypt": "pharaoh", "egyptian": "pharaoh",
    "vikings": "viking", "norse": "viking", "king": "crown", "queen": "crown", "emperor": "crown",
    "monarch": "crown", "pope": "mitre", "napoleon": "bicorne", "caesar": "laurel", "greek": "laurel",
    "greece": "laurel", "soldier": "army", "sailor": "navy", "civilian": "civ", "person": "civ",
    "civilians": "civ", "students": "student", "scientist": "glasses", "nerd": "glasses",
    "worker": "hardhat", "businessman": "tophat_gray", "politician": "tophat_gray", "rich": "tophat",
    "plain": "civ", "": "civ", "aussie": "marine", "australia": "marine",
    "napoleonic": "shako", "grenadier": "bearskin", "guard": "bearskin", "redcoat": "shako", "musketeer": "shako",
    "infantry": "shako", "napoleon_soldier": "shako", "french_soldier": "shako",
}


def resolve_kind(kind):
    k = str(kind or "civ").strip().lower().replace(" ", "_").replace("-", "_")
    k = KIND_ALIASES.get(k, k)
    return k if k in HATS else "civ"


class Pen(doodle.Canvas):
    """Doodle pen drawing at 2x on RGBA (layer) or RGB (background)."""

    def __init__(self, seed=1, rgba=True, bg=PAPER, size=None):
        """size: (w, h) in screen pixels for a small canvas (animated characters); default = the full frame."""
        self.rnd = random.Random(seed)
        w, h = size or (W, H)
        if rgba:
            self.im = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
        else:
            self.im = Image.new("RGB", (int(w * SS), int(h * SS)), bg)
        self.d = ImageDraw.Draw(self.im)

    def shadow(self, x, y, rx, ry=None):
        ry = ry or rx * 0.17
        self.d.ellipse([(x - rx) * SS, (y - ry) * SS, (x + rx) * SS, (y + ry) * SS], fill=(0, 0, 0, 38))

    # ---------------- stickman ----------------
    def stick(self, x, y, s=1.0, kind="japan", arms=((20, 15), (20, 15)), legs=((12, 0), (12, 0)),
              mouth="smile", eyes="dot", look=0, flip=False, extra=(), prop=None, blink=False, shadow=True,
              col=INK, hat_color=None, head=(0, 0), lean=0, coat=None):
        """Draw a stickman. (x, y) = point between the feet. Head top is about 375*s above y.
        head = (dx, dy) nudges the head (nods, head shakes); lean moves the shoulders sideways (bending, leaning)."""
        if isinstance(arms, str):
            arms = ARMS.get(arms, ARMS["down"])
        if isinstance(legs, str):
            legs = LEGS.get(legs, LEGS["stand"])
        if flip:
            arms = (arms[1], arms[0])
            legs = (legs[1], legs[0])
        kind = resolve_kind(kind)
        L = lambda v: v * s
        lw = 11 * s
        if shadow:
            self.shadow(x, y + L(4), L(62))
        hx = x + L(lean) * 1.15 + L(head[0])
        hy = y - L(300) + L(head[1]) + abs(L(lean)) * 0.12
        hr = L(64)
        neck = (x + L(lean), y - L(234) + abs(L(lean)) * 0.1)
        hip = (x, y - L(118))
        sh = (x + L(lean) * 0.9, y - L(205) + abs(L(lean)) * 0.1)
        feet = []
        for side, (a, b) in zip((-1, 1), legs):
            ar = math.radians(a)
            knee = (hip[0] + side * math.sin(ar) * L(60), hip[1] + math.cos(ar) * L(60))
            br = math.radians(a - b)
            foot = (knee[0] + side * math.sin(br) * L(60), knee[1] + math.cos(br) * L(60))
            self.line([hip, knee, foot], lw, col, 0.6)
            feet.append((foot, side))
        for (fx, fy), side in feet:
            self.ell(fx + side * L(10), fy + L(2), L(20), L(10), col, 0)
        self.line([neck, hip], lw, col, 0.6)
        cc = to_color(coat, None) if coat else None
        if cc:
            self._coat(neck, sh, hip, s, cc, kind)
        hands, fdirs = [], []
        for side, (a, b) in zip((-1, 1), arms):
            ar = math.radians(a)
            elbow = (sh[0] + side * math.sin(ar) * L(58), sh[1] + math.cos(ar) * L(58))
            fr = math.radians(a + b)
            hand = (elbow[0] + side * math.sin(fr) * L(56), elbow[1] + math.cos(fr) * L(56))
            if cc:
                wrist = (elbow[0] + (hand[0] - elbow[0]) * 0.72, elbow[1] + (hand[1] - elbow[1]) * 0.72)
                self.line([(sh[0] + side * L(20), sh[1] + L(4)), elbow, wrist], L(27), INK, 0.4)
                self.line([(sh[0] + side * L(20), sh[1] + L(4)), elbow, wrist], L(19), cc, 0.4)
                self.line([wrist, hand], lw, col, 0.4)
            else:
                self.line([sh, elbow, hand], lw, col, 0.6)
            self.circ(hand[0], hand[1], L(9), col, 0)
            hands.append(hand)
            fdirs.append((side * math.sin(fr), math.cos(fr)))
        if prop:
            self._prop(prop, hands, s, flip, fdirs)
        self.circ(hx, hy, hr, (255, 253, 247), 7 * s)
        f = -1 if flip else 1
        self._hat(kind, hx, hy, hr, s, f, to_color(hat_color, None) if hat_color else None)
        self._face(hx, hy, s, mouth, "closed" if blink else eyes, look * f if look else 0, f, kind)
        for e in extra or ():
            self._extra(e, hx, hy, s, f)
        return hands

    def _coat(self, neck, sh, hip, s, cc, kind):
        """A jacket over the stick body: uniforms (redcoats vs blue coats), suits, robes."""
        L = lambda v: v * s
        top_y = sh[1] - L(8)
        pts = [(neck[0] - L(16), top_y - L(6)), (sh[0] - L(36), top_y), (hip[0] - L(32), hip[1] + L(6)),
               (hip[0] - L(26), hip[1] + L(44)), (hip[0] - L(4), hip[1] + L(18)), (hip[0] + L(4), hip[1] + L(18)),
               (hip[0] + L(26), hip[1] + L(44)), (hip[0] + L(32), hip[1] + L(6)), (sh[0] + L(36), top_y),
               (neck[0] + L(16), top_y - L(6))]
        self.poly(pts, cc, 6 * s, INK, 0.4)
        light = tuple(min(255, int(v + (255 - v) * 0.85)) for v in cc)
        self.poly([(neck[0] - L(14), top_y - L(4)), (neck[0], top_y + L(22)), (neck[0] + L(14), top_y - L(4))],
                  light, 3 * s, INK, 0.3)
        for k in range(4):
            q = (k + 1) / 5
            bx = neck[0] + (hip[0] - neck[0]) * q
            by = top_y + L(26) + (hip[1] - top_y - L(26)) * q
            self.circ(bx, by, L(5), YELLOW, 2 * s)
        if kind in CROSSBELTS:
            for sgn in (-1, 1):
                self.line([(sh[0] + sgn * L(30), top_y + L(4)), (hip[0] - sgn * L(28), hip[1] + L(4))], L(9), WHITE, 0.3)
        if kind in EPAULETTES:
            for sgn in (-1, 1):
                self.ell(sh[0] + sgn * L(34), top_y + L(2), L(17), L(8), YELLOW, 3 * s)
                for fx in (-10, -3, 4, 11):
                    self.line([(sh[0] + sgn * L(34) + L(fx), top_y + L(8)), (sh[0] + sgn * L(34) + L(fx), top_y + L(18))],
                              2.5 * s, YELLOW, 0.2)
        self.line([(hip[0] - L(30), hip[1] - L(4)), (hip[0] + L(30), hip[1] - L(4))], L(6), darker(cc, 0.55), 0.3)

    def _face(self, x, hy, s, mouth, eyes, look, f, kind):
        L = lambda v: v * s
        ey = hy + L(4)
        lo = look * L(7)
        for ex in (-L(22), L(22)):
            cx = x + ex
            if eyes == "wide":
                self.circ(cx, ey, L(15), WHITE, 5 * s)
                self.circ(cx + lo, ey, L(6.5), INK, 0)
            elif eyes == "closed":
                self.line([(cx - L(10), ey + L(1)), (cx + L(10), ey + L(1))], 6 * s, INK, 0.2)
            elif eyes == "happy":
                self.line([(cx - L(11), ey + L(5)), (cx, ey - L(5)), (cx + L(11), ey + L(5))], 6 * s, INK, 0.2)
            elif eyes == "dead":
                self.line([(cx - L(9), ey - L(9)), (cx + L(9), ey + L(9))], 5 * s, INK, 0.2)
                self.line([(cx + L(9), ey - L(9)), (cx - L(9), ey + L(9))], 5 * s, INK, 0.2)
            else:
                self.circ(cx + lo, ey, L(7.5), INK, 0)
            if eyes in ("angry", "sad", "worried"):
                inner = 1 if ex < 0 else -1
                if eyes == "angry":
                    p1 = (cx - inner * L(14), ey - L(22))
                    p2 = (cx + inner * L(12), ey - L(13))
                else:
                    p1 = (cx - inner * L(14), ey - L(13))
                    p2 = (cx + inner * L(12), ey - L(22))
                self.line([p1, p2], 6 * s, INK, 0.2)
        my = hy + L(32)
        if mouth == "smile":
            self.line([(x - L(20), my - L(5)), (x - L(8), my + L(6)), (x + L(8), my + L(6)), (x + L(20), my - L(5))], 6 * s, INK, 0.2)
        elif mouth == "grin":
            self.chord(x - L(24), my - L(16), x + L(24), my + L(16), 0, 180, WHITE, 5 * s)
        elif mouth == "open":
            self.ell(x, my + L(3), L(13), L(11), (150, 45, 55), 5 * s)
        elif mouth == "scream":
            self.ell(x, my + L(8), L(17), L(22), (150, 45, 55), 5 * s)
        elif mouth == "frown":
            self.line([(x - L(18), my + L(8)), (x - L(7), my), (x + L(7), my), (x + L(18), my + L(8))], 6 * s, INK, 0.2)
        elif mouth == "smirk":
            self.line([(x - L(14), my + L(3)), (x + L(10), my + L(3)), (x + L(20), my - L(6))], 6 * s, INK, 0.2)
        elif mouth == "wavy":
            self.line([(x - L(18), my + L(3)), (x - L(9), my - L(3)), (x, my + L(3)), (x + L(9), my - L(3)), (x + L(18), my + L(3))], 5 * s, INK, 0.2)
        elif mouth == "o":
            self.circ(x, my + L(2), L(7), (150, 45, 55), 4 * s)
        else:
            self.line([(x - L(14), my + L(2)), (x + L(14), my + L(2))], 6 * s, INK, 0.2)
        if kind in ("britain",):
            self._mustache(x, my, s)

    def _mustache(self, x, my, s):
        L = lambda v: v * s
        self.line([(x - L(22), my - L(8)), (x - L(4), my - L(12)), (x + L(4), my - L(12)), (x + L(22), my - L(8))], 8 * s, BROWN, 0.2)

    def _dome(self, x, hy, s, x0, y0, x1, y1, fill, w=6):
        L = lambda v: v * s
        self.chord(x + L(x0), hy + L(y0), x + L(x1), hy + L(y1), 180, 360, fill, w * s)

    def _crown_dome(self, x, yb, s, rx, ry, fill, w=6):
        """The round top of a hat: half an ellipse whose flat edge sits on the hat line yb, hugging the head."""
        self.chord(x - rx * s, yb - ry * s, x + rx * s, yb + ry * s, 180, 360, fill, w * s)

    def _hat(self, kind, x, hy, hr, s, f, hc=None):
        """Hats sit ON the head: their band is on the forehead line (yb, just above the eyebrows) and they are at
        least as wide as the head there, so no head outline shows between hat and head."""
        L = lambda v: v * s
        yb = hy - L(26)          # the hat line: where a hat meets the forehead
        if kind in ("japan", "headband"):
            band = hc if (hc and kind == "headband") else WHITE
            self.poly([(x - L(49), hy - L(46)), (x + L(49), hy - L(46)), (x + L(67), hy - L(18)), (x - L(67), hy - L(18))],
                      band, 5 * s, wob=0.3)
            if kind == "japan" or not hc:
                self.circ(x, hy - L(32), L(10), RED, 0)
            kx = x - f * L(64)
            self.line([(kx, hy - L(30)), (kx - f * L(40), hy - L(2))], 9 * s, band, 0.3)
            self.line([(kx, hy - L(30)), (kx - f * L(46), hy - L(26))], 9 * s, band, 0.3)
            self.line([(kx, hy - L(30)), (kx - f * L(40), hy - L(2))], 2 * s, INK, 0.3)
        elif kind in ("army", "cap", "china", "dutch", "student"):
            c = hc or {"army": (122, 128, 74), "cap": (122, 128, 74), "china": (78, 92, 110), "dutch": ORANGE,
                       "student": (30, 30, 40)}[kind]
            self._crown_dome(x, yb, s, 68, 58, c)
            if kind in ("army", "cap", "china"):
                self.rect(x - L(69), yb - L(13), L(138), L(15), darker(c, 0.77), 5 * s)
            self.poly([(x + f * L(14), yb - L(2)), (x + f * L(90), yb + L(10)), (x + f * L(64), yb - L(8))],
                      darker(c, 0.55), 4 * s)
            if kind == "army":
                self.circ(x, yb - L(30), L(7), YELLOW, 3 * s)
            elif kind == "china":
                self.circ(x, yb - L(32), L(11), (40, 70, 160), 3 * s)
                self.circ(x, yb - L(32), L(5), WHITE, 0)
            elif kind == "student":
                self.circ(x, yb - L(30), L(7), YELLOW, 2 * s)
        elif kind == "navy":
            self.ell(x, yb - L(30), L(78), L(22), WHITE, 6 * s)
            self.rect(x - L(66), yb - L(16), L(132), L(19), INK, 4 * s)
            self.rect(x - L(60), yb - L(11), L(120), L(6), YELLOW, 0)
            self.poly([(x + f * L(10), yb + L(2)), (x + f * L(84), yb + L(12)), (x + f * L(58), yb - L(4))], INK, 3 * s)
        elif kind in ("america", "tophat", "tophat_gray"):
            c = hc or (NAVY if kind == "america" else (60, 60, 66) if kind == "tophat_gray" else (40, 40, 46))
            tall = 82 if kind == "tophat_gray" else 112
            self.rect(x - L(53), yb - L(tall), L(106), L(tall), c, 6 * s, r=L(8))
            if kind != "tophat_gray":
                self.rect(x - L(53), yb - L(30), L(106), L(17), RED if kind == "america" else darker(c, 0.6), 5 * s)
            self.ell(x, yb - L(2), L(88 if kind != "tophat_gray" else 80), L(12), c, 6 * s)
            if kind == "america":
                self.poly([(x - L(16), hy + L(64)), (x, hy + L(72)), (x + L(16), hy + L(64)), (x + L(16), hy + L(82)),
                           (x, hy + L(74)), (x - L(16), hy + L(82))], RED, 4 * s)
        elif kind == "shako":
            # Napoleonic infantry: a tall cylinder (a bit wider on top), visor, plate and a red plume
            c = hc or (34, 36, 48)
            self.ell(x - f * L(34), yb - L(128), L(12), L(28), RED, 4 * s)
            self.poly([(x - L(62), yb + L(4)), (x - L(68), yb - L(104)), (x + L(68), yb - L(104)), (x + L(62), yb + L(4))],
                      c, 6 * s, INK, 0.3)
            self.ell(x, yb - L(104), L(68), L(9), darker(c, 0.75), 4 * s)
            self.ell(x + f * L(16), yb + L(4), L(58), L(11), INK, 0)
            self.circ(x, yb - L(52), L(14), YELLOW, 4 * s)
        elif kind == "bearskin":
            c = hc or (26, 26, 30)
            self.ell(x, yb - L(78), L(72), L(96), c, 6 * s, INK)
            for k in range(7):
                ang = math.pi * (0.15 + 0.7 * k / 6)
                px, py = x - math.cos(ang) * L(70), yb - L(78) - math.sin(ang) * L(92)
                self.line([(px, py), (px - math.cos(ang) * L(9), py - math.sin(ang) * L(9))], 4 * s, (70, 70, 76), 0.6)
            self.ell(x - f * L(48), yb - L(106), L(10), L(26), RED, 3 * s)
            self.line([(x - L(58), yb + L(6)), (x - L(30), hy + L(52)), (x + L(30), hy + L(52)), (x + L(58), yb + L(6))],
                      4 * s, (200, 170, 70), 0.3)
        elif kind in ("britain", "bowler"):
            c = hc or (40, 40, 46)
            self._crown_dome(x, yb, s, 57, 66, c)
            self.ell(x, yb - L(1), L(82), L(12), c, 5 * s)
        elif kind in ("ussr", "furhat"):
            c = hc or (120, 86, 60)
            self.rect(x - L(80), yb - L(26), L(30), L(80), c, 5 * s, r=L(10))
            self.rect(x + L(50), yb - L(26), L(30), L(80), c, 5 * s, r=L(10))
            self.rect(x - L(72), yb - L(78), L(144), L(82), c, 6 * s, r=L(24))
            self.line([(x - L(64), yb - L(22)), (x + L(64), yb - L(22))], 3 * s, darker(c, 0.7), 0.3)
            if kind == "ussr":
                self.circ(x, yb - L(46), L(12), RED, 3 * s)
        elif kind in ("germany", "helmet", "marine"):
            c = hc or {"germany": (112, 118, 112), "helmet": (112, 118, 112), "marine": (102, 112, 70)}[kind]
            if kind == "germany":
                for sd in (-1, 1):
                    self.poly([(x + sd * L(68), yb - L(10)), (x + sd * L(84), yb + L(26)), (x + sd * L(56), yb + L(14))],
                              c, 5 * s)
            self._crown_dome(x, yb + L(6), s, 76, 70, c)
            self.line([(x - L(74), yb + L(4)), (x + L(74), yb + L(4))], 4 * s, darker(c, 0.7), 0.3)
        elif kind == "italy":
            c = (50, 70, 50)
            for k in range(4):
                self.line([(x - f * L(36), yb - L(36)), (x - f * L(112 + k * 10), yb - L(78 - k * 22))], 6 * s,
                          (30, 40, 30), 0.4)
            self._crown_dome(x, yb, s, 62, 58, c)
            self.ell(x, yb - L(1), L(86), L(11), c, 5 * s)
        elif kind in ("france", "beret"):
            c = hc or (52, 72, 150)
            self.ell(x - f * L(10), yb - L(20), L(74), L(27), c, 6 * s)
            self.line([(x - f * L(10), yb - L(46)), (x - f * L(6), yb - L(62))], 6 * s, INK, 0.2)
        elif kind == "pilot":
            self._crown_dome(x, yb + L(6), s, 70, 66, BROWN)
            for sd in (-1, 1):
                self.rect(x + sd * L(56) - L(13), yb, L(26), L(48), BROWN, 4 * s, r=L(10))
            self.rect(x - L(50), yb - L(28), L(42), L(26), (170, 210, 235), 4 * s, r=L(8))
            self.rect(x + L(8), yb - L(28), L(42), L(26), (170, 210, 235), 4 * s, r=L(8))
        elif kind == "glasses":
            self._glasses(x, hy, s)
        elif kind == "headphones":
            self._glasses(x, hy, s)
            self.d.arc([(x - L(74)) * SS, (hy - L(78)) * SS, (x + L(74)) * SS, (hy + L(40)) * SS], 180, 360, fill=INK,
                       width=int(8 * s * SS))
            self.rect(x - L(86), hy - L(14), L(24), L(44), (70, 70, 80), 4 * s, r=L(8))
            self.rect(x + L(62), hy - L(14), L(24), L(44), (70, 70, 80), 4 * s, r=L(8))
        elif kind == "crown":
            c = hc or (240, 200, 70)
            self.poly([(x - L(64), yb + L(4)), (x + L(64), yb + L(4)), (x + L(70), yb - L(74)), (x + L(34), yb - L(34)),
                       (x, yb - L(88)), (x - L(34), yb - L(34)), (x - L(70), yb - L(74))], c, 6 * s, wob=0.3)
            self.rect(x - L(65), yb - L(18), L(130), L(22), c, 5 * s)
            for dx in (-34, 0, 34):
                self.circ(x + L(dx), yb - L(7), L(7), RED, 2 * s)
            for px, py in ((-70, -74), (0, -88), (70, -74)):
                self.circ(x + L(px), yb + L(py), L(7), (250, 248, 240), 2 * s)
        elif kind == "roman":
            c = hc or (200, 170, 90)
            crest = RED
            self.ell(x, yb - L(70), L(62), L(32), crest, 6 * s)
            for k in range(-40, 50, 20):
                self.line([(x + L(k), yb - L(78)), (x + L(k * 1.15), yb - L(98 - abs(k) * 0.4))], 3 * s,
                          darker(crest, 0.7), 0.2)
            self._crown_dome(x, yb + L(4), s, 72, 64, c)
            for sd in (-1, 1):
                self.rect(x + sd * L(62) - L(12), yb - L(4), L(24), L(62), c, 5 * s, r=L(8))
        elif kind == "laurel":
            for deg in (170, 150, 130, 110, 70, 50, 30, 10):
                a = math.radians(deg)
                self.ell(x + L(64) * math.cos(a), hy - L(26) - L(42) * math.sin(a) + L(10) * (1 - math.sin(a)),
                         L(15), L(8), (110, 170, 90), 3 * s)
        elif kind == "viking":
            c = hc or (170, 170, 180)
            for side in (-1, 1):
                self.poly([(x + side * L(56), yb - L(20)), (x + side * L(104), yb - L(58)), (x + side * L(102), yb - L(120)),
                           (x + side * L(82), yb - L(56)), (x + side * L(44), yb - L(34))], (245, 240, 220), 5 * s, wob=0.3)
            self._crown_dome(x, yb + L(2), s, 70, 66, c)
            self.rect(x - L(70), yb - L(12), L(140), L(16), BROWN, 5 * s)
            self.rect(x - L(7), yb, L(14), L(34), c, 4 * s)
        elif kind in ("pirate", "tricorn"):
            c = hc or ((30, 30, 36) if kind == "pirate" else (60, 50, 50))
            self.poly([(x - L(100), yb - L(8)), (x, yb + L(6)), (x + L(100), yb - L(8)), (x + L(62), yb - L(80)),
                       (x, yb - L(60)), (x - L(62), yb - L(80))], c, 6 * s, wob=0.3)
            self.line([(x - L(92), yb - L(8)), (x, yb + L(4)), (x + L(92), yb - L(8))], 3 * s, (200, 170, 70), 0.3)
            if kind == "pirate":
                self.circ(x, yb - L(36), L(11), WHITE, 3 * s)
                self.line([(x + L(15), hy - L(4)), (x + L(58), yb - L(2))], 4 * s, INK, 0.2)
                self.circ(x + L(22), hy + L(4), L(14), INK, 0)
        elif kind == "bicorne":
            c = hc or (30, 30, 40)
            self.chord(x - L(114), yb - L(74), x + L(114), yb + L(78), 180, 360, c, 6 * s)
            self.line([(x - L(108), yb + L(1)), (x + L(108), yb + L(1))], 3 * s, (200, 170, 70), 0.3)
            self.circ(x + f * L(42), yb - L(38), L(14), (230, 230, 240), 3 * s)
            self.circ(x + f * L(42), yb - L(38), L(7), RED, 0)
        elif kind == "cowboy":
            c = hc or (170, 120, 70)
            self._crown_dome(x, yb - L(6), s, 54, 92, c)
            self.rect(x - L(52), yb - L(30), L(104), L(14), darker(c, 0.6), 0)
            self.ell(x, yb - L(4), L(116), L(20), c, 6 * s)
        elif kind == "knight":
            c = hc or (190, 192, 200)
            self.rect(x - L(70), hy - L(84), L(140), L(150), c, 6 * s, r=L(30))
            self.rect(x - L(52), hy - L(8), L(104), L(12), INK, 0)
            self.line([(x, hy + L(10)), (x, hy + L(50))], 5 * s, darker(c, 0.6), 0.2)
            self.chord(x - L(30), hy - L(124), x + L(30), hy - L(42), 180, 360, RED, 4 * s)   # plume sits on the helm
            return  # face hidden by helm visor (eyes still drawn on top)
        elif kind == "wizard":
            c = hc or (80, 70, 150)
            self.poly([(x - L(70), yb - L(2)), (x + L(70), yb - L(2)), (x + f * L(22), yb - L(170))], c, 6 * s, wob=0.3)
            self.ell(x, yb - L(2), L(96), L(15), c, 5 * s)
            self.text("*", x - L(8), yb - L(60), 40 * s, YELLOW)
        elif kind == "pharaoh":
            c1, c2 = (60, 90, 170), (232, 186, 60)
            self.poly([(x - L(64), yb - L(10)), (x + L(64), yb - L(10)), (x + L(94), hy + L(70)), (x + L(58), hy + L(70)),
                       (x + L(54), hy), (x - L(54), hy), (x - L(58), hy + L(70)), (x - L(94), hy + L(70))], c2, 6 * s, wob=0.3)
            for k in range(3):
                yy = yb + L(k * 30)
                self.line([(x - L(66 + k * 8), yy), (x - L(56), yy)], 6 * s, c1, 0.2)
                self.line([(x + L(56), yy), (x + L(66 + k * 8), yy)], 6 * s, c1, 0.2)
            self._crown_dome(x, yb + L(2), s, 68, 64, c2)
            self.line([(x - L(64), yb - L(16)), (x + L(64), yb - L(16))], 6 * s, c1, 0.2)
            self.line([(x - L(52), yb - L(40)), (x + L(52), yb - L(40))], 6 * s, c1, 0.2)
            self.circ(x, yb - L(26), L(9), (60, 160, 90), 3 * s)
        elif kind == "turban":
            c = hc or (240, 236, 220)
            self.ell(x, yb - L(24), L(74), L(44), c, 6 * s)
            self.line([(x - L(62), yb - L(32)), (x + L(52), yb - L(8))], 4 * s, darker(c, 0.75), 0.2)
            self.line([(x - L(56), yb - L(52)), (x + L(60), yb - L(26))], 4 * s, darker(c, 0.75), 0.2)
            self.circ(x, yb - L(42), L(9), RED, 3 * s)
        elif kind == "chef":
            for dx in (-36, 0, 36):
                self.circ(x + L(dx), yb - L(84), L(38), WHITE, 5 * s)
            self.rect(x - L(60), yb - L(76), L(120), L(80), WHITE, 5 * s)
            self.line([(x - L(60), yb - L(14)), (x + L(60), yb - L(14))], 3 * s, (210, 210, 220), 0.3)
        elif kind == "graduate":
            c = hc or (30, 30, 40)
            self._crown_dome(x, yb, s, 64, 50, c)
            self.poly([(x - L(100), yb - L(50)), (x, yb - L(80)), (x + L(100), yb - L(50)), (x, yb - L(24))], c, 5 * s,
                      wob=0.2)
            self.line([(x + L(2), yb - L(52)), (x + L(46), yb - L(48)), (x + L(70), yb + L(10))], 4 * s, YELLOW, 0.2)
        elif kind == "samurai":
            c = hc or (60, 50, 60)
            for sd in (-1, 1):
                self.poly([(x + sd * L(94), yb + L(2)), (x + sd * L(62), yb - L(32)), (x + sd * L(52), yb + L(10))],
                          c, 5 * s)
            self.poly([(x - L(10), yb - L(52)), (x - L(58), yb - L(122)), (x, yb - L(70)), (x + L(58), yb - L(122)),
                       (x + L(10), yb - L(52))], (232, 186, 60), 4 * s, wob=0.2)
            self._crown_dome(x, yb + L(4), s, 72, 66, c)
            self.line([(x - L(70), yb + L(4)), (x + L(70), yb + L(4))], 4 * s, (232, 186, 60), 0.3)
        elif kind == "hardhat":
            c = hc or YELLOW
            self._crown_dome(x, yb, s, 66, 64, c)
            self.line([(x, yb - L(62)), (x, yb - L(8))], 4 * s, darker(c, 0.8), 0.2)
            self.ell(x, yb - L(1), L(84), L(11), c, 5 * s)
        elif kind == "astronaut":
            self.circ(x, hy, L(90), (220, 235, 245), 6 * s)
            self.d.ellipse([(x - L(70)) * SS, (hy - L(70)) * SS, (x + L(70)) * SS, (hy + L(70)) * SS], fill=(255, 253, 247))
            self.circ(x, hy, hr, (255, 253, 247), 6 * s)
        elif kind == "mitre":
            c = hc or (250, 248, 240)
            self.poly([(x - L(62), yb + L(4)), (x + L(62), yb + L(4)), (x + L(50), yb - L(110)), (x, yb - L(152)),
                       (x - L(50), yb - L(110))], c, 6 * s, wob=0.3)
            self.line([(x, yb - L(4)), (x, yb - L(132))], 8 * s, (232, 186, 60), 0.2)
            self.line([(x - L(30), yb - L(76)), (x + L(30), yb - L(76))], 8 * s, (232, 186, 60), 0.2)
            self.line([(x - L(60), yb - L(6)), (x + L(60), yb - L(6))], 6 * s, (232, 186, 60), 0.2)

    def _glasses(self, x, hy, s):
        L = lambda v: v * s
        for ex in (-22, 22):
            self.circ(x + L(ex), hy + L(4), L(17), None, 4 * s)
        self.line([(x - L(5), hy + L(4)), (x + L(5), hy + L(4))], 4 * s, INK, 0.2)

    def _extra(self, e, x, hy, s, f):
        L = lambda v: v * s
        if e == "sweat":
            self.sweat(x + f * L(76), hy - L(30), s * 1.1)
        elif e == "blush":
            for ex in (-38, 38):
                self.ell(x + L(ex), hy + L(22), L(12), L(6), (245, 150, 150), 0)
        elif e == "tear":
            self.sweat(x - L(24), hy + L(30), s * 0.8)
        elif e == "vein":
            vx, vy = x + f * L(44), hy - L(44)
            for a, b in (((-10, -4), (-3, -4)), ((3, -4), (10, -4)), ((-10, 4), (-3, 4)), ((3, 4), (10, 4))):
                self.line([(vx + L(a[0]), vy + L(a[1] * 2.2)), (vx + L(b[0]) - L(1), vy + L(b[1]))], 5 * s, RED, 0.2)
        elif e in ("q", "?"):
            self.text("?", x + f * L(80), hy - L(110), 90 * s, INK, stroke=6 * s)
        elif e == "!":
            self.text("!", x + f * L(80), hy - L(110), 100 * s, RED, stroke=6 * s)
        elif e == "steam":
            for dx in (-55, 55):
                self.smoke(x + L(dx), hy - L(80), 0.45 * s, (235, 235, 240))
        elif e == "mustache":
            self._mustache(x, hy + L(32), s)
        elif e == "beard":
            self.chord(x - L(50), hy + L(0), x + L(50), hy + L(96), 0, 180, (90, 70, 55), 4 * s)
        elif e == "glasses":
            self._glasses(x, hy, s)
        elif e == "zzz":
            for k in range(3):
                self.text("z", x + f * L(70 + k * 26), hy - L(70 + k * 34), (34 + k * 10) * s, INK, stroke=4 * s, f="hand")

    def _prop(self, p, hands, s, flip, fdirs=None):
        L = lambda v: v * s
        if isinstance(p, (list, tuple)):
            kind, pcol = p[0], (to_color(p[1]) if len(p) > 1 else RED)
        else:
            kind, pcol = p, RED
        hx, hy = hands[1] if not flip else hands[0]
        sgn = -1 if flip else 1
        if kind == "sword":
            # held upright, or along the forearm when the arm is raised or thrust forward (slashing)
            ux, uy = sgn * 0.07, -1.0
            if fdirs:
                fx, fy = fdirs[1] if not flip else fdirs[0]
                if fy < 0.45:
                    n = math.hypot(fx, fy - 0.35) or 1
                    ux, uy = fx / n, (fy - 0.35) / n
            n = math.hypot(ux, uy) or 1
            ux, uy = ux / n, uy / n
            self.line([(hx, hy), (hx + ux * L(150), hy + uy * L(150))], 10 * s, (225, 228, 236), 0.2)
            self.line([(hx - uy * L(18), hy + ux * L(18)), (hx + uy * L(18), hy - ux * L(18))], 9 * s, YELLOW, 0.2)
        elif kind in ("hammer", "pickaxe", "shovel"):
            # tools follow the forearm when it swings, so hammering and digging read at a glance
            ux, uy = sgn * 0.25, -1.0
            if fdirs:
                fx, fy = fdirs[1] if not flip else fdirs[0]
                if fy < 0.6:
                    ux, uy = fx, fy - 0.3
            n = math.hypot(ux, uy) or 1
            ux, uy = ux / n, uy / n
            ln = L(120) if kind != "hammer" else L(95)
            ex, ey = hx + ux * ln, hy + uy * ln
            self.line([(hx - ux * L(16), hy - uy * L(16)), (ex, ey)], 8 * s, BROWN, 0.2)
            px, py = -uy, ux                       # across the handle
            if kind == "hammer":
                self.poly([(ex + px * L(30) - ux * L(6), ey + py * L(30) - uy * L(6)),
                           (ex + px * L(30) + ux * L(16), ey + py * L(30) + uy * L(16)),
                           (ex - px * L(22) + ux * L(16), ey - py * L(22) + uy * L(16)),
                           (ex - px * L(22) - ux * L(6), ey - py * L(22) - uy * L(6))], (120, 124, 136), 5 * s)
            elif kind == "pickaxe":
                self.line([(ex + px * L(52) - ux * L(26), ey + py * L(52) - uy * L(26)), (ex, ey + uy * L(6)),
                           (ex - px * L(52) - ux * L(26), ey - py * L(52) - uy * L(26))], 10 * s, (120, 124, 136), 0.2)
            else:
                self.poly([(ex - px * L(22), ey - py * L(22)), (ex + px * L(22), ey + py * L(22)),
                           (ex + px * L(18) + ux * L(40), ey + py * L(18) + uy * L(40)),
                           (ex + ux * L(52), ey + uy * L(52)),
                           (ex - px * L(18) + ux * L(40), ey - py * L(18) + uy * L(40))], (150, 154, 166), 5 * s)
        elif kind == "flag":
            self.line([(hx, hy + L(30)), (hx, hy - L(150))], 7 * s, BROWN, 0.2)
            self.poly([(hx, hy - L(150)), (hx + sgn * L(110), hy - L(130)), (hx, hy - L(95))], pcol, 5 * s)
        elif kind == "whiteflag":
            self.line([(hx, hy + L(30)), (hx, hy - L(150))], 7 * s, BROWN, 0.2)
            self.poly([(hx, hy - L(150)), (hx + sgn * L(100), hy - L(145)), (hx + sgn * L(95), hy - L(95)), (hx, hy - L(100))], WHITE, 5 * s)
        elif kind == "paper":
            self.rect(hx - L(10) if sgn > 0 else hx - L(80), hy - L(110), L(90), L(115), (255, 255, 250), 5 * s)
            x0 = hx + L(4) if sgn > 0 else hx - L(66)
            for i in range(4):
                self.line([(x0, hy - L(88) + L(i * 22)), (x0 + L(60), hy - L(88) + L(i * 22))], 4 * s, (150, 150, 160), 0.3)
        elif kind == "megaphone":
            self.poly([(hx, hy - L(8)), (hx + sgn * L(90), hy - L(48)), (hx + sgn * L(90), hy + L(40)), (hx, hy + L(8))], (230, 230, 240), 6 * s)
        elif kind == "teacup":
            self.rect(hx - L(22), hy - L(34), L(44), L(36), WHITE, 5 * s, r=L(6))
            self.d.arc([(hx + L(14)) * SS, (hy - L(28)) * SS, (hx + L(36)) * SS, (hy - L(6)) * SS], 270, 90, fill=INK, width=int(5 * s * SS))
        elif kind == "pointer":
            self.line([(hx, hy), (hx + sgn * L(150), hy - L(90))], 7 * s, BROWN, 0.2)
        elif kind == "can":
            self.rect(hx - L(26), hy - L(10), L(52), L(64), (200, 60, 50), 5 * s, r=L(6))
        elif kind == "bowl":
            self.chord(hx - L(36), hy - L(30), hx + L(36), hy + L(30), 0, 180, (240, 240, 240), 5 * s)
        elif kind == "spear":
            self.line([(hx, hy + L(60)), (hx, hy - L(190))], 7 * s, BROWN, 0.2)
            self.poly([(hx - L(14), hy - L(185)), (hx, hy - L(230)), (hx + L(14), hy - L(185))], (210, 212, 220), 4 * s)
        elif kind == "shield":
            c = pcol if isinstance(p, (list, tuple)) else (190, 60, 50)
            self.ell(hx, hy, L(46), L(60), c, 6 * s)
            self.circ(hx, hy, L(12), YELLOW, 4 * s)
        elif kind == "torch":
            self.line([(hx, hy + L(30)), (hx + sgn * L(8), hy - L(70))], 9 * s, BROWN, 0.2)
            self.flame(hx + sgn * L(8), hy - L(66), 0.6 * s)
        elif kind == "book":
            self.rect(hx - L(40), hy - L(60), L(80), L(64), (170, 60, 60), 5 * s, r=L(6))
        elif kind == "scroll":
            self.rect(hx - L(50), hy - L(70), L(100), L(70), (255, 250, 232), 5 * s, r=L(14))
        elif kind == "money":
            self.blob(hx, hy - L(30), L(40), L(36), (215, 190, 120), 5 * s, rough=0.08, seed=5)
            self.text("$", hx, hy - L(28), 44 * s, (60, 130, 70))


__all__ = ["Pen", "ARMS", "LEGS", "MOUTHS", "EYES", "EXTRAS", "HELD", "HATS", "KIND_ALIASES", "resolve_kind"]
