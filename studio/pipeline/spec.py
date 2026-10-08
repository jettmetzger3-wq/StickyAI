"""The structured scene spec: what a scene is, as plain machine-readable JSON the engine interprets, plus the storyboard
preview page and the final list of sources.

Per scene (projects/<slug>/storyboard/specs/NNN.json):
    scene_id, duration, narration, template, purpose, visual (the plan), visual_requirements (with what is satisfied),
    location, characters (with their registry asset ids), props, actions (what happens on screen, in order), camera,
    transition, claims (research ids), world (the world state after the scene), coverage, scene_hash.
The rendered scene JSON (scenes/NNN.json) is what the renderer reads; the spec describes it. Both are deterministic: the
same spec and assets always render the same pictures, so any single scene can be changed and re-rendered alone.
"""
import hashlib
import html
import json
import os

from ..knowledge import semantics as SM
from .project import write_json, read_json


def _hash(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:10]


def actions_of(scene):
    """What the scene does, in order, as short verbs ("show_map", "highlight_region:thirteen_colonies", ...)."""
    out = []
    bg = (scene or {}).get("bg") or {}
    if bg.get("type") == "map":
        out.append("show_map")
    else:
        out.append(f"set_background:{bg.get('type')}")
    for el in (scene or {}).get("elements") or []:
        t = el.get("type")
        if t == "territory":
            out.append("highlight_region:" + str(el.get("region") or ",".join(el.get("countries") or [])))
        elif t == "arrow":
            out.append(f"move_{el.get('units') or 'arrow'}")
        elif t == "text":
            out.append("label:" + str(el.get("text"))[:30])
        elif t == "char" and not el.get("narrator"):
            out.append("character:" + str(el.get("who") or el.get("kind")))
            for d in el.get("do") or []:
                if isinstance(d, dict) and d.get("act"):
                    out.append(f"{d['act']}:{el.get('who') or el.get('kind')}")
        elif t == "crowd":
            out.append("crowd:" + str(el.get("who") or el.get("kind")))
        elif t == "prop":
            out.append("show:" + str(el.get("name")))
        elif t in ("counter", "chart", "timeline"):
            out.append(f"show_{t}")
    cam = (scene or {}).get("camera") or {}
    for sh in cam.get("shots") or []:
        out.append(f"camera:{sh.get('move', 'cut')}:zoom{sh.get('zoom', 1.0)}" + (f":{sh['region']}" if sh.get("region") else ""))
    return out[:40]


def build(i, beat, scene, a, info, cov, world, duration, registry, claims_by_beat=None, transition_to=None):
    reg = {SM.canon(e["name"]): e for e in registry or []}
    chars = []
    for e in (scene or {}).get("elements") or []:
        if e.get("type") == "char" and not e.get("narrator") and e.get("who"):
            r = reg.get(SM.canon(e["who"]))
            chars.append(dict(name=e["who"], asset_id=(r or {}).get("id") or "cast:" + SM.canon(e["who"]).replace(" ", "_"),
                              kind=e.get("kind"), coat=e.get("coat")))
    bg = (scene or {}).get("bg") or {}
    location = dict(type=bg.get("type"), name=(world or {}).get("location", {}).get("name") or "",
                    region=(world or {}).get("location", {}).get("region") or "")
    if bg.get("type") == "map":
        location["center"], location["width"] = bg.get("center"), bg.get("width")
    cam = (scene or {}).get("camera") or {}
    spec = dict(
        scene_id=i, duration=round(float(duration or 0), 2), narration=beat.get("text"), template=(info or {}).get("pattern") or "",
        purpose=beat.get("purpose", ""), visual=beat.get("visual", ""),
        visual_requirements=[dict(value=m["value"], kind=m["kind"], need=m["need"], satisfied=m["satisfied"]) for m in (cov or {}).get("items", [])],
        location=location, characters=chars,
        props=[e.get("name") for e in (scene or {}).get("elements") or [] if e.get("type") == "prop"],
        actions=actions_of(scene),
        camera=dict(start="wide" if not cam.get("shots") else "wide", movement=("zoom" if cam.get("shots") or cam.get("zoom") else "static"),
                    shots=cam.get("shots") or [], zoom=cam.get("zoom")),
        transition=dict(type=(scene or {}).get("transition") or "auto", target_scene=transition_to),
        claims=(claims_by_beat or {}).get(i, beat.get("claims") or []),
        coverage=dict(score=(cov or {}).get("score"), missing=[m["value"] for m in (cov or {}).get("missing", [])]),
        world=world)
    spec["scene_hash"] = _hash(dict(spec, scene=scene))
    return spec


def write_all(pr, beats, scenes, analyses, plan_info, covs, worlds, durations, registry, claims_by_beat=None):
    """Write storyboard/specs/NNN.json for every scene and the preview page. Returns the specs {i: spec}."""
    d = pr.p("storyboard", "specs")
    os.makedirs(d, exist_ok=True)
    specs = {}
    n = len(beats)
    for i in range(n):
        sc = scenes.get(i)
        if not sc:
            continue
        beat = beats[i]
        spec = build(i, beat, sc, analyses[i] if i < len(analyses) else {}, (plan_info or {}).get(i) or {}, covs.get(i), worlds.get(i),
                     durations[i] if i < len(durations) else 0, registry, claims_by_beat, i + 1 if i + 1 < n else None)
        if beat.get("host"):
            spec["template"] = "HOST_" + str(beat["host"]).upper()
        specs[i] = spec
        write_json(os.path.join(d, f"{i:03d}.json"), spec)
    write_json(pr.p("storyboard", "specs.json"), dict(scenes={str(k): dict(template=v["template"], hash=v["scene_hash"], coverage=v["coverage"]["score"]) for k, v in specs.items()}))
    return specs


def _bar(score):
    pct = int(round(100 * (score if score is not None else 1)))
    col = "#2e9e5b" if pct >= 80 else "#e0a526" if pct >= 50 else "#d6453d"
    return f'<div class="bar"><span style="width:{pct}%;background:{col}"></span></div><b>{pct}%</b>'


def preview_html(title, specs, muted=None, sources=None, rel_previews="../previews"):
    """A static storyboard page: thumbnail, narration, visual description, duration, characters, location, transition,
    coverage and what is missing, for every scene. Open it in a browser; nothing is uploaded."""
    rows = []
    for i in sorted(specs):
        s = specs[i]
        cov = s["coverage"]
        reqs = "".join(f'<span class="{"ok" if r["satisfied"] else "no"}">{"✓" if r["satisfied"] else "✗"} {html.escape(str(r["value"]))}</span>'
                       for r in s["visual_requirements"][:8])
        m = (muted or {}).get("per_scene", {}).get(str(i))
        mt = ""
        if m:
            mt = '<div class="muted">muted test: ' + " ".join(f'<span class="{"ok" if m[k] else "no"}">{k}</span>' for k in ("who", "where", "what", "when", "change")) + "</div>"
        chars = ", ".join(html.escape(str(c["name"])) for c in s["characters"]) or "none"
        loc = html.escape(" / ".join(x for x in (s["location"].get("name"), s["location"].get("type")) if x))
        rows.append(f"""<article>
<img src="{rel_previews}/{i:03d}.jpg" alt="scene {i + 1}" onerror="this.style.visibility='hidden'">
<div class="body"><h3>Scene {i + 1} <small>{html.escape(str(s['template']))} · {s['duration']} s</small></h3>
<p class="nar">“{html.escape(str(s['narration']))}”</p>
<p class="vis">{html.escape(str(s.get('visual') or ' · '.join(s['actions'][:5])))}</p>
<div class="meta"><span>Location: {loc or '-'}</span><span>Characters: {chars}</span><span>Transition: {html.escape(str(s['transition']['type']))} → {('scene ' + str(s['transition']['target_scene'] + 1)) if s['transition']['target_scene'] is not None else 'end'}</span></div>
<div class="cov">Coverage {_bar(cov['score'])}</div><div class="reqs">{reqs}</div>{mt}</div></article>""")
    src = ""
    if sources:
        src = "<h2>Sources used</h2><ol>" + "".join(
            f'<li><a href="{html.escape(s["url"])}">{html.escape(s.get("title") or s["url"])}</a> <small>{html.escape(s.get("organization", ""))} · {s.get("tier", "")}</small></li>' for s in sources) + "</ol>"
    head = f"<h1>{html.escape(title)}</h1><p>{len(specs)} scenes" + (f" · muted-test score {int(round(100 * muted['score']))}%" if muted else "") + "</p>"
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Storyboard: {html.escape(title)}</title>
<style>body{{font:15px/1.45 system-ui,sans-serif;margin:0;padding:24px;background:#faf6ee;color:#262630}}h1{{margin:0 0 4px}}article{{display:flex;gap:16px;background:#fff;border:1px solid #e6dfd0;border-radius:14px;margin:14px 0;padding:12px;max-width:1100px}}
article img{{width:320px;height:180px;object-fit:cover;border-radius:8px;flex:none;background:#eee}}.body{{flex:1;min-width:0}}h3{{margin:0 0 4px}}h3 small{{color:#7a7468;font-weight:400}}
.nar{{margin:4px 0;font-style:italic}}.vis{{margin:4px 0;color:#5a554b}}.meta span{{display:inline-block;margin:0 14px 2px 0;color:#7a7468;font-size:13px}}
.bar{{display:inline-block;width:120px;height:9px;background:#eee;border-radius:5px;margin:0 8px;vertical-align:middle}}.bar span{{display:block;height:9px;border-radius:5px}}
.reqs span,.muted span{{display:inline-block;margin:2px 6px 0 0;padding:1px 8px;border-radius:10px;font-size:12px}}.ok{{background:#e3f4e9;color:#1d6b3d}}.no{{background:#fbe3e1;color:#9c2b24}}
.muted{{margin-top:4px;font-size:12px;color:#7a7468}}@media(max-width:760px){{article{{flex-direction:column}}article img{{width:100%;height:auto;aspect-ratio:16/9}}}}</style>
<body>{head}{''.join(rows)}{src}</body></html>"""


def sources_markdown(title, sources_used):
    """The final source list (only sources a scene really uses) as Markdown and as plain text for the video description."""
    md = [f"# Sources for {title}", ""]
    txt = ["Sources:"]
    for k, s in enumerate(sources_used, 1):
        label = s.get("title") or s["url"]
        md.append(f"{k}. [{label}]({s['url']}) - {s.get('organization', '') or 'unknown publisher'}"
                  + (f" ({s['date']})" if s.get("date") else "") + f" [{s.get('tier', '')}]")
        txt.append(f"- {label}: {s['url']}")
    return "\n".join(md) + "\n", "\n".join(txt)
