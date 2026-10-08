"""Reference images: use a picture as a BLUEPRINT for a scene, never as something to copy.

Step 1 (one AI call, cached by the image's hash): a vision-capable writer describes the picture's COMPOSITION as
structured data: who is where (normalised x/y), what they do, which props, what text, how the camera frames it, what the
eye sees first and why it works. It is told to describe storytelling structure, not to reproduce any artist's drawing.
Step 2 (local, deterministic): `to_scene` turns that composition into a Stickman Studio scene with the studio's own
characters, props, backgrounds and camera, reusing existing assets (and reporting anything it had to substitute).

Only use images you made or have the right to analyse. The image is never stored in the repository; the composition
JSON (and the technique notes) go to research/reference-clips/<id>.json.
"""
import hashlib
import json
import os

from .. import cache as CA
from ..engine.pen import resolve_kind
from ..engine.registry import guess_prop, resolve_prop
from ..engine.schema import BG_TYPES, POSE_ALIASES
from ..knowledge import people as PE
from . import assets as AS

SYSTEM = ("You are a storyboard analyst. You describe the composition of a reference picture as structured data so a different "
          "animation engine can rebuild the same storytelling idea with its own stickman art. You never reproduce or trace "
          "an artist's style details; you describe positions, actions, hierarchy and why the picture works. JSON only.")

SCHEMA = {"type": "object", "required": ["summary", "characters", "props"], "properties": {
    "summary": {"type": "string"}, "background": {"type": "object"}, "characters": {"type": "array"}, "props": {"type": "array"},
    "text": {"type": "array"}, "camera": {"type": "object"}, "hierarchy": {"type": "array"}, "technique": {"type": "string"}}}


def prompt():
    return f"""Analyse the attached reference picture as a scene COMPOSITION for a stickman history video.
All positions are normalised: x from 0 (left edge) to 1 (right edge), y from 0 (top) to 1 (bottom); a character's y is where
their feet are.

Return JSON:
- summary: one sentence: what is happening and what story point it makes.
- background: {{"kind": one of {', '.join(sorted(BG_TYPES))} or "map", "description": "...", "time": "day|dusk|night", "map_region": "<region if it is a map>"}}
- characters: every figure or group: {{"name": "<who, if clearly identifiable from caption or context, else empty>", "role": "<what they are>",
  "x","y", "size": "small|medium|large|giant", "facing": "left|right|front", "pose": "stand|point|arms_up|cheer|shrug|think|wave|hips|lean",
  "expression": "smile|grin|open|frown|smirk|flat|o", "hat": "<hat or nation: crown, tricorn, helmet, top hat, none...>", "coat_color": "<color>",
  "action": "<verb>", "group": false, "count": 1}}   (use group=true and a count for crowds)
- props: {{"name": "<what it is>", "x","y","size": "small|medium|large", "text": "<any words on it>"}}
- text: words visible in the picture {{"text","x","y","size": "small|medium|large"}}
- camera: {{"framing": "wide|medium|close", "focus": [x, y], "movement_idea": "<what a moving camera would do here>"}}
- hierarchy: what the eye reads first, second, third (short phrases)
- technique: 1 to 3 sentences on WHY this composition works (the reusable storytelling rule), in your own words.
Describe composition and storytelling only. Do not describe artistic style details that would let someone copy it."""


def image_key(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return CA.key("reference", h.hexdigest())


def analyze(llm, path, call=None):
    """The composition JSON for the image at `path` (cached; one vision request the first time). `call(llm, system, prompt,
    images, label)` may be passed to share the stage's usage ledger; otherwise the writer is called directly."""
    k = image_key(path)
    hit = CA.get("llm", k)
    if hit:
        return hit, True
    if not getattr(llm, "supports_images", False):
        raise RuntimeError(f"{getattr(llm, 'label', 'this writer')} can't look at images: choose Claude Code, which can")
    if call:
        data = call(llm, SYSTEM, prompt(), [path], "reference image")
    else:
        text, _ = llm.complete(SYSTEM, prompt(), schema=SCHEMA, images=[path], label="reference image")
        from ..providers import extract_json
        data = extract_json(text) if isinstance(text, str) else text
    if isinstance(data, dict):
        CA.put("llm", k, data, dict(kind="reference-image"))
    return data, False


# ------------------------------------------------------------------ composition -> scene (local)
SCALE = {"small": 0.55, "medium": 0.9, "large": 1.35, "giant": 2.0}
PROP_SCALE = {"small": 0.7, "medium": 1.0, "large": 1.6}
POSES = {"stand": "down", "point": "point_right", "arms_up": "up", "cheer": "cheer", "shrug": "shrug", "think": "think",
         "wave": "wave", "hips": "hips", "lean": "down"}


def _px(x, y):
    return int(max(0.0, min(1.0, float(x if x is not None else 0.5))) * 1920), int(max(0.0, min(1.0, float(y if y is not None else 0.9))) * 1080)


def to_scene(comp, cast=()):
    """(scene JSON, report) from a composition dict. report = dict(reused=[...], substituted=[...], missing=[...])."""
    rep = dict(reused=[], substituted=[], missing=[])
    comp = comp if isinstance(comp, dict) else {}
    bgd = comp.get("background") or {}
    kind = str(bgd.get("kind") or "paper").lower().replace(" ", "_")
    if kind == "map" and bgd.get("map_region"):
        bg = {"type": "map", "style": "dark", "center": [0, 30], "width": 80, "labels": []}
    else:
        got, how = AS.find("background", kind)
        if not got:
            rep["substituted"].append(f"background {kind!r} -> paper")
        bg = {"type": got or "paper"}
        if got and bgd.get("time") in ("dusk", "night"):
            bg["time"] = bgd["time"]
    els, order = [], 0
    for ch in comp.get("characters") or []:
        if not isinstance(ch, dict):
            continue
        x, y = _px(ch.get("x"), ch.get("y"))
        y = max(y, 780)
        hat = str(ch.get("hat") or "").lower().replace("top hat", "tophat")
        if ch.get("group"):
            el = {"type": "crowd", "kind": resolve_kind(hat) if hat and hat != "none" else "civ", "count": int(min(30, max(4, ch.get("count") or 10))),
                  "rows": 2, "x": x, "y": min(y, 940), "width": 700, "scale": 0.55, "who": str(ch.get("role") or ch.get("name") or "crowd")[:30]}
            if ch.get("coat_color"):
                el["coat"] = str(ch["coat_color"])
        else:
            name = str(ch.get("name") or "").strip()
            e = PE.find(name) if name else None
            el = {"type": "char", "x": x, "y": y, "scale": SCALE.get(str(ch.get("size") or "medium"), 0.9),
                  "kind": resolve_kind(PE.look(e)["kind"] if e else hat) if (e or (hat and hat != "none")) else "civ"}
            if e:
                el["who"] = e["name"]
                rep["reused"].append(f"person {e['name']} (historical people database)")
                lk = PE.look(e)
                for k in ("hat_color", "coat"):
                    if lk.get(k):
                        el[k] = lk[k]
            elif name:
                el["who"] = name[:30]
            if not e and ch.get("coat_color"):
                el["coat"] = str(ch["coat_color"])
            if ch.get("facing") == "left":
                el["flip"] = True
            pose = POSES.get(str(ch.get("pose") or "stand"), "down")
            el["pose"] = pose
            if ch.get("expression") in ("smile", "grin", "open", "frown", "smirk", "flat", "o"):
                el["mouth"] = ch["expression"]
        el["at"] = round(min(0.6, 0.03 + 0.08 * order), 2)
        order += 1
        els.append(el)
    for pr in comp.get("props") or []:
        if not isinstance(pr, dict):
            continue
        name = str(pr.get("name") or "")
        found, how = AS.find("prop", name)
        if not found:
            rep["missing"].append(name)
            continue
        if how != "exact":
            rep["substituted"].append(f"prop {name!r} -> {found} ({how})")
        else:
            rep["reused"].append(f"prop {found}")
        x, y = _px(pr.get("x"), pr.get("y"))
        el = {"type": "prop", "name": found, "x": x, "y": y, "scale": PROP_SCALE.get(str(pr.get("size") or "medium"), 1.0),
              "at": round(min(0.7, 0.1 + 0.08 * order), 2)}
        if pr.get("text") and found in ("document", "scroll", "newspaper"):
            el["params"] = {"title": str(pr["text"])[:22]}
        order += 1
        els.append(el)
    for t in comp.get("text") or []:
        if isinstance(t, dict) and t.get("text"):
            x, y = _px(t.get("x"), t.get("y"))
            els.append({"type": "text", "text": str(t["text"])[:40], "x": x, "y": min(y, 900), "size": {"small": 44, "medium": 64, "large": 90}.get(str(t.get("size") or "medium"), 64),
                        "color": "navy", "at": round(min(0.7, 0.1 + 0.08 * order), 2)})
            order += 1
    cam = comp.get("camera") or {}
    scene = {"bg": bg, "elements": els[:30], "camera": {"zoom": [1.0, 1.06]}, "note": "from a reference image: " + str(comp.get("summary") or "")[:120]}
    if cam.get("framing") in ("medium", "close") and isinstance(cam.get("focus"), (list, tuple)) and len(cam["focus"]) == 2:
        fx, fy = _px(cam["focus"][0], cam["focus"][1])
        scene["camera"] = {"shots": [{"at": 0, "zoom": 1.0}, {"at": 0.3, "zoom": 1.5 if cam["framing"] == "close" else 1.25, "focus": [fx, fy], "move": "cut"},
                                     {"at": 0.85, "zoom": 1.0, "move": "pan"}]}
    return scene, rep


def save_pattern(root, name, comp, report=None):
    """Keep the composition and its technique note (never the image) in research/reference-clips/."""
    d = os.path.join(root, "research", "reference-clips")
    os.makedirs(d, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")[:48] or "reference"
    path = os.path.join(d, slug + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(source="user-provided reference image (not stored)", composition=comp, report=report or {},
                       technique=(comp or {}).get("technique", ""), provenance="[user reference]"), f, indent=1, ensure_ascii=False)
    return path
