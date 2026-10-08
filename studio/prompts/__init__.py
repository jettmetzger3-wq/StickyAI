"""All LLM prompts in one place. The scene-language reference is generated from the engine's registries so
the docs the LLM sees always match what the renderer can draw."""
import json
import os

from ..engine.pen import ARMS, LEGS, MOUTHS, EYES, EXTRAS, HELD, HATS, KIND_ALIASES
from ..engine.registry import PROPS, ICONABLE, PROP_GROUPS, ANIMATED
from ..engine.pen import MOUNTS
from ..engine.places import SKYLINES, STREET_STYLES
from ..engine.geo import REGIONS
from ..engine.schema import ENTERS, IDLES, BG_TYPES
from ..engine.puppet import ACTIONS
from ..engine.weather import WEATHERS, LIGHTS
from ..engine.action_fx import PROP_ACTS

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
            "properties": {"mood": {"type": "string", "enum": ["fun", "tense", "somber"]}, "text": {"type": "string"},
                           "part": {"type": "string", "enum": ["hook", "intro", "story", "payoff"]},
                           "purpose": {"type": "string"}, "location": {"type": "string"}, "visual": {"type": "string"},
                           "claims": {"type": "array", "items": {"type": "string"}}}}},
        "facts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["beat", "claim", "confidence", "note"],
            "properties": {"beat": {"type": "integer"}, "claim": {"type": "string"},
                           "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                           "note": {"type": "string"}}}},
        "cast": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name", "kind", "hat_color", "coat", "look"],
            "properties": {"name": {"type": "string"}, "kind": {"type": "string"}, "hat_color": {"type": "string"},
                           "coat": {"type": "string"}, "look": {"type": "string", "enum": ["", "beard", "mustache"]},
                           "role": {"type": "string"}}}},
    },
}

WRITING_RULES = """STRUCTURE (every beat gets a "part")
1. HOOK ("hook", exactly one beat, under 15 words): the most surprising thing in the whole story, as a statement or
   a question the video will answer.
2. [The channel's host stickman says hello right after the hook ("Hey, it's the host! Today we're talking about
   <the title>."). Do NOT write that greeting.]
3. INTRO ("intro", 2 to 4 beats, about 20 to 40 seconds): the viewer arrives knowing nothing, so say plainly what the
   topic IS or WAS in the first intro beat (start with it: "So what was the Cold War?" / "So what even is a
   mortgage?"): what it was, who was involved, when and where, and why it still matters. Then tell them how this
   video will go ("First we'll see how it started, then the three moments it almost went wrong, and how it ended").
   Anyone who has never heard of the topic should be able to follow everything after this.
4. STORY ("story"): the main part, told in order or in clear chapters.
5. PAYOFF ("payoff", the last 1 or 2 beats): land the story and echo the opening hook in a new light. Do NOT write
   a subscribe or "thanks for watching" line and no recap of the video: the studio adds the like and subscribe
   ending by itself.

WRITING RULES
- Output a list of BEATS. Each beat = one or two spoken sentences, roughly 15 to 30 words, plus a mood:
  "fun" (default, jokes allowed), "tense" (stakes rising, lighter jokes), "somber" (tragedy: no jokes).
- Open 2 to 4 story loops ("remember the oil problem?" style) and close every one of them later with a callback.
- Every 5 to 8 beats end a section on a specific mini-cliffhanger (what is about to go wrong, not a vague
  "but that was only the beginning").
- Change the pattern every 30 to 90 seconds (a map, a "meanwhile", a quick list, a fake quote, a rhetorical question).
- Anchor beats to concrete dates, people, places and numbers, and compare big numbers to things people know
  ("an army the size of Philadelphia", "a country smaller than California").
- Write for the eye: every beat should be drawable as one doodle scene. Name the places, objects and events
  (a map, an invasion, a ship sinking, a storm, a coronation, prices rising) so the animator can show them.
- Give the main people a personality and a running joke, and let them react in character.
- Spoken style: contractions, short sentences, plain words. Funny but respectful.
- Never use these AI-sounding words/phrases: {avoid}. Never use the "It's not X, it's Y" construction.
  Never use em dashes or en dashes; use commas, periods or "and".
- Sensitive history (massacres, bombings, genocide, slavery, famine): switch those beats to "somber", no jokes,
  respectful wording, and casualty numbers that sit inside mainstream historian ranges ("historians estimate...").
- Write numbers as digits for years ("1941") and words or digits for amounts; the voice handles both.

FLOW (the video must feel like ONE story, never a list of facts)
- Hand off every beat: the next beat starts from where the last one ended. If a beat ends on a question, the next
  one answers it. If it ends on a person, object, place or number, the next one picks that up in its first words
  ("That pile of gold?", "Ferdinand, meanwhile, had other plans.").
- Chain with cause and effect: read each pair of neighbouring beats with "so" or "but" between them. If neither
  fits, the pair is a jump, so add the missing step or a bridge.
- Bridge every change of place, time or person with a clause that says so: "Three years later, in Moscow...", "To
  see why, rewind to 1945.", "Meanwhile, back at the palace...". Years between beats never jump by more than a
  decade or two without saying how much time passed.
- Never introduce a new name, place or term without one short phrase saying who or what it is ("Khrushchev, the
  Soviet leader with a famous temper"). Don't mention something the viewer was never told about.
- Close every section by naming what happens next or what is at stake, and open the next section by answering it.
- No "and then" chains and no beat that could be moved elsewhere without anyone noticing.

STORY SHAPE AND THE PICTURE (every beat also carries four short notes for the animator)
- Tell it as Context -> Event -> Consequence -> Next event. Each beat answers: what is happening, who is involved,
  where, why it matters, and what changes because of it. Cut any fact that has no job in the story.
- "purpose": what this beat does for the story, max 10 words ("explain why the colonies grew apart").
- "location": where it happens, max 6 words, specific ("Boston Harbor", "Atlantic coast of North America", "Independence Hall, Philadelphia").
- "visual": what the viewer should SEE, max 16 words, described by what the sentence MEANS and not by its keywords
  ("a map of the 13 colonies along the Atlantic coast, England far across the ocean"; "delegates writing the Constitution in a hot room").
- "claims": the ids of the research facts (the [c...] ids in the RESEARCH block, if there is one) this beat uses.
- One beat can carry two or three related sentences when they make one picture; do not split a single idea into several beats.

FACT LIST
- Alongside the script, list EVERY date, number and factual claim as a checklist item with the beat index it
  appears in (0-based), your confidence ("high" | "medium" | "low") and a short note (why uncertain, or the
  common alternative figure). Be honest: mark anything debated or approximate as "medium" or "low".

CAST
- List the recurring characters (nations, people, groups). For each pick a stickman "kind" (hat) from this list:
  {kinds}
  (aliases also work: {aliases}). Optionally give a hat_color (a color name or #hex) to tell similar hats apart,
  otherwise use "". Give people and armies a coat (jacket color: "#C8302B" British red, "#2B3F8C" French blue,
  "#2F5D3A" Russian green, a king's purple, a banker's gray) or "" for plain stickmen, and a look: "beard",
  "mustache" or "". They keep this look in every scene, so pick what makes them recognizable.
"""


def target_beats(minutes):
    return max(6, int(round(float(minutes) * 8)))


def script_prompt(topic, minutes=10, tone="funny but respectful", style_notes="", source=None, faithfulness="balanced",
                  extra="", research=""):
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
    if research:
        parts.append(research)
    if extra:
        parts.append("EXTRA INSTRUCTIONS FROM THE USER: " + extra)
    parts.append(rules)
    parts.append('Answer with JSON only: {"title": working title, "topic": short topic, "beats": [{"mood", "text", "part"}], '
                 '"facts": [{"beat", "claim", "confidence", "note"}], "cast": [{"name", "kind", "hat_color", "coat", "look"}]}')
    return "\n\n".join(parts)


def regen_beat_prompt(beats, index, instruction=""):
    ctx = []
    for i in range(max(0, index - 3), min(len(beats), index + 4)):
        mark = ">>>" if i == index else "   "
        ctx.append(f"{mark} [{i}] ({beats[i]['mood']}) {beats[i]['text']}")
    return ("Rewrite ONLY the beat marked >>> so it flows with its neighbours: it picks up the last idea of the beat "
            "before it and hands off to the next one, with a bridge for any jump in place or time. Keep it 15-30 words, spoken style, "
            "accurate, no em dashes, no AI filler words. " + (f"User request: {instruction}. " if instruction else "") +
            "\n\n" + "\n".join(ctx) +
            '\n\nAnswer with JSON only: {"mood": "fun|tense|somber", "text": "..."}')


SMOOTH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["rewrites"],
    "properties": {"rewrites": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["beat", "text"],
        "properties": {"beat": {"type": "integer"}, "text": {"type": "string"}}}}},
}


def smooth_prompt(script, seams):
    """Ask for new wording for the beats that need it. `seams` = [(beat index, why)]: a beat that doesn't connect to the
    one before it, or a quality problem (flat opening, trailing ending, repeated phrase, machine-sounding word, too long)."""
    beats = script.get("beats") or []
    want = {i for i, _ in seams}
    show = sorted({j for i in want for j in (i - 2, i - 1, i, i + 1) if 0 <= j < len(beats)})
    lines, last = [], None
    for j in show:
        if last is not None and j != last + 1:
            lines.append("   ...")
        tag = ">>>" if j in want else "   "
        lines.append(f"{tag} [{j}] {beats[j]['text']}")
        last = j
    why = "\n".join(f"- beat {i}: {w}" for i, w in seams)
    return f"""Here is part of a narration script for the video "{script.get('title', '')}". The beats marked >>> have the
problems listed below (they don't connect to the beat before them, or they read badly).

{chr(10).join(lines)}

WHAT'S WRONG
{why}

Rewrite ONLY the >>> beats and fix exactly what is listed. To connect: pick up the last idea, name or question of the beat
before in the first words, use a clear cause-and-effect link ("so", "but", "which meant") or a short bridge for a change of
place or time ("Three years later, in Moscow..."), and say who or what any new name is in a few words. A flat opening
becomes a hook in its first six words (a surprising fact, a bold claim or a question: no greeting, no "in this video"). A
trailing ending lands on a clear payoff or punchline. A repeated phrase or a machine-sounding word gets fresh, plain
wording. A beat that is too long is tightened to one idea. Keep every date, number and fact exactly as it is, keep the
voice and the jokes, keep it spoken (15 to 30 words, never more than 35), no em dashes, no AI filler words. Don't touch
beats that aren't marked.

Answer with JSON only: {{"rewrites": [{{"beat": n, "text": "..."}}]}}"""


REGEN_BEAT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["mood", "text"],
                     "properties": {"mood": {"type": "string", "enum": ["fun", "tense", "somber"]},
                                    "text": {"type": "string"}}}


# ------------------------------------------------------------------ fact-check
FACTCHECK_SYSTEM = ("You are a careful history fact-checker for an educational YouTube channel. You verify claims "
                    "against reliable sources, you say when something is debated, and you never invent sources. "
                    "You always answer with JSON only.")

FACTCHECK_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["checks", "rewrites"],
    "properties": {
        "checks": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["fact", "beat", "claim", "verdict", "correction", "source"],
            "properties": {"fact": {"type": "integer"}, "beat": {"type": "integer"}, "claim": {"type": "string"},
                           "verdict": {"type": "string", "enum": ["correct", "wrong", "unsure"]},
                           "correction": {"type": "string"}, "source": {"type": "string"}}}},
        "rewrites": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["beat", "text"],
            "properties": {"beat": {"type": "integer"}, "text": {"type": "string"}}}},
    },
}


def factcheck_prompt(script, web=False, items=None):
    beats = "\n".join(f"[{i}] {b['text']}" for i, b in enumerate(script.get("beats") or []))
    facts = "\n".join(f"#{i} (beat {f.get('beat')}, {f.get('confidence', '?')}): {f.get('claim')}"
                      + (f" -- writer's note: {f['note']}" if f.get("note") else "")
                      for i, f in enumerate(script.get("facts") or []))
    how = ("Use web search to check them: prefer encyclopedias, museums, universities and well-known history "
           "references; name the source you used in a few words.") if web else \
        ("You can't browse the web here, so check them against what you know; if you are not confident, say "
         "\"unsure\" rather than guessing, and use the source field for what the mainstream view is.")
    only = ""
    if items:
        only = ("\nThe studio already verified everything else against sourced research. Check ONLY these items that the "
                "research does not mention (beat: item):\n" + "\n".join(f"- beat {x['beat']}: {x['kind']} {x['item']}" for x in items[:30]) + "\n")
    return f"""Fact-check this narration script for a history video titled "{script.get('title', '')}".{only}

SCRIPT (beat number in brackets):
{beats}

FACT LIST from the writer (index, beat, the writer's own confidence):
{facts or "(none listed)"}

Check every fact marked medium or low, every number of deaths or casualties, and any other claim in the script
that looks wrong or exaggerated to you (at most 25 checks; skip the obviously true ones). {how}

For each check give: fact (its # index from the list, or -1 if it's not in the list), beat, claim, verdict
("correct", "wrong" or "unsure"), correction (the right fact, or the accepted range if historians disagree; empty if
correct), source (a few words).

For every beat that contains something WRONG, add a rewrite: the whole beat rewritten with the fact corrected, same
length, same voice and jokes, spoken style, no em dashes. Don't rewrite beats that are fine or only "unsure".

Answer with JSON only: {{"checks": [...], "rewrites": [{{"beat": n, "text": "..."}}]}}"""


# ------------------------------------------------------------------ storyboard
STORYBOARD_SYSTEM = ("You are the storyboard artist of a funny stickman history YouTube channel. You turn each "
                     "narration beat into ONE doodle scene described in a small JSON scene language. You never write "
                     "code, only JSON.")


def props_doc(compact=False):
    out = []
    if compact:
        return "\n".join(f"  {label}: {', '.join(names)}" for label, names in PROP_GROUPS)
    for label, names in PROP_GROUPS:
        out.append(f"  {label}:")
        for n in names:
            a, _, d = PROPS[n]
            out.append(f"    - {n}{' (center)' if a == 'center' else ''}: {d}")
    return "\n".join(out)


def scene_language(compact=False):
    props = props_doc(compact)
    regions = ", ".join(sorted(REGIONS))
    return f"""SCENE LANGUAGE (1920x1080 frame, x to the right, y down. Bottom 180 px (y > 900) is reserved for captions:
never put text there. Characters' feet may stand at y 860-930.)

A scene is: {{"bg": {{...}}, "elements": [...], "camera": {{...}}}}

BACKGROUNDS ("bg"): type is one of {", ".join(BG_TYPES)}.
  paper {{color}} | sunburst {{color, ray}} | ground {{sky, ground, y: horizon y (default 860)}} |
  painted places (sky gradient, scenery; add "time": day|dawn|dusk|night|storm):
    field (grass, a tree line: armies, farms, speeches) | hills | desert | snow |
    city {{skyline?}} (a skyline; skyline adds the city's landmarks: {", ".join(sorted(SKYLINES))}) |
    street {{style: {"|".join(STREET_STYLES)}}} (a town street with houses, shops, cobbles; western = saloons) |
    palace (grand hall: columns, curtains, chandelier, checkered marble: kings, courts, treaties, balls) |
    harbor (quay, moored sailing ships: ports, trade, navies, explorers leaving) | beach (sand, palms, waves) |
    underwater (light rays, seaweed, fish: submarines, shipwrecks, sea life) | space (stars, Earth, moon) |
    jungle | mountains (snowy peaks, pines: Alps, Himalayas, crossings) | trench (WW1 trench, sandbags, wire) |
    battlefield {{style: river|open|ruins}} (a real battlefield: village, church tower, river and wooden bridge,
      trampled ground, craters, black smoke rising; ruins = WW1/WW2 shell holes and wire) |
    interior {{wall, floor}} (rooms, offices, small halls) |
  PLACES WHERE THINGS HAPPEN (full backgrounds with moving parts; add "time" for outdoor ones):
    construction {{what: factory|house|tower|castle|wall|ship, progress: [from, to] (0-1, how built it is at the
      start and end of the scene; default [0.3, 0.85]) | "done"}} (a construction site: the frame stands, a tower
      crane lowers steel, workers hammer on scaffolding and the walls rise WHILE the scene plays; ship = shipyard) |
    factory {{style: outside|inside}} (outside: brick halls, chimneys pouring smoke, a railway with wagons;
      inside: a running conveyor belt with crates, turning gears, a stamping press) |
    farm (wheat field, plowed field, barn, silo, haystacks, windmill) | mine (timbered tunnel, rails into the dark,
    an ore cart, lanterns) | classroom (blackboard, teacher's desk, globe) | lab (flasks bubbling, shelves of jars,
    microscope) | parliament (tiers of benches full of members, the Speaker's chair) | courtroom (judge's bench,
    witness stand, jury) | prison (a cell: stone walls, barred window, bunk, tally marks, bars) |
    market {{style: {"|".join(STREET_STYLES)}}} (stalls with striped awnings and goods, bunting) |
    camp (army tents, the general's striped tent, stacked muskets, a crackling campfire)
  THE PLACE IS THE BACKGROUND: when the narration says where something happens or what someone does ("he built a
    factory", "they fought at Austerlitz", "she was thrown in prison", "peasants farmed", "parliament debated"),
    use that place as the full bg. Never show it as a small prop on a plain page.
  sea {{sky, sea, horizon (default 520)}} | night | dark {{color}} (use for somber beats) |
  map {{center: [lon, lat], width: degrees of longitude across the frame (Europe ~40, a country ~15-25, Pacific ~110),
       territories: [{{countries: [...] | region: preset, color, clip?: [[lon,lat],...], box?: [lon0,lat0,lon1,lat1]}}],
       labels: [{{text, lon, lat, size}}], style: "paper" (light doodle map) | "dark" (navy sea, dark land, white
       borders: dramatic, like big history channels; use bright territory colors on it)}}
       (Mercator; keep everything you mention inside the view)
  Any bg can have "items": static props/shapes drawn into the background (no animation).

ELEMENTS (all screen positions are x,y pixels; on map scenes you may use lon/lat instead):
  char:  a stickman. {{x, y = point between the feet, scale (0.4 small .. 1.6 giant; 1.0 = 375 px tall), kind (hat),
         hat_color?, pose, legs, mouth, eyes, extras[], prop (held item), prop_color?, flip (face left), look (-1|0|1)}}
         kind: {", ".join(h for h in HATS if h != "none")}
         pose: {", ".join(ARMS)}
         legs: {", ".join(LEGS)}
         mouth: {", ".join(MOUTHS)}    eyes: {", ".join(EYES)}
         extras: {", ".join(EXTRAS)} ("q" = question mark)   prop: {", ".join(HELD)}
         coat: a jacket color, so people and armies are recognizable (British redcoats "#C8302B", French blue
         "#2B3F8C", Russian green "#2F5D3A", Prussian "#1F2A44", Union blue "#30407A", Confederate gray "#8A8C8E",
         a king's purple, a businessman's gray suit). Uniform hats (shako, bearskin, tricorn) add white crossbelts,
         officers' hats (bicorne, crown, navy) add gold epaulettes. pose "hand_in_coat" = Napoleon's pose.
         ride: {"|".join(MOUNTS)} (the character sits on it; walk/run then gallops; flip faces left)
         who: the cast member this is ("Napoleon"): they get their cast hat, coat and beard automatically.
         say: what the character SAYS, as a list of 1-3 short lines (max ~8 words each), shown one after another in
         speech bubbles over their head while they talk: ["Soldiers! Glory awaits!", {{"text": "CHARGE!",
         "at": "word:attacked"}}]. The engine positions the bubbles and points the tails; no need for bubble elements.
         Characters are ALIVE on their own (breathing, blinking, glancing around) and talk automatically while
         they have something to say. Make them ACT with "do": a list of actions, each
         {{act, at ("word:..." or 0-1), dur (seconds, optional)}}:
           {", ".join(sorted(ACTIONS))}
           walk/run/sneak also take "to": [x, y] (or dx); "offscreen": true lets them leave the frame.
           e.g. "do": [{{"act": "walk", "to": [1200, 900], "at": "word:marched"}}, {{"act": "cheer", "at": "word:won"}}]
  crowd: rows of the same character with depth, all alive {{kind, count (2-40), rows (1-4), x, y (front row feet),
         width (px), scale (0.4-0.9), pose, mouth, eyes, flip, coat, ride (cavalry!), do: [...], say: [...] (the crowd
         shouts back)}} (armies, mobs, voters, workers)
  text:  {{text, x, y (center), size (40-120), color, font: "bold" (Fredoka) | "hand" (handwritten), align}}
  prop:  {{name, x, y, scale, color?, params?}}. Props stand on x,y (bottom-center) unless marked (center), then x,y is
         their middle. Scale 1 is roughly life-size next to a scale-1 stickman for objects, and about 1.5-2x a
         person for buildings and landmarks. Props flagged with "params: flip" face left with params {{"flip": true}}.
         Available props (detailed doodles, pick the most specific one):
{props}
         Plus any CUSTOM PROPS listed for this video below (use them by name like library props).
         These props move on their own (no need to animate them): {", ".join(sorted(ANIMATED))}.
  bubble: a free-standing speech/thought bubble {{text ("\\n" for new line), x, y (center), size, tail:
         "left"|"right"|"down"|"none", font}} (prefer a character's "say"; use bubble for narrator asides)
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
         (it draws itself from start to end). Armies on the move: add units: a hat kind ("shako", "army",
         "roman"...) for little soldiers marching along it, or a prop ("tank", "ship", "horse", "galleon"...),
         count (soldiers 1-8), unit_color (their coats), march (seconds to reach the end).
  battle: crossed swords on a burst, with a boom {{x, y or lon, lat, label ("Waterloo"), size}}
  front: a front line with little teeth on the side that is attacking {{points: [...] or keys: [{{at, points}}, ...]
         (the line moves smoothly from one shape to the next: a front advancing, a border shifting), color, side:
         "left"|"right" (relative to the direction of the points), width}}
  counter: a number that counts {{from, to, x, y, size, at, until (or dur seconds), prefix ("$"), suffix (" troops"),
         format: "year"|"number"}} (years ticking by 1939 -> 1945, armies growing, money, deaths in somber beats)
  pointer: a big bobbing arrow pointing AT a spot {{x, y or lon, lat (the tip), from: n|ne|e|se|s|sw|w|nw
         (where the arrow comes from), size, color}} (a front line, a city, a tiny detail)
  empire (maps): borders that change over the years {{name, color, steps: [{{at, year, countries: [...] | region}},
         ...] (2-5 steps)}}: each step spreads out from the old heartland and the year ticks in a corner
         (negative years = BC). Use it whenever a state grows or shrinks over time (Rome, the Mongols, Napoleon).
  city: add "capital": true for a star marker with a ripple (a nation's capital, an emperor's seat).
  route: a path that draws itself {{points: [...] or from/to, curve, color, style: dashed|dotted|solid, icon: a prop
         ("ship", "galleon", "camel", "horse", "train", "carrier"...) or a hat kind for a walker, dur (seconds)}}
         (trade routes like the Silk Road, voyages, migrations, a leader's journey, an escape).
  chart: an animated chart {{style: bar | hbar (ranking) | line, title, data: [{{label, value, color?}}] (2-8 rows),
         prefix ("$"), suffix (" km²"), decimals, x, y (center), w, h}}: bars grow and numbers tick up, a line draws
         itself. Use real numbers from the narration (armies, money, population, prices).
  timeline: years on a line {{events: [{{year, label, at}}] (2-6), y (default 640)}}: markers drop in as the
         narrator says them and a marker travels along.
  compare: 2-4 things as circles whose AREA matches their numbers {{items: [{{label, value, color, icon (a prop)}}],
         prefix, suffix}} (army sizes, populations, before/after).
  split: then vs now, a divider down the middle {{left: "1850", right: "TODAY", tint: left|right|none (that side
         turns old-photo sepia)}}; put the "then" things on the left half and the "now" things on the right.

  Natural Earth country names (common ones): "United States of America", "United Kingdom", "Russia", "China",
  "Japan", "France", "Germany", "Italy", "Spain", "Egypt", "India", "Korea" (both Koreas), "Turkey", "Iran", ...
  Region presets: {regions}

ANIMATION (any element): enter: {", ".join(ENTERS)} (default pop); at: when it appears, a fraction 0-1 of the
  scene or "word:Britain" to pop in exactly when the narrator says that word (best!); delay (seconds after "at");
  idle: {", ".join(IDLES)} (chars default to bob); exit: fraction or "word:xxx" to fade out;
  move: {{dx, dy, from, to}} (from/to like "at"); z: layer order (higher = in front).
TRANSITION (optional, top level): "transition": auto (default) | cut | slide | wipe | zoom | iris | paper | fade,
  how this scene replaces the one before. Leave it out; auto cuts between map shots and same-place scenes and fades
  around sad beats. Use "cut" for rapid-fire jokes, "zoom" to dive into a detail, "iris" for a reveal.
WEATHER AND LIGHT (optional, top level, outdoor places and maps):
  "weather": {", ".join(WEATHERS)} or {{type, amount (0.3-2), wind (-2..2), at, until}}: falling snow (Russia 1812),
  a blizzard, rain, a storm with lightning and thunder, drifting fog, ash and embers over a burning city.
  Night places get twinkling stars by themselves.
  "light": {{to: {"|".join(LIGHTS)}, at, dur (seconds)}}: the light changes during the scene (night falls, a dusk,
  the room goes dark when the bad news lands).
ACTION MOMENTS: props can DO something at a moment: "do": [{{act: {"|".join(PROP_ACTS)}, at, dur, target}}].
  fire = a cannon / tank recoils with a flash and smoke, a ship fires a broadside; with "target": [x, y] or
  {{lon, lat}} a cannonball flies there and explodes. explode = it blows apart in a fireball. collapse = a wall,
  tower, castle or building crumbles into dust and rubble. sink = a ship tilts and goes under. shake = it trembles.
  The "explosion" prop bursts in by itself. Sword fights: two characters with prop "sword", facing each other
  ~300 px apart, both with "do": [{{"act": "slash", "at": ..., "dur": 2}}] (sparks fly when the blades meet).
CAMERA: {{zoom: [start, end] (1.0-1.12, a slow push-in like [1.0, 1.05]), center: [x, y], to: [x, y],
  shots: [{{at, zoom (1.0-2.2), focus: [x, y] or {{lon, lat}}, region: a country or region preset (the camera
  frames it), move: cut|pan|whip}}]}}
  Two map scenes in a row where the second is a closer view of a place on the first (smaller width, center inside
  the first) zoom into it automatically, like Google Earth; a wider one zooms out.
  shots make a scene feel edited: start wide, then cut to a close-up of a face (zoom 1.6-2) when the joke lands,
  pan across a map to the next place, whip (fast blurred pan) to something surprising. Every shot slowly pushes in.
  Land the close-up EXACTLY on the punchline or reveal word ("at": "word:furious"), and cut back wide after.
  Without shots the camera does it for you: characters' faces react on words like "suddenly" (shocked),
  "betrayed" (furious), "won" (smug), "lost" (crushed), and the camera cuts in on the last such face; painted places
  get a slow sideways pan. Set "react": false on a character (or the scene) to keep its face as you wrote it.

COLORS: ink, red, darkred, navy, blue, lightblue, green, darkgreen, olive, gray, dgray, orange, yellow, gold, brown,
  white, purple, pink, teal, cream, maroon, khaki, silver, black, paper, sea, land, or "#rrggbb".

STYLE RULES
- One clear idea per scene. 3 to 8 elements. Big readable labels (size 50-110). Leave breathing room.
- Put the story in its world: Napoleon gets Paris streets, palaces, battlefields, muskets and cannons; pirates get
  harbors, beaches, underwater shots and treasure; Rome gets the Colosseum skyline and chariots. Use the VISUAL KIT
  and specific props (eiffel_tower, galleon, guillotine...) instead of generic ones.
- DIALOGUE: characters talk a lot. Whenever the narration says someone said, ordered, promised, warned, asked,
  boasted, refused, declared, rallied or motivated people, or reacts to news, give that character "say" lines in
  their own voice (funny, short, in character: Napoleon rallying his men says "Soldiers! Glory awaits!", his army
  answers "Vive l'Empereur!"). Two characters can trade lines (each with its own "at"). Aim for a speaking character
  in at least half the scenes that have characters. Never just repeat the narration word for word.
- Characters ARE the nations/people (use the cast). Size shows power (big = strong, small = weak).
- Make the joke visual: exaggerated faces, a bubble with a funny one-liner, a sticky note callback, a sign.
- Time the reveals to the narration with "word:..." so things pop in as they are said.
- Vary backgrounds and layouts from scene to scene; use maps whenever geography matters. Don't use the same
  background twice in a row: switch between maps, painted places (field, city, interior...) and plain ones.
- Keep things moving: give the main character at least one action ("do"), use 1-3 camera shots in scenes longer
  than ~5 seconds, and on maps let arrows draw, pointers bob and the camera travel.
- Make people recognizable: armies and officials wear coat colors that match their side, leaders ride horses on
  battlefields, a king has his crown and a purple or red coat; the same person keeps the same look all video.
- War maps should feel alive: troops march along invasion arrows (units), battles get a battle marker, fronts and
  borders move with keys, and a counter ticks the year or the size of an army. Empires that grow or shrink get an
  "empire" with dated steps; journeys and trade get a "route" with a ship or caravan.
- Show the big moments happening: cannons fire, ships sink, walls collapse, things explode, swords clash. Put the
  weather in when the narration mentions it (snow, rain, a storm, fog, a city burning) and let night fall.
- Numbers deserve a picture: a chart for money/armies/prices, compare for "X was ten times bigger than Y", a
  timeline when the narration lists several dates, split for then vs now.
- Somber beats: bg "dark", "paper" or a dusk/storm place, fade entrances, no jokes, no grins, no explosions as gags,
  candles are fine; slow actions only (bow, cry, look, walk); any "say" lines are quiet and respectful; gentle snow,
  rain or "light": "dusk" suit them.
- Keep every element fully inside the frame; text never below y=880.
"""


def scene_language_compact():
    """The same language in about a third of the words, for free writers with small per-minute limits."""
    return f"""SCENE LANGUAGE (1920x1080, x right, y down; y > 900 is for captions: no text there; feet at y 860-930)
A scene: {{"bg": {{...}}, "elements": [...], "camera": {{...}}, "weather"?, "light"?, "transition"?}}

BG types: {", ".join(BG_TYPES)}. Painted places take "time": day|dawn|dusk|night|storm.
THE PLACE IS THE BACKGROUND: "he built a factory" = bg construction {{what: factory}} (walls rise during the scene),
a battle = battlefield, a trial = courtroom, jail = prison, farming = farm. Never a small prop on a plain page.
construction {{what: factory|house|tower|castle|wall|ship, progress: [0.3, 0.85] | "done"}}. factory {{style: outside|inside}}.
battlefield {{style: river|open|ruins}}. market {{style: like street}}. city {{skyline: one of
{", ".join(sorted(SKYLINES))}}}. street {{style: {"|".join(STREET_STYLES)}}}. map {{center: [lon, lat], width (degrees across:
Europe 40, a country 15-25), style: paper|dark, territories: [{{countries: [...] | region, color}}], labels: [{{text, lon,
lat, size}}]}}. dark {{color}} for sad beats. Region presets: {", ".join(sorted(REGIONS))}.

ELEMENTS (x, y pixels; on maps lon/lat or {{"lon", "lat"}} points):
  char {{x, y (feet), scale (0.4-1.6), who (cast name), kind (hat), pose, mouth, eyes, prop, coat, ride (horse...),
       flip, say: ["short line", {{"text": "...", "at": "word:x"}}], do: [{{act, at, to?}}]}}
       kind: {", ".join(h for h in HATS if h != "none")}
       pose: {", ".join(ARMS)} | mouth: {", ".join(MOUTHS)} | eyes: {", ".join(EYES)} | prop: {", ".join(HELD)}
       act: {", ".join(sorted(ACTIONS))} (walk/run take "to": [x, y]; "slash" = sword fight)
  crowd {{kind, count (2-40), rows, x, y, width, scale, coat, ride, do, say}}
  text {{text, x, y, size (40-120), color, font: bold|hand}} | bubble {{text, x, y, tail}} | note | sign | board {{title, lines}}
  prop {{name, x, y (bottom-center), scale, color, params, do: [{{act: {"|".join(PROP_ACTS)}, at, target}}]}}
  icons {{icon, count, per_row, x, y}} | shape {{shape: rect|circle|ellipse|line|poly, ...}} | group {{items}}
  maps: territory {{countries | region, color}}, city {{name, lon, lat, capital}}, arrow {{from, to | points, curve,
       color, units (hat kind or prop: little soldiers / tanks march along), count}}, battle {{lon, lat, label}},
       front {{keys: [{{at, points}}], color, side}}, empire {{name, color, steps: [{{at, year, countries | region}}]}},
       route {{points | from, to, icon (ship, camel, horse...), style: dashed|dotted|solid}}, pointer {{lon, lat, from}}
  counter {{from, to, x, y, size, format: year|number, prefix, suffix}}
  chart {{style: bar|hbar|line, title, data: [{{label, value}}], prefix, suffix}} | timeline {{events: [{{year, label, at}}]}}
  compare {{items: [{{label, value, icon}}]}} | split {{left: "1850", right: "TODAY", tint: left}}
Props: names below (pick the most specific):
{props_doc(True)}
ANIMATION (any element): enter: {", ".join(ENTERS)}; at: 0-1 or "word:X" (pops in when the narrator says X: best);
  exit; idle: {", ".join(IDLES)}; move {{dx, dy, from, to}}; z.
WEATHER: "weather": {"|".join(WEATHERS)}. LIGHT: "light": {{to: {"|".join(LIGHTS)}, at}}.
CAMERA: {{zoom: [1.0, 1.05], shots: [{{at, zoom (1-2.2), focus: [x, y] | {{lon, lat}}, region, move: cut|pan|whip}}]}}
  Close-ups land on the punchline word ("at": "word:X"). Faces react to "suddenly", "betrayed", "won", "lost" by
  themselves.
COLORS: red, darkred, navy, blue, green, darkgreen, olive, gray, orange, yellow, gold, brown, white, purple, black,
  "#rrggbb".
RULES: one idea per scene, 3-8 elements, big labels. Put the story in its world (places, specific props, coats).
Characters talk (say) whenever someone speaks or reacts. Time things to words with "word:...". Vary backgrounds.
Show big moments (fire, explode, collapse, sink, slash), weather the narration mentions, charts/timelines for numbers
and dates. Somber beats: dark or dusk, fades, no jokes. Everything inside the frame.
"""


def load_examples():
    with open(os.path.join(HERE, "examples.json"), encoding="utf-8") as f:
        return json.load(f)


# the most instructive examples first, for writers that only get a few
KEY_EXAMPLES = ("army_speech", "invasion_map", "factory_goes_up", "pirates_harbor", "broke_king", "paris_bread")


def examples_block(limit=20):
    ex = load_examples()
    if limit < len(ex):
        key = [e for n in KEY_EXAMPLES for e in ex if e["name"] == n]
        ex = (key + [e for e in ex if e not in key])[:limit]
    out = []
    for e in ex:
        out.append(f'BEAT ({e["mood"]}): {e["text"]}\nSCENE: ' + json.dumps(e["scene"], separators=(",", ":")))
    return "\n\n".join(out)


def custom_props_block(kit):
    if not kit:
        return ""
    lines = [f"- {d['name']}{' (center)' if d['anchor'] == 'center' else ''}: {d['desc']}" for d in kit]
    return "CUSTOM PROPS DRAWN FOR THIS VIDEO (use them by name as props, they look great):\n" + "\n".join(lines)


def storyboard_prompt(batch, all_beats, cast, title, visual_hints=None, kit_text="", custom=None, examples=20,
                      compact=False):
    """batch: list of (index, beat). visual_hints: {index: "what the source video showed around then"}.
    kit_text: the topic's VISUAL KIT block. custom: props designed for this video."""
    cast_lines = "\n".join(f"- {c.get('name')}: kind={c.get('kind')}" + (f", hat_color={c['hat_color']}" if c.get("hat_color") else "")
                           + (f", coat={c['coat']}" if c.get("coat") else "") + (f", {c['look']}" if c.get("look") else "")
                           for c in cast or [])
    first = batch[0][0]
    ctx = [f"[{i}] ({b['mood']}) {b['text']}" for i, b in enumerate(all_beats) if first - 2 <= i < first]
    beats = []
    for i, b in batch:
        line = f"[{i}] ({b['mood']}) {b['text']}"
        if visual_hints and visual_hints.get(i):
            line += f"\n     (source video showed: {visual_hints[i]})"
        beats.append(line)
    ex = f"EXAMPLES (beat -> scene):\n{examples_block(examples)}\n" if examples else ""
    return f"""{scene_language_compact() if compact else scene_language()}

{ex}

VIDEO: {title}
CAST (give a char "who": "<name>" and the studio dresses them the same in every scene; you may still change
their hat for a moment that calls for it, like a crown at a coronation):
{cast_lines or "- (pick sensible kinds)"}

{kit_text}

{custom_props_block(custom)}

Previous beats for context:
{chr(10).join(ctx) or "(start of video)"}

Make one scene for each of these beats:
{chr(10).join(beats)}

Answer with JSON only: {{"scenes": [{{"beat": <index>, "scene": {{"bg": ..., "elements": [...], "camera": ...}}}}, ...]}}"""


# ------------------------------------------------------------------ props designed for one video
PROP_DESIGN_SYSTEM = ("You design simple, bold doodle props for a stickman history cartoon, as lists of flat shapes "
                      "with dark outlines. You only answer with JSON.")


_PROP_SPEC = """Draw each one on a 100 x 100 grid (x to the right, y DOWN, 0,0 = top-left) as a list of shapes, back to front:
  {"shape": "rect", "x": left, "y": top, "w": width, "h": height, "fill": color, "r": corner radius (optional)}
  {"shape": "circle", "x": cx, "y": cy, "r": radius, "fill": color}
  {"shape": "ellipse", "x": cx, "y": cy, "rx": rx, "ry": ry, "fill": color}
  {"shape": "poly", "points": [[x, y], ...], "fill": color}           (3-24 points, closed)
  {"shape": "line", "points": [[x, y], ...], "color": color, "width": 1-6}   (open line)
  {"shape": "text", "text": "short", "x": cx, "y": cy, "size": 8-30, "color": color}
Every filled shape gets a dark outline automatically ("outline": false to skip it, good for highlights/shading).
Colors: names (red, navy, gold, brown, gray, white, black, green, darkgreen, cream, khaki, silver, ...) or "#rrggbb".
Style: bold and readable when small, 6-25 shapes, big shapes first, a few details (stripes, rivets, shading,
highlights), flat cartoon colors, no tiny text. Fill most of the grid. "anchor": "bottom" for things that stand on
the ground (rest them on y = 100), "center" for floating or held items.

Answer with JSON only: {"props": [{"name": "snake_case_name", "anchor": "bottom|center",
"description": "what it is, a few words", "parts": [...]}]}"""


def prop_design_prompt(title, topic, beats, kit_text="", wanted=None):
    """`wanted` = [(object, sentence it appears in)]: the objects the plan says must be seen and no library prop shows.
    With it the request is short (just those objects); without it the writer reads the whole story and chooses."""
    if wanted:
        lines = "\n".join(f'- {w}: "{str(ctx)[:140]}"' for w, ctx in wanted[:10])
        return f"""VIDEO: {title} ({topic})
Draw ONE prop for each object below, and nothing else (every other object is already in the library):
{lines}

{_PROP_SPEC}"""
    text = " ".join(b.get("text", "") for b in beats)[:9000]
    library = ", ".join(sorted(n for n in PROPS if n != "custom"))
    return f"""VIDEO: {title} ({topic})
NARRATION: {text}

{kit_text}

The animation library already has these props: {library}

Design 4 to 8 EXTRA props this specific story needs that the library does not have: the famous objects, symbols,
vehicles, weapons, food, documents, inventions and items that are named or important in the narration (for example
Napoleon's bicorne on a pillow, the Rosetta Stone, a Spitfire, the Declaration of Independence, a spinning jenny, a
Viking rune stone). Skip anything the library already covers well.

{_PROP_SPEC}"""


def fix_scenes_prompt(items):
    """ONE request for several scenes that still have problems. items = [(beat index, beat, scene, [problems])]."""
    blocks = []
    for i, beat, scene, problems in items:
        blocks.append(f"[{i}] ({beat['mood']}) {beat['text']}\nPROBLEMS: " + "; ".join(problems[:6])
                      + "\nSCENE: " + json.dumps(scene, separators=(",", ":"))[:3500])
    return f"""{scene_language_compact()}

These scenes were checked against their narration and still have problems. Fix each one (keep what is good, change what the
problems say, keep every element inside the frame).

{chr(10).join(blocks)}

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
                                     "image_prompt": {"type": "string"}, "prop": {"type": "string"}}},
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
- thumbnail: line1 (2-4 punchy words, the hook), line2 (1-3 words that raise a question or an emotion, like
  "BIG MISTAKE", "WHY?!", "IT FAILED"), small_kind (the small furious underdog's hat kind), big_kind (the giant smug
  one's kind), prop (one object that sums up the story, from the prop library: cannon, crown, galleon, explosion,
  moneybag, oil barrel...), image_prompt (a short scene description for an AI image background, no text in the
  image). Thumbnails are read at phone size: fewer words beat more words. Kinds come from:
  {", ".join(h for h in HATS if h != "none")}.
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
