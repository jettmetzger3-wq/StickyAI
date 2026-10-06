import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, cx, ErrorBox, Spinner } from "../ui.jsx";
import { withApproval } from "./Project.jsx";

const KINDS_HINT =
  "japan, army, navy, america, tophat, britain, bowler, china, ussr, furhat, germany, helmet, italy, dutch, france, beret, marine, student, pilot, glasses, crown, roman, laurel, viking, pirate, tricorn, bicorne, cowboy, knight, wizard, pharaoh, turban, chef, graduate, samurai, hardhat, astronaut, mitre, cap, headband, civ";

export default function ScriptTab({ d, slug, reload, running }) {
  const script = d.script;
  const [beats, setBeats] = useState([]);
  const [facts, setFacts] = useState([]);
  const [cast, setCast] = useState([]);
  const [title, setTitle] = useState("");
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  const [busyBeat, setBusyBeat] = useState(null);

  useEffect(() => {
    if (!script || dirty) return;
    setBeats(script.beats.map((b, i) => ({ ...b, origin: i })));
    setFacts(script.facts || []);
    setCast(script.cast || []);
    setTitle(script.title || "");
  }, [script, dirty]);

  const words = useMemo(() => beats.reduce((a, b) => a + b.text.split(/\s+/).filter(Boolean).length, 0), [beats]);
  if (!script)
    return (
      <Card>
        <p className="text-sm text-stone-500 dark:text-zinc-400">{running ? "Writing the script…" : "No script yet. Press Start."}</p>
      </Card>
    );

  const edit = (i, patch) => {
    setBeats((bs) => bs.map((b, k) => (k === i ? { ...b, ...patch } : b)));
    setDirty(true);
  };
  const move = (i, dir) => {
    setBeats((bs) => {
      const a = [...bs];
      const j = i + dir;
      if (j < 0 || j >= a.length) return a;
      [a[i], a[j]] = [a[j], a[i]];
      return a;
    });
    setDirty(true);
  };

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      await api.put(`/api/projects/${encodeURIComponent(slug)}/script`, { title, beats, facts, cast });
      setDirty(false);
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function regen(i) {
    const instruction = prompt("Optional: how should this beat change? (leave empty to just rewrite it)", "");
    if (instruction === null) return;
    setBusyBeat(i);
    try {
      const r = await withApproval((approved) =>
        api.post(`/api/projects/${encodeURIComponent(slug)}/beats/${i}/regenerate`, { instruction, approved })
      );
      if (r?.beat) edit(i, r.beat);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusyBeat(null);
    }
  }

  async function toggleFact(k) {
    const nf = facts.map((f, j) => (j === k ? { ...f, checked: !f.checked } : f));
    setFacts(nf);
    await api.put(`/api/projects/${encodeURIComponent(slug)}/facts`, { facts: nf }).catch(() => {});
  }

  const checked = facts.filter((f) => f.checked).length;
  return (
    <div className="space-y-4">
      <Card
        title={
          <span>
            Script <span className="text-sm font-normal text-stone-500">· {beats.length} beats · {words} words · ~{(words / 150).toFixed(1)} min</span>
          </span>
        }
        actions={
          <>
            {dirty && <span className="text-xs text-amber-600">unsaved changes</span>}
            <Button variant="primary" disabled={!dirty || saving || running} onClick={save}>
              {saving ? <Spinner /> : null} Save script
            </Button>
          </>
        }
      >
        <input
          className="mb-3 w-full text-lg font-semibold"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            setDirty(true);
          }}
        />
        <ErrorBox error={err} />
        <div className="space-y-2">
          {beats.map((b, i) => {
            const n = b.text.split(/\s+/).filter(Boolean).length;
            return (
              <div key={i} className="group flex gap-2 rounded-xl border border-stone-200 p-2 dark:border-zinc-800">
                <div className="flex w-20 shrink-0 flex-col items-center gap-1 pt-1 text-xs text-stone-400">
                  <span className="font-mono">#{i}</span>
                  <select
                    value={b.mood}
                    onChange={(e) => edit(i, { mood: e.target.value })}
                    className={cx("w-20 px-1 py-0.5 text-xs", b.mood === "somber" && "bg-slate-200 dark:bg-slate-800")}
                  >
                    <option value="fun">fun</option>
                    <option value="tense">tense</option>
                    <option value="somber">somber</option>
                  </select>
                </div>
                <textarea
                  className="min-h-[3.2rem] flex-1 resize-y border-0 bg-transparent px-1 py-1 focus:ring-1 dark:bg-transparent"
                  value={b.text}
                  rows={2}
                  onChange={(e) => edit(i, { text: e.target.value })}
                />
                <div className="flex w-24 shrink-0 flex-col items-end gap-1">
                  <span className={cx("text-xs", n > 30 ? "text-red-600" : "text-stone-400")}>{n} words</span>
                  <div className="flex gap-1 opacity-60 group-hover:opacity-100">
                    <button title="Move up" className="px-1" onClick={() => move(i, -1)}>
                      ↑
                    </button>
                    <button title="Move down" className="px-1" onClick={() => move(i, 1)}>
                      ↓
                    </button>
                    <button
                      title="Insert a beat after"
                      className="px-1"
                      onClick={() => {
                        setBeats((bs) => [...bs.slice(0, i + 1), { mood: b.mood, text: "New beat.", origin: null }, ...bs.slice(i + 1)]);
                        setDirty(true);
                      }}
                    >
                      +
                    </button>
                    <button
                      title="Delete"
                      className="px-1 text-red-600"
                      onClick={() => {
                        setBeats((bs) => bs.filter((_, k) => k !== i));
                        setDirty(true);
                      }}
                    >
                      ×
                    </button>
                  </div>
                  <button className="text-xs text-amber-700 hover:underline dark:text-amber-400" disabled={busyBeat !== null} onClick={() => regen(i)}>
                    {busyBeat === i ? "rewriting…" : "↻ rewrite"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card
        title={
          <span>
            Fact checklist <span className="text-sm font-normal text-stone-500">· {checked}/{facts.length} checked</span>
          </span>
        }
      >
        <p className="mb-3 text-xs text-stone-500 dark:text-zinc-400">
          Every date, number and claim in the script. Tick each one after you verify it. Medium/low confidence ones deserve a quick search.
        </p>
        {script.factcheck && (
          <div className="mb-3 rounded-lg border border-stone-200 bg-stone-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-950">
            <p className="font-semibold">
              Auto fact-check{" "}
              <span className="font-normal text-stone-500">
                ({script.factcheck.web ? "Claude searched the web" : "from Claude's knowledge, no web search"})
              </span>
            </p>
            <p className="text-stone-600 dark:text-zinc-400">
              {script.factcheck.counts?.correct || 0} confirmed · {script.factcheck.counts?.wrong || 0} wrong
              {script.factcheck.fixed?.length ? ` (fixed in beat${script.factcheck.fixed.length > 1 ? "s" : ""} ${script.factcheck.fixed.map((i) => "#" + i).join(", ")})` : ""} ·{" "}
              {script.factcheck.counts?.unsure || 0} unsure (check these yourself)
            </p>
            {(script.factcheck.checks || [])
              .filter((c) => c.verdict !== "correct")
              .map((c, k) => (
                <p key={k} className="mt-1 text-xs text-stone-600 dark:text-zinc-400">
                  <Badge kind={c.verdict === "wrong" ? "error" : "paused"}>{c.verdict}</Badge> <span className="font-mono text-stone-400">#{c.beat}</span> {c.claim}
                  {c.correction && <span className="block pl-1">→ {c.correction}</span>}
                  {c.source && <span className="block pl-1 text-stone-400">source: {c.source}</span>}
                </p>
              ))}
          </div>
        )}
        <div className="space-y-1.5">
          {facts.map((f, k) => (
            <label key={k} className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={!!f.checked} onChange={() => toggleFact(k)} className="mt-0.5" />
              <span className="flex-1">
                <span className="mr-1 font-mono text-xs text-stone-400">#{f.beat}</span>
                {f.claim}
                {f.note && <span className="block text-xs text-stone-500 dark:text-zinc-400">{f.note}</span>}
              </span>
              {f.auto && (
                <span title={f.auto_note || ""}>
                  <Badge kind={f.auto === "correct" ? "done" : f.auto === "wrong" ? "error" : "paused"}>
                    {f.auto === "correct" ? "confirmed" : f.auto}
                  </Badge>
                </span>
              )}
              <Badge kind={f.confidence}>{f.confidence}</Badge>
            </label>
          ))}
          {facts.length === 0 && <p className="text-sm text-stone-500">No facts listed.</p>}
        </div>
      </Card>

      <Card title="Cast (who is who)">
        <p className="mb-2 text-xs text-stone-500 dark:text-zinc-400">Hats ("kind") the storyboard uses for each character. Options: {KINDS_HINT}.</p>
        <div className="space-y-2">
          {cast.map((c, k) => (
            <div key={k} className="grid grid-cols-[1fr_1fr_8rem_auto] gap-2">
              <input value={c.name} onChange={(e) => (setCast(cast.map((x, j) => (j === k ? { ...x, name: e.target.value } : x))), setDirty(true))} />
              <input value={c.kind} onChange={(e) => (setCast(cast.map((x, j) => (j === k ? { ...x, kind: e.target.value } : x))), setDirty(true))} />
              <input
                placeholder="hat color"
                value={c.hat_color || ""}
                onChange={(e) => (setCast(cast.map((x, j) => (j === k ? { ...x, hat_color: e.target.value } : x))), setDirty(true))}
              />
              <Button size="sm" variant="ghost" onClick={() => (setCast(cast.filter((_, j) => j !== k)), setDirty(true))}>
                ×
              </Button>
            </div>
          ))}
          <Button size="sm" onClick={() => (setCast([...cast, { name: "", kind: "civ", hat_color: "" }]), setDirty(true))}>
            + Add character
          </Button>
        </div>
      </Card>
    </div>
  );
}
