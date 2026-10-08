"""The meaning layer: what a sentence needs the viewer to SEE, and whether a scene shows it.

Keyword matching says "the narration contains 'England', so show England". This module asks what the sentence is
about: "England established 13 colonies along the Atlantic coast" is about the 13 colonies on the Atlantic coast of
North America, with England as the place they came from. It works in four local steps (no AI call):

    enrich()        add meaning to the beat analysis: named regions, a map that fits the story, the famous document or
                    event behind the sentence, and the "frame" (colonization, writing a constitution, ...)
    requirements()  the typed list of things the picture must communicate (region, document, person, group, place,
                    number, time, action), from the analysis plus any `needs` Claude's plan wrote down
    scene_concepts()  what a finished scene JSON actually communicates (map view and highlighted regions, labels,
                    props, people, banner text ...)
    coverage()      requirements met / requirements, with the list of what is missing

Claude supplies the judgement for anything the curated tables (knowledge/context.json) don't know: its per-scene
`needs` go through the same classifier, so the same checker scores them.
"""
import json
import math
import os
import re

from ..engine import geo
from . import people as PE

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "context.json"), encoding="utf-8") as _f:
    CTX = json.load(_f)

NUM_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
             "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15", "twenty": "20"}
STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "and", "for", "with", "by", "its", "his", "her", "their", "was", "were",
        "is", "are", "along", "across", "over", "into", "from", "that", "this"}
COVERAGE_FAIL = 0.5            # below this a scene does not communicate its narration (the user's own examples: 25% fails)
COVERAGE_BLOCK = 0.34          # below this after repair a scene is not rendered ("obviously inadequate")


# ---------------------------------------------------------------- canonical words
def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss") and not w.endswith("us"):
        return w[:-1]
    return w


def canon(text):
    """Lower-case, number words as digits, plural endings folded: 'Thirteen Colonies!' -> '13 colony'."""
    t = re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower().replace("&", " and ").replace("'", ""))
    out = []
    for w in t.split():
        w = NUM_WORDS.get(w, w)
        out.append(_stem(w))
    return " ".join(out)


def _words(c):
    return [w for w in c.split() if w not in STOP]


def phrase_in(canon_text, phrase):
    p = canon(phrase)
    return bool(p) and re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", canon_text) is not None


_SYN = {}
for _grp in CTX.get("synonyms") or []:
    _cs = {canon(x) for x in _grp}
    for _c in _cs:
        _SYN.setdefault(_c, set()).update(_cs)


def alternatives(c):
    """A concept and its synonyms."""
    return {c} | _SYN.get(c, set())


def concept_match(want, have):
    """Does the concept `want` appear in the set of concepts a scene `have`? Exact, synonym, whole-phrase containment,
    or all of its content words present in one concept."""
    ww = _words(want)
    for alt in alternatives(want):
        if alt in have:
            return True
    if not ww:
        return False
    for h in have:
        hw = set(_words(h))
        for alt in alternatives(want):
            aw = _words(alt)
            if aw and (set(aw) <= hw) and (len(aw) >= 2 or len(aw[0]) >= 4):
                return True
    return False


# ---------------------------------------------------------------- regions, documents, events
def _gate_ok(gate, text_c, topic_c):
    if not gate:
        return True
    words = CTX.get("topic_words", {}).get(gate, [])
    both = text_c + " " + topic_c
    return any(phrase_in(both, w) for w in words)


def _auto_regions():
    """Every region preset in the geography code is a region the narration can name ('the Balkans', 'Middle East')."""
    out = []
    known = {r["id"] for r in CTX["regions"]} | {r.get("territory") for r in CTX["regions"]}
    for key in geo.REGIONS:
        if key in known or key.endswith(("_1942", "_117", "_1683", "_1279")):
            continue
        phrase = key.replace("_", " ")
        out.append(dict(id=key, territory=key, phrases=[phrase], concepts=[phrase], must=[phrase], label=phrase.upper(), auto=True))
    return out


_AUTO = None


def _region_view(r):
    """(center, width) for a region entry: the table's own, or fitted to the region's shape."""
    if r.get("center") and r.get("width"):
        return list(r["center"]), float(r["width"])
    g = geo.region_geom(r.get("territory") or r["id"])
    if g is None:
        return [0.0, 30.0], 60.0
    x0, y0, x1, y1 = g.bounds
    span = max(x1 - x0, (y1 - y0) * 1.7)
    return [round((x0 + x1) / 2, 1), round(max(-55, min(65, (y0 + y1) / 2)), 1)], round(max(18.0, min(span * 1.5 + 6, 110.0)), 1)


def _country_point(name):
    from . import composer as CO
    return CO._country_point(name)


COLONIZE = re.compile(r"\b(establish|found|settl|plant|set up|sets up|build|built|creat)\w*\b", re.I)
COLONIZED = re.compile(r"\bcolon(?:iz|is)(?:ed|ing|ation|e)\b|\bcolony (?:was|were) (?:founded|established)", re.I)
WRITE = re.compile(r"\b(wrote|write|writing|drafted|draft|drafting|authored)\b", re.I)


def enrich(a, text, topic=""):
    """The beat analysis `a` plus meaning (a copy). Adds: regions, map (a story-fitted map spec), context (the document
    or event behind the sentence), frames, and puts the origin country of a colonization in the right role."""
    global _AUTO
    if _AUTO is None:
        _AUTO = _auto_regions()
    out = dict(a)
    t, tc = canon(text), canon(topic)
    found = []
    for r in CTX["regions"] + _AUTO:
        hit = next((p for p in r["phrases"] if phrase_in(t, p)), None)
        if not hit and r.get("generic_phrases") and _gate_ok(r.get("generic_gate"), t, tc):
            hit = next((p for p in r["generic_phrases"] if phrase_in(t, p)), None)
        if hit:
            found.append(dict(r, matched=hit))
    # a colony group named with the coast ("13 colonies ... Atlantic coast"): the colonies are the subject
    found.sort(key=lambda r: (r["id"] == "atlantic_coast", bool(r.get("auto")), -len(r.get("matched", ""))))
    frames = list(a.get("frames") or [])
    events = list(a.get("events") or [])
    if found and (COLONIZED.search(text or "") or (COLONIZE.search(text or "") and re.search(r"\bcolon(?:y|ies)\b", text or "", re.I))):
        frames.append("colonization")
        if "colonization" not in events:
            events.append("colonization")
    if WRITE.search(text or ""):
        frames.append("writing")
    # documents and events behind the sentence
    ctx_entry = None
    for kind in ("events", "documents"):
        for e in CTX[kind]:
            if any(phrase_in(t, p) for p in e["phrases"]) and _gate_ok(e.get("gate"), t, tc):
                verbs = [v for v in e.get("verbs", []) if phrase_in(t, v)]
                ctx_entry = dict(e, kind="event" if kind == "events" else "document", verbs_hit=verbs)
                var = next((v for v in e.get("variants") or [] if any(phrase_in(t, w) for w in v.get("when", []))), None)
                if var:         # the same event told another way ("the siege of Yorktown" vs "the surrender at Yorktown")
                    ctx_entry.update({k: v for k, v in var.items() if k not in ("when", "concepts")})
                    ctx_entry["concepts"] = list(e.get("concepts", [])) + list(var.get("concepts", []))
                break
        if ctx_entry:
            break
    out["context"] = ctx_entry
    if ctx_entry:           # "the colonists wrote the Constitution" is about the Constitution, not about a map of the colonies
        found = [r for r in found if r.get("matched") not in (r.get("generic_phrases") or [])]
    out["regions"] = found
    if not found:
        frames = [f for f in frames if f != "colonization"]
        events = [e for e in events if e != "colonization"]
    if ctx_entry and ctx_entry["kind"] == "event" and "event_tableau" not in events:
        events.append("event_tableau")
    if ctx_entry and ctx_entry["kind"] == "document" and ctx_entry["verbs_hit"] and "document_creation" not in events:
        events.append("document_creation")
    out["frames"], out["events"] = frames, events
    # the map that tells THIS story
    out["map"] = None
    if found and not (ctx_entry and ctx_entry["kind"] == "event"):
        primary = found[0]
        center, width = _region_view(primary)
        origin = None
        ship = "colonization" in frames             # a founding sentence sends a ship; a named far-away country is only shown
        for p in a.get("places") or []:
            if p.get("kind") == "country" and not re.search(r"united states|america", p["name"], re.I):
                pt = _country_point(p["name"])
                if pt:
                    origin = dict(name=p["name"], lon=round(pt[0], 1), lat=round(pt[1], 1))
                    break
        if origin:
            from . import composer as CO
            c2, w2 = CO.geo_view([(origin["lon"], origin["lat"]), tuple(center)])
            center, width = c2, max(width, w2)
        out["map"] = dict(region=primary["id"], territory=primary.get("territory") or "", label=primary.get("label") or "",
                          label_at=primary.get("label_at"), center=center, width=min(width, 110.0), origin=origin, ship=bool(origin and ship),
                          target=_region_view(primary), concepts=primary.get("concepts", []), extra=[r["id"] for r in found[1:]])
        # the agent country is where the colonists came from, not what the picture is about
        for p in out.get("places") or []:
            if origin and p.get("name") == origin["name"]:
                p["role"] = "origin"
    return out


def pattern_hint(a):
    """A pattern id the meaning pins down (so no AI choice is needed), or None."""
    c = a.get("context")
    if "colonization" in (a.get("frames") or []) and a.get("map"):
        return "COLONIZATION"
    if c and c["kind"] == "event":
        return "FAMOUS_EVENT"
    if c and c["kind"] == "document" and c.get("verbs_hit"):
        return c.get("pattern") or "DOCUMENT_SIGNING"
    if a.get("map") and (a["map"].get("region") == "atlantic_coast" or a["map"].get("territory")):
        return "MAP_EXPLANATION"
    return None


# ---------------------------------------------------------------- requirements
def _req(kind, value, any_=None, need="must", why=""):
    v = canon(value)
    alts = sorted({canon(x) for x in (any_ or [value]) if canon(x)} | {v})
    return dict(kind=kind, value=str(value), canon=v, any=alts, need=need, why=why)


def classify_need(text):
    """A free-text need written by Claude's plan ("North America", "13 colonies", "Declaration of Independence") as a
    typed requirement."""
    t = canon(text)
    for r in CTX["regions"] + (_AUTO or []):
        if any(phrase_in(t, p) for p in r["phrases"]) or t == canon(r["id"].replace("_", " ")):
            return _req("region", text, [text] + r.get("concepts", [])[:3], "must", "named by the plan")
    for e in CTX["documents"]:
        if any(phrase_in(t, p) for p in e["phrases"]):
            return _req("document", text, [text] + e["concepts"][:2], "must", "named by the plan")
    for e in CTX["events"]:
        if any(phrase_in(t, p) for p in e["phrases"]):
            return _req("event", text, [text, e["label"]] + e["concepts"][:2], "must", "named by the plan")
    for c in CTX["geo_concepts"]:
        if phrase_in(t, c) or phrase_in(canon(c), t):
            return _req("geo", text, [text, c], "must", "named by the plan")
    f = PE.find(str(text))
    if f:
        return _req("person", text, [f["name"], text], "must", "named by the plan")
    if re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", str(text)):
        return _req("time", text, [text], "should", "named by the plan")
    if re.search(r"\d", str(text)):
        return _req("number", text, [text], "must", "named by the plan")
    return _req("object", text, [text], "must", "named by the plan")


def requirements(a, text, needs=()):
    """What the picture for this beat must communicate. `a` is enrich()ed analysis; `needs` are Claude's strings."""
    R, seen = [], set()

    def add(r):
        k = r["canon"]
        if k not in seen and r["canon"]:
            seen.add(k)
            R.append(r)

    m = a.get("map")
    c = a.get("context")
    for r in (a.get("regions") or [])[:2]:
        for must in (r.get("must") or [r["id"].replace("_", " ")]):
            add(_req("region" if must == (r.get("must") or [None])[0] else "geo", must,
                     [must] + ([r["id"].replace("_", " ")] if must == (r.get("must") or [None])[0] else []), "must", f"the narration names {r['matched']!r}"))
    if m and m.get("origin"):
        add(_req("place", m["origin"]["name"], [m["origin"]["name"]] + [k for k, v in geo.ALIASES.items() if v == m["origin"]["name"] or (isinstance(v, list) and m["origin"]["name"] in v)],
                 "should", "where the colonies came from"))
    if c:
        if c["kind"] == "document":
            add(_req("document", c["id"].replace("_", " "), [c["id"].replace("_", " ")] + c["phrases"][:2], "must", "the document the sentence is about"))
            if c.get("group"):
                add(_req("group", c["group"], [c["group"], "founding fathers", "delegates"] if c["group"] == "delegates" else [c["group"]], "should", "who made it"))
            for p in c.get("who", [])[:2]:
                add(_req("person", p, [p], "should", "who made it"))
            if c.get("banner"):
                add(_req("time", c["banner"], [c["banner"], str(c.get("year") or "")], "should", "where and when"))
            if c.get("verbs_hit"):
                add(_req("action", "writing or signing", ["writing", "signing", "quill", "sign", "write"], "should", "what is happening"))
        else:
            add(_req("event", c["label"], [c["label"], c["id"].replace("_", " ")], "must", "the event the sentence is about"))
            if c.get("banner"):
                add(_req("time", c["banner"], [c["banner"], str(c.get("year") or "")], "should", "where and when"))
            for cr in c.get("crowds", [])[:2]:
                add(_req("group", cr["who"], [cr["who"]], "should", "who is there"))
            for p in c.get("people", [])[:1]:
                add(_req("person", p, [p], "should", "who is there"))
            for pr in c.get("props", [])[:2]:
                add(_req("object", pr["name"], [pr["name"]], "should", "what it looks like"))
    covered = {rq["canon"] for rq in R}
    for p in a.get("people") or []:
        if c and any(canon(p["name"]) in canon(x) or canon(x) in canon(p["name"]) for x in c.get("who", []) + c.get("people", [])):
            continue
        add(_req("person", p["name"], [p["name"]] + p["name"].split()[-1:], "must", "named in the narration"))
    for g in (a.get("groups") or [])[:2]:
        add(_req("group", g, [g], "should", "named in the narration"))
    for p in a.get("places") or []:
        if p.get("role") == "origin" or (m and canon(p["name"]) in covered):
            continue
        if m or (c and c["kind"] == "event"):
            continue                                    # the story-fitted map or event scene already says where
        add(_req("place", p["name"], [p["name"]] + [k for k, v in geo.ALIASES.items() if v == p["name"]][:3], "must", "named in the narration"))
    for n in (a.get("numbers") or [])[:2]:
        v = (n.get("shown") or n.get("text") or n.get("value") or str(n)) if isinstance(n, dict) else str(n)
        add(_req("number", v, [v], "must", "a figure the viewer should see"))
    if not (c and c.get("banner")) and a.get("years"):
        add(_req("time", str(a["years"][0]), [str(a["years"][0])], "should", "when"))
    for need in needs or []:
        add(classify_need(need))
    return R


# ---------------------------------------------------------------- what a scene shows
PROP_WORDS = {"quill": ["quill", "writing", "pen"], "document": ["document", "writing"], "scroll": ["document", "scroll"],
              "newspaper": ["document", "news"], "teapot": ["tea", "teapot"], "ship": ["ship", "boat", "sea"],
              "sailboat": ["ship", "boat"], "galleon": ["ship", "boat", "galleon", "sea"], "rowboat": ["boat", "river"], "crate": ["crate", "box"], "barrel": ["barrel"],
              "cannon": ["cannon", "artillery"], "musket": ["musket", "rifle", "weapon"], "tent": ["tent", "camp"],
              "flag": ["flag"], "bell": ["bell"], "fort": ["fort"], "church": ["church"], "horse": ["horse"], "fire": ["fire"],
              "crown": ["crown", "king"], "coin": ["money", "coin"], "check": ["approved", "check"], "dove": ["peace"]}
BG_WORDS = {"harbor": ["harbor", "port", "sea"], "parliament": ["parliament", "legislature", "chamber"],
            "interior": ["indoor", "room", "hall"], "battlefield": ["battle", "battlefield", "field"], "field": ["field"],
            "snow": ["snow", "winter"], "street": ["street", "town"], "palace": ["palace", "hall"], "sea": ["sea", "water"],
            "city": ["city"], "construction": ["construction"], "courtroom": ["court"], "prison": ["prison"]}


def _country_names(names):
    out = set()
    for n in names or []:
        if isinstance(n, str):
            out.add(canon(n))
            for k, v in geo.ALIASES.items():
                if v == n or (isinstance(v, list) and n in v):
                    out.add(canon(k))
    return out


def _view_box(bg):
    c = bg.get("center") or [0, 0]
    w = float(bg.get("width") or 60)
    lat_span = w * 0.5625 * max(0.25, math.cos(math.radians(c[1])))
    return c[0] - w / 2, c[1] - lat_span / 2, c[0] + w / 2, c[1] + lat_span / 2


def scene_concepts(scene):
    """The set of canonical concepts a scene communicates to someone who watches it muted."""
    S = set()
    if not isinstance(scene, dict):
        return S
    bg = scene.get("bg") or {}
    bt = bg.get("type")
    for w in BG_WORDS.get(bt, [bt] if bt else []):
        S.add(canon(w))

    def add_text(t):
        c = canon(t)
        if c:
            S.add(c)
            for w in _words(c):
                if len(w) >= 3:
                    S.add(w)

    for l in bg.get("labels") or []:
        add_text(l.get("text"))
    if bt == "map":
        x0, y0, x1, y1 = _view_box(bg)
        width = x1 - x0
        for name, box in CTX["geo_concepts"].items():
            bx0, by0, bx1, by1 = box
            if bx0 > bx1:
                continue
            cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
            if x0 <= cx <= x1 and y0 <= cy <= y1 and width >= 0.12 * (bx1 - bx0):
                S.add(canon(name))
        S.add("map")
        for t in bg.get("territories") or []:
            _territory_concepts(S, t)
    for el in scene.get("elements") or []:
        t = el.get("type")
        if t == "territory":
            _territory_concepts(S, el)
        elif t in ("text", "note", "sign", "board", "bubble", "label"):
            add_text(el.get("text") or el.get("title"))
            for ln in el.get("lines") or []:
                add_text(ln)
        elif t == "char":
            add_text(el.get("who"))
            if el.get("who"):
                S.add("person")
                for tok in str(el["who"]).split()[-1:]:
                    add_text(tok)
            for d in el.get("do") or []:
                if isinstance(d, dict) and d.get("act") in ("sign", "write", "lean"):
                    S.update({"writing", "signing"})
        elif t == "crowd":
            add_text(el.get("who"))
            S.add("crowd")
        elif t == "prop":
            n = el.get("name")
            for w in PROP_WORDS.get(n, [n]):
                S.add(canon(w))
            p = el.get("params") or {}
            for k in ("title", "label"):
                add_text(p.get(k))
            for ln in p.get("text") or []:
                add_text(ln)
            if n in ("document", "scroll", "newspaper") and p.get("title"):
                S.add(canon(p["title"]))
        elif t in ("city", "pointer"):
            add_text(el.get("name") or el.get("text"))
        elif t == "arrow":
            S.add("route")
            if el.get("units"):
                S.update(canon(w) for w in PROP_WORDS.get(str(el["units"]), [str(el["units"])]))
        elif t in ("timeline", "chart", "counter", "compare"):
            S.update({"number", "timeline" if t == "timeline" else "figure"})
            for k in ("title", "label", "text"):
                add_text(el.get(k))
            for it in el.get("items") or []:
                if isinstance(it, dict):
                    add_text(it.get("label") or it.get("text"))
                    add_text(it.get("year") or it.get("value"))
    return S


def _territory_concepts(S, el):
    reg = el.get("region")
    if reg:
        for r in CTX["regions"] + (_AUTO or []):
            if r.get("territory") == reg or r["id"] == reg:
                S.update(canon(c) for c in r.get("concepts", []))
                S.add(canon(r["id"].replace("_", " ")))
        S.add(canon(str(reg).replace("_", " ")))
    S.update(_country_names(el.get("countries")))
    for cname in el.get("countries") or []:
        if isinstance(cname, str):
            S.add(canon(cname))


NUMERIC = re.compile(r"\d")


def _satisfied(r, S):
    k = r["kind"]
    if k == "number":
        digits = re.findall(r"\d[\d,.]*", r["value"])
        have_digits = [c for c in S if NUMERIC.search(c)]
        return any(any(d.replace(",", "") in h.replace(",", "") for h in have_digits) for d in digits) or concept_match(r["canon"], S)
    if k == "time":
        yrs = re.findall(r"\b\d{3,4}\b", " ".join(r["any"]))
        if any(any(y in h for h in S) for y in yrs):
            return True
    return any(concept_match(alt, S) for alt in r["any"])


def coverage(reqs, scene):
    """How much of what the narration needs can be seen in the scene: weight(must)=1, weight(should)=0.5."""
    S = scene_concepts(scene)
    items, got, total = [], 0.0, 0.0
    for r in reqs:
        w = 1.0 if r["need"] == "must" else 0.5
        ok = _satisfied(r, S)
        total += w
        got += w if ok else 0.0
        items.append(dict(kind=r["kind"], value=r["value"], need=r["need"], satisfied=ok, why=r.get("why", "")))
    score = 1.0 if not total else round(got / total, 3)
    return dict(score=score, items=items, missing=[i for i in items if not i["satisfied"]],
                must_missing=[i for i in items if not i["satisfied"] and i["need"] == "must"], concepts=sorted(S)[:60])
