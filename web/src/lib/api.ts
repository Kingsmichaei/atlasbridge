// Small fetch wrapper for the gateway. Account routes use the session cookie (same origin)
// and must send X-AtlasBridge-Client, which the gateway checks to block cross-site requests.

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Options = { method?: string; body?: unknown; apiKey?: string; signal?: AbortSignal };

export async function api<T = unknown>(path: string, { method, body, apiKey, signal }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { "X-AtlasBridge-Client": "web" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  const r = await fetch(path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(errorMessage(data, r.status), r.status);
  return data as T;
}

export function errorMessage(data: unknown, status: number): string {
  const d = data as { error?: { message?: string }; detail?: unknown };
  if (d?.error?.message) return d.error.message;
  if (Array.isArray(d?.detail)) return d.detail.map((x: { msg?: string }) => x.msg).join("; ");
  if (typeof d?.detail === "string") return d.detail;
  return `Request failed (${status})`;
}

// ---- shapes returned by the gateway ----

export type User = {
  id: number; email: string; name: string; organisation: string; created_at: string; last_login_at: string | null;
};

export type ApiKey = {
  id: number; label: string; prefix: string; created_at: string;
  last_used_at: string | null; revoked_at: string | null; active: boolean;
};

export type NewKey = ApiKey & { api_key: string; note: string; replaces?: number };

export type Usage = {
  days: number;
  since: string;
  totals: {
    requests: number; successful: number; success_rate: number | null; median_latency_ms: number | null;
    prompt_tokens: number; completion_tokens: number;
  };
  per_day: { date: string; requests: number; errors: number }[];
  by_endpoint: Record<string, number>;
  by_language: Record<string, number>;
  by_key: { id: number; label: string; prefix: string; requests: number }[];
};

export type Health = {
  gateway: string;
  version: string;
  upstream: { status?: string; mode?: string; backend?: string; backends?: Record<string, string> };
};
