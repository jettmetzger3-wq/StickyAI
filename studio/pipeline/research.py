"""Topic research (deep mode only): ONE request per topic, cached for every later video on that topic.

The brief lists the people (with a one-line look and personality), places, documents (their real names and a few real
lines), numbers worth showing, and a short timeline. It feeds the script writer (so facts come from research, not
memory), the prop text on documents, and the character registry. If the same topic was researched before (for any
earlier video), the answer comes from data/cache/research/ and no AI is used.
"""
import re

from .. import cache as CA

SYSTEM = ("You research history topics for a stickman YouTube channel. You use reliable sources when you can search, say "
          "when something is debated, and never invent sources or quotes. You only answer with JSON.")


def topic_key(topic):
    return CA.key("brief", re.sub(r"\s+", " ", str(topic or "").lower().strip()))


def brief_prompt(topic, minutes):
    return f"""Research the topic "{topic}" for a {minutes:g}-minute funny-but-accurate stickman history video.

Return the facts the script and the animators will need, short and concrete:
- summary: 3 sentences on what happened and why it matters.
- people: the 6 to 10 most important people: name, role (max 8 words), years (e.g. "1732-1799"), look (their famous
  clothing, hair, beard or hat, max 10 words), trait (personality in max 6 words).
- places: 4 to 8 key places with a one-line note.
- documents: the important documents, laws, telegrams or newspapers: name, and 2 to 4 REAL short lines (at most 24
  characters each) that are actually written in it, or a headline for a newspaper.
- numbers: 5 to 8 striking numbers (casualties, money, sizes, dates) as {{"claim": "...", "value": "..."}}.
- timeline: 8 to 12 key events as {{"year": 1787, "event": "max 10 words"}}.
- visuals: 5 ideas for memorable pictures (a famous scene, object or moment), one line each.

Answer with JSON only: {{"summary": "...", "people": [{{"name","role","years","look","trait"}}], "places": [{{"name","note"}}],
"documents": [{{"name","lines":[...]}}], "numbers": [{{"claim","value"}}], "timeline": [{{"year","event"}}], "visuals": ["..."]}}"""


def get_brief(ctx, llm, topic, minutes, call):
    """The cached brief for `topic`, asking the AI only the first time. `call(llm, system, prompt, label, web)` is the
    stage's cached, ledger-recording request function. Returns (brief dict or None, was_cached)."""
    k = topic_key(topic)
    hit = CA.get("research", k)
    if hit:
        ctx.log(f"research: reused the saved brief on '{topic}' (no AI call)")
        return hit, True
    data = call(llm, SYSTEM, brief_prompt(topic, minutes), "research", bool(getattr(llm, "supports_web", False)))
    if not isinstance(data, dict) or not (data.get("people") or data.get("timeline")):
        return None, False
    CA.put("research", k, data, dict(topic=topic))
    return data, False


def notes_for_script(brief, limit=1800):
    """The brief as a compact block for the script prompt."""
    if not brief:
        return ""
    out = ["BACKGROUND RESEARCH (use these facts; they were checked):", str(brief.get("summary") or "")[:400]]
    if brief.get("people"):
        out.append("People: " + "; ".join(f"{p.get('name')} ({p.get('role')}, {p.get('years')}; {p.get('trait')})"
                                          for p in brief["people"][:9] if isinstance(p, dict)))
    if brief.get("timeline"):
        out.append("Timeline: " + "; ".join(f"{t.get('year')}: {t.get('event')}" for t in brief["timeline"][:12] if isinstance(t, dict)))
    if brief.get("numbers"):
        out.append("Numbers: " + "; ".join(f"{n.get('claim')} = {n.get('value')}" for n in brief["numbers"][:8] if isinstance(n, dict)))
    if brief.get("visuals"):
        out.append("Memorable pictures: " + "; ".join(str(v) for v in brief["visuals"][:5]))
    return "\n".join(x for x in out if x)[:limit]


def cast_from_brief(brief):
    """Cast entries (name, role, period, trait, look hints) for the people in the brief; looks are resolved by the
    character registry (people.json first, then the AI's own hat choice)."""
    from ..knowledge import people as PE
    out = []
    for p in (brief or {}).get("people") or []:
        if isinstance(p, dict) and p.get("name"):
            ent = dict(name=str(p["name"])[:40], role=str(p.get("role") or "")[:60], period=str(p.get("years") or ""),
                       trait=str(p.get("trait") or "")[:60])
            if not PE.find(p["name"]):          # someone people.json doesn't know: the researcher's words become the look
                ent.update(PE.look_from_text(p.get("look"), p.get("years")))
            out.append(ent)
    return out


def docs_from_brief(brief):
    """{lower-case document name: (TITLE, lines, prop)} so props_intel can write the real lines on real documents."""
    out = {}
    for d in (brief or {}).get("documents") or []:
        if isinstance(d, dict) and d.get("name"):
            lines = [str(x)[:28] for x in (d.get("lines") or []) if str(x).strip()][:4]
            if lines:
                nm = str(d["name"]).strip()
                prop = "newspaper" if re.search(r"newspaper|headline|times|herald|gazette", nm, re.I) else \
                    "scroll" if re.search(r"treaty|declaration|edict|proclamation|charter|pact", nm, re.I) else "document"
                out[nm.lower()] = (nm.upper()[:34], lines, prop)
    return out
