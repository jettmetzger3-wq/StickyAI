import { useState } from "react";
import { api } from "../api.js";
import { Button, Card, ErrorBox, Field, Spinner } from "../ui.jsx";
import { go, useConfig } from "../App.jsx";

export default function Login({ signup: startSignup }) {
  const cfg = useConfig();
  const [signup, setSignup] = useState(!!startSignup && cfg.signup !== false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const free = cfg.pricing?.plans?.free;

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.post(signup ? "/api/auth/signup" : "/api/auth/login", { email, password });
      await cfg.reload();
      go(signup ? "/new" : "/");
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-5xl items-center gap-10 py-6 lg:grid-cols-2">
      <div>
        <h1 className="text-4xl font-bold leading-tight">
          Paste a stickman video.
          <br />
          Get a brand-new one.
        </h1>
        <p className="mt-4 text-stone-600 dark:text-zinc-400">
          Stickman Studio watches a YouTube video, writes an original script on the same subject, draws every scene as an animated doodle, records the voice,
          adds music and captions, and hands you the finished video with titles, chapters, tags, a thumbnail and a Short.
        </p>
        <ul className="mt-4 space-y-1 text-sm text-stone-600 dark:text-zinc-400">
          {free && (
            <li>
              • <b>Free:</b> {free.videos_per_month} videos a month, up to {free.max_minutes} minutes each
            </li>
          )}
          <li>
            • <b>Pro:</b> studio voices, AI music and thumbnail art.{" "}
            <a href="#/pricing" className="underline">
              See pricing
            </a>
          </li>
        </ul>
      </div>
      <Card>
        <div className="mb-4 flex gap-1 rounded-xl bg-stone-100 p-1 dark:bg-zinc-800">
          {[
            [false, "Log in"],
            [true, "Create account"],
          ].map(([v, label]) => (
            <button
              key={label}
              onClick={() => setSignup(v)}
              disabled={v && cfg.signup === false}
              className={
                "flex-1 rounded-lg px-3 py-2 text-sm font-medium " + (signup === v ? "bg-white shadow-sm dark:bg-zinc-900" : "text-stone-500 dark:text-zinc-400")
              }
            >
              {label}
            </button>
          ))}
        </div>
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email">
            <input type="email" autoComplete="email" required className="w-full" value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" hint={signup ? "At least 8 characters." : ""}>
            <input
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              required
              minLength={signup ? 8 : undefined}
              className="w-full"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <ErrorBox error={err} />
          <Button variant="primary" size="lg" className="w-full" disabled={busy}>
            {busy && <Spinner />}
            {signup ? "Create my free account" : "Log in"}
          </Button>
          {cfg.signup === false && <p className="text-xs text-stone-500">New sign-ups are closed right now.</p>}
        </form>
      </Card>
    </div>
  );
}
