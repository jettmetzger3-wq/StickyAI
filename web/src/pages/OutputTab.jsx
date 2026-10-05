import { useState } from "react";
import { api, fileUrl, fmtBytes, fmtCost, fmtTime } from "../api.js";
import { Button, Card, CopyButton, ErrorBox, Spinner } from "../ui.jsx";
import { useConfig } from "../App.jsx";
import { withApproval } from "./Project.jsx";

function ShortCard({ d, slug, dl }) {
  const cfg = useConfig();
  const f = d.final || {};
  const sh = d.short || {};
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [thumbs, setThumbs] = useState(sh.thumbs || []);
  const canCalliope = (cfg.mode !== "hosted" || cfg.user?.is_admin) && sh.calliope?.job_id && sh.calliope?.done;
  if (!f.short && !f.short_ai) return null;
  const text = [sh.title, "", sh.description, "", (sh.hashtags || []).join(" ")].join("\n").trim();
  const base = `/api/projects/${encodeURIComponent(slug)}/calliope/thumbnails`;

  async function makeThumbs() {
    setErr(null);
    setBusy(true);
    try {
      const r = await withApproval((approved) => api.post(base, { count: 3, approved }));
      if (r) setMsg(r.message);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    setErr(null);
    setBusy(true);
    try {
      const r = await api.get(base);
      setThumbs(r.thumbs);
      if (!r.thumbs.length) setMsg("Not ready yet, try again in a minute.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Short (vertical teaser)" actions={<CopyButton text={text} label="Copy title & description" />}>
      <div className="flex flex-wrap gap-5">
        {f.short && (
          <div>
            <video src={fileUrl(slug, f.short.path, f.short.v) + "#t=0.5"} preload="metadata" controls className="h-[480px] rounded-xl bg-black" />
            <a href={dl("short")} className="mt-2 block">
              <Button size="sm">⬇ Stickman Short ({fmtBytes(f.short.size)})</Button>
            </a>
          </div>
        )}
        {f.short_ai && (
          <div>
            <video src={fileUrl(slug, f.short_ai.path, f.short_ai.v) + "#t=0.5"} preload="metadata" controls className="h-[480px] rounded-xl bg-black" />
            <a href={dl("short_ai")} className="mt-2 block">
              <Button size="sm">⬇ Calliope AI Short ({fmtBytes(f.short_ai.size)})</Button>
            </a>
          </div>
        )}
        <div className="min-w-[220px] flex-1 space-y-2 text-sm">
          <div className="font-semibold">{sh.title}</div>
          <p className="text-stone-600 dark:text-zinc-400">{sh.description}</p>
          <div className="text-sky-700 dark:text-sky-400">{(sh.hashtags || []).join(" ")}</div>
          <p className="text-xs text-stone-500 dark:text-zinc-400">
            Upload it as a Short (vertical, under 60 s) and link the full video in the description or as the Short's related video.
          </p>
          {canCalliope && (
            <div className="space-y-2 border-t border-stone-200 pt-3 dark:border-zinc-800">
              <div className="font-medium">Calliope thumbnails</div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" disabled={busy} onClick={makeThumbs}>
                  {busy && <Spinner />} Make 3 thumbnails…
                </Button>
                <Button size="sm" variant="ghost" disabled={busy} onClick={refresh}>
                  Refresh
                </Button>
              </div>
              {msg && <p className="text-xs">{msg}</p>}
              <ErrorBox error={err} />
              <div className="grid grid-cols-2 gap-2">
                {thumbs.map((t) => (
                  <a key={t} href={fileUrl(slug, `final/${t}`)} target="_blank" rel="noreferrer">
                    <img src={fileUrl(slug, `final/${t}`)} className="rounded-lg" alt="" />
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

function CostSummary({ d }) {
  const cfg = useConfig();
  const m = d.meta;
  const plan = cfg.mode === "hosted" && !cfg.user?.is_admin;
  const b = m.billing;
  if (plan) {
    return (
      <Card title="Plan usage">
        <p className="text-sm">
          {b?.tier === "pro"
            ? `This video set aside ${b.minutes} Pro minutes` + (b.settled ? ` and used ${b.used ?? b.minutes} (${b.refunded || 0} went back to you).` : ".")
            : "This video used 1 free video from your monthly allowance."}
        </p>
      </Card>
    );
  }
  const byStage = {};
  for (const c of m.costs || []) {
    const k = c.stage;
    byStage[k] = byStage[k] || { usd: 0, credits: 0 };
    byStage[k].usd += c.usd || 0;
    byStage[k].credits += c.credits || 0;
  }
  const rows = Object.entries(byStage);
  return (
    <Card title="What this video cost">
      {rows.length === 0 ? (
        <p className="text-sm text-emerald-700 dark:text-emerald-400">$0: made entirely with free tools.</p>
      ) : (
        <div className="space-y-1 text-sm">
          {rows.map(([st, c]) => (
            <div key={st} className="flex justify-between">
              <span>{d.stage_labels[st] || st}</span>
              <span>{fmtCost({ usd: c.usd, credits: c.credits })}</span>
            </div>
          ))}
          <div className="flex justify-between border-t border-stone-200 pt-1 font-semibold dark:border-zinc-800">
            <span>Total</span>
            <span>${(d.spent_usd || 0).toFixed(2)}</span>
          </div>
          {d.budget_usd > 0 && <p className="text-xs text-stone-500">Per-video limit: ${d.budget_usd.toFixed(2)} (Settings)</p>}
        </div>
      )}
    </Card>
  );
}

export default function OutputTab({ d, slug }) {
  const yt = d.youtube;
  const f = d.final || {};
  const dl = (kind) => `/api/projects/${encodeURIComponent(slug)}/download/${kind}`;
  if (!f.video)
    return (
      <Card>
        <p className="text-sm text-stone-500 dark:text-zinc-400">The final video isn't made yet. It appears here when the Render and Mix steps finish.</p>
      </Card>
    );
  const tags = (yt?.tags || []).join(", ");
  return (
    <div className="space-y-4">
      <Card
        title="Video"
        actions={
          <>
            <a href={dl("video")}>
              <Button variant="primary">⬇ Full quality ({fmtBytes(f.video.size)})</Button>
            </a>
            {f.share && (
              <a href={dl("share")}>
                <Button>⬇ Share copy ({fmtBytes(f.share.size)})</Button>
              </a>
            )}
          </>
        }
      >
        <video src={fileUrl(slug, f.video.path, f.video.v)} controls className="w-full rounded-xl bg-black" poster={f.thumbnail ? fileUrl(slug, f.thumbnail.path, f.thumbnail.v) : undefined} />
      </Card>

      {yt && (
        <>
          <Card title="Titles (pick one)">
            <div className="space-y-2">
              {yt.titles.map((t, i) => (
                <div key={i} className="flex items-center justify-between gap-3 rounded-lg bg-stone-100 px-3 py-2 dark:bg-zinc-800">
                  <span className="font-medium">{t}</span>
                  <span className="flex items-center gap-2">
                    <span className={t.length > 70 ? "text-xs text-red-600" : "text-xs text-stone-400"}>{t.length}/100</span>
                    <CopyButton text={t} />
                  </span>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Description" actions={<CopyButton text={yt.description} label="Copy description" />}>
            <textarea readOnly className="mono h-72 w-full text-xs" value={yt.description} />
            <p className="mt-2 text-xs text-stone-500 dark:text-zinc-400">
              Chapters use the real scene start times and start at 0:00, so YouTube turns them into chapters automatically.
            </p>
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Card title="Tags" actions={<CopyButton text={tags} label="Copy tags" />}>
              <div className="flex flex-wrap gap-1.5">
                {yt.tags.map((t) => (
                  <span key={t} className="rounded-full bg-stone-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
                    {t}
                  </span>
                ))}
              </div>
              {yt.hashtags?.length > 0 && <div className="mt-2 text-sm text-sky-700 dark:text-sky-400">{yt.hashtags.join(" ")}</div>}
            </Card>
            <Card title="Chapters">
              <ul className="space-y-0.5 text-sm">
                {yt.chapters.map((c, i) => (
                  <li key={i}>
                    <span className="mr-2 font-mono text-stone-500">{c.time}</span>
                    {c.title}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-stone-500">Video length {fmtTime(yt.duration)}</p>
            </Card>
          </div>
          {f.thumbnail && (
            <Card title="Thumbnail" actions={<a href={dl("thumbnail")}><Button>⬇ Download</Button></a>}>
              <img src={fileUrl(slug, f.thumbnail.path, f.thumbnail.v)} className="w-full max-w-2xl rounded-xl" alt="" />
            </Card>
          )}
          {yt.question && (
            <Card title="Pinned comment idea" actions={<CopyButton text={yt.question} />}>
              <p className="text-sm">{yt.question}</p>
            </Card>
          )}
        </>
      )}
      <ShortCard d={d} slug={slug} dl={dl} />
      <CostSummary d={d} />
    </div>
  );
}
