import { useEffect, useState } from "react";
import { api } from "../api.js";
import { Badge, Button, Card, ErrorBox, Spinner } from "../ui.jsx";

export default function Admin() {
  const [users, setUsers] = useState(null);
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState(null);
  const [q, setQ] = useState("");

  const load = () => {
    api.get("/api/admin/users").then((d) => setUsers(d.users)).catch((e) => setErr(e.message));
    api.get("/api/admin/stats").then(setStats).catch(() => {});
  };
  useEffect(load, []);

  async function update(u, patch) {
    setErr(null);
    try {
      const r = await api.put(`/api/admin/users/${u.id}`, patch);
      setUsers(users.map((x) => (x.id === u.id ? { ...x, ...r.user } : x)));
    } catch (e) {
      setErr(e.message);
    }
  }

  if (!users) return <Spinner />;
  const shown = users.filter((u) => u.email.includes(q.toLowerCase()));
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Admin</h1>
      <ErrorBox error={err} />
      {stats && (
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            ["Users", stats.users],
            ["Pro subscribers", stats.pro_users],
            ["Monthly revenue", `$${stats.mrr_usd.toFixed(2)}`],
            [`Tool spend (${stats.month})`, `$${stats.tool_spend_usd.toFixed(2)}`],
          ].map(([k, v]) => (
            <Card key={k}>
              <div className="text-xs text-stone-500 dark:text-zinc-400">{k}</div>
              <div className="text-2xl font-bold">{v}</div>
            </Card>
          ))}
        </div>
      )}
      {stats && !stats.billing.enabled && (
        <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-500/10 dark:text-amber-300">
          Payments are off: add STRIPE_SECRET_KEY, STRIPE_PRICE_PRO, STRIPE_PRICE_PACK and STRIPE_WEBHOOK_SECRET (see DEPLOY.md). Until then you can give people Pro by hand
          below.
        </div>
      )}
      <Card title="Users" actions={<input placeholder="search email" value={q} onChange={(e) => setQ(e.target.value)} />}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-stone-500 dark:text-zinc-400">
              <tr>
                <th className="py-2">Email</th>
                <th>Plan</th>
                <th>This month</th>
                <th>Videos</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} className="border-t border-stone-100 dark:border-zinc-800">
                  <td className="py-2">
                    {u.email} {u.is_admin && <Badge kind="paid">admin</Badge>} {u.disabled && <Badge kind="error">disabled</Badge>}
                    <div className="text-xs text-stone-500">{u.sub_status ? `Stripe: ${u.sub_status}` : ""}</div>
                  </td>
                  <td>
                    <select value={u.plan} onChange={(e) => update(u, { plan: e.target.value })}>
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                    </select>
                  </td>
                  <td className="text-xs">
                    {u.usage.free_videos_used} free videos · {u.usage.pro_minutes_used} Pro min
                    <div className="text-stone-500">{u.usage.extra_minutes} pack min</div>
                  </td>
                  <td>{u.projects}</td>
                  <td className="space-x-1 text-right whitespace-nowrap">
                    <Button
                      size="sm"
                      onClick={() => {
                        const m = prompt("Add how many Pro minutes? (negative to remove)", "10");
                        if (m && !isNaN(Number(m))) update(u, { add_minutes: Number(m) });
                      }}
                    >
                      + minutes
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => {
                        const p = prompt(`New password for ${u.email} (8+ characters)`);
                        if (p) update(u, { password: p });
                      }}
                    >
                      Reset password
                    </Button>
                    <Button size="sm" variant={u.disabled ? "default" : "ghost"} onClick={() => update(u, { disabled: !u.disabled })}>
                      {u.disabled ? "Enable" : "Disable"}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => confirm(`${u.is_admin ? "Remove" : "Give"} admin rights for ${u.email}?`) && update(u, { is_admin: !u.is_admin })}>
                      {u.is_admin ? "− admin" : "+ admin"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {stats?.by_provider?.length > 0 && (
        <Card title="Tool spend by provider this month">
          {stats.by_provider.map((r) => (
            <div key={r.provider} className="flex justify-between text-sm">
              <span>{r.provider}</span>
              <span>
                ${r.usd.toFixed(2)}
                {r.credits ? ` · ${Math.round(r.credits).toLocaleString()} credits` : ""}
              </span>
            </div>
          ))}
        </Card>
      )}
      <p className="text-xs text-stone-500 dark:text-zinc-400">
        Plans, prices, limits and the cost cap per video are in <a className="underline" href="#/settings">Settings</a> under "Website (hosted mode)".
      </p>
    </div>
  );
}
