"""The VIDEO ESTIMATE: how many AI calls and tokens a video will use, before it runs.

It uses the real script when there is one (so cached plans and props are counted as cached), otherwise the number of
beats a video of that length will have. Numbers come from the prompt sizes measured in this codebase (see
docs/architecture-upgrade.md); the "old way" line is what the same video cost before the director existed (a full
scene-language request for every batch of scenes), so the saving is visible.
"""
import math

from .. import cache as CA
from ..config import load_settings
from ..knowledge import patterns as PT
from ..prompts import target_beats
from ..usage import tokens
from . import modes as MD
from ..research import budget as RB, engine as RS_EN, store as RS_ST
from .project import read_json

SCENE_LANGUAGE_TOK = 9400       # the full scene-language manual (33.6k chars) every classic batch re-sends
EXAMPLES_TOK = 5700             # the 20 example scenes
PLAN_FIXED_TOK = 2400           # the pattern catalog + instructions of one director request
PLAN_PER_BEAT_IN = 95           # a beat and the studio's local hints
PLAN_PER_BEAT_OUT = 95          # pattern + slots + a line
SCENE_OUT_TOK = 600             # one full scene as JSON
CUSTOM_EXAMPLES_TOK = 1800      # the six key examples the custom path sends instead of twenty
CUSTOM_SHARE = {"fast": 0.0, "normal": 0.08, "deep": 0.1}
WARN_TOKENS = 250_000
WARN_CALLS = 30


def _beats(project, meta):
    sc = (project.script() or {}) if hasattr(project, "script") else {}
    beats = sc.get("beats") or []
    minutes = float((meta.get("options") or {}).get("minutes") or 10)
    return beats, sc, (len(beats) or target_beats(minutes)), minutes


def item(task, label, calls, in_tok, out_tok, cached=0, note=""):
    return dict(task=task, label=label, calls=calls, cached=cached, in_tok=int(in_tok), out_tok=int(out_tok), note=note)


def classic_items(n, batch=12):
    """What the same storyboard cost with the old method: one full request per batch of scenes."""
    batches = max(1, math.ceil(n / batch))
    return [item("storyboard", "classic storyboard", batches, batches * (SCENE_LANGUAGE_TOK + EXAMPLES_TOK + batch * 120),
                 n * SCENE_OUT_TOK, note="old method: the full scene manual in every request"),
            item("props", "props", 1, 4000, 4000)]


def estimate_video(project, meta=None):
    meta = meta or project.meta()
    opts = meta.get("options") or {}
    st = load_settings()
    prof = MD.profile(meta, settings=st)
    beats, script, n, minutes = _beats(project, meta)
    engine = opts.get("storyboard_engine") or st.get("storyboard_engine") or "director"
    youtube = meta.get("mode") == "youtube" or bool(opts.get("style_url"))
    items = []
    if youtube and opts.get("watch", True):
        items.append(item("watch", "watching the source video", 1, 5000, 1000))
    research = None
    rc = RB.resolve_config(st, opts, prof["name"])
    if rc["enabled"] and (prof["research"] or opts.get("research_mode") in RB.MODES) and meta.get("topic"):
        topic = str(meta.get("topic") or script.get("title") or "")
        slug_, extra = RS_ST.find(topic)
        saved = RS_ST.load(slug_) if slug_ else None
        covered = False
        if saved:
            enough, gaps = RS_EN.assess(saved["brief"], saved["claims"], saved["sources"], rc, True)
            covered = enough and not RS_EN.focus_gaps([w for w in extra if len(w) > 3], saved["brief"], saved["claims"])
        research = dict(mode=rc["mode"], max_queries=rc["max_queries"], max_sources=rc["max_sources"], saved=bool(saved), covered=covered,
                        searches=0 if covered else rc["max_queries"])
        items.append(item("research", f"web research ({rc['mode']}: up to {rc['max_queries']} searches, {rc['max_sources']} sources)",
                          0 if covered else 1, 1500, 3500 + 120 * rc["min_claims"], cached=1 if covered else 0,
                          note="answered from the saved research on this topic: 0 searches" if covered else
                          ("part of the topic is saved: only the gaps are researched" if saved else "")))
    tr = 0
    if meta.get("mode") == "youtube":
        segs = read_json(project.p("source", "transcript.json"), []) if hasattr(project, "p") else []
        tr = tokens(sum(len(s.get("text", "")) + 8 for s in segs or []) or float(opts.get("duration") or minutes * 60) * 16)
        tr = min(tr, 33000)
    items.append(item("script", "writing the script", 1, 1600 + tr, n * 60 + 1500))
    if prof["factcheck"] and opts.get("fact_check", st.get("fact_check", True)) is not False:
        items.append(item("factcheck", "fact-check", 1, tokens(n * 260 + 4000), 1500,
                          note="with web search; 0 calls when the sourced research already covers every year, number and name" if research else "with web search"))
    if prof["smooth"]:
        items.append(item("script", "smoothing the flow (only if the script jumps around)", 0, 2000, 1000, note="0-1 calls"))
    if engine == "director":
        cast = [c for c in script.get("cast") or [] if isinstance(c, dict)]
        reg = [dict(name=c.get("name"), kind=c.get("kind"), hat_color=c.get("hat_color"), coat=c.get("coat"), look=c.get("look")) for c in cast]
        from . import director as DR
        cached = new = 0
        for b in beats:
            if b.get("host"):
                continue
            if CA.has("plans", DR.plan_key(b, [dict(e, hat_color=e.get("hat_color"), coat=e.get("coat"), look=e.get("look")) for e in reg])):
                cached += 1
            else:
                new += 1
        if not beats:
            new = n
        if prof["name"] == "fast":
            new = int(new * 0.4)                             # confident local matches need no AI at all
        calls = math.ceil(new / prof["plan_batch"]) if new else 0
        items.append(item("storyboard", "director plan (pattern + details per scene)", calls,
                          calls * PLAN_FIXED_TOK + new * PLAN_PER_BEAT_IN, new * PLAN_PER_BEAT_OUT, cached=cached,
                          note=f"{cached} of {cached + new} scenes already planned" if cached else ""))
        custom_n = int(round((new + cached) * CUSTOM_SHARE[prof["name"]])) if prof["custom_ai"] else 0
        if custom_n:
            size = 12
            c_calls = math.ceil(custom_n / size)
            items.append(item("storyboard", "full scene writer (only for scenes no pattern fits)", c_calls,
                              c_calls * (SCENE_LANGUAGE_TOK + CUSTOM_EXAMPLES_TOK + size * 120), custom_n * SCENE_OUT_TOK,
                              note=f"about {custom_n} scenes (usually 5-15%)"))
            if prof["props_ai"] and not CA.get("props", "_index"):
                items.append(item("props", "drawing extra props", 1, 4000, 4000))
            elif prof["props_ai"]:
                items.append(item("props", "drawing extra props", 0, 4000, 4000, note="0-1 calls: reused from earlier videos when possible"))
        if prof["review_ai"]:
            items.append(item("storyboard", "AI fix for scenes the review couldn't fix", 2, 2 * 9400, 2 * 600, note="up to 6 scenes"))
    else:
        items += classic_items(n, 12)
    if prof["package_ai"]:
        items.append(item("package", "titles, description, thumbnail text", 1, tokens(n * 160 + 3000), 1500))
    if prof["short_ai"]:
        items.append(item("short", "picking the Short's moment", 1, tokens(n * 120 + 2500), 800))
    tot = dict(calls=sum(i["calls"] for i in items), cached=sum(i["cached"] for i in items),
               in_tok=sum(i["in_tok"] for i in items), out_tok=sum(i["out_tok"] for i in items))
    tot["tokens"] = tot["in_tok"] + tot["out_tok"]
    old = [i for i in items if i["task"] not in ("storyboard", "props")] + classic_items(n, 12)
    base = dict(calls=sum(i["calls"] for i in old), tokens=sum(i["in_tok"] + i["out_tok"] for i in old))
    warn = []
    if tot["tokens"] > WARN_TOKENS or tot["calls"] > WARN_CALLS:
        warn.append(f"This is a big video for your Claude plan (about {tot['tokens']:,} tokens in {tot['calls']} calls). "
                    f"Fast mode uses far less.")
    return dict(mode=prof["name"], mode_label=prof["label"], beats=n, engine=engine, items=items, total=tot,
                old_way=base, saved_pct=round(100 * (1 - tot["tokens"] / base["tokens"])) if base["tokens"] else 0, warnings=warn,
                research=research, levels=levels(items), usage_level=level(tot["tokens"]))


def level(tokens_):
    return "LOW" if tokens_ < 30_000 else "MEDIUM" if tokens_ < 90_000 else "HIGH"


def levels(items):
    """LOW / MEDIUM / HIGH per kind of work, plus the parts that never use the AI (rendering is always local)."""
    def toks(*tasks):
        return sum(i["in_tok"] + i["out_tok"] for i in items if i["task"] in tasks and i["calls"])
    out = {}
    for name, tasks in (("Research", ("research",)), ("Script", ("script",)), ("Fact check", ("factcheck",)),
                        ("Storyboard and scene planning", ("storyboard",)), ("Props, titles and Short", ("props", "package", "short"))):
        t = toks(*tasks)
        out[name] = "NONE" if not t else "LOW" if t < 8_000 else "MEDIUM" if t < 25_000 else "HIGH"
    out["Rendering, animation, audio, video"] = "LOCAL (no AI)"
    return out
