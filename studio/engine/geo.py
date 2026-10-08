"""Natural Earth countries (world-atlas countries-50m TopoJSON) decoded by hand, plus region presets.

Geometries are stored in plain lon/lat. When drawing a map we pick, for every polygon, the copy shifted
by -360/0/+360 degrees that falls inside the view. That way Hawaii and Midway (lon < -100) show up next to
Japan on a Pacific map, and Alaska still shows up on a North America map.
"""
import json
import math
import os
from functools import lru_cache

from shapely import affinity
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "geo", "countries-50m.json")


def decode_topojson(topo, obj="countries"):
    """Decode a TopoJSON object into {name: [list of rings per polygon]} with absolute lon/lat coordinates."""
    tr = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        pts = []
        if tr:
            sx, sy = tr["scale"]
            tx, ty = tr["translate"]
            x = y = 0
            for dx, dy in arc:
                x += dx
                y += dy
                pts.append((x * sx + tx, y * sy + ty))
        else:
            pts = [tuple(p[:2]) for p in arc]
        arcs.append(pts)

    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    out = {}
    for g in topo["objects"][obj]["geometries"]:
        name = (g.get("properties") or {}).get("name") or str(g.get("id"))
        if g["type"] == "Polygon":
            polys = [g["arcs"]]
        elif g["type"] == "MultiPolygon":
            polys = g["arcs"]
        else:
            continue
        out[name] = [[ring(r) for r in p] for p in polys]
    return out


def _to_shape(polys):
    shapes = []
    for rings in polys:
        if not rings or len(rings[0]) < 3:
            continue
        try:
            P = Polygon(rings[0], [r for r in rings[1:] if len(r) >= 3]).buffer(0)
        except Exception:
            continue
        if not P.is_empty:
            shapes.append(P)
    return unary_union(shapes) if shapes else None


@lru_cache(maxsize=1)
def _load():
    with open(ASSET, encoding="utf-8") as f:
        topo = json.load(f)
    raw = decode_topojson(topo, "countries")
    countries = {}
    for name, polys in raw.items():
        g = _to_shape(polys)
        if g is not None:
            countries[name] = g
    return countries


class _Countries(dict):
    """Lazy dict: loading the 750 KB topojson only happens when a map is actually used."""

    def _ensure(self):
        if not dict.__len__(self):
            dict.update(self, _load())

    def __getitem__(self, k):
        self._ensure()
        return dict.__getitem__(self, k)

    def __contains__(self, k):
        self._ensure()
        return dict.__contains__(self, k)

    def items(self):
        self._ensure()
        return dict.items(self)

    def keys(self):
        self._ensure()
        return dict.keys(self)

    def get(self, k, d=None):
        self._ensure()
        return dict.get(self, k, d)

    def __len__(self):
        self._ensure()
        return dict.__len__(self)

    def __iter__(self):
        self._ensure()
        return dict.__iter__(self)


COUNTRIES = _Countries()

ALIASES = {
    "usa": "United States of America", "us": "United States of America", "united states": "United States of America",
    "america": "United States of America", "uk": "United Kingdom", "britain": "United Kingdom",
    "great britain": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom",
    "south korea": "South Korea", "north korea": "North Korea", "korea": ["North Korea", "South Korea"],
    "czech republic": "Czechia", "czechoslovakia": ["Czechia", "Slovakia"], "drc": "Dem. Rep. Congo",
    "congo (kinshasa)": "Dem. Rep. Congo", "democratic republic of the congo": "Dem. Rep. Congo",
    "bosnia": "Bosnia and Herz.", "bosnia and herzegovina": "Bosnia and Herz.", "north macedonia": "Macedonia",
    "ivory coast": "Côte d'Ivoire", "cote d'ivoire": "Côte d'Ivoire", "east timor": "Timor-Leste",
    "burma": "Myanmar", "persia": "Iran", "siam": "Thailand", "ceylon": "Sri Lanka", "holland": "Netherlands",
    "south sudan": "S. Sudan", "central african republic": "Central African Rep.", "dominican republic": "Dominican Rep.",
    "equatorial guinea": "Eq. Guinea", "western sahara": "W. Sahara", "uae": "United Arab Emirates",
    "eswatini": "eSwatini", "swaziland": "eSwatini", "soviet union": "@ussr", "ussr": "@ussr",
    "yugoslavia": ["Slovenia", "Croatia", "Bosnia and Herz.", "Serbia", "Montenegro", "Macedonia", "Kosovo"],
    "solomon islands": "Solomon Is.", "marshall islands": "Marshall Is.", "northern mariana islands": "N. Mariana Is.",
    "falkland islands": "Falkland Is.", "palestine": "Palestine", "israel": "Israel", "vatican city": "Vatican",
    "turkiye": "Turkey", "türkiye": "Turkey", "ottoman empire": "@ottoman_1683", "roman empire": "@roman_empire_117",
}

_EUROPE_W = ["Portugal", "Spain", "France", "Belgium", "Netherlands", "Luxembourg", "United Kingdom", "Ireland",
             "Switzerland", "Austria", "Germany", "Italy", "Denmark", "Norway", "Sweden", "Finland", "Iceland",
             "Malta", "Andorra", "Monaco", "San Marino", "Liechtenstein", "Vatican"]
_EUROPE_E = ["Poland", "Czechia", "Slovakia", "Hungary", "Slovenia", "Croatia", "Bosnia and Herz.", "Serbia",
             "Montenegro", "Kosovo", "Albania", "Macedonia", "Greece", "Bulgaria", "Romania", "Moldova", "Ukraine",
             "Belarus", "Lithuania", "Latvia", "Estonia", "Cyprus"]
_USSR = ["Russia", "Ukraine", "Belarus", "Moldova", "Lithuania", "Latvia", "Estonia", "Georgia", "Armenia",
         "Azerbaijan", "Kazakhstan", "Uzbekistan", "Turkmenistan", "Kyrgyzstan", "Tajikistan"]
_MIDEAST = ["Turkey", "Syria", "Lebanon", "Israel", "Palestine", "Jordan", "Iraq", "Iran", "Saudi Arabia", "Kuwait",
            "Qatar", "Bahrain", "United Arab Emirates", "Oman", "Yemen", "Cyprus", "N. Cyprus"]
_N_AFRICA = ["Morocco", "W. Sahara", "Algeria", "Tunisia", "Libya", "Egypt", "Sudan"]
_S_AMERICA = ["Brazil", "Argentina", "Chile", "Peru", "Colombia", "Venezuela", "Ecuador", "Bolivia", "Paraguay",
              "Uruguay", "Guyana", "Suriname", "Falkland Is."]
_C_AMERICA = ["Mexico", "Guatemala", "Belize", "Honduras", "El Salvador", "Nicaragua", "Costa Rica", "Panama"]
_CARIB = ["Cuba", "Haiti", "Dominican Rep.", "Jamaica", "Bahamas", "Puerto Rico", "Trinidad and Tobago"]
_SE_ASIA = ["Myanmar", "Thailand", "Laos", "Cambodia", "Vietnam", "Malaysia", "Singapore", "Indonesia",
            "Philippines", "Brunei", "Timor-Leste"]
_E_ASIA = ["China", "Mongolia", "North Korea", "South Korea", "Japan", "Taiwan"]
_S_ASIA = ["India", "Pakistan", "Bangladesh", "Nepal", "Bhutan", "Sri Lanka", "Afghanistan"]

# Region presets. Values: list of country names, "@other_preset", or dict(countries=[...], clip=[(lon,lat),...],
# box=(lon0, lat0, lon1, lat1), minus=[...]). Historical borders are approximations meant for doodle maps.
REGIONS = {
    "western_europe": _EUROPE_W,
    "eastern_europe": _EUROPE_E,
    "europe": _EUROPE_W + _EUROPE_E + [dict(countries=["Russia"], box=(20, 40, 60, 75))],
    "ussr": _USSR,
    "middle_east": _MIDEAST,
    "north_africa": _N_AFRICA,
    "south_america": _S_AMERICA,
    "central_america": _C_AMERICA,
    "caribbean": _CARIB,
    "north_america": ["United States of America", "Canada", "Mexico", "Greenland"],
    "southeast_asia": _SE_ASIA,
    "east_asia": _E_ASIA,
    "south_asia": _S_ASIA,
    "central_asia": ["Kazakhstan", "Uzbekistan", "Turkmenistan", "Kyrgyzstan", "Tajikistan"],
    "oceania": ["Australia", "New Zealand", "Papua New Guinea", "Fiji", "Solomon Is.", "Vanuatu", "New Caledonia"],
    "scandinavia": ["Norway", "Sweden", "Denmark", "Finland", "Iceland"],
    "balkans": ["Slovenia", "Croatia", "Bosnia and Herz.", "Serbia", "Montenegro", "Kosovo", "Albania", "Macedonia",
                "Bulgaria", "Greece", "Romania"],
    "british_isles": ["United Kingdom", "Ireland"],
    "iberia": ["Spain", "Portugal"],
    "korea": ["North Korea", "South Korea"],
    "indochina": ["Vietnam", "Laos", "Cambodia"],
    "manchuria": dict(countries=["China"], clip=[(115.5, 42.5), (119.5, 47), (119.6, 50), (120.5, 53.8), (127, 50.5),
                                                 (135.5, 48.5), (131.5, 42.6), (129.5, 42.4), (126, 41), (124.3, 39.9),
                                                 (121.6, 38.9), (121, 40.7), (119.5, 39.9), (117.5, 40.4)]),
    "japan_1942": ["Japan", "korea", "Taiwan", "Myanmar", "Malaysia", "Singapore", "Brunei", "Indonesia",
                   "Philippines", "Timor-Leste", "Guam", "Vietnam", "Laos", "Cambodia", "Thailand",
                   dict(countries=["China"], clip=[(115.5, 42.5), (119.5, 47), (119.6, 50), (120.5, 53.8), (127, 50.5),
                                                   (135.5, 48.5), (131.5, 42.6), (126, 41), (121.6, 38.9), (124.3, 39.9),
                                                   (117.5, 40.4), (114, 41.5), (111, 41), (110, 39.5), (110.5, 37),
                                                   (111, 35), (112.5, 34.3), (114.5, 32), (114, 30.5), (112.8, 29.4),
                                                   (113, 28.2), (116, 28.8), (117.5, 30), (119.8, 29.8), (122.5, 29.5),
                                                   (122.8, 31.5), (121, 32.8), (119, 35), (119.5, 37), (122.8, 37.5)]),
                   dict(countries=["Papua New Guinea"], box=(140, -8.2, 156, 0)),
                   dict(countries=["Solomon Is."], box=(154, -10, 162.5, -5))],
    "roman_empire_117": dict(countries=["Italy", "Spain", "Portugal", "France", "Belgium", "Netherlands", "Switzerland",
                                        "Austria", "Slovenia", "Croatia", "Bosnia and Herz.", "Serbia", "Montenegro",
                                        "Kosovo", "Albania", "Macedonia", "Greece", "Bulgaria", "Romania", "Hungary",
                                        "Turkey", "Cyprus", "N. Cyprus", "Syria", "Lebanon", "Israel", "Palestine",
                                        "Jordan", "Egypt", "Libya", "Tunisia", "Algeria", "Morocco", "United Kingdom",
                                        "Germany", "Iraq", "Armenia", "Georgia", "Malta", "Saudi Arabia"],
                             clip=[(-10, 36), (-10, 44), (-5, 49), (-6, 51), (-3, 53.5), (-4, 55.5), (-1, 55.8),
                                   (2, 52), (4.5, 51.8), (7, 50.5), (8.5, 48.6), (13, 48.5), (17, 48), (19, 47.5),
                                   (22, 48), (27, 48), (30, 46), (40, 44), (44, 42.5), (47, 40), (48, 33), (47, 30),
                                   (38, 28), (35, 27.5), (34, 24), (33, 22), (25, 25), (20, 29), (15, 30.5),
                                   (11, 31), (8, 33), (2, 34), (-4, 33.5), (-9, 32), (-10, 36)]),
    "ottoman_1683": dict(countries=["Turkey", "Greece", "Bulgaria", "Romania", "Serbia", "Bosnia and Herz.", "Albania",
                                    "Macedonia", "Kosovo", "Montenegro", "Hungary", "Syria", "Lebanon", "Israel",
                                    "Palestine", "Jordan", "Iraq", "Egypt", "Libya", "Tunisia", "Algeria", "Cyprus",
                                    "N. Cyprus", "Moldova", "Saudi Arabia", "Yemen", "Ukraine", "Georgia", "Croatia"],
                         clip=[(18, 48), (24, 48.5), (30, 47.5), (37, 47.5), (44, 42), (48, 38), (48.5, 30),
                               (46, 24), (44, 13), (39, 15), (36, 24), (34, 22), (25, 22), (20, 30), (10, 33),
                               (-1, 34.5), (-1, 36.5), (8, 37.5), (12, 33), (20, 33), (24, 36), (19, 40),
                               (14.5, 45), (16, 46.5)]),
    "mongol_empire_1279": dict(countries=["Mongolia", "China", "Russia", "Kazakhstan", "Uzbekistan", "Turkmenistan",
                                          "Kyrgyzstan", "Tajikistan", "Afghanistan", "Iran", "Iraq", "Ukraine",
                                          "Belarus", "Georgia", "Armenia", "Azerbaijan", "korea", "Pakistan",
                                          "Turkey", "Syria", "Moldova"],
                               clip=[(25, 47), (24, 52), (40, 58), (60, 58), (85, 55), (110, 55), (130, 53), (135, 47),
                                     (129, 35), (122, 30), (121, 23), (110, 20), (103, 22), (97, 28), (80, 32),
                                     (70, 30), (61, 25), (52, 27), (46, 30), (38, 36), (33, 38), (30, 44)]),
    "british_raj": ["India", "Pakistan", "Bangladesh", "Myanmar"],
    "thirteen_colonies": dict(countries=["United States of America"],
                              clip=[(-84, 31), (-81, 30.7), (-75, 35), (-70, 41.5), (-67, 45), (-71, 45.2),
                                    (-76, 43.5), (-79.8, 42), (-80.5, 39.5), (-83.5, 36.5), (-85, 34.5)]),
    "new_england": dict(countries=["United States of America"], box=(-73.8, 41.0, -66.8, 47.6)),
    "middle_colonies": dict(countries=["United States of America"], clip=[(-80.5, 39.7), (-75.5, 39.7), (-75.1, 38.5), (-74.0, 39.3), (-73.9, 40.5), (-73.7, 41.0), (-73.4, 42.9), (-74.8, 44.5), (-79, 43.5), (-80.5, 42)]),
    "southern_colonies": dict(countries=["United States of America"], clip=[(-85.2, 31.0), (-81.2, 30.7), (-75.5, 35.2), (-75.8, 36.6), (-77.5, 39.0), (-79.5, 39.7), (-80.5, 38.2), (-83.5, 36.5), (-85.2, 34.8)]),
    "confederacy": dict(countries=["United States of America"],
                        clip=[(-106.6, 32), (-103, 36.5), (-94.6, 36.5), (-89.5, 36.5), (-81.7, 36.6),
                              (-75.9, 36.6), (-77, 39), (-75.5, 37.5), (-75.4, 35.2), (-80, 25), (-97, 25.8)]),
}


def _resolve_name(n):
    key = str(n).strip()
    if key in COUNTRIES:
        return [key]
    low = key.lower()
    if low in ALIASES:
        v = ALIASES[low]
        return v if isinstance(v, list) else [v]
    for k in COUNTRIES.keys():
        if k.lower() == low:
            return [k]
    return []


def countries_geom(names):
    parts = []
    for n in names or ():
        if isinstance(n, dict):
            g = region_geom(n)
            if g is not None:
                parts.append(g)
            continue
        for r in _resolve_name(n):
            if isinstance(r, str) and r.startswith("@"):
                g = region_geom(r[1:])
                if g is not None:
                    parts.append(g)
            elif r in COUNTRIES:
                parts.append(COUNTRIES[r])
    return unary_union(parts) if parts else None


def unknown_names(names):
    """Names that don't resolve to any country/region (used by the validator to warn)."""
    bad = []
    for n in names or ():
        if isinstance(n, dict):
            continue
        if not _resolve_name(n) and str(n).strip().lower() not in REGIONS:
            bad.append(n)
    return bad


def region_geom(spec):
    """spec: preset name, list of names, or dict(countries=..., region=..., clip=..., box=..., minus=...)."""
    if spec is None:
        return None
    if isinstance(spec, str):
        key = spec.strip().lower().lstrip("@")
        if key in REGIONS:
            return region_geom(REGIONS[key])
        return countries_geom([spec])
    if isinstance(spec, (list, tuple)):
        return countries_geom(spec)
    if isinstance(spec, dict):
        g = None
        if spec.get("region"):
            g = region_geom(spec["region"])
        if spec.get("countries"):
            cg = countries_geom(spec["countries"])
            g = cg if g is None else (g.union(cg) if cg is not None else g)
        if g is None:
            return None
        if spec.get("clip") and len(spec["clip"]) >= 3:
            try:
                g = g.intersection(Polygon([tuple(p[:2]) for p in spec["clip"]]).buffer(0))
            except Exception:
                pass
        if spec.get("box") and len(spec["box"]) == 4:
            g = g.intersection(box(*spec["box"]))
        if spec.get("minus"):
            m = region_geom(spec["minus"])
            if m is not None:
                g = g.difference(m)
        return g
    return None


def C(*names):
    return countries_geom(names)


def clip(geom, lonlat_pts):
    return geom.intersection(Polygon(lonlat_pts))


# ------------------------------------------------------------------ projection
def merc(lat):
    lat = max(-85.0, min(85.0, lat))
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


class View:
    """A Mercator view: center lon/lat and width in degrees of longitude across the 1920 px frame."""

    def __init__(self, lon_c, lat_c, width_deg, W=1920, H=1080):
        self.W, self.H = W, H
        self.lc, self.la, self.k = float(lon_c), float(lat_c), W / float(width_deg)
        self.wd = float(width_deg)

    def wrap(self, lon):
        while lon - self.lc > 180:
            lon -= 360
        while lon - self.lc < -180:
            lon += 360
        return lon

    def xy(self, lon, lat):
        lon = self.wrap(lon)
        return (self.W / 2 + (lon - self.lc) * self.k,
                self.H / 2 - (merc(lat) - merc(self.la)) * self.k * 180 / math.pi)

    def bbox(self, pad=6):
        lon0, lon1 = self.lc - self.wd / 2 - pad, self.lc + self.wd / 2 + pad
        hdeg = (self.H / self.k) * math.pi / 180
        m0 = merc(self.la) - hdeg / 2
        m1 = merc(self.la) + hdeg / 2
        inv = lambda m: math.degrees(2 * math.atan(math.exp(m)) - math.pi / 2)
        return lon0, max(inv(m0) - pad, -80), lon1, min(inv(m1) + pad, 84)

    def in_view(self, geom, pad=6):
        """Return the part of geom inside the view, trying the -360/0/+360 shifted copies (Pacific fix)."""
        if geom is None or geom.is_empty:
            return None
        bx = box(*self.bbox(pad))
        parts = []
        for off in (-360, 0, 360):
            g = affinity.translate(geom, xoff=off) if off else geom
            if not g.intersects(bx):
                continue
            gi = g.intersection(bx)
            if not gi.is_empty:
                parts.append(gi)
        if not parts:
            return None
        return unary_union(parts)


def geom_polys(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    if hasattr(g, "geoms"):
        out = []
        for gg in g.geoms:
            out += geom_polys(gg)
        return out
    return []
