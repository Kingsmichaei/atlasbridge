import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, errorMessage } from "../lib/api";
import { getPlaygroundKey, setPlaygroundKey } from "../lib/keyStore";
import { ErrorNote } from "../components/ui";
import { LANG_NAMES } from "../lib/format";

const LANG_OPTIONS = [["en", "English"], ["ha", "Hausa"], ["ig", "Igbo"], ["yo", "Yoruba"]] as const;

const EXAMPLES: [string, string][] = [
  ["Hausa", "Menene amfanin ruwa ga jikin dan Adam?"],
  ["Igbo", "Kedu ihe bụ uru mmiri na-arụ n'ahụ mmadụ?"],
  ["Yoruba", "Kini anfaani omi fun ara eniyan?"],
  ["English", "Explain mobile money to a market trader in two sentences."],
];

type Msg = { role: "user" | "assistant"; content: string; error?: boolean };

function Chat({ apiKey, needKey }: { apiKey: string; needKey: () => boolean }) {
  const [history, setHistory] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [replyLang, setReplyLang] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState("");
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => { log.current?.scrollTo({ top: 1e9 }); }, [history]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy || needKey()) return;
    const sent: Msg[] = [...history.filter((m) => !m.error), { role: "user", content: text }];
    setInput("");
    setHistory([...sent, { role: "assistant", content: "" }]);
    setBusy(true);
    setMeta("");
    const t0 = performance.now();
    let reply = "";
    try {
      const r = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
        body: JSON.stringify({ model: "n-atlas", stream: true, language: replyLang, messages: sent.map(({ role, content }) => ({ role, content })) }),
      });
      if (!r.ok || !r.body) throw new Error(errorMessage(await r.json().catch(() => ({})), r.status));
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") continue;
          const chunk = JSON.parse(data);
          if (chunk.error) throw new Error(chunk.error.message);
          reply += chunk.choices?.[0]?.delta?.content ?? "";
          setHistory([...sent, { role: "assistant", content: reply }]);
        }
      }
      setMeta(`Replied in ${((performance.now() - t0) / 1000).toFixed(1)} s`);
    } catch (err) {
      // Keep the failed turn on screen, but leave it out of the history sent next time (as the classic page did).
      setHistory([...sent.slice(0, -1), { role: "user", content: text, error: true }, { role: "assistant", content: (err as Error).message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
        {EXAMPLES.map(([lang, q]) => (
          <button key={lang} type="button" className="btn btn-ghost shrink-0 px-3 py-1.5 text-xs font-medium" onClick={() => setInput(q)}>
            {lang}: {q.slice(0, 24)}…
          </button>
        ))}
      </div>
      <div ref={log} className="flex h-[22rem] flex-col gap-3 overflow-y-auto rounded-xl border border-line bg-paper p-3 sm:h-[26rem]" aria-live="polite">
        {history.length === 0 && (
          <p className="m-auto max-w-xs text-center text-sm text-muted">Ask anything in English, Hausa, Igbo or Yoruba. N-ATLaS replies in the same language unless you pick one below.</p>
        )}
        {history.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2.5 text-[15px] ${
              m.role === "user" ? `self-end rounded-br-md bg-brand text-white ${m.error ? "opacity-60" : ""}`
              : m.error ? "self-start border border-danger text-danger"
              : "self-start rounded-bl-md border border-line bg-white"
            }`}
          >
            {m.content || "…"}
          </div>
        ))}
      </div>
      <form onSubmit={send} className="mt-3 flex gap-2">
        <label htmlFor="chat-input" className="sr-only">Message</label>
        <input id="chat-input" className="field" autoComplete="off" placeholder="Type a message…" value={input} onChange={(e) => setInput(e.target.value)} />
        <button className="btn btn-primary" disabled={busy}>{busy ? "…" : "Send"}</button>
      </form>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        <button type="button" className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => { setHistory([]); setMeta(""); }}>New chat</button>
        <label htmlFor="reply-lang" className="text-muted">Reply in</label>
        <select id="reply-lang" className="field w-auto py-1.5" value={replyLang} onChange={(e) => setReplyLang(e.target.value)}>
          <option value="auto">Same as my message</option>
          {LANG_OPTIONS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
        <span className="text-xs text-muted">{meta}</span>
      </div>
    </div>
  );
}

function Translate({ apiKey, needKey }: { apiKey: string; needKey: () => boolean }) {
  const [source, setSource] = useState("auto");
  const [target, setTarget] = useState("ha");
  const [text, setText] = useState("Wash your hands with soap and clean water before eating.");
  const [out, setOut] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run() {
    if (needKey()) return;
    setBusy(true); setError(""); setOut("");
    try {
      const d = await api<{ translation: string; source: string }>("/v1/translate", { apiKey, body: { text, source, target } });
      setOut(d.translation + (source === "auto" ? `\n\n(detected ${LANG_NAMES[d.source] ?? d.source})` : ""));
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="t-from">From</label>
          <select id="t-from" className="field" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="auto">Detect automatically</option>
            {LANG_OPTIONS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="t-to">To</label>
          <select id="t-to" className="field" value={target} onChange={(e) => setTarget(e.target.value)}>
            {LANG_OPTIONS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="label" htmlFor="t-text">Text</label>
        <textarea id="t-text" className="field min-h-28" maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <button className="btn btn-primary" onClick={run} disabled={busy || !text.trim()}>{busy ? "Translating…" : "Translate"}</button>
      <ErrorNote>{error}</ErrorNote>
      {out && <div className="whitespace-pre-wrap rounded-xl border border-line bg-paper p-4">{out}</div>}
    </div>
  );
}

function Detect({ apiKey, needKey }: { apiKey: string; needKey: () => boolean }) {
  const [text, setText] = useState("Kedu ihe bụ uru mmiri na-arụ n'ahụ mmadụ?");
  const [method, setMethod] = useState("heuristic");
  const [out, setOut] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run() {
    if (needKey()) return;
    setBusy(true); setError(""); setOut("");
    try {
      const d = await api<{ name: string; language: string; confidence?: number; method: string }>("/v1/detect-language", { apiKey, body: { text, method } });
      setOut(`${d.name} (${d.language})` + (d.confidence != null ? ` · confidence ${Math.round(d.confidence * 100)}%` : "") + ` · ${d.method}`);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <div className="space-y-3">
      <div>
        <label className="label" htmlFor="d-text">Text</label>
        <textarea id="d-text" className="field min-h-28" maxLength={4000} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="d-method" className="sr-only">Method</label>
        <select id="d-method" className="field sm:w-auto" value={method} onChange={(e) => setMethod(e.target.value)}>
          <option value="heuristic">Fast (offline rules)</option>
          <option value="model">Ask N-ATLaS</option>
        </select>
        <button className="btn btn-primary" onClick={run} disabled={busy || !text.trim()}>{busy ? "Detecting…" : "Detect"}</button>
      </div>
      <ErrorNote>{error}</ErrorNote>
      {out && <div className="rounded-xl border border-line bg-paper p-4 font-medium">{out}</div>}
    </div>
  );
}

const TABS = [["chat", "Chat"], ["translate", "Translate"], ["detect", "Detect language"]] as const;

export default function Playground() {
  const [apiKey, setKey] = useState(getPlaygroundKey);
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("chat");
  const keyInput = useRef<HTMLInputElement>(null);
  const update = (v: string) => { setKey(v.trim()); setPlaygroundKey(v.trim()); };
  const needKey = () => {
    if (apiKey) return false;
    keyInput.current?.focus();
    return true;
  };

  return (
    <div className="container-x py-8">
      <h1 className="text-2xl font-bold tracking-tight">Playground</h1>
      <p className="mt-1 text-sm text-muted">Try N-ATLaS with your own key. Requests count towards your usage like any other.</p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside className="card h-fit space-y-3">
          <h2 className="font-semibold">API key</h2>
          <div>
            <label className="label" htmlFor="pg-key">Paste an AtlasBridge key</label>
            <input id="pg-key" ref={keyInput} className="field font-mono" placeholder="ab_…" autoComplete="off" spellCheck={false} value={apiKey} onChange={(e) => update(e.target.value)} />
          </div>
          <p className="text-xs text-muted">
            Keys are stored hashed, so the dashboard can't show an existing key again. Kept only for this browser tab and forgotten when you close it.
          </p>
          <Link to="/dashboard/keys" className="btn btn-ghost w-full">Create a key</Link>
          <p className="text-xs text-muted">Don't send personal or sensitive information: beta logs keep short previews of prompts and replies.</p>
        </aside>
        <section className="card min-w-0">
          <div className="-mx-5 -mt-1 mb-4 flex gap-1 overflow-x-auto border-b border-line px-5" role="tablist">
            {TABS.map(([id, name]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium ${tab === id ? "border-brand text-ink" : "border-transparent text-muted hover:text-ink"}`}
              >
                {name}
              </button>
            ))}
          </div>
          {tab === "chat" && <Chat apiKey={apiKey} needKey={needKey} />}
          {tab === "translate" && <Translate apiKey={apiKey} needKey={needKey} />}
          {tab === "detect" && <Detect apiKey={apiKey} needKey={needKey} />}
        </section>
      </div>
    </div>
  );
}
