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
}
LEGS = {
    "stand": ((12, 0), (12, 0)),
    "walk": ((28, 10), (-12, -25)),
    "run": ((45, 60), (-35, -30)),
    "wide": ((24, 0), (24, 0)),
    "jump": ((40, 70), (40, 70)),
}

MOUTHS = ("smile", "grin", "open", "scream", "frown", "smirk", "wavy", "flat", "o")
EYES = ("dot", "wide", "happy", "closed", "angry", "sad", "worried", "dead")
EXTRAS = ("sweat", "blush", "tear", "vein", "q", "!", "steam", "mustache", "beard", "glasses", "zzz")
HELD = ("sword", "flag", "whiteflag", "paper", "megaphone", "teacup", "pointer", "can", "bowl", "spear",
        "shield", "torch", "book", "scroll", "money")

# hats ("kind"). Many nation names are aliases of a hat.
HATS = ("japan", "headband", "army", "navy", "america", "tophat", "britain", "bowler", "china", "ussr", "furhat",
        "germany", "helmet", "italy", "dutch", "france", "beret", "marine", "student", "pilot", "glasses",
        "headphones", "tophat_gray", "civ", "cap", "crown", "roman", "laurel", "viking", "pirate", "tricorn",
        "bicorne", "cowboy", "knight", "wizard", "pharaoh", "turban", "chef", "graduate", "samurai", "hardhat",
        "astronaut", "mitre", "shako", "bearskin", "none")

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
              col=INK, hat_color=None, head=(0, 0), lean=0):
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
        hands = []
        for side, (a, b) in zip((-1, 1), arms):
            ar = math.radians(a)
            elbow = (sh[0] + side * math.sin(ar) * L(58), sh[1] + math.cos(ar) * L(58))
            fr = math.radians(a + b)
            hand = (elbow[0] + side * math.sin(fr) * L(56), elbow[1] + math.cos(fr) * L(56))
            self.line([sh, elbow, hand], lw, col, 0.6)
            self.circ(hand[0], hand[1], L(9), col, 0)
            hands.append(hand)
        if prop:
            self._prop(prop, hands, s, flip)
        self.circ(hx, hy, hr, (255, 253, 247), 7 * s)
        f = -1 if flip else 1
        self._hat(kind, hx, hy, hr, s, f, to_color(hat_color, None) if hat_color else None)
        self._face(hx, hy, s, mouth, "closed" if blink else eyes, look * f if look else 0, f, kind)
        for e in extra or ():
            self._extra(e, hx, hy, s, f)
        return hands

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

    def _hat(self, kind, x, hy, hr, s, f, hc=None):
        L = lambda v: v * s
        if kind in ("japan", "headband"):
            band = hc if (hc and kind == "headband") else WHITE
            yb = hy - L(30)
            self.poly([(x - L(60), yb - L(12)), (x + L(60), yb - L(12)), (x + L(63), yb + L(10)), (x - L(63), yb + L(10))], band, 5 * s, wob=0.4)
            if kind == "japan" or not hc:
                self.circ(x, yb - L(1), L(10), RED, 0)
            kx = x - f * L(62)
            self.line([(kx, yb), (kx - f * L(40), yb + L(28))], 9 * s, band, 0.3)
            self.line([(kx, yb), (kx - f * L(46), yb + L(4))], 9 * s, band, 0.3)
            self.line([(kx, yb), (kx - f * L(40), yb + L(28))], 2 * s, INK, 0.3)
        elif kind in ("army", "cap"):
            c = hc or (122, 128, 74)
            self._dome(x, hy, s, -66, -98, 66, 10, c)
            self.rect(x - L(68), hy - L(46), L(136), L(13), darker(c, 0.77), 5 * s)
            self.poly([(x + f * L(10), hy - L(38)), (x + f * L(84), hy - L(28)), (x + f * L(60), hy - L(40))], darker(c, 0.5), 4 * s)
            if kind == "army":
                self.circ(x, hy - L(62), L(7), YELLOW, 3 * s)
        elif kind == "navy":
            self.ell(x, hy - L(62), L(74), L(22), WHITE, 6 * s)
            self.rect(x - L(62), hy - L(58), L(124), L(18), INK, 0)
            self.rect(x - L(56), hy - L(54), L(112), L(6), YELLOW, 0)
            self.poly([(x + f * L(10), hy - L(42)), (x + f * L(80), hy - L(30)), (x + f * L(55), hy - L(44))], INK, 3 * s)
        elif kind in ("america", "tophat", "tophat_gray"):
            c = hc or (NAVY if kind == "america" else (60, 60, 66) if kind == "tophat_gray" else (40, 40, 46))
            if kind == "tophat_gray":
                self.rect(x - L(80), hy - L(70), L(160), L(18), c, 5 * s, r=L(8))
                self.rect(x - L(46), hy - L(150), L(92), L(86), c, 5 * s, r=L(8))
            else:
                self.rect(x - L(86), hy - L(70), L(172), L(20), c, 6 * s, r=L(9))
                self.rect(x - L(50), hy - L(170), L(100), L(104), c, 6 * s, r=L(8))
                self.rect(x - L(50), hy - L(96), L(100), L(17), RED if kind == "america" else darker(c, 0.6), 5 * s)
            if kind == "america":
                self.poly([(x - L(16), hy + L(64)), (x, hy + L(72)), (x + L(16), hy + L(64)), (x + L(16), hy + L(82)), (x, hy + L(74)), (x - L(16), hy + L(82))], RED, 4 * s)
        elif kind == "shako":
            # Napoleonic infantry: a tall cylinder (a bit wider on top), visor, plate and a red plume
            c = hc or (34, 36, 48)
            self.poly([(x - L(48), hy - L(52)), (x - L(56), hy - L(150)), (x + L(56), hy - L(150)), (x + L(48), hy - L(52))],
                      c, 6 * s, INK, 0.3)
            self.ell(x + f * L(18), hy - L(52), L(54), L(12), INK, 0)
            self.circ(x, hy - L(100), L(14), YELLOW, 4 * s)
            self.ell(x - f * L(30), hy - L(172), L(12), L(28), RED, 4 * s)
        elif kind == "bearskin":
            c = hc or (26, 26, 30)
            self.ell(x, hy - L(120), L(70), L(92), c, 6 * s, INK)
            for k in range(7):
                ang = math.pi * (0.15 + 0.7 * k / 6)
                px, py = x - math.cos(ang) * L(68), hy - L(120) - math.sin(ang) * L(88)
                self.line([(px, py), (px - math.cos(ang) * L(9), py - math.sin(ang) * L(9))], 4 * s, (70, 70, 76), 0.6)
            self.ell(x - f * L(48), hy - L(150), L(10), L(26), RED, 3 * s)
        elif kind in ("britain", "bowler"):
            c = hc or (40, 40, 46)
            self._dome(x, hy, s, -58, -120, 58, -10, c)
            self.rect(x - L(80), hy - L(70), L(160), L(14), c, 5 * s, r=L(7))
        elif kind == "china":
            self._dome(x, hy, s, -66, -100, 66, 4, (78, 92, 110))
            self.rect(x - L(68), hy - L(50), L(136), L(13), (56, 66, 80), 5 * s)
            self.poly([(x + f * L(10), hy - L(42)), (x + f * L(84), hy - L(30)), (x + f * L(60), hy - L(44))], (40, 46, 56), 4 * s)
            self.circ(x, hy - L(68), L(11), (40, 70, 160), 3 * s)
            self.circ(x, hy - L(68), L(5), WHITE, 0)
        elif kind in ("ussr", "furhat"):
            c = hc or (120, 86, 60)
            self.rect(x - L(70), hy - L(110), L(140), L(70), c, 6 * s, r=L(22))
            self.rect(x - L(78), hy - L(56), L(30), L(70), c, 5 * s, r=L(10))
            self.rect(x + L(48), hy - L(56), L(30), L(70), c, 5 * s, r=L(10))
            if kind == "ussr":
                self.circ(x, hy - L(82), L(12), RED, 3 * s)
        elif kind in ("germany", "helmet"):
            c = hc or (112, 118, 112)
            self._dome(x, hy, s, -74, -104, 74, 30, c)
            if kind == "germany":
                self.poly([(x - L(74), hy - L(37)), (x - L(84), hy - L(10)), (x - L(62), hy - L(18))], c, 5 * s)
                self.poly([(x + L(74), hy - L(37)), (x + L(84), hy - L(10)), (x + L(62), hy - L(18))], c, 5 * s)
        elif kind == "italy":
            self._dome(x, hy, s, -60, -100, 60, -10, (50, 70, 50))
            self.rect(x - L(84), hy - L(62), L(168), L(13), (50, 70, 50), 5 * s, r=L(6))
            for k in range(4):
                self.line([(x - f * L(30), hy - L(70)), (x - f * L(110 + k * 10), hy - L(110 - k * 22))], 6 * s, (30, 40, 30), 0.4)
        elif kind == "dutch":
            self._dome(x, hy, s, -64, -96, 64, 6, ORANGE)
            self.poly([(x + f * L(14), hy - L(46)), (x + f * L(90), hy - L(36)), (x + f * L(62), hy - L(50))], (210, 120, 40), 4 * s)
        elif kind in ("france", "beret"):
            c = hc or (52, 72, 150)
            self.ell(x - f * L(8), hy - L(58), L(66), L(22), c, 6 * s)
            self.line([(x - f * L(8), hy - L(78)), (x - f * L(4), hy - L(96))], 6 * s, INK, 0.2)
        elif kind == "marine":
            self._dome(x, hy, s, -74, -98, 74, 24, (102, 112, 70))
        elif kind == "student":
            self._dome(x, hy, s, -64, -94, 64, 6, (30, 30, 40))
            self.poly([(x + f * L(14), hy - L(46)), (x + f * L(86), hy - L(36)), (x + f * L(62), hy - L(50))], (20, 20, 26), 4 * s)
            self.circ(x, hy - L(64), L(7), YELLOW, 2 * s)
        elif kind == "pilot":
            self._dome(x, hy, s, -68, -80, 68, 40, BROWN)
            self.rect(x - L(48), hy - L(52), L(40), L(26), (170, 210, 235), 4 * s, r=L(8))
            self.rect(x + L(8), hy - L(52), L(40), L(26), (170, 210, 235), 4 * s, r=L(8))
        elif kind == "glasses":
            self._glasses(x, hy, s)
        elif kind == "headphones":
            self._glasses(x, hy, s)
            self.d.arc([(x - L(72)) * SS, (hy - L(80)) * SS, (x + L(72)) * SS, (hy + L(40)) * SS], 180, 360, fill=INK, width=int(8 * s * SS))
            self.rect(x - L(84), hy - L(14), L(24), L(44), (70, 70, 80), 4 * s, r=L(8))
            self.rect(x + L(60), hy - L(14), L(24), L(44), (70, 70, 80), 4 * s, r=L(8))
        elif kind == "crown":
            c = hc or (240, 200, 70)
            yb = hy - L(48)
            self.poly([(x - L(56), yb + L(8)), (x + L(56), yb + L(8)), (x + L(64), yb - L(70)), (x + L(30), yb - L(30)),
                       (x, yb - L(84)), (x - L(30), yb - L(30)), (x - L(64), yb - L(70))], c, 6 * s, wob=0.3)
            for dx in (-32, 0, 32):
                self.circ(x + L(dx), yb - L(6), L(7), RED, 2 * s)
        elif kind == "roman":
            c = hc or (200, 170, 90)
            crest = RED
            self.ell(x, hy - L(104), L(62), L(36), crest, 6 * s)
            for k in range(-40, 50, 20):
                self.line([(x + L(k), hy - L(112)), (x + L(k * 1.15), hy - L(132 - abs(k) * 0.4))], 3 * s, darker(crest, 0.7), 0.2)
            self._dome(x, hy, s, -70, -100, 70, 20, c)
            self.rect(x - f * L(72) - L(12), hy - L(30), L(24), L(60), c, 5 * s, r=L(8))
        elif kind == "laurel":
            for deg in (165, 145, 125, 105, 75, 55, 35, 15):
                a = math.radians(deg)
                self.ell(x + L(68) * math.cos(a), hy - L(62) * math.sin(a), L(15), L(8), (110, 170, 90), 3 * s)
        elif kind == "viking":
            c = hc or (170, 170, 180)
            for side in (-1, 1):
                self.poly([(x + side * L(52), hy - L(50)), (x + side * L(100), hy - L(90)), (x + side * L(98), hy - L(150)),
                           (x + side * L(78), hy - L(85)), (x + side * L(40), hy - L(62))], (245, 240, 220), 5 * s, wob=0.3)
            self._dome(x, hy, s, -68, -104, 68, 18, c)
            self.rect(x - L(70), hy - L(48), L(140), L(14), BROWN, 5 * s)
            self.rect(x - L(7), hy - L(44), L(14), L(48), c, 4 * s)
        elif kind in ("pirate", "tricorn"):
            c = hc or ((30, 30, 36) if kind == "pirate" else (60, 50, 50))
            self.poly([(x - L(96), hy - L(50)), (x, hy - L(70)), (x + L(96), hy - L(50)), (x + L(56), hy - L(124)),
                       (x, hy - L(104)), (x - L(56), hy - L(124))], c, 6 * s, wob=0.3)
            if kind == "pirate":
                self.circ(x, hy - L(86), L(11), WHITE, 3 * s)
                self.line([(x + L(15), hy - L(4)), (x + L(55), hy - L(40))], 4 * s, INK, 0.2)
                self.circ(x + L(22), hy + L(4), L(14), INK, 0)
        elif kind == "bicorne":
            c = hc or (30, 30, 40)
            self.chord(x - L(110), hy - L(120), x + L(110), hy - L(10), 180, 360, c, 6 * s)
            self.circ(x + f * L(40), hy - L(70), L(14), (230, 230, 240), 3 * s)
            self.circ(x + f * L(40), hy - L(70), L(7), RED, 0)
        elif kind == "cowboy":
            c = hc or (170, 120, 70)
            self.ell(x, hy - L(54), L(110), L(20), c, 6 * s)
            self._dome(x, hy, s, -50, -150, 50, -40, c)
            self.rect(x - L(48), hy - L(74), L(96), L(12), darker(c, 0.6), 0)
        elif kind == "knight":
            c = hc or (190, 192, 200)
            self.rect(x - L(70), hy - L(84), L(140), L(150), c, 6 * s, r=L(30))
            self.rect(x - L(52), hy - L(8), L(104), L(12), INK, 0)
            self.line([(x, hy + L(10)), (x, hy + L(50))], 5 * s, darker(c, 0.6), 0.2)
            self.chord(x - L(30), hy - L(140), x + L(30), hy - L(60), 180, 360, RED, 4 * s)
            return  # face hidden by helm visor (eyes still drawn on top)
        elif kind == "wizard":
            c = hc or (80, 70, 150)
            self.poly([(x - L(80), hy - L(46)), (x + L(80), hy - L(46)), (x + f * L(20), hy - L(200))], c, 6 * s, wob=0.3)
            self.ell(x, hy - L(46), L(92), L(14), c, 5 * s)
            self.text("*", x - L(10), hy - L(100), 40 * s, YELLOW)
        elif kind == "pharaoh":
            c1, c2 = (60, 90, 170), (232, 186, 60)
            self.poly([(x - L(62), hy - L(40)), (x + L(62), hy - L(40)), (x + L(92), hy + L(70)), (x + L(56), hy + L(70)),
                       (x + L(52), hy), (x - L(52), hy), (x - L(56), hy + L(70)), (x - L(92), hy + L(70))], c2, 6 * s, wob=0.3)
            for k in range(3):
                yy = hy - L(28) + L(k * 30)
                self.line([(x - L(64 + k * 8), yy), (x - L(54), yy)], 6 * s, c1, 0.2)
                self.line([(x + L(54), yy), (x + L(64 + k * 8), yy)], 6 * s, c1, 0.2)
            self._dome(x, hy, s, -64, -100, 64, 0, c2)
            self.line([(x - L(60), hy - L(55)), (x + L(60), hy - L(55))], 6 * s, c1, 0.2)
            self.circ(x, hy - L(70), L(9), (60, 160, 90), 3 * s)
        elif kind == "turban":
            c = hc or (240, 236, 220)
            self.ell(x, hy - L(58), L(72), L(40), c, 6 * s)
            self.line([(x - L(60), hy - L(66)), (x + L(50), hy - L(42))], 4 * s, darker(c, 0.75), 0.2)
            self.circ(x, hy - L(76), L(9), RED, 3 * s)
        elif kind == "chef":
            for dx in (-34, 0, 34):
                self.circ(x + L(dx), hy - L(118), L(36), WHITE, 5 * s)
            self.rect(x - L(52), hy - L(110), L(104), L(64), WHITE, 5 * s)
        elif kind == "graduate":
            c = hc or (30, 30, 40)
            self._dome(x, hy, s, -54, -90, 54, -20, c)
            self.poly([(x - L(96), hy - L(80)), (x, hy - L(110)), (x + L(96), hy - L(80)), (x, hy - L(56))], c, 5 * s, wob=0.2)
            self.line([(x + L(40), hy - L(80)), (x + L(70), hy - L(30))], 4 * s, YELLOW, 0.2)
        elif kind == "samurai":
            c = hc or (60, 50, 60)
            self._dome(x, hy, s, -68, -100, 68, 16, c)
            self.poly([(x - L(92), hy - L(30)), (x - L(60), hy - L(60)), (x - L(50), hy - L(20))], c, 5 * s)
            self.poly([(x + L(92), hy - L(30)), (x + L(60), hy - L(60)), (x + L(50), hy - L(20))], c, 5 * s)
            self.poly([(x - L(10), hy - L(84)), (x - L(56), hy - L(150)), (x, hy - L(100)), (x + L(56), hy - L(150)), (x + L(10), hy - L(84))],
                      (232, 186, 60), 4 * s, wob=0.2)
        elif kind == "hardhat":
            c = hc or YELLOW
            self._dome(x, hy, s, -66, -100, 66, 8, c)
            self.rect(x - L(80), hy - L(52), L(160), L(12), c, 5 * s, r=L(6))
        elif kind == "astronaut":
            self.circ(x, hy, L(90), (220, 235, 245), 6 * s)
            self.d.ellipse([(x - L(70)) * SS, (hy - L(70)) * SS, (x + L(70)) * SS, (hy + L(70)) * SS], fill=(255, 253, 247))
            self.circ(x, hy, hr, (255, 253, 247), 6 * s)
        elif kind == "mitre":
            c = hc or (250, 248, 240)
            self.poly([(x - L(56), hy - L(52)), (x + L(56), hy - L(52)), (x + L(46), hy - L(150)), (x, hy - L(190)),
                       (x - L(46), hy - L(150))], c, 6 * s, wob=0.3)
            self.line([(x, hy - L(60)), (x, hy - L(170))], 8 * s, (232, 186, 60), 0.2)
            self.line([(x - L(28), hy - L(120)), (x + L(28), hy - L(120))], 8 * s, (232, 186, 60), 0.2)

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

    def _prop(self, p, hands, s, flip):
        L = lambda v: v * s
        if isinstance(p, (list, tuple)):
            kind, pcol = p[0], (to_color(p[1]) if len(p) > 1 else RED)
        else:
            kind, pcol = p, RED
        hx, hy = hands[1] if not flip else hands[0]
        sgn = -1 if flip else 1
        if kind == "sword":
            self.line([(hx, hy), (hx + sgn * L(10), hy - L(150))], 10 * s, (225, 228, 236), 0.2)
            self.line([(hx - L(18), hy - L(4)), (hx + L(18), hy + L(2))], 9 * s, YELLOW, 0.2)
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
