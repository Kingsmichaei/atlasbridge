import { Link } from "react-router";

/** The AtlasBridge mark (same path as src/assets/mark.svg), drawn in the current text colour. */
export function Mark({ className = "h-7 w-auto" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 114" className={className} aria-hidden="true" fill="currentColor">
      <path d="M0 0 L64 44 L0 66 Z M15 44.98 L30.97 39.49 L15 28.52 Z M0 68 H42 A22 22 0 0 1 42 112 H0 Z M15 83 V97 H42 A7 7 0 0 0 42 83 Z M0 51 H15 V114 H0 Z" />
    </svg>
  );
}

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className={`flex items-center gap-2.5 no-underline ${light ? "text-white" : "text-ink"}`} aria-label="AtlasBridge home">
      <span className={light ? "text-white" : "text-brand"}><Mark className="h-7 w-auto" /></span>
      <span className="text-lg font-bold tracking-tight">AtlasBridge</span>
    </Link>
  );
}

export const ATTRIBUTION =
  "N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.";
