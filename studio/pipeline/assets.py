"""Asset lookup and reuse: before anything new is made, find what already exists.

The library has props (~230), hats/nations (45), painted backgrounds, map regions, saved characters (the per-video
registry plus the historical people database) and props other videos already had drawn (the custom-prop cache). `find`
answers "do we already have this?" with the nearest match; `inventory` is the list for the UI and docs; `missing`
reports anything in a finished scene that no asset provides (the schema repair normally replaces it first).
"""
from .. import cache as CA
from ..engine import geo
from ..engine.pen import HATS, resolve_kind
from ..engine.registry import PROPS, guess_prop, resolve_prop
from ..engine.schema import BG_TYPES
from ..knowledge import people as PE


def find(kind, name):
    """(asset id, how) for the nearest existing asset of `kind` ('prop', 'hat', 'background', 'region', 'person'), or (None, '')."""
    n = str(name or "").strip()
    if kind == "prop":
        if resolve_prop(n):
            return resolve_prop(n), "exact"
        idx = CA.get("props", "_index") or {}
        key = n.lower().replace(" ", "_")
        if key in idx:
            return key, "custom prop saved by an earlier video"
        g = guess_prop(n)
        return (g, "nearest library prop") if g else (None, "")
    if kind == "hat":
        k = resolve_kind(n)
        return (k, "exact" if k == n.lower() else "nearest") if k in HATS else (None, "")
    if kind == "background":
        k = n.lower().replace(" ", "_")
        return (k, "exact") if k in BG_TYPES else (None, "")
    if kind == "region":
        k = n.lower().replace(" ", "_")
        return (k, "exact") if k in geo.REGIONS or geo.countries_geom([n]) is not None else (None, "")
    if kind == "person":
        e = PE.find(n)
        return (e["id"], "historical people database") if e else (None, "")
    return None, ""


def inventory():
    return dict(props=len(PROPS), custom_props=len(CA.get("props", "_index") or {}), hats=len(HATS), backgrounds=len(BG_TYPES),
                regions=len(geo.REGIONS), people=len(PE._index()) if hasattr(PE, "_index") else 0)


def missing(scene, custom_names=()):
    """Names in `scene` that no asset provides: [(kind, name)]."""
    have = set(PROPS) | set(custom_names or ())
    out = []
    for el in (scene or {}).get("elements") or []:
        if el.get("type") == "prop" and el.get("name") not in have and not resolve_prop(el.get("name")):
            out.append(("prop", el.get("name")))
        if el.get("type") in ("char", "crowd") and el.get("kind") and el["kind"] not in HATS:
            out.append(("hat", el["kind"]))
    bg = ((scene or {}).get("bg") or {}).get("type")
    if bg and bg not in BG_TYPES:
        out.append(("background", bg))
    return out
