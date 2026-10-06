import { useEffect, useMemo, useRef, useState } from "react";
import { api, fmtCost, fmtTime, sumCosts } from "../api.js";
import { Badge, Button, Card, cx, ErrorBox, Field, Spinner, Toggle } from "../ui.jsx";
import { go, useConfig } from "../App.jsx";
import VoicePicker from "./VoicePicker.jsx";

const STAGE_ORDER = ["transcript", "llm", "voice", "music", "image", "shorts"];
const STAGE_NAMES = { transcript: "Transcript", llm: "Writer", voice: "Voice", music: "Music", image: "Thumbnail art", shorts: "Shorts teaser" };
const EST_LABELS = {
  source: "Watch source",
  script: "Script",
  storyboard: "Storyboard",
  voice: "Voice",
  mix: "Music",
  package: "Title & thumbnail",
  shorts: "Shorts teaser",
};

// Hosted website, normal user: pick Free or Pro; the plan decides the tools and the allowance pays for it.
function PlanPicker({ cfg, tier, setTier, minutes }) {
  const u = cfg.user.usage;
  const plans = cfg.pricing.plans;
  const freeLeft = Math.max(0, u.free_videos_limit - u.free_videos_used);
  const proOk = u.plan === "pro" || u.extra_minutes > 0;
  const paid = !!cfg.pricing.paid_plans;
  const showPro = paid || proOk; // while the site is free-only, Pro only shows for people an admin gave it to
  const card = (id, title, lines, ok) => (
    <button
      key={id}
      disabled={!ok}
      onClick={() => setTier(id)}
      className={cx(
        "rounded-2xl border-2 p-4 text-left transition disabled:opacity-50",
        tier === id ? "border-amber-500 bg-amber-50 dark:bg-amber-500/10" : "border-stone-200 hover:border-stone-300 dark:border-zinc-800 dark:hover:border-zinc-700"
      )}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="font-semibold">{title}</span>
        <Badge kind={id === "free" ? "free" : "paid"}>{id === "free" ? `${freeLeft} left` : `${u.pro_minutes_left} min left`}</Badge>
      </div>
      <ul className="space-y-0.5 text-xs text-stone-600 dark:text-zinc-400">
        {lines.map((b) => (
          <li key={b}>• {b}</li>
        ))}
      </ul>
    </button>
  );
  return (
    <div>
      <div className={cx("grid gap-3", showPro && "sm:grid-cols-2")}>
        {card(
          "free",
          "Free",
          [`Up to ${plans.free.max_minutes} min`, "Kokoro voice, built-in music & thumbnail", plans.free.watermark ? "Small watermark" : "No watermark"],
          freeLeft > 0
        )}
        {showPro && card("pro", "Pro", [`Up to ${plans.pro.max_minutes} min`, "ElevenLabs voice, AI music & thumbnail art", "No watermark"], proOk)}
      </div>
      {freeLeft === 0 && !proOk && (
        <p className="mt-3 text-sm">You've made all your free videos for this month. More on the 1st!</p>
      )}
      {!proOk && paid && (
        <p className="mt-3 text-sm">
          Want studio voices and AI music?{" "}
          <a href="#/pricing" className="font-medium text-amber-700 underline dark:text-amber-400">
            Upgrade to Pro
          </a>
        </p>
      )}
      {tier === "pro" && minutes > u.pro_minutes_left && (
        <p className="mt-3 text-sm text-red-700 dark:text-red-400">
          This needs {minutes} Pro minutes and you have {u.pro_minutes_left}. Make it shorter or{" "}
          <a href="#/pricing" className="underline">
            buy more minutes
          </a>
          .
        </p>
      )}
    </div>
  );
}

export default function NewVideo() {
  const cfg = useConfig();
  const planMode = cfg.mode === "hosted" && !cfg.user?.is_admin;
  const [mode, setMode] = useState("youtube");
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState(null);
  const [previewErr, setPreviewErr] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [topic, setTopic] = useState("");
  const [minutes, setMinutes] = useState(10);
  const [tone, setTone] = useState("funny but respectful");
  const [faith, setFaith] = useState("balanced");
  const [styleUrl, setStyleUrl] = useState("");
  const [extra, setExtra] = useState("");
  const [watch, setWatch] = useState(true);
  const [autopilot, setAutopilot] = useState(true);
  const [shareCopy, setShareCopy] = useState(true);
  const [credit, setCredit] = useState(true);
  const [tier, setTier] = useState(planMode && cfg.user?.usage?.plan === "pro" ? "pro" : "free");
  const [aiShort, setAiShort] = useState(false);
  const [catalog, setCatalog] = useState(null);
  const [tiers, setTiers] = useState(null);
  const [notes, setNotes] = useState({});
  const [custom, setCustom] = useState(null);
  const [voice, setVoice] = useState({});
  const [estimate, setEstimate] = useState(null);
  const [unavailable, setUnavailable] = useState({});
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(null);
  const [balances, setBalances] = useState({});

  useEffect(() => {
    api.get("/api/providers").then((d) => {
      setCatalog(d.catalog);
      setTiers(d.tiers);
      setNotes(d.notes || {});
      setCustom((c) => ({ ...d.tiers.free, ...(c || {}) }));
    });
    api.get("/api/settings").then((d) => {
      setSettings(d.settings);
      setAutopilot(d.settings.autopilot !== false);
      setShareCopy(d.settings.share_copy !== false);
      // "Custom" starts from your default tools (Settings > Tools)
      setCustom((c) => ({ ...(c || {}), ...d.settings.providers }));
    });
    if (!planMode) api.get("/api/balances").then((d) => setBalances(d.balances || {})).catch(() => {});
  }, []);

  const maxMinutes = planMode ? cfg.pricing.plans[tier]?.max_minutes || 3 : 20;
  useEffect(() => {
    if (minutes > maxMinutes) setMinutes(maxMinutes);
  }, [maxMinutes]);

  const providers = useMemo(() => {
    if (!tiers) return null;
    if (planMode) {
      // what the voice picker should offer; the server picks the real tools from the plan
      const el = catalog?.voice?.find((p) => p.id === "elevenlabs")?.available;
      return { ...tiers.free, voice: tier === "pro" && el ? "elevenlabs" : "kokoro" };
    }
    if (tier === "custom") return custom;
    return tiers[tier];
  }, [tier, tiers, custom, catalog]);

  // fetch the YouTube preview when a link is pasted
  const lastUrl = useRef("");
  useEffect(() => {
    if (mode !== "youtube") return;
    const u = url.trim();
    if (!u || u === lastUrl.current || !/youtu/.test(u)) return;
    const t = setTimeout(() => {
      lastUrl.current = u;
      setLoadingPreview(true);
      setPreviewErr(null);
      api
        .post("/api/source/preview", { url: u })
        .then((d) => {
          setPreview(d);
          if (d.duration) setMinutes(Math.max(1, Math.min(maxMinutes, Math.round(d.duration / 60))));
        })
        .catch((e) => {
          setPreview(null);
          setPreviewErr(e.message);
        })
        .finally(() => setLoadingPreview(false));
    }, 500);
    return () => clearTimeout(t);
  }, [url, mode]);

  // live cost estimate (not on the hosted website: there the plan covers the cost)
  useEffect(() => {
    if (!providers || planMode) return;
    const t = setTimeout(() => {
      api
        .post("/api/estimate", {
          mode,
          minutes,
          providers,
          duration: preview?.duration || null,
          options: { watch, style_url: mode === "topic" ? styleUrl : "" },
        })
        .then((d) => {
          setEstimate(d.estimate);
          setUnavailable(d.unavailable || {});
        })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [providers, minutes, mode, watch, styleUrl, preview]);

  const paidStages = estimate ? Object.entries(estimate).filter(([, e]) => !e.total.free) : [];
  const total = sumCosts(paidStages.map(([, e]) => e.total));
  const relevantUnavailable = Object.entries(unavailable).filter(([st]) => st !== "transcript" || mode === "youtube");

  async function start() {
    setError(null);
    if (mode === "youtube" && !url.trim()) return setError("Paste a YouTube link first.");
    if (mode === "topic" && !topic.trim()) return setError("Type a topic first.");
    setBusy(true);
    try {
      const approve = {};
      for (const [st, e] of paidStages) approve[st] = e.total;
      const r = await api.post("/api/projects", {
        mode,
        url: url.trim(),
        topic: topic.trim(),
        minutes: Number(minutes),
        tone,
        faithfulness: faith,
        style_url: styleUrl.trim(),
        extra,
        watch,
        autopilot,
        share_copy: shareCopy,
        credit_source: credit,
        providers,
        voice,
        approve,
        tier: planMode ? tier : "",
        ai_short: planMode && aiShort,
      });
      if (planMode) cfg.reload();
      go(`/p/${encodeURIComponent(r.slug)}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const tierCard = (id, title, sub, bullets) => (
    <button
      key={id}
      onClick={() => setTier(id)}
      className={cx(
        "rounded-2xl border-2 p-4 text-left transition",
        tier === id ? "border-amber-500 bg-amber-50 dark:bg-amber-500/10" : "border-stone-200 hover:border-stone-300 dark:border-zinc-800 dark:hover:border-zinc-700"
      )}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="font-semibold">{title}</span>
        <Badge kind={id === "free" ? "free" : "paid"}>{sub}</Badge>
      </div>
      <ul className="space-y-0.5 text-xs text-stone-600 dark:text-zinc-400">
        {bullets.map((b) => (
          <li key={b}>• {b}</li>
        ))}
      </ul>
    </button>
  );

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">New video</h1>
          <p className="text-sm text-stone-500 dark:text-zinc-400">
            Drop in a stickman YouTube video and get a brand-new, original stickman video on the same subject. Or start from any history topic.
          </p>
        </div>

        <div className="inline-flex rounded-xl border border-stone-200 bg-white p-1 dark:border-zinc-800 dark:bg-zinc-900">
          {[
            ["youtube", "▶ Remake a YouTube video"],
            ["topic", "✏️ Start from a topic"],
          ].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setMode(id)}
              className={cx("rounded-lg px-4 py-2 text-sm font-medium", mode === id ? "bg-amber-500 text-zinc-950" : "hover:bg-stone-100 dark:hover:bg-zinc-800")}
            >
              {label}
            </button>
          ))}
        </div>

        <Card>
          {mode === "youtube" ? (
            <div className="space-y-4">
              <Field label="YouTube link" hint="The app reads the video's captions and looks at its frames, then writes a NEW script in its own words.">
                <input className="w-full" placeholder="https://www.youtube.com/watch?v=..." value={url} onChange={(e) => setUrl(e.target.value)} />
              </Field>
              {loadingPreview && (
                <div className="flex items-center gap-2 text-sm text-stone-500">
                  <Spinner /> Reading the video…
                </div>
              )}
              <ErrorBox error={previewErr} />
              {preview && (
                <div className="flex gap-4 rounded-xl bg-stone-100 p-3 dark:bg-zinc-800">
                  {preview.thumbnail && <img src={preview.thumbnail} className="w-40 rounded-lg object-cover" alt="" />}
                  <div className="min-w-0">
                    <div className="font-semibold">{preview.title}</div>
                    <div className="text-sm text-stone-500 dark:text-zinc-400">
                      {preview.channel} · {fmtTime(preview.duration)}
                      {preview.chapters?.length ? ` · ${preview.chapters.length} chapters` : ""}
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-stone-500 dark:text-zinc-400">{preview.description}</p>
                  </div>
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="How close to the original?">
                  <select className="w-full" value={faith} onChange={(e) => setFaith(e.target.value)}>
                    <option value="close">Close: same structure and beats, new wording</option>
                    <option value="balanced">Balanced: same subject and main points</option>
                    <option value="loose">Loose: same subject, fresh angle</option>
                  </select>
                </Field>
                <Field label="Focus or angle (optional)">
                  <input className="w-full" placeholder="e.g. focus on the economics" value={topic} onChange={(e) => setTopic(e.target.value)} />
                </Field>
              </div>
              <Toggle checked={watch} onChange={setWatch} label="Watch the video's frames too" hint="Grabs ~48 frames into contact sheets so the AI sees the drawing style, characters and gags (not just the words)." />
              <Toggle checked={credit} onChange={setCredit} label="Credit the original video in the description" />
              <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-300">
                The writer is told never to copy sentences from the source. YouTube demonetizes "reused content", so an original script and your own visuals matter.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              <Field label="Topic">
                <input className="w-full" placeholder="The Fall of Rome" value={topic} onChange={(e) => setTopic(e.target.value)} />
              </Field>
              <Field label="Reference video for style (optional)" hint="A YouTube link whose pacing and humor you like. Its content is not used.">
                <input className="w-full" placeholder="https://www.youtube.com/watch?v=..." value={styleUrl} onChange={(e) => setStyleUrl(e.target.value)} />
              </Field>
            </div>
          )}
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <Field label={`Target length: ${minutes} min`} hint={`About ${Math.round(minutes * 8)} scenes`}>
              <input type="range" min="1" max={maxMinutes} step="0.5" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} className="w-full" />
            </Field>
            <Field label="Tone">
              <input className="w-full" value={tone} onChange={(e) => setTone(e.target.value)} />
            </Field>
          </div>
          <Field label="Extra instructions for the writer (optional)" className="mt-4">
            <textarea className="w-full" rows={2} value={extra} onChange={(e) => setExtra(e.target.value)} placeholder="e.g. make Napoleon a recurring tiny guy with a big hat" />
          </Field>
        </Card>

        {planMode && (
          <Card title="Plan">
            <PlanPicker cfg={cfg} tier={tier} setTier={setTier} minutes={minutes} />
            {tier === "pro" &&
              cfg.pricing.plans.pro.shorts?.includes("calliope") &&
              catalog?.shorts?.find((p) => p.id === "calliope")?.available && (
                <div className="mt-4">
                  <Toggle
                    checked={aiShort}
                    onChange={setAiShort}
                    label={`Also make an AI-illustrated Short with Calliope (+${cfg.pricing.ai_short_minutes} Pro min)`}
                    hint="Every video already gets a free stickman Short."
                  />
                </div>
              )}
          </Card>
        )}
        {!planMode && (
        <Card title="Quality">
          <div className="grid gap-3 sm:grid-cols-3">
            {tierCard("free", "Free", "$0", [
              "Unlimited videos",
              "Claude Code writes (your plan)",
              "Kokoro voice (offline)",
              "Built-in music, thumbnail & Short",
            ])}
            {tierCard("pro", "Pro", "paid", [
              "Anthropic API writer",
              "ElevenLabs voice + exact word timing",
              "ElevenLabs music & AI thumbnail art",
              "Calliope AI Short (if connected)",
            ])}
            {tierCard("custom", "Custom", "mix", ["Pick each tool yourself", "Free ones are always listed first"])}
          </div>
          {tier === "custom" && catalog && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {STAGE_ORDER.filter((st) => st !== "transcript" || mode === "youtube").map((st) => (
                <Field key={st} label={STAGE_NAMES[st]}>
                  <select className="w-full" value={custom[st]} onChange={(e) => setCustom({ ...custom, [st]: e.target.value })}>
                    {catalog[st].map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                        {!p.available ? " (not set up)" : ""}
                      </option>
                    ))}
                  </select>
                  <span className="mt-1 block text-xs text-stone-500 dark:text-zinc-400">{catalog[st].find((p) => p.id === custom[st])?.description}</span>
                </Field>
              ))}
              <p className="text-xs text-stone-500 sm:col-span-2 dark:text-zinc-400">{notes.openart}</p>
            </div>
          )}
          {relevantUnavailable.length > 0 && (
            <div className="mt-4 space-y-1 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/40 dark:text-red-300">
              {relevantUnavailable.map(([st, why]) => (
                <div key={st}>
                  <b>{catalog?.[st]?.find((p) => p.id === providers[st])?.label}</b>: {why}.{" "}
                  {/key/i.test(why) && (
                    <a href="#/settings" className="underline">
                      Add it in Settings
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>
        )}

        <Card title="Voice">
          {providers && settings && <VoicePicker provider={providers.voice} settings={settings} value={voice} onChange={setVoice} />}
        </Card>

        <Card title="Workflow">
          <div className="space-y-3">
            <Toggle
              checked={autopilot}
              onChange={setAutopilot}
              label="Autopilot"
              hint="On: runs straight to the finished video. Off: pauses so you can review and edit the script, the storyboard and the voice."
            />
            <Toggle checked={shareCopy} onChange={setShareCopy} label="Also make a small share copy (under 30 MB)" />
          </div>
        </Card>
      </div>

      <div className="space-y-4 lg:sticky lg:top-20 lg:self-start">
        {planMode ? (
          <Card title="Your plan">
            {tier === "free" ? (
              <p className="text-sm">
                Uses <b>1</b> of your {cfg.user.usage.free_videos_limit} free videos this month (
                {Math.max(0, cfg.user.usage.free_videos_limit - cfg.user.usage.free_videos_used)} left).
              </p>
            ) : (
              <p className="text-sm">
                Uses up to <b>{minutes + (aiShort ? cfg.pricing.ai_short_minutes : 0)}</b> of your {cfg.user.usage.pro_minutes_left} Pro minutes. If the video comes
                out shorter, the rest comes back.
              </p>
            )}
            <p className="mt-2 text-xs text-stone-500 dark:text-zinc-400">No extra charges: the tools are included in your plan.</p>
            <Button variant="primary" size="lg" className="mt-4 w-full" disabled={busy} onClick={start}>
              {busy ? <Spinner /> : null}
              Make my video
            </Button>
            <ErrorBox error={error} />
            {error && /upgrade|minutes|plan/i.test(error) && (
              <a href="#/pricing" className="mt-2 block text-sm underline">
                See plans
              </a>
            )}
          </Card>
        ) : (
        <Card title="Cost">
          {!estimate ? (
            <Spinner />
          ) : paidStages.length === 0 ? (
            <div>
              <div className="text-3xl font-bold text-emerald-600">$0</div>
              <p className="text-sm text-stone-500 dark:text-zinc-400">Everything in this setup is free.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {paidStages.map(([st, e]) => (
                <div key={st} className="text-sm">
                  <div className="flex justify-between gap-2">
                    <span>{EST_LABELS[st] || st}</span>
                    <span className="font-medium">{fmtCost(e.total)}</span>
                  </div>
                  {e.lines.map((l, i) => (
                    <div key={i} className="text-xs text-stone-500 dark:text-zinc-400">
                      {l.provider}: {l.cost.note}
                    </div>
                  ))}
                </div>
              ))}
              <div className="border-t border-stone-200 pt-2 dark:border-zinc-800">
                <div className="flex justify-between font-semibold">
                  <span>Total estimate</span>
                  <span>{fmtCost(total)}</span>
                </div>
                <p className="mt-1 text-xs text-stone-500 dark:text-zinc-400">
                  Nothing is charged until you click the button below. If a step later needs noticeably more than this, the run pauses and asks you again.
                </p>
              </div>
              {Object.keys(balances).length > 0 && (
                <div className="rounded-lg bg-stone-100 p-2 text-xs dark:bg-zinc-800">
                  {Object.entries(balances).map(([id, b]) => (
                    <div key={id}>
                      {b.label}: {b.text || `${b.remaining?.toLocaleString()} of ${b.limit?.toLocaleString()} ${b.unit} left`}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          <Button variant={paidStages.length ? "pay" : "primary"} size="lg" className="mt-4 w-full" disabled={busy} onClick={start}>
            {busy ? <Spinner /> : null}
            {paidStages.length ? `Approve ${fmtCost(total)} & start` : "Make my video (free)"}
          </Button>
          <ErrorBox error={error} />
        </Card>
        )}
        <Card>
          <ol className="space-y-1 text-xs text-stone-600 dark:text-zinc-400">
            {mode === "youtube" && <li>1. Watch: captions + frames of the source video</li>}
            <li>{mode === "youtube" ? "2" : "1"}. Script: original narration, fact checklist</li>
            <li>· Storyboard: one doodle scene per beat</li>
            <li>· Voice: narration per line</li>
            <li>· Render: animated scenes, captions</li>
            <li>· Music & mix: -15 LUFS final mix</li>
            <li>· Package: 3 titles, description with chapters, tags, thumbnail</li>
            <li>· Short: a vertical teaser for YouTube Shorts</li>
          </ol>
        </Card>
      </div>
    </div>
  );
}
