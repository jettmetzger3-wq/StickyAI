"""The channel mascot: one recurring host stickman who greets viewers after the hook, signs off at the end, and
leans in from the right edge to react to the video's biggest moments ("WHAT?!", "Oof.", "Ha!").

The host's look and lines come from Settings (name, hat, colors, beard). Its two speaking beats are ordinary
beats in the script (marked "host"), so they can be edited or deleted in the Script tab; their scenes are drawn
here without asking the AI. Cameos are added while rendering, so turning them off needs no new storyboard.
"""
import re

from ..engine.pen import resolve_kind
from ..engine.reactions import triggers

DEFAULTS = dict(on=True, name="Sticky", kind="cap", hat_color="red", coat="", look="", intro=True, outro=True,
                cameos=True, intro_line="Hey, it's {name}! Today: {title}.",
                outro_line="And that's the story of {title}! I'm {name}. See you next time!")
QUIPS = {"surprise": ["WHAT?!", "Wait, what?", "No way!"], "angry": ["Rude!", "Seriously?!", "Ugh!"],
         "smug": ["Called it.", "Classic.", "Nailed it."], "laugh": ["Ha!", "LOL", "Hah!"],
         "sad": ["Oof.", "Ouch...", "Oh no."], "scared": ["Yikes!", "Uh oh...", "Eek!"],
         "happy": ["Yay!", "Nice!", "Woo!"], "confused": ["Huh?", "Wait...", "Hmm?"]}
CAMEO_ORDER = ("surprise", "laugh", "angry", "smug", "scared", "sad", "confused", "happy")
CAMEO_EVERY = 7          # at most one cameo per this many beats


def settings_of(settings):
    m = dict(DEFAULTS)
    m.update({k: v for k, v in ((settings or {}).get("mascot") or {}).items() if k in DEFAULTS and v is not None})
    m["kind"] = resolve_kind(m.get("kind") or "cap")
    m["name"] = str(m.get("name") or "Sticky").strip()[:24] or "Sticky"
    return m


def host_el(m, **kw):
    el = dict(type="char", kind=m["kind"], who=m["name"], react=False)
    if m.get("hat_color"):
        el["hat_color"] = m["hat_color"]
    if m.get("coat"):
        el["coat"] = m["coat"]
    if m.get("look") in ("beard", "mustache"):
        el["extras"] = [m["look"]]
    el.update(kw)
    return el


def _line(template, m, title):
    title = re.sub(r"\s+", " ", str(title or "").strip()).rstrip(".!?") or "history"
    try:
        out = str(template).format(name=m["name"], title=title)
    except (KeyError, IndexError, ValueError):
        out = str(template)
    return re.sub(r"\s+", " ", out).strip()[:200]


# ------------------------------------------------------------------ script beats
def add_host_beats(script, settings):
    """Put the host's greeting after the hook and its sign-off at the end (or update them). Changes `script`."""
    m = settings_of(settings)
    beats = [b for b in script.get("beats") or [] if not b.get("host")]
    if not m["on"] or not beats:
        script["beats"] = beats
        return script
    title = script.get("title") or script.get("topic") or ""
    if m["intro"]:
        beats.insert(min(1, len(beats)), dict(mood="fun", text=_line(m["intro_line"], m, title), host="intro"))
    if m["outro"]:
        last = [b for b in beats if not b.get("host")][-1]
        beats.append(dict(mood="somber" if last.get("mood") == "somber" else "fun",
                          text=_line(m["outro_line"], m, title), host="outro"))
    script["beats"] = beats
    return script


# ------------------------------------------------------------------ the host's own scenes
def host_scene(beat, settings, title="", idx=0):
    """The greeting and the sign-off: the host big on screen, talking with the narrator's voice."""
    m = settings_of(settings)
    talk = [{"at": 0.0, "dur": 60}]
    title_txt = re.sub(r"\s+", " ", str(title or "")).strip().upper()[:28]
    if beat.get("host") == "outro":
        somber = beat.get("mood") == "somber"
        return {
            "bg": {"type": "dark"} if somber else {"type": "sunburst", "color": "#FFE7A8", "ray": "#FFD36B"},
            "elements": [
                host_el(m, x=620, y=900, scale=1.3, narrator=True, talk=talk, pose="wave" if not somber else "down",
                        mouth="smile", enter="pop", at=0.0,
                        do=[] if somber else [{"act": "wave", "at": 0.05, "dur": 1.8}, {"act": "point", "at": 0.6}]),
                {"type": "shape", "shape": "rect", "x": 1320, "y": 470, "w": 540, "h": 160, "fill": "#E0453A",
                 "stroke": "#7A1E18", "width": 8, "radius": 36, "enter": "pop", "at": 0.35},
                {"type": "text", "text": "SUBSCRIBE", "x": 1320, "y": 470, "size": 76, "color": "white",
                 "enter": "pop", "at": 0.35},
                {"type": "text", "text": m["name"].upper(), "x": 620, "y": 330, "size": 60, "color": "navy",
                 "at": 0.1},
            ],
            "camera": {"zoom": [1.0, 1.04]}, "react": False,
        }
    return {
        "bg": {"type": "sunburst", "color": "#DDF0FF", "ray": "#B8E0FF"},
        "elements": [
            host_el(m, x=560, y=900, scale=1.35, narrator=True, talk=talk, pose="wave", mouth="grin", enter="drop",
                    at=0.0, do=[{"act": "wave", "at": 0.1, "dur": 1.6}, {"act": "point", "at": 0.55}]),
            {"type": "text", "text": m["name"].upper(), "x": 560, "y": 310, "size": 60, "color": "navy", "at": 0.05},
            {"type": "text", "text": title_txt or "TODAY", "x": 1330, "y": 450, "size": 96 if len(title_txt) < 16 else 70,
             "color": "red", "enter": "pop", "at": 0.45},
        ],
        "camera": {"zoom": [1.0, 1.05]}, "react": False,
    }


# ------------------------------------------------------------------ cameos at big moments
def cameo_plan(beats, settings):
    """{beat index: (trigger word, expression)} for the beats where the host pops in: the strongest reaction
    word in every stretch of CAMEO_EVERY beats (never in the first two beats, the host's own beats or the end)."""
    m = settings_of(settings)
    if not (m["on"] and m["cameos"]):
        return {}
    cands = []
    for i, b in enumerate(beats):
        if b.get("host") or i < 2 or i >= len(beats) - 1:
            continue
        words = str(b.get("text") or "").split()
        hits = triggers(words)
        if b.get("mood") == "somber":
            hits = [(k, e) for k, e in hits if e in ("sad", "scared")]
        if not hits:
            continue
        k, expr = min(hits, key=lambda h: (CAMEO_ORDER.index(h[1]), -h[0]))
        cands.append((CAMEO_ORDER.index(expr), i, words[k], expr))
    out = {}
    for rank, i, word, expr in sorted(cands):
        if all(abs(i - j) >= CAMEO_EVERY for j in out):
            out[i] = (re.sub(r"[^\w'-]", "", word), expr)
    return out


def cameo_elements(word, expr, settings, idx=0):
    """The host leaning in from the right edge (above the captions) on the word, with a one-word quip, then
    slipping away again."""
    m = settings_of(settings)
    quip = QUIPS.get(expr, ["Whoa!"])[idx % 3]
    at = f"word:{word}"
    return [
        host_el(m, x=1862, y=905, scale=0.85, peek=True, flip=True, enter="slide_right", at=at,
                exit=f"word:{word}+1.9", z=6, life=True,
                do=[{"act": "lean", "amount": 26, "at": at, "dur": 1.9}, {"act": "react", "expr": expr, "at": at}]),
        {"type": "bubble", "text": quip, "x": 1660, "y": 450, "size": 46, "tail": [120, 56],
         "at": f"word:{word}+0.15", "exit": f"word:{word}+1.8", "z": 6},
    ]


def with_cameo(scene, i, beats, settings, plan=None):
    """The scene as rendered: the stored scene plus the host's cameo when this beat has one."""
    plan = cameo_plan(beats, settings) if plan is None else plan
    if i not in plan or not isinstance(scene, dict):
        return scene
    word, expr = plan[i]
    out = dict(scene)
    out["elements"] = list(scene.get("elements") or []) + cameo_elements(word, expr, settings, i)
    return out
