import { useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, ErrorBox, Spinner } from "../ui.jsx";
import { go, useConfig } from "../App.jsx";

export async function checkout(kind, setErr, setBusy) {
  setErr(null);
  setBusy(kind);
  try {
    const r = await api.post("/api/billing/checkout", { kind });
    window.location.href = r.url; // Stripe's own payment page
  } catch (e) {
    setErr(e.message);
    setBusy(null);
  }
}

export default function Pricing() {
  const cfg = useConfig();
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(null);
  const p = cfg.pricing;
  if (!p) return <Spinner />;
  if (!p.paid_plans) {
    return (
      <div className="mx-auto max-w-xl py-10 text-center">
        <h1 className="text-3xl font-bold">It's free</h1>
        <p className="mt-2 text-stone-600 dark:text-zinc-400">
          Everyone gets {p.plans.free.videos_per_month} videos a month, up to {p.plans.free.max_minutes} minutes each. No card needed.
        </p>
        <Button variant="primary" size="lg" className="mt-6" onClick={() => go(cfg.user ? "/new" : "/signup")}>
          {cfg.user ? "Make a video" : "Create a free account"}
        </Button>
      </div>
    );
  }
  const free = p.plans.free;
  const pro = p.plans.pro;
  const user = cfg.user;
  const isPro = user?.plan === "pro";
  const billing = cfg.billing || {};

  const features = {
    free: [
      `${free.videos_per_month} videos a month`,
      `Up to ${free.max_minutes} minutes each`,
      "Claude writes the script and storyboard",
      "Natural offline voice (Kokoro)",
      "Built-in music, sound effects and thumbnail",
      "Free stickman Short for every video",
      free.watermark ? "Small \"Made with Stickman Studio\" mark" : "No watermark",
    ],
    pro: [
      `${pro.pro_minutes} Pro minutes every month`,
      `Videos up to ${pro.max_minutes} minutes`,
      "ElevenLabs studio voice with exact word timing",
      "AI-composed music and AI thumbnail art",
      "Stickman Short for every video",
      "No watermark",
      "Cancel any time",
    ],
  };

  const card = (id, plan, price, per, cta) => (
    <Card className={id === "pro" ? "border-2 border-amber-500" : ""}>
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">{plan.name}</h2>
        {id === "pro" && <Badge kind="paid">most popular</Badge>}
      </div>
      <div className="mt-2">
        <span className="text-4xl font-bold">{price}</span>
        <span className="text-stone-500 dark:text-zinc-400">{per}</span>
      </div>
      <ul className="mt-4 space-y-1.5 text-sm">
        {features[id].map((f) => (
          <li key={f}>✓ {f}</li>
        ))}
      </ul>
      <div className="mt-5">{cta}</div>
    </Card>
  );

  const freeCta = user ? (
    <Button className="w-full" onClick={() => go("/new")}>
      {isPro ? "Included" : "Make a free video"}
    </Button>
  ) : (
    <Button className="w-full" onClick={() => go("/signup")}>
      Start free
    </Button>
  );
  const proCta = !user ? (
    <Button variant="primary" className="w-full" onClick={() => go("/signup")}>
      Create an account to upgrade
    </Button>
  ) : isPro ? (
    <Button className="w-full" onClick={() => go("/account")}>
      You're on Pro
    </Button>
  ) : billing.enabled ? (
    <Button variant="pay" className="w-full" disabled={!!busy} onClick={() => checkout("pro", setErr, setBusy)}>
      {busy === "pro" && <Spinner />} Upgrade to Pro
    </Button>
  ) : (
    <Button className="w-full" disabled>
      Payments open soon
    </Button>
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="text-center">
        <h1 className="text-3xl font-bold">Simple pricing</h1>
        <p className="mt-1 text-stone-500 dark:text-zinc-400">Start free. Upgrade when you want studio-quality voice and music.</p>
      </div>
      <ErrorBox error={err} />
      <div className="grid gap-5 md:grid-cols-2">
        {card("free", free, "$0", "", freeCta)}
        {card("pro", pro, `$${pro.price_usd}`, " / month", proCta)}
      </div>
      <Card title={`Need more? ${p.pack.name}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-stone-600 dark:text-zinc-400">
            A one-time pack of {p.pack.minutes} Pro minutes for <b>${p.pack.price_usd}</b>. Pack minutes never expire and work on any plan.
          </p>
          {user && billing.packs ? (
            <Button variant="pay" disabled={!!busy} onClick={() => checkout("pack", setErr, setBusy)}>
              {busy === "pack" && <Spinner />} Buy {p.pack.minutes} minutes
            </Button>
          ) : null}
        </div>
      </Card>
      <Card title="How Pro minutes work">
        <ul className="space-y-1.5 text-sm text-stone-600 dark:text-zinc-400">
          <li>• A Pro minute is one minute of finished video made with the Pro tools. A 10-minute video uses 10 Pro minutes.</li>
          <li>• We set the minutes aside when your video starts. If it comes out shorter, the difference goes straight back.</li>
          <li>• Delete a video before it's finished and you get all of its minutes back.</li>
          <li>• Monthly minutes reset on the 1st (UTC). Pack minutes are used after your monthly ones and never expire.</li>
          <li>• Payments are handled by Stripe. We never see your card number. Cancel any time from your account page.</li>
        </ul>
      </Card>
    </div>
  );
}
