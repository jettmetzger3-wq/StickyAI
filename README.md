# Stickman Studio

A website that runs on your own PC and turns a **YouTube link** (or any history topic) into a
**brand-new, ready-to-post stickman video**, in the style of channels like "Historically".

Paste a stickman video's link and the app:

1. **watches** it: reads the captions and grabs ~48 frames into contact sheets so the AI sees the drawing style, characters and gags,
2. writes a **new, original script** on the same subject (it never copies sentences: YouTube demonetizes "reused content"), plus a fact checklist,
3. draws a **storyboard**: one animated doodle scene per line (maps, stickmen with hats, props, speech bubbles),
4. records the **voice**, renders every scene in parallel, adds **music, sound effects and captions**,
5. writes **3 titles, a description with real chapter timestamps, tags and a thumbnail**.

Then you post it yourself.

Every step has a **free** option. **Paid tools are optional** (better voice, music and AI art), and the
app **never spends money or credits without showing you an estimate and waiting for your click**.

---

## Quick start

You need **Python 3.11+** and **ffmpeg**. Node.js is only needed if you want to rebuild the dashboard
(a built copy is included).

| | Windows 11 | Debian / Ubuntu |
|---|---|---|
| ffmpeg | `winget install --id Gyan.FFmpeg -e` | `sudo apt install ffmpeg` |
| Python | `winget install --id Python.Python.3.12 -e` | `sudo apt install python3 python3-venv` |
| Start | double-click **`start.bat`** | `./start.sh` |

The first start creates a `.venv` folder and installs the Python packages (a few minutes). Then your
browser opens **http://localhost:8765**.

**Free writer:** the default writer is **Claude Code on your own subscription** (no API bill). Install it
once with `npm install -g @anthropic-ai/claude-code` and run `claude` to log in. The app calls
`claude -p` in the background. No Claude Code? Pick "Ollama (local model)" or "Basic (no AI, for testing)".

**Free voice:** Kokoro downloads its model (~340 MB) from GitHub the first time you preview or use it.

---

## Free vs Pro

| Step | Free (default) | Pro (optional, needs keys) |
|---|---|---|
| Transcript (YouTube remakes) | the video's own captions, or Whisper on your PC | ElevenLabs Scribe (reads the YouTube link directly) |
| Watching the frames | Claude Code looks at the contact sheets | Anthropic API |
| Script, storyboard, titles | Claude Code (your plan) | Anthropic API: Claude Opus 5.5 by default ($4 / $20 per million tokens), Sonnet 5.5 or Haiku 4.5 cheaper |
| Voice | Kokoro (offline, `am_michael` at 1.2x) | ElevenLabs `eleven_flash_v2_5`, voice "George", ~0.5 credits per character, 1 take per line, **exact word timing** |
| Music | built-in synth (ukulele / tense / somber, crossfaded), or your own upload | ElevenLabs Music (one instrumental bed per mood) |
| Thumbnail | built-in doodle thumbnail | ElevenLabs image or Higgsfield (AI background, our title text on top) |

You can mix and match: the New Video page has **Free**, **Pro** and **Custom** (one dropdown per step).

**How costs work**
- Before you start, the right-hand panel shows an estimate per step. The start button says
  "Approve ~$X & start". Nothing paid runs before that click.
- While running, if a step would cost noticeably more than you approved (more than 25% over), the run **pauses and asks again**.
- Some providers don't publish a per-request price (ElevenLabs music, transcription and images; Higgsfield).
  Those show "amount set by provider". After the call, the app measures the real usage from your ElevenLabs balance and logs it.
- Balances are shown where the provider's API reports them (ElevenLabs).
- The dollar figure for ElevenLabs credits uses a rate you can change in Settings (default $0.22 per 1,000 credits ≈ the Creator plan).

**API keys** go in Settings (or in a `.env` file, see `.env.example`). They are stored only in `.env`
(gitignored), never logged and never shown again.

**Not included, on purpose**
- **OpenArt** has no public developer API (only an MCP connector inside the Claude app), so a standalone
  website can't call it. Its free-tier images also carry a watermark.
- The ElevenLabs / OpenArt / Higgsfield / Calliope **connectors you use inside the Claude app** can't be
  reached from a standalone website. The app uses each service's official API with your own key instead.

---

## Using the dashboard

- **New video**: paste a YouTube link (or switch to "Start from a topic"). Choose how closely to follow the
  original (close / balanced / loose), the length (it defaults to the source's length), quality tier, voice
  (with previews), and **Autopilot**:
  - **on**: runs straight to the finished video,
  - **off**: pauses after the **script**, the **storyboard** and the **voice** so you can edit before continuing.
- **Project page**: live progress for each step (scene X of Y with ETA), plus tabs:
  - **Script**: edit, reorder, insert or delete beats, change moods, "↻ rewrite" one beat with the AI, tick off the fact checklist, edit the cast (who wears which hat).
  - **Storyboard**: a still of every scene. Click one to scrub through time, nudge elements, delete elements, edit the scene JSON, "Redraw with AI" (optionally with instructions), or re-render just that scene into the video.
  - **Voice & music**: listen to each line, change the voice, upload your own royalty-free music and re-mix.
  - **Output**: the video player, download buttons (full quality + a share copy under 30 MB), the 3 titles, description and tags with copy buttons, chapters and the thumbnail.
  - **Source** (remakes): what the AI saw when it watched the video, the frames and the transcript.
  - **Costs & log**: switch tools per step, remaining estimates, what was actually spent, and the run log.
- **Re-run from here** on any step redoes it and everything after it, but each step only redoes what changed
  (edited lines get new audio, changed scenes get re-rendered).

---

## Command line

```bash
python -m studio make "The Fall of Rome" --minutes 3             # topic -> finished video (free)
python -m studio make "https://www.youtube.com/watch?v=..."      # remake a YouTube video
python -m studio make "..." --tier pro                           # paid tools (asks before spending)
python -m studio make "..." --llm claude_cli --voice kokoro --music synth --image local
python -m studio make "..." --checkpoints                        # pause after script/storyboard/voice
python -m studio resume <project-folder-name>                    # continue after a pause or error
python -m studio rerender <project-folder-name> 4 7               # re-render scenes 4 and 7
python -m studio list | doctor | serve
```

Use `.venv/bin/python` (Linux) or `.venv\Scripts\python` (Windows) if you didn't activate the venv.

---

## Where things are saved

Each video is a folder `projects/<name>/`, so any step can be resumed or redone:

```
meta.json          settings, step status, approvals, costs
source/            YouTube info, transcript, frames, contact sheets, visual notes
script.json        beats (mood + text), fact list, cast
scenes/000.json    one scene per beat, in the JSON scene language
previews/          storyboard stills
audio/             one WAV per beat + voice.json (durations, word timing)
segments/          one MP4 per scene
final/             video.mp4, video_share.mp4, mix.wav, thumbnail.png, youtube.json, description.txt
```

Settings live in `data/settings.json`, the project index and cost ledger in `data/studio.db` (SQLite),
the Kokoro model in `data/models/`.

---

## Troubleshooting

- **"ffmpeg not found"**: install it (see Quick start), then open a *new* terminal so PATH updates.
- **YouTube link won't load / no captions**: update the downloader with `.venv/bin/python -m pip install -U yt-dlp`
  (Windows: `.venv\Scripts\python -m pip install -U yt-dlp`). If the video has no captions at all, pick
  "Whisper on my PC" (`pip install faster-whisper` first) or "ElevenLabs Scribe" as the transcript tool.
- **"the `claude` command was not found"**: install Claude Code and run `claude` once to log in, or set its path in Settings.
  The app removes `ANTHROPIC_API_KEY` from the environment when it calls `claude`, so the free writer always uses
  your subscription and never your API key.
- **Kokoro download fails**: download `kokoro-v1.0.onnx` and `voices-v1.0.bin` from
  https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 and put them in `data/models/`.
- **A scene looks wrong**: open it in the Storyboard tab, nudge or delete elements, edit the JSON, or "Redraw with AI".
  Then "Re-render this scene in the video" (only that scene is re-rendered).
- **Something failed mid-run**: fix the cause and press **Resume**. Finished work is kept.

---

## How it works (for the curious)

- **`studio/engine/`**: the video engine from the first video, cleaned up into a package: doodle drawing at 2x
  with LANCZOS downsampling, stickmen with ~40 hats (nations, crown, Roman, Viking, pharaoh, knight, ...),
  ~75 props, Natural Earth maps (Mercator, any region; Pacific islands wrap correctly), easing, blinking,
  bobbing, a smooth float camera clamped so it never shows black edges, captions (7 words max, double spaces,
  out of everyone's way), procedural music and sound effects, and the mix (voice first, music ~13 dB under
  with light ducking, then two-pass `loudnorm` to -15 LUFS / -1.5 dB true peak).
- **The JSON scene language** (`engine/schema.py`, `engine/compiler.py`): the AI never writes code. It writes
  JSON like `{"bg": {"type": "map", ...}, "elements": [{"type": "char", "kind": "roman", "at": "word:Caesar"}]}`.
  Every scene is auto-repaired (wrong names, off-screen positions, text in the caption area, labels on faces,
  somber-scene rules) and validated against a JSON Schema before rendering. If a scene is broken the AI is asked
  to fix it, and as a last resort a simple rule-based scene is used. 14 hand-made example scenes
  (`studio/prompts/examples.json`) teach the AI the style.
- **Rendering**: each scene is composited frame by frame and piped raw into ffmpeg (x264), one MP4 per scene in
  a process pool (CPU cores minus one), then concatenated with the final mix.
- **Providers** (`studio/providers/`): one interface per step, implementations registered in
  `providers/__init__.py`. Paid ones use the official SDKs (`anthropic`, `elevenlabs`, `higgsfield-client`).

## Development

```bash
python -m pytest                        # tests: TopoJSON, scene schema/compiler, captions, years, chapters, costs
python -m studio.engine.measure_props   # after adding/changing a prop
cd web && npm install && npm run dev    # dashboard with hot reload (proxy to python -m studio serve)
cd web && npm run build                 # rebuild web/dist
```

`reference/` keeps the original starter engine examples (the Japan WW2 script and hand-written scenes).

## Licenses

Fredoka and Patrick Hand fonts: SIL Open Font License. Map data: Natural Earth (public domain) via
world-atlas (ISC). Only use music you have the rights to.
