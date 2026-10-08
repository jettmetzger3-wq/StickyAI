# Layout: how every scene is checked and repaired before it is rendered

Code: `studio/engine/layout.py`. Used by the storyboard review (`studio/pipeline/review.py`), by the render stage
(`stages.layout_prepare` / `layout_gate`), by the scene specs and preview page, and shown in the Storyboard tab.
Nothing in it calls an AI, and nothing shrinks text: it moves things.

## The idea in one paragraph

Every element gets a measured box (characters by head/hat/body, text by its real font, bubbles with their tail, icon grids,
arrows as real lines, group pieces) and a role (title, label, stat, bubble, character, crowd, important prop, scenery,
panel...). One function, `findings()`, lists every problem with a severity (high / medium / low) and a cost; the report,
the per-scene score and the repair all use that same list, so they cannot disagree. `fix_scene()` then lowers the cost in
stages and **never accepts a change that creates a new medium/high problem**.

## Your twelve requirements, and what answers each

| # | Requirement | What the code does |
|---|---|---|
| 1 | Collision prevention | text/text, bubble/text (a bubble over a title is always **high**), bubble tail/text, text/character (head and hat count more than the body), character/important prop (a head on a document is a problem), prop/prop, arrows and icon grids against text/people/props. Intentional overlaps are not flagged: text on a board/sign/panel, two lines of one card, a label naming its own prop, a stamp (check mark) on a document, scenery partly behind a crowd, things that are never on screen together (times are compared). |
| 2 | Safe margins | 64 px for text, 56 px for bubbles, 40 px for people, 28 px for important props, 40 px at the top; nothing readable in the bottom 180 px where captions are burned in; important props may not sit under the captions. Cut off by the frame = **high**. Decoration and the host's "peek in from the edge" may run off the frame. |
| 3 | Character sizing | a lone character: 0.5-1.5; a speaker: at least 0.7; a group of 3+ may be as small as 0.42; neighbours on the same ground may differ at most 1.6x (a main character stays the bigger one). Fixed by scaling, keeping the body inside the margins. |
| 4 | Visual hierarchy | a minor object more than 2.2x the area of the subject shrinks (landmarks and set pieces are exempt: they are the place); the subject may not be pushed to the edge of the picture. |
| 5 | Text placement | overlap, closeness (28 px of air), edges, minimum size (title 56, label 40, figure 60, bubble 40), text over an important object, text over a face. Repairs search free space around the text and prefer the position with the most clearance. |
| 6 | Speech bubbles | the tail must point at a speaker (character, crowd, or a prop that "talks"); a bubble never covers a face, a title, a figure, a board or a document; its tail never crosses another label or face; it sizes itself to its words; tails stay 24-170 px long; bubbles keep 56 px from the edge. A bubble that points at nobody is re-aimed at the nearest speaker only when one is near enough. |
| 7 | Empty space | flagged (low) when everything sits on one side or the scene is nearly empty; repaired by centring the whole group, and only when every element is a plain x-positioned one (an arrow or map element cannot be shifted blindly). |
| 8 | Scene-level pass | `fix_scene()` runs before rendering: tails, sizes, then moves in order bubbles/labels -> props -> characters, sizes again, centring, camera, automatic camera. It repeats until nothing more improves, so running it twice changes nothing. |
| 9 | Not an afterthought | the pattern library is laid out to pass without any repair (a test checks all 35 patterns); the repair is the safety net for custom and edited scenes. |
| 10 | Automatic correction before asking Claude | order: move the bubble, move the label, move the prop, move/resize the character, ease or drop the camera close-up, switch off the automatic close-up. Only a **high** problem left after all of that is `escalate`: Deep mode sends the scenes that still have open problems to the writer in one batched request (`ai_fix_open`); in the other modes the scene is listed in the Storyboard tab and blocked from rendering until redrawn or "Render anyway". |
| 11 | Consistency across scenes | `consistency()`: one title size and height for the whole video; the same person at the same size from scene to scene (leads are compared with leads, supporting parts with supporting parts). Scene layouts share conventions (banner at y=105, main 1.2-1.25, witness 0.85-0.9). |
| 12 | The paused-frame test | not a rule a program can ask; the layout score, the muted-video test and `previews/` (real frames) are what we check, and the demo is re-rendered and looked at after every layout change. |

## Where it runs

1. **Storyboard stage**: after each scene is built, `review.check_layout` repairs it; then the consistency pass; then a final
   audit gives `review.json -> layout` (`mean`, `per_beat`, `open`, `escalate`). The preview page and `specs/NNN.json` show the layout score.
2. **Render stage**: `layout_prepare` lays out every scene once more (a scene may have been edited by hand), saves the repair
   with the scene (so the render cache key matches what was checked), and `layout_gate` stops a scene with a high problem that
   moving things could not fix. Settings -> "Scenes with a layout problem that can't be fixed" (block / warn); per video
   "Render anyway (layout)".
3. **The host's cameo** (the mascot leaning in): dropped for that scene if it would land on a character, a bubble or a label.
4. **Automatic close-ups**: the engine adds some on its own; if one would cut a label or bubble in half, the scene's automatic
   camera is switched off.

## Tuning

All thresholds are constants at the top of `studio/engine/layout.py` (`MARGIN`, `GAP`, `MIN_SIZE`, `CHAR_*`, `SCALE_RATIO`).
After changing one: `python -m pytest -q tests/test_layout.py`, then `python scripts/demo/run_american_revolution.py` and
look at `previews/`. Numbers did not see an oversized ship, and the layout score will not see a bad idea either.

## What it does not do (said plainly)

* It measures what the scene JSON says. Parts of a **background** (painted benches, buildings, a window) are not elements, so a
  label can sit on a background face and the check will not know.
* Colour **contrast** is not checked (the engine already switches text to a light colour on dark backgrounds).
* Boxes for characters are rectangles; a stick figure is thin, so overlaps with a character body are weighed at 30% and only
  the head and hat count in full.
* "Is this interesting?" is not computed. Hierarchy is size, position and centre-ness, not meaning (meaning is `coverage`).
* Camera framing is checked for text and for the speaker's head, not for every possible shot of a very long scene.
* Cross-scene consistency covers titles and character scale, not every possible convention.
