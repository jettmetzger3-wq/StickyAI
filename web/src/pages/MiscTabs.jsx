import { useEffect, useRef, useState } from "react";
import { api, fileUrl, fmtCost, fmtTime } from "../api.js";
import { Badge, Button, Card, ErrorBox, Field, Spinner } from "../ui.jsx";
import VoicePicker from "./VoicePicker.jsx";

export function AudioTab({ d, slug, reload, running }) {
  const [catalog, setCatalog] = useState(null);
  const [settings, setSettings] = useState(null);
  const [voice, setVoice] = useState(d.meta.options?.voice || {});
  const [err, setErr] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);
  const m = d.meta;
  useEffect(() => {
    api.get("/api/providers").then((x) => setCatalog(x.catalog));
    api.get("/api/settings").then((x) => setSettings(x.settings));
  }, []);
  const beats = d.script?.beats || [];
  const vb = d.voice?.beats || [];

  async function setProvider(stage, id) {
    await api.put(`/api/projects/${encodeURIComponent(slug)}/options`, { providers: { [stage]: id } });
    reload();
  }

  return (
    <div className="space-y-4">
      <Card title="Voice settings">
        {catalog && (
          <Field label="Voice provider" className="mb-3">
            <select value={m.providers.voice} onChange={(e) => setProvider("voice", e.target.value)} disabled={running}>
              {catalog.voice.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                  {!p.available ? " (not set up)" : ""}
                </option>
              ))}
            </select>
          </Field>
        )}
        {settings && <VoicePicker provider={m.providers.voice} settings={settings} value={voice} onChange={setVoice} />}
        <div className="mt-3 flex gap-2">
          <Button
            disabled={running}
            onClick={async () => {
              await api.put(`/api/projects/${encodeURIComponent(slug)}/options`, { options: { voice } });
              if (confirm("Voice settings saved. Re-generate the narration now? (Only lines that changed are redone.)"))
                await api.post(`/api/projects/${encodeURIComponent(slug)}/run`, { start: "voice" });
              reload();
            }}
          >
            Save voice settings
          </Button>
        </div>
      </Card>

      <Card title={`Narration${d.voice?.total ? ` · ${fmtTime(d.voice.total)}` : ""}`}>
        {vb.length === 0 && <p className="text-sm text-stone-500">No narration yet.</p>}
        <div className="space-y-2">
          {beats.map((b, i) =>
            d.scenes[i]?.has_audio ? (
              <div key={i} className="flex flex-wrap items-center gap-3 border-b border-stone-100 pb-2 dark:border-zinc-800">
                <span className="w-8 font-mono text-xs text-stone-400">#{i}</span>
                <audio controls preload="none" src={fileUrl(slug, `audio/b_${String(i).padStart(3, "0")}.wav`, Math.round(d.meta.updated))} className="h-8" />
                <span className="text-xs text-stone-500">{vb[i]?.dur ? `${vb[i].dur.toFixed(1)}s` : ""}</span>
                <span className="min-w-0 flex-1 truncate text-sm">{b.text}</span>
                {vb[i] && vb[i].text !== b.text && <Badge kind="awaiting_review">script changed</Badge>}
              </div>
            ) : null
          )}
        </div>
        <p className="mt-3 text-xs text-stone-500 dark:text-zinc-400">
          Pronunciations (e.g. Meiji → May-jee) are in Settings. Captions always keep the original spelling.
        </p>
      </Card>

      <Card title="Music">
        {catalog && (
          <Field label="Music source" className="mb-3">
            <select value={m.providers.music} onChange={(e) => setProvider("music", e.target.value)} disabled={running}>
              {catalog.music.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                  {!p.available ? " (not set up)" : ""}
                </option>
              ))}
            </select>
          </Field>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,.flac,.aac"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setUploading(true);
              setErr(null);
              try {
                const fd = new FormData();
                fd.append("file", file);
                await api.upload(`/api/projects/${encodeURIComponent(slug)}/music`, fd);
                reload();
              } catch (x) {
                setErr(x.message);
              } finally {
                setUploading(false);
              }
            }}
          />
          <Button onClick={() => fileRef.current.click()} disabled={uploading}>
            {uploading ? <Spinner /> : "⬆"} Upload my own music
          </Button>
          {m.options?.music_file && <span className="text-sm text-stone-500">Using: {m.options.music_file}</span>}
          {d.meta.stages?.mix?.status === "done" && (
            <Button disabled={running} onClick={() => api.post(`/api/projects/${encodeURIComponent(slug)}/run`, { start: "mix" }).then(reload)}>
              Re-mix with this music
            </Button>
          )}
        </div>
        <p className="mt-2 text-xs text-stone-500 dark:text-zinc-400">Use royalty-free music only. It loops under the whole video, about 13 dB below the voice.</p>
        <ErrorBox error={err} />
      </Card>
    </div>
  );
}

export function SourceTab({ d, slug }) {
  const s = d.source;
  const [transcript, setTranscript] = useState(null);
  useEffect(() => {
    if (s?.has_transcript)
      fetch(fileUrl(slug, "source/transcript.txt"))
        .then((r) => r.text())
        .then(setTranscript)
        .catch(() => {});
  }, [slug, s?.has_transcript]);
  if (!s) return <Card><p className="text-sm text-stone-500">The source video hasn't been read yet.</p></Card>;
  const vn = s.visual_notes;
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex gap-4">
          {s.thumbnail && <img src={s.thumbnail} className="w-48 rounded-lg" alt="" />}
          <div>
            <a href={s.url} target="_blank" rel="noreferrer" className="text-lg font-semibold hover:underline">
              {s.title}
            </a>
            <div className="text-sm text-stone-500">
              {s.channel} · {fmtTime(s.duration)}
            </div>
          </div>
        </div>
      </Card>
      {vn && (
        <Card title="What the AI saw when it watched the video">
          <p className="text-sm">
            <b>Style:</b> {vn.style}
          </p>
          {vn.characters?.length > 0 && (
            <p className="mt-1 text-sm">
              <b>Characters:</b> {vn.characters.join("; ")}
            </p>
          )}
          {vn.running_gags?.length > 0 && (
            <p className="mt-1 text-sm">
              <b>Running gags:</b> {vn.running_gags.join("; ")}
            </p>
          )}
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer">Moment by moment ({vn.moments?.length || 0})</summary>
            <ul className="mt-1 space-y-0.5 text-xs">
              {(vn.moments || []).map((x, i) => (
                <li key={i}>
                  <span className="font-mono">{fmtTime(x.time)}</span> {x.visual}
                </li>
              ))}
            </ul>
          </details>
        </Card>
      )}
      {s.sheets?.length > 0 && (
        <Card title="Frames it looked at">
          <div className="grid gap-2 md:grid-cols-2">
            {s.sheets.map((f) => (
              <img key={f} src={fileUrl(slug, `source/sheets/${f}`)} className="rounded-lg" alt="" />
            ))}
          </div>
        </Card>
      )}
      {transcript && (
        <Card title="Transcript (research material only, never copied)">
          <pre className="mono max-h-96 overflow-y-auto whitespace-pre-wrap text-xs">{transcript}</pre>
        </Card>
      )}
    </div>
  );
}

const EST_LABELS = { source: "Watch source", script: "Script", storyboard: "Storyboard", voice: "Voice", mix: "Music", package: "Title & thumbnail" };

export function CostsTab({ d, slug, log }) {
  const [runlog, setRunlog] = useState("");
  const [catalog, setCatalog] = useState(null);
  const m = d.meta;
  useEffect(() => {
    fetch(fileUrl(slug, "run.log", Date.now()))
      .then((r) => (r.ok ? r.text() : ""))
      .then((t) => setRunlog(t.split("\n").slice(-150).join("\n")));
    api.get("/api/providers").then((x) => setCatalog(x.catalog));
  }, [slug, m.updated]);
  const spentUsd = (m.costs || []).reduce((a, c) => a + (c.usd || 0), 0);
  const spentCr = (m.costs || []).reduce((a, c) => a + (c.credits || 0), 0);
  return (
    <div className="space-y-4">
      <Card title="Tools for this video">
        {catalog && (
          <div className="grid gap-3 sm:grid-cols-2">
            {["transcript", "llm", "voice", "music", "image"]
              .filter((st) => st !== "transcript" || m.mode === "youtube")
              .map((st) => (
                <Field key={st} label={{ transcript: "Transcript", llm: "Writer", voice: "Voice", music: "Music", image: "Thumbnail art" }[st]}>
                  <select
                    className="w-full"
                    value={m.providers[st]}
                    onChange={async (e) => {
                      await api.put(`/api/projects/${encodeURIComponent(slug)}/options`, { providers: { [st]: e.target.value } });
                      window.location.reload();
                    }}
                  >
                    {catalog[st].map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                        {!p.available ? " (not set up)" : ""}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
          </div>
        )}
      </Card>
      <Card title="Estimated cost of the remaining paid steps">
        {Object.entries(d.estimate || {}).filter(([, e]) => !e.total.free).length === 0 ? (
          <p className="text-sm text-emerald-700 dark:text-emerald-400">Nothing left to pay for: every remaining step is free.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {Object.entries(d.estimate)
              .filter(([, e]) => !e.total.free)
              .map(([st, e]) => (
                <li key={st} className="flex justify-between">
                  <span>{EST_LABELS[st] || st}</span>
                  <span>
                    {fmtCost(e.total)} {m.approvals?.[st] && <Badge kind="done">approved</Badge>}
                  </span>
                </li>
              ))}
          </ul>
        )}
      </Card>
      <Card title={`Spent on this video: $${spentUsd.toFixed(2)}${spentCr ? ` + ${Math.round(spentCr).toLocaleString()} credits` : ""}`}>
        {(m.costs || []).length === 0 ? (
          <p className="text-sm text-stone-500">Nothing spent. 🎉</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {m.costs.map((c, i) => (
                <tr key={i} className="border-b border-stone-100 dark:border-zinc-800">
                  <td className="py-1">{c.stage}</td>
                  <td>{c.provider}</td>
                  <td>{c.usd ? `$${c.usd.toFixed(3)}` : ""}</td>
                  <td>{c.credits ? `${Math.round(c.credits)} cr` : ""}</td>
                  <td className="text-xs text-stone-500">{c.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card title="Log">
        <pre className="mono max-h-96 overflow-y-auto whitespace-pre-wrap text-xs">{runlog || log.join("\n") || "(empty)"}</pre>
      </Card>
    </div>
  );
}
