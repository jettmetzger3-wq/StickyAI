"""Faces that react to the words: characters look shocked on "suddenly", furious on "betrayed", smug on "won",
crushed on "lost", right as the narrator says the word.

Who reacts: the character the clause is about (its cast name, e.g. "Napoleon", or its side, e.g. "the French"),
otherwise everyone for shock, fear and joy, or the scene's main character for the rest. A character's own
"do" actions always win: no reaction is added on top of one, and each character reacts at most twice per scene.
"""
import re

from .pen import KIND_ALIASES, resolve_kind
from .timing import norm_word

# expression -> words (a trailing * matches any ending: "betray*" = betrayed, betrayal, betrays...)
WORDS = {
    "surprise": ("suddenly", "sudden", "surprise*", "shock*", "unexpected*", "astonish*", "stunned", "whoa",
                 "boom", "twist", "amazed", "amazing", "incredibl*", "unbelievabl*"),
    "angry": ("betray*", "traitor*", "furious", "fury", "angry", "anger*", "outrag*", "insult*", "humiliat*",
              "enraged", "rage", "backstab*", "infuriat*", "livid", "seething", "revenge"),
    "smug": ("won", "win", "wins", "winning", "victory", "victorious", "triumph*", "conquer*", "outsmart*",
             "outwit*", "genius", "brilliant*", "easily", "flawless*", "crushed", "humbled"),
    "sad": ("lost", "loses", "losing", "defeat*", "died", "dies", "death", "killed", "failed", "fails", "failure",
            "disaster*", "ruined", "ruin", "bankrupt*", "tragic*", "tragedy", "starv*", "mourn*", "heartbroken",
            "exiled", "abandoned", "doomed"),
    "scared": ("terrified", "terrifying", "scared", "afraid", "fear*", "panic*", "horror", "horrified",
               "nightmare", "dread*", "trembl*", "frighten*"),
    "happy": ("celebrat*", "rejoic*", "cheered", "hooray", "delighted", "thrilled", "overjoyed", "finally",
              "relieved", "proud"),
    "laugh": ("laughed", "laughing", "laugh", "laughs", "joke*", "hilarious", "ridiculous", "absurd", "mocked",
              "mocking", "ridicul*"),
    "confused": ("confus*", "puzzl*", "baffl*", "bewilder*", "mystery", "mysterious", "strange", "weird",
                 "nobody knew", "no idea", "no clue"),
}
EVERYONE = ("surprise", "scared", "happy")          # with no clear subject, the whole scene reacts to these
SOMBER_OK = ("sad", "scared")
FACE_ACTS = {"surprise", "angry", "cry", "laugh", "celebrate", "cheer", "tremble", "faint", "facepalm", "slash",
             "fight", "think", "shrug", "talk", "react", "dance"}
REACT_DUR = 1.5
MAX_PER_CHAR = 2
CLAUSE_END = re.compile(r"[.,;:!?—]$|--$")
CLAUSE_WORDS = {"but", "while", "whereas", "although", "though", "meanwhile", "yet"}
NEGATIONS = {"not", "never", "no", "nobody", "hardly", "didn't", "wasn't", "weren't", "couldn't", "wouldn't",
             "didnt", "wasnt", "werent", "couldnt", "wouldnt", "without"}


def _matches(key, pattern):
    if pattern.endswith("*"):
        return key.startswith(pattern[:-1]) and len(key) >= len(pattern) - 1
    return key == pattern


def triggers(words):
    """[(word index, expression)] for the narration's trigger words (multi-word phrases included)."""
    keys = [norm_word(w) for w in words]
    out = []
    for i, key in enumerate(keys):
        if not key:
            continue
        for expr, pats in WORDS.items():
            hit = False
            for pat in pats:
                parts = pat.split()
                if len(parts) > 1:
                    if keys[i:i + len(parts)] == parts:
                        hit = True
                elif _matches(key, pat):
                    hit = True
                if hit:
                    break
            if hit:
                prev = keys[max(0, i - 2):i]
                if any(p in NEGATIONS for p in prev):
                    break                       # "never lost", "not surprised": no reaction
                out.append((i, expr))
                break
    return out


def _names(el, cast_kinds):
    """Words in the narration that point at this character: its cast name and its side (the French...)."""
    names = set()
    who = str(el.get("who") or "")
    for part in re.split(r"[\s_-]+", who.lower()):
        part = norm_word(part)
        if len(part) >= 3 and part not in ("the", "of", "and", "von", "van", "der", "de", "la", "le"):
            names.add(part)
    kind = resolve_kind(el.get("kind"))
    if kind not in ("civ",):
        for alias, k in KIND_ALIASES.items():
            if k == kind and alias and "_" not in alias and alias not in ("king", "queen", "plain", "person"):
                names.add(alias)
        names.add(kind)
    return names


def _clause_bounds(words, i):
    a = i
    while a > 0 and not CLAUSE_END.search(words[a - 1]) and norm_word(words[a]) not in CLAUSE_WORDS:
        a -= 1
    b = i
    while b < len(words) - 1 and not CLAUSE_END.search(words[b]) and norm_word(words[b + 1]) not in CLAUSE_WORDS:
        b += 1
    return a, b


def plan(scene, timer, mood="fun"):
    """{element index: [(t0 seconds, expression)]} for the scene's characters and crowds."""
    if scene.get("react") is False:
        return {}
    els = scene.get("elements") or []
    people = [(k, el) for k, el in enumerate(els) if isinstance(el, dict) and el.get("type") in ("char", "crowd")
              and el.get("react", True) is not False]
    if not people:
        return {}
    words = timer.words
    keys = [norm_word(w) for w in words]
    names = {k: _names(el, None) for k, el in people}
    chars = [(k, el) for k, el in people if el.get("type") == "char"]
    main = max(chars, key=lambda kv: (float(kv[1].get("scale") or 1.0), -kv[0]))[0] if chars else None
    out = {}
    found = []
    for i, expr in triggers(words):
        if mood == "somber" and expr not in SOMBER_OK:
            continue
        t0 = timer.starts[i] - 0.05
        a, b = _clause_bounds(words, i)
        subject = None
        best = None
        for k, _ in people:                     # nearest name before the trigger, else after it, in the clause
            for j in list(range(i - 1, a - 1, -1)) + list(range(i + 1, b + 1)):
                if keys[j] in names[k] or (keys[j].endswith("s") and keys[j][:-1] in names[k]):
                    d = (i - j) if j < i else (j - i) + 50
                    if best is None or d < best:
                        best, subject = d, k
                    break
        if subject is not None:
            found.append((0, t0, expr, [subject]))
        elif expr in EVERYONE:
            found.append((1, t0, expr, [k for k, _ in people]))
        elif main is not None:
            found.append((1, t0, expr, [main]))
    # reactions of a named character first, then the guesses
    for _, t0, expr, targets in sorted(found, key=lambda f: (f[0], f[1])):
        for k in targets:
            lst = out.setdefault(k, [])
            if len(lst) < MAX_PER_CHAR and all(abs(t0 - t) > REACT_DUR + 0.1 for t, _ in lst):
                lst.append((max(0.0, t0), expr))
    return {k: sorted(v) for k, v in out.items() if v}


def merge(acts, reactions, appear_s, exit_s=None, dur=None):
    """Add react actions to a character's action list where they don't fight the character's own actions."""
    out = list(acts)
    for t0, expr in reactions:
        if t0 < appear_s + 0.25 or (exit_s is not None and t0 > exit_s - 0.4):
            continue
        if dur is not None and t0 > dur - 0.4:
            continue
        busy = any(a["act"] in FACE_ACTS and a["t0"] - 0.3 < t0 + REACT_DUR and t0 < a["t0"] + a.get("dur", 1.0)
                   for a in out)
        if busy:
            continue
        out.append(dict(act="react", t0=t0, dur=REACT_DUR, expr=expr))
    return sorted(out, key=lambda a: a["t0"])
