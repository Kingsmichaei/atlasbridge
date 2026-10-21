import { ErrorNote, Stat } from "../../components/ui";
import Breakdown from "../../components/Breakdown";
import { ENDPOINT_NAMES, LANG_NAMES, ms, pct } from "../../lib/format";
import { useUsage } from "./DashboardLayout";

export default function UsagePage() {
  const { usage, error } = useUsage(30);
  if (error) return <ErrorNote>{error}</ErrorNote>;
  if (!usage) return <div className="h-64 animate-pulse rounded-xl bg-white" />;
  const t = usage.totals;
  const entries = (o: Record<string, number>, names: Record<string, string>) =>
    Object.entries(o).map(([k, v]) => ({ name: names[k] ?? k, value: v }));
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Last 30 days, across all your keys, including revoked and deleted ones.</p>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Requests" value={t.requests.toLocaleString()} />
        <Stat label="Success rate" value={pct(t.success_rate)} />
        <Stat label="Median latency" value={ms(t.median_latency_ms)} />
        <Stat label="Tokens" value={(t.prompt_tokens + t.completion_tokens).toLocaleString()} hint={`${t.prompt_tokens.toLocaleString()} in · ${t.completion_tokens.toLocaleString()} out`} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card">
          <h2 className="mb-4 font-semibold">By endpoint</h2>
          <Breakdown items={entries(usage.by_endpoint, ENDPOINT_NAMES)} />
        </section>
        <section className="card">
          <h2 className="mb-1 font-semibold">By language</h2>
          <p className="mb-4 text-xs text-muted">Detected language of the request (target language for translations)</p>
          <Breakdown items={entries(usage.by_language, LANG_NAMES)} />
        </section>
      </div>
      <section className="card">
        <h2 className="mb-4 font-semibold">By key</h2>
        <Breakdown items={usage.by_key.map((k) => ({ name: `${k.label} (${k.prefix}…)`, value: k.requests }))} />
      </section>
    </div>
  );
}
