import { useEffect, useState } from "react";
import type { Health } from "./api";

export type Status = { tone: "ok" | "warn" | "bad" | "unknown"; text: string; detail: string };

export function describe(h: Health | null, failed: boolean): Status {
  if (failed) return { tone: "bad", text: "Gateway unreachable", detail: "The AtlasBridge gateway didn't answer." };
  if (!h) return { tone: "unknown", text: "Checking model…", detail: "Is the N-ATLaS model online right now?" };
  const up = h.upstream ?? {};
  if (up.status !== "ok") return { tone: "bad", text: "Model offline", detail: "No N-ATLaS server is reachable right now." };
  if (up.mode === "mock") return { tone: "ok", text: "Mock mode", detail: "Canned replies for development (MOCK_UPSTREAM=1)." };
  if (up.backend === "cpu-backup")
    return {
      tone: "warn", text: "Online (CPU backup)",
      detail: "The fast GPU server is off, so replies come from the always-on CPU backup and can take up to a minute.",
    };
  return { tone: "ok", text: "N-ATLaS online", detail: "Served by the GPU server." };
}

/** Polls /health once a minute, like the classic playground. */
export function useHealth(): Status {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    const check = () =>
      fetch("/health")
        .then((r) => r.json())
        .then((h: Health) => { if (alive) { setHealth(h); setFailed(false); } })
        .catch(() => { if (alive) setFailed(true); });
    check();
    const t = setInterval(check, 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  return describe(health, failed);
}
