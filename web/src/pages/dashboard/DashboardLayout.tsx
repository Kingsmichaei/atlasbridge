import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { api, type Usage } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const TABS = [
  { to: "/dashboard", label: "Overview", end: true },
  { to: "/dashboard/keys", label: "API keys" },
  { to: "/dashboard/usage", label: "Usage" },
  { to: "/dashboard/settings", label: "Settings" },
];

export default function DashboardLayout() {
  const { user } = useAuth();
  return (
    <div className="container-x py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted">Signed in as {user?.email}</p>
      </div>
      <nav className="-mx-4 mb-6 flex gap-1 overflow-x-auto border-b border-line px-4 sm:mx-0 sm:px-0" aria-label="Dashboard">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium no-underline ${isActive ? "border-brand text-ink" : "border-transparent text-muted hover:text-ink"}`
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}

/** Last-30-days usage for the logged-in user. */
export function useUsage(days = 30) {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const ctl = new AbortController();
    api<Usage>(`/account/usage?days=${days}`, { signal: ctl.signal })
      .then(setUsage)
      .catch((e) => { if (e.name !== "AbortError") setError(e.message); });
    return () => ctl.abort();
  }, [days]);
  return { usage, error };
}
