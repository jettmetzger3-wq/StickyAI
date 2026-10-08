"""Claims: one factual statement, the source that supports it, and the scenes that use it."""
import hashlib
import re

from . import sources as SRC

CONF = ("unverified", "low", "medium", "high")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
                "forty": 40, "fifty": 50, "hundred": 100}
STOP = set("the a an and or of in on at to for from with by as is was were be been it its this that these those he she they "
           "his her their them had has have not but so then than into over after before during about against between "
           "who which what when where why how also just very more most much many some any".split())
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2}|[1-9][0-9]{2})\b")
NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
# countries, continents and oceans everybody knows: not worth a fact-check call on their own (their years and numbers still are)
COMMON_NAMES = set("""england britain england france spain portugal germany italy russia china japan india egypt greece rome europe
america asia africa australia canada mexico atlantic pacific ocean""".split())
SPAN = re.compile(r"\b(\d+|" + "|".join(NUMBER_WORDS) + r")\s+(year|years|decade|decades|century|centuries)\s+(later|earlier|before|after|ago)\b", re.I)
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]{2,}(?:\s+(?:of\s+|the\s+)?[A-Z][a-z]{2,})*)")


def norm(text):
    return re.sub(r"[^a-z0-9 ]+", " ", str(text or "").lower()).strip()


def claim_id(text):
    return "c" + hashlib.md5(norm(text)[:120].encode()).hexdigest()[:8]


def keys(text):
    """The checkable bits of a sentence: years, numbers (digits or number words), proper names, and rarer words."""
    t = str(text or "")
    out = {"year": set(), "num": set(), "name": set(), "word": set()}
    for m in YEAR.finditer(t):
        out["year"].add(m.group(1))
    for m in NUMBER.finditer(t):
        v = m.group(0).replace(",", "")
        if v not in out["year"]:
            out["num"].add(v.rstrip("."))
    low = norm(t).split()
    for w in low:
        if w in NUMBER_WORDS:
            out["num"].add(str(NUMBER_WORDS[w]))
    for m in PROPER.finditer(t):
        nm = m.group(1).strip()
        if nm.lower() not in STOP:
            out["name"].add(nm.lower())
    for w in low:
        if len(w) >= 6 and w not in STOP:
            out["word"].add(w)
    return out


def confidence(raw_conf, url, organization=""):
    """The claim's confidence: what the researcher said, capped by how trustworthy the source is."""
    c = str(raw_conf or "medium").lower()
    c = c if c in CONF else "medium"
    if not url:
        return "unverified"
    q = SRC.quality(url, organization)
    cap = "high" if q["score"] >= 0.9 else "medium" if q["score"] >= 0.45 else "low"
    return CONF[min(CONF.index(c), CONF.index(cap))]


def make_claim(raw, sources_by_url=None):
    """A validated claim record from the researcher's raw dict, or None when there is no usable statement."""
    if not isinstance(raw, dict):
        return None
    text = re.sub(r"\s+", " ", str(raw.get("claim") or "")).strip()
    if len(text) < 12:
        return None
    url = str(raw.get("url") or "").strip()
    src = (sources_by_url or {}).get(url) or {}
    org = str(raw.get("organization") or src.get("organization") or "")
    q = SRC.quality(url, org) if url else dict(tier="none", score=0.0, host="")
    return dict(id=claim_id(text), claim=text[:400], source=str(raw.get("source") or src.get("title") or "")[:200], url=url,
                organization=org[:120], date=str(raw.get("date") or src.get("date") or "")[:40],
                evidence=re.sub(r"\s+", " ", str(raw.get("evidence") or "")).strip()[:400],
                confidence=confidence(raw.get("confidence"), url, org), tier=q["tier"], used_in_scenes=[])


def make_source(raw):
    if not isinstance(raw, dict) or not str(raw.get("url") or "").strip():
        return None
    url = str(raw["url"]).strip()
    q = SRC.quality(url, raw.get("organization") or "")
    return dict(url=url, title=str(raw.get("title") or "")[:200], organization=str(raw.get("organization") or "")[:120],
                date=str(raw.get("date") or "")[:40], tier=q["tier"], score=q["score"], host=q["host"], used=False)


def merge_claims(old, new):
    """Union by id; when both have it keep the better-supported one."""
    by = {c["id"]: c for c in old}
    for c in new:
        o = by.get(c["id"])
        if not o:
            by[c["id"]] = c
        elif CONF.index(c["confidence"]) > CONF.index(o["confidence"]):
            c["used_in_scenes"] = sorted(set(o.get("used_in_scenes") or []) | set(c.get("used_in_scenes") or []))
            by[c["id"]] = c
    return list(by.values())


def merge_sources(old, new):
    by = {s["url"]: s for s in old}
    for s in new:
        by.setdefault(s["url"], s)
    return list(by.values())


# ---------------------------------------------------------------- claims <-> the script
def _hits(beat_keys, claim_keys):
    strong = len(beat_keys["year"] & claim_keys["year"]) + len(beat_keys["num"] & claim_keys["num"]) \
        + len(beat_keys["name"] & claim_keys["name"])
    weak = len(beat_keys["word"] & claim_keys["word"])
    return strong, weak


def link_scenes(claims, beats):
    """Fill every claim's used_in_scenes (beat index = scene index) by what the narration really says: a claim is used
    by a beat when they share at least two checkable items (a year, a number, a name) or one of those plus rarer words.
    Claims the writer tagged on a beat (beat["claims"]) count too. Returns {beat index: [claim ids]}."""
    ck = {c["id"]: keys(c["claim"]) for c in claims}
    used = {}
    for c in claims:
        c["used_in_scenes"] = []
    for i, b in enumerate(beats):
        if b.get("host"):
            continue
        bk = keys(b.get("text"))
        hit = set(b.get("claims") or [])
        for c in claims:
            strong, weak = _hits(bk, ck[c["id"]])
            if strong >= 2 or (strong >= 1 and weak >= 2) or (weak >= 4 and strong == 0 and len(ck[c["id"]]["word"]) <= 8):
                hit.add(c["id"])
        for cid in hit:
            for c in claims:
                if c["id"] == cid and i not in c["used_in_scenes"]:
                    c["used_in_scenes"].append(i)
        used[i] = sorted(hit)
    return used


def corpus_keys(claims, brief):
    """Everything the research supports, as one set of checkable items."""
    allk = {"year": set(), "num": set(), "name": set(), "word": set()}
    texts = [c["claim"] + " " + c.get("evidence", "") for c in claims]
    b = brief or {}
    texts.append(str(b.get("summary") or ""))
    for p in b.get("people") or []:
        texts.append(" ".join(str(p.get(k) or "") for k in ("name", "role", "years")) if isinstance(p, dict) else str(p))
    for t in b.get("timeline") or []:
        texts.append(f"{t.get('year')} {t.get('event')}" if isinstance(t, dict) else str(t))
    for n in b.get("numbers") or []:
        texts.append(f"{n.get('claim')} {n.get('value')}" if isinstance(n, dict) else str(n))
    for d in b.get("documents") or []:
        texts.append(str(d.get("name") if isinstance(d, dict) else d))
    for p in b.get("places") or []:
        texts.append(" ".join(str(p.get(k) or "") for k in ("name", "note")) if isinstance(p, dict) else str(p))
    for t in texts:
        k = keys(t)
        for kk in allk:
            allk[kk] |= k[kk]
    return allk


def _spans_explained(text, years):
    """Numbers that are only a gap between two years the script itself states ("six years later" after 1781 and 1787)."""
    out = set()
    for m in SPAN.finditer(str(text or "")):
        n = m.group(1).lower()
        n = int(n) if n.isdigit() else NUMBER_WORDS.get(n)
        unit = {"y": 1, "d": 10, "c": 100}[m.group(2)[0].lower()]
        if n and any(abs(a - b) == n * unit for a in years for b in years):
            out.add(str(n))
    return out


def unsupported_items(beats, claims, brief):
    """The years, numbers and names in the script that NOTHING in the research mentions: these are the only things the
    fact-check call has to look at. Returns [{beat, kind, item}] (empty = the research covers everything checkable).
    Not counted: well-known country names, and "N years later" when the script's own years give that gap."""
    corpus = corpus_keys(claims, brief)
    years = {int(y) for b in beats if not b.get("host") for y in keys(b.get("text"))["year"]}
    out = []
    for i, b in enumerate(beats):
        if b.get("host"):
            continue
        k = keys(b.get("text"))
        k["num"] -= _spans_explained(b.get("text"), years)
        k["name"] -= COMMON_NAMES
        for kind in ("year", "num", "name"):
            for item in sorted(k[kind]):
                if item not in corpus[kind]:
                    out.append(dict(beat=i, kind=kind, item=item))
    return out


def prompt_lines(claims, limit=40):
    """The claims as compact lines for the script prompt, best-supported first."""
    ranked = sorted(claims, key=lambda c: (-CONF.index(c["confidence"]), c["id"]))[:limit]
    return "\n".join(f"[{c['id']}] {c['claim']}" + (f" ({SRC.host_of(c['url'])})" if c.get("url") else " (unsourced)")
                     for c in ranked)


def used_sources(claims, sources):
    """Only the sources that support a claim some scene actually uses, with the claims they back."""
    by = {s["url"]: dict(s, claims=[]) for s in sources}
    for c in claims:
        if c.get("used_in_scenes") and c.get("url"):
            s = by.setdefault(c["url"], dict(url=c["url"], title=c.get("source", ""), organization=c.get("organization", ""),
                                             date=c.get("date", ""), tier=c.get("tier", ""), claims=[]))
            s["claims"].append(c["id"])
    out = [s for s in by.values() if s["claims"]]
    out.sort(key=lambda s: (-float(s.get("score") or 0), s.get("title") or ""))
    return out
