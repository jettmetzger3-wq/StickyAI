"""Font loading (Fredoka bold/semibold and Patrick Hand, both SIL OFL)."""
import os
from functools import lru_cache

from PIL import ImageFont

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONTS = {
    "bold": os.path.join(ASSETS, "fonts", "fredoka-latin-700-normal.woff"),
    "semi": os.path.join(ASSETS, "fonts", "fredoka-latin-600-normal.woff"),
    "hand": os.path.join(ASSETS, "fonts", "patrick-hand-latin-400-normal.woff"),
}


@lru_cache(maxsize=256)
def font(name, size):
    return ImageFont.truetype(FONTS.get(name, FONTS["bold"]), max(1, int(size)))
