# Pricing: what a video costs to make, and why Pro is $19.99

These are the numbers behind the default plans in hosted mode. All of them can be changed in
**Settings → Website (hosted mode)** (and the real price people pay is the Price you create in Stripe).

> **Right now the website is free-only.** Paid plans are off by default (Settings → Website → Paid plans), so
> people only see the Free plan, and a monthly AI budget ($20 by default) caps what free videos can cost you.
> Everything below is ready for the day you switch Pro on.
>
> On your own PC there are no plans at all: you make as many videos as you want, free with the free tools.

## What the tools cost per video

Estimates from the app's own cost formulas (they include headroom for the model's thinking tokens, so real
bills usually come in lower). Writer: Claude Opus 5.5 at $4 / $20 per million input / output tokens.

| Step | 3-minute video | 10-minute video |
|---|---|---|
| Watch the source video (YouTube remakes) | ~$0.13 | ~$0.13 |
| Script | ~$0.11 | ~$0.25 |
| Storyboard (one scene per line, the biggest part) | ~$0.58 | ~$1.94 |
| YouTube package (titles, description, chapters, tags) | ~$0.06 | ~$0.07 |
| Short (picking the moment) | ~$0.03 | ~$0.03 |
| **Writer total** | **~$0.80–0.90** | **~$2.30–2.45** |
| ElevenLabs voice (Flash v2.5, ~0.5 credits per character) | ~1,350 credits ≈ $0.30 | ~4,500 credits ≈ $1.00 |
| ElevenLabs music | paid once per mood, then reused | same |
| AI thumbnail background | ~$0.05–0.10 | ~$0.05–0.10 |
| **Pro video total** | **~$1.25** | **~$3.50** (≈ $0.35 per finished minute) |

ElevenLabs credits are priced at $0.22 per 1,000 (Creator plan). Bigger ElevenLabs plans are cheaper per credit.
Kokoro (the free voice), the synth music, the built-in thumbnail and the stickman Short cost nothing to run
except server time.

## The plans

| | Free | Pro | Minutes pack |
|---|---|---|---|
| Price | $0 | **$19.99 / month** | **$5.99** one time |
| What you get | 2 videos a month, up to 3 minutes | 30 Pro minutes a month, videos up to 15 minutes | +10 Pro minutes, never expire |
| Tools | Claude writer, Kokoro voice, synth music, built-in thumbnail, watermark | ElevenLabs voice, AI music, AI thumbnail art, no watermark | same as Pro |
| Worst-case tool cost | ~$1.80 per user per month | ~$10.50 (all 30 minutes used) | ~$3.50 |
| Stripe fee (2.9% + $0.30) | – | ~$0.88 | ~$0.47 |
| **Margin in the worst case** | –$1.80 (marketing cost) | **~$8.60 (≈ 43%)** | **~$2.00 (≈ 34%)** |

Why $19.99:
- It covers the worst case (a subscriber using every minute every month) with roughly 40% left for the server,
  support and refunds. Most subscribers use part of their minutes, so the typical margin is higher.
- It sits where people already pay for AI video and voice tools ($20–30 a month), and 30 minutes is three
  full 10-minute videos, a realistic month for a small channel.
- "Pro minutes" track the real cost driver (finished video length), so a heavy user can't cost more than
  they paid: when the minutes run out they buy a pack or wait for the 1st.

## The safety nets

- **Minutes are reserved up front** and the unused part is returned when the video is finished. A run can't
  produce a video much longer than it reserved (+25%).
- **Cost cap per video** (default $8): steps approve themselves only while a video's real tool spending stays
  under it. Above that the run waits for the admin.
- **AI edits per video** (default 40): rewriting a line or redrawing a scene calls the AI again, so each video
  gets a budget of them. Re-running the Script or Storyboard step counts as 10.
- **Videos at the same time** (default 2): rendering uses every CPU core; extra videos wait in line.
- **Sign-ups per network** (default 3 a day) make it harder to farm free videos.

## Knobs if the numbers don't work for you

- Free plan writer → Claude Sonnet 5.5 roughly halves the free plan's cost; Haiku 4.5 cuts it by about 75%.
  Opus is the default because the storyboard (turning lines into funny scenes) is where quality shows most.
- Free videos per month, the longest free video, Pro minutes and the pack size are all in Settings.
- A cheaper ElevenLabs plan per credit (Pro, Scale) lowers the voice cost; music is already paid once per mood.
