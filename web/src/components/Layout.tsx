import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../lib/auth";
import { useHealth, type Status } from "../lib/health";
import { ATTRIBUTION, Logo } from "./Brand";

const GITHUB = "https://github.com/Kingsmichaei/atlasbridge";

const DOT: Record<Status["tone"], string> = {
  ok: "bg-brand-bright",
  warn: "bg-gold",
  bad: "bg-danger",
  unknown: "bg-muted",
};

export function StatusPill({ compact = false }: { compact?: boolean }) {
  const s = useHealth();
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted" title={s.detail} role="status">
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${DOT[s.tone]}`} aria-hidden="true" />
      <span className={compact ? "sr-only sm:not-sr-only" : ""}>{s.text}</span>
    </span>
  );
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-2 text-sm font-medium no-underline ${isActive ? "text-brand" : "text-ink hover:text-brand"}`;

function Header() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  const links = (
    <>
      <NavLink to="/guide" className={navClass}>Docs</NavLink>
      <NavLink to="/playground" className={navClass}>Playground</NavLink>
      {user && <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>}
      <a href={GITHUB} className={navClass({ isActive: false })} target="_blank" rel="noopener">GitHub</a>
    </>
  );

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
      <div className="container-x flex h-16 items-center gap-3">
        <Logo />
        <nav className="ml-4 hidden items-center gap-1 md:flex" aria-label="Main">{links}</nav>
        <div className="ml-auto flex items-center gap-3">
          <StatusPill compact />
          {user ? (
            <Link to="/dashboard" className="btn-ghost btn hidden sm:inline-flex">{user.name.split(" ")[0]}</Link>
          ) : (
            <span className="hidden items-center gap-2 sm:flex">
              <Link to="/login" className="btn btn-ghost">Log in</Link>
              <Link to="/signup" className="btn btn-primary">Get an API key</Link>
            </span>
          )}
          <button
            className="btn btn-ghost px-3 md:hidden"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label="Menu"
            onClick={() => setOpen((o) => !o)}
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="currentColor" aria-hidden="true">
              {open ? <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="2" /> : <path d="M3 5h14v2H3zM3 9h14v2H3zM3 13h14v2H3z" />}
            </svg>
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" className="container-x flex flex-col gap-1 border-t border-line pb-4 pt-2 md:hidden" aria-label="Main">
          {links}
          {!user && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Link to="/login" className="btn btn-ghost">Log in</Link>
              <Link to="/signup" className="btn btn-primary">Get an API key</Link>
            </div>
          )}
        </nav>
      )}
    </header>
  );
}

function Footer() {
  return (
    <footer className="mt-16 border-t border-line bg-white">
      <div className="container-x grid gap-6 py-8 text-sm text-muted md:grid-cols-[1fr_auto]">
        <div className="space-y-2">
          <p className="font-medium text-ink">{ATTRIBUTION}</p>
          <p>
            AtlasBridge is an independent developer tool built on N-ATLaS for the National AI Innovation Challenge 2026.
            Model output can be wrong, so check anything important.
          </p>
        </div>
        <nav className="flex flex-wrap gap-x-5 gap-y-2 md:flex-col" aria-label="Footer">
          <Link to="/guide">Docs</Link>
          <a href="/docs">API reference</a>
          <Link to="/playground">Playground</Link>
          <a href={GITHUB} target="_blank" rel="noopener">GitHub</a>
          <a href="https://huggingface.co/NCAIR1/N-ATLaS" target="_blank" rel="noopener">N-ATLaS terms</a>
        </nav>
      </div>
    </footer>
  );
}

export function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 btn btn-primary">Skip to content</a>
      <Header />
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
