import { useEffect, useState } from "react";
import { api, fileUrl, fmtTime } from "../api.js";
import { Badge, Button, Card, cx, ErrorBox, Modal, Spinner } from "../ui.jsx";
import { withApproval } from "./Project.jsx";

const CHECK_LABEL = {
  narration: "Narration match",
  coverage: "Shows the narration",
  history: "History",
  continuity: "Continuity",
  characters: "Characters",
  props: "Props",
  action: "Action",
  camera: "Camera",
  layout: "Layout",
  pacing: "Pacing",
  emotion: "Mood",
  redundancy: "No repeats",
  usage: "AI usage",
};

function ReviewCard({ review, usage, slug }) {
  const [allowed, setAllowed] = useState(false);
  const [allowedLayout, setAllowedLayout] = useState(false);
  if (!review) return null;
  const open = (review.issues || []).filter((i) => !i.fixed);
  return (
    <Card title="Storyboard review" className="mb-3">
      <p className="text-sm text-stone-600 dark:text-zinc-400">
        The studio checked every scene before voicing and rendering: <b>{review.fixed}</b> problems fixed automatically
        {open.length ? <>, <b>{open.length}</b> left for you to look at</> : ", nothing left to fix"}.
        {usage?.total && (
          <> This video used <b>{usage.total.calls}</b> AI calls (~{Math.round(usage.total.tokens / 1000)}k tokens){usage.total.cached ? <> and reused <b>{usage.total.cached}</b> saved answers</> : null}.</>
        )}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3 lg:grid-cols-4">
        {Object.entries(review.scores || {}).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-xs">
            <span className="w-28 shrink-0 text-stone-600 dark:text-zinc-400">{CHECK_LABEL[k] || k}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-stone-200 dark:bg-zinc-800">
              <span className={cx("block h-full", v >= 0.8 ? "bg-emerald-500" : v >= 0.5 ? "bg-amber-500" : "bg-red-500")} style={{ width: `${Math.round(v * 100)}%` }} />
            </span>
          </div>
        ))}
      </div>
      {review.coverage && (
        <p className="mt-2 text-sm text-stone-600 dark:text-zinc-400">
          Narration-to-picture coverage <b>{Math.round((review.coverage.mean ?? 1) * 100)}%</b>
          {review.muted && <> · muted-video test <b>{Math.round(review.muted.score * 100)}%</b> (who, where, what, when, what changed)</>}
          {(review.coverage.failed || []).length > 0 && (
            <span className="text-red-700 dark:text-red-400"> · scenes {(review.coverage.failed || []).map((i) => i + 1).join(", ")} don't show what is said</span>
          )}
          {(review.muted?.weak || []).length > 0 && <> · hard to follow muted: {(review.muted.weak || []).map((i) => i + 1).join(", ")}</>}
        </p>
      )}
      {review.layout && (
        <p className="mt-1 text-sm text-stone-600 dark:text-zinc-400">
          Layout (collisions, margins, sizes, speech bubbles) <b>{Math.round((review.layout.mean ?? 1) * 100)}%</b>
          {(review.layout.escalate || []).length > 0 && (
            <span className="text-red-700 dark:text-red-400"> · scenes {(review.layout.escalate || []).map((i) => i + 1).join(", ")} still have a layout problem moving things could not fix</span>
          )}
          {(review.layout.open || []).filter((x) => x.sev === "medium").length > 0 && (
            <> · {(review.layout.open || []).filter((x) => x.sev === "medium").length} smaller issue(s) left</>
          )}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <a className="text-sm underline" href={fileUrl(slug, "storyboard/preview.html")} target="_blank" rel="noreferrer">Open the storyboard preview page</a>
        {(review.layout?.escalate || []).length > 0 && !allowedLayout && (
          <Button size="sm" onClick={async () => { await api.put(`/api/projects/${encodeURIComponent(slug)}/options`, { options: { allow_layout_issues: true } }); setAllowedLayout(true); }}>
            Render anyway (layout)
          </Button>
        )}
        {(review.coverage?.blocked || []).length > 0 && !allowed && (
          <Button size="sm" onClick={async () => { await api.put(`/api/projects/${encodeURIComponent(slug)}/options`, { options: { allow_low_coverage: true } }); setAllowed(true); }}>
            Render anyway
          </Button>
        )}
      </div>
      {(review.issues || []).length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm font-medium">All {(review.issues || []).length} findings</summary>
          <ul className="mt-1 space-y-0.5 text-xs text-stone-600 dark:text-zinc-400">
            {review.issues.map((i, k) => (
              <li key={k}>
                <span className="font-mono text-stone-400">{i.beat >= 0 ? `#${i.beat}` : "all"}</span> {i.msg}{" "}
                {i.fixed ? <Badge kind="done">fixed</Badge> : <Badge kind="paused">{i.severity}</Badge>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}
export default function StoryboardTab({ d, slug, reload, running }) {
  const [open, setOpen] = useState(null);
  const beats = d.script?.beats || [];
  if (!d.scenes.some((s) => s.has_scene))
    return (
      <Card>
        <p className="text-sm text-stone-500 dark:text-zinc-400">{running ? "Drawing the storyboard…" : "No storyboard yet."}</p>
      </Card>
    );
  const world = d.world || {};
  return (
    <>
      <ReviewCard review={d.review} usage={d.usage} slug={slug} />
      {(world.themes?.length > 0 || world.sheet) && (
        <Card className="mb-3">
          {world.themes?.length > 0 && (
            <p className="text-sm text-stone-600 dark:text-zinc-400">
              <span className="font-semibold text-stone-800 dark:text-zinc-200">This video's world: </span>
              {world.themes.join(" · ")}. Scenes use its places, props and catchphrases.
            </p>
          )}
          {world.sheet && (
            <details className="mt-2">
              <summary className="cursor-pointer text-sm font-semibold text-stone-800 dark:text-zinc-200">
                {world.props.length} props drawn just for this video
              </summary>
              <img src={fileUrl(slug, world.sheet, world.sheet_v)} alt="custom props" className="mt-2 max-h-72 rounded-lg border border-stone-200 dark:border-zinc-800" />
            </details>
          )}
        </Card>
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {d.scenes.map((s) => (
          <button
            key={s.i}
            onClick={() => s.has_scene && setOpen(s.i)}
            className="group overflow-hidden rounded-xl border border-stone-200 bg-white text-left shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="relative aspect-video bg-stone-100 dark:bg-zinc-800">
              {s.has_preview ? (
                <img src={fileUrl(slug, `previews/${String(s.i).padStart(3, "0")}.jpg`, s.preview_v)} className="h-full w-full object-cover" alt="" loading="lazy" />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-stone-400">{s.has_scene ? "no preview" : "not drawn yet"}</div>
              )}
              <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-xs text-white">
                #{s.i}
                {s.start != null ? ` · ${fmtTime(s.start)}` : ""}
              </span>
              {(s.warnings?.length > 0 || s.source === "rules") && (
                <span className="absolute right-2 top-2 rounded bg-amber-500 px-1.5 py-0.5 text-xs text-black" title={(s.warnings || []).join("\n")}>
                  {s.source === "rules" ? "simple scene" : "⚠"}
                </span>
              )}
            </div>
            <div className="p-2.5">
              <div className="mb-1 flex items-center gap-2">
                <Badge kind={beats[s.i]?.mood}>{beats[s.i]?.mood}</Badge>
                {s.source === "edited" && <Badge kind="paused">edited</Badge>}
                {s.pattern && s.pattern !== "CUSTOM" && <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-stone-500 dark:bg-zinc-800 dark:text-zinc-400">{s.pattern.replace(/_/g, " ").toLowerCase()}</span>}
              </div>
              <p className="line-clamp-2 text-xs text-stone-600 dark:text-zinc-400">{beats[s.i]?.text}</p>
            </div>
          </button>
        ))}
      </div>
      {open !== null && (
        <SceneModal
          slug={slug}
          i={open}
          beat={beats[open]}
          info={d.scenes[open]}
          rendered={d.meta.stages?.render?.status === "done"}
          running={running}
          onClose={() => {
            setOpen(null);
            reload();
          }}
          onNav={(k) => setOpen((o) => Math.max(0, Math.min(beats.length - 1, o + k)))}
          reload={reload}
        />
      )}
    </>
  );
}

const MOVABLE = ["char", "text", "prop", "bubble", "note", "sign", "board", "icons", "shape"];

function SceneModal({ slug, i, beat, info, rendered, running, onClose, onNav, reload }) {
  const [scene, setScene] = useState(null);
  const [json, setJson] = useState("");
  const [jsonErr, setJsonErr] = useState(null);
  const [errors, setErrors] = useState(null);
  const [fixes, setFixes] = useState([]);
  const [img, setImg] = useState(null);
  const [t, setT] = useState(0.85);
  const [busy, setBusy] = useState(false);
  const base = `/api/projects/${encodeURIComponent(slug)}/scenes/${i}`;

  const renderPreview = async (tt = t) => {
    const r = await api.post(`${base}/preview?t=${tt}`);
    setImg(fileUrl(slug, r.path, r.v));
  };

  useEffect(() => {
    setScene(null);
    setImg(null);
    setErrors(null);
    setFixes(info?.fixes || []);
    api.get(base).then((r) => {
      setScene(r.scene);
      setJson(JSON.stringify(r.scene, null, 2));
    });
    renderPreview(0.85).catch(() => {});
    setT(0.85);
  }, [i]);

  async function save(sc) {
    setBusy(true);
    setErrors(null);
    try {
      const r = await api.put(base, { scene: sc });
      setScene(r.scene);
      setJson(JSON.stringify(r.scene, null, 2));
      setFixes(r.fixes || []);
      await renderPreview();
    } catch (e) {
      if (e.status === 422) setErrors(e.data.errors);
      else setErrors([e.message]);
    } finally {
      setBusy(false);
    }
  }

  function nudge(k, dx, dy) {
    const sc = structuredClone(scene);
    const el = sc.elements[k];
    if (el.lon != null && el.lat != null) {
      el.lon = +(el.lon + dx / 40).toFixed(2);
      el.lat = +(el.lat - dy / 40).toFixed(2);
    } else {
      el.x = Math.round((el.x ?? 960) + dx);
      el.y = Math.round((el.y ?? 540) + dy);
    }
    setScene(sc);
    setJson(JSON.stringify(sc, null, 2));
    save(sc);
  }

  async function redraw() {
    const instruction = prompt("Optional: what should change in this scene? (empty = just redraw it)", "");
    if (instruction === null) return;
    try {
      const r = await withApproval((approved) => api.post(`${base}/regenerate`, { instruction, approved }));
      if (r) {
        alert("Redrawing in the background. The preview updates when it's done.");
        onClose();
      }
    } catch (e) {
      alert(e.message);
    }
  }

  return (
    <Modal open onClose={onClose} title={`Scene #${i}`} wide>
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <div className="space-y-3">
          <div className="relative aspect-video overflow-hidden rounded-xl bg-stone-100 dark:bg-zinc-800">
            {img ? <img src={img} className="h-full w-full object-contain" alt="" /> : <div className="flex h-full items-center justify-center"><Spinner /></div>}
            {busy && <div className="absolute inset-0 flex items-center justify-center bg-white/40 dark:bg-black/40"><Spinner /></div>}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-stone-500">time</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={t}
              onChange={(e) => setT(Number(e.target.value))}
              onMouseUp={() => renderPreview(t)}
              onTouchEnd={() => renderPreview(t)}
              className="flex-1"
            />
            <span className="w-10 text-right text-xs">{Math.round(t * 100)}%</span>
          </div>
          <div className="rounded-xl bg-stone-100 p-3 text-sm dark:bg-zinc-800">
            <Badge kind={beat?.mood}>{beat?.mood}</Badge> <span className="ml-1">{beat?.text}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => onNav(-1)}>← Prev</Button>
            <Button onClick={() => onNav(1)}>Next →</Button>
            <Button variant="primary" disabled={running} onClick={redraw}>
              ↻ Redraw with AI
            </Button>
            {rendered && (
              <Button
                disabled={running}
                onClick={async () => {
                  await api.post(`${base}/rerender`);
                  alert("Re-rendering this scene and re-assembling the video in the background.");
                  onClose();
                }}
              >
                🎞 Re-render this scene in the video
              </Button>
            )}
          </div>
          {fixes?.length > 0 && (
            <details className="text-xs text-stone-500 dark:text-zinc-400">
              <summary className="cursor-pointer">Auto-fixes applied ({fixes.length})</summary>
              <ul>
                {fixes.map((f, k) => (
                  <li key={k}>• {f}</li>
                ))}
              </ul>
            </details>
          )}
          {info?.warnings?.length > 0 && (
            <div className="text-xs text-amber-700 dark:text-amber-400">
              {info.warnings.map((w, k) => (
                <div key={k}>⚠ {w}</div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div>
            <div className="mb-1 text-sm font-medium">Elements (nudge to move)</div>
            <div className="max-h-56 space-y-1 overflow-y-auto pr-1">
              {(scene?.elements || []).map((el, k) => (
                <div key={k} className="flex items-center gap-2 rounded-lg bg-stone-100 px-2 py-1 text-xs dark:bg-zinc-800">
                  <span className="w-12 font-mono text-stone-500">{el.type}</span>
                  <span className="flex-1 truncate">{el.text || el.title || el.name || el.kind || el.icon || el.region || (el.countries || []).join(", ")}</span>
                  {MOVABLE.includes(el.type) && (
                    <span className="flex gap-0.5">
                      {[
                        ["←", -40, 0],
                        ["→", 40, 0],
                        ["↑", 0, -40],
                        ["↓", 0, 40],
                      ].map(([s, dx, dy]) => (
                        <button key={s} className="rounded px-1 hover:bg-stone-200 dark:hover:bg-zinc-700" onClick={() => nudge(k, dx, dy)} disabled={busy}>
                          {s}
                        </button>
                      ))}
                    </span>
                  )}
                  <button
                    className="px-1 text-red-600"
                    title="Remove"
                    onClick={() => {
                      const sc = structuredClone(scene);
                      sc.elements.splice(k, 1);
                      setScene(sc);
                      setJson(JSON.stringify(sc, null, 2));
                      save(sc);
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-sm font-medium">Scene JSON</span>
              <Button
                size="sm"
                variant="primary"
                disabled={busy}
                onClick={() => {
                  try {
                    const sc = JSON.parse(json);
                    setJsonErr(null);
                    save(sc);
                  } catch (e) {
                    setJsonErr("Not valid JSON: " + e.message);
                  }
                }}
              >
                Save & preview
              </Button>
            </div>
            <textarea className={cx("mono h-80 w-full text-xs", jsonErr && "border-red-500")} value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} />
            <ErrorBox error={jsonErr} />
            {errors && <ErrorBox error={errors.join("\n")} />}
          </div>
        </div>
      </div>
    </Modal>
  );
}
