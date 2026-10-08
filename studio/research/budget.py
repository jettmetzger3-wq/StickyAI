"""The research budget: how much searching a video may do, tracked and enforced.

Claude Code does the web searching inside one request, so the limits are enforced three ways: they are written into
the request ("at most N searches, M sources, stop as soon as it is enough"), the answer is checked against them
(sources over the limit are dropped and the overrun is recorded), and whether the evidence is ENOUGH is judged locally
afterwards. If the budget is used up and the evidence still has holes, the run stops and asks; it never silently goes on.
"""
import re
import time

MODES = {   # the three research modes; every number can be overridden in Settings > research
    "fast": dict(max_queries=4, max_sources=6, depth="fast", max_research_time=120, min_claims=8, min_sources=3,
                 min_timeline=4, min_people=3),
    "normal": dict(max_queries=10, max_sources=15, depth="normal", max_research_time=300, min_claims=15, min_sources=5,
                   min_timeline=6, min_people=4),
    "deep": dict(max_queries=20, max_sources=30, depth="deep", max_research_time=600, min_claims=28, min_sources=9,
                 min_timeline=9, min_people=6),
}
DEFAULTS = dict(enabled=True, mode="", reuse_cached_research=True, require_approval_for_extra_research=True)
LIMIT_KEYS = ("max_queries", "max_sources", "depth", "max_research_time", "min_claims", "min_sources", "min_timeline",
              "min_people")


class ResearchBudgetReached(Exception):
    """The budget is used up and the evidence still has gaps: ask the user before researching more."""

    def __init__(self, info):
        super().__init__("the research budget is used up; approval is needed to research more")
        self.info = info


def mode_for(settings, options, gen_mode="normal"):
    """The research mode: the video's own choice, else Settings > research.mode, else the generation mode."""
    for src in ((options or {}).get("research_mode"), (settings.get("research") or {}).get("mode")):
        if src in MODES:
            return src
    return gen_mode if gen_mode in MODES else "normal"


def resolve_config(settings=None, options=None, gen_mode="normal"):
    """The effective research config for one video: mode defaults, then Settings > research, then the video's own."""
    settings = settings or {}
    cfg = dict(DEFAULTS)
    mode = mode_for(settings, options, gen_mode)
    cfg.update(MODES[mode])
    user = settings.get("research") or {}
    for k, v in user.items():
        if k in DEFAULTS or k in LIMIT_KEYS:
            if v is not None and v != "":
                cfg[k] = v
    for k, v in ((options or {}).get("research") or {}).items():
        if (k in DEFAULTS or k in LIMIT_KEYS) and v is not None and v != "":
            cfg[k] = v
    cfg["mode"] = mode
    for k in ("max_queries", "max_sources", "max_research_time", "min_claims", "min_sources", "min_timeline", "min_people"):
        try:
            cfg[k] = max(0, int(cfg[k]))
        except (TypeError, ValueError):
            cfg[k] = MODES[mode][k]
    return cfg


def norm_query(q):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", "", str(q or "").lower())).strip()


class Budget:
    """What one research run has used so far, against what it may use."""

    def __init__(self, cfg, granted=None):
        g = granted or {}
        self.cfg = cfg
        self.max_queries = cfg["max_queries"] + int(g.get("queries") or 0)
        self.max_sources = cfg["max_sources"] + int(g.get("sources") or 0)
        self.max_time = cfg["max_research_time"] + int(g.get("seconds") or 0)
        self.queries = []                 # normalised queries that were really run
        self.repeated = 0                 # queries that were run more than once (wasted)
        self.sources = set()
        self.cached_hits = 0              # things answered from the cache instead of the web
        self.started = time.time()
        self.overrun = []                 # notes about limits Claude exceeded

    # ---- charging
    def charge_queries(self, queries):
        for q in queries or []:
            n = norm_query(q)
            if not n:
                continue
            if n in self.queries:
                self.repeated += 1
            else:
                self.queries.append(n)
        if len(self.queries) > self.max_queries:
            self.overrun.append(f"{len(self.queries)} searches reported, {self.max_queries} allowed")

    def charge_sources(self, urls):
        for u in urls or []:
            if u:
                self.sources.add(str(u).split("#")[0].rstrip("/"))

    def hit_cache(self, n=1):
        self.cached_hits += n

    # ---- state
    @property
    def elapsed(self):
        return time.time() - self.started

    def exhausted(self):
        return (len(self.queries) >= self.max_queries or len(self.sources) >= self.max_sources
                or self.elapsed >= self.max_time)

    def remaining(self):
        return dict(queries=max(0, self.max_queries - len(self.queries)), sources=max(0, self.max_sources - len(self.sources)),
                    seconds=max(0, int(self.max_time - self.elapsed)))

    def report(self):
        return dict(mode=self.cfg["mode"], queries=len(self.queries), max_queries=self.max_queries,
                    sources=len(self.sources), max_sources=self.max_sources, repeated_queries=self.repeated,
                    cached_hits=self.cached_hits, seconds=int(self.elapsed), max_seconds=self.max_time,
                    exhausted=self.exhausted(), overrun=list(self.overrun))
