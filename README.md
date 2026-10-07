# Stickman Studio

A website that runs on your own PC and turns a **YouTube link** (or any history topic) into a
**brand-new, ready-to-post stickman video**, in the style of channels like "Historically".

Paste a stickman video's link and the app:

1. **watches** it: reads the captions and grabs ~48 frames into contact sheets so the AI sees the drawing style, characters and gags,
2. writes a **new, original script** on the same subject (it never copies sentences: YouTube demonetizes "reused content"), plus a fact checklist,
3. draws a **storyboard**: one animated doodle scene per line (maps, stickmen with hats, props, speech bubbles),
4. records the **voice**, renders every scene in parallel, adds **music, sound effects and captions**,
5. writes **3 titles, a description with real chapter timestamps, tags and a thumbnail**,
6. cuts a **vertical Short** (25-55 s, big captions, "full video on the channel") to promote it.

Then you post it yourself.

**On your own PC there are no limits:** make as many videos as you want. With the free tools
(Claude Code on your plan, Kokoro voice, built-in music) they cost nothing.

Want it **on your phone**? `start.bat online` / `./start.sh online` gives you a free private link (see below).
Your **free website on Netlify** (landing page, waitlist and an "Open my studio" button that finds your PC) is in
[`netlify-site/`](netlify-site/README.md). Want a full **public website where other people make videos**? See [DEPLOY.md](DEPLOY.md). It starts **free-only**; a Pro plan with
Stripe payments is built in and can be switched on later ([PRICING.md](PRICING.md)).

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
`claude -p` in the background.

**No Claude plan? Use a free API key instead:**
- **Google Gemini**: free key at https://aistudio.google.com/apikey (no card). Make it in a Google project
  **without billing**, then it can never cost anything. Good scripts and titles; scenes are a bit plainer than
  Claude's. The free tier has a daily request limit (AI Studio shows yours); the studio sends 16 scenes per request
  so a 10-minute video needs only about 12-20 requests. Google may use free-tier prompts to improve its products.
- **Groq**: free key at https://console.groq.com/keys (no card, free plan). Very fast, but the free limits are small
  (about 8,000 tokens a minute, 1,000 requests a day), so scenes are drawn two at a time with shorter
  instructions. Settings shows how many free requests are left today.

Paste the key under Settings → API keys (`GEMINI_API_KEY` / `GROQ_API_KEY`) and pick the writer as default (or per
video). When a per-minute limit is hit the studio waits; when the day's limit is used up the video pauses and you
press **Resume** the next day. "Ollama (local model)" and "Basic (no AI, for testing)" also work.

**Pick your writer, and who does what:** Settings → "Writer: which AI does what".
- **Main writer**: Claude Code (your plan, the default), Gemini, Groq, the Anthropic API, Ollama or Basic. It
  writes everything, and new videos start with it (the New Video page can still pick another per video).
- **Who does what**: hand any single job to a different AI: writing the script, fact-checking, watching the source
  video, designing props, drawing the scenes, titles and description, picking the Short's moment. For example the
  script on Claude and the scenes on Gemini. A paid writer always shows its price first and waits for your OK.
- **Backup writer**: if your Claude plan hits its usage limit in the middle of a video, a free writer (Gemini, Groq
  or Ollama on your PC) takes over for the rest of that step instead of the video stopping; the video gets a note
  saying so, and Claude is tried again after its reset time. Or choose "Stop and wait for me". Only free writers can
  step in, so nothing starts costing money on its own.

**Claude plan saver** (Settings → Writer, on "Balanced" by default): uses less of your Claude plan for the same
video. The script, the fact-check and the scenes keep your best Claude model; the side jobs (watching the source
video, designing props, titles and description, picking the Short) use Sonnet (titles and the Short pick also
think less, on Claude Code versions that support it); scenes are asked for 12 at a time instead of 8, so the long
scene instructions are sent a third fewer times; and the first batch of scenes goes alone so the batches after it
can reuse Claude Code's prompt cache of those instructions. The channel host's
greeting and sign-off scenes are drawn without asking the AI at all. "Maximum savings" goes further (Haiku for
titles and the Short, Sonnet for the fact-check, 16 scenes per request, fewer example scenes; scenes can get a
little plainer); "Off" uses your default model everywhere. You can also set the Claude model per job in the
"Who does what" table.

**Free voice:** Kokoro downloads its model (~340 MB) from GitHub the first time you preview or use it.

### Use it from your phone (free, just for you)

```bash
start.bat online        # Windows (or double-click start-online.bat)
./start.sh online       # Linux / macOS (or ./start-online.sh)
```

This runs the same studio with a login and opens a free Cloudflare link like
`https://some-random-words.trycloudflare.com` that works on your phone or any computer while the start
window is open. It needs Cloudflare's free `cloudflared` program (no account):
`winget install --id Cloudflare.cloudflared` (Windows), `brew install cloudflared` (macOS) or the `.deb` from
https://github.com/cloudflare/cloudflared/releases (Debian/Ubuntu).

- The first time, the browser on your PC asks you to create your **owner account**. Only you can log in; nobody
  can sign up through the link, and the owner account can only be created on the PC itself.
- Same videos, same free tools, no limits. Your PC does the work, so it has to stay on.
- The link changes every time you start it. Don't post it publicly: it's your private studio.
- Live progress updates arrive every few seconds instead of instantly (Cloudflare's free links don't stream them).

---

## Free vs Pro

| Step | Free (default) | Pro (optional, needs keys) |
|---|---|---|
| Transcript (YouTube remakes) | the video's own captions, or Whisper on your PC | ElevenLabs Scribe (reads the YouTube link directly) |
| Watching the frames | Claude Code looks at the contact sheets | Anthropic API |
| Script, storyboard, titles | Claude Code (your plan), or a free Gemini / Groq key | Anthropic API: Claude Opus 5.5 by default ($4 / $20 per million tokens), Sonnet 5.5 or Haiku 4.5 cheaper |
| Voice | Kokoro (offline, `am_michael` at 1.2x) | ElevenLabs `eleven_flash_v2_5`, voice "George", ~0.5 credits per character, 1 take per line, **exact word timing** |
| Music | built-in synth (fun, tense, sad, epic battle, mystery, triumph; musical hits on big moments), or your own upload | ElevenLabs Music (one instrumental bed per mood) |
| Thumbnail | built-in doodle thumbnail | ElevenLabs image or Higgsfield (AI background, our title text on top) |
| Short | stickman Short cut from your video (1080x1920, big captions) | also a Calliope AI-illustrated Short (your Calliope credits, see below) |

You can mix and match: the New Video page has **Free**, **Pro** and **Custom** (one dropdown per step).

**How costs work**
- Before you start, the right-hand panel shows an estimate per step. The start button says
  "Approve ~$X & start". Nothing paid runs before that click.
- While running, if a step would cost noticeably more than you approved (more than 25% over), the run **pauses and asks again**.
- **Limit per video** (Settings → Spending, default $15): even approved steps pause and ask before one video's
  spending goes over it. Approving raises the limit for that video only.
- ElevenLabs music is composed once per mood (fun, tense, somber) and **reused in later videos** (Settings).
- Some providers don't publish a per-request price (ElevenLabs music, transcription and images; Higgsfield).
  Those show "amount set by provider". After the call, the app measures the real usage from your ElevenLabs balance and logs it.
- Balances are shown where the provider's API reports them (ElevenLabs).
- The dollar figure for ElevenLabs credits uses a rate you can change in Settings (default $0.22 per 1,000 credits ≈ the Creator plan).

**API keys** go in Settings (or in a `.env` file, see `.env.example`). They are stored only in `.env`
(gitignored), never logged and never shown again.

**Not included, on purpose**
- **OpenArt** has no public developer API (only an MCP connector inside the Claude app), so a standalone
  website can't call it. Its free-tier images also carry a watermark.
- The ElevenLabs / OpenArt / Higgsfield **connectors you use inside the Claude app** can't be reached from a
  standalone website. The app uses each service's official API with your own key instead.

**Calliope (AI Shorts and thumbnails)** has no plain web API, only an MCP connector, so the app reaches it
through **Claude Code on your PC**. One-time setup:

```bash
claude mcp add --transport http calliope https://www.calliopelabs.co/api/mcp
claude          # then type /mcp and log in to Calliope
```

Then press **Settings → Calliope → Test connection** (free) and pick "Calliope AI Short" as the Shorts tool
(the Pro tier does). Before anything is spent, the app asks Calliope for its **exact credit estimate** and waits
for your OK. Once an AI Short exists, the Output tab can also order **Calliope thumbnails** (again with the exact
price first). If Calliope isn't ready, you still get the free stickman Short. Korpi can be added the same way
once its connector works.

---

## Using the dashboard

- **New video**: paste a YouTube link (or switch to "Start from a topic"). Choose how closely to follow the
  original (close / balanced / loose), the length (it defaults to the source's length), quality tier, voice
  (with previews), and **Autopilot**:
  - **on**: runs straight to the finished video,
  - **off**: pauses after the **script**, the **storyboard** and the **voice** so you can edit before continuing.
- **Project page**: live progress for each step (scene X of Y with ETA), plus tabs:
  - **Script**: edit, reorder, insert or delete beats, change moods, "↻ rewrite" one beat with the AI, tick off the fact checklist (with the automatic fact-check's verdicts and fixes), edit the cast (who wears which hat).
  - **Storyboard**: a still of every scene. Click one to scrub through time, nudge elements, delete elements, edit the scene JSON, "Redraw with AI" (optionally with instructions), or re-render just that scene into the video.
  - **Voice & music**: listen to each line, change the voice, upload your own royalty-free music and re-mix.
  - **Output**: the video player, download buttons (full quality + a share copy under 30 MB), the 3 titles, description and tags with copy buttons, chapters, the thumbnail, the Short (with its title, description and #shorts tags), **Upload to YouTube** (see below) and what the video cost.
  - **Source** (remakes): what the AI saw when it watched the video, the frames and the transcript.
  - **Costs & log**: switch tools per step, remaining estimates, what was actually spent, and the run log.
- **Re-run from here** on any step redoes it and everything after it, but each step only redoes what changed
  (edited lines get new audio, changed scenes get re-rendered).

### Upload straight to YouTube (free)

The Output tab can upload the finished video (or the Short) to your channel with the title, description, chapters,
tags and thumbnail filled in, as private, unlisted or public, or scheduled to go public at a set time. It uses
Google's free YouTube Data API with **your own** Google project, so nothing is shared with anyone:

1. Open console.cloud.google.com, create a project and enable **YouTube Data API v3**.
2. Under "Google Auth Platform" set up the consent screen (External) and add your Google account as a test user.
3. Create an OAuth client of type **Desktop app**; copy the client ID and secret.
4. In the studio: Settings > API keys > `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`, then **Connect YouTube**
   (on the PC, since Google sends you back to `localhost`). After that you can upload from your phone too.

It costs nothing; Google's free daily quota allows several uploads a day. Google may keep videos uploaded by a new,
unaudited API project private; if that happens, publish them from YouTube Studio or request Google's free API
audit for your project. Custom thumbnails need a verified channel (YouTube asks for a phone number once).

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
python -m studio online                                          # your studio + a free private link for your phone
python -m studio admin you@example.com                           # website (hosted mode): make an admin
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
final/             video.mp4, video_share.mp4, mix.wav, thumbnail.png, youtube.json, description.txt,
                   short.mp4 (+ short_ai.mp4 from Calliope), short.json
shorts/            the Short's scenes without the small captions
```

Settings live in `data/settings.json`, the project index and cost ledger in `data/studio.db` (SQLite),
the Kokoro model in `data/models/`.

---

## Troubleshooting

- **"ffmpeg not found"**: install it (see Quick start), then open a *new* terminal so PATH updates.
- **"Couldn't watch the video frames … Requested format is not available"**: YouTube now makes downloaders solve
  a small JavaScript puzzle. Install Node.js (`winget install --id OpenJS.NodeJS.LTS -e`) or Deno
  (`winget install --id DenoLand.Deno -e`), restart the app, and update the downloader (below). Until then the app
  looks at YouTube's own still frames instead, so the remake still works.
- **A video is stuck after the computer was switched off**: just start the app again. Interrupted videos are
  paused automatically; open it and press **Resume** (finished steps are kept) or **Delete**.
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

- **Animation** (`studio/engine/puppet.py`): stickmen are re-posed every frame. They breathe, blink, glance around,
  talk while their speech bubble is up, and act on cue (walk, run, jump, wave, point, cheer, nod, shake head, shrug,
  think, facepalm, tremble, lean, bow, faint, laugh, cry, dance, fight...). Crowds have depth. Scenes can have
  several camera shots (cuts to close-ups, pans, whip pans with motion blur), maps can be light or dark with bobbing
  pointer arrows, and backgrounds include painted places (field, hills, desert, snow, city, battlefield, rooms) at
  any time of day. Old storyboards get automatic motion too.
- **Each video gets its own world** (`studio/pipeline/themes.py`, `studio/engine/places.py`): the studio reads the
  title, topic and script and picks topic kits (about 30: France, Britain, USA, Russia, Rome, Egypt, Japan, China,
  the sea, space, the Middle Ages, WW1, WW2, the Cold War, the Wild West, pirates' Caribbean...). Each kit brings
  places, props, hats and catchphrases, so a Napoleon video happens on Paris streets, in palaces and on
  battlefields, and a pirate video in harbors, on beaches and underwater. Places include city skylines with real
  landmarks (Paris, London, New York, Washington, Moscow, Rome, Cairo, Istanbul, Delhi, Tokyo, Beijing, Berlin...),
  town streets (European, medieval, Asian, Arab, Wild West), palace halls, harbors, beaches, underwater, space,
  jungle, mountains, WW1 trenches, and the places where things happen (see below). Two scenes in a row never look
  the same (colors or time of day change).
- **Props** (`studio/engine/props_*.py`): about 230 detailed doodles: world landmarks, ships from Viking longships to
  the Titanic, sea life, animals, food from baguettes to sushi, weapons and machines across history, and everyday
  objects. On top of that, before the storyboard the writer designs a few extra props this particular story needs
  (the Rosetta Stone, a Spitfire, Napoleon's hat on a pillow...) as simple shapes, which are checked, saved with the
  project and shown on the Storyboard tab. Turn this off in Settings ("Draw extra props for each video").
- **Motion and sound**: windmills turn, flags wave, fires flicker, smoke rises, lighthouse beams sweep and rotors
  spin on their own. Scenes change with slides, wipes, zoom-throughs, iris and page turns (cuts between map shots,
  fades around sad moments). Every place has its own quiet background sound (waves, gulls, street murmur, wind,
  jungle, battle, crickets at night), characters' footsteps, jumps and cheers are heard, and little "blah blah"
  blips play while a speech bubble is up. Captions light up the word being spoken. All of it can be switched off
  in Settings.
- **Characters you recognize**: coats in each side's colors (British redcoats, French blue, Russian green...) with
  crossbelts or gold epaulettes depending on the hat, beards and mustaches, Napoleon's hand-in-coat pose, and
  riders on horses, camels, elephants and chariots (they gallop when they move; whole cavalry crowds too).
- **War maps**: troops (or tanks, ships) march along invasion arrows, battles get a crossed-swords marker with a
  boom, front lines move smoothly between positions, and counters tick years, army sizes or money.
- **Living maps** (`engine/livemap.py`): empires grow and shrink over the years (each change spreads out from the
  heartland while the year ticks, BC and AD), capitals get a star with a ripple, routes draw themselves with a ship,
  camel or walker riding the tip (the Silk Road, Columbus, a retreat), the camera can frame a country, and a closer
  map right after a wider one zooms into it like Google Earth.
- **Weather and light** (`engine/weather.py`): falling snow, blizzards, rain, storms with lightning and thunder,
  drifting fog, ash and embers over burning cities, twinkling stars and shooting stars at night, and the light
  changing during a scene (night falling, a dusk, a room going dark). Weather the narration mentions is added
  automatically, with its own background sound.
- **Action moments** (`engine/action_fx.py`): props do things on cue: cannons and tanks fire (recoil, flash,
  smoke, a cannonball that explodes on its target), ships fire broadsides or sink, castles and walls collapse into
  dust and rubble, things blow apart, forts shake, and characters fight with swords (the blade follows the arm,
  sparks and clangs when blades meet).
- **Charts and timelines** (`engine/charts.py`): bar charts and rankings that grow with numbers ticking up, line
  charts that draw themselves, timelines where dates drop in as they're said, size comparisons (circles whose area
  matches the numbers) and then-vs-now split screens with an old-photo side.
- **Same character, same look**: the script's cast lists each person's hat, outfit color and beard or mustache;
  in every scene a character marked with `"who"` (or wearing a hat only one cast member has) gets that look, so
  Napoleon is always in French blue. A coronation crown and similar costume changes are kept.
- **Thumbnails**: big faces cut out like stickers (white outline, soft shadow), a close-up giant against a furious
  small character, a prop that sums up the story, huge double-outlined words in the cast's colors.
- **Places where things happen** (`engine/places_work.py`): when the narration says what someone does, the whole
  screen becomes that place instead of a small prop on a plain page. "He built a factory" is a construction site:
  the steel frame stands, a tower crane carries beams over and lowers them, workers hammer on the scaffolding and
  the brick walls rise while the scene plays (also houses, skyscrapers, castles, walls and ships on a slipway; the
  same building keeps rising over several scenes and its chimney starts smoking when it's finished). Battles happen
  on a real battlefield (a village with a church tower, a river with a wooden bridge, trampled ground, craters,
  black smoke rising; also open plains and WW1/WW2 ruins), and there are working factories (smoking chimneys and a
  railway outside; a running conveyor belt, turning gears and a stamping press inside), farms, mines, classrooms,
  labs with bubbling flasks, parliament, a courtroom, a prison cell, a market and an army camp with a crackling
  fire, each with its own background sound. The writer is told to use them, and the auto-repair switches a plain
  scene to the right place when the narration names it (and leaves figures of speech like "built an empire" alone).
- **Faces that react to the words** (`engine/reactions.py`): characters look shocked on "suddenly", furious on
  "betrayed", smug on "won", crushed on "lost", scared on "terrified", laugh on "laughed", right as the narrator
  says the word. The character the sentence is about reacts ("Napoleon won, and Francis was furious"); a gasp with
  no clear subject goes through everyone. A character's own actions always win. Settings → "Faces react to the words".
- **Smarter camera**: without hand-made shots, the camera cuts in to a close-up exactly on the punchline word (the
  last face that reacts) and cuts back out after it; wide painted places get a slow sideways pan instead of a
  plain push-in. Settings → "Smart camera".
- **Channel mascot** (`pipeline/mascot.py`): your channel's own host stickman (Settings → Channel mascot: name, hat,
  colors, beard, its lines). It says hi right after the hook ("Hey, it's Sticky! Today: ..."), signs off at the end
  next to a subscribe button, and leans in from the edge of the screen to react to the biggest moments ("WHAT?!",
  "Oof.", "Ha!"), at most once every 7 scenes. Its lines are ordinary beats in the Script tab, so you can edit or
  delete them, they never end up in the Short, and the New Video page can switch it off for one video.
- **Drifting clouds**: the clouds of every painted sky drift slowly and pass behind buildings, hills and towers.
- **Fallback scenes** (Basic mode, or when an AI scene can't be repaired) now use maps with territories and
  invasion arrows when countries are mentioned, timelines for several dates, counters for big numbers ("600,000
  men", "£2 billion") and action moments (ships sinking, forts collapsing, cannons firing).
- **Speed**: rendering is about 2.5x faster than before (the camera crops and scales instead of warping the whole
  frame, and redrawn characters use a cheaper, equally clean downscale).
- **Music and narration**: the free synth picks the music from the story (epic drums for battles, mystery for
  secrets, a fanfare for victories, sad strings for sad moments), adds a musical hit on big moments (a victory, a
  twist, a war breaking out, a flop), and the narrator slows down with a pause for sad parts and speeds up a little
  for jokes. The narration is polished like a YouTube mic (no low rumble, clearer words, an even level). Each can
  be switched off in Settings.
- **Fact-check**: right after writing the script, the writer double-checks the claims it was unsure about (with web
  search when it runs on Claude Code, free on your plan), rewrites any beat that got a fact wrong, and lists what it
  confirmed, fixed and couldn't settle on the Script tab.
- **Dialogue**: characters talk. A character's `"say"` lines appear one after another in speech bubbles over their
  head (placed to dodge labels and props, tail pointing at them) while their mouth moves, and crowds can shout back.
  When the narration says someone spoke, ordered, promised or rallied people and the scene has nobody talking, the
  studio gives that character a short in-character line.
- **`studio/engine/`**: the video engine from the first video, cleaned up into a package: doodle drawing at 2x
  with LANCZOS downsampling, stickmen with ~45 hats (nations, crown, Roman, Viking, pharaoh, knight, shako, ...),
  ~230 props, Natural Earth maps (Mercator, any region; Pacific islands wrap correctly), easing, blinking,
  bobbing, a smooth float camera clamped so it never shows black edges, captions (7 words max, double spaces,
  out of everyone's way), procedural music and sound effects, and the mix (voice first, music ~13 dB under
  with light ducking, then two-pass `loudnorm` to -15 LUFS / -1.5 dB true peak).
- **The JSON scene language** (`engine/schema.py`, `engine/compiler.py`): the AI never writes code. It writes
  JSON like `{"bg": {"type": "map", ...}, "elements": [{"type": "char", "kind": "roman", "at": "word:Caesar"}]}`.
  Every scene is auto-repaired (wrong names, off-screen positions, text in the caption area, labels on faces,
  somber-scene rules) and validated against a JSON Schema before rendering. If a scene is broken the AI is asked
  to fix it, and as a last resort a simple rule-based scene (that still follows the video's topic) is used.
  26 hand-made example scenes
  (`studio/prompts/examples.json`) teach the AI the style (writers with small free limits get a compact version of
  the instructions and the 3 most useful examples).
- **Rendering**: each scene is composited frame by frame and piped raw into ffmpeg (x264), one MP4 per scene in
  a process pool (CPU cores minus one), then concatenated with the final mix.
- **Providers** (`studio/providers/`): one interface per step, implementations registered in
  `providers/__init__.py`. Paid ones use the official SDKs (`anthropic`, `elevenlabs`, `higgsfield-client`).

## Development

```bash
python -m pytest                        # tests: TopoJSON, scene schema/compiler, captions, years, chapters, costs,
                                        # accounts/plans/Stripe webhooks, Shorts, the Claude Code MCP bridge
python -m studio.engine.measure_props   # after adding/changing a prop
cd web && npm install && npm run dev    # dashboard with hot reload (proxy to python -m studio serve)
cd web && npm run build                 # rebuild web/dist
```

`reference/` keeps the original starter engine examples (the Japan WW2 script and hand-written scenes).

## Licenses

Fredoka and Patrick Hand fonts: SIL Open Font License. Map data: Natural Earth (public domain) via
world-atlas (ISC). Only use music you have the rights to.
