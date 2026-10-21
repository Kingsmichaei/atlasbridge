import { useEffect, useRef, useState, type ReactNode } from "react";

export function CopyButton({ text, label = "Copy", className = "" }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className={className || "btn btn-ghost px-3 py-1.5 text-xs"}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          // Older Android browsers: fall back to a hidden textarea.
          const t = document.createElement("textarea");
          t.value = text;
          document.body.appendChild(t);
          t.select();
          document.execCommand("copy");
          t.remove();
        }
        setDone(true);
        setTimeout(() => setDone(false), 1500);
      }}
    >
      {done ? "Copied" : label}
    </button>
  );
}

export function CodeBlock({ code, title }: { code: string; title?: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-[#1f2e26] bg-code">
      <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-2">
        <span className="truncate font-mono text-xs text-[#8fb7a1]">{title ?? ""}</span>
        <CopyButton text={code} className="rounded-md bg-white/10 px-2.5 py-1 text-xs font-semibold text-white hover:bg-white/20" />
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-[#d7e8dd]"><code>{code}</code></pre>
    </div>
  );
}

/** Tabs over several code samples (curl / Python / JavaScript ...). */
export function CodeTabs({ samples }: { samples: { label: string; title?: string; code: string }[] }) {
  const [i, setI] = useState(0);
  return (
    <div>
      <div className="mb-2 flex gap-1 overflow-x-auto" role="tablist">
        {samples.map((s, j) => (
          <button
            key={s.label}
            role="tab"
            aria-selected={i === j}
            onClick={() => setI(j)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap ${i === j ? "bg-brand-dark text-white" : "text-muted hover:text-ink"}`}
          >
            {s.label}
          </button>
        ))}
      </div>
      <CodeBlock code={samples[i].code} title={samples[i].title} />
    </div>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose?: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && onClose) onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-2xl bg-white p-6 shadow-xl outline-none sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-lg font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <p className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger" role="alert">{children}</p>;
}

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-1 text-3xl font-bold tracking-tight">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}
