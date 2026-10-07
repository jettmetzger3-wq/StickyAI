"""Visual continuity: scene 8 has to know what happened in scene 7.

The tracker keeps, after every scene: the place (and its look), the time of day, who is on stage, which props are out,
the emotional tone, the pattern that was used and the camera. The director prompt gets the last few as a "story so far"
line, the composer reuses the same place when the story stays there, and check() finds the places where a scene
jumps (a new place with no title card, a day turning into night mid-conversation, a character in a different hat).
"""
import copy
import re

from ..knowledge import composer as CO
from .themes import TIME_NEXT
from .project import read_json, write_json

PAINTED = ("field", "hills", "desert", "snow", "city", "battlefield", "street", "harbor", "beach", "jungle", "mountains",
           "palace")
TIME_WORDS = {"night": "night", "midnight": "night", "dawn": "dawn", "sunrise": "dawn", "dusk": "dusk", "sunset": "dusk",
              "evening": "dusk", "morning": "day", "storm": "storm"}


def state_of(scene, a=None, pattern="", beat_idx=0):
    """What a finished scene leaves behind, as plain JSON."""
    bg = dict((scene or {}).get("bg") or {})
    els = (scene or {}).get("elements") or []
    chars = [e.get("who") or e.get("kind") for e in els if e.get("type") == "char" and not e.get("narrator")]
    props = [e.get("name") for e in els if e.get("type") == "prop"]
    cam = (scene or {}).get("camera") or {}
    return dict(beat=beat_idx, place=bg.get("type"), bg=bg, time=bg.get("time"), chars=chars[:6], props=props[:6],
                tone=(a or {}).get("emotion") or (a or {}).get("mood") or "neutral", pattern=pattern,
                camera="close-up" if cam.get("shots") else "wide", people=[p["name"] for p in (a or {}).get("people", [])][:4])


class Tracker:
    """The per-video continuity state, saved in continuity.json so a redrawn scene knows what came before it."""

    def __init__(self, project=None):
        self.project = project
        self.data = (read_json(project.p("continuity.json"), {}) or {}) if project else {}
        self.states = self.data.get("states") or {}

    def before(self, i):
        """The composer's state dict to start beat `i` with (the state after beat i-1)."""
        prev = self.states.get(str(i - 1)) or {}
        c = {}
        if prev.get("bg"):
            c["bg"] = copy.deepcopy(prev["bg"])
        if prev.get("banner"):
            c["banner"] = tuple(prev["banner"])
        return c

    def record(self, i, scene, a, pattern, ctx_state=None):
        st = state_of(scene, a, pattern, i)
        if ctx_state and ctx_state.get("banner"):
            st["banner"] = list(ctx_state["banner"])
        self.states[str(i)] = st
        return st

    def line(self, i, n=2):
        """'Story so far' for the director prompt: the last n scenes in one short line each."""
        out = []
        for k in range(max(0, i - n), i):
            st = self.states.get(str(k))
            if st:
                out.append(f"[{k}] {st.get('pattern') or 'scene'} in {st.get('place') or '?'}"
                           + (f" ({st['time']})" if st.get("time") else "")
                           + (f"; on stage: {', '.join(str(c) for c in st['chars'] if c)}" if st.get("chars") else "")
                           + f"; tone {st.get('tone')}")
        return "\n".join(out)

    def save(self, issues=None):
        if self.project:
            write_json(self.project.p("continuity.json"), dict(states=self.states, issues=issues or self.data.get("issues") or []))


def check(scenes, analyses, registry, beats):
    """Fix and report continuity breaks. `scenes` = {index: scene dict} (changed in place). Returns [issue dicts]."""
    issues = []
    by_name = {}
    for e in registry or []:
        for key in [e["name"].lower()] + [p for p in re.split(r"\s+", e["name"].lower()) if len(p) >= 4]:
            by_name.setdefault(key, e)
    order = sorted(scenes)
    prev = None
    for i in order:
        sc = scenes[i]
        if not isinstance(sc, dict):
            continue
        a = analyses[i] if i < len(analyses) else {}
        bg = sc.get("bg") or {}
        text = (beats[i].get("text") if i < len(beats) else "") or ""
        # 1. a character in a different outfit than the registry says
        for el in sc.get("elements") or []:
            if el.get("type") != "char" or not el.get("who") or el.get("narrator"):
                continue
            e = by_name.get(str(el["who"]).lower()) or by_name.get(str(el["who"]).lower().split()[-1])
            if e and el.get("kind") and e.get("kind") and el["kind"] != e["kind"] and el["kind"] not in ("crown", "laurel", "knight"):
                issues.append(dict(beat=i, check="continuity", severity="low", fixed=True,
                                   msg=f"{el['who']} had a different hat ({el['kind']}) than in the rest of the video: set to {e['kind']}"))
                el["kind"] = e["kind"]
                if e.get("hat_color"):
                    el["hat_color"] = e["hat_color"]
        if prev is not None:
            pbg = (scenes[prev].get("bg") or {}) if isinstance(scenes[prev], dict) else {}
            # 2. the same place suddenly at another time of day
            natural = TIME_NEXT.get(pbg.get("time") or "day")          # day -> dusk -> night -> dawn is time passing
            if bg.get("type") == pbg.get("type") and bg.get("type") in PAINTED and (bg.get("time") or "day") != (pbg.get("time") or "day") \
                    and (bg.get("time") or "day") != natural:
                said = any(w in text.lower() for w in TIME_WORDS)
                if not said and sc.get("light") is None:
                    issues.append(dict(beat=i, check="continuity", severity="low", fixed=True,
                                       msg=f"the time of day changed from {pbg.get('time') or 'day'} to {bg.get('time') or 'day'} with no reason: kept {pbg.get('time') or 'day'}"))
                    if pbg.get("time"):
                        bg["time"] = pbg["time"]
                    else:
                        bg.pop("time", None)
            # 3. a new place with nothing telling the viewer where we are
            elif bg.get("type") != pbg.get("type") and bg.get("type") not in ("map", "paper", "sunburst", "dark"):
                titled = any(e.get("type") == "text" and e.get("y", 999) < 200 for e in sc.get("elements") or [])
                place = next((p for p in a.get("places") or []), None)
                year = (a.get("years") or [None])[0]
                if not titled and (place or year) and not a.get("intro"):
                    label = ", ".join(str(x) for x in (place["name"] if place else None, year) if x)
                    sc.setdefault("elements", []).insert(0, CO.text(label, CO.MID, 105, 70, "navy", at=0.0))
                    issues.append(dict(beat=i, check="continuity", severity="low", fixed=True,
                                       msg=f"the story moved to a new place with no title: added '{label}'"))
        prev = i
    return issues
