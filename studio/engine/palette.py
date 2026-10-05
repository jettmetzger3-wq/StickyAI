"""Colors used by the doodle engine, plus helpers to turn names/hex strings into RGB tuples."""

INK = (38, 38, 48)
PAPER = (250, 245, 232)
SEA = (150, 202, 228)
SEA2 = (112, 170, 205)
LAND = (234, 202, 132)
RED = (214, 60, 55)
NAVY = (52, 72, 132)
GREEN = (132, 188, 112)
GRAY = (172, 172, 184)
DGRAY = (110, 110, 124)
ORANGE = (246, 160, 70)
SKIN = (255, 250, 240)
BROWN = (150, 105, 70)
YELLOW = (250, 220, 90)
WHITE = (255, 255, 255)
SUN = (255, 236, 175)
DARK = (44, 46, 62)

NAMED = {
    "ink": INK, "black": (20, 20, 26), "paper": PAPER, "sea": SEA, "sea2": SEA2, "land": LAND,
    "red": RED, "darkred": (150, 30, 30), "navy": NAVY, "blue": (70, 120, 200), "lightblue": (170, 210, 235),
    "green": GREEN, "darkgreen": (60, 140, 70), "olive": (122, 128, 74), "gray": GRAY, "grey": GRAY,
    "dgray": DGRAY, "darkgray": DGRAY, "orange": ORANGE, "skin": SKIN, "brown": BROWN, "yellow": YELLOW,
    "gold": (232, 186, 60), "white": WHITE, "purple": (130, 80, 160), "pink": (240, 150, 170),
    "teal": (60, 160, 160), "sun": SUN, "dark": DARK, "cream": (255, 250, 232), "maroon": (128, 30, 50),
    "khaki": (190, 170, 110), "silver": (205, 208, 216),
}


def color(c, default=INK):
    """Accept 'red', '#d63c37', [214, 60, 55] or None and return an RGB tuple."""
    if c is None:
        return default
    if isinstance(c, (list, tuple)):
        if len(c) >= 3:
            return tuple(int(max(0, min(255, v))) for v in c[:3])
        return default
    s = str(c).strip().lower()
    if s in NAMED:
        return NAMED[s]
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) == 6:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return default
    return default


def darker(c, k=0.7):
    return tuple(int(v * k) for v in c)


def lighter(c, k=0.5):
    return tuple(int(v + (255 - v) * k) for v in c)
