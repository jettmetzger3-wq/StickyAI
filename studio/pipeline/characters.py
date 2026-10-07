"""The character registry: every recurring person or group in a video, defined ONCE.

projects/<slug>/characters/<id>.json holds the definition (name, role, period, hat, hat color, coat, beard, personality,
which beats they appear in). Every scene reads the same definition, so Washington in scene 4 is still Washington in
scene 15. Known historical people start from knowledge/people.json (and the look any earlier video gave them);
the script's own cast (the AI's picks, or what you edited in the Script tab) always wins over the defaults.
"""
import os
import re

from ..engine.pen import resolve_kind
from ..knowledge import people as PE
from ..knowledge.analysis import analyze
from .project import read_json, write_json

FIELDS = ("kind", "hat_color", "coat", "look")


def slug_id(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").lower()).strip("_") or "person"


def build(script, analyses=None):
    """The registry for a script: [{id, name, kind, hat_color, coat, look, role, period, trait, known, beats}].
    `analyses` = one analyze() result per beat (computed here when not given)."""
    beats = script.get("beats") or []
    cast = [c for c in script.get("cast") or [] if isinstance(c, dict) and c.get("name")]
    if analyses is None:
        seen, analyses = set(), []
        for b in beats:
            analyses.append(analyze(b.get("text", ""), b.get("mood", "fun"), cast, seen))
    out, by_id = [], {}

    def add(entry):
        by_id[entry["id"]] = entry
        out.append(entry)
        return entry

    for c in cast:                                               # the script's cast first: it wins
        e = PE.find(c.get("name"))
        ent = dict(id=(e or {}).get("id") or slug_id(c["name"]), name=c["name"], known=bool(e), beats=[],
                   role=c.get("role") or (e or {}).get("role", ""),
                   period=c.get("period") or (f"{e['born']} to {e['died']}" if e else ""),
                   trait=c.get("trait") or (e or {}).get("trait", ""))
        base = PE.look(e) if e else {k: "" for k in FIELDS}
        for k in FIELDS:
            ent[k] = c.get(k) or base.get(k) or ""
        ent["kind"] = resolve_kind(ent["kind"] or "civ")
        add(ent)
    for i, a in enumerate(analyses):                             # known people the script never listed
        for p in a.get("people") or []:
            e = PE.find(p["name"], (a.get("years") or [None])[0])
            if e and e["id"] not in by_id and not any(x["name"].lower() == e["name"].lower() for x in out):
                ent = PE.cast_entry(e)
                ent["beats"] = []
                add(ent)
    for i, a in enumerate(analyses):                             # where each one appears
        text = (beats[i].get("text") if i < len(beats) else "") or ""
        low = text.lower()
        for ent in out:
            keys = {ent["name"].lower()} | {p for p in re.split(r"\s+", ent["name"].lower()) if len(p) >= 4}
            if any(re.search(r"\b" + re.escape(k) + r"s?\b", low) for k in keys):
                ent["beats"].append(i)
    return out


def as_cast(registry):
    """The registry in the shape check_scene()/apply_cast() expect (name, kind, hat_color, coat, look, role)."""
    return [{k: e.get(k, "") for k in ("name", "kind", "hat_color", "coat", "look", "role")} for e in registry]


def save(project, registry):
    d = project.p("characters")
    os.makedirs(d, exist_ok=True)
    keep = {f"{e['id']}.json" for e in registry} | {"index.json"}
    for fn in os.listdir(d):
        if fn.endswith(".json") and fn not in keep:
            os.remove(os.path.join(d, fn))
    for e in registry:
        write_json(os.path.join(d, f"{e['id']}.json"), e)
    write_json(os.path.join(d, "index.json"), [dict(id=e["id"], name=e["name"], beats=e["beats"][:40]) for e in registry])
    for e in registry:                                           # the next video starts from this look
        if e.get("known") and not PE.cache.has("people", PE.cache.key("look", e["id"])):
            PE.remember(e["id"], e)


def load(project):
    d = project.p("characters")
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".json") and fn != "index.json":
            e = read_json(os.path.join(d, fn))
            if e:
                out.append(e)
    return out


def merge_into_script(script, registry):
    """Put the full look back into script["cast"] (the old normalise step dropped coat and beard), and add the known
    people the script didn't list. Changes `script`."""
    cast = []
    for e in registry:
        cast.append({k: e.get(k, "") for k in ("name", "kind", "hat_color", "coat", "look", "role", "period", "trait")})
    script["cast"] = cast
    return script


def describe(e):
    """One line for the director prompt."""
    look = ", ".join(x for x in (e["kind"], e.get("hat_color"), (e.get("coat") and "coat " + e["coat"]), e.get("look")) if x)
    bits = [e["name"] + ":"]
    if e.get("role"):
        bits.append(e["role"][:60] + ";")
    if e.get("period"):
        bits.append(e["period"] + ";")
    bits.append("looks: " + look)
    return " ".join(bits)
