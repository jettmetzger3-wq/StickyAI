# Stickman Studio 2.0: research, meaning and memory

This is the plan **and** the record of what was actually built. Every claim below points at code that exists; things that
are not built are in "What is still missing". Read `docs/architecture-upgrade.md` for the earlier (v1.5) work this builds on.

## The split of work

| Claude (the brain) decides | Local code (the studio) does |
|---|---|
| what is true: web research, claims with sources | caching, budgets, source ranking, claim <-> scene linking |
| the story: script, narrative purpose per beat | structure check, flow seams, evidence check |
| which pattern shows a beat and what must be SEEN (`needs`) | turning words into typed requirements, scoring coverage, composing the scene, patching gaps |
| odd scenes no pattern fits | validating/repairing scene JSON, world state, QC, muted test |
| titles/description text | all drawing, animation, voice, mixing, encoding |

Claude is called in **batches** (one research request, one script, one plan per ~16 beats). Nothing is called per frame,
per element or per retry of something deterministic.

## 1. Assessment of the project before this work (kept short)

Good and kept: the scene language + auto-repair (`studio/engine/schema.py`), the renderer, the 35-pattern library with the
local composer, the director plan, the character registry, continuity, caching, the usage ledger, modes, the cost gate.

Weak, and what was done:

| Weakness | Fix |
|---|---|
| Research was Deep-only, one unbudgeted request, claims had no sources | `studio/research/` engine (below) in Fast/Normal/Deep |
| The fact-check was always an extra AI call | evidence-first: only years/numbers/names the research does not mention go to it; **0 calls** when the sourced research covers the script |
| A scene could look right and say the wrong thing (a UK map for "the 13 colonies") | meaning layer + **coverage score** + render gate (below) |
| "Colonies" meant nothing without Claude writing the scene | curated `context.json` (regions, documents, events, synonyms) + typed `needs` from the director |
| No record of where/when each scene is | `world_state.json`, scene specs, time-jump checks |
| Looks written by the researcher ("red coat") were thrown away | `people.look_from_text`: hat + coat for people `people.json` does not know |
| A close-up could cut a label or bubble in half | camera crop rule, now part of the layout validator |
| A scene could be filled instead of composed (a bubble over a title, text on a face, a head on a document, a character half the size of its neighbour) | `studio/engine/layout.py`: one geometry model for the report and the repair, local repair in a fixed order that can never create a new problem, a render gate for what is left; see `docs/layout.md` |

Removed: nothing was deleted. The old "write every scene" path stays (`storyboard_engine: classic`) and is the "before"
column in the usage table. Replaced in behaviour: the Deep-only research brief, the unconditional fact-check call, and
"best keyword match wins" as the final pattern choice.

## 2. How web research works

`studio/research/engine.py: research_topic(...)`. Claude Code is allowed `WebSearch`/`WebFetch` for research calls
(`call_llm(..., web=True)`), so **no API key and no extra service** is needed.

1. **Look in the cache first** (`data/research_cache/<topic>/`: `research.md`, `sources.json`, `claims.json`,
   `metadata.json`, plus `brief.json`). "The American Revolution" and "the causes of the American Revolution" share one entry.
   If the saved research is *enough* (counted locally, `assess()`), the answer is **0 searches**.
2. **Only the gaps are researched.** A second pass names exactly what is missing ("11 more sourced claims", "an angle
   not covered: crisis") and says "do not repeat what is known".
3. **One budgeted request** per pass. The budget (`studio/research/budget.py`) is written into the request, checked on the
   way back, and recorded.
4. **Stop when the evidence is enough** (counts of sourced claims, independent sources, an official/archival source,
   timeline length, people). No searching "for the sake of it".
5. **If the budget is spent and holes remain, the run pauses and asks** (`ResearchBudgetReached` -> the project shows a
   "Research needs your OK" card with the gaps and a proposed extra budget). It never silently continues.

### Modes (visible on the New Video page before anything runs)

| Mode | Searches | Sources | Time | Evidence wanted |
|---|---|---|---|---|
| Fast | 4 | 6 | 120 s | 8 claims / 3 sources (Fast generation mode skips research entirely) |
| Normal | 10 | 15 | 300 s | 15 claims / 5 sources |
| Deep | 20 | 30 | 600 s | 28 claims / 9 sources |

Every number is a setting (`Settings > Research`, or per video). Defaults come from the generation mode.

### Permissions and limits (what is enforced and how, honestly)

* **Enforced by the prompt + validation, not by intercepting each search.** Claude Code runs the searches inside one
  request, so the studio cannot stop search number 11. It (a) tells Claude the limits, (b) drops sources over the limit
  and records `overrun`, (c) counts the searches Claude reports (`queries_used`), (d) repeats are counted as wasted.
* **No spending:** research uses your Claude plan like any other call; it is on the usage ledger and the estimate shows
  it before you click. Paid providers still go through `costs.py` approval.
* **Extra research needs your click:** `POST /api/projects/{slug}/research/approve`
  `{queries, sources, seconds}` (a grant is its own small budget) or `{use_what_we_have: true}`.
* If the writer cannot search the web, every claim is `unverified` with no URL; nothing is invented to fill the gap.

### Source quality and tracking

* `studio/research/sources.py` ranks by tier: archive / government / museum / academic / encyclopedia / reputable
  organisation / tertiary / avoid (blogs, SEO farms) / other. The tier **caps a claim's confidence** (a blog claim cannot be "high").
* Each claim: `claim, source, url, organization, date, evidence, confidence, tier, used_in_scenes`.
* `claims.link_scenes` links claims to beats by shared years/numbers/names (and tags the writer put on a beat).
* The final **used sources list** contains only sources behind claims some scene uses: `final/sources.md` and the
  video description.

## 3. Meaning layer: what the viewer must SEE

`studio/knowledge/semantics.py` + `context.json` (curated seed knowledge for the US founding era; everything else relies on
Claude's per-beat `needs`):

* `enrich` adds regions ("the 13 colonies" -> a highlighted map region), events (Boston Tea Party, Yorktown with a
  *surrender* variant), documents (Constitution -> Philadelphia, 1787, Madison, delegates), frames (colonization).
* `requirements` turns the beat (+ the plan's `needs`) into typed requirements: region, geo, place, person, group,
  document, event, number, time, action, object, each `must` or `should`.
* `coverage` scores a scene against them (must = 1, should = 0.5, synonyms count): **fail < 50%**, **block < 34%**.
* `studio/pipeline/coverage.py: choose` tries the plan's pattern, the semantic hint and the local best; if nothing passes
  it searches all patterns; then `patch` adds what a plain addition can (a person, a number, a date line).
* **Render gate** (`stages.coverage_gate`): scenes that do not show their narration block rendering with a plain
  message (Settings > `coverage_gate`: block/warn; per video `allow_low_coverage`).

## 4. Memory and continuity

* **World state** (`world_state.json`): place, region and year per scene; a jump in time or place must be explained.
* **Character memory** (`characters/<id>.json`, `characters.py`): one look per person for the whole video and, for
  people `people.json` knows, across videos. Looks the researcher describes become hat + coat.
* **Asset reuse** (`studio/pipeline/assets.py`): `find / missing / inventory`: props and looks that already exist are
  reused; missing ones are listed instead of silently replaced.
* **Scene specs** (`storyboard/specs/NNN.json`) hold narration, purpose, requirements, coverage, world, characters and
  the scene JSON the engine reads. `storyboard/preview.html` is a one-page contact sheet.

## 5. QC before the expensive part

`review.py` (local, auto-fixes): narration match, coverage, history (anachronistic props), continuity, characters, props,
action, camera (**close-ups never cut a label or speech bubble in half**), pacing, emotion, redundancy.
`muted.py`: the **muted-video test**: from the picture alone, can a viewer tell who / where / what / when / what changed?
Scores and weak scenes are in `review.json`. Per-scene repair: fixes are applied to the scene, and a single scene can be
re-composed or re-rendered (`POST /api/projects/{slug}/scenes/{i}/preview`, `stage_render(only=...)`).

**Determinism:** the render cache key is the scene JSON + `ENGINE_VERSION`; film grain is seeded; the same scene gives the
same pixels. `scripts/bench_render.py --check` proves it. `ENGINE_VERSION` stays 9 (new scene looks come from new
layouts, not from changed pixels).

## 6. Reference images

`studio/pipeline/reference.py`: a reference **image** is analysed once (vision JSON, cached by hash) into a *composition
blueprint* (layout, props, characters, camera), then converted **deterministically** into a scene using the studio's own
props. It reports what it reused, what it substituted and what is missing. It never copies the picture.
CLI: `python -m studio research reference add <image>`, `... reference convert <composition.json>`.

## 7. Claude usage, before and after

Measured by the estimator for a 10-minute video (`scripts/demo/run_american_revolution.py`, section 7). These are
**estimates**, not measurements of real Claude Code usage.

| Way | AI calls | Tokens | Level |
|---|---|---|---|
| v1: write every scene | 12 | ~201k | HIGH |
| v2 Normal | 12 | ~88k | MEDIUM |
| v2 Fast | 3 | ~19k | LOW |

The call count barely changes in Normal; the saving is **tokens** (~56%) and **repeats**: a second video on the same
topic skips the research call, a fact-check that finds everything sourced skips its call, and identical prompts come from the
cache. Rendering, animation, audio and video are local in every row.

## 8. How to run

* Website: `.\start.bat`, New Video: pick the generation mode and the **research mode**; the estimate is shown first.
  Project > Script shows research, claims and sources; Storyboard shows coverage, muted-test and the preview.
* CLI: `python -m studio research topic "The American Revolution" --mode normal`, `python -m studio research cache`.
* Demo (no AI, no cost, throw-away folder): `python scripts/demo/run_american_revolution.py [--no-render]`.
  Real research from official sources is in `scripts/demo/american_revolution_research.json`; the script and director
  plan come from a stand-in writer in the exact schemas Claude answers (see the file header).
* Tests: `python -m pytest -q tests`.

## 9. What is still missing (said plainly)

1. **Page text could not be opened** in the sandbox where the demo research was done (WebFetch was blocked for the
   archive/library/park-service sites), so those claims' evidence is marked "from the search-result summary". On your PC
   Claude Code opens the pages itself. The studio cannot verify a quote is on a page; it records the claim, the URL and
   the evidence text Claude gave.
2. **Search limits are not hard limits** (see Permissions). A request can still use more searches than asked; the overrun is recorded and shown.
3. **`context.json` is US-founding-era only.** Other topics depend on Claude's `needs` and on `people.json`/`gazetteer.json`.
   Adding a topic = adding entries (no code): regions, events, documents, synonyms.
4. **Coverage measures what the scene contains, not how good it looks.** The demo frames were checked by eye and found
   an oversized ship, label collisions and a missing coat that coverage did not see: those were fixed and have tests, but a
   bubble tail crossing a label (Yorktown) is still possible.
5. **Reference videos** (`research/` library, `research add <url>`) were not extended: YouTube was not reachable from the
   build environment. Only reference *images* are new. `[seed]` rules stay `[seed]` until checked in a real video.
6. **No real Claude call was executed in the build environment** (no CLI there). The prompts and schemas are tested with a
   stand-in writer; the first run on your PC is the first real test of the research prompt's JSON.
7. Claim <-> scene linking is word/number overlap, not understanding; a paraphrase can be missed (it errs towards
   "unused", never towards listing a source that is not used).
8. No GPU encode; a 10-minute video still takes minutes of CPU (`docs/performance.md`).
9. Copyright: sources are listed, nothing from other creators is stored. Quotes from sources are short evidence
   phrases, not page copies.
