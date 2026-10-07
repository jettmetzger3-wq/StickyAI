# Stickman Studio: architecture upgrade plan

Status: PLAN (written before any of this was implemented). The sections at the bottom are updated with real,
measured results as each part lands. Nothing below is claimed as done until its box is ticked.

## A. Current architecture (what exists and works today)

* **Server / UI**: FastAPI (`studio/server/app.py`) + React dashboard (`web/`). One project per video in
  `projects/<slug>/` (`meta.json`, `script.json`, `scenes/NNN.json`, `previews/`, `audio/`, `segments/`, `final/`).
* **Stages** (`pipeline/runner.py`, `pipeline/stages.py`): source -> script -> storyboard -> voice -> render -> mix ->
  package -> shorts. Each stage is re-runnable; `costs.py` gates anything that spends money.
* **Scene language** (`engine/schema.py`, ~1400 lines): the AI writes small JSON scenes (bg, elements, camera).
  `check_scene`/`repair_scene` repair them locally; `engine/compiler.py` builds a `Scene`; Pillow renders frames
  locally (30-65 ms/frame). Places, props (~400), puppets, reactions, camera, weather, maps, charts are all local code.
* **Local intelligence already there**: `rules.py` (offline script, `rule_scene`, `map_scene`, `number_counter`,
  `timeline_scene`), `themes.py` (topic kits, dialogue lines, background variety), `schema.activity_place`, `reactions.py`,
  `mascot.py`, `flow.py` (new, seam checker).
* **Writers** (`providers/llm.py`, `pipeline/writers.py`): Claude Code CLI (`claude -p`, your plan), Gemini, Groq,
  Anthropic API, Ollama, Basic. Per-task writer/model, plan saver, free-only backup on plan limit.
* **MCP**: only `providers/mcp_bridge.py` (Calliope, paid, optional; every MCP tool call is one extra `claude -p`).
* **Caching today**: per-scene key (text + mood) in `storyboard.json`; `props.json` keyed by whole script; per-beat voice
  reuse; segment hash (includes ENGINE_VERSION); music beds in `data/cache`. **No LLM-response cache. No memory between videos.**

## B. AI-call map (one 10-minute video, about 80 beats)

| # | Call | Where | Runs | In (tokens, measured by chars/3.6) | Out | Cacheable | Needed? |
|---|------|-------|------|------------------------------------|-----|-----------|---------|
| 1 | watch (vision, YouTube remake only) | `stage_source` | 1 | ~3k + 4 images | ~1k | yes (per URL) | only for remakes |
| 2 | script | `stage_script` | 1 | ~1.6k | ~4k (script+facts+cast) | yes | yes |
| 3 | fact-check (web search) | `fact_check` | 1 | ~3.5k | ~1.5k | yes | optional (fast mode: off) |
| 4 | smooth flow (new) | `smooth_flow` | 0-1 | ~2k | ~1k | yes | only if seams found |
| 5 | custom props design | `design_props` | 1 | ~4k | ~4k | **per prop name, across videos** | optional |
| 6 | **storyboard batches** | `stage_storyboard` | 7 (12 beats each; 10 at 8 beats) | **~16k each** (33.6k-char scene language + 20k-char examples + beats) | ~6k each | per-beat plan | **the hot spot** |
| 7 | fix scene (per scene that fails local repair) | storyboard | rare, 0-n | **~9.4k each** (entire scene language again) | ~0.6k | yes | local repair first |
| 8 | JSON retry (call_llm tries=2) | `call_llm` | 0-n | repeats the whole prompt | | n/a | keep, but cache |
| 9 | package (titles, chapters, thumbnail) | `stage_package` | 1 | ~3k | ~1.5k | yes | yes |
| 10 | Short pick | `shorts.pick_clip` | 1 | ~2.5k | ~0.8k | yes (already per key) | local rule fallback exists |
| 11 | rewrite one beat / regenerate one scene (user clicks) | `app.py` | on demand | 1-9k | small | n/a | user-triggered |
| 12 | Calliope MCP (paid, optional) | `mcp_bridge` | on demand | small each | | n/a | optional |

Total, normal run: ~13 calls, ~135k input + ~56k output tokens.

## C. Where Claude usage goes

1. **Storyboard = ~85% of everything.** Every 12-beat batch re-sends the same ~13k tokens of scene-language manual and
   examples (7 times per video), and asks for ~550 tokens of scene JSON per beat.
2. The "fix scene" call re-sends the entire manual (~9.4k tokens) for one scene.
3. No response cache: re-running a stage after a crash or a small edit re-pays for identical prompts.
4. Custom props are re-designed every video even when the same prop (Rosetta Stone) was drawn before.
5. Fact-check + smooth flow + props + package + short are small but all run every time, even in a quick test.
6. A bug that hurts quality: `normalize_script` drops the cast's `coat` and `look`, so recurring characters lose
   their coat color and beard between scenes (only hat + hat color survive).

## D. Caching system (proposed)

`studio/cache.py`: one content-addressed store under `data/cache/` (namespaces below), with hit/miss counters.
* `llm/` response cache keyed by sha256(provider, model, system, prompt, schema, image hashes). Never stores failures.
* `research/` topic briefs (deep mode) keyed by normalized topic; reused by every later video on that topic.
* `props/` custom prop drawings keyed by prop name; the next video reuses them instead of asking again.
* `plans/` per-beat director plans keyed by (beat text, mood, cast signature, pattern-library version).
* `people/` the global look of every historical person already used (Washington looks the same in every video).
* Per project: `usage.json` ledger (every AI call: stage, task, model, tokens in/out, cached or not, seconds).
Settings: `cache_enabled`, "Clear cache" button. Cached results are shown in the estimate ("12 of 80 scenes cached").

## E. Visual memory (proposed)

* `research/` (markdown, human-readable, committed, global): per-channel and per-video analysis files plus distilled
  `scene-patterns.md`, `camera-patterns.md`, ... Every rule is tagged with where it came from (analysed video /
  documented technique / my own knowledge) so nothing is passed off as observed when it was not.
* `studio/knowledge/` (machine-readable, global): `patterns.json` (30+ scene patterns: slots, characters, actions,
  background, props, camera, timing, transitions, tone, narration triggers), `people.json` (historical people ->
  look), `props_intel.py` (documents, headlines, statistics, money), `analysis.py` (beat -> people/places/documents/
  numbers/event type/emotion, local, no AI), `patterns.py` (retrieval), `composer.py` (pattern + slots -> scene JSON).
* Video-specific, in `projects/<slug>/`: `characters/<id>.json`, `plan.json`, `continuity.json`, `review.json`, `usage.json`.
* Rule: nothing from a creator's frames, art, characters or dialogue is stored; only the production logic.

## F. Research system (proposed)

1. **What I can really do from this machine** (checked, not assumed):
   * `youtube.com` is blocked by this session's egress proxy (HTTP 403 on CONNECT), so `yt-dlp`/`/watch` cannot run here.
   * vidIQ's connector can watch a video on vidIQ's servers and return a timestamped scene-by-scene walkthrough
     (`vidiq_video_watch`, 25 vidIQ credits each; transcript 5). Balance: 150 credits. **Needs your OK before any use.**
   * Free: web search/fetch of articles and episode guides (text only, no frames).
2. **Method per analysed video**: one fixed template (`research/videos/_TEMPLATE.md`): shot table (time, narration,
   what is on screen, characters, props + their text, camera, transition, duration), then "WHEN the narrator says X
   -> the animation does Y" rules, then the distilled reusable pattern(s).
3. **Keeps growing on your PC** (where YouTube works): `python -m studio research add <url>` reuses the existing
   source-stage pipeline (low-res download, frames, contact sheets, one vision call) and writes a skeleton file in
   `research/videos/` for the patterns to be distilled.
4. Deep mode only: one cached "topic brief" call per topic (key people with looks, places, documents, numbers, timeline).

## G. Scene-generation pipeline (proposed)

```
TOPIC -> cache check -> [deep: research brief, cached]
 -> SCRIPT (one call: script + facts + cast WITH looks + key entities; structure + flow rules; seam check, smooth only if needed)
 -> local ANALYSIS (beat -> people, places, documents, numbers, event type, emotion)
 -> PATTERN RETRIEVAL (local, from research/knowledge)
 -> CHARACTER REGISTRY (cast + people DB + earlier videos; characters/<id>.json)
 -> DIRECTOR PLAN (one call per ~20 beats, ~4k tokens in: pattern + slot fills + jokes, NOT scene JSON)
 -> LOCAL COMPOSER (plan -> scene JSON with the existing engine; the AI says WHAT, the engine decides HOW)
 -> beats the patterns can't express: existing full storyboard call, only for those beats
 -> CONTINUITY pass (location/characters/props/time/tone carried scene to scene, establishing shots inserted)
 -> QC REVIEW (local checks + auto-fix; deep mode may ask the AI to fix only what is left)
 -> previews -> voice -> render -> mix -> package -> shorts
```
Modes (chosen on the New Video page, default in Settings): **Fast** (no research, no fact-check, no custom props, plan only,
cache everything, ~3-4 calls), **Normal** (plan + full storyboard for custom beats, flow smoothing, review), **Deep**
(research brief, fact-check with web, richer plan batches, AI fix pass after review).
Before any run: a VIDEO ESTIMATE (calls, tokens, cached vs new, warning above a threshold).

## H. Files to be created / modified

New: `research/**` (see E), `studio/cache.py`, `studio/usage.py`, `studio/knowledge/{__init__,patterns,analysis,people,props_intel,composer}.py`
+ `patterns.json`, `people.json`, `studio/pipeline/{modes,characters,continuity,review,director}.py`, `studio/research_cli.py`,
`CLAUDE.md`, tests (`test_cache_usage.py`, `test_knowledge.py`, `test_director.py`, `test_review.py`).
Modified: `pipeline/stages.py` (call_llm cache + ledger, script merge, storyboard director route, review hook, props cache),
`prompts/__init__.py` (director prompt, script cast fields, entities), `pipeline/costs.py` + `server/app.py` (usage estimate,
mode, cache endpoints), `providers/llm.py` (token usage capture), `config.py`, `pipeline/mascot.py`, `pipeline/flow.py`,
`web/src/pages/{NewVideo,Settings,StoryboardTab,ScriptTab}.jsx`, `README.md`.
