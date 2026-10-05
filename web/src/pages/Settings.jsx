import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, ErrorBox, Field, Spinner, Toggle } from "../ui.jsx";
import VoicePicker from "./VoicePicker.jsx";

const STAGES = [
  ["transcript", "Transcript"],
  ["llm", "Writer"],
  ["voice", "Voice"],
  ["music", "Music"],
  ["image", "Thumbnail art"],
];

export default function Settings() {
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
