"""Free thumbnail renderer: big two-line title, a small angry character vs a giant smug one, sunburst."""
from PIL import Image, ImageDraw

from .core import Scene, W, H
from .fonts import font
from .palette import color as C, INK, RED, WHITE, PAPER


def _fit(text, max_w, size, f="bold", stroke=14):
    while size > 40:
        fnt = font(f, size)
        if fnt.getlength(text) + stroke * 2 <= max_w:
            break
        size -= 6
    return size


def render_thumbnail(out_path, line1, line2="", small_kind="civ", big_kind="crown", accent="red",
                     bg_color=None, ray_color=None, background_image=None):
    """1280x720 PNG. If background_image (path) is given (e.g. from an AI image provider), it replaces the
    sunburst and our characters/text are drawn on top for a consistent look."""
    sc = Scene(0, 2.0, "fun", "")
    sc.bg_sunburst(C(bg_color, PAPER), C(ray_color, (255, 226, 150)))
    sc.char(330, 1045, 0.8, small_kind, enter=None, idle=None, arms="angry_fists", mouth="open", eyes="angry",
            extra=("vein",), sfx=None)
    sc.char(1570, 1140, 1.75, big_kind, enter=None, idle=None, arms="cross", mouth="smirk", eyes="dot", flip=True,
            sfx=None)
    sc.camera(1.0, 1.0)
    if background_image:
        try:
            bg = Image.open(background_image).convert("RGB")
            r = max(W / bg.width, H / bg.height)
            bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1), Image.LANCZOS)
            left, top = (bg.width - W) // 2, (bg.height - H) // 2
            sc.bg = bg.crop((left, top, left + W, top + H))
        except Exception:
            pass
    im = sc.render_at(1.0)
    d = ImageDraw.Draw(im)
    acc = C(accent, RED)
    cx, max_w = 760, 1220
    s1 = _fit(line1.upper(), max_w, 190)
    d.text((cx, 175), line1.upper(), font=font("bold", s1), fill=acc, anchor="mm", stroke_width=16, stroke_fill=WHITE)
    if line2:
        s2 = _fit(line2.upper(), max_w, 150)
        d.text((cx, 175 + s1 * 0.5 + s2 * 0.62), line2.upper(), font=font("bold", s2), fill=INK, anchor="mm",
               stroke_width=14, stroke_fill=WHITE)
    im = im.convert("RGB").resize((1280, 720), Image.LANCZOS)
    im.save(out_path)
    return out_path
