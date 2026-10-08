"""A free, local quality pass over the script: what an editor would circle before the voice is recorded.

It never asks an AI. It finds the beats that need rewording and says why in plain words; only those beats go back to the
writer, in the same single request that smooths the flow (`stages.smooth_flow`, `fix_list` below). Checks:

  opening   a greeting, "in this video", "today we..." or a hook that runs on (the first seconds decide if people stay)
  ending    the story ends on a trailing word ("and", "but") or a filler ("so yeah", "that's about it")
  repeats   the same four-word phrase in three or more beats, or three beats opening with the same two words
  filler    words that read as machine-written (the list the writer is already told to avoid)
  pacing    a beat too long to say in one breath
  notes     (never rewritten) a run of beats of the same length, and names the voice may stumble on

Numbers, years and names are never touched here; a rewrite must keep them (flow.keeps_facts).
"""
import re

from . import flow as FL
from .. import prompts as PR

LONG_BEAT = 38                 # words: more than this is hard to say in one breath (a rewrite is asked to stay under 35)
HOOK_MAX = 30                  # a hook that runs past this many words is a paragraph
MONOTONE = 5                   # this many beats in a row of about the same length read like a metronome
REPEAT_GRAM = 4
REPEAT_MIN = 3

FLAT_OPENER = re.compile(
    r"^\W*(hello|hi|hey|welcome|greetings|in this video|in today'?s|today,? (we|i)\b|so,? today|let'?s (dive|get started|talk about|take a look)|"
    r"before we (begin|start)|ladies and gentlemen|this video)", re.I)
WEAK_END_WORD = {"and", "but", "so", "because", "the", "a", "an", "to", "of", "or", "that", "which", "with", "for", "in", "on"}
WEAK_END_PHRASE = re.compile(r"(so yeah|and that'?s (all|it|about it)|that'?s (all|about it|it for)|anyway|i guess|something like that|"
                             r"and so on|the end|you know)\W*$", re.I)
FILLER_PHRASES = ("it's important to note", "it is important to note", "when it comes to", "in the world of", "plays a crucial role",
                  "a testament to", "shed light on", "sheds light on", "at the end of the day", "needless to say", "game-changer",
                  "dive into", "dives into", "rich tapestry", "ever-evolving", "in today's world", "stands as a")
STOP = FL.STOP | set("one of the most a an is was were are be been to".split())
HARD_NAME = re.compile(r"\b[A-Z][a-z]*(?:szcz|zcz|prz|rzy|wsk|czy|cze|cza|czo|zhou|khr|kh[aeiouy]|ghi)[a-z]*\b", re.I)


def _words(text):
    return re.findall(r"[a-z0-9']+", str(text or "").lower())


def _real(beats):
    """[(index, text)] of the beats the writer wrote (the host's own beats are not part of the story)."""
    return [(i, b.get("text", "")) for i, b in enumerate(beats or []) if b.get("text") and not b.get("host")]


def _repeats(real):
    where = {}
    for i, t in real:
        w = _words(t)
        seen = set()
        for k in range(len(w) - REPEAT_GRAM + 1):
            g = tuple(w[k:k + REPEAT_GRAM])
            if sum(1 for x in g if x not in STOP) >= 2 and g not in seen:
                seen.add(g)
                where.setdefault(g, []).append(i)
    out = {}
    for g, idx in where.items():
        if len(idx) >= REPEAT_MIN:
            for i in idx[REPEAT_MIN - 1:]:                  # the first two uses are fine; the third and later get the note
                out.setdefault(i, f"repeats '{' '.join(g)}' from earlier beats")
    return out


def _openers(real):
    out = {}
    heads = [(i, " ".join(_words(t)[:2])) for i, t in real]
    for k in range(len(heads)):
        window = heads[max(0, k - 4):k + 1]
        h = heads[k][1]
        if len(h.split()) == 2 and sum(1 for _, x in window if x == h) >= 3:
            out.setdefault(heads[k][0], f"opens with '{h}' again (three of the last five beats do)")
    return out


def problems(beats):
    """[(beat index, why, severity)] the writer should fix. severity: 'high' (opening/ending) or 'medium'."""
    real = _real(beats)
    out = {}

    def add(i, why, sev="medium"):
        old = out.get(i)
        out[i] = (f"{old[0]}; {why}" if old else why, "high" if sev == "high" or (old and old[1] == "high") else "medium")

    if real:
        i0, t0 = real[0]
        if (beats[i0].get("part") in (None, "hook") or i0 == 0):
            if FLAT_OPENER.match(t0):
                add(i0, "the opening is a greeting or 'in this video': start on the most surprising thing instead", "high")
            elif len(t0.split()) > HOOK_MAX:
                add(i0, f"the hook is {len(t0.split())} words: a hook is one or two short sentences", "high")
        i1, t1 = real[-1]
        w = _words(t1)
        if len(real) > 1 and ((w and w[-1] in WEAK_END_WORD) or WEAK_END_PHRASE.search(t1)):
            add(i1, "the last line trails off: end on a clear payoff or punchline", "high")
    for i, why in _repeats(real).items():
        add(i, why)
    for i, why in _openers(real).items():
        add(i, why)
    for i, t in real:
        low = t.lower()
        hit = [x for x in PR.AVOID_WORDS if re.search(r"\b" + re.escape(x), low)] + [x for x in FILLER_PHRASES if x in low]
        if hit:
            add(i, f"reads machine-written ({', '.join(repr(x) for x in hit[:3])}): say it plainly")
        n = len(t.split())
        if n > LONG_BEAT:
            add(i, f"{n} words is a lot to say in one breath: tighten it")
    return [(i, why, sev) for i, (why, sev) in sorted(out.items())]


def notes(beats):
    """Things worth knowing that are never rewritten automatically."""
    real = _real(beats)
    out = []
    counts = [len(t.split()) for _, t in real]
    run = 1
    for k in range(1, len(counts) + 1):
        if k < len(counts) and abs(counts[k] - counts[k - 1]) <= 2:
            run += 1
            continue
        if run >= MONOTONE:
            out.append(dict(beat=real[k - run][0], kind="pacing",
                            msg=f"beats {real[k - run][0] + 1}-{real[k - 1][0] + 1} are all about {counts[k - 1]} words: vary the rhythm with a short punchline"))
        run = 1
    names = {}
    for i, t in real:
        for m in HARD_NAME.finditer(t):
            if m.start() > 0 and m.group(0)[0].isupper() and m.group(0).lower() not in STOP:
                names.setdefault(m.group(0), i)
    for nm, i in list(names.items())[:6]:
        out.append(dict(beat=i, kind="pronounce", msg=f"'{nm}' may be hard for the voice: add how it sounds in Settings > pronunciations if it comes out wrong"))
    return out


def report(script):
    beats = (script or {}).get("beats") or []
    real = _real(beats)
    counts = [len(t.split()) for _, t in real] or [0]
    return dict(problems=[dict(beat=i, why=w, severity=s) for i, w, s in problems(beats)], notes=notes(beats),
                stats=dict(beats=len(real), words=sum(counts), mean=round(sum(counts) / len(counts), 1), longest=max(counts), shortest=min(counts)))


def urgent(beats):
    """The beats whose problem is worth a request on its own: a bad opening or ending."""
    return {i for i, _, s in problems(beats) if s == "high"}


def fix_list(beats):
    """[(beat, why)] for the writer: the beats that don't connect to the one before (flow.seams) plus every beat the
    quality pass flagged, one line per beat. This is what 'Smooth the flow' rewrites, in one request."""
    merged = {}
    for i, why in FL.seams(beats):
        merged[i] = why
    for i, why, _ in problems(beats):
        merged[i] = f"{merged[i]}; {why}" if i in merged else why
    return sorted(merged.items())


def worth_asking(items, beats):
    """One rewrite request is worth it when several beats need it (3 or 10%), or when the opening or ending is bad."""
    if not items:
        return False
    return len(items) >= 3 and len(items) >= 0.1 * max(1, len(beats)) or bool({i for i, _ in items} & urgent(beats))
