import { useEffect, useState } from "react";
import { api } from "./api.js";
import { cx } from "./ui.jsx";
import Library from "./pages/Library.jsx";
import NewVideo from "./pages/NewVideo.jsx";
import ProjectPage from "./pages/Project.jsx";
import Settings from "./pages/Settings.jsx";

// Tiny hash router: #/  #/new  #/p/<slug>  #/settings
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

export default function App() {
  const route = useRoute();
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.get("/api/health").then(setHealth).catch(() => setHealth({ ok: false }));
  }, []);

  let page;
  if (route.startsWith("/p/")) page = <ProjectPage slug={decodeURIComponent(route.slice(3))} />;
  else if (route.startsWith("/new")) page = <NewVideo />;
  else if (route.startsWith("/settings")) page = <Settings />;
  else page = <Library />;

  const nav = [
    ["#/", "Library", route === "/" || route === ""],
    ["#/new", "New video", route.startsWith("/new")],
    ["#/settings", "Settings", route.startsWith("/settings")],
  ];
  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-40 border-b border-stone-200 bg-stone-50/90 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <a href="#/" className="flex items-center gap-2 font-bold">
            <img src="/favicon.svg" className="h-8 w-8" alt="" />
            <span className="text-lg">Stickman Studio</span>
          </a>
          <nav className="ml-4 flex gap-1">
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
            {health && !health.ffmpeg && (
              <span className="rounded-lg bg-red-100 px-2 py-1 text-xs text-red-800 dark:bg-red-900/40 dark:text-red-300">
                ffmpeg not found: install it first
              </span>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{page}</main>
    </div>
  );
}
