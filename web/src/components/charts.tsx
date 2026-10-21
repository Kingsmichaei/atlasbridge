import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Usage } from "../lib/api";

const shortDate = (iso: string) => new Date(iso + "T00:00:00Z").toLocaleDateString(undefined, { day: "numeric", month: "short", timeZone: "UTC" });

type TipProps = { active?: boolean; payload?: { payload: Usage["per_day"][number] }[] };

function DayTip({ active, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-line bg-white px-3 py-2 text-xs shadow-md">
      <div className="font-semibold text-ink">{shortDate(d.date)}</div>
      <div className="text-muted">{d.requests} request{d.requests === 1 ? "" : "s"}{d.errors ? `, ${d.errors} failed` : ""}</div>
    </div>
  );
}

/** Requests per day (single series, so no legend; the card title names it). */
export function RequestsPerDay({ data }: { data: Usage["per_day"] }) {
  const total = data.reduce((n, d) => n + d.requests, 0);
  return (
    <div>
      <div className="h-56 w-full" role="img" aria-label={`Requests per day: ${total} in total over ${data.length} days`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -20 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke="#eef1ed" />
            <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11, fill: "#5d6b63" }} tickLine={false}
                   axisLine={{ stroke: "#dfe4de" }} minTickGap={24} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#5d6b63" }} tickLine={false} axisLine={false} width={44} />
            <Tooltip content={<DayTip />} cursor={{ fill: "#0a7a45", fillOpacity: 0.06 }} />
            <Bar dataKey="requests" fill="#0a7a45" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-muted">Show as table</summary>
        <div className="mt-2 max-h-60 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-muted"><tr><th className="py-1 font-medium">Day</th><th className="py-1 text-right font-medium">Requests</th><th className="py-1 text-right font-medium">Failed</th></tr></thead>
            <tbody>
              {[...data].reverse().filter((d) => d.requests).map((d) => (
                <tr key={d.date} className="border-t border-line"><td className="py-1">{shortDate(d.date)}</td><td className="py-1 text-right tabular-nums">{d.requests}</td><td className="py-1 text-right tabular-nums">{d.errors}</td></tr>
              ))}
            </tbody>
          </table>
          {!total && <p className="py-2 text-xs text-muted">No requests in this period.</p>}
        </div>
      </details>
    </div>
  );
}
