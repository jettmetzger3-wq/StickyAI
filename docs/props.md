# Props: assets you pick, not pictures the AI draws

Code: `studio/engine/prop_library.py` (the library), `studio/knowledge/propindex.py` (the word index), `studio/props_cli.py`
(`python -m studio props ...`). Data: `studio/knowledge/prop_library.json`, `studio/knowledge/prop_words.json`,
`data/prop_library/*.json` (yours), `data/prop_gaps.json` (what is missing).

## Where props come from

| Kind | How many | Where | Scene stores |
|---|---|---|---|
| Drawn in code | ~230 | `studio/engine/props*.py`, `registry.PROPS` | the name |
| Hand-drawn library | 43 + 2 variants | `prop_library.json`, built by `scripts/build_prop_library.py` | the name (the render key carries a fingerprint of the design) |
| Drawn for earlier videos | grows | `data/prop_library/<name>.json`, one file per prop | the shapes, inside the scene (a saved scene renders anywhere) |

All of them are real entries in `registry.PROPS`: the scene writer sees them in its prop list, `check_scene` accepts them, the
layout check measures them, the renderer draws them. A **variant** is a built-in prop with fixed settings (`tea_chest` = the crate
labelled TEA; `white_flag` = a white flag). A library design never replaces a prop drawn in code, and an exact library name beats a
looser alias (`bread` is now a loaf, not a baguette; `cross` still means the X mark, the Christian cross is `christian_cross`).

## How a word becomes a prop (`propindex.find / pick`)

1. A phrase that is a prop name ("statue of liberty", "printing press") or a word that is a prop or alias ("cannon", "harbor").
2. The meaning table (`prop_words.json`, ~1,100 concrete nouns: "troops" -> helmet, "treaty" -> scroll, "gunpowder" -> keg) and
   the tags of library props ("duel" -> pistol). Abstract words are left out on purpose: they put props on every scene.
3. The year (written in the text, or given) removes what did not exist yet (`ERA_FIRST`, a library prop's `frm`).
4. Words that are verbs in one sentence ("prices **rose**", "they **cross** the river") count only as a noun ("a red rose").
5. `covers(phrase)` is the strict test for named objects: "the Rosetta Stone" is *not* covered by "stone -> rocks".

Used by `composer.prop_in_text` (11 pattern slots), `registry.guess_prop` (last resort for a made-up name), the coverage check
(`semantics.scene_concepts`: a keg satisfies "gunpowder"), `coverage.patch` (adds a missing object at the first free spot that
creates no new layout problem) and the storyboard review (`review.check_history`).

## When the AI is asked

Only for an object the director's plan says must be seen (`needs`) that `covers()` says no prop shows. One short request
(`prompts.prop_design_prompt(wanted=...)`, about a third of the old one), and none when everything is covered (logged and counted
in the savings meter). What comes back is checked (`custom_props.clean_kit`) and kept for good. Whatever still has no prop is
written to `data/prop_gaps.json`.

```
python -m studio props list --names     what is in the library
python -m studio props gaps             objects stories wanted that nothing shows (most wanted first)
python -m studio props seed             draw the most wanted in ONE request (shows the estimate, asks first)
python -m studio props sheet            data/prop_library_sheet.png: a picture of every library prop
```

## Adding props

* Hand-drawn: add a builder and a `DESIGNS` line in `scripts/build_prop_library.py` (shapes on a 100 x 100 grid, tags, years,
  category), run `python scripts/build_prop_library.py --sheet`, **look at the sheet**, commit the JSON it writes.
* Words: add a line to `prop_words.json` (target must be a real prop; `tests/test_propindex.py` checks every target and that no
  vague word such as "will", "light" or "power" slips in).
* Cached render keys: a scene that uses a library prop gets that design's fingerprint in its render key, so redrawing a library
  prop re-renders exactly the scenes that show it. Scenes without library props keep their keys.

## What it does not do (said plainly)

* The index understands words, not sentences: "the king's gold crown" finds *crown* or *gold_bars*, whichever word comes first.
* The meaning table is hand-curated and English only. The 43 hand-drawn props are simple flat shapes: good at video size, not art.
* Which objects the plan lists in `needs` is the AI's judgement; props the plan never mentions are not drawn by anyone.
