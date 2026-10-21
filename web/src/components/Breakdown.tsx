/** A ranked breakdown as labelled horizontal bars: name, bar, count and share, all as text. */
export default function Breakdown({ items, empty = "No requests yet." }: { items: { name: string; value: number }[]; empty?: string }) {
  const total = items.reduce((n, i) => n + i.value, 0);
  const max = Math.max(1, ...items.map((i) => i.value));
  if (!total) return <p className="py-6 text-center text-sm text-muted">{empty}</p>;
  return (
    <ul className="space-y-3">
      {[...items].sort((a, b) => b.value - a.value).map((i) => (
        <li key={i.name} title={`${i.name}: ${i.value} (${Math.round((i.value / total) * 100)}%)`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate font-medium">{i.name}</span>
            <span className="shrink-0 tabular-nums text-muted">{i.value.toLocaleString()} · {Math.round((i.value / total) * 100)}%</span>
          </div>
          <div className="h-2 rounded-full bg-paper">
            <div className="h-2 rounded-full bg-brand" style={{ width: `${Math.max(2, (i.value / max) * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
