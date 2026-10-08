"""The research orchestrator: reuse what is cached, research only what is missing, stay inside the budget, stop when
the evidence is enough, and ask before going over.

    research_topic(...) -> Research        (or raises ResearchBudgetReached when it needs the user's OK to continue)

The only AI work is the one budgeted web-research request per pass; the decisions around it are code.
"""
import time

from . import budget as BD
from . import claims as CL
from . import sources as SRC
from . import store as ST

SYSTEM = ("You are the research desk of a history video studio. You search the web, open reliable sources (national archives, "
          "libraries, museums, universities, governments, reputable encyclopedias), and record facts WITH the source that says "
          "so. You never invent a source, URL, quote or number. If you cannot find or open something, you say so. You only "
          "answer with JSON.")


def research_prompt(topic, minutes, cfg, focus=(), gaps=(), known=0, web=True):
    lim = (f"BUDGET: at most {cfg['max_queries']} web searches and at most {cfg['max_sources']} sources opened, in at most "
           f"{cfg['max_research_time']} seconds. Stop as soon as you have enough reliable evidence; do not search for the sake "
           f"of searching. Prefer primary and official sources (archives.gov, loc.gov, si.edu, nps.gov, universities, museums, "
           f"Britannica); avoid blogs, SEO articles and unsourced summaries.") if web else (
        "You cannot search the web in this run: answer from your own knowledge, give NO urls, and mark every claim "
        "confidence \"unverified\".")
    need = ""
    if focus:
        need += f"\nFOCUS: the video is about these angles; make sure they are covered: {', '.join(focus)}."
    if gaps:
        need += f"\nKNOWN GAPS in what is already saved ({known} claims): " + "; ".join(gaps) + ". Research ONLY these gaps; do not repeat what is known."
    return f"""Research the topic "{topic}" for a {minutes:g}-minute stickman history video.
{lim}{need}

Return JSON with:
- summary: 3 sentences on what happened and why it matters.
- timeline: 8 to 14 key events {{"year": 1775, "event": "max 12 words"}} in order.
- people: 6 to 10 key people {{"name","role" (max 8 words),"years","look" (famous clothing/hair/hat, max 10 words),"trait" (max 6 words)}}.
- places: 4 to 8 key places {{"name","note"}} (say WHERE each is: region, coast, colony, city).
- documents: important documents/laws/newspapers {{"name","lines":[2-4 REAL short lines (max 24 characters each) that are written in it]}}.
- numbers: 5 to 8 striking numbers {{"claim","value"}}.
- visuals: 5 memorable pictures a viewer should see (a famous scene, object or moment), one line each.
- claims: {max(cfg['min_claims'], 12)} to {cfg['min_claims'] * 2} atomic factual statements the script is likely to use (dates, names, numbers, causes, places, consequences). Each: {{"claim": "one checkable sentence", "url": "the page that says it", "evidence": "a short phrase or paraphrase from that page", "confidence": "high|medium|low", "date": "publication date if shown"}}.
- sources: every page you used {{"url","title","organization","date"}} (only pages you really opened).
- queries_used: the searches you actually ran (strings).
- gaps: anything important you could NOT establish.

Answer with JSON only."""


class Research:
    def __init__(self, topic, slug, brief, claims, sources, report, cached, sufficient, gaps, metadata=None):
        self.topic, self.slug, self.brief, self.claims, self.sources = topic, slug, brief, claims, sources
        self.report, self.cached, self.sufficient, self.gaps = report, cached, sufficient, gaps
        self.metadata = metadata or {}


def assess(brief, claims, sources, cfg, web=True):
    """Is the evidence ENOUGH? Plain counting and source quality, no AI. Returns (enough, [what is missing])."""
    gaps = []
    b = brief or {}
    sourced = [c for c in claims if c.get("url")]
    if web:
        if len(sourced) < cfg["min_claims"]:
            gaps.append(f"{cfg['min_claims'] - len(sourced)} more sourced claims")
        urls = {c["url"] for c in sourced} | {s["url"] for s in sources}
        if len(urls) < cfg["min_sources"]:
            gaps.append(f"{cfg['min_sources'] - len(urls)} more independent sources")
        strong = [u for u in urls if SRC.quality(u)["score"] >= 0.9]
        okay = [u for u in urls if SRC.quality(u)["score"] >= 0.65]
        if urls and not strong and len(okay) < 2:
            gaps.append("no archive, government, museum or university source")
    elif len(claims) < cfg["min_claims"]:
        gaps.append(f"{cfg['min_claims'] - len(claims)} more claims")
    if len([t for t in b.get("timeline") or [] if isinstance(t, dict)]) < cfg["min_timeline"]:
        gaps.append("a longer timeline")
    if len([p for p in b.get("people") or [] if isinstance(p, dict)]) < cfg["min_people"]:
        gaps.append("more key people")
    return (not gaps), gaps


def focus_gaps(focus, brief, claims):
    """Focus words (angles of this video) that nothing in the saved research mentions."""
    text = " ".join([c["claim"] for c in claims] + [str(brief)]).lower()
    return [f for f in focus if f.lower() not in text]


def _validate(raw, cfg, budget, web):
    """The researcher's answer as clean records, trimmed to the budget."""
    raw = raw if isinstance(raw, dict) else {}
    srcs = [s for s in (CL.make_source(x) for x in raw.get("sources") or []) if s] if web else []
    if len(srcs) > budget.max_sources:
        budget.overrun.append(f"{len(srcs)} sources returned, {budget.max_sources} allowed: kept the {budget.max_sources} best")
        srcs = sorted(srcs, key=lambda s: -s["score"])[:budget.max_sources]
    by_url = {s["url"]: s for s in srcs}
    claims = []
    for x in raw.get("claims") or []:
        c = CL.make_claim(x, by_url)
        if not c:
            continue
        if not web or (c["url"] and c["url"] not in by_url and len(by_url) >= budget.max_sources):
            c.update(url="", confidence="unverified", tier="none")      # a source we dropped or never had: say so, don't pretend
        elif c["url"] and c["url"] not in by_url:
            s = CL.make_source(dict(url=c["url"], title=c["source"], organization=c["organization"], date=c["date"]))
            if s:
                by_url[c["url"]] = s
                srcs.append(s)
        claims.append(c)
    budget.charge_queries(raw.get("queries_used") if isinstance(raw.get("queries_used"), list) else [])
    budget.charge_sources([s["url"] for s in srcs])
    brief = {k: raw.get(k) for k in ("summary", "people", "places", "documents", "numbers", "timeline", "visuals") if raw.get(k)}
    gaps = [str(g)[:160] for g in raw.get("gaps") or [] if g] if isinstance(raw.get("gaps"), list) else []
    return brief, claims, srcs, gaps


def research_topic(ctx, llm, call, topic, minutes, cfg, focus=(), grant=None, web=None):
    """Research `topic` inside the budget. `call(llm, system, prompt, label, web)` runs one cached AI request and returns
    the parsed JSON. `grant` = {"queries": n, "sources": n, "seconds": n} the user approved on top of the budget.
    Returns a Research, or None when research is turned off; raises BD.ResearchBudgetReached when the evidence still has
    holes, the budget is spent and extra research was not approved."""
    if not cfg.get("enabled", True):
        return None
    web = bool(getattr(llm, "supports_web", False)) if web is None else web
    if grant:           # an approved top-up is its own small budget: exactly what the user agreed to, no more
        cfg = dict(cfg, max_queries=int(grant.get("queries") or 0), max_sources=int(grant.get("sources") or 0),
                   max_research_time=int(grant.get("seconds") or 0))
    budget = BD.Budget(cfg)
    cached_slug, extra = ST.find(topic)
    saved = ST.load(cached_slug) if (cached_slug and cfg.get("reuse_cached_research", True)) else None
    slug = cached_slug or ST.slug(topic)
    brief, claims, sources = ((saved or {}).get("brief") or {}), ((saved or {}).get("claims") or []), ((saved or {}).get("sources") or [])
    meta = dict((saved or {}).get("metadata") or {})
    foc = list(focus or []) + [w for w in extra if len(w) > 3]
    enough, gaps = assess(brief, claims, sources, cfg, web) if saved else (False, ["no saved research for this topic"])
    gaps = gaps + [f"angle not covered yet: {f}" for f in focus_gaps(foc, brief, claims)] if saved else gaps
    if saved and not [g for g in gaps]:
        budget.hit_cache(len(claims))
        ctx.log(f"research: reused the saved research on '{topic}' ({len(claims)} claims, {len(sources)} sources): 0 searches")
        return Research(topic, slug, brief, claims, sources, budget.report(), True, True, [], meta)
    passes = 0
    while True:
        passes += 1
        known = len(claims)
        only_gaps = gaps if saved or passes > 1 else []
        rem = budget.remaining()
        pcfg = cfg if passes == 1 else dict(cfg, max_queries=max(1, rem["queries"]), max_sources=max(1, rem["sources"]),
                                            max_research_time=max(30, rem["seconds"]))
        prompt = research_prompt(topic, minutes, pcfg, foc, only_gaps, known, web)
        ctx.log(f"research ({cfg['mode']}): pass {passes}, {'filling gaps: ' + '; '.join(only_gaps) if only_gaps else 'first pass'}"
                f"{'' if web else ' (no web search on this writer)'}")
        raw = call(llm, SYSTEM, prompt, "research" if passes == 1 else f"research gaps {passes}", web)
        nb, nc, ns, ngaps = _validate(raw, cfg, budget, web)
        if not (nb or nc):
            ctx.warn("the researcher returned nothing usable" + (" (the script is written from the model's own knowledge)" if passes == 1 else ""))
            break
        brief = ST.merge_brief(brief, nb)
        claims = CL.merge_claims(claims, nc)
        sources = CL.merge_sources(sources, ns)
        enough, gaps = assess(brief, claims, sources, cfg, web)
        gaps = gaps + [f"angle not covered yet: {f}" for f in focus_gaps(foc, brief, claims)]
        meta.update(mode=cfg["mode"], web=web, budget=budget.report(), gaps=gaps + [g for g in ngaps if g not in gaps],
                    passes=int(meta.get("passes") or 0) + 1, last_pass=time.time())
        ST.save(slug, topic, brief, claims, sources, meta)
        if enough or not gaps:
            ctx.log(f"research: enough evidence ({len(claims)} claims, {len(sources)} sources, {len(budget.queries)} searches reported)")
            break
        if passes >= 2 or budget.exhausted() or not web:
            # budget spent (or the one follow-up pass is done) and the evidence still has holes: never go on silently
            if cfg.get("require_approval_for_extra_research", True) and web and not grant:
                info = dict(topic=topic, slug=slug, gaps=gaps, budget=budget.report(), claims=len(claims), sources=len(sources),
                            proposal=dict(queries=max(3, cfg["max_queries"] // 2), sources=max(3, cfg["max_sources"] // 2),
                                          seconds=max(60, cfg["max_research_time"] // 2)))
                raise BD.ResearchBudgetReached(info)
            ctx.warn("research stopped with gaps: " + "; ".join(gaps))
            break
    meta["budget"] = budget.report()
    ST.save(slug, topic, brief, claims, sources, meta)
    return Research(topic, slug, brief, claims, sources, budget.report(), False, enough, gaps, meta)
