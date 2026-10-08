"""Controlled research: one budgeted web-research pass per topic, cached, with every claim tied to a source.

    budget.py   how much research is allowed (modes, limits, approval) and what has been used
    sources.py  how trustworthy a source is (archives and governments first, blogs last)
    claims.py   claim records, linking claims to beats/scenes, checking a script against the evidence
    store.py    the per-topic cache: data/research_cache/<topic>/{research.md,sources.json,claims.json,metadata.json}
    engine.py   the orchestrator the script stage calls

Claude does the searching and reading (Claude Code's own WebSearch/WebFetch on your plan: no MCP server and no API key
needed). Everything else (limits, caching, source scoring, claim bookkeeping, deciding "is this enough?") is plain code.
"""
from .budget import Budget, ResearchBudgetReached, resolve_config, MODES            # noqa: F401
from .engine import research_topic, Research                                           # noqa: F401
