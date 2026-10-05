# The Stickman Studio website on Netlify (free plan)

What's here, and why it's only the front door:

- `public/index.html`: the landing page (examples, how it works, free download, waitlist).
- **Waitlist**: a Netlify Form called `waitlist` (free plan: 100 sign-ups a month). See the emails in Netlify:
  your project → **Forms** → waitlist. Lots of sign-ups = time to open an online version.
- **Open my studio**: `netlify/functions/studio-link.mts` remembers where your studio is right now. Your studio runs
  on your own PC (`start.bat online`), behind a free Cloudflare link that changes every time it starts. While it
  runs, it tells this function its current link once a minute, so the button on your Netlify site always sends you
  to the right place. If your PC is off, the button says the studio is offline.

The video engine itself can't run on Netlify: it needs Python, ffmpeg and several minutes of CPU per video, and
Netlify only runs short JavaScript functions. That's why the studio stays on your PC.

## Connect your studio (one time)

1. In Netlify: your project → **Project configuration → Environment variables** → copy the value of
   `STUDIO_LINK_SECRET`.
2. In your studio (`start.bat`): **Settings → API keys → STUDIO_LINK_SECRET**, paste it, Save. Then
   **Settings → Video & workflow → Your Netlify website**: `https://<your-project>.netlify.app`, Save settings.
3. Start it with `start.bat online`. The window says "Your Netlify site's Open my studio button now points here".

## Deploying changes

The project's settings live in `netlify.toml` at the repo root (base folder `netlify-site`). Either:
- **From GitHub (recommended):** in Netlify, *Project configuration → Build & deploy → Link repository*, pick this
  repo and the branch. Every push then redeploys by itself.
- **From your PC:** `npm install -g netlify-cli`, then in the repo folder `netlify deploy --prod`.

## Test the function

```bash
cd netlify-site && npm install && npm test
```
