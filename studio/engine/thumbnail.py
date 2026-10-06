"""Free thumbnail renderer: big faces, a small furious character against a giant smug one, a bold two-line title.

What makes stickman-history thumbnails work at phone size: faces large enough to read the emotion, characters
cut out like stickers (thick white outline and a soft shadow) so they pop off any background, few words in huge
double-outlined letters, and saturated colors.
"""
from PIL import Image, ImageDraw, ImageFilter

from .doodle import W, H, SS
from .pen import Pen
from .fonts import font
from .palette import color as C, INK, RED, WHITE

TW, TH = 1280, 720


def _fit(text, max_w, size, f="bold", stroke=14):
    while size > 40:
        fnt = font(f, size)
        if fnt.getlength(text) + stroke * 2 <= max_w:
            break
        size -= 6
    return size


def _finish(p, w, h):
    return p.im.convert("RGBa").resize((int(w), int(h)), Image.LANCZOS).convert("RGBA")


def sticker(img, border=14, shadow=18):
    """A cut-out look: white outline around the shape plus a soft dark shadow below-right."""
    pad = border + shadow + 6
    big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    big.paste(img, (pad, pad), img)
    a = big.getchannel("A")
    grown = a.filter(ImageFilter.MaxFilter(border * 2 + 1 if border % 2 == 0 else border * 2 + 1))
    sh = grown.filter(ImageFilter.GaussianBlur(shadow / 2)).point(lambda v: int(v * 0.45))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out.paste((20, 18, 30, 255), (10, 12), sh)
    out.paste((255, 255, 255, 255), (0, 0), grown)
    out.alpha_composite(big)
    return out, pad


def _stick(kind, s, w, h, foot_y, **pose):
    p = Pen(3, rgba=True, size=(w, h))
    p.stick(w / 2, foot_y, s, kind, shadow=False, **pose)
    return _finish(p, w, h)


def _rays(base, ray, cx, cy):
    im = Image.new("RGB", (W, H), base)
    p = Pen(1, rgba=False, bg=base)
    p.sunburst(cx, cy, col=ray)
    im = p.im.resize((W, H), Image.LANCZOS)
    # brighter in the middle, darker toward the corners
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([cx - 900, cy - 700, cx + 900, cy + 700], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    dark = Image.blend(im, Image.new("RGB", (W, H), (40, 20, 10)), 0.35)
    return Image.composite(im, dark, glow)


def render_thumbnail(out_path, line1, line2="", small_kind="civ", big_kind="crown", accent="red",
                     bg_color=None, ray_color=None, background_image=None, prop=None, small_coat=None,
                     big_coat=None):
    """1280x720 PNG. background_image (path, e.g. from an AI image provider) replaces the rays; the characters
    and the title are always drawn on top, so every thumbnail has the channel's look."""
    if background_image:
        try:
            bg = Image.open(background_image).convert("RGB")
            r = max(W / bg.width, H / bg.height)
            bg = bg.resize((int(bg.width * r) + 1, int(bg.height * r) + 1), Image.LANCZOS)
            left, top = (bg.width - W) // 2, (bg.height - H) // 2
            im = bg.crop((left, top, left + W, top + H))
        except Exception:
            background_image = None
    if not background_image:
        im = _rays(C(bg_color, (255, 205, 70)), C(ray_color, (255, 160, 40)), 1250, 640)
    im = im.convert("RGBA")
    # the giant smug one: a close-up, cut at the chest
    big = _stick(big_kind, 2.9, 1500, 1500, 1500 + 380, arms="cross", mouth="smirk", eyes="dot", flip=True,
                 coat=big_coat)
    bb = big.getbbox()
    if bb:
        big = big.crop(bb)
    big_s, pad = sticker(big, 16, 26)
    bx = int(min(1600 - big_s.width / 2, W - big_s.width + pad - 10))     # head around x 1600, never cut off
    im.alpha_composite(big_s, (bx, int(H - big_s.height + pad + 10)))
    # the small furious one, in front
    small = _stick(small_kind, 1.7, 1000, 1000, 980, arms="angry_fists", mouth="scream", eyes="angry",
                   extra=("vein", "sweat"), coat=small_coat)
    sb = small.getbbox()
    if sb:
        small = small.crop(sb)
    small_s, pad2 = sticker(small, 14, 22)
    sx, sy = 70, int(H - small_s.height + pad2 * 0.6 + 40)
    if prop:
        from .registry import resolve_prop, guess_prop, PROPS, prop_bounds, prop_anchor
        name = resolve_prop(prop) or guess_prop(prop)
        if name:
            x0, y0, x1, y1 = prop_bounds(name, {})
            k = min(420 / max(1.0, x1 - x0), 380 / max(1.0, y1 - y0))
            p = Pen(4, rgba=True, size=(560, 520))
            cy = 260 + ((y1 - y0) * k / 2 if prop_anchor(name, {}) == "bottom" else 0)
            PROPS[name][1](p, 280, cy, k, None, {})
            pi = _finish(p, 560, 520)
            pb = pi.getbbox()
            if pb:
                pi, pp = sticker(pi.crop(pb), 12, 18)
                im.alpha_composite(pi, (int(sx + small_s.width - 60), int(H - pi.height - 30)))
    im.alpha_composite(small_s, (sx, sy))
    # the title: huge, double outline (black, then white), accent color on the first line
    d = ImageDraw.Draw(im)
    acc = C(accent, RED)
    cx, max_w = 690, 1240
    t1 = (line1 or "").upper().replace(" ", "  ")          # big bold letters need wider gaps between words
    s1 = _fit(t1, max_w, 210, stroke=30)
    y1 = 70 + s1 * 0.5
    d.text((cx + 6, y1 + 8), t1, font=font("bold", s1), fill=(20, 18, 28), anchor="mm", stroke_width=30,
           stroke_fill=(20, 18, 28))                                           # drop shadow
    d.text((cx, y1), t1, font=font("bold", s1), fill=acc, anchor="mm", stroke_width=30, stroke_fill=(20, 18, 28))
    d.text((cx, y1), t1, font=font("bold", s1), fill=acc, anchor="mm", stroke_width=16, stroke_fill=WHITE)
    if line2:
        t2 = line2.upper().replace(" ", "  ")
        s2 = _fit(t2, max_w, 170, stroke=26)
        y2 = y1 + s1 * 0.5 + s2 * 0.62
        d.text((cx + 5, y2 + 7), t2, font=font("bold", s2), fill=(20, 18, 28), anchor="mm", stroke_width=26,
               stroke_fill=(20, 18, 28))
        d.text((cx, y2), t2, font=font("bold", s2), fill=WHITE, anchor="mm", stroke_width=26, stroke_fill=(20, 18, 28))
    out = im.convert("RGB").resize((TW, TH), Image.LANCZOS)
    out.save(out_path)
    return out_path
