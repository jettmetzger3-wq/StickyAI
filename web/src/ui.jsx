import { useEffect, useState } from "react";

export function cx(...a) {
  return a.filter(Boolean).join(" ");
}

export function Button({ variant = "default", size = "md", className, ...p }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const sizes = { sm: "px-2.5 py-1 text-xs", md: "px-3.5 py-2 text-sm", lg: "px-5 py-3 text-base" };
  const variants = {
    default:
      "border border-stone-300 bg-white hover:bg-stone-100 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800",
    primary: "bg-amber-500 text-zinc-950 hover:bg-amber-400 shadow-sm",
    danger: "bg-red-600 text-white hover:bg-red-500",
    ghost: "hover:bg-stone-200/70 dark:hover:bg-zinc-800",
    pay: "bg-emerald-600 text-white hover:bg-emerald-500 shadow-sm",
  };
  return <button className={cx(base, sizes[size], variants[variant], className)} {...p} />;
}

export function Card({ className, title, actions, children }) {
  return (
    <div className={cx("rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900", className)}>
      {(title || actions) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h3 className="text-base font-semibold">{title}</h3>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

const BADGE = {
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  running: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300",
  pending: "bg-stone-100 text-stone-600 dark:bg-zinc-800 dark:text-zinc-400",
  skipped: "bg-stone-100 text-stone-400 dark:bg-zinc-800 dark:text-zinc-500",
  error: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  awaiting_review: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  awaiting_approval: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  paused: "bg-stone-100 text-stone-700 dark:bg-zinc-800 dark:text-zinc-300",
  new: "bg-stone-100 text-stone-700 dark:bg-zinc-800 dark:text-zinc-300",
  free: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  paid: "bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300",
  fun: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  tense: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300",
  somber: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};
const LABEL = { awaiting_review: "needs review", awaiting_approval: "needs approval" };

export function Badge({ kind, children, className }) {
  return (
    <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", BADGE[kind] || BADGE.pending, className)}>
      {children ?? LABEL[kind] ?? kind}
    </span>
  );
}

export function Progress({ value, className }) {
  return (
    <div className={cx("h-2 w-full overflow-hidden rounded-full bg-stone-200 dark:bg-zinc-800", className)}>
      <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${Math.round((value || 0) * 100)}%` }} />
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }) {
  return (
    <label
      className="flex cursor-pointer select-none items-start gap-3"
      onClick={(e) => {
        e.preventDefault();
        onChange(!checked);
      }}
    >
      <span
        role="switch"
        aria-checked={checked}
        className={cx(
          "relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full transition",
          checked ? "bg-amber-500" : "bg-stone-300 dark:bg-zinc-700"
        )}
      >
        <span className={cx("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition", checked ? "left-4.5" : "left-0.5")} />
      </span>
      <span>
        <span className="text-sm font-medium">{label}</span>
        {hint && <span className="block text-xs text-stone-500 dark:text-zinc-400">{hint}</span>}
      </span>
    </label>
  );
}

export function Field({ label, hint, children, className }) {
  return (
    <label className={cx("block", className)}>
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-stone-500 dark:text-zinc-400">{hint}</span>}
    </label>
  );
}

export function Modal({ open, onClose, title, children, wide }) {
  useEffect(() => {
    if (!open) return;
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4" onClick={onClose}>
      <div
        className={cx("my-8 w-full rounded-2xl bg-white p-5 shadow-xl dark:bg-zinc-900", wide ? "max-w-6xl" : "max-w-lg")}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="rounded-lg px-2 py-1 text-xl leading-none hover:bg-stone-100 dark:hover:bg-zinc-800">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }) {
  const [done, setDone] = useState(false);
  return (
    <Button
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text || "");
        } catch {
          const ta = document.createElement("textarea");
          ta.value = text || "";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? "Copied!" : label}
    </Button>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
      {String(error)}
    </div>
  );
}

export function Spinner() {
  return <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" />;
}
