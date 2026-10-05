import type { Context, Config } from "@netlify/functions";
import { getStore, getDeployStore } from "@netlify/blobs";
import { createHash, timingSafeEqual } from "node:crypto";

// The owner's studio runs on their own PC behind a free Cloudflare link that changes every time it starts.
// While it runs, it posts its current link here (with a secret) about once a minute; the "Open my studio" button
// asks for it. A link that hasn't been refreshed for 3 minutes counts as offline.
const STALE_MS = 3 * 60 * 1000;
const LINK_RE = /^https:\/\/[a-z0-9-]+\.trycloudflare\.com$/;

function store() {
  // production keeps its own data; previews and branch deploys get a throwaway store
  return Netlify.context?.deploy?.context === "production"
    ? getStore({ name: "studio", consistency: "strong" })
    : getDeployStore({ name: "studio", consistency: "strong" });
}

function sameSecret(given: string, expected: string) {
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}

export default async (req: Request, context: Context) => {
  const s = store();
  if (req.method === "GET") {
    const link = await s.get("link", { type: "json" });
    const fresh = link && Date.now() - link.at < STALE_MS;
    return Response.json(fresh ? { online: true, url: link.url } : { online: false },
                         { headers: { "Cache-Control": "no-store" } });
  }
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }
  const expected = Netlify.env.get("STUDIO_LINK_SECRET") || "";
  const auth = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  if (expected.length < 16 || !auth || !sameSecret(auth, expected)) {
    return new Response("Unauthorized", { status: 401 });
  }
  let body: { url?: string; offline?: boolean } = {};
  try {
    body = await req.json();
  } catch {
    return new Response("Bad request", { status: 400 });
  }
  if (body.offline) {
    await s.delete("link");
    return Response.json({ ok: true, online: false });
  }
  if (!body.url || !LINK_RE.test(body.url)) {
    return new Response("Only https://<name>.trycloudflare.com links are accepted", { status: 400 });
  }
  await s.setJSON("link", { url: body.url, at: Date.now() });
  return Response.json({ ok: true, online: true });
};

export const config: Config = {
  path: "/api/studio-link",
};
