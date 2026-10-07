"""Beat analysis, done locally with no AI: what is this line of narration ABOUT?

analyze(text, mood, cast, seen) -> dict with
  people     [{name, id, known, role}]   known historical people, cast members and titled names ("General Howe")
  intro      names that appear for the first time in the video (so the scene can introduce them)
  groups     nations/armies mentioned (from the cast and the country list)
  places     [{name, kind}] named countries and cities; place_type: the painted-place background this suggests
  documents  [{kind, name}]              treaties, laws, telegrams, newspapers...
  numbers    [{value, shown, unit, kind}] money, casualties, counts, percentages (not years)
  years      [int]
  verbs      the action words (signed, marched, declared, ...)
  emotion    triumph | tragedy | tension | shock | humor | neutral
  events     event tags used by the pattern retriever (war_declaration, treaty, election, ...)
"""
import re

from ..engine.reactions import triggers
from . import people as PE, gazetteer as GZ

MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")
NOT_NAMES = set(MONTHS) | {"the", "a", "an", "but", "and", "so", "then", "when", "after", "before", "while", "meanwhile",
                           "today", "suddenly", "finally", "now", "in", "on", "at", "by", "it", "he", "she", "they",
                           "we", "this", "that", "these", "those", "his", "her", "their", "monday", "tuesday",
                           "wednesday", "thursday", "friday", "saturday", "sunday", "god", "english", "french",
                           "german", "british", "american", "russian", "soviet", "chinese", "japanese", "european",
                           "congress", "parliament", "senate", "army", "navy", "war", "world", "cold", "civil"}
TITLES = ("general", "king", "queen", "president", "admiral", "emperor", "tsar", "lord", "duke", "sir", "pope",
          "colonel", "captain", "prince", "princess", "chancellor", "premier", "senator", "governor", "marshal",
          "commander", "sultan", "pharaoh", "doctor", "dr.", "lady", "count", "baron", "bishop", "prime minister")
DOC_KINDS = [  # (kind, regex for the word)
    ("treaty", r"treaty|armistice|peace accords?|accords?|truce|pact|agreement|settlement|capitulation"),
    ("declaration", r"declaration|manifesto|proclamation|ultimatum"),
    ("law", r"\bacts?\b|\blaws?\b|\bbills?\b|amendment|constitution|charter|statute|legislation|decree|edict|compromise|doctrine"),
    ("telegram", r"telegram|telegraph message|wire\b"),
    ("letter", r"\bletters?\b|\bnote\b|message|memo\b|orders?\b"),
    ("newspaper", r"newspapers?|headlines?|front page|press\b|the times\b"),
    ("contract", r"contract|deal\b|deed|patent|ledger|receipt|bond\b"),
    ("map_doc", r"\bmap\b|blueprint|plans?\b"),
]
NAMED_DOC = re.compile(
    r"\b((?:The )?(?:Treaty|Declaration|Act|Edict|Proclamation|Compromise|Peace|Pact|Convention|Charter|Doctrine|Accords?|"
    r"Armistice|Statute) of [A-Z][a-z]+(?: [A-Z][a-z]+)?|(?:[A-Z][a-z]+ ){1,2}(?:Treaty|Act|Pact|Proclamation|Declaration|"
    r"Accords?|Doctrine|Manifesto|Edict|Telegram|Amendment|Agreement|Compromise|Charter|Constitution)|"
    r"(?:The )?(?:Constitution|Bill of Rights|Magna Carta|Declaration of Independence|Emancipation Proclamation|"
    r"Communist Manifesto|Monroe Doctrine|Truman Doctrine))\b")
MONEY = {"$": "dollars", "£": "pounds", "€": "euros"}
NUM = re.compile(r"(?P<cur>[$£€])?\s?(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?P<scale>million|billion|thousand|percent|%)?"
                 r"(?:\s+(?P<unit>[a-z]+))?", re.I)
UNITS = {"men": "count", "soldiers": "casualty", "troops": "count", "people": "count", "dead": "casualty",
         "killed": "casualty", "died": "casualty", "ships": "count", "tanks": "count", "planes": "count",
         "dollars": "money", "pounds": "money", "francs": "money", "gold": "money", "coins": "money",
         "workers": "count", "prisoners": "count", "refugees": "count", "casualties": "casualty", "civilians": "casualty",
         "deaths": "casualty", "votes": "count", "colonies": "count", "states": "count", "miles": "distance",
         "kilometers": "distance", "years": "time", "days": "time", "months": "time", "weeks": "time"}

PLACE_RULES = [  # (regex, background type) - first match wins, ordered most specific first
    (r"courtroom|\btrial\b|\bjudge\b|\bjury\b|on trial", "courtroom"),
    (r"\bprison\b|\bjail\b|dungeon|imprisoned|locked up|prison cell", "prison"),
    (r"\bparliament\b|house of commons|senate|\bcongress\b|constitutional convention|assembly|chamber|legislature|"
     r"\bvoted\b|\bvote\b", "parliament"),
    (r"\bpalace\b|throne|royal court|versailles|\bcourt of\b|the king'?s|the queen'?s|\bcoronation\b|\bballroom\b", "palace"),
    (r"trenches?|no man'?s land|western front|over the top", "trench"),
    (r"battle|battlefield|\bsiege\b|charged|\bcharge\b|artillery|cannon|musket|\bfought\b|clash|\bwar zone\b|"
     r"bombard", "battlefield"),
    (r"harbou?r|\bport\b|\bdocks?\b|\bships?\b|\bfleet\b|\bnavy\b|\bsailed\b|voyage|\bat sea\b|armada|\bgalleon", "harbor"),
    (r"\bocean\b|underwater|submarine|\bu-?boats?\b", "underwater"),
    (r"\bdesert\b|sahara|\bsands?\b|oasis", "desert"),
    (r"\bmountains?\b|\balps\b|himalaya|\bpass\b|andes", "mountains"),
    (r"\bsnow\b|\bwinter\b|siberia|blizzard|frozen|\bice\b", "snow"),
    (r"\bjungle\b|rainforest|amazon", "jungle"),
    (r"\bfarms?\b|\bpeasants?\b|\bharvest\b|\bcrops?\b|wheat|\bvillage\b|countryside", "field"),
    (r"\bstreets?\b|\bmob\b|\briots?\b|\bprotest|\bcrowds? gathered|\bsquare\b|\bmarket\b", "street"),
    (r"\bcity\b|\bcapital\b|skyline|metropolis|downtown", "city"),
    (r"\boffice\b|\bmeeting\b|\bboardroom\b|\bdesk\b|\bsecret room\b|\bbunker\b|\bcabinet\b|white house|kremlin",
     "interior"),
    (r"\bspace\b|\borbit|\bmoon\b|sputnik|\brocket\b", "space"),
]
VERBS = ("signed", "sign", "declared", "declares", "marched", "march", "invaded", "invade", "attacked", "attack",
         "voted", "elected", "died", "killed", "executed", "born", "founded", "built", "invented", "discovered",
         "sailed", "crossed", "fled", "surrendered", "negotiated", "passed", "banned", "arrested", "burned",
         "stormed", "won", "lost", "fought", "ruled", "crowned", "resigned", "promised", "demanded", "refused",
         "bombed", "landed", "escaped", "captured", "conquered", "united", "split", "collapsed", "crashed",
         "protested", "rioted", "traded", "bought", "sold", "taxed", "revolted", "spied", "plotted", "met",
         "argued", "joked", "gave", "spoke", "announced", "ordered", "ended", "began", "started")
EVENT_WORDS = {
    "war_declaration": r"declared war|declares war|declare war|\bultimatum|war on\b|mobili[sz]ed|ordered the invasion|invaded",
    "treaty": r"treaty|armistice|peace deal|peace accord|ceasefire|cease-fire|truce|surrender|capitulat|peace conference",
    "election": r"\belection|\belected\b|\bballots?\b|\bvoters?\b|landslide|\bcampaign\b|polls\b|won the presidency|\bvotes? for",
    "law": r"\bpassed (?:a|the)? ?\w* ?(?:law|act|bill)|\blaws?\b|\bact\b|\bbill\b|amendment|legislat|\bcongress\b|\bparliament\b|\bsenate\b|constitution|convention|\bcharter\b",
    "signing": r"\bsigned\b|\bsigns\b|signing|signature|ratif",
    "speech": r"\bspeech\b|\bspoke to\b|\baddress(?:ed)?\b|told the crowd|\brally\b|\bbroadcast\b|\bpodium\b|\bannounced\b",
    "battle": r"\bbattle\b|\bfought\b|\bcharged\b|\bsiege\b|\bclash|\battacked\b|\bbombed\b|\bstormed\b|\bartillery\b|\bshelled\b",
    "movement": r"\bmarched\b|\bsailed\b|\bcrossed\b|\badvanced\b|\bretreated\b|\bfled\b|\btraveled\b|\bvoyage\b|\bexpedition\b|\bjourney\b",
    "protest": r"\bprotest|\bdemonstrat|\bstrike\b|\bboycott|\bpetition|\bdemanded\b|\bmarch on\b",
    "riot": r"\briot|\bmob\b|\buprising\b|\brevolt\b|\brebellion\b|\brevolution\b|\blooted\b|\bstormed the\b|\bburned (?:down|the)\b",
    "death": r"\bdied\b|\bdeath of\b|\bassassinat|\bkilled\b|\bexecuted\b|\bfuneral\b|\bburied\b|\bpassed away\b|\bmurdered\b|\bpoisoned\b|\bbeheaded\b|\bwas shot\b|\bshot dead\b|\bdrowned\b",
    "crisis": r"\bcrash|\bdepression\b|\binflation\b|\bbankrupt|\bdebt\b|\brecession\b|\bcollapsed\b|\bfamine\b|\bunemploy|\btax(?:es)?\b|\btariffs?\b|\bbroke\b|\bpoverty",
    "invention": r"\binvent|\bpatent|\bdiscover|\bbreakthrough|\bfirst ever\b|\bbuilt the first\b|\bnew machine\b",
    "technology": r"\bmachine\b|\bengine\b|\bsteam\b|\bfactory\b|\bassembly line\b|\btelegraph\b|\brailroad\b|\bmill\b|\bcannon works\b|\btechnology\b",
    "migration": r"\bmigrat|\bimmigra|\bsettlers?\b|\brefugees?\b|\bemigrat|\bexodus\b|\bcolonists?\b|\bfled to\b|\bmoved to\b|\bsailed to\b|\bleft for\b|\bleft their homes?\b",
    "social": r"\brights\b|\bequality\b|\bfreedom\b|\babolish|\bsegregat|\bslavery\b|\bwomen'?s\b|\bsuffrage\b|\breform|\bcivil rights\b|\bliberat",
    "plot": r"\bspy\b|\bspies\b|\bsecret\b|\bplot\b|\bconspir|\bcoup\b|\bsabotag|\bintelligence\b|\bassassination plan",
    "debate": r"\bdebate|\bargued\b|\bdisagreed\b|\bopposed\b|\bfaction|\brivals?\b|\bparties\b|\bclashed over\b",
    "celebration": r"\bcelebrat|\bparade\b|\bvictory\b|\btriumph|\bcheered\b|\bwon\b|\bfestival\b",
    "disaster": r"\bearthquake|\bflood|\bplague\b|\bepidemic\b|\bsank\b|\bcrashed\b|\bexploded\b|\bfire\b|\bdisaster\b|\beruption",
    "intro_person": r"\bwas born\b|\ba man named\b|\bknown as\b|\bbecame\b|\brose to power\b|\bnew leader\b|\btook over\b|\btook power\b",
    "city": r"\bin (?:the city of )?[A-Z][a-z]+,? (?:the capital|a city|a port)|\bcapital\b|\bthe city of\b",
    "country": r"\bthe (?:country|nation|kingdom|republic|empire) of\b|\bat the time\b|\bback then\b",
    "cause": r"\bbecause\b|\bcaused\b|\bled to\b|\bas a result\b|\bwhich meant\b|\btherefore\b|\bconsequence|\btriggered\b|\bsparked\b|\bresulted\b|\bthat's why\b|\bso now\b",
    "change": r"\bbefore\b.*\bafter\b|\bused to\b|\bno longer\b|\bchanged\b|\btransformed\b|\bnow\b.*\bthen\b|\bcompared to\b|\btoday\b",
    "dialogue": r"\bsaid\b|\btold\b|\basked\b|\breplied\b|\bwhispered\b|\bshouted\b|\bargued with\b",
}
_EVENT_RX = {k: re.compile(v, re.I) for k, v in EVENT_WORDS.items()}
_PLACE_RX = [(re.compile(rx, re.I), bg) for rx, bg in PLACE_RULES]


def years_in(text):
    out = []
    for m in re.finditer(r"\b(1\d{3}|20\d{2})\b|\b(\d{1,4})\s?(BC|BCE|AD|CE)\b", str(text or "")):
        if m.group(1):
            out.append(int(m.group(1)))
        else:
            n = int(m.group(2))
            out.append(-n if m.group(3) in ("BC", "BCE") else n)
    return out


def numbers_in(text):
    """Quantities worth showing: money, casualties, counts, percentages. Years and tiny numbers are skipped."""
    out = []
    for m in NUM.finditer(str(text or "")):
        raw = m.group("num")
        try:
            v = float(raw.replace(",", ""))
        except ValueError:
            continue
        scale = (m.group("scale") or "").lower()
        unit = (m.group("unit") or "").lower()
        if scale in ("percent", "%") or unit == "percent":
            out.append(dict(value=v, shown=f"{raw}%", unit="percent", kind="percent", text=m.group(0).strip()))
            continue
        if not scale and 1000 <= v <= 2100 and "," not in raw and unit not in UNITS:
            continue                                            # a year
        v *= {"thousand": 1e3, "million": 1e6, "billion": 1e9}.get(scale, 1)
        cur = m.group("cur")
        kind = "money" if cur else UNITS.get(unit, "")
        if not kind and v < 100:
            continue
        if kind in ("time", "distance") or v < 20:
            continue
        unit_txt = MONEY.get(cur or "", unit)
        if v >= 1e9:
            shown = f"{v / 1e9:g} billion"
        elif v >= 1e6:
            shown = f"{v / 1e6:g} million"
        else:
            shown = f"{int(v):,}"
        out.append(dict(value=v, shown=(cur or "") + shown, unit=unit_txt, kind=kind or "count", text=m.group(0).strip()))
    return out


def documents_in(text):
    """Named and unnamed documents. Named: 'Treaty of Versailles', 'the Stamp Act'. Unnamed: kind only."""
    out, seen = [], set()
    for m in NAMED_DOC.finditer(str(text or "")):
        name = m.group(1).strip()
        if name.lower().startswith("the "):
            name = name[4:]
        kind = "law"
        for k, rx in DOC_KINDS:
            if re.search(rx, name, re.I):
                kind = k
                break
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append(dict(kind=kind, name=name))
    low = str(text or "").lower()
    if not out:
        for k, rx in DOC_KINDS:
            m = re.search(rx, low)
            if m:
                out.append(dict(kind=k, name=""))
                break
    return out


def place_type(text):
    from ..engine.schema import activity_place
    low = str(text or "")
    work = activity_place(low)                                    # a factory going up, a mine, a classroom...
    if work:
        return work.get("type") if isinstance(work, dict) else str(work)
    for rx, bg in _PLACE_RX:
        if rx.search(low):
            return bg
    return ""


REGIONY = {"europe", "asia", "africa", "america", "americas", "east", "west", "north", "south", "middle", "pacific", "atlantic",
           "ocean", "sea", "union", "states", "empire", "republic", "kingdom", "party", "army", "navy", "council", "nations",
           "treaty", "war", "front", "wall", "plan", "doctrine", "crisis", "race", "bloc", "pact"}


def _titled_names(text):
    """'General Howe', 'Lord Cornwallis', and capitalised pairs in the middle of a sentence ('Benedict Arnold')."""
    out = []
    for m in re.finditer(r"\b(" + "|".join(t.title() for t in TITLES) + r")\.? ((?:[A-Z][a-z]+)(?: [A-Z][a-z]+)?)", text):
        out.append(m.group(2).split()[-1] if m.group(2).lower().split()[0] in NOT_NAMES else m.group(0))
    for m in re.finditer(r"(?<=[a-z,;] )([A-Z][a-z]+ [A-Z][a-z]+)\b", text):
        w1, w2 = m.group(1).lower().split()
        if w1 not in NOT_NAMES and w2 not in NOT_NAMES and not PE.find(m.group(1)) and not GZ.find(m.group(1)) \
                and w1 not in REGIONY and w2 not in REGIONY:
            out.append(m.group(1))
    return out


def _cast_hits(text, cast):
    low = " " + str(text or "").lower() + " "
    hits = []
    for c in cast or []:
        n = str(c.get("name") or "").strip()
        if not n:
            continue
        parts = [p for p in re.split(r"\s+", n.lower()) if len(p) >= 4 and p not in NOT_NAMES]
        keys = [n.lower()] + parts
        for k in keys:
            m = re.search(r"\b" + re.escape(k) + r"s?\b", low)
            if m:
                hits.append((m.start(), c))
                break
    hits.sort(key=lambda h: h[0])
    return [c for _, c in hits]


def emotion_of(text, mood="fun"):
    exprs = [e for _, e in triggers(str(text or "").split())]
    if mood == "somber" or any(e == "sad" for e in exprs):
        return "tragedy"
    if any(e in ("smug", "happy") for e in exprs):
        return "triumph"
    if any(e in ("angry", "scared") for e in exprs) or mood == "tense":
        return "tension"
    if any(e == "surprise" for e in exprs):
        return "shock"
    if any(e in ("laugh", "confused") for e in exprs):
        return "humor"
    return "neutral"


def analyze(text, mood="fun", cast=None, seen=None):
    """Everything the pattern retriever and the composer need to know about one beat. `seen` = names already
    introduced earlier in the video (a set the caller updates with result["intro"])."""
    from ..pipeline.rules import countries_in
    text = str(text or "")
    seen = seen if seen is not None else set()
    yrs = years_in(text)
    year = yrs[0] if yrs else None
    people, ids = [], set()
    for c in _cast_hits(text, cast):
        e = PE.find(c.get("name"), year)
        pid = (e or {}).get("id") or "cast:" + str(c.get("name")).lower()
        if pid not in ids:
            ids.add(pid)
            people.append(dict(name=c.get("name"), id=pid, known=bool(e), role=c.get("role") or (e or {}).get("role", ""),
                               cast=True, kind=c.get("kind")))
    for e, shown in PE.find_in_text(text, year):
        if e["id"] not in ids and ("cast:" + e["name"].lower()) not in ids:
            ids.add(e["id"])
            people.append(dict(name=e["name"], id=e["id"], known=True, role=e["role"], cast=False, kind=e["kind"]))
    for n in _titled_names(text):
        k = "cast:" + n.lower()
        if k not in ids and not any(n.lower() in (p["name"] or "").lower() for p in people):
            ids.add(k)
            people.append(dict(name=n, id=k, known=False, role="", cast=False, kind="civ"))
    intro = [p["name"] for p in people if p["id"] not in seen]
    for p in people:
        seen.add(p["id"])
    countries = countries_in(text)
    cities = GZ.find_in_text(text)
    places = [dict(name=c["name"], kind="city", lon=c["lon"], lat=c["lat"], country=c["country"], skyline=c["skyline"])
              for c in cities] + [dict(name=n, kind="country") for n, _ in countries]
    groups = [c.get("name") for c in cast or [] if c.get("kind") not in (None, "", "civ")
              and re.search(r"\b" + re.escape(str(c.get("name")).lower()) + r"\b", text.lower()) and not any(
                  p["name"] == c.get("name") for p in people)]
    events = [k for k, rx in _EVENT_RX.items() if rx.search(text)]
    opening = " ".join(text.split()[:7])
    if cities and re.search(r"\b(?:in|at|near|outside|inside|from)\b", opening, re.I) and any(c["shown"].lower() in opening.lower() for c in cities):
        events.append("city")                                 # "In Paris, in 1789, ..." sets the scene in a city
    elif countries and re.match(r"\s*(?:in|by|across|throughout)\b", opening, re.I):
        events.append("country")
    verbs = [v for v in VERBS if re.search(r"\b" + v + r"\b", text.lower())]
    return dict(people=people, intro=intro, groups=groups, places=places, place_type=place_type(text),
                documents=documents_in(text), numbers=numbers_in(text), years=yrs, verbs=verbs,
                emotion=emotion_of(text, mood), events=events, mood=mood, text=text)
