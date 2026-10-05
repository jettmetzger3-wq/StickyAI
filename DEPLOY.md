# Running Stickman Studio as a public website (hosted mode)

The same app that runs on your PC can run as a website where people sign up, make videos on a **Free** plan
and pay for **Pro** with Stripe. You pay for the AI tools (Anthropic, ElevenLabs) from your own accounts;
your customers pay you a subscription. See [PRICING.md](PRICING.md) for the cost math behind the default prices.

Nothing here is switched on by default. The app on your PC (`start.bat` / `start.sh`) stays exactly as it is.

## What changes in hosted mode

| | On your PC (local mode) | Website (hosted mode) |
|---|---|---|
| Who can use it | you, on localhost | anyone with an account |
| Paying for tools | you approve every estimate | the plan covers it; steps approve themselves under a per-video cost cap |
| Writer | Claude Code on your subscription, or the API | **Anthropic API only** (a personal Claude subscription can't serve other people) |
| Tools per video | you pick | the plan picks (Free: Kokoro, synth music; Pro: ElevenLabs voice, music, AI thumbnail art) |
| Settings, API keys | you | admins only |
| Projects | all yours | each user sees only their own |

## You need

- A Linux server with **4+ CPU cores and 8 GB RAM** (rendering is CPU-heavy; 8 cores renders about twice as fast).
  Any VPS works (Hetzner, DigitalOcean, Linode, ...). Disk: about 200 MB per finished 10-minute video.
- A **domain name** with an A record pointing at the server.
- **Docker** with the compose plugin (`curl -fsSL https://get.docker.com | sh`).
- An **Anthropic API key** (console.anthropic.com) for the writer.
- An **ElevenLabs API key** on a paid plan for Pro voices and music (commercial use needs a paid ElevenLabs plan).
- A **Stripe account** to take payments (you can start without it and give people Pro by hand).

## 1. Start it

```bash
git clone <your repo> stickman-studio && cd stickman-studio
cp .env.example .env
nano .env        # set STUDIO_DOMAIN, STUDIO_ADMIN_EMAIL, ANTHROPIC_API_KEY, ELEVENLABS_API_KEY
docker compose up -d --build
```

Caddy gets an HTTPS certificate for your domain automatically. Open `https://your-domain`, click
**Create account** and sign up with the `STUDIO_ADMIN_EMAIL` address: that account is the admin
(it gets the **Admin** and **Settings** pages and no limits).

Locked out or want another admin? On the server:

```bash
docker compose exec studio python -m studio admin you@example.com            # make an account admin
docker compose exec studio python -m studio admin you@example.com --password # and set its password
```

## 2. Set up Stripe

Do this in **test mode** first (the toggle at the top of the Stripe dashboard), then repeat with live keys.

1. **Product catalog → Add product** "Stickman Studio Pro", recurring, **$19.99 / month**. Copy the Price ID
   (`price_...`) into `STRIPE_PRICE_PRO`.
2. **Add product** "+10 Pro minutes", one-off, **$5.99**. Copy its Price ID into `STRIPE_PRICE_PACK`.
3. **Developers → API keys**: copy the secret key into `STRIPE_SECRET_KEY`.
4. **Developers → Webhooks → Add endpoint**: URL `https://your-domain/api/billing/webhook`, events
   `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`,
   `customer.subscription.deleted`. Copy the signing secret (`whsec_...`) into `STRIPE_WEBHOOK_SECRET`.
5. **Settings → Billing → Customer portal**: turn it on (lets people cancel, change cards and see invoices).
6. `docker compose up -d` to load the new keys. Buy Pro with the test card `4242 4242 4242 4242`, any future
   date, any CVC. Your account page should show Pro within a few seconds.

If you change the prices in Stripe, change the numbers in **Settings → Website (hosted mode)** too; those are
only what the Pricing page shows. Card details never touch your server: Stripe hosts the payment page.

## 3. Check the knobs

**Settings → Website (hosted mode)** (admins only):

- Free videos per month, the longest video per plan, Pro minutes per month, the minutes pack.
- Writer model per plan (Opus by default; Sonnet or Haiku make the Free plan much cheaper).
- **Tool cost cap per video** ($8): above this a run waits for an admin to approve it on the project page.
- **Videos made at the same time** (2): the rest wait in line and start automatically.
- **AI edits per video** (40), watermark text, sign-ups on/off.

The **Admin** page lists users with their usage. You can change someone's plan, add or remove Pro minutes,
reset a password, disable an account, and see this month's revenue and tool spend.

## Things to know

- **YouTube may block server IPs.** Remakes download captions and a low-res copy with yt-dlp, and YouTube
  sometimes asks datacenter IPs to "sign in". If that happens, export a `cookies.txt` from a browser where
  you're logged in to YouTube (with a throwaway account), copy it into the volume
  (`docker compose cp cookies.txt studio:/data/cookies.txt`) and set `STUDIO_YTDLP_COOKIES=/data/cookies.txt`.
  Topic videos don't touch YouTube at all.
- **Kokoro** downloads its voice model (~340 MB) into the data volume the first time it's used.
- **Calliope AI Shorts** are off on the website. Calliope only has an MCP connector, so the app reaches it
  through Claude Code. To offer it, install Claude Code in the container, add the connector
  (`claude mcp add --transport http calliope https://www.calliopelabs.co/api/mcp`), log in, run it with an
  `ANTHROPIC_API_KEY` (never a personal subscription), set your Calliope credit price in Settings, and turn on
  "Offer Calliope AI Shorts". Every video always gets the free stickman Short.
- **Keys:** keys in `.env` win over keys typed into the Settings page (those are kept in the data volume at
  `/data/.env`). Never commit `.env`.
- **Backups:** everything (accounts, usage, projects) is in the `studio-data` volume.
  `docker run --rm -v stickman-studio_studio-data:/d -v $PWD:/b alpine tar czf /b/backup.tgz -C /d .`
- **Updates:** `git pull && docker compose up -d --build`.
- **Logs:** `docker compose logs -f studio`.

## Your responsibilities as the operator

- Terms of service and a privacy policy (you store emails and the videos people make).
- Sales tax / VAT: Stripe Tax can calculate and collect it.
- Copyright: the app writes original scripts and draws its own scenes, and tells the AI never to copy the
  source's sentences, but people can still paste videos they have no right to remake. Say in your terms that
  users are responsible for what they make, and take down what you're asked to.
- The narration is an AI voice; every description says so, and YouTube asks creators to disclose it.
- The tools' own terms: Anthropic's commercial terms (API), ElevenLabs (paid plan for commercial use),
  Stripe, and Calliope if you turn it on.

## Running without Docker

```bash
pip install -r requirements.txt
cd web && npm ci && npm run build && cd ..
export STUDIO_MODE=hosted STUDIO_PUBLIC_URL=https://your-domain STUDIO_TRUST_PROXY=1 STUDIO_ADMIN_EMAIL=you@example.com
python -m studio serve --host 127.0.0.1 --port 8765     # behind nginx/Caddy that terminates HTTPS
```

Keep the app behind an HTTPS reverse proxy: the login cookie is marked Secure when `STUDIO_PUBLIC_URL` starts
with `https://`. Don't expose port 8765 directly.
