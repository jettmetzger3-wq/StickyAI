"""Generation modes: how much AI a video uses.

FAST    for testing and quick drafts. No research, no fact-check, no custom prop drawing; the AI only writes the script
        and one compact "director plan" per ~24 scenes. Beats the plan can't express are drawn by the local composer
        and the old rule-based scenes (no AI). Titles and the Short's moment come from local rules.
NORMAL  the everyday mode. Script, flow smoothing when the script jumps around, a plan per ~16 scenes, the full
        storyboard writer only for the scenes the plan marks "custom", props drawn once and cached, a local review
        that fixes weak scenes.
DEEP    the best video. A cached topic brief first (key people, places, documents, numbers), fact-check with web search,
        a plan per ~10 scenes with more context, the full storyboard writer for custom scenes, and an AI pass that
        fixes whatever the local review still flags.

Choose per video on the New Video page; the default is Settings > gen_mode.
"""
from ..config import load_settings

DEFAULT = "normal"

MODES = {
    "fast": dict(
        label="Fast", blurb="Quick drafts and testing: the fewest AI calls, everything cached.",
        research=False, factcheck=False, smooth=False, props_ai=False, plan_batch=24, custom_ai=False,
        review_ai=False, package_ai=False, short_ai=False, plan_examples=0),
    "normal": dict(
        label="Normal", blurb="Everyday quality with low usage: a compact plan, AI only where it matters.",
        research=False, factcheck=True, smooth=True, props_ai=True, plan_batch=16, custom_ai=True,
        review_ai=False, package_ai=True, short_ai=True, plan_examples=2),
    "deep": dict(
        label="Deep", blurb="Best quality: topic research, web fact-check, richer plan, AI polish. Uses the most.",
        research=True, factcheck=True, smooth=True, props_ai=True, plan_batch=10, custom_ai=True,
        review_ai=True, package_ai=True, short_ai=True, plan_examples=4),
}


def name_of(meta=None, opts=None, settings=None):
    """The mode for this video: its own option, else Settings > gen_mode, else normal (unknown names are skipped)."""
    opts = opts if opts is not None else ((meta or {}).get("options") or {})
    for cand in (opts.get("gen_mode"), (settings if settings is not None else load_settings()).get("gen_mode")):
        c = str(cand or "").lower()
        if c in MODES:
            return c
    return DEFAULT


def profile(meta=None, opts=None, settings=None):
    p = dict(MODES[name_of(meta, opts, settings)])
    p["name"] = name_of(meta, opts, settings)
    return p


def catalog():
    return [dict(id=k, label=v["label"], blurb=v["blurb"]) for k, v in MODES.items()]
