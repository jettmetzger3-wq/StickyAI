// Small fetch helpers for the Python backend.
async function request(method, url, body, isForm) {
  // X-Studio: other websites can't add this header, so they can't make the dashboard do things for them
  const opts = { method, headers: { "X-Studio": "1" }, credentials: "same-origin" };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
  }
  const res = await fetch(url, opts);
  let data = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (res.status === 401 && !url.startsWith("/api/auth/")) {
    // hosted website: the login expired; App shows the login page
    window.dispatchEvent(new Event("studio:logged-out"));
  }
  if (!res.ok) {
    const err = new Error((data && (data.detail || data.message)) || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (u) => request("GET", u),
  post: (u, b = {}) => request("POST", u, b),
  put: (u, b = {}) => request("PUT", u, b),
  del: (u) => request("DELETE", u),
  upload: (u, form) => request("POST", u, form, true),
};

export const fileUrl = (slug, path, v) =>
  `/api/projects/${slug}/file/${path}${v ? `?v=${v}` : ""}`;

export function fmtCost(c) {
  if (!c) return "free";
  const parts = [];
  if (c.usd) parts.push(`~$${c.usd.toFixed(2)}`);
  if (c.credits) parts.push(`~${Math.round(c.credits).toLocaleString()} ${c.credit_unit || "credits"}`);
  if (c.known === false) parts.push("amount set by provider");
  return parts.length ? parts.join(" + ") : "free";
}

export function sumCosts(list) {
  const t = { usd: 0, credits: 0, known: true, credit_unit: "" };
  for (const c of list) {
    if (!c) continue;
    t.usd += c.usd || 0;
    t.credits += c.credits || 0;
    if (c.known === false) t.known = false;
    t.credit_unit = t.credit_unit || c.credit_unit;
  }
  t.free = !t.usd && !t.credits && t.known;
  return t;
}

export function fmtTime(s) {
  if (s == null) return "";
  s = Math.round(s);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

export function fmtBytes(n) {
  if (!n) return "";
  if (n > 1e9) return (n / 1e9).toFixed(2) + " GB";
  if (n > 1e6) return (n / 1e6).toFixed(1) + " MB";
  return Math.round(n / 1e3) + " KB";
}

export function useEvents(slug, onEvent) {
  // returns a cleanup function; caller wires it in useEffect
  const es = new EventSource(`/api/events${slug ? `?project=${encodeURIComponent(slug)}` : ""}`);
  es.onmessage = (m) => {
    try {
      onEvent(JSON.parse(m.data));
    } catch {}
  };
  return () => es.close();
}
