import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, ErrorBox, Field, Progress, Spinner } from "../ui.jsx";
import { useConfig } from "../App.jsx";
import { checkout } from "./Pricing.jsx";

export default function Account() {
  const cfg = useConfig();
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(null);
  const [pw, setPw] = useState({ old: "", new: "" });
  const [pwMsg, setPwMsg] = useState(null);
  const paid = /paid=(\w+)/.exec(window.location.hash)?.[1];

  // after Stripe sends you back, the webhook may take a few seconds: refresh a few times
  useEffect(() => {
    if (!paid) return;
    let n = 0;
    const t = setInterval(() => {
      cfg.reload();
      if (++n >= 5) clearInterval(t);
    }, 3000);
    return () => clearInterval(t);
  }, [paid]);

  const user = cfg.user;
  if (!user) return <Spinner />;
  const u = user.usage;
  const pricing = cfg.pricing;
  const billing = cfg.billing || {};
  const isPro = u.plan === "pro";

  async function portal() {
    setErr(null);
    setBusy("portal");
    try {
      const r = await api.post("/api/billing/portal");
      window.location.href = r.url;
    } catch (e) {
      setErr(e.message);
      setBusy(null);
    }
  }
  async function changePw(e) {
    e.preventDefault();
    setPwMsg(null);
    try {
      await api.post("/api/auth/password", pw);
      setPw({ old: "", new: "" });
      setPwMsg("Password changed.");
    } catch (e2) {
      setPwMsg(e2.message);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-2xl font-bold">Account</h1>
      {paid && (
        <div className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300">
          Thanks! Your payment went through. {paid === "pro" ? "Pro" : "Your minutes"} will show up here within a few seconds.
        </div>
      )}
      <ErrorBox error={err} />
      <Card title="Your plan" actions={<Badge kind={isPro ? "paid" : "free"}>{isPro ? "Pro" : "Free"}</Badge>}>
        <div className="text-sm text-stone-500 dark:text-zinc-400">{user.email}</div>
        {u.unlimited ? (
          <p className="mt-3 text-sm">Admin account: no limits.</p>
        ) : (
          <div className="mt-4 space-y-4">
            {!isPro && (
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Free videos this month</span>
                  <span>
                    {u.free_videos_used} of {u.free_videos_limit} used
                  </span>
                </div>
                <Progress value={u.free_videos_limit ? u.free_videos_used / u.free_videos_limit : 1} />
              </div>
            )}
            {isPro && (
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span>Pro minutes this month</span>
                  <span>
                    {u.pro_minutes_used} of {u.pro_minutes_monthly} used
                  </span>
                </div>
                <Progress value={u.pro_minutes_monthly ? Math.min(1, u.pro_minutes_used / u.pro_minutes_monthly) : 1} />
              </div>
            )}
            {u.extra_minutes > 0 && (
              <div className="text-sm">
                Extra Pro minutes from packs: <b>{u.extra_minutes}</b> (never expire)
              </div>
            )}
            <div className="text-xs text-stone-500 dark:text-zinc-400">Monthly allowances reset on the 1st (UTC). Current month: {u.month}.</div>
          </div>
        )}
        <div className="mt-5 flex flex-wrap gap-2">
          {!isPro && billing.enabled && (
            <Button variant="pay" disabled={!!busy} onClick={() => checkout("pro", setErr, setBusy)}>
              {busy === "pro" && <Spinner />} Upgrade to Pro (${pricing?.plans?.pro?.price_usd}/month)
            </Button>
          )}
          {billing.packs && (
            <Button disabled={!!busy} onClick={() => checkout("pack", setErr, setBusy)}>
              {busy === "pack" && <Spinner />} Buy {pricing?.pack?.minutes} Pro minutes (${pricing?.pack?.price_usd})
            </Button>
          )}
          {user.has_billing && (
            <Button disabled={!!busy} onClick={portal}>
              {busy === "portal" && <Spinner />} Manage billing & invoices
            </Button>
          )}
          {!billing.enabled && <span className="text-sm text-stone-500">Online payments aren't switched on yet.</span>}
        </div>
        {user.sub_status && user.sub_status !== "active" && (
          <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">Subscription status: {user.sub_status.replace("_", " ")}</p>
        )}
      </Card>
      <Card title="Change password">
        <form onSubmit={changePw} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Field label="Current password">
            <input type="password" autoComplete="current-password" className="w-full" value={pw.old} onChange={(e) => setPw({ ...pw, old: e.target.value })} />
          </Field>
          <Field label="New password">
            <input type="password" autoComplete="new-password" minLength={8} className="w-full" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} />
          </Field>
          <Button disabled={!pw.old || pw.new.length < 8}>Change</Button>
        </form>
        {pwMsg && <p className="mt-2 text-sm">{pwMsg}</p>}
      </Card>
    </div>
  );
}
