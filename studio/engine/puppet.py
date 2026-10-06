"""Animated stickmen ("puppets").

A puppet is re-posed every frame instead of being one frozen drawing:
- life: it breathes (small bob), its arms sway a little, it blinks at random moments and glances around;
- talk: the mouth flaps while it speaks (speech bubbles), with a small head bob;
- actions: walk, run, jump, wave, point, cheer, nod, shake head, shrug, think, facepalm, tremble, lean, bow,
  turn, faint, laugh, angry, cry, dance, look, sneak...

Poses are rounded (a few degrees, whole pixels) and each distinct pose is drawn once on a small canvas and
cached, so a scene usually needs only a few dozen drawings per character.
"""
import math
import random

from PIL import Image

from .doodle import SS, shrink
from .pen import Pen, ARMS, LEGS, MOUNTS

LOOKABLE = ("dot", "wide", "angry", "sad", "worried")

# action name -> default duration in seconds
ACTIONS = {
    "walk": 2.0, "run": 1.2, "sneak": 2.5, "jump": 0.6, "hop": 0.4, "wave": 1.6, "point": 1.6, "cheer": 1.6,
    "celebrate": 2.0, "nod": 1.0, "shake_head": 1.0, "shrug": 1.4, "think": 2.0, "facepalm": 1.6, "tremble": 2.0,
    "lean": 1.6, "bow": 1.4, "turn": 0.0, "faint": 0.6, "laugh": 1.6, "angry": 1.6, "cry": 2.0, "dance": 2.4,
    "look": 1.6, "talk": 2.0, "surprise": 0.8, "salute": 1.6, "fight": 1.6, "slash": 1.7,
}
ACTION_ALIASES = {
    "walks": "walk", "move": "walk", "go": "walk", "stroll": "walk", "march": "walk", "running": "run",
    "run_away": "run", "flee": "run", "charge": "run", "jumps": "jump", "leap": "jump", "bounce": "hop",
    "waves": "wave", "hello": "wave", "bye": "wave", "points": "point", "cheers": "cheer", "yay": "cheer",
    "victory": "celebrate", "party": "celebrate", "yes": "nod", "agree": "nod", "no": "shake_head",
    "shake": "shake_head", "disagree": "shake_head", "dunno": "shrug", "ponder": "think", "wonder": "think",
    "doh": "facepalm", "scared": "tremble", "shiver": "tremble", "fear": "tremble", "panic": "tremble",
    "peek": "lean", "bend": "lean", "kneel": "bow", "flip": "turn", "turn_around": "turn", "fall": "faint",
    "die": "faint", "collapse": "faint", "giggle": "laugh", "rage": "angry", "stomp": "angry", "sob": "cry",
    "sad": "cry", "glance": "look", "speak": "talk", "say": "talk", "shout": "talk", "gasp": "surprise",
    "shock": "surprise", "punch": "fight", "attack": "fight", "duel": "slash", "swordfight": "slash",
    "sword_fight": "slash", "fence": "slash", "fencing": "slash", "clash": "slash", "stab": "slash",
    "swing": "slash", "strike": "slash", "slashes": "slash", "parry": "slash",
}


def resolve_action(name):
    n = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    n = ACTION_ALIASES.get(n, n)
    return n if n in ACTIONS else None


def ease(q):
    q = min(max(q, 0.0), 1.0)
    return q * q * (3 - 2 * q)


def _arms(v):
    if isinstance(v, str):
        v = ARMS.get(v, ARMS["down"])
    return [list(v[0]), list(v[1])]


def _legs(v):
    if isinstance(v, str):
        v = LEGS.get(v, LEGS["stand"])
    return [list(v[0]), list(v[1])]


class Puppet:
    """One animated character. x, y = point between the feet at the start; s = scale."""

    def __init__(self, x, y, s, pose, actions=(), talk=(), life=True, seed=0, mood="fun", speed=1.0):
        self.x, self.y, self.s = float(x), float(y), float(s)
        self.base = dict(pose)
        self.base["arms"] = _arms(self.base.get("arms", "down"))
        self.base["legs"] = _legs(self.base.get("legs", "stand"))
        self.actions = sorted(actions, key=lambda a: a["t0"])   # [{act, t0, dur, dx, dy, dir, ...}] in seconds
        self.talk = list(talk)                                  # [(t0, t1)] seconds
        self.life = life
        self.mood = mood
        self.speed = speed
        self.rng = random.Random(seed)
        self.phase = self.rng.uniform(0, 6.28)
        # blink and glance timetables (seconds), random but fixed for this character
        t, self.blinks = self.rng.uniform(0.6, 2.5), []
        while t < 120:
            self.blinks.append(t)
            t += self.rng.uniform(2.2, 5.0) if mood != "tense" else self.rng.uniform(1.5, 3.5)
        t, self.glances = self.rng.uniform(1.0, 3.0), []
        while t < 120:
            self.glances.append((t, self.rng.choice((-1, 1, 0, -1, 1)), self.rng.uniform(0.8, 2.0)))
            t += self.rng.uniform(2.0, 5.0)
        self.cache = {}
        self.ride = MOUNTS.get(self.base.get("ride")) and self.base.get("ride")
        if self.ride:
            self.base["legs"] = _legs("stand" if MOUNTS[self.ride]["stand"] else "sit")
        big = 1.35 if self.ride else 1.0
        self.cw, self.ch = 820 * s * big, 820 * s * big   # local canvas (screen px)
        self.foot = (self.cw / 2, self.ch - 60 * s)      # where the ground point is drawn on it

    # ---------------------------------------------------------------- pose at time t
    def state(self, t):
        """Returns (pose dict, dx, dy, rot) for time t (seconds into the scene)."""
        p = dict(self.base)
        p["arms"] = [list(a) for a in self.base["arms"]]
        p["legs"] = [list(l) for l in self.base["legs"]]
        p["extra"] = tuple(self.base.get("extra") or ())
        p["head"] = [0.0, 0.0]
        p["lean"] = 0.0
        p["blink"] = False
        dx = dy = rot = 0.0
        flip = bool(self.base.get("flip"))
        moving = False
        # completed actions leave lasting changes (a walk ends somewhere else, a turn stays turned, ...)
        for a in self.actions:
            if t < a["t0"]:
                break
            q = (t - a["t0"]) / a["dur"] if a["dur"] > 0 else 1.0
            act = a["act"]
            if act in ("walk", "run", "sneak"):
                e = ease(q) if act != "run" else min(1.0, max(0.0, q))
                dx += a.get("dx", 0) * min(e, 1.0)
                dy += a.get("dy", 0) * min(e, 1.0)
                if q < 1:
                    moving = True
                    flip = a["dx"] < 0 if a.get("dx") else flip
                    self._walk(p, t - a["t0"], act)
                    if act == "run":
                        p["lean"] = 14 * (-1 if flip else 1)
                    if act == "sneak":
                        p["lean"] = 10 * (-1 if flip else 1)
                        p["legs"] = [[30, 50], [-10, 40]]
                elif a.get("dx"):
                    flip = a["dx"] < 0          # ends facing the way it walked
            elif act == "turn":
                flip = not flip
            elif act == "faint":
                d = -1 if flip else 1
                rot = -88 * d * ease(min(q, 1.0))
                p["eyes"] = "dead"
                p["mouth"] = "o"
            elif q < 1:
                dx2, dy2 = self._act(p, act, q, t - a["t0"], a, flip)
                dx += dx2
                dy += dy2
        p["flip"] = flip
        if self.ride:
            # a rider keeps their seat; moving means the mount gallops (a bouncy ride)
            p["legs"] = [list(l) for l in self.base["legs"]]
            if moving:
                dy -= abs(math.sin(2 * math.pi * t * 2.4)) * 12 * self.s
        # talking: mouth flaps and the head bobs a little
        talking = any(t0 <= t < t1 for t0, t1 in self.talk)
        if talking:
            k = int(t * 9 + self.phase * 3)
            p["mouth"] = ("open", "o", self.base.get("mouth", "smile"), "open", "grin")[k % 5]
            p["head"][1] += 2.5 * math.sin(t * 11)
        # life: breathing, arm sway, blinks, glances
        if self.life and not moving and not rot:
            speed = 1.6 if self.mood == "tense" else (0.7 if self.mood == "somber" else 1.0)
            dy += 3.0 * self.s * math.sin(2 * math.pi * t * speed / 1.6 + self.phase)
            sway = 4.0 * math.sin(2 * math.pi * t * speed / 3.1 + self.phase)
            for arm in p["arms"]:
                if abs(arm[0]) < 60:            # only relaxed arms sway; poses held up stay put
                    arm[0] += sway
            if self.mood == "somber":
                p["head"][1] += 4
        if any(b <= t < b + 0.13 for b in self.blinks) and p.get("eyes") in LOOKABLE + (None,):
            p["blink"] = True
        if p.get("look") in (None, 0) and p.get("eyes", "dot") in LOOKABLE and not talking:
            for g0, look, gd in self.glances:
                if g0 <= t < g0 + gd:
                    p["look"] = look
                    break
                if g0 > t:
                    break
        return p, dx, dy, rot

    def _walk(self, p, el, act):
        steps = {"walk": 1.9, "run": 3.2, "sneak": 1.2}[act]
        amp = {"walk": 26, "run": 42, "sneak": 18}[act]
        ph = 2 * math.pi * el * steps * self.speed
        sw = math.sin(ph)
        # the same angle on both legs swings them in opposite directions (one forward, one back)
        p["legs"] = [[amp * sw, max(0, 32 * math.sin(ph + 1.2))], [amp * sw, max(0, 32 * math.sin(ph + 1.2 + math.pi))]]
        if p.get("prop") is None or act == "run":
            p["arms"] = [[20 - amp * 0.8 * sw, 25 if act == "run" else 15], [20 - amp * 0.8 * sw, 25 if act == "run" else 15]]
        p["head"][1] += -abs(math.sin(ph)) * (6 if act == "run" else 3)

    def _act(self, p, act, q, el, a, flip):
        """Pose for one in-progress action. Returns extra (dx, dy)."""
        s = self.s
        dx = dy = 0.0
        fwd = -1 if flip else 1
        osc = lambda hz, amp: amp * math.sin(2 * math.pi * hz * el)
        if act in ("jump", "hop"):
            h = (130 if act == "jump" else 55)
            dy = -h * 4 * q * (1 - q)
            if 0.15 < q < 0.85:
                p["legs"] = [[30, 55], [30, 55]] if act == "jump" else [[18, 25], [18, 25]]
                p["arms"] = [[110, 20], [110, 20]] if act == "jump" else p["arms"]
        elif act == "wave":
            p["arms"][1] = [150, 25 + osc(2.8, 30)]
            p["mouth"] = p.get("mouth") if p.get("mouth") not in (None, "flat", "frown") else "smile"
        elif act == "point":
            jab = 8 * math.exp(-el * 6) * math.sin(el * 30)
            p["arms"][1] = [95 + jab, -5]
            p["look"] = 1
        elif act in ("cheer", "celebrate"):
            p["arms"] = [[155 + osc(3, 12), 15], [155 - osc(3, 12), 15]]
            p["mouth"] = "grin"
            p["eyes"] = "happy"
            if act == "celebrate":
                dy = -40 * abs(math.sin(2 * math.pi * 1.6 * el))
        elif act == "nod":
            p["head"][1] += 7 + 7 * math.sin(2 * math.pi * 2.4 * el)
        elif act == "shake_head":
            p["head"][0] += 8 * math.sin(2 * math.pi * 2.8 * el)
            p["mouth"] = "frown" if p.get("mouth") in (None, "smile", "grin") else p.get("mouth")
        elif act == "shrug":
            k = math.sin(math.pi * min(q * 1.6, 1.0))
            p["arms"] = [[20 + 50 * k, 15 + 60 * k], [20 + 50 * k, 15 + 60 * k]]
            p["head"][1] += 4 * k
            p["mouth"] = "flat"
            p["eyes"] = "sad" if p.get("eyes") == "dot" else p.get("eyes")
        elif act == "think":
            p["arms"][1] = [35, -150]
            p["look"] = -1
            p["mouth"] = "flat"
            p["extra"] = tuple(p["extra"]) + (("q",) if q > 0.3 and "q" not in p["extra"] else ())
        elif act == "facepalm":
            p["arms"][1] = [40, -150]
            p["head"][1] += 6
            p["eyes"] = "closed"
            p["mouth"] = "frown"
        elif act == "tremble":
            dx = 2.5 if int(el * 22) % 2 else -2.5
            p["eyes"] = "wide"
            p["mouth"] = "wavy"
            if "sweat" not in p["extra"]:
                p["extra"] = tuple(p["extra"]) + ("sweat",)
        elif act == "lean":
            k = math.sin(math.pi * min(q * 1.25, 1.0))
            p["lean"] = (a.get("amount") or 28) * fwd * k
            p["head"][1] += 10 * k
        elif act == "bow":
            k = math.sin(math.pi * q)
            p["lean"] = 26 * fwd * k
            p["head"][1] += 26 * k
            p["eyes"] = "closed" if k > 0.5 else p.get("eyes")
        elif act == "laugh":
            p["mouth"] = ("grin", "open")[int(el * 8) % 2]
            p["eyes"] = "happy"
            dy = -10 * abs(math.sin(2 * math.pi * 3 * el))
            p["head"][1] += 3 * math.sin(2 * math.pi * 6 * el)
        elif act == "angry":
            p["eyes"] = "angry"
            p["mouth"] = ("scream", "frown")[int(el * 5) % 2]
            p["arms"] = [[40, -60], [40, -60]]
            dy = -18 * abs(math.sin(2 * math.pi * 2.5 * el))
            if "vein" not in p["extra"]:
                p["extra"] = tuple(p["extra"]) + ("vein",)
        elif act == "cry":
            p["eyes"] = "sad"
            p["mouth"] = "wavy"
            p["head"][1] += 8
            p["arms"] = [[30, -140], [30, -140]] if q > 0.2 else p["arms"]
            if "tear" not in p["extra"]:
                p["extra"] = tuple(p["extra"]) + ("tear",)
            dy = 2 * math.sin(2 * math.pi * 4 * el)
        elif act == "dance":
            k = int(el * 3) % 2
            p["arms"] = [[150, 20], [20, 15]] if k else [[20, 15], [150, 20]]
            p["legs"] = [[20, 0], [-10, 30]] if k else [[-10, 30], [20, 0]]
            dy = -20 * abs(math.sin(2 * math.pi * 1.5 * el))
            p["mouth"] = "grin"
        elif act == "look":
            p["look"] = a.get("dir") or 1
        elif act == "talk":
            p["mouth"] = ("open", "o", "smile", "open", "grin")[int(el * 9) % 5]
            p["head"][1] += 2.5 * math.sin(el * 11)
            p["arms"][1] = [60 + osc(1.2, 15), 30]
        elif act == "surprise":
            p["eyes"] = "wide"
            p["mouth"] = "o"
            dy = -30 * 4 * q * (1 - q)
            if "!" not in p["extra"]:
                p["extra"] = tuple(p["extra"]) + ("!",)
        elif act == "salute":
            p["arms"][1] = [140, -120]
            p["mouth"] = "flat"
        elif act == "slash" or (act == "fight" and p.get("prop") in ("sword", "spear")):
            # raise the sword, then strike forward (one cycle every 0.42 s; see action_fx.SLASH_CYCLE)
            ph = (el % 0.42) / 0.42
            up = ph < 0.45
            p["arms"] = [[45, -60], [128, 22] if up else [88, -14]]
            p["eyes"] = "angry"
            p["mouth"] = "frown" if up else "scream"
            if p.get("prop") is None:
                p["prop"] = "sword"
            dx = (0 if up else 18) * fwd
        elif act == "fight":
            k = int(el * 4) % 2
            p["arms"] = [[100, 10], [40, 10]] if k else [[40, 10], [100, 10]]
            p["eyes"] = "angry"
            p["mouth"] = "scream"
            dx = 10 * fwd * k
        return dx * s, dy * s

    # ---------------------------------------------------------------- drawing
    @staticmethod
    def _key(p):
        r = lambda v, step=3: int(round(v / step))
        return (tuple(r(v) for arm in p["arms"] for v in arm), tuple(r(v) for leg in p["legs"] for v in leg),
                p.get("mouth"), p.get("eyes"), p.get("look") or 0, bool(p.get("flip")), bool(p.get("blink")),
                tuple(p.get("extra") or ()), r(p["head"][0], 1), r(p["head"][1], 1), r(p.get("lean", 0), 2))

    def image(self, p, kind, seed, rot=0):
        """(RGBA image, (x, y) offset of its top-left from the feet point)."""
        key = (self._key(p), int(round(rot / 4)) if rot else 0, p.get("coat"), self.ride)
        hit = self.cache.get(key)
        if hit:
            return hit
        pen = Pen(seed, rgba=True, size=(self.cw, self.ch))
        q = lambda v, step=3: round(v / step) * step
        fx, fy = self.foot
        if self.ride:
            from .registry import PROPS
            m = MOUNTS[self.ride]
            ms = self.s * m["k"]
            f = -1 if p.get("flip") else 1
            pen.shadow(fx, fy + 4 * self.s, 190 * ms)
            PROPS[m["prop"]][1](pen, fx, fy, ms, None, {"flip": bool(p.get("flip")), "saddle": True})
            fx = fx + m["seat"][0] * ms * f
            fy = fy + m["seat"][1] * ms + (0 if m["stand"] else 112 * self.s)
        pen.stick(fx, fy, self.s, kind,
                  arms=tuple(tuple(q(v) for v in a) for a in p["arms"]),
                  legs=tuple(tuple(q(v) for v in l) for l in p["legs"]),
                  mouth=p.get("mouth") or "smile", eyes=p.get("eyes") or "dot", look=p.get("look") or 0,
                  flip=bool(p.get("flip")), extra=tuple(p.get("extra") or ()), prop=p.get("prop"),
                  blink=bool(p.get("blink")), shadow=p.get("shadow", True) and not rot and not self.ride,
                  hat_color=p.get("hat_color"), head=(round(p["head"][0]), round(p["head"][1])),
                  lean=q(p.get("lean", 0), 2), coat=p.get("coat"))
        im = shrink(pen.im, self.cw, self.ch)
        ox, oy = -self.foot[0], -self.foot[1]
        if rot:
            # rotate around the feet (falling over)
            big = Image.new("RGBA", (im.width * 2, im.height * 2), (0, 0, 0, 0))
            big.paste(im, (int(im.width - self.foot[0]), int(im.height - self.foot[1])))
            im = big.rotate(rot, resample=Image.BICUBIC, center=(im.width, im.height))
            ox, oy = -im.width / 2, -im.height / 2
        bb = im.getchannel("A").getbbox()
        if not bb:
            res = (None, (0, 0))
        else:
            res = (im.crop(bb), (ox + bb[0], oy + bb[1]))
        self.cache[key] = res
        return res
