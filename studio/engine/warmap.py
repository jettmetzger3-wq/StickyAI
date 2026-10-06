"""War-map pieces that move: troops marching along an arrow, battle markers, front lines that shift over time,
and counters that tick (years, troops, money). They work on maps (lon/lat) and on any other scene (x/y)."""
import math

from .doodle import W, H
from .palette import color as C, INK, RED, WHITE, YELLOW, ORANGE, darker
from .pen import resolve_kind, HATS, KIND_ALIASES


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def resample(pts, n=24):
    """n points evenly spaced along a polyline."""
    if len(pts) < 2:
        return [tuple(pts[0])] * n if pts else [(960.0, 540.0)] * n
    segs, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        segs.append(d)
        total += d
    out = []
    for i in range(n):
        target = total * i / (n - 1)
        acc = 0.0
        for k, d in enumerate(segs):
            if acc + d >= target or k == len(segs) - 1:
                f = 0.0 if d == 0 else min(1.0, (target - acc) / d)
                (x0, y0), (x1, y1) = pts[k], pts[k + 1]
                out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
                break
            acc += d
    return out


def along(pts, q):
    """Point and direction (radians) at fraction q (0..1) of a polyline's length."""
    q = min(max(q, 0.0), 1.0)
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lens) or 1.0
    target, acc = total * q, 0.0
    for k, d in enumerate(lens):
        if acc + d >= target or k == len(lens) - 1:
            f = 0.0 if d == 0 else min(1.0, (target - acc) / d)
            (x0, y0), (x1, y1) = pts[k], pts[k + 1]
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f), math.atan2(y1 - y0, x1 - x0)
        acc += d
    return pts[-1], 0.0


def bbox(pts, pad):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0 = max(-200, min(xs) - pad), max(-200, min(ys) - pad)
    x1, y1 = min(W + 200, max(xs) + pad), min(H + 200, max(ys) + pad)
    return x0, y0, max(4, x1 - x0), max(4, y1 - y0)


# ------------------------------------------------------------------ drawing
def draw_front(p, pts, col, width=12, side=1, teeth=True):
    """A front line: thick line with small triangles on the side the army faces."""
    p.line(pts, width + 8, WHITE, 0.3)
    p.line(pts, width, col, 0.3)
    if not teeth:
        return
    lens = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lens)
    n = int(total / 46)
    for i in range(1, n):
        (x, y), a = along(pts, i / n)
        nx, ny = -math.sin(a) * side, math.cos(a) * side
        ux, uy = math.cos(a), math.sin(a)
        tri = [(x - ux * 11 + nx * width * 0.4, y - uy * 11 + ny * width * 0.4),
               (x + ux * 11 + nx * width * 0.4, y + uy * 11 + ny * width * 0.4),
               (x + nx * (width * 0.4 + 17), y + ny * (width * 0.4 + 17))]
        p.poly(tri, col, 3, WHITE, 0.2)


def draw_battle(p, x, y, s=1.0, label="", pulse=0.0):
    """Crossed swords over a burst: a battle happened here."""
    r = 62 * s * (1 + 0.08 * pulse)
    pts = []
    for i in range(18):
        a = 2 * math.pi * i / 18
        rr = r if i % 2 == 0 else r * 0.6
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    p.poly(pts, ORANGE, 5 * s)
    p.poly([(x + (px - x) * 0.6, y + (py - y) * 0.6) for px, py in pts], YELLOW, 0)
    for sgn in (-1, 1):
        blade = [(x + sgn * 30 * s, y + 30 * s), (x - sgn * 46 * s, y - 46 * s)]
        p.line(blade, 13 * s, INK, 0.2)
        p.line(blade, 7 * s, (230, 232, 240), 0.2)
        gx, gy = x + sgn * 30 * s, y + 30 * s
        k = 14 * s / math.sqrt(2)
        p.line([(gx - k, gy + sgn * k), (gx + k, gy - sgn * k)], 8 * s, (200, 150, 50), 0.2)
        p.line([(gx, gy), (x + sgn * 46 * s, y + 46 * s)], 8 * s, (110, 70, 44), 0.2)
        p.circ(x + sgn * 48 * s, y + 48 * s, 7 * s, (200, 150, 50), 3 * s)
    if label:
        p.text(str(label)[:24], x, y + r + 34 * s, 40 * s, INK, stroke=8 * s, scol=WHITE)


def fmt_count(v, kind="number", prefix="", suffix="", decimals=0):
    if kind == "year":
        y = int(round(v))
        return f"{prefix}{abs(y)} BC{suffix}" if y < 0 else f"{prefix}{y}{suffix}"
    if decimals:
        body = f"{v:,.{int(decimals)}f}"
    else:
        body = f"{int(round(v)):,}"
    return f"{prefix}{body}{suffix}"


def draw_marchers(p, pts, q, units, n, col, s, t, flip_ok=True):
    """`n` small soldiers (or one prop, e.g. a tank) walking along pts; the leader is at fraction q."""
    from .registry import resolve_prop, PROPS
    prop = resolve_prop(units)
    gap = 0.07
    for i in range(n):
        qi = q - i * gap
        if qi < 0:
            break
        (x, y), a = along(pts, qi)
        left = math.cos(a) < 0
        if prop:
            _, fn, _ = PROPS[prop]
            fn(p, x, y + 20 * s, 0.32 * s, col, {"flip": left})
        else:
            kind = resolve_kind(units)
            step = math.sin(t * 9 + i * 1.7)
            legs = ((22 * step, 0), (-22 * step, 0))
            p.stick(x, y + 28 * s, 0.2 * s, kind, arms=((25, 15), (25, 15)), legs=legs, flip=left,
                    shadow=False, coat=col)


def is_kind(v):
    k = str(v or "").strip().lower().replace(" ", "_")
    return k in HATS or k in KIND_ALIASES
