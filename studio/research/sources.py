"""How much to trust a source: a local lookup by who published it, never a guess about the content."""
import re
from urllib.parse import urlparse

# (tier, score, pattern on the host). First match wins. Scores: 1.0 primary/official ... 0.1 avoid.
TIERS = [
    ("archive", 1.0, r"(^|\.)(archives\.gov|loc\.gov|nationalarchives\.gov\.uk|archive\.org/details|founders\.archives\.gov|avalon\.law\.yale\.edu|constitutioncenter\.org|masshist\.org|monticello\.org|mountvernon\.org)$"),
    ("government", 0.95, r"(^|\.)(gov|gov\.uk|mil|gc\.ca|gouv\.fr|europa\.eu|un\.org)$"),
    ("museum", 0.95, r"(^|\.)(si\.edu|smithsonianmag\.com|britishmuseum\.org|metmuseum\.org|nps\.gov|colonialwilliamsburg\.org|history\.org|rmg\.co\.uk|nationalgeographic\.org)$"),
    ("academic", 0.9, r"(^|\.)(edu|ac\.uk|edu\.au|ac\.jp|ac\.nz)$"),
    ("academic", 0.9, r"(^|\.)(jstor\.org|oup\.com|cambridge\.org|academic\.oup\.com|history\.ac\.uk|historians\.org|ushistory\.org|nationalww2museum\.org)$"),
    ("encyclopedia", 0.7, r"(^|\.)(britannica\.com|encyclopedia\.com|worldhistory\.org|newworldencyclopedia\.org)$"),
    ("reputable_org", 0.65, r"(^|\.)(history\.com|bbc\.co\.uk|bbc\.com|pbs\.org|npr\.org|nytimes\.com|economist\.com|smithsonianmag\.com|thoughtco\.com)$"),
    ("tertiary", 0.45, r"(^|\.)(wikipedia\.org|wikimedia\.org|wikisource\.org)$"),
    ("avoid", 0.1, r"(^|\.)(blogspot\.com|wordpress\.com|medium\.com|quora\.com|reddit\.com|pinterest\.com|tumblr\.com|substack\.com|answers\.com|ehow\.com|fandom\.com|brainyquote\.com|goodreads\.com)$"),
]
TIERS = [(t, s, re.compile(p, re.I)) for t, s, p in TIERS]
PRIMARY = ("archive", "government", "museum", "academic")


def host_of(url):
    try:
        return (urlparse(str(url)).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def quality(url, organization=""):
    """{tier, score, host}: how much to trust a source by its publisher."""
    host = host_of(url)
    full = (host + urlparse(str(url)).path.lower()) if host else ""
    for tier, score, rx in TIERS:
        if rx.search(host) or (tier == "archive" and rx.search(full)):
            return dict(tier=tier, score=score, host=host)
    if not host:
        return dict(tier="none", score=0.0, host="")
    if re.search(r"(museum|library|archive|university|college|historical.?society|foundation)", host + " " + str(organization or "").lower()):
        return dict(tier="reputable_org", score=0.6, host=host)
    return dict(tier="other", score=0.35, host=host)


def is_primary(url, organization=""):
    return quality(url, organization)["tier"] in PRIMARY


def best_score(urls):
    return max([quality(u)["score"] for u in urls] or [0.0])
