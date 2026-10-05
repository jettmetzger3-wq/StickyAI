"""All LLM prompts in one place. The scene-language reference is generated from the engine's registries so
the docs the LLM sees always match what the renderer can draw."""
import json
import os

from ..engine.pen import ARMS, LEGS, MOUTHS, EYES, EXTRAS, HELD, HATS, KIND_ALIASES
from ..engine.registry import PROPS, ICONABLE
from ..engine.geo import REGIONS
from ..engine.schema import ENTERS, IDLES, BG_TYPES

HERE = os.path.dirname(os.path.abspath(__file__))

AVOID_WORDS = ("delve", "tapestry", "testament", "intricate", "multifaceted", "pivotal", "realm", "unveil",
               "embark", "navigate the complexities", "in conclusion", "it's worth noting", "a rich history")

# ------------------------------------------------------------------ script
SCRIPT_SYSTEM = ("You are the head writer of a hugely popular YouTube channel of funny, simple stickman history "
                 "explainers (like 'Historically' or 'The ENTIRE History of Rome'). You write tight, spoken, "
                 "punchy narration that is accurate. You always answer with JSON only.")

SCRIPT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["title", "topic", "beats", "facts", "cast"],
    "properties": {
        "title": {"type": "string"},
        "topic": {"type": "string"},
        "beats": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["mood", "text"],
            "properties": {"mood": {"type": "string", "enum": ["fun", "tense", "somber"]}, "text": {"type": "string"}}}},
        "facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["beat", "claim", "confidence", "note"],
            "properties": {"beat": {"type": "integer"}, "claim": {"type": "string"},
                           "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                           "note": {"type": "string"}}}},
        "cast": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "kind", "hat_color"],
            "properties": {"name": {"type": "string"}, "kind": {"type": "string"}, "hat_color": {"type": "string"}}}},
    },
}

WRITING_RULES = """WRITING RULES
- Output a list of BEATS. Each beat = one or two spoken sentences, roughly 15 to 30 words, plus a mood:
  "fun" (default, jokes allowed), "tense" (stakes rising, lighter jokes), "somber" (tragedy: no jokes).
- Hook in the first 20 seconds: open with a surprising fact AND the question the video will answer.
- Open 2 to 4 story loops ("remember the oil problem?" style) and close every one of them later with a callback.
- Change the pattern every 30 to 90 seconds (a map, a "meanwhile", a quick list, a fake quote, a rhetorical question).
- Anchor beats to concrete dates, people, places and numbers. Every beat should be drawable as one doodle scene.
- Spoken style: contractions, short sentences, plain words. Funny but respectful.
- Never use these AI-sounding words/phrases: {avoid}. Never use the "It's not X, it's Y" construction.
  Never use em dashes or en dashes; use commas, periods or "and".
- Sensitive history (massacres, bombings, genocide, slavery, famine): switch those beats to "somber", no jokes,
  respectful wording, and casualty numbers that sit inside mainstream historian ranges ("historians estimate...").
- End with a payoff that echoes the opening hook, then one short subscribe line (last beat).
- Write numbers as digits for years ("1941") and words or digits for amounts; the voice handles both.

FACT LIST
- Alongside the script, list EVERY date, number and factual claim as a checklist item with the beat index it
  appears in (0-based), your confidence ("high" | "medium" | "low") and a short note (why uncertain, or the
  common alternative figure). Be honest: mark anything debated or approximate as "medium" or "low".

CAST
- List the recurring characters (nations, people, groups). For each pick a stickman "kind" (hat) from this list:
  {kinds}
  (aliases also work: {aliases}). Optionally give a hat_color (a color name or #hex) to tell similar hats apart,
  otherwise use "".
"""


def target_beats(minutes):
    return max(6, int(round(float(minutes) * 8)))


def script_prompt(topic, minutes=10, tone="funny but respectful", style_notes="", source=None, faithfulness="balanced",
                  extra=""):
    """source: dict(title, channel, description, chapters, transcript_text, visual_notes) for YouTube remakes."""
    n = target_beats(minutes)
    rules = WRITING_RULES.format(avoid=", ".join(AVOID_WORDS), kinds=", ".join(h for h in HATS if h != "none"),
                                 aliases=", ".join(sorted(KIND_ALIASES)[:40]))
    parts = []
    if source:
        how = {
            "close": "Follow the source video's structure and order of events closely, keep its main beats and the "
                     "spirit of its jokes, but rewrite every sentence in your own words.",
            "balanced": "Cover the same subject and the same main points, but build your own structure, hook and jokes.",
            "loose": "Only keep the subject. Research it yourself and make a fresh video with its own angle.",
        }.get(faithfulness, "")
        parts.append(
            "TASK: Remake a YouTube video as a NEW, ORIGINAL stickman history script.\n"
            "You are given the source video's transcript and notes as research material. Write a completely new "
            "narration: never copy sentences or distinctive phrases from the source (copied scripts get channels "
            "demonetized for 'reused content'). Fact-check the source; if it gets something wrong, write the correct "
            "version and mention it in the fact list note.\n"
            f"How closely to follow it: {faithfulness.upper()}. {how}\n")
        src = [f"SOURCE VIDEO: {source.get('title', '')} (channel: {source.get('channel', '')}, "
               f"{int(source.get('duration') or 0) // 60} min)"]
        if source.get("chapters"):
            src.append("Chapters: " + "; ".join(f"{c.get('start_time', 0):.0f}s {c.get('title', '')}" for c in source["chapters"]))
        if source.get("visual_notes"):
            vn = source["visual_notes"]
            src.append("What the video shows (from watching it): style: " + str(vn.get("style", "")) +
                       ". Characters: " + ", ".join(vn.get("characters", [])) +
                       ". Running gags: " + ", ".join(vn.get("running_gags", [])))
        text = source.get("transcript_text", "")
        if len(text) > 120000:
            text = text[:120000] + " [...]"
        src.append("TRANSCRIPT (timestamps in seconds):\n" + text)
        parts.append("\n".join(src))
        if topic:
            parts.append(f"Topic focus requested by the user: {topic}")
    else:
        parts.append(f"TASK: Write a stickman history explainer script about: {topic}")
        if style_notes:
            parts.append("Style reference notes: " + style_notes)
    words = int(round(float(minutes) * 150))
    parts.append(f"LENGTH (strict): about {minutes} minutes spoken at ~150 words per minute = about {words} words in "
                 f"total, split into about {n} beats (between {int(n * 0.85)} and {int(n * 1.15)}). Beats average about "
                 f"19 words; never more than 30 words in one beat. Count your words. Tone: {tone}.")
    if extra:
        parts.append("EXTRA INSTRUCTIONS FROM THE USER: " + extra)
    parts.append(rules)
    parts.append('Answer with JSON only: {"title": working title, "topic": short topic, "beats": [{"mood", "text"}], '
                 '"facts": [{"beat", "claim", "confidence", "note"}], "cast": [{"name", "kind", "hat_color"}]}')
    return "\n\n".join(parts)


def regen_beat_prompt(beats, index, instruction=""):
    ctx = []
    for i in range(max(0, index - 3), min(len(beats), index + 4)):
        mark = ">>>" if i == index else "   "
        ctx.append(f"{mark} [{i}] ({beats[i]['mood']}) {beats[i]['text']}")
    return ("Rewrite ONLY the beat marked >>> so it flows with its neighbours. Keep it 15-30 words, spoken style, "
            "accurate, no em dashes, no AI filler words. " + (f"User request: {instruction}. " if instruction else "") +
            "\n\n" + "\n".join(ctx) +
            '\n\nAnswer with JSON only: {"mood": "fun|tense|somber", "text": "..."}')


REGEN_BEAT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["mood", "text"],
                     "properties": {"mood": {"type": "string", "enum": ["fun", "tense", "somber"]},
                                    "text": {"type": "string"}}}


# ------------------------------------------------------------------ storyboard
STORYBOARD_SYSTEM = ("You are the storyboard artist of a funny stickman history YouTube channel. You turn each "
                     "narration beat into ONE doodle scene described in a small JSON scene language. You never write "
                     "code, only JSON.")


def scene_language():
    props = "\n".join(f"  - {n} ({a}): {d}" for n, (a, _, d) in sorted(PROPS.items()))
    regions = ", ".join(sorted(REGIONS))
    return f"""SCENE LANGUAGE (1920x1080 frame, x to the right, y down. Bottom 180 px (y > 900) is reserved for captions:
never put text there. Characters' feet may stand at y 860-930.)

A scene is: {{"bg": {{...}}, "elements": [...], "camera": {{...}}}}

BACKGROUNDS ("bg"): type is one of {", ".join(BG_TYPES)}.
  paper {{color}} | sunburst {{color, ray}} | ground {{sky, ground, y: horizon y (default 860)}} |
  sea {{sky, sea, horizon (default 520)}} | night | dark {{color}} (use for somber beats) |
  map {{center: [lon, lat], width: degrees of longitude across the frame (Europe ~40, a country ~15-25, Pacific ~110),
       territories: [{{countries: [...] | region: preset, color, clip?: [[lon,lat],...], box?: [lon0,lat0,lon1,lat1]}}],
       labels: [{{text, lon, lat, size}}]}}  (Mercator; keep everything you mention inside the view)
  Any bg can have "items": static props/shapes drawn into the background (no animation).

ELEMENTS (all screen positions are x,y pixels; on map scenes you may use lon/lat instead):
  char:  a stickman. {{x, y = point between the feet, scale (0.4 small .. 1.6 giant; 1.0 = 375 px tall), kind (hat),
         hat_color?, pose, legs, mouth, eyes, extras[], prop (held item), prop_color?, flip (face left), look (-1|0|1)}}
         kind: {", ".join(h for h in HATS if h != "none")}
         pose: {", ".join(ARMS)}
         legs: {", ".join(LEGS)}
         mouth: {", ".join(MOUTHS)}    eyes: {", ".join(EYES)}
         extras: {", ".join(EXTRAS)} ("q" = question mark)   prop: {", ".join(HELD)}
  text:  {{text, x, y (center), size (40-120), color, font: "bold" (Fredoka) | "hand" (handwritten), align}}
  prop:  {{name, x, y, scale, color?, params?}}. Anchor "bottom" = x,y is the bottom-center (things standing on the
         ground); anchor "center" = x,y is the middle. Available props:
{props}
  bubble: speech bubble {{text ("\\n" for new line), x, y (center), size, tail: "left"|"right"|"down", font}}
  note:  yellow sticky note {{text, x, y, size}}
  sign:  wooden sign on a post {{text, x, y = bottom of the post, size}}
  board: whiteboard list {{x, y (center), title, lines: [...], size}} (great for "THE PLAN", pros/cons, rankings)
  icons: a grid of small prop icons for counts/comparisons {{icon (one of: {", ".join(ICONABLE)}), count, per_row,
         x, y (bottom-center of the grid), scale (0.3-1.0)}}
  shape: {{shape: rect|circle|ellipse|line|poly, x, y, w, h, r, points: [[x,y],...], fill, stroke, width, radius}}
  group: {{items: [prop/text/shape/char...]}} several things that animate together as one layer
  territory (maps): {{countries: [...] | region, clip?, box?, color}} default enter "wipe_right"
  city (maps): {{name, lon, lat, size, color}}
  arrow: {{from: [x,y] or {{lon,lat}}, to: ..., or points: [...], curve (px bend, + or -), color, width, head}}

  Natural Earth country names (common ones): "United States of America", "United Kingdom", "Russia", "China",
  "Japan", "France", "Germany", "Italy", "Spain", "Egypt", "India", "Korea" (both Koreas), "Turkey", "Iran", ...
  Region presets: {regions}

ANIMATION (any element): enter: {", ".join(ENTERS)} (default pop); at: when it appears, a fraction 0-1 of the
  scene or "word:Britain" to pop in exactly when the narrator says that word (best!); delay (seconds after "at");
  idle: {", ".join(IDLES)} (chars default to bob); exit: fraction or "word:xxx" to fade out;
  move: {{dx, dy, from, to}} (from/to like "at"); z: layer order (higher = in front).
CAMERA: {{zoom: [start, end] (1.0-1.12, a slow push-in like [1.0, 1.05]), center: [x, y], to: [x, y]}}

COLORS: ink, red, darkred, navy, blue, lightblue, green, darkgreen, olive, gray, dgray, orange, yellow, gold, brown,
  white, purple, pink, teal, cream, maroon, khaki, silver, black, paper, sea, land, or "#rrggbb".

STYLE RULES
- One clear idea per scene. 3 to 8 elements. Big readable labels (size 50-110). Leave breathing room.
- Characters ARE the nations/people (use the cast). Size shows power (big = strong, small = weak).
- Make the joke visual: exaggerated faces, a bubble with a funny one-liner, a sticky note callback, a sign.
- Time the reveals to the narration with "word:..." so things pop in as they are said.
- Vary backgrounds and layouts from scene to scene; use maps whenever geography matters.
- Somber beats: bg "dark" or "paper", fade entrances, no jokes, no grins, no explosions as gags, candles are fine.
- Keep every element fully inside the frame; text never below y=880.
"""


def load_examples():
    with open(os.path.join(HERE, "examples.json"), encoding="utf-8") as f:
        return json.load(f)


def examples_block(limit=14):
    ex = load_examples()[:limit]
    out = []
    for e in ex:
        out.append(f'BEAT ({e["mood"]}): {e["text"]}\nSCENE: ' + json.dumps(e["scene"], separators=(",", ":")))
    return "\n\n".join(out)


def storyboard_prompt(batch, all_beats, cast, title, visual_hints=None):
    """batch: list of (index, beat). visual_hints: {index: "what the source video showed around then"}."""
    cast_lines = "\n".join(f"- {c.get('name')}: kind={c.get('kind')}" + (f", hat_color={c['hat_color']}" if c.get("hat_color") else "")
                           for c in cast or [])
    first = batch[0][0]
    ctx = [f"[{i}] ({b['mood']}) {b['text']}" for i, b in enumerate(all_beats) if first - 2 <= i < first]
    beats = []
    for i, b in batch:
        line = f"[{i}] ({b['mood']}) {b['text']}"
        if visual_hints and visual_hints.get(i):
            line += f"\n     (source video showed: {visual_hints[i]})"
        beats.append(line)
    return f"""{scene_language()}

EXAMPLES (beat -> scene):
{examples_block()}

VIDEO: {title}
CAST (use these kinds consistently):
{cast_lines or "- (pick sensible kinds)"}

Previous beats for context:
{chr(10).join(ctx) or "(start of video)"}

Make one scene for each of these beats:
{chr(10).join(beats)}

Answer with JSON only: {{"scenes": [{{"beat": <index>, "scene": {{"bg": ..., "elements": [...], "camera": ...}}}}, ...]}}"""


def fix_scene_prompt(scene, errors, beat):
    return f"""{scene_language()}

This scene for the beat below has problems. Return a corrected scene.
BEAT ({beat['mood']}): {beat['text']}
PROBLEMS:
{chr(10).join('- ' + e for e in errors[:12])}
SCENE:
{json.dumps(scene)[:6000]}

Answer with JSON only: {{"bg": ..., "elements": [...], "camera": ...}}"""


# ------------------------------------------------------------------ watching the source video
VISION_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["style", "characters", "running_gags", "moments"],
    "properties": {
        "style": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "string"}},
        "running_gags": {"type": "array", "items": {"type": "string"}},
        "moments": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["time", "visual"],
            "properties": {"time": {"type": "number"}, "visual": {"type": "string"}}}},
    },
}


def vision_prompt(n_images, title):
    return (f"These {n_images} images are contact sheets of frames from the YouTube video '{title}'. Each small frame "
            "has its timestamp (seconds) printed in the corner. Describe how the video LOOKS so another animator can "
            "make an original video on the same topic: the drawing style, the recurring characters and how they are "
            "drawn (hats, colors, what represents which nation/person), running visual gags, and for each frame a short "
            "description of what is on screen (as 'moments' with the time in seconds). Be concrete and short.\n"
            'Answer with JSON only: {"style": "...", "characters": ["..."], "running_gags": ["..."], '
            '"moments": [{"time": 12, "visual": "..."}]}')


# ------------------------------------------------------------------ YouTube packaging
PACKAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["titles", "hook", "chapters", "question", "tags", "hashtags", "thumbnail"],
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}},
        "hook": {"type": "string"},
        "chapters": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["beat", "title"],
            "properties": {"beat": {"type": "integer"}, "title": {"type": "string"}}}},
        "question": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "thumbnail": {"type": "object", "additionalProperties": False,
                      "required": ["line1", "line2", "small_kind", "big_kind", "image_prompt"],
                      "properties": {"line1": {"type": "string"}, "line2": {"type": "string"},
                                     "small_kind": {"type": "string"}, "big_kind": {"type": "string"},
                                     "image_prompt": {"type": "string"}}},
    },
}


def package_prompt(script, minutes):
    beats = "\n".join(f"[{i}] {b['text']}" for i, b in enumerate(script.get("beats", [])))
    cast = ", ".join(f"{c.get('name')}={c.get('kind')}" for c in script.get("cast", []))
    return f"""Package this stickman history video for YouTube. Video length: about {minutes:.1f} minutes.
Working title: {script.get('title', '')}
Cast: {cast}

SCRIPT (beat index in brackets):
{beats}

Return:
- titles: 3 clickable but honest title options (max 70 characters, no clickbait lies, no emojis).
- hook: a 2-3 sentence description opening paragraph that makes people want to watch.
- chapters: 5 to 10 chapters as {{"beat": index where the chapter starts, "title": short chapter name}}. The first
  chapter must start at beat 0. Chapters must be at least ~10 seconds apart (several beats).
- question: one question to ask viewers in the comments.
- tags: 10-15 search tags. hashtags: 3 hashtags like "#history".
- thumbnail: line1 (2-4 punchy words), line2 (2-4 words), small_kind (the small angry character's hat kind),
  big_kind (the giant smug character's kind), image_prompt (a short scene description for an AI image
  background, no text in the image). Kinds come from: {", ".join(h for h in HATS if h != "none")}.
Plain spoken English, no em dashes, no AI filler words. Answer with JSON only."""


SHORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["start", "end", "title", "script", "description", "hashtags"],
    "properties": {
        "start": {"type": "integer"}, "end": {"type": "integer"},
        "title": {"type": "string"}, "script": {"type": "string"}, "description": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
    },
}


def short_prompt(script, durations, video_title):
    beats = "\n".join(f"[{i}] ({d:.1f}s) {b['text']}" for i, (b, d) in enumerate(zip(script.get("beats", []), durations)))
    return f"""We are cutting a YouTube Short (vertical, under 60 seconds) out of this stickman history video
to make people want to watch the full video "{video_title}".

SCRIPT (beat index, scene length in seconds, narration):
{beats}

Return:
- start, end: the first and last beat index of ONE continuous run of beats that works on its own as a Short.
  It must open with a hook (a surprising claim, a question or a funny moment), make sense without the rest of the
  video, and the scene lengths from start to end must add up to between 25 and 55 seconds.
- title: the Short's on-screen title, max 40 characters, punchy, no emojis.
- script: a standalone narration for an AI-made version of this Short, 90 to 150 words, same facts and jokes,
  ending with a short nudge to watch the full video on the channel.
- description: one or two sentences for the Short's description.
- hashtags: 3 hashtags, the first one "#shorts".
Plain spoken English, no em dashes, no AI filler words. Answer with JSON only."""
