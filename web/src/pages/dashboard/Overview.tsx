import { Link } from "react-router";
import { ErrorNote, Stat } from "../../components/ui";
import { RequestsPerDay } from "../../components/charts";
import { ms, pct } from "../../lib/format";
import { useUsage } from "./DashboardLayout";

export default function Overview() {
  const { usage, error } = useUsage(30);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  const t = usage?.totals;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Requests" value={t ? t.requests.toLocaleString() : "…"} hint="Last 30 days" />
        <Stat label="Success rate" value={t ? pct(t.success_rate) : "…"} hint={t ? `${t.successful.toLocaleString()} succeeded` : undefined} />
        <Stat label="Median latency" value={t ? ms(t.median_latency_ms) : "…"} hint="Time to full reply" />
      </div>
      <section className="card">
        <h2 className="font-semibold">Requests per day</h2>
        <p className="mb-4 text-xs text-muted">Last 30 days, all your keys (UTC)</p>
        {usage ? <RequestsPerDay data={usage.per_day} /> : <div className="h-56 animate-pulse rounded-lg bg-paper" />}
      </section>
      {t && t.requests === 0 && (
        <section className="card bg-brand-soft">
          <h2 className="font-semibold">Make your first request</h2>
          <p className="mt-1 text-sm text-muted">
            <Link to="/dashboard/keys">Create an API key</Link>, then try it in the <Link to="/playground">playground</Link> or
            follow the <Link to="/guide">quick start</Link>.
          </p>
        </section>
      )}
    </div>
  );
}
