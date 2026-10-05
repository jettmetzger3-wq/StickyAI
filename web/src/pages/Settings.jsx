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
                {b.label}: {b.remaining?.toLocaleString()} of {b.limit?.toLocaleString()} {b.unit} left ({b.tier})
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

      <Card title="Writer">
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
          <Field label="Claude Code model (optional)" hint="Leave empty to use your Claude Code default.">
            <input className="w-full" value={s.llm_models.claude_cli || ""} onChange={(e) => set({ llm_models: { ...s.llm_models, claude_cli: e.target.value } })} />
          </Field>
          <Field label="Path to the claude command (optional)" hint="Only if it isn't found automatically.">
            <input className="w-full" value={s.claude_cli_path || ""} onChange={(e) => set({ claude_cli_path: e.target.value })} />
          </Field>
          <Field label="Ollama URL and model">
            <div className="flex gap-2">
              <input className="flex-1" value={s.ollama_url} onChange={(e) => set({ ollama_url: e.target.value })} />
              <input className="w-32" value={s.llm_models.ollama} onChange={(e) => set({ llm_models: { ...s.llm_models, ollama: e.target.value } })} />
            </div>
          </Field>
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
      {cfg.mode === "hosted" && <HostedCard s={s} set={set} />}

      <Card title="Video & workflow">
        <div className="grid gap-4 sm:grid-cols-2">
          <Toggle checked={s.autopilot} onChange={(v) => set({ autopilot: v })} label="Autopilot by default" hint="Off = pause after script, storyboard and voice." />
          <Toggle checked={s.share_copy} onChange={(v) => set({ share_copy: v })} label="Make a small share copy" />
          <Field label={`Music level: ${s.music_db} dB`} hint="Relative to full scale; the voice sits at about -1 dB, so -13 is ~12 dB under it.">
            <input type="range" min="-24" max="-6" step="1" value={s.music_db} onChange={(e) => set({ music_db: Number(e.target.value) })} className="w-full" />
          </Field>
          <Field label="Share copy max size (MB)">
            <input type="number" className="w-full" value={s.share_max_mb} onChange={(e) => set({ share_max_mb: Number(e.target.value) })} />
          </Field>
          <Field label="Render workers (0 = CPU cores minus one)">
            <input type="number" min="0" className="w-full" value={s.render_workers} onChange={(e) => set({ render_workers: Number(e.target.value) })} />
          </Field>
          <Field label="Port" hint="Takes effect after a restart.">
            <input type="number" className="w-full" value={s.port} onChange={(e) => set({ port: Number(e.target.value) })} />
          </Field>
        </div>
      </Card>
    </div>
  );
}
