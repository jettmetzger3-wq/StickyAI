import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api.js";
import { cx, Spinner } from "./ui.jsx";
import Library from "./pages/Library.jsx";
import NewVideo from "./pages/NewVideo.jsx";
import ProjectPage from "./pages/Project.jsx";
import Settings from "./pages/Settings.jsx";
import Login from "./pages/Login.jsx";
import Pricing from "./pages/Pricing.jsx";
import Account from "./pages/Account.jsx";
import Admin from "./pages/Admin.jsx";

// Tiny hash router: #/  #/new  #/p/<slug>  #/settings  (hosted website: #/login #/pricing #/account #/admin)
function useRoute() {
  const [hash, setHash] = useState(window.location.hash || "#/");
  useEffect(() => {
    const h = () => setHash(window.location.hash || "#/");
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  return hash.replace(/^#/, "");
}

export const go = (path) => {
  window.location.hash = path;
};

// mode ("local" | "hosted"), the signed-in user with plan usage, pricing; reload() after login/purchases
export const ConfigContext = createContext({ mode: "local", user: null, reload: () => {} });
export const useConfig = () => useContext(ConfigContext);

function ThemeToggle() {
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));
  return (
    <button
      title="Toggle dark mode"
      className="rounded-lg px-2 py-1.5 text-lg hover:bg-stone-200/70 dark:hover:bg-zinc-800"
      onClick={() => {
        const d = !dark;
        setDark(d);
        document.documentElement.classList.toggle("dark", d);
        try {
          localStorage.setItem("theme", d ? "dark" : "light");
        } catch {}
      }}
    >
      {dark ? "☀️" : "🌙"}
    </button>
  );
}

function OnlineLink({ url }) {
  const [copied, setCopied] = useState(false);
  if (!url) return null;
  return (
    <button
      title={`Your online link (works while the start window is open): ${url}`}
      onClick={() => {
        navigator.clipboard?.writeText(url).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
      className="hidden max-w-[16rem] truncate rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-900 sm:inline dark:bg-emerald-900/40 dark:text-emerald-300"
    >
      {copied ? "Copied!" : `📱 ${url.replace("https://", "")}`}
    </button>
  );
}

function UsageChip({ user }) {
  const u = user?.usage;
  if (!u || u.unlimited) return null;
  const text =
    u.plan === "pro"
      ? `${u.pro_minutes_left} Pro min left`
      : `${Math.max(0, u.free_videos_limit - u.free_videos_used)} of ${u.free_videos_limit} free videos left` +
        (u.extra_minutes > 0 ? ` · ${u.extra_minutes} Pro min` : "");
  return (
    <a href="#/account" className="hidden rounded-full bg-stone-200/70 px-3 py-1 text-xs font-medium sm:inline dark:bg-zinc-800">
      {text}
    </a>
  );
}

export default function App() {
  const route = useRoute();
  const [health, setHealth] = useState(null);
  const [cfg, setCfg] = useState(null);

  const reload = useCallback(
    () =>
      api
        .get("/api/config")
        .then(setCfg)
        .catch(() => setCfg({ mode: "local", user: null })),
    []
  );
  useEffect(() => {
    reload();
    api.get("/api/health").then(setHealth).catch(() => setHealth({ ok: false }));
    const out = () => reload();
    window.addEventListener("studio:logged-out", out);
    return () => window.removeEventListener("studio:logged-out", out);
  }, [reload]);

  if (!cfg) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }
  const hosted = cfg.mode === "hosted";
  const priv = !!cfg.private; // your own studio online: one owner, no plans or payments
  const paid = !!cfg.pricing?.paid_plans; // Pro + payments switched on in Settings (off: the site is free-only)
  const user = cfg.user;
  const admin = !hosted || user?.is_admin;

  let page;
  if (hosted && !user) {
    if (route.startsWith("/pricing") && !priv && paid) page = <Pricing />;
    else page = <Login signup={route.startsWith("/signup")} />;
  } else if (route.startsWith("/p/")) page = <ProjectPage slug={decodeURIComponent(route.slice(3))} />;
  else if (route.startsWith("/new")) page = <NewVideo />;
  else if (route.startsWith("/settings") && admin) page = <Settings />;
  else if (route.startsWith("/pricing") && hosted && !priv && paid) page = <Pricing />;
  else if (route.startsWith("/account") && hosted) page = <Account />;
  else if (route.startsWith("/admin") && hosted && !priv && user?.is_admin) page = <Admin />;
  else page = <Library />;

  const nav = [];
  if (!hosted || user) {
    nav.push(["#/", "Library", route === "/" || route === ""], ["#/new", "New video", route.startsWith("/new")]);
  }
  if (hosted && !priv && paid) nav.push(["#/pricing", "Pricing", route.startsWith("/pricing")]);
  if (hosted && user) nav.push(["#/account", "Account", route.startsWith("/account")]);
  if (hosted && !priv && user?.is_admin) nav.push(["#/admin", "Admin", route.startsWith("/admin")]);
  if (admin && (!hosted || user)) nav.push(["#/settings", "Settings", route.startsWith("/settings")]);

  async function logout() {
    await api.post("/api/auth/logout").catch(() => {});
    await reload();
    go("/login");
  }

  return (
    <ConfigContext.Provider value={{ ...cfg, reload }}>
      <div className="min-h-full">
        <header className="sticky top-0 z-40 border-b border-stone-200 bg-stone-50/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
            <a href="#/" className="flex items-center gap-2 font-bold">
              <img src="/favicon.svg" className="h-8 w-8" alt="" />
              <span className="text-lg">Stickman Studio</span>
            </a>
            <nav className="flex flex-wrap gap-1 sm:ml-4">
              {nav.map(([href, label, active]) => (
                <a
                  key={href}
                  href={href}
                  className={cx(
                    "rounded-lg px-3 py-1.5 text-sm font-medium",
                    active ? "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-300" : "hover:bg-stone-200/70 dark:hover:bg-zinc-800"
                  )}
                >
                  {label}
                </a>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-2">
              {health && !health.ffmpeg && admin && (
                <span className="rounded-lg bg-red-100 px-2 py-1 text-xs text-red-800 dark:bg-red-900/40 dark:text-red-300">
                  ffmpeg not found: install it first
                </span>
              )}
              {hosted && user && <UsageChip user={user} />}
              {priv && user && <OnlineLink url={cfg.online_url} />}
              {hosted && user && (
                <button onClick={logout} className="rounded-lg px-2 py-1.5 text-sm hover:bg-stone-200/70 dark:hover:bg-zinc-800" title={user.email}>
                  Log out
                </button>
              )}
              {hosted && !priv && !user && !route.startsWith("/login") && route !== "/" && route !== "" && (
                <a href="#/login" className="rounded-lg bg-amber-500 px-3 py-1.5 text-sm font-medium text-zinc-950">
                  Log in
                </a>
              )}
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{page}</main>
      </div>
    </ConfigContext.Provider>
  );
}
