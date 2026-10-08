"""The per-topic research cache: data/research_cache/<topic>/{research.md, sources.json, claims.json, metadata.json}.

(`research/` at the top of the repository is the hand-written visual library that is committed; the topic caches are your
own data, so they live next to the other caches in data/.)  brief.json next to them is the structured brief (people,
places, documents, numbers, timeline, visual ideas) the script, character and prop code read.
"""
import json
import os
import re
import time

from .. import config
from . import claims as CL

LEAD_WORDS = {"the", "a", "an", "of", "history", "video", "story", "about", "in", "and", "on", "to"}


def root():
    return os.path.join(config.DATA_DIR, "research_cache")


def tokens(topic):
    return [w for w in re.sub(r"[^a-z0-9 ]+", " ", str(topic or "").lower()).split() if w not in LEAD_WORDS]


def slug(topic):
    return "-".join(tokens(topic))[:60] or "topic"


def find(topic):
    """(slug of the cached topic to reuse, extra words of this topic the cache doesn't mention) or (None, tokens).
    'The American Revolution' and 'the causes of the American Revolution' share one cache; 'causes' becomes the focus."""
    mine = set(tokens(topic))
    exact = slug(topic)
    if os.path.isdir(os.path.join(root(), exact)):
        return exact, []
    best, best_n = None, 0
    if os.path.isdir(root()):
        for d in os.listdir(root()):
            theirs = set(d.split("-"))
            if len(theirs) >= 2 and (theirs <= mine or mine <= theirs) and len(theirs & mine) >= 2 and len(theirs & mine) > best_n:
                best, best_n = d, len(theirs & mine)
    if best:
        return best, sorted(mine - set(best.split("-")))
    return None, sorted(mine)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load(slug_):
    d = os.path.join(root(), slug_)
    if not os.path.isdir(d):
        return None
    return dict(slug=slug_, brief=_read(os.path.join(d, "brief.json"), {}), claims=_read(os.path.join(d, "claims.json"), []),
                sources=_read(os.path.join(d, "sources.json"), []), metadata=_read(os.path.join(d, "metadata.json"), {}))


def save(slug_, topic, brief, claims, sources, metadata):
    d = os.path.join(root(), slug_)
    os.makedirs(d, exist_ok=True)
    meta = dict(metadata or {})
    meta.update(topic=meta.get("topic") or topic, updated=time.time(), claims=len(claims), sources=len(sources))
    meta.setdefault("created", time.time())
    for name, data in (("brief.json", brief), ("claims.json", claims), ("sources.json", sources), ("metadata.json", meta)):
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
    with open(os.path.join(d, "research.md"), "w", encoding="utf-8") as f:
        f.write(markdown(topic, brief, claims, sources, meta))
    return d


def merge_brief(old, new):
    out = dict(old or {})
    for k in ("summary",):
        if new.get(k) and not out.get(k):
            out[k] = new[k]
    keyfn = dict(people=lambda x: str(x.get("name", "")).lower(), places=lambda x: str(x.get("name", "")).lower(),
                 documents=lambda x: str(x.get("name", "")).lower(), numbers=lambda x: str(x.get("claim", "")).lower()[:40],
                 timeline=lambda x: f"{x.get('year')}:{str(x.get('event', '')).lower()[:24]}")
    for k, fn in keyfn.items():
        seen = {fn(x) for x in out.get(k) or [] if isinstance(x, dict)}
        out[k] = list(out.get(k) or []) + [x for x in new.get(k) or [] if isinstance(x, dict) and fn(x) not in seen]
    vis = list(out.get("visuals") or [])
    out["visuals"] = vis + [v for v in new.get("visuals") or [] if v not in vis]
    return out


def markdown(topic, brief, claims, sources, meta):
    b = brief or {}
    L = [f"# Research: {topic}", "", f"_{len(claims)} claims, {len(sources)} sources; researched in {meta.get('mode', '?')} mode._", ""]
    if b.get("summary"):
        L += ["## Summary", b["summary"], ""]
    if b.get("timeline"):
        L += ["## Timeline"] + [f"- **{t.get('year')}** {t.get('event')}" for t in b["timeline"] if isinstance(t, dict)] + [""]
    if b.get("people"):
        L += ["## People"] + [f"- **{p.get('name')}** ({p.get('years', '')}): {p.get('role', '')}" for p in b["people"] if isinstance(p, dict)] + [""]
    if b.get("documents"):
        L += ["## Documents"] + [f"- {d.get('name')}" for d in b["documents"] if isinstance(d, dict)] + [""]
    L += ["## Claims and their evidence"]
    for c in sorted(claims, key=lambda c: (-CL.CONF.index(c["confidence"]), c["id"])):
        L.append(f"- `{c['id']}` [{c['confidence']}] {c['claim']}" + (f" ([{c.get('source') or c['url']}]({c['url']}))" if c.get("url") else " (no source)"))
        if c.get("evidence"):
            L.append(f"    - evidence: {c['evidence']}")
    L += ["", "## Sources"] + [f"- [{s.get('title') or s['url']}]({s['url']}) ({s.get('organization', '')}; {s.get('tier')})" for s in sources]
    if meta.get("gaps"):
        L += ["", "## Known gaps"] + [f"- {g}" for g in meta["gaps"]]
    return "\n".join(L) + "\n"
