export const LANG_NAMES: Record<string, string> = { en: "English", ha: "Hausa", ig: "Igbo", yo: "Yoruba", und: "Unknown" };
export const ENDPOINT_NAMES: Record<string, string> = { chat: "Chat completions", translate: "Translate", detect: "Detect language" };

export function when(iso: string | null): string {
  if (!iso) return "Never";
  const d = new Date(iso);
  const secs = (Date.now() - d.getTime()) / 1000;
  if (secs < 60) return "Just now";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function ms(v: number | null): string {
  if (v == null) return "–";
  return v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`;
}

export function pct(v: number | null): string {
  return v == null ? "–" : `${(v * 100).toFixed(v === 1 ? 0 : 1)}%`;
}
