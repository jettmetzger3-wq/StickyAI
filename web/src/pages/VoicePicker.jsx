import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { Button, Field, Spinner } from "../ui.jsx";

// Picks a voice for the selected voice provider and plays free previews.
export default function VoicePicker({ provider, settings, value, onChange }) {
  const [voices, setVoices] = useState([]);
  const [avail, setAvail] = useState(true);
  const [reason, setReason] = useState("");
  const [playing, setPlaying] = useState(false);
  const [err, setErr] = useState(null);
  const audio = useRef(null);
  const vs = settings.voice || {};

  useEffect(() => {
    setVoices([]);
    api
      .get(`/api/voices?provider=${provider}`)
      .then((d) => {
        setVoices(d.voices || []);
        setAvail(d.available);
        setReason(d.reason);
      })
      .catch(() => {});
  }, [provider]);

  const current =
    provider === "kokoro" ? value.kokoro_voice || vs.kokoro_voice : provider === "elevenlabs" ? value.elevenlabs_voice_id || vs.elevenlabs_voice_id : "default";
  const speed = value.kokoro_speed || vs.kokoro_speed || 1.2;

  async function play() {
    setErr(null);
    setPlaying(true);
    try {
      let src;
      if (provider === "elevenlabs") {
        const d = await api.get(`/api/voices/preview?provider=elevenlabs&voice=${encodeURIComponent(current)}`);
        src = d.url;
      } else {
        src = `/api/voices/preview?provider=${provider}&voice=${encodeURIComponent(current)}&speed=${provider === "kokoro" ? speed : 0}`;
        const r = await fetch(src);
        if (!r.ok) throw new Error((await r.json()).detail || "preview failed");
        src = URL.createObjectURL(await r.blob());
      }
      audio.current.src = src;
      await audio.current.play();
    } catch (e) {
      setErr(e.message);
    } finally {
      setPlaying(false);
    }
  }

  if (provider === "system") return <p className="text-sm text-stone-500">System voice (robotic, for testing only).</p>;
  return (
    <div className="space-y-3">
      {!avail && <p className="text-sm text-amber-700 dark:text-amber-400">{reason}</p>}
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto] sm:items-end">
        <Field label={provider === "kokoro" ? "Kokoro voice" : "ElevenLabs voice"}>
          <select
            className="w-full"
            value={current}
            onChange={(e) => onChange(provider === "kokoro" ? { ...value, kokoro_voice: e.target.value } : { ...value, elevenlabs_voice_id: e.target.value })}
          >
            {voices.length === 0 && <option value={current}>{current}</option>}
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
                {v.gender ? ` (${v.gender}, ${v.lang})` : v.category ? ` (${v.category})` : ""}
              </option>
            ))}
          </select>
        </Field>
        {provider === "kokoro" && (
          <Field label={`Speed ${speed}`}>
            <input
              type="range"
              min="0.8"
              max="1.5"
              step="0.05"
              value={speed}
              onChange={(e) => onChange({ ...value, kokoro_speed: Number(e.target.value) })}
            />
          </Field>
        )}
        <Button onClick={play} disabled={playing}>
          {playing ? <Spinner /> : "▶"} Preview
        </Button>
      </div>
      {provider === "kokoro" && <p className="text-xs text-stone-500 dark:text-zinc-400">The first preview downloads the Kokoro model (~340 MB) once.</p>}
      {provider === "elevenlabs" && <p className="text-xs text-stone-500 dark:text-zinc-400">Previews use ElevenLabs' free sample clips (no credits).</p>}
      {err && <p className="text-sm text-red-600">{err}</p>}
      <audio ref={audio} className="hidden" />
    </div>
  );
}
