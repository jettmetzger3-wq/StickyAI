"""Cost estimates and approvals. Nothing paid runs unless the user approved an estimate for that stage.

An approval stores the estimate the user saw. A stage may run if its fresh estimate is within 125% of the
approved dollars/credits (estimates move a little once the real script exists). Otherwise it pauses and asks again.
"""
import json
import time

from .. import providers as P
from ..config import load_settings
from ..prompts import target_beats
from .project import read_json

MARGIN = 1.25


class NeedsApproval(Exception):
    def __init__(self, stage, cost, lines, over_budget=None):
        super().__init__(f"{stage} needs approval")
        self.stage, self.cost, self.lines = stage, cost, lines
        self.over_budget = over_budget      # dict(budget, spent) when this would push the video over its budget


def spent(meta):
    return round(sum(float(c.get("usd") or 0) for c in meta.get("costs") or []), 4)


def budget(meta):
    """Per-video spending limit in dollars (Settings > max_usd_per_video, raised when you approve going over)."""
    b = meta.get("budget_usd")
    if b is None:
        b = load_settings().get("max_usd_per_video") or 0
    return float(b or 0)


def _prov(meta, stage):
    pid = (meta.get("providers") or {}).get(stage) or P.TIERS["free"][stage]
    return P.get(stage, pid)


def _minutes(meta):
    return float((meta.get("options") or {}).get("minutes") or 10)


def stage_estimate(project, stage, meta=None, only=None, for_check=False):
    """Return (Cost, [(provider label, Cost)]) for one stage, using the real artifacts when they exist."""
    meta = meta or project.meta()
    opts = meta.get("options") or {}
    lines = []
    llm = _prov(meta, "llm")
    script = project.script() or {}
    beats = script.get("beats") or []
    n = len(beats) or target_beats(_minutes(meta))
    if only is not None and stage in ("storyboard",):
        n = max(1, len(only))
    src_meta = getattr(project, "source_meta", None) or read_json(project.p("source", "meta.json"), {}) or {}
    duration = float(src_meta.get("duration") or _minutes(meta) * 60)

    if stage == "source":
        if meta.get("mode") == "youtube" or opts.get("style_url"):
            tp = _prov(meta, "transcript")
            if tp.paid:
                lines.append((tp.label, tp.estimate(duration=duration)))
            if opts.get("watch", True) and llm.supports_images and llm.paid:
                lines.append((llm.label + " (watching frames)", llm.estimate_tokens(4 * 1700 * 3.5 + 3000, 3000)))
    elif stage == "script" and llm.paid:
        tchars = 0
        if meta.get("mode") == "youtube":
            tr = read_json(project.p("source", "transcript.json"), []) or []
            tchars = sum(len(s.get("text", "")) + 8 for s in tr) or duration * 16
        lines.append((llm.label, llm.estimate_tokens(min(tchars, 120000) + 9000, n * 70 + 1500)))
    elif stage == "storyboard" and llm.paid:
        batches = max(1, (n + 7) // 8)
        lines.append((llm.label, llm.estimate_tokens(batches * 24500, n * 650)))
    elif stage == "voice":
        vp = _prov(meta, "voice")
        if vp.paid:
            chars = sum(len(b["text"]) for b in beats) if beats else n * 140
            done = (project.voice() or {}).get("beats") or []
            if beats and done and project.voice().get("provider") == vp.id:
                # only lines whose text changed will be re-generated
                chars = sum(len(b["text"]) for i, b in enumerate(beats)
                            if i >= len(done) or done[i].get("text") != b["text"])
            lines.append((vp.label, vp.estimate(chars=chars)))
    elif stage == "mix":
        mp = _prov(meta, "music")
        if mp.paid:
            moods = {b.get("mood", "fun") for b in beats} or {"fun", "tense"}
            lines.append((mp.label, mp.estimate(moods=moods)))
    elif stage == "package":
        if llm.paid:
            lines.append((llm.label, llm.estimate_tokens(n * 160 + 3000, 1500)))
        ip = _prov(meta, "image")
        if ip.paid:
            lines.append((ip.label, ip.estimate()))
    elif stage == "shorts":
        sp = _prov(meta, "shorts")
        if sp.paid:
            q = meta.get("calliope_quote")
            if q:
                c = q["cost"]
                lines.append((sp.label, P.Cost(c.get("usd", 0), c.get("credits", 0), c.get("credit_unit", ""),
                                               c.get("known", True), c.get("note", ""))))
            elif not for_check:
                # the step asks Calliope for the exact price first and pauses for your OK on that number
                lines.append((sp.label, P.Cost(0.0, known=False, credit_unit="Calliope credits",
                                               note="Calliope quotes the exact credits first; you approve that number")))
    total = P.FREE
    for _, c in lines:
        total = total + c
    return total, lines


def estimate_all(project):
    meta = project.meta()
    out = {}
    for st in ("source", "script", "storyboard", "voice", "mix", "package", "shorts"):
        if meta.get("stages", {}).get(st, {}).get("status") == "skipped":
            continue
        c, lines = stage_estimate(project, st, meta)
        out[st] = dict(total=c.to_dict(), lines=[dict(provider=l, cost=c2.to_dict()) for l, c2 in lines])
    return out


def is_paid(cost, lines):
    return bool(lines) and not cost.is_free


def approve(project, stages_costs):
    """stages_costs: {stage: cost_dict}. Records what the user saw and clicked OK on.
    Approving a step that goes over the video's budget raises the budget to cover it."""
    def f(m):
        ap = m.setdefault("approvals", {})
        for st, c in stages_costs.items():
            ap[st] = dict(usd=float(c.get("usd") or 0), credits=float(c.get("credits") or 0),
                          known=bool(c.get("known", True)), at=time.time())
        pend = m.get("pending")
        if pend and pend.get("type") == "approval" and pend.get("stage") in stages_costs:
            if pend.get("over_budget"):
                usd = float(stages_costs[pend["stage"]].get("usd") or 0)
                m["budget_usd"] = round(max(budget(m), spent(m) + usd * MARGIN + 0.01), 2)
            m["pending"] = None
    project.update(f)


def check(project, stage, only=None):
    """Raise NeedsApproval unless this stage is free or already approved for (about) this amount,
    and it keeps the video under its budget."""
    cost, lines = stage_estimate(project, stage, only=only, for_check=True)
    if not is_paid(cost, lines):
        return cost
    meta = project.meta()
    b = budget(meta)
    if b > 0 and cost.usd > 0 and spent(meta) + cost.usd > b + 0.005 and not meta.get("auto_approve"):
        raise NeedsApproval(stage, cost, lines, over_budget=dict(budget=b, spent=spent(meta)))
    ap = (meta.get("approvals") or {}).get(stage)
    if ap:
        ok_usd = cost.usd <= ap["usd"] * MARGIN + 0.01
        ok_cr = cost.credits <= ap["credits"] * MARGIN + 1
        if ok_usd and ok_cr:
            return cost
    raise NeedsApproval(stage, cost, lines)


def record(project, stage, provider, usd=0.0, credits=0.0, note=""):
    def f(m):
        m.setdefault("costs", []).append(dict(stage=stage, provider=provider, usd=round(float(usd or 0), 4),
                                              credits=round(float(credits or 0), 1), note=note, at=time.time()))
    project.update(f)


def balances(meta):
    """Balances for the paid providers this project uses (only where the provider API exposes it)."""
    out = {}
    for stage in ("transcript", "llm", "voice", "music", "image", "shorts"):
        try:
            p = _prov(meta, stage)
        except KeyError:
            continue
        if p.paid and p.available()[0]:
            b = p.balance()
            if b:
                out[p.id] = b
    return out


def describe(cost_dict):
    c = cost_dict
    parts = []
    if c.get("usd"):
        parts.append(f"~${c['usd']:.2f}")
    if c.get("credits"):
        parts.append(f"~{c['credits']:,.0f} {c.get('credit_unit') or 'credits'}")
    if not c.get("known", True):
        parts.append("amount set by provider")
    return ", ".join(parts) or "free"


class Draft:
    """A not-yet-created project, so the New Video form can show estimates before anything runs."""

    def __init__(self, mode, providers, options, duration=None):
        self._meta = dict(mode=mode, providers=providers, options=options,
                          stages={"source": {"status": "pending" if (mode == "youtube" or options.get("style_url")) else "skipped"}})
        self.source_meta = {"duration": duration} if duration else None

    def meta(self):
        return self._meta

    def script(self):
        return None

    def voice(self):
        return {}

    def p(self, *parts):
        return "/nonexistent/" + "/".join(parts)


def estimate_draft(mode, providers, options, duration=None):
    return estimate_all(Draft(mode, providers, options, duration))
