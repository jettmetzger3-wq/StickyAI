"""Registry of props the scene JSON can use.

Every prop is placed by its anchor point: "bottom" = bottom-center (things that stand on the ground),
"center" = visual center (explosions, clocks, icons...). Bounding boxes measured at scale 1 live in
prop_bounds.json (regenerate with `python -m studio.engine.measure_props`).
"""
import json
import os

from . import props as P
from .palette import color as C, GRAY, RED, NAVY, BROWN, INK, YELLOW, WHITE, GREEN, ORANGE

HERE = os.path.dirname(os.path.abspath(__file__))
BOUNDS_FILE = os.path.join(HERE, "prop_bounds.json")


def _c(c, default):
    return C(c, default) if c is not None else default


def _f(k, key, default):
    try:
        return float(k.get(key, default))
    except (TypeError, ValueError):
        return default


def _colors(v):
    if not v:
        return None
    return [C(x) for x in v]


def _crate(p, x, y, s, c, k):
    """A wooden crate standing on (x, y)."""
    col = _c(c, (196, 150, 98))
    w, h = 210 * s, 170 * s
    p.rect(x - w / 2, y - h, w, h, col, 7 * s, INK)
    for yy in (y - h * 0.66, y - h * 0.33):
        p.line([(x - w / 2, yy), (x + w / 2, yy)], 4 * s, INK, 0.4)
    p.line([(x - w / 2 + 8 * s, y - 8 * s), (x + w / 2 - 8 * s, y - h + 8 * s)], 5 * s, INK, 0.4)
    if k.get("label"):
        p.text(str(k["label"])[:10].upper(), x, y - h / 2, 44 * s, (40, 30, 20), stroke=5 * s, scol=(236, 214, 170))


# name: (anchor, draw(p, x, y, s, color, params), short description for the LLM)
PROPS = {
    "crate": ("bottom", _crate, "wooden crate / box. params: label (short text like FOOD, GOLD)"),
    # transport & military
    "ship": ("bottom", lambda p, x, y, s, c, k: p.ship(x, y - 45 * s, s, _c(c, GRAY), flag=C(k["flag"]) if k.get("flag") else None), "steel warship. params: flag (color)"),
    "carrier": ("bottom", lambda p, x, y, s, c, k: p.carrier(x, y - 38 * s, s, hit=bool(k.get("hit"))), "aircraft carrier. params: hit (bool, burning)"),
    "tanker": ("bottom", lambda p, x, y, s, c, k: p.tank_ship(x, y - 42 * s, s), "cargo/oil tanker ship"),
    "sailboat": ("bottom", lambda p, x, y, s, c, k: p.sailboat(x, y - 25 * s, s, _c(c, BROWN), flag=C(k["flag"]) if k.get("flag") else None), "old wooden sailing ship (any era before steam). params: flag (color)"),
    "plane": ("center", lambda p, x, y, s, c, k: p.plane(x, y, s, ang=_f(k, "angle", 0), col=_c(c, (215, 218, 226))), "propeller plane, nose points right. params: angle (degrees)"),
    "tank": ("bottom", lambda p, x, y, s, c, k: p.tank(x, y, s, _c(c, (122, 128, 74))), "army tank, gun points right"),
    "cannon": ("bottom", lambda p, x, y, s, c, k: p.cannon(x, y - 58 * s, s), "old cannon"),
    "train": ("bottom", lambda p, x, y, s, c, k: p.train(x, y - 70 * s, s), "bullet/passenger train"),
    "car": ("bottom", lambda p, x, y, s, c, k: P.car(p, x, y, s, _c(c, (220, 70, 60))), "car"),
    "bike": ("bottom", lambda p, x, y, s, c, k: P.bike(p, x, y, s), "bicycle"),
    "rocket": ("bottom", lambda p, x, y, s, c, k: p.rocket(x, y, s, _c(c, (235, 235, 242))), "space rocket with flame"),
    "bomb": ("center", lambda p, x, y, s, c, k: p.bomb(x, y, s), "falling bomb"),
    "helmet": ("bottom", lambda p, x, y, s, c, k: p.helmet(x, y, s), "soldier helmet on the ground"),
    "sword": ("center", lambda p, x, y, s, c, k: p.sword(x, y, s, _f(k, "angle", -30)), "sword. params: angle"),
    "explosion": ("center", lambda p, x, y, s, c, k: P.boom(p, x, y, 110 * s), "cartoon explosion / boom"),
    "mushroom_cloud": ("bottom", lambda p, x, y, s, c, k: p.mushroom(x, y, s), "atomic mushroom cloud (somber scenes only)"),
    "fort": ("bottom", lambda p, x, y, s, c, k: p.fort(x, y, s), "stone fortress wall with gate"),
    "castle": ("bottom", lambda p, x, y, s, c, k: p.castle(x, y, s, roof=_c(c, RED)), "medieval castle. color = roof/flag color"),
    # buildings & places
    "factory": ("bottom", lambda p, x, y, s, c, k: p.factory(x, y, s), "factory with smoking chimneys"),
    "skyline": ("bottom", lambda p, x, y, s, c, k: p.city(x - 300 * s, y, int(_f(k, "buildings", 7)), bool(k.get("burning")), s), "row of city buildings. params: buildings (int), burning (bool)"),
    "palace": ("bottom", lambda p, x, y, s, c, k: P.palace(p, x, y, s), "asian-style palace / government building"),
    "temple": ("bottom", lambda p, x, y, s, c, k: p.temple(x, y, s), "greek/roman temple with columns (also: senate, bank, court)"),
    "pyramid": ("bottom", lambda p, x, y, s, c, k: p.pyramid(x, y, s), "egyptian pyramid"),
    "house": ("bottom", lambda p, x, y, s, c, k: p.house(x, y, s, roof=_c(c, (190, 80, 60))), "small house. color = roof"),
    "tent": ("bottom", lambda p, x, y, s, c, k: p.tent(x, y, s, _c(c, (220, 200, 150))), "army/nomad tent"),
    "wall": ("bottom", lambda p, x, y, s, c, k: p.wall(x, y, _f(k, "w", 400) * s, _f(k, "h", 160) * s, _c(c, (200, 120, 90))), "brick wall. params: w, h"),
    "door": ("bottom", lambda p, x, y, s, c, k: P.door(p, x, y, 220 * s, 380 * s), "door (someone leaves / walks out)"),
    "table": ("bottom", lambda p, x, y, s, c, k: P.table(p, x, y - 146, _f(k, "w", 600) * s), "conference table. params: w"),
    "throne": ("bottom", lambda p, x, y, s, c, k: p.throne(x, y, s, _c(c, (190, 50, 60))), "royal throne"),
    "island": ("bottom", lambda p, x, y, s, c, k: p.island(x, y - 40 * s, s), "small island with a palm tree"),
    "tree": ("bottom", lambda p, x, y, s, c, k: p.tree(x, y, s, _c(c, (110, 170, 90))), "tree"),
    "mountain": ("bottom", lambda p, x, y, s, c, k: p.mountain(x, y, s), "snowy mountain"),
    "derrick": ("bottom", lambda p, x, y, s, c, k: p.derrick(x, y, s), "oil derrick"),
    # objects
    "barrel": ("bottom", lambda p, x, y, s, c, k: p.barrel(x, y - 60 * s, s, bool(k.get("empty"))), "oil barrel. params: empty (bool, crossed out)"),
    "moneybag": ("bottom", lambda p, x, y, s, c, k: p.moneybag(x, y, s), "bag of money"),
    "coin": ("bottom", lambda p, x, y, s, c, k: p.coin(x, y, s), "gold coin"),
    "crown": ("bottom", lambda p, x, y, s, c, k: p.crown(x, y, s, _c(c, (240, 200, 70))), "crown (power, monarchy)"),
    "trophy": ("bottom", lambda p, x, y, s, c, k: p.trophy(x, y, s), "trophy cup (victory)"),
    "book": ("bottom", lambda p, x, y, s, c, k: p.book(x, y, s, _c(c, (170, 60, 60))), "book"),
    "scroll": ("center", lambda p, x, y, s, c, k: p.scroll(x, y, s), "paper scroll / treaty"),
    "document": ("center", lambda p, x, y, s, c, k: p.doc(x - 70 * s, y - 95 * s, 140 * s, 190 * s, int(_f(k, "lines", 5))), "sheet of paper with lines (law, letter, treaty)"),
    "flag": ("bottom", lambda p, x, y, s, c, k: p.flag(x, y, s, _c(c, RED), C(k["color2"]) if k.get("color2") else None), "flag on a pole. color + params: color2 (middle stripe)"),
    "radio": ("center", lambda p, x, y, s, c, k: p.radio(x, y, s), "old radio (broadcast, news)"),
    "tv": ("bottom", lambda p, x, y, s, c, k: P.tv(p, x, y, s), "old TV"),
    "ballot": ("bottom", lambda p, x, y, s, c, k: P.ballot(p, x, y, s), "ballot box (election)"),
    "lock": ("center", lambda p, x, y, s, c, k: p.lock(x, y, s), "padlock (embargo, sealed)"),
    "magnifier": ("center", lambda p, x, y, s, c, k: p.magnifier(x, y, s), "magnifying glass (investigate)"),
    "lightbulb": ("bottom", lambda p, x, y, s, c, k: p.lightbulb(x, y, s, k.get("lit", True) is not False), "light bulb (idea)"),
    "globe": ("bottom", lambda p, x, y, s, c, k: p.globe(x, y, s), "world globe"),
    "candle": ("bottom", lambda p, x, y, s, c, k: p.candle(x, y, s), "memorial candle (somber)"),
    "lantern": ("center", lambda p, x, y, s, c, k: p.lantern(x, y, s, bool(k.get("lit", True))), "paper lantern"),
    "gravestone": ("bottom", lambda p, x, y, s, c, k: p.gravestone(x, y, s, str(k.get("label", "RIP"))[:12]), "gravestone (somber). params: label"),
    "hourglass": ("center", lambda p, x, y, s, c, k: p.hourglass(x, y, s, _f(k, "fill", 0.2)), "hourglass (time running out). params: fill 0..1"),
    "calendar": ("center", lambda p, x, y, s, c, k: p.calendar(x - 100 * s, y - 110 * s, s, int(_f(k, "circled", 3))), "calendar. params: circled (int days)"),
    "clock": ("center", lambda p, x, y, s, c, k: P.clock(p, x, y, 110 * s, _f(k, "frac", 0.25)), "clock. params: frac 0..1"),
    "gauge": ("center", lambda p, x, y, s, c, k: P.gauge(p, x, y, 130 * s, _f(k, "frac", 0.2), str(k.get("low", "E")), str(k.get("high", "F"))), "fuel gauge. params: frac 0..1, low, high labels"),
    "pie": ("center", lambda p, x, y, s, c, k: P.pie(p, x, y, 120 * s, _f(k, "frac", 0.5), _c(c, NAVY), C(k.get("color2"), (225, 225, 230))), "pie chart. params: frac 0..1, color2"),
    "line_chart": ("bottom", lambda p, x, y, s, c, k: P.chart(p, x - _f(k, "w", 600) * s / 2, y, _f(k, "w", 600) * s, _f(k, "h", 380) * s,
                                                              [tuple(v[:2]) for v in (k.get("points") or [(0, 0.2), (0.5, 0.5), (1, 0.9)])], _c(c, RED)),
                   "line chart with arrow. params: points [[x0..1, y0..1], ...], w, h"),
    "bar_chart": ("bottom", lambda p, x, y, s, c, k: p.bar_chart(x, y, _f(k, "w", 420) * s, _f(k, "h", 300) * s, k.get("values") or (0.3, 0.6, 0.9), _colors(k.get("colors"))),
                  "bar chart. params: values [0..1, ...], colors [...], w, h"),
    "xmark": ("center", lambda p, x, y, s, c, k: P.xmark(p, x, y, 60 * s, 18 * s), "big red X (no / failed / crossed out)"),
    "check": ("center", lambda p, x, y, s, c, k: P.check(p, x, y, 50 * s, 18 * s), "green check mark"),
    "speed_lines": ("center", lambda p, x, y, s, c, k: p.speed(x + 70 * s, y - 50 * s, 4, 140 * s), "motion lines (put behind something moving right)"),
    "smoke": ("bottom", lambda p, x, y, s, c, k: p.smoke(x - 15 * s, y - 22 * s, s), "rising smoke"),
    "fire": ("bottom", lambda p, x, y, s, c, k: p.flame(x, y, s), "flame / fire"),
    "cloud": ("center", lambda p, x, y, s, c, k: p.cloud(x, y, s), "white cloud"),
    "dove": ("center", lambda p, x, y, s, c, k: P.dove(p, x, y, s), "peace dove"),
    "bear": ("bottom", lambda p, x, y, s, c, k: p.bear(x, y - 100 * s, s), "bear (Russia joke)"),
    "crowd": ("bottom", lambda p, x, y, s, c, k: p.crowd(x - 175 * s, y - 38 * s, int(_f(k, "n", 6)), s), "small crowd of background people. params: n"),
    "mousetrap": ("bottom", lambda p, x, y, s, c, k: P.mousetrap(p, x, y, s), "mousetrap (a trap)"),
    "subscribe": ("center", lambda p, x, y, s, c, k: P.subscribe(p, x, y, s), "red SUBSCRIBE button (end of video)"),
    "puppet": ("bottom", lambda p, x, y, s, c, k: P.puppet(p, x, y, s, str(k.get("kind", "civ"))), "stickman on strings (puppet state). params: kind"),
    "folding_screen": ("bottom", lambda p, x, y, s, c, k: P.screen(p, x, y, 420 * s, 360 * s), "folding screen (hiding something)"),
    "rewind": ("center", lambda p, x, y, s, c, k: P.rewind(p, x, y, str(k.get("label", ""))[:16]), "rewind button. params: label (e.g. '~1850')"),
    "railway": ("bottom", lambda p, x, y, s, c, k: p.railway(_f(k, "x1", 0), _f(k, "x2", 1920), y - 32), "railway track across the frame. params: x1, x2"),
    "periscope": ("bottom", lambda p, x, y, s, c, k: p.periscope(x, y, s), "submarine periscope"),
    "mini_carrier": ("center", lambda p, x, y, s, c, k: P.mini_carrier(p, x, y, 2 * s), "tiny carrier icon (for counts)"),
}

PROP_ALIASES = {
    "boat": "sailboat", "galley": "sailboat", "galleon": "sailboat", "warship": "ship", "battleship": "ship",
    "destroyer": "ship", "submarine": "periscope", "airplane": "plane", "aeroplane": "plane", "boom": "explosion",
    "bomb_explosion": "explosion", "mushroom": "mushroom_cloud", "nuke": "mushroom_cloud", "city": "skyline",
    "buildings": "skyline", "money": "moneybag", "gold": "coin", "chart": "line_chart", "graph": "line_chart",
    "bars": "bar_chart", "x": "xmark", "cross": "xmark", "x_mark": "xmark", "check_mark": "check", "tick": "check",
    "paper": "document", "letter": "document", "treaty": "scroll", "fortress": "fort", "senate": "temple",
    "colosseum": "temple", "church": "house", "oil": "barrel", "oil_barrel": "barrel", "flame": "fire",
    "idea": "lightbulb", "bulb": "lightbulb", "grave": "gravestone", "tombstone": "gravestone", "planet": "globe",
    "earth": "globe", "world": "globe", "cart": "car", "truck": "car", "oil_rig": "derrick", "people": "crowd",
    "speed": "speed_lines", "tanker_ship": "tanker", "tank_ship": "tanker", "subscribe_button": "subscribe",
    "pie_chart": "pie", "fuel_gauge": "gauge", "time": "clock",
}

ICONABLE = ("mini_carrier", "ship", "plane", "tank", "barrel", "moneybag", "coin", "house", "tree", "sailboat",
            "factory", "candle", "crowd", "flag", "castle", "rocket", "book", "trophy", "skyline")


def resolve_prop(name):
    n = str(name or "").strip().lower().replace(" ", "_").replace("-", "_")
    n = PROP_ALIASES.get(n, n)
    return n if n in PROPS else None


_bounds = None


def prop_bounds(name):
    """(x0, y0, x1, y1) of the prop at scale 1 relative to its anchor point."""
    global _bounds
    if _bounds is None:
        try:
            with open(BOUNDS_FILE, encoding="utf-8") as f:
                _bounds = json.load(f)
        except (OSError, ValueError):
            _bounds = {}
    b = _bounds.get(name)
    if b:
        return tuple(b)
    anchor = PROPS.get(name, ("bottom",))[0]
    return (-150, -300, 150, 0) if anchor == "bottom" else (-120, -120, 120, 120)
