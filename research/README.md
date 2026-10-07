# Stickman Studio research library

This is the studio's **visual memory**: production rules for animated history explainers, written down once so every new
video starts from them instead of from scratch. It is global (it does not change from video to video). Everything about
one specific video (its characters, plan, review, usage) lives in `projects/<slug>/` instead.

| File | What it holds |
|---|---|
| `visual-storytelling.md` | "WHEN the narrator says X, the animation does Y" rules, the backbone |
| `scene-patterns.md` | the 33 reusable scene templates (generated from `studio/knowledge/patterns.json`) |
| `character-patterns.md` | how people, groups, crowds and recurring characters are drawn and staged |
| `prop-patterns.md` | what a prop must say; documents, newspapers, signs, numbers, money, weapons |
| `camera-patterns.md` | shots, zooms, pans, when the camera moves |
| `transition-patterns.md` | how one scene hands over to the next |
| `historical-animation-patterns.md` | maps, crowds, battles, politics, large numbers, serious events, jokes |
| `channel-analysis/` | one file per channel studied |
| `videos/` | one file per analysed video (shot table: narration, picture, props, camera, transition) |
| `style-library/` | the studio's own look (colors, hats, line style) |

## How honest the library is (read this)

Every rule carries a provenance tag:

- `[seed]` a documented technique of the genre, written from general knowledge. **Not yet checked frame by frame.**
- `[verified: <video> @ <time>]` seen in a specific video, with the timestamps in that video's file under `videos/`.
- `[user clip]` seen in a clip you supplied.

At the time of writing nearly everything is `[seed]`: the cloud session this was written in cannot reach YouTube
(its network policy returns 403 for youtube.com), so no video could be downloaded or watched there. To turn seeds into
verified rules, on a PC that can reach YouTube run `python -m studio research add <url>` (see `studio/research_cli.py`):
it measures every cut and shot length with ffmpeg, aligns the narration, and writes a shot table in `videos/` for you (or
Claude Code) to fill from the contact sheets. Then `python -m studio research learn` saves the distilled patterns.

## What is never stored

Other creators' frames, artwork, characters, dialogue or music. Only production logic: what kind of shot, in what order,
how long, what the camera does, which technique makes a joke land. The studio's own artwork is always drawn fresh.

## How the studio uses it

`studio/knowledge/patterns.json` is the machine-readable form. For every beat of a script the studio (1) analyses the
line locally (people, places, documents, numbers, event type, mood), (2) retrieves the patterns that fit, (3) asks the AI
only to choose and fill in the details, and (4) builds the scene with `studio/knowledge/composer.py`.
