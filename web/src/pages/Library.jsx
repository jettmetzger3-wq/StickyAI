import { useEffect, useState } from "react";
import { api, fileUrl } from "../api.js";
import { Badge, Button, Card } from "../ui.jsx";

export default function Library() {
  const [items, setItems] = useState(null);
  const [spent, setSpent] = useState(null);
  const load = () => api.get("/api/projects").then((d) => setItems(d.projects));
  useEffect(() => {
    load();
    api.get("/api/balances").then((d) => setSpent(d.spent)).catch(() => {});
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Your videos</h1>
          <p className="text-sm text-stone-500 dark:text-zinc-400">
            Paste a YouTube link (or type a topic) and get a brand-new stickman video, ready to post.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {spent && (spent.usd > 0 || spent.credits > 0) && (
            <span className="text-xs text-stone-500 dark:text-zinc-400">
              Spent so far: ${spent.usd.toFixed(2)}
              {spent.credits ? ` + ${Math.round(spent.credits).toLocaleString()} credits` : ""}
            </span>
          )}
          <a href="#/new">
            <Button variant="primary" size="lg">+ New video</Button>
          </a>
        </div>
      </div>
      {items && items.length === 0 && (
        <Card className="py-16 text-center">
          <div className="mb-2 text-5xl">🎬</div>
          <p className="mb-4 text-stone-600 dark:text-zinc-400">No videos yet.</p>
          <a href="#/new">
            <Button variant="primary">Make your first video</Button>
          </a>
        </Card>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(items || []).map((p) => (
          <a key={p.slug} href={`#/p/${encodeURIComponent(p.slug)}`} className="group">
            <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm transition group-hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
              <div className="aspect-video bg-stone-100 dark:bg-zinc-800">
                {p.has_thumb ? (
                  <img src={fileUrl(p.slug, "final/thumbnail.png", Math.round(p.updated))} className="h-full w-full object-cover" alt="" />
                ) : (
                  <div className="flex h-full items-center justify-center text-4xl opacity-40">✏️</div>
                )}
              </div>
              <div className="space-y-1 p-4">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="line-clamp-2 font-semibold">{p.title}</h3>
                  <Badge kind={p.running ? "running" : p.status}>{p.running ? "running" : undefined}</Badge>
                </div>
                <div className="flex flex-wrap gap-x-3 text-xs text-stone-500 dark:text-zinc-400">
                  <span>{p.mode === "youtube" ? "YouTube remake" : "Topic"}</span>
                  {p.minutes && <span>{p.minutes} min target</span>}
                  <span>{new Date(p.created * 1000).toLocaleDateString()}</span>
                  {p.spent_usd > 0 && <span>${p.spent_usd.toFixed(2)} spent</span>}
                </div>
              </div>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
