"""Does the script flow? A free, local check of every pair of neighbouring beats.

A beat "connects" to the one before it when it picks something up from it (a shared name or word, a pronoun that
points back, a "so" / "but" / "meanwhile" opener, an answer to a question) and when it says so if a lot of time has
passed. Beats that connect to nothing are "seams": the viewer is dragged from one point to another. The script stage
asks the writer to smooth the worst ones (see PR.smooth_prompt); the Script tab shows what is left.
"""
import re

STOP = set("""a an and are as at be been being but by can could did do does for from had has have he her his how i if in is it its
just me more most my no not of on one or our out over said she so some than that the their them then there these they this
those to too up us was we were what when where which who why will with would you your into about after before again all also
any because both each even every few first got him how much new now off only other own same still such take through under until
very way well while""".split())
CONNECT = re.compile(
    r"^\W*(so|but|and|or|yet|still|then|now|here|there|this|that|these|those|it|its|they|their|them|he|his|him|she|her|"
    r"we|because|since|which|meanwhile|later|earlier|after|before|when|once|while|until|by then|by now|at the same|"
    r"in the end|finally|however|instead|of course|turns out|the result|as a result|that's|thats|why|how|what|who|"
    r"another|next|first|second|third|last|also|even|not|never|nobody|everyone|suddenly|soon|eventually|"
    r"for that|because of|despite|to understand|to see|to find|back|years|decades|months|weeks|days|one|two|three)\b",
    re.I)
TIME_BRIDGE = re.compile(
    r"\b(later|earlier|ago|years?|decades?|centuries|months?|weeks?|days?|meanwhile|by then|by now|next|following|"
    r"before|after|rewind|flash|back|same year|that year|the year|until|since|eventually|soon|finally|already|"
    r"previous|prior|once|forward|then|rewind|fast)\b", re.I)
YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2}|[5-9][0-9]{2}\s?(?:BC|AD|BCE|CE))\b")
NUM = re.compile(r"\d[\d,.]*")
JUMP_YEARS = 20


def _words(text):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'-]+|\d+", str(text or "")):
        lw = w.lower().strip("'-")
        if len(lw) >= 4 and lw not in STOP:
            out.append(lw[:5])
    return set(out)


def _years(text):
    ys = []
    for m in YEAR.finditer(str(text or "")):
        t = m.group(1)
        if t.isdigit():
            ys.append(int(t))
    return ys


def _pair(prev, cur):
    """Why `cur` doesn't connect to `prev`, or "" if it does."""
    if prev.rstrip().endswith("?"):
        return ""                                   # the question is answered next
    head = " ".join(cur.split()[:4])
    ya, yb = _years(prev), _years(cur)
    if ya and yb and abs(yb[0] - ya[-1]) >= JUMP_YEARS and not TIME_BRIDGE.search(" ".join(cur.split()[:14])):
        return f"jumps from {ya[-1]} to {yb[0]} without saying how much time passed"
    if CONNECT.match(cur) or CONNECT.match(head):
        return ""
    if _words(prev) & _words(cur):
        return ""
    if TIME_BRIDGE.search(" ".join(cur.split()[:10])):
        return ""
    return "doesn't pick up anything from the beat before it"


def seams(beats):
    """[(beat index, why)] for the beats that don't connect to the one before. The hook and the host's own beats
    are exempt (the hook is meant to stand alone, the host just talks to the viewer)."""
    out = []
    prev = None
    for i, b in enumerate(beats or []):
        if b.get("host") or b.get("part") == "hook" or i == 0:
            prev = None if b.get("host") else b.get("text")
            continue
        if prev is not None and b.get("text"):
            why = _pair(prev, b["text"])
            if why:
                out.append((i, why))
        prev = b.get("text")
    return out


def numbers(text):
    return {n.strip(".,") for n in NUM.findall(str(text or "")) if n.strip(".,")}


def keeps_facts(old, new):
    """A smoothed beat must keep every number and year the original had."""
    return numbers(old) <= numbers(new)


def apply_rewrites(beats, rewrites, wanted, clean=lambda t: t):
    """Put accepted rewrites into `beats` (only beats in `wanted`, only if no number was lost, 6 to 45 words).
    Returns the indices that changed."""
    done = []
    for rw in rewrites or []:
        if not isinstance(rw, dict):
            continue
        i, text = rw.get("beat"), clean(rw.get("text"))
        if not (isinstance(i, int) and i in wanted and 0 <= i < len(beats) and text):
            continue
        if beats[i].get("host") or text == beats[i]["text"] or not 6 <= len(text.split()) <= 45:
            continue
        if not keeps_facts(beats[i]["text"], text):
            continue
        beats[i]["text"] = text
        done.append(i)
    return done
