import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, ErrorBox, Field, Spinner, Toggle } from "../ui.jsx";
import VoicePicker from "./VoicePicker.jsx";
import { useConfig } from "../App.jsx";

const STAGES = [
  ["transcript", "Transcript"],
  ["llm", "Writer"],
  ["voice", "Voice"],
  ["music", "Music"],
  ["image", "Thumbnail art"],
  ["shorts", "Shorts teaser"],
];

function CalliopeCard({ s, set, onTested }) {
  const c = s.calliope || {};
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const setC = (patch) => set({ calliope: { ...c, ...patch } });
  async function test() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post("/api/calliope/test");
      setC({ connected: true, templates: r.templates });
      setMsg(`Connected. ${r.templates.length} Short templates found.`);
      onTested();
    } catch (e) {
      setC({ connected: false });
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card title="Calliope (AI Shorts & thumbnails)" actions={c.connected ? <Badge kind="done">connected</Badge> : <Badge kind="pending">not connected</Badge>}>
      <p className="mb-3 text-xs text-stone-500 dark:text-zinc-400">
        Calliope has no plain web API, only an MCP connector, so the app reaches it through Claude Code on this PC. One-time setup in a terminal:{" "}
        <code className="rounded bg-stone-100 px-1 dark:bg-zinc-800">claude mcp add --transport http calliope https://www.calliopelabs.co/api/mcp</code>, then run{" "}
        <code className="rounded bg-stone-100 px-1 dark:bg-zinc-800">claude</code>, type <code>/mcp</code> and log in to Calliope. AI Shorts use your Calliope credits
        (you approve Calliope's exact estimate first); the Claude Code calls use your Claude plan.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="MCP server name in Claude Code" hint="Tools are called mcp__<name>__<tool>.">
          <input className="w-full" value={c.server || "calliope"} onChange={(e) => setC({ server: e.target.value })} />
        </Field>
        <Field label="Short template">
          <select className="w-full" value={c.template_id || ""} onChange={(e) => setC({ template_id: e.target.value })}>
            <option value="">Most popular Short template</option>
            {(c.templates || []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} {t.visibility === "mine" ? "(mine)" : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Quality" hint="medium is cheapest, extra is the best.">
          <select className="w-full" value={c.quality || "medium"} onChange={(e) => setC({ quality: e.target.value })}>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="extra">extra</option>
          </select>
        </Field>
        <Field label="$ per 1,000 Calliope credits" hint="Only for dollar estimates. 0 = show credits only.">
          <input type="number" step="0.01" className="w-full" value={c.usd_per_1k_credits || 0} onChange={(e) => setC({ usd_per_1k_credits: Number(e.target.value) })} />
        </Field>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Button disabled={busy} onClick={test}>
          {busy && <Spinner />} Test connection (free)
        </Button>
        {msg && <span className="text-sm">{msg}</span>}
      </div>
    </Card>
  );
}

function HostedCard({ s, set }) {
  const h = s.hosted;
  const setH = (patch) => set({ hosted: { ...h, ...patch } });
  const setPlan = (id, patch) => setH({ plans: { ...h.plans, [id]: { ...h.plans[id], ...patch } } });
  const num = (v) => Number(v);
  return (
    <Card title="Website (hosted mode)">
      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <Toggle
          checked={!!h.paid_plans}
          onChange={(v) => setH({ paid_plans: v })}
          label="Paid plans (Pro + payments)"
          hint="Off: the site is free-only. Turn on when people are using it and your Stripe keys are in (DEPLOY.md)."
        />
        <Field label="Monthly AI budget for other people's videos ($)" hint="New videos wait until the 1st once it's used up. Your own videos don't count. 0 = no limit.">
          <input type="number" step="1" min="0" className="w-full" value={h.monthly_budget_usd} onChange={(e) => setH({ monthly_budget_usd: num(e.target.value) })} />
        </Field>
      </div>
      <p className="mb-3 text-xs text-stone-500 dark:text-zinc-400">
        Prices shown on the Pricing page (when paid plans are on). The amount people actually pay is the Price you created in Stripe, so keep them the same.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {["free", "pro"].map((id) => (
          <div key={id} className="space-y-2 rounded-xl bg-stone-100 p-3 dark:bg-zinc-800">
            <div className="font-semibold">{h.plans[id].name} plan</div>
            {id === "pro" && (
              <Field label="Price per month ($)">
                <input type="number" step="0.01" className="w-full" value={h.plans.pro.price_usd} onChange={(e) => setPlan("pro", { price_usd: num(e.target.value) })} />
              </Field>
            )}
            {id === "free" ? (
              <Field label="Free videos per month">
                <input type="number" className="w-full" value={h.plans.free.videos_per_month} onChange={(e) => setPlan("free", { videos_per_month: num(e.target.value) })} />
              </Field>
            ) : (
              <Field label="Pro minutes per month">
                <input type="number" className="w-full" value={h.plans.pro.pro_minutes} onChange={(e) => setPlan("pro", { pro_minutes: num(e.target.value) })} />
              </Field>
            )}
            <Field label="Longest video (minutes)">
              <input type="number" className="w-full" value={h.plans[id].max_minutes} onChange={(e) => setPlan(id, { max_minutes: num(e.target.value) })} />
            </Field>
            <Field label="Writer model" hint="Opus is the best; cheaper models cut the cost per video.">
              <select className="w-full" value={h.plans[id].llm_model} onChange={(e) => setPlan(id, { llm_model: e.target.value })}>
                <option value="claude-opus-5-5">Claude Opus 5.5</option>
                <option value="claude-sonnet-5-5">Claude Sonnet 5.5</option>
                <option value="claude-haiku-4-5">Claude Haiku 4.5</option>
              </select>
            </Field>
            <Toggle checked={h.plans[id].watermark} onChange={(v) => setPlan(id, { watermark: v })} label="Watermark" />
          </div>
        ))}
        <Field label={`Minutes pack: ${h.pack.minutes} min for $`}>
          <div className="flex gap-2">
            <input type="number" className="w-24" value={h.pack.minutes} onChange={(e) => setH({ pack: { ...h.pack, minutes: num(e.target.value) } })} />
            <input type="number" step="0.01" className="w-24" value={h.pack.price_usd} onChange={(e) => setH({ pack: { ...h.pack, price_usd: num(e.target.value) } })} />
          </div>
        </Field>
        <Field label="Tool cost cap per video ($)" hint="Steps auto-approve under this; above it the run waits for you.">
          <input type="number" step="0.5" className="w-full" value={h.max_usd_per_video} onChange={(e) => setH({ max_usd_per_video: num(e.target.value) })} />
        </Field>
        <Field label="Videos made at the same time">
          <input type="number" min="1" className="w-full" value={h.max_concurrent_runs} onChange={(e) => setH({ max_concurrent_runs: num(e.target.value) })} />
        </Field>
        <Field label="AI edits per video" hint="Beat rewrites and scene redraws (re-running Script/Storyboard counts 10).">
          <input type="number" className="w-full" value={h.ai_edits_per_video} onChange={(e) => setH({ ai_edits_per_video: num(e.target.value) })} />
        </Field>
        <Field label="Watermark text">
          <input className="w-full" value={h.watermark_text} onChange={(e) => setH({ watermark_text: e.target.value })} />
        </Field>
        <div className="space-y-2">
          <Toggle checked={h.allow_signup} onChange={(v) => setH({ allow_signup: v })} label="Allow new sign-ups" />
          <Toggle checked={h.ai_shorts} onChange={(v) => setH({ ai_shorts: v })} label="Offer Calliope AI Shorts to Pro users" hint="Needs Claude Code + Calliope on the server (see DEPLOY.md)." />
        </div>
      </div>
    </Card>
  );
}

function YouTubeCard() {
  const [st, setSt] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const back = (window.location.hash.split("youtube=")[1] || "").split("&")[0];
  const load = () => api.get("/api/youtube/status").then(setSt).catch(() => setSt(null));
  useEffect(() => {
    load();
  }, []);
  if (!st) return null;
  async function connect() {
    setErr(null);
    setBusy(true);
    try {
      const r = await api.post("/api/youtube/connect", {});
      window.location.href = r.url;
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  }
  async function disconnect() {
    await api.post("/api/youtube/disconnect", {});
    load();
  }
  const onPC = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  return (
    <Card title="YouTube channel (upload from the studio)">
      {back && back !== "connected" && <ErrorBox error={`YouTube sign-in: ${decodeURIComponent(back)}`} />}
      {st.connected ? (
        <div className="flex flex-wrap items-center gap-3">
          <Badge kind="done">connected</Badge>
          <span className="text-sm">{st.channel?.title || "your channel"}</span>
          <Button size="sm" onClick={disconnect}>Disconnect</Button>
        </div>
      ) : (
        <div className="space-y-2 text-sm text-stone-600 dark:text-zinc-400">
          <p>Free, one-time setup (about 10 minutes) so finished videos can go straight to your channel:</p>
          <ol className="list-decimal space-y-1 pl-5">
            <li>Go to console.cloud.google.com, create a project, and enable the <b>YouTube Data API v3</b>.</li>
            <li>Under "Google Auth Platform", set up the consent screen (External) and add your own Google account as a test user.</li>
            <li>Create an OAuth client of type <b>Desktop app</b> and copy its client ID and secret.</li>
            <li>Paste them above as <code>YOUTUBE_CLIENT_ID</code> and <code>YOUTUBE_CLIENT_SECRET</code>, then click Connect.</li>
          </ol>
          <p className="text-xs">
            It costs nothing. Google limits how many uploads per day the free API allows (plenty for a channel). Do the Connect step on this PC
            {onPC ? "" : " (not from your phone: Google sends you back to localhost)"}.
          </p>
          <ErrorBox error={err} />
          <Button variant="primary" onClick={connect} disabled={busy || !st.configured || !onPC}>
            {busy ? <Spinner /> : "Connect YouTube"}
          </Button>
          {!st.configured && <p className="text-xs text-amber-700">Add the client ID and secret first.</p>}
        </div>
      )}
    </Card>
  );
}

function FreeModel({ id, label, hint, s, set }) {
  const [models, setModels] = useState([]);
  const [msg, setMsg] = useState("");
  const load = () => {
    setMsg("loading…");
    api
      .get(`/api/llm/models?provider=${id}`)
      .then((d) => {
        setModels(d.models || []);
        setMsg(d.error ? d.error : d.models?.length ? `${d.models.length} models` : "add the key first");
      })
      .catch((e) => setMsg(String(e.message || e)));
  };
  return (
    <Field label={label} hint={hint}>
      <div className="flex gap-2">
        <input
          className="flex-1"
          list={`models-${id}`}
          value={s.llm_models[id] || ""}
          onChange={(e) => set({ llm_models: { ...s.llm_models, [id]: e.target.value } })}
        />
        <Button size="sm" variant="ghost" onClick={load}>List</Button>
      </div>
      <datalist id={`models-${id}`}>
        {models.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
      {msg && <span className="text-xs text-stone-500 dark:text-zinc-400">{msg}</span>}
    </Field>
  );
}

const TASKS = [
  ["script", "Writing the script", "The most important job. Your best writer."],
  ["factcheck", "Fact-checking", "Claude Code can search the web for this; the others check from memory."],
  ["watch", "Watching the source video", "Needs a writer that can see images (Claude, Gemini)."],
  ["props", "Designing extra props", "One request per video."],
  ["storyboard", "Drawing the scenes", "The biggest job: most of the AI usage goes here."],
  ["package", "Titles, description, thumbnail text", "Short and easy: a lighter model does it just as well."],
  ["short", "Picking the Short's best moment", "Short and easy."],
];
const MODEL_LABEL = { "": "Studio default", default: "My Claude Code default", opus: "Opus 5.5", sonnet: "Sonnet 5.5", haiku: "Haiku 4.5" };
const SAVER_MODELS = {
  off: {},
  balanced: { short: "haiku" },
  max: { props: "haiku", package: "haiku", short: "haiku" },
};

function WriterCard({ s, set, catalog }) {
  const llms = (catalog && catalog.llm) || [];
  const main = s.providers.llm;
  const tw = s.task_writers || {};
  const tm = s.claude_task_models || {};
  const saver = s.plan_saver || "balanced";
  const mainModel = s.llm_models?.claude_cli || "sonnet";
  const byId = Object.fromEntries(llms.map((p) => [p.id, p]));
  const label = (p) => `${p.label}${p.paid ? " (paid)" : ""}${p.available ? "" : " (not set up)"}`;
  return (
    <Card title="Writer: which AI does what">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Main writer" hint="Writes everything unless you hand a job to another AI below. New videos start with it.">
          <select className="w-full" value={main} onChange={(e) => set({ providers: { ...s.providers, llm: e.target.value } })}>
            {llms.map((p) => (
              <option key={p.id} value={p.id}>{label(p)}</option>
            ))}
          </select>
        </Field>
        <Field label="If my Claude plan runs out mid-video" hint="Only free writers can step in, so nothing starts costing money on its own. Claude is used again as soon as your plan allows.">
          <select className="w-full" value={s.backup_writer || "auto"} onChange={(e) => set({ backup_writer: e.target.value })}>
            <option value="auto">Switch to Gemini (or Groq if that's the key I have)</option>
            <option value="gemini">Switch to Gemini</option>
            <option value="groq">Switch to Groq</option>
            <option value="ollama">Switch to Ollama (on this PC)</option>
            <option value="off">Stop and wait for me</option>
          </select>
        </Field>
      </div>

      <div className="mt-4 text-sm font-medium">Who does what</div>
      <p className="mb-2 text-xs text-stone-500 dark:text-zinc-400">
        Hand any job to a different AI. A paid writer always shows its price first and waits for your OK.
      </p>
      <div className="space-y-2">
        {TASKS.map(([id, name, hint]) => {
          const who = tw[id] || "";
          const eff = who || main;
          const isClaude = eff === "claude_cli";
          const auto = SAVER_MODELS[saver]?.[id];
          return (
            <div key={id} className="grid items-center gap-2 rounded-lg bg-stone-50 p-2 sm:grid-cols-[1fr_14rem_11rem] dark:bg-zinc-800/60">
              <div>
                <div className="text-sm">{name}</div>
                <div className="text-xs text-stone-500 dark:text-zinc-400">{hint}</div>
              </div>
              <select value={who} onChange={(e) => set({ task_writers: { ...tw, [id]: e.target.value } })}>
                <option value="">Main writer ({byId[main]?.short || byId[main]?.label || main})</option>
                {llms.map((p) => (
                  <option key={p.id} value={p.id}>{label(p)}</option>
                ))}
              </select>
              {isClaude ? (
                <select value={tm[id] || ""} onChange={(e) => set({ claude_task_models: { ...tm, [id]: e.target.value } })}
                  title="Which Claude model Claude Code uses for this job">
                  {Object.entries(MODEL_LABEL).map(([v, l]) => (
                    <option key={v} value={v}>{v === "" ? `${l} (${MODEL_LABEL[auto || mainModel] || "Sonnet 5.5"})` : l}</option>
                  ))}
                </select>
              ) : (
                <span className="text-xs text-stone-400">{byId[eff]?.paid ? "paid: you approve the price" : "free"}</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Field label="Claude plan saver" hint={
          saver === "off" ? "Every Claude job uses the main model, 8 scenes per request." :
          saver === "max" ? "Stretches your plan furthest: the lightest model (Haiku 4.5) for props, titles and the Short pick, bigger batches, fewer example scenes. Scenes can get a little plainer." :
          "Same quality: everything runs on the main model except the small Short-picking job (Haiku 4.5); scenes that still need the full scene writer go 12 per request and the shared instructions are cached after the first request."
        }>
          <select className="w-full" value={saver} onChange={(e) => set({ plan_saver: e.target.value })}>
            <option value="balanced">Balanced (recommended, same quality)</option>
            <option value="max">Maximum savings</option>
            <option value="off">Off</option>
          </select>
        </Field>
        <Field label="Claude model for everything" hint="Sonnet 5.5 is much lighter on your plan and nearly as good as Opus for this. Pick Opus for the very best, or hand a single job to Opus in the table above.">
          <select className="w-full" value={s.llm_models.claude_cli || ""} onChange={(e) => set({ llm_models: { ...s.llm_models, claude_cli: e.target.value } })}>
            <option value="">Sonnet 5.5 (recommended)</option>
            <option value="opus">Opus 5.5 (best quality, uses more)</option>
            <option value="haiku">Haiku 4.5 (lightest, plainer scenes)</option>
            <option value="default">Whatever my Claude Code is set to</option>
          </select>
        </Field>
      </div>
    </Card>
  );
}

function GenerationCard({ s, set }) {
  const [cache, setCache] = useState(null);
  const refresh = () => api.get("/api/modes").then((d) => setCache(d.cache)).catch(() => {});
  useEffect(() => {
    refresh();
  }, []);
  const mode = s.gen_mode || "normal";
  return (
    <Card title="How much AI a video uses">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field
          label="Default quality mode"
          hint={
            mode === "fast"
              ? "Fast: for drafts and tests. No research, no fact-check, no extra props; the AI only writes the script and a compact scene plan."
              : mode === "deep"
              ? "Deep: topic research, web fact-check, richer scene plans and an AI fix for scenes the review could not fix. Uses the most."
              : "Normal: script, a compact scene plan, the full scene writer only for odd scenes, a local review. Low usage, high quality."
          }
        >
          <select className="w-full" value={mode} onChange={(e) => set({ gen_mode: e.target.value })}>
            <option value="fast">Fast</option>
            <option value="normal">Normal (recommended)</option>
            <option value="deep">Deep</option>
          </select>
        </Field>
        <Field label="How scenes are drawn" hint="Director: the AI picks a scene pattern and details, the studio builds it (far fewer tokens). Classic: the AI writes every scene in full (the old way).">
          <select className="w-full" value={s.storyboard_engine || "director"} onChange={(e) => set({ storyboard_engine: e.target.value })}>
            <option value="director">Director (recommended)</option>
            <option value="classic">Classic (old way, uses a lot more)</option>
          </select>
        </Field>
        <Toggle checked={s.cache_enabled !== false} onChange={(v) => set({ cache_enabled: v })} label="Reuse what the AI already made" hint="Same question, same answer: no second charge to your plan. Topic research and drawn props are reused by later videos." />
        <div className="text-sm">
          <div className="font-medium">Saved so far</div>
          {cache ? (
            <p className="text-xs text-stone-500 dark:text-zinc-400">
              {cache.total.entries} items ({(cache.total.kb / 1024).toFixed(1)} MB): {cache.llm.entries} AI answers, {cache.plans.entries} scene plans, {cache.research.entries} topic briefs, {cache.props.entries} props.
            </p>
          ) : (
            <Spinner />
          )}
          <Button
            size="sm"
            className="mt-1"
            onClick={async () => {
              if (confirm("Delete everything the studio saved (AI answers, plans, research, drawn props)? Videos are not touched.")) {
                await api.del("/api/cache");
                refresh();
              }
            }}
          >
            Clear saved answers
          </Button>
        </div>
      </div>
    </Card>
  );
}
const HAT_CHOICES = ["cap", "tophat", "bowler", "beret", "headphones", "glasses", "graduate", "cowboy", "pirate", "wizard", "crown", "chef", "hardhat", "bicorne", "viking", "headband", "none"];

function MascotCard({ s, set }) {
  const m = { on: true, name: "Sticky", kind: "cap", hat_color: "red", coat: "", look: "", intro: true, outro: true, cameos: true, ...(s.mascot || {}) };
  const setM = (patch) => set({ mascot: { ...m, ...patch } });
  return (
    <Card title="Channel mascot">
      <p className="mb-3 text-xs text-stone-500 dark:text-zinc-400">
        Your channel's own host stickman. It says hi right after the hook, signs off at the end with a subscribe button, and pops up in the corner
        to react to the biggest moments ("WHAT?!", "Oof."). Its lines are normal beats in the Script tab, so you can edit or delete them per video.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Toggle checked={m.on !== false} onChange={(v) => setM({ on: v })} label="Use the mascot in new videos" />
        <Field label="Name">
          <input className="w-full" value={m.name} maxLength={24} onChange={(e) => setM({ name: e.target.value })} />
        </Field>
        <Field label="Hat">
          <select className="w-full" value={m.kind} onChange={(e) => setM({ kind: e.target.value })}>
            {HAT_CHOICES.map((h) => <option key={h} value={h}>{h}</option>)}
          </select>
        </Field>
        <Field label="Hat color" hint="A color name (red, navy, gold...) or #rrggbb">
          <input className="w-full" value={m.hat_color || ""} onChange={(e) => setM({ hat_color: e.target.value })} />
        </Field>
        <Field label="Coat color (optional)" hint="Empty = classic stick body">
          <input className="w-full" value={m.coat || ""} onChange={(e) => setM({ coat: e.target.value })} />
        </Field>
        <Field label="Face">
          <select className="w-full" value={m.look || ""} onChange={(e) => setM({ look: e.target.value })}>
            <option value="">Clean-shaven</option>
            <option value="mustache">Mustache</option>
            <option value="beard">Beard</option>
          </select>
        </Field>
        <Toggle checked={m.intro !== false} onChange={(v) => setM({ intro: v })} label="Says hi after the hook" />
        <Toggle checked={m.outro !== false} onChange={(v) => setM({ outro: v })} label="Signs off at the end" />
        <Toggle checked={m.cameos !== false} onChange={(v) => setM({ cameos: v })} label="Pops in at big moments" hint="At most once every 7 scenes, on the biggest reaction word." />
        <div />
        <Field label="Greeting" hint="{name} and {title} are filled in.">
          <input className="w-full" value={m.intro_line || ""} onChange={(e) => setM({ intro_line: e.target.value })} />
        </Field>
        <Field label="Sign-off" hint="{name} and {title} are filled in.">
          <input className="w-full" value={m.outro_line || ""} onChange={(e) => setM({ outro_line: e.target.value })} />
        </Field>
      </div>
      <ProfilePicture />
    </Card>
  );
}

// The mascot as a YouTube profile picture. Drawn on this PC from the SAVED mascot settings (no AI, no cost).
function ProfilePicture() {
  const [backdrop, setBackdrop] = useState("sunburst");
  const [rev, setRev] = useState(0);
  const url = (extra = "") => `/api/mascot/profile-picture?size=800&backdrop=${backdrop}${extra}&v=${rev}`;
  return (
    <div className="mt-5 flex flex-wrap items-center gap-4 border-t border-stone-200 pt-4 dark:border-zinc-700">
      <img src={url()} alt="Mascot profile picture" className="h-28 w-28 rounded-full border border-stone-300 object-cover dark:border-zinc-600" />
      <div className="min-w-[14rem] flex-1">
        <div className="text-sm font-medium">YouTube profile picture</div>
        <p className="mb-2 text-xs text-stone-500 dark:text-zinc-400">
          Your mascot as an 800x800 picture. YouTube shows it as a circle, so everything important sits in the middle. Uses the saved mascot above (save first
          after changing the hat), drawn on this PC, no AI and no cost.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select value={backdrop} onChange={(e) => setBackdrop(e.target.value)}>
            <option value="sunburst">Sunny rays</option>
            <option value="sky">Sky blue rays</option>
            <option value="paper">Paper</option>
            <option value="dark">Dark</option>
          </select>
          <Button size="sm" onClick={() => setRev(rev + 1)}>Refresh</Button>
          <a
            className="inline-flex items-center justify-center rounded-lg bg-amber-500 px-2.5 py-1 text-xs font-medium text-zinc-950 shadow-sm transition hover:bg-amber-400"
            href={url("&download=true")}
            download="mascot-profile-picture.png"
          >
            Download PNG
          </a>
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const cfg = useConfig();
  const [s, setS] = useState(null);
  const [secrets, setSecrets] = useState({});
  const [catalog, setCatalog] = useState(null);
  const [notes, setNotes] = useState({});
  const [keyInputs, setKeyInputs] = useState({});
  const [pron, setPron] = useState([]);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(null);
  const [balances, setBalances] = useState(null);

  const load = () =>
    api.get("/api/settings").then((d) => {
      setS(d.settings);
      setSecrets(d.secrets);
      setPron(Object.entries(d.settings.pronunciations || {}));
    });
  useEffect(() => {
    load();
    api.get("/api/providers").then((d) => {
      setCatalog(d.catalog);
      setNotes(d.notes || {});
    });
    api.get("/api/balances").then(setBalances).catch(() => {});
  }, []);
  if (!s) return <Spinner />;

  const set = (patch) => setS({ ...s, ...patch });
  async function save() {
    setErr(null);
    try {
      const body = { ...s, pronunciations: Object.fromEntries(pron.filter(([k]) => k.trim())) };
      const r = await api.put("/api/settings", body);
      setS(r.settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setErr(e.message);
    }
  }
  async function saveKey(name, value) {
    const r = await api.put("/api/secrets", { name, value });
    setSecrets(r.secrets);
    setKeyInputs({ ...keyInputs, [name]: "" });
    api.get("/api/providers").then((d) => setCatalog(d.catalog));
  }

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="flex items-center gap-2">
          {saved && <span className="text-sm text-emerald-600">Saved</span>}
          <Button variant="primary" onClick={save}>
            Save settings
          </Button>
        </div>
      </div>
      <ErrorBox error={err} />

      <Card title="API keys (optional, for the paid tools)">
        <p className="mb-3 text-xs text-stone-500 dark:text-zinc-400">
          Keys are saved in the <code>.env</code> file next to the app (it's in .gitignore) and never shown again or sent anywhere except the provider.
          Free mode needs none of these.
        </p>
        <div className="space-y-3">
          {Object.entries(secrets).map(([name, info]) => (
            <div key={name} className="grid items-center gap-2 sm:grid-cols-[14rem_1fr_auto_auto]">
              <div>
                <div className="font-mono text-xs">{name}</div>
                <div className="text-xs text-stone-500 dark:text-zinc-400">{info.label}</div>
              </div>
              <input
                type="password"
                autoComplete="off"
                placeholder={info.set ? "•••••••• (saved)" : "paste key"}
                value={keyInputs[name] || ""}
                onChange={(e) => setKeyInputs({ ...keyInputs, [name]: e.target.value })}
              />
              <Button size="sm" disabled={!keyInputs[name]} onClick={() => saveKey(name, keyInputs[name])}>
                Save
              </Button>
              {info.set ? (
                <Button size="sm" variant="ghost" onClick={() => confirm(`Remove ${name}?`) && saveKey(name, "")}>
                  Remove
                </Button>
              ) : (
                <span />
              )}
            </div>
          ))}
        </div>
        {balances && Object.keys(balances.balances || {}).length > 0 && (
          <div className="mt-4 rounded-lg bg-stone-100 p-3 text-sm dark:bg-zinc-800">
            {Object.entries(balances.balances).map(([id, b]) => (
              <div key={id}>
                {b.label}: {b.text || `${b.remaining?.toLocaleString()} of ${b.limit?.toLocaleString()} ${b.unit} left (${b.tier})`}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Tools available on this PC">
        {catalog &&
          STAGES.map(([st, label]) => (
            <div key={st} className="mb-3">
              <div className="mb-1 text-sm font-medium">{label}</div>
              <div className="space-y-1">
                {catalog[st].map((p) => (
                  <div key={p.id} className="flex items-start gap-2 text-sm">
                    <span className={p.available ? "text-emerald-600" : "text-stone-400"}>{p.available ? "●" : "○"}</span>
                    <span className="flex-1">
                      {p.label} <Badge kind={p.paid ? "paid" : "free"}>{p.paid ? "paid" : "free"}</Badge>
                      {!p.available && <span className="block text-xs text-stone-500 dark:text-zinc-400">{p.reason}</span>}
                    </span>
                    <label className="flex items-center gap-1 text-xs">
                      <input
                        type="radio"
                        name={`def-${st}`}
                        checked={s.providers[st] === p.id}
                        onChange={() => set({ providers: { ...s.providers, [st]: p.id } })}
                      />
                      default
                    </label>
                  </div>
                ))}
              </div>
            </div>
          ))}
        <p className="text-xs text-stone-500 dark:text-zinc-400">{notes.openart}</p>
        <p className="mt-1 text-xs text-stone-500 dark:text-zinc-400">{notes.mcp}</p>
      </Card>

      <WriterCard s={s} set={set} catalog={catalog} />

      <GenerationCard s={s} set={set} />

      <Card title="Writer models">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Anthropic API model" hint="Opus 5.5: $4 / $20 per million tokens. Sonnet 5.5: $2 / $10. Haiku 4.5: $1 / $5.">
            <select
              className="w-full"
              value={s.llm_models.anthropic}
              onChange={(e) => set({ llm_models: { ...s.llm_models, anthropic: e.target.value } })}
            >
              <option value="claude-opus-5-5">Claude Opus 5.5 (best)</option>
              <option value="claude-sonnet-5-5">Claude Sonnet 5.5 (cheaper)</option>
              <option value="claude-haiku-4-5">Claude Haiku 4.5 (cheapest)</option>
            </select>
          </Field>
          <Field label="Path to the claude command (optional)" hint="Only if it isn't found automatically.">
            <input className="w-full" value={s.claude_cli_path || ""} onChange={(e) => set({ claude_cli_path: e.target.value })} />
          </Field>
          <FreeModel id="gemini" label="Gemini model (free key)" s={s} set={set}
            hint="gemini-flash-latest: best free quality. gemini-flash-lite-latest: more free requests per day, plainer scenes." />
          <FreeModel id="groq" label="Groq model (free key)" s={s} set={set}
            hint="openai/gpt-oss-120b is the strongest free model. Free plan: ~8,000 tokens a minute, 1,000 requests a day." />
          <Field label="Ollama URL and model">
            <div className="flex gap-2">
              <input className="flex-1" value={s.ollama_url} onChange={(e) => set({ ollama_url: e.target.value })} />
              <input className="w-32" value={s.llm_models.ollama} onChange={(e) => set({ llm_models: { ...s.llm_models, ollama: e.target.value } })} />
            </div>
          </Field>
        </div>
        <div className="mt-3 rounded-lg bg-stone-100 p-3 text-xs text-stone-600 dark:bg-zinc-800 dark:text-zinc-300">
          <b>Free writers without your Claude plan:</b> get a free Gemini key at{" "}
          <a className="underline" href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>{" "}
          or a free Groq key at{" "}
          <a className="underline" href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys</a>,
          paste it under API keys above, then pick it as the default writer. No card is needed. Keep the Gemini key in a
          Google project <b>without billing</b> and stay on Groq's free plan, and they can never cost money. Free limits:
          when a minute's limit is hit the studio waits; when the day's limit is used up the video pauses and you press
          Resume the next day. Google may use free-tier prompts to improve its products.
        </div>
      </Card>

      <Card title="Default voice">
        <VoicePicker
          provider="kokoro"
          settings={s}
          value={s.voice}
          onChange={(v) => set({ voice: { ...s.voice, ...v } })}
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Field label="ElevenLabs voice ID" hint="Default: George (JBFqnCBsd6RMkjVDRZzb)">
            <input className="w-full" value={s.voice.elevenlabs_voice_id} onChange={(e) => set({ voice: { ...s.voice, elevenlabs_voice_id: e.target.value } })} />
          </Field>
          <Field label="ElevenLabs model" hint="Flash v2.5 ≈ 0.5 credits per character. Multilingual v2 ≈ 1 credit per character.">
            <select className="w-full" value={s.voice.elevenlabs_model} onChange={(e) => set({ voice: { ...s.voice, elevenlabs_model: e.target.value } })}>
              <option value="eleven_flash_v2_5">eleven_flash_v2_5 (cheap, fast)</option>
              <option value="eleven_turbo_v2_5">eleven_turbo_v2_5</option>
              <option value="eleven_multilingual_v2">eleven_multilingual_v2 (richer)</option>
            </select>
          </Field>
          <Field label="$ per 1,000 ElevenLabs credits" hint="Only used to show dollar estimates. 0.22 ≈ Creator plan ($22 for 100k). Set it to match your plan.">
            <input type="number" step="0.01" className="w-full" value={s.elevenlabs_usd_per_1k_credits} onChange={(e) => set({ elevenlabs_usd_per_1k_credits: Number(e.target.value) })} />
          </Field>
        </div>
      </Card>

      <Card title="Pronunciation dictionary" actions={<Button size="sm" onClick={() => setPron([...pron, ["", ""]])}>+ Add</Button>}>
        <p className="mb-2 text-xs text-stone-500 dark:text-zinc-400">
          How the voice should say tricky words (per word, case-insensitive). Captions keep the original spelling. Built in: Manchukuo, Meiji, Leyte, Nanjing,
          Mukden, Guadalcanal, Saipan, Hirohito… Years like 1941 are read as "nineteen forty-one" automatically.
        </p>
        <div className="space-y-2">
          {pron.map(([k, v], i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <input placeholder="Word" value={k} onChange={(e) => setPron(pron.map((p, j) => (j === i ? [e.target.value, p[1]] : p)))} />
              <input placeholder="Say it like" value={v} onChange={(e) => setPron(pron.map((p, j) => (j === i ? [p[0], e.target.value] : p)))} />
              <Button size="sm" variant="ghost" onClick={() => setPron(pron.filter((_, j) => j !== i))}>
                ×
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Spending">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Limit per video ($)" hint="Even after you approve the estimate, a run pauses and asks again before one video's spending goes over this.">
            <input type="number" step="0.5" min="0" className="w-full" value={s.max_usd_per_video} onChange={(e) => set({ max_usd_per_video: Number(e.target.value) })} />
          </Field>
          <Toggle
            checked={s.reuse_music_beds !== false}
            onChange={(v) => set({ reuse_music_beds: v })}
            label="Reuse ElevenLabs music between videos"
            hint="Each mood (fun, tense, somber) is composed and paid for once, then reused."
          />
        </div>
      </Card>

      <CalliopeCard s={s} set={set} onTested={() => api.get("/api/providers").then((d) => setCatalog(d.catalog))} />
      {(cfg.mode !== "hosted" || cfg.private) && <YouTubeCard />}
      {cfg.mode === "hosted" && <HostedCard s={s} set={set} />}

      <MascotCard s={s} set={set} />

      <Card title="Video & workflow">
        <div className="grid gap-4 sm:grid-cols-2">
          <Toggle checked={s.autopilot} onChange={(v) => set({ autopilot: v })} label="Autopilot by default" hint="Off = pause after script, storyboard and voice." />
          <Toggle checked={s.share_copy} onChange={(v) => set({ share_copy: v })} label="Make a small share copy" />
          <Toggle checked={s.transitions !== false} onChange={(v) => set({ transitions: v })} label="Transitions between scenes" hint="Slides, wipes, zooms and fades instead of hard cuts." />
          <Toggle
            checked={(s.caption_style || "highlight") === "highlight"}
            onChange={(v) => set({ caption_style: v ? "highlight" : "plain" })}
            label="Highlight the spoken word in captions"
          />
          <Toggle checked={s.ambience !== false} onChange={(v) => set({ ambience: v })} label="Background sounds for each place" hint="Waves at sea, crowds in streets, wind in the mountains, battle noise..." />
          <Toggle checked={s.action_sounds !== false} onChange={(v) => set({ action_sounds: v })} label="Footsteps, jumps and cheers" />
          <Toggle checked={s.talk_blips !== false} onChange={(v) => set({ talk_blips: v })} label='Little "blah blah" sounds when characters talk' />
          <Toggle checked={s.music_styles !== false} onChange={(v) => set({ music_styles: v })} label="Music that fits the moment" hint="Free synth: epic drums for battles, mystery for secrets, a fanfare for victories, sad strings for sad parts." />
          <Toggle checked={s.music_stings !== false} onChange={(v) => set({ music_stings: v })} label="Musical hits on big moments" hint='A fanfare when someone wins, "dun dun DUN" on a twist, a sad trombone when a plan flops.' />
          <Toggle checked={s.mood_narration !== false} onChange={(v) => set({ mood_narration: v })} label="Narrator follows the mood" hint="Slower with a pause for sad parts, a little faster for jokes." />
          <Toggle checked={s.voice_polish !== false} onChange={(v) => set({ voice_polish: v })} label="Polish the narration" hint="Removes low rumble, makes words a bit clearer and evens out loud and quiet parts, like a YouTube narrator's mic." />
          <Toggle checked={s.auto_reactions !== false} onChange={(v) => set({ auto_reactions: v })} label="Faces react to the words" hint='Characters look shocked on "suddenly", furious on "betrayed", smug on "won", crushed on "lost", right on the word.' />
          <Toggle checked={s.auto_camera !== false} onChange={(v) => set({ auto_camera: v })} label="Smart camera" hint="A close-up cuts in exactly on the punchline word, and wide places get a slow pan." />
          <Toggle checked={s.fact_check !== false} onChange={(v) => set({ fact_check: v })} label="Fact-check the script" hint="After writing, the writer double-checks uncertain facts (with web search on Claude Code) and fixes mistakes." />
          <Toggle
            checked={s.custom_props !== false}
            onChange={(v) => set({ custom_props: v })}
            label="Draw extra props for each video"
            hint="Before the storyboard, the writer designs a few props this story needs (one more AI call, free on Claude Code)."
          />
          <Field label={`Music level: ${s.music_db} dB`} hint="Relative to full scale; the voice sits at about -1 dB, so -13 is ~12 dB under it.">
            <input type="range" min="-24" max="-6" step="1" value={s.music_db} onChange={(e) => set({ music_db: Number(e.target.value) })} className="w-full" />
          </Field>
          <Field label="Share copy max size (MB)">
            <input type="number" className="w-full" value={s.share_max_mb} onChange={(e) => set({ share_max_mb: Number(e.target.value) })} />
          </Field>
          <Field label="Render workers (0 = CPU cores minus one)">
            <input type="number" min="0" className="w-full" value={s.render_workers} onChange={(e) => set({ render_workers: Number(e.target.value) })} />
          </Field>
          <Field label="Your Netlify website (optional)" hint='e.g. https://stickman-studio.netlify.app. While "start.bat online" runs, its "Open my studio" button sends you here. Also add STUDIO_LINK_SECRET under API keys.'>
            <input className="w-full" placeholder="https://your-site.netlify.app" value={s.netlify_site || ""} onChange={(e) => set({ netlify_site: e.target.value.trim() })} />
          </Field>
          <Field label="Port" hint="Takes effect after a restart.">
            <input type="number" className="w-full" value={s.port} onChange={(e) => set({ port: Number(e.target.value) })} />
          </Field>
        </div>
      </Card>
    </div>
  );
}
