import { useCallback, useEffect, useRef, useState } from "react";
import { api, fmtCost, sumCosts, useEvents } from "../api.js";
import { Badge, Button, Card, cx, Elapsed, ErrorBox, Progress, Spinner } from "../ui.jsx";
import { go, useConfig } from "../App.jsx";
import ScriptTab from "./ScriptTab.jsx";
import StoryboardTab from "./StoryboardTab.jsx";
import OutputTab from "./OutputTab.jsx";
import { AudioTab, SourceTab, CostsTab } from "./MiscTabs.jsx";

const STAGES = ["source", "script", "storyboard", "voice", "render", "mix", "package", "shorts"];

export default function ProjectPage({ slug }) {
  const cfg = useConfig();
  const [d, setD] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState(null);
  const [live, setLive] = useState({});
  const [log, setLog] = useState([]);
  const timer = useRef(null);
  const lastStatus = useRef(null);

  const load = useCallback(() => {
    return api
      .get(`/api/projects/${encodeURIComponent(slug)}`)
      .then((x) => {
        const st = x.meta.status;
        // jump to the right tab when a run finishes or pauses for review
        if (lastStatus.current && lastStatus.current !== st) {
          if (st === "done") {
            setTab("output");
            if (cfg.mode === "hosted") cfg.reload(); // unused Pro minutes came back
          }
          else if (st === "awaiting_review") setTab(x.meta.pending?.stage === "voice" ? "audio" : x.meta.pending?.stage);
        }
        lastStatus.current = st;
        setD(x);
        setError(null);
        return x;
      })
      .catch((e) => setError(e.message));
  }, [slug]);

  useEffect(() => {
    load().then((x) => {
      if (!x) return;
      const m = x.meta;
      if (m.status === "done") setTab("output");
      else if (m.pending?.type === "review") setTab(m.pending.stage === "voice" ? "audio" : m.pending.stage);
      else setTab("script");
    });
  }, [load]);

  useEffect(() => {
    const stop = useEvents(slug, (ev) => {
      if (ev.type === "progress") setLive((l) => ({ ...l, [ev.stage]: { progress: ev.progress, message: ev.message } }));
      if (ev.type === "log") setLog((l) => [...l.slice(-200), `[${ev.stage}] ${ev.message}`]);
      if (ev.type === "stage" || ev.type === "status") {
        clearTimeout(timer.current);
        timer.current = setTimeout(load, 300);
      }
    });
    // safety net in case an event is missed
    const t = setInterval(() => d?.running && load(), 2000);
    return () => {
      stop();
      clearInterval(t);
    };
  }, [slug, load, d?.running]);

  if (error) return <ErrorBox error={error} />;
  if (!d) return <Spinner />;
  const m = d.meta;
  // the server knows whether a run is really going (a video interrupted by a shutdown is not running)
  const running = !!d.running;
  const pend = m.pending;

  async function action(path, body) {
    try {
      await api.post(`/api/projects/${encodeURIComponent(slug)}/${path}`, body || {});
      setTimeout(load, 300);
    } catch (e) {
      alert(e.message);
    }
  }

  const tabs = [
    ...(m.mode === "youtube" || m.options?.style_url ? [["source", "Source"]] : []),
    ["script", "Script"],
    ["storyboard", "Storyboard"],
    ["audio", "Voice & music"],
    ["output", "Output"],
    ["costs", "Costs & log"],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <button onClick={() => go("/")} className="text-sm text-stone-500 hover:underline dark:text-zinc-400">
            ← Library
          </button>
          <h1 className="text-2xl font-bold">{m.title}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-stone-500 dark:text-zinc-400">
            <Badge kind={running ? "running" : m.status} />
            <span>{m.mode === "youtube" ? "YouTube remake" : "Topic video"}</span>
            {m.source_url && (
              <a href={m.source_url} target="_blank" rel="noreferrer" className="truncate underline">
                source
              </a>
            )}
            <span>· autopilot {m.options?.autopilot === false ? "off" : "on"}</span>
            {m.tier && <Badge kind={m.tier === "pro" ? "paid" : "free"}>{m.tier === "pro" ? "Pro" : "Free"}</Badge>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {running ? (
            <Button onClick={() => action("cancel")}>Stop</Button>
          ) : (
            m.status !== "done" &&
            !pend && (
              <Button variant="primary" onClick={() => action("run", {})}>
                ▶ {m.status === "new" ? "Start" : "Resume"}
              </Button>
            )
          )}
          <Button
            variant="ghost"
            disabled={running}
            onClick={async () => {
              if (!confirm("Delete this project and all its files?")) return;
              await api.del(`/api/projects/${encodeURIComponent(slug)}`);
              go("/");
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      {m.error && !running && (
        <ErrorBox
          error={
            <span>
              {m.error} <span className="text-xs opacity-70">(fix it, then press Resume)</span>
            </span>
          }
        />
      )}
      {running && m.status !== "queued" && (() => {
        // one clear "it's working" card at the top: which step, what it's doing, how long it's been
        const st = STAGES.find((k) => m.stages?.[k]?.status === "running");
        if (!st) return null;
        const s = m.stages[st];
        const lv = live[st];
        const done = STAGES.filter((k) => ["done", "skipped"].includes(m.stages?.[k]?.status)).length;
        return (
          <div className="rounded-2xl border border-sky-200 bg-sky-50 p-4 dark:border-sky-900 dark:bg-sky-500/10">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-semibold">
                <Spinner /> {d.stage_labels[st]}
                <span className="text-sm font-normal text-stone-500 dark:text-zinc-400">
                  step {Math.min(done + 1, STAGES.length)} of {STAGES.filter((k) => m.stages?.[k]?.status !== "skipped").length}
                </span>
              </div>
              <span className="text-sm text-stone-500 dark:text-zinc-400">
                running for <Elapsed since={s.started} />
              </span>
            </div>
            <Progress value={Math.max(lv?.progress ?? 0, s.progress ?? 0)} active className="mt-2" />
            <div className="mt-1 text-sm text-stone-600 dark:text-zinc-300">{lv?.message || s.message || "working…"}</div>
          </div>
        );
      })()}
      {m.status === "queued" && (
        <div className="rounded-2xl border border-sky-300 bg-sky-50 p-4 text-sm dark:border-sky-800 dark:bg-sky-500/10">
          <b>In line{d.queue_position ? ` (number ${d.queue_position})` : ""}.</b> Other videos are being made right now; yours starts automatically as soon as
          one finishes.
        </div>
      )}
      {m.notes?.length > 0 && (
        <div className="rounded-xl bg-stone-100 p-3 text-xs text-stone-600 dark:bg-zinc-800 dark:text-zinc-400">{m.notes.join(" · ")}</div>
      )}
      {pend && !running && <PendingBanner slug={slug} pend={pend} onDone={load} setTab={setTab} canApprove={cfg.mode !== "hosted" || cfg.user?.is_admin} />}

      <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
        <Card className="h-fit p-4">
          <ol className="space-y-3">
            {STAGES.map((st) => {
              const s = m.stages?.[st] || {};
              if (s.status === "skipped") return null;
              const lv = live[st];
              const isRun = s.status === "running";
              return (
                <li key={st}>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className={cx("flex items-center gap-1.5 font-medium", s.status === "pending" && "text-stone-400 dark:text-zinc-500")}>
                      {isRun && running && <Spinner />}
                      {d.stage_labels[st]}
                    </span>
                    {isRun && running ? (
                      <span className="text-xs text-sky-700 dark:text-sky-300">
                        <Elapsed since={s.started} />
                      </span>
                    ) : (
                      <Badge kind={s.status} />
                    )}
                  </div>
                  {(isRun || s.status === "error") && (
                    <>
                      <Progress
                        value={isRun ? Math.max(lv?.progress ?? 0, s.progress ?? 0) : s.progress}
                        active={isRun && running}
                        className="mt-1"
                      />
                      <div className="mt-1 truncate text-xs text-stone-500 dark:text-zinc-400" title={lv?.message || s.message}>
                        {isRun ? lv?.message || s.message : s.message}
                      </div>
                    </>
                  )}
                  {!running && (s.status === "done" || s.status === "error") && (
                    <button
                      className="text-xs text-stone-500 hover:underline dark:text-zinc-400"
                      onClick={() => {
                        if (confirm(`Re-run "${d.stage_labels[st]}" and everything after it? (Only changed parts are redone.)`)) action("run", { start: st });
                      }}
                    >
                      re-run from here
                    </button>
                  )}
                </li>
              );
            })}
          </ol>
          {m.warnings?.length > 0 && (
            <details className="mt-4 text-xs">
              <summary className="cursor-pointer text-amber-700 dark:text-amber-400">{m.warnings.length} note(s)</summary>
              <ul className="mt-1 space-y-1 text-stone-600 dark:text-zinc-400">
                {m.warnings.slice(-10).map((w, i) => (
                  <li key={i}>• {w.message}</li>
                ))}
              </ul>
            </details>
          )}
        </Card>

        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap gap-1 border-b border-stone-200 dark:border-zinc-800">
            {tabs.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cx(
                  "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
                  tab === id ? "border-amber-500 text-amber-700 dark:text-amber-400" : "border-transparent text-stone-500 hover:text-stone-800 dark:text-zinc-400 dark:hover:text-zinc-200"
                )}
              >
                {label}
              </button>
            ))}
          </div>
          {tab === "source" && <SourceTab d={d} slug={slug} />}
          {tab === "script" && <ScriptTab d={d} slug={slug} reload={load} running={running} />}
          {tab === "storyboard" && <StoryboardTab d={d} slug={slug} reload={load} running={running} />}
          {tab === "audio" && <AudioTab d={d} slug={slug} reload={load} running={running} />}
          {tab === "output" && <OutputTab d={d} slug={slug} />}
          {tab === "costs" && <CostsTab d={d} slug={slug} log={log} />}
        </div>
      </div>
    </div>
  );
}

function PendingBanner({ slug, pend, onDone, setTab, canApprove }) {
  const [busy, setBusy] = useState(false);
  const labels = { script: "script", storyboard: "storyboard", voice: "voice" };
  if (pend.type === "review") {
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-500/10">
        <div>
          <div className="font-semibold">Checkpoint: review the {labels[pend.stage] || pend.stage}</div>
          <div className="text-sm text-stone-600 dark:text-zinc-400">Make any edits you want, then continue to the next step.</div>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setTab(pend.stage === "voice" ? "audio" : pend.stage)}>Review</Button>
          <Button
            variant="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              await api.post(`/api/projects/${encodeURIComponent(slug)}/continue`);
              setBusy(false);
              onDone();
            }}
          >
            Looks good, continue →
          </Button>
        </div>
      </div>
    );
  }
  const total = pend.estimate;
  if (!canApprove) {
    return (
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-500/10">
        <b>This video hit the website's safety limit for one video.</b> The site admin has been asked to check it. You can also shorten the script and try
        again.
      </div>
    );
  }
  const ob = pend.over_budget;
  return (
    <div className="rounded-2xl border border-violet-300 bg-violet-50 p-4 dark:border-violet-800 dark:bg-violet-500/10">
      <div className="font-semibold">This step uses paid services: {fmtCost(total)}</div>
      {ob && (
        <div className="mt-1 text-sm text-amber-800 dark:text-amber-300">
          This would take this video's spending to about ${(ob.spent + (total.usd || 0)).toFixed(2)}, above your limit of ${ob.budget.toFixed(2)} per video
          (Settings). Approving raises the limit for this video only.
        </div>
      )}
      <ul className="mt-1 text-sm text-stone-600 dark:text-zinc-400">
        {(pend.lines || []).map((l, i) => (
          <li key={i}>
            • {l.provider}: {fmtCost(l.cost)} <span className="text-xs">({l.cost.note})</span>
          </li>
        ))}
      </ul>
      {pend.balances && Object.keys(pend.balances).length > 0 && (
        <div className="mt-2 text-xs text-stone-500">
          {Object.entries(pend.balances).map(([id, b]) => (
            <div key={id}>
              Balance: {b.remaining?.toLocaleString()} of {b.limit?.toLocaleString()} {b.unit} left
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <Button
          variant="pay"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await api.post(`/api/projects/${encodeURIComponent(slug)}/approve`, { stages: { [pend.stage]: total } });
            setBusy(false);
            onDone();
          }}
        >
          Approve {fmtCost(total)} & continue
        </Button>
        <span className="self-center text-xs text-stone-500 dark:text-zinc-400">Or switch this step to a free tool in Costs & log → Tools.</span>
      </div>
    </div>
  );
}

export async function withApproval(call) {
  // Calls an endpoint; if it answers 402 (needs approval) asks the user and retries with approved: true.
  try {
    return await call(false);
  } catch (e) {
    if (e.status === 402 && e.data?.needs_approval) {
      const c = e.data.cost;
      if (!confirm(`"${e.data.label}" uses ${e.data.provider}: ${fmtCost(c)}${c.note ? ` (${c.note})` : ""}.\n\nSpend this?`)) return null;
      return await call(true);
    }
    throw e;
  }
}
export { sumCosts };
