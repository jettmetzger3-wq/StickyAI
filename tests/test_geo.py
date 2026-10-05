from studio.engine.geo import decode_topojson, View, COUNTRIES, region_geom, countries_geom, unknown_names


def test_decode_small_topology_with_transform_and_reversed_arcs():
    topo = {
        "type": "Topology",
        "transform": {"scale": [1, 1], "translate": [10, 20]},
        "arcs": [[[0, 0], [5, 0], [0, 5]], [[5, 5], [-5, 0], [0, -5]]],
        "objects": {"countries": {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "arcs": [[0, 1]], "properties": {"name": "Square"}},
            {"type": "Polygon", "arcs": [[~1, ~0]], "properties": {"name": "Reversed"}},
        ]}},
    }
    out = decode_topojson(topo)
    ring = out["Square"][0][0]
    # delta-decoded + transformed
    assert ring[0] == (10, 20) and ring[1] == (15, 20) and ring[2] == (15, 25)
    assert ring[-1] == (10, 20)  # closed
    rev = out["Reversed"][0][0]
    assert rev[0] == (10, 20) and rev[1] == (10, 25)


def test_real_atlas_has_countries():
    assert len(COUNTRIES) > 200
    for name in ("Japan", "United States of America", "Russia", "Italy", "Egypt"):
        assert name in COUNTRIES
    lon0, lat0, lon1, lat1 = COUNTRIES["Japan"].bounds
    assert 120 < lon0 < 135 and 140 < lon1 < 155


def test_hawaii_shows_on_a_pacific_map_and_alaska_on_an_americas_map():
    usa = COUNTRIES["United States of America"]
    pacific = View(163, 18, 112)
    g = pacific.in_view(usa)
    assert g is not None
    minx, miny, maxx, maxy = g.bounds
    assert maxx > 190  # Hawaii shifted by +360 (about -155 -> 205)
    x, y = pacific.xy(-157.9, 21.3)  # Pearl Harbor given in negative longitude
    assert 0 < x < 1920 and 0 < y < 1080
    americas = View(-120, 50, 90)
    g2 = americas.in_view(usa)
    assert g2 is not None and g2.bounds[0] < -150  # Alaska stays where it is


def test_aliases_and_regions():
    assert countries_geom(["UK"]).equals(COUNTRIES["United Kingdom"])
    korea = countries_geom(["Korea"])
    assert korea.contains(COUNTRIES["South Korea"].representative_point())
    assert region_geom("roman_empire_117") is not None
    assert region_geom({"countries": ["Russia"], "box": [141, 45.8, 145, 50]}).area < COUNTRIES["Russia"].area / 100
    assert unknown_names(["Japan", "Atlantis"]) == ["Atlantis"]
