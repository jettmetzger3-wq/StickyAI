# Stickman Studio: notes for Claude Code

A website on the user's own PC that turns a topic (or a YouTube link) into a finished stickman history video: research ->
script -> storyboard -> voice -> render -> mix -> package -> Shorts. Python 3.11 + FastAPI + Pillow/ffmpeg, React dashboard
in `web/` (built copy in `web/dist`, rebuild with `cd web && npm run build`). Full docs: `README.md`. Architecture:
`docs/architecture-v2.md` (research, meaning, memory, honest limits) and `docs/architecture-upgrade.md` (director, modes).
**Read those files on demand; do not paste them into context.**

## Rules that always apply
1. **Never spend money or credits without the user's click.** Paid providers go through `studio/pipeline/costs.py`
   (estimate -> approval). Secrets live only in the git-ignored `.env`; never log or print them.
2. **Use Claude as little as possible.** The AI decides WHAT; local code decides HOW and checks it. Before adding an AI call,
   see "Which tasks are local" below. Never call the AI per element, per frame or per retry of something deterministic.
3. **Don't regenerate what exists.** Everything the AI answers is cached (`studio/cache.py`); topic research, plans, props and
   people looks are reused across videos. Use `call_llm(..., cache=False)` only for explicit "redo this" buttons.
4. **Honest provenance in research.** A rule in `research/` is `[seed]` until it was checked in a real video (`[verified: ...]`).
   Never invent channel/video analysis. Never store other creators' frames, art or dialogue in the repo.
5. Only develop on the branch the session names; no pull requests unless asked; no model names in commits.
6. **Research stays inside its budget** (`studio/research/budget.py`). Reuse `data/research_cache/` first, research only gaps, stop
   when the evidence is enough, and pause for the user's OK before going over. Never invent a source, URL or quote; a claim
   with no source is `unverified`. Say honestly when a page could not be opened.
7. **A scene must show its narration.** Coverage (`semantics.coverage`) is checked before rendering; do not lower the gate to
   get green. Look at real frames (`previews/`) after changing how scenes look: numbers do not see an oversized ship.

## Where things are
| What | Where |
|---|---|
| Pipeline stages, AI calls (`call_llm`), caching hook | `studio/pipeline/stages.py` |
| Generation modes (fast/normal/deep) | `studio/pipeline/modes.py` |
| Director (AI plans a pattern per scene; composer builds it) | `studio/pipeline/director.py`, `studio/knowledge/composer.py` |
| Scene patterns (35) + retriever | `studio/knowledge/patterns.json`, `patterns.py`; human copy `research/scene-patterns.md` |
| Local beat analysis (people, places, documents, numbers, events, mood) | `studio/knowledge/analysis.py` |
| Historical people (looks), cities | `studio/knowledge/people.json`, `gazetteer.json` |
| Prop text (documents, headlines, slogans, era props) | `studio/knowledge/props_intel.py` |
| Character registry per video | `projects/<slug>/characters/<id>.json` (`studio/pipeline/characters.py`) |
| Continuity (place/time/people carried scene to scene) | `studio/pipeline/continuity.py` -> `projects/<slug>/continuity.json` |
| Storyboard QC with local auto-fixes | `studio/pipeline/review.py` -> `projects/<slug>/review.json` |
| Cache (llm, research, props, plans, people) | `studio/cache.py`, `data/cache/` |
| Usage ledger + estimate | `studio/usage.py`, `studio/pipeline/estimate.py`, `projects/<slug>/usage.json` |
| Script structure, flow check and smoothing | `studio/prompts/__init__.py`, `studio/pipeline/flow.py` |
| Scene language + auto-repair (the contract with the engine) | `studio/engine/schema.py` (`check_scene`) |
| Renderer, props (~230), places, puppets, camera | `studio/engine/*` |
| Research engine (budget, cache, sources, claims, approval) | `studio/research/{engine,budget,sources,claims,store}.py`; cache `data/research_cache/` |
| Meaning: what must be SEEN, coverage score, curated regions/events/documents | `studio/knowledge/semantics.py`, `context.json`; `studio/pipeline/coverage.py` |
| World state, scene specs + preview page, muted-video test, asset lookup, reference images | `pipeline/{world,spec,muted,assets,reference}.py` |
| Hand-written visual library + tool to extend it (reference videos) | `research/`, `studio/research_cli.py` |
| Demo (American Revolution, no AI, no cost) | `scripts/demo/run_american_revolution.py` |

## How a video is made (normal mode)
**research** (1 budgeted web request, or 0 when the saved research is enough) -> script (1 AI call, structure hook -> intro -> story ->
payoff, a purpose + location + visual per beat, claims tagged) -> evidence check (local; the fact-check call only for what the
research does not cover) -> flow check (local; 1 call only if the script jumps) -> **local analysis of every beat** -> pattern retrieval -> character registry -> **director plan**
(1 AI call per ~16 beats: pattern id + slot values + `needs`, what must be seen) -> **composer builds scenes, scored for coverage** -> odd beats only: full scene writer -> local
check/repair -> continuity -> **review (local fixes)** -> previews -> voice -> render -> mix -> package -> Short.
`gen_mode` fast = no research/fact-check/props, plan only; normal = research (10 searches) ; deep = 20 searches + AI polish. `storyboard_engine: classic` is the
old write-every-scene path (kept; costs ~2x more).

## Which tasks are local (never ask the AI) and which need it
Local: JSON/scene validation and repair, duplicate/existing-asset checks, timing and durations, entity extraction, pattern
retrieval, prop text, character looks, continuity, review fixes, flow seam detection, caching, estimates, rendering, audio sync,
file conversion. AI: the script, fact-check (needs web), choosing patterns + jokes + slot text, odd scenes, titles/description.

## Tests
`python -m pytest -q tests` (about 520 tests, ~1.5 minutes). `tests/conftest.py` makes a bug in a scene layout fail loudly.
Rendering checks: `python -m studio research build-docs` regenerates `research/scene-patterns.md` after editing patterns.json.
Speed work: measure first with `python scripts/bench_render.py` (`--profile frames|build`), prove the picture is unchanged with `--save`/`--check`, and read `docs/performance.md` for what was already tried. Only speed-ups that leave the picture unchanged keep `ENGINE_VERSION` as is.
When you change how scenes look, bump `ENGINE_VERSION` in `studio/engine/render.py` (it is part of the render cache key).
