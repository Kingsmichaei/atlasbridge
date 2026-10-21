import { useEffect, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { CodeBlock, CodeTabs } from "../components/ui";
import { ATTRIBUTION } from "../components/Brand";
import { baseUrl, origin, quickSamples, SDK_INSTALL } from "../lib/snippets";

// Everything on this page is taken from the gateway code (gateway/app/main.py, upstream.py,
// language.py). Keep it in sync when the API changes.

const SECTIONS = [
  ["quick-start", "Quick start"],
  ["authentication", "Authentication"],
  ["chat", "Chat completions"],
  ["streaming", "Streaming"],
  ["language", "Controlling the reply language"],
  ["translate", "Translate"],
  ["detect", "Detect language"],
  ["other", "Models and usage"],
  ["errors", "Errors and rate limits"],
  ["limits", "Limits and model notes"],
] as const;

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 border-b border-line pb-10 pt-2 last:border-0">
      <h2 className="mb-3 text-xl font-bold tracking-tight">
        <a href={`#${id}`} className="text-ink no-underline hover:underline">{title}</a>
      </h2>
      <div className="space-y-4 text-[15px] leading-relaxed [&_li]:ml-5 [&_li]:list-disc [&_p_code]:rounded [&_p_code]:bg-brand-soft [&_p_code]:px-1 [&_li_code]:rounded [&_li_code]:bg-brand-soft [&_li_code]:px-1 [&_td_code]:rounded [&_td_code]:bg-brand-soft [&_td_code]:px-1">
        {children}
      </div>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <thead className="bg-paper text-xs text-muted">
          <tr>{head.map((h) => <th key={h} className="px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line align-top">
          {rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="px-3 py-2">{c}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

const CHAT_RESPONSE = `{
  "id": "chatcmpl-…",
  "object": "chat.completion",
  "model": "n-atlas",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Ruwa yana taimaka wa jiki…"},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 61, "completion_tokens": 48, "total_tokens": 109},
  "x_atlasbridge": {
    "detected_language": "ha",
    "reply_language": "ha",
    "backend": "gpu"
  }
}`;

const STREAM_PY = `from openai import OpenAI

client = OpenAI(api_key="ab_YOUR_KEY", base_url="${"{BASE}"}")
stream = client.chat.completions.create(
    model="n-atlas",
    stream=True,
    messages=[{"role": "user", "content": "Bawo ni? Sọ fún mi nípa Ìbàdàn."}],
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`;

const STREAM_WIRE = `data: {"id":"chatcmpl-…","object":"chat.completion.chunk","model":"n-atlas","choices":[{"index":0,"delta":{"content":"Ẹ "},"finish_reason":null}]}

data: {"id":"chatcmpl-…","object":"chat.completion.chunk","model":"n-atlas","choices":[{"index":0,"delta":{"content":"kú "},"finish_reason":null}]}

data: [DONE]`;

const ERROR_SHAPE = `{
  "error": {
    "message": "Rate limit: 20 requests per minute.",
    "type": "invalid_request_error",
    "code": 429
  }
}`;

export default function Guide() {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);
  const base = baseUrl();

  return (
    <div className="container-x py-8">
      <div className="grid gap-8 lg:grid-cols-[14rem_1fr]">
        <aside className="lg:sticky lg:top-24 lg:h-fit">
          <details className="card p-4 lg:hidden">
            <summary className="cursor-pointer text-sm font-semibold">On this page</summary>
            <nav className="mt-3 flex flex-col gap-2 text-sm" aria-label="Docs sections">
              {SECTIONS.map(([id, t]) => <a key={id} href={`#${id}`}>{t}</a>)}
            </nav>
          </details>
          <nav className="hidden flex-col gap-1 text-sm lg:flex" aria-label="Docs sections">
            <span className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Docs</span>
            {SECTIONS.map(([id, t]) => (
              <a key={id} href={`#${id}`} className="rounded-md px-2 py-1.5 text-ink no-underline hover:bg-white hover:text-brand">{t}</a>
            ))}
            <a href="/docs" className="mt-3 rounded-md px-2 py-1.5 no-underline hover:bg-white">Interactive API reference →</a>
          </nav>
        </aside>

        <article className="min-w-0 max-w-3xl">
          <header className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight">AtlasBridge docs</h1>
            <p className="mt-2 text-muted">
              AtlasBridge serves N-ATLaS, Nigeria's multilingual LLM, through an OpenAI-compatible API.
              The base URL is <code className="rounded bg-brand-soft px-1">{base}</code>.
            </p>
            <p className="mt-3 rounded-lg border border-line bg-white px-3 py-2 text-sm text-muted">{ATTRIBUTION}</p>
          </header>

          <Section id="quick-start" title="Quick start">
            <ol className="space-y-1 [&>li]:list-decimal">
              <li><Link to="/signup">Create an account</Link> and open <Link to="/dashboard/keys">API keys</Link> to create a key. Copy it: it is shown once.</li>
              <li>Point any OpenAI client at <code>{base}</code> with model <code>n-atlas</code>.</li>
              <li>Send messages in English, Hausa, Igbo or Yoruba. Replies come back in the same language.</li>
            </ol>
            <CodeTabs samples={quickSamples()} />
            <p>
              The AtlasBridge SDK is optional: <code>{SDK_INSTALL}</code>. It takes the site URL (<code>{origin()}</code>) and adds{" "}
              <code>/v1</code> itself. It also installs an <code>atlasbridge</code> command: set <code>ATLASBRIDGE_API_KEY</code> and{" "}
              <code>ATLASBRIDGE_BASE_URL</code>, then run <code>atlasbridge chat "Sannu"</code>.
            </p>
          </Section>

          <Section id="authentication" title="Authentication">
            <p>Every <code>/v1</code> request needs your key as a Bearer token:</p>
            <CodeBlock code={"Authorization: Bearer ab_YOUR_KEY"} title="header" />
            <ul>
              <li>Keys start with <code>ab_</code>. AtlasBridge stores only a hash, so a lost key can't be shown again: rotate it or create a new one in the dashboard.</li>
              <li>You can have up to 5 active keys, for example one per app or environment. Rotating a key revokes the old one immediately.</li>
              <li>A missing key returns <code>401</code> "Missing API key"; a wrong or revoked key returns <code>401</code> "Invalid or revoked API key."</li>
              <li>Keep keys on your server. Don't put them in a mobile app or web page that users can download.</li>
            </ul>
          </Section>

          <Section id="chat" title="Chat completions">
            <p><code>POST /v1/chat/completions</code> takes the OpenAI chat format.</p>
            <Table
              head={["Field", "Type", "Default", "Notes"]}
              rows={[
                [<code>model</code>, "string", <code>n-atlas</code>, "Any value is accepted; responses always say n-atlas."],
                [<code>messages</code>, "array", "required", <>At least one <code>{"{role, content}"}</code>. Roles: system, user, assistant. Content is a string.</>],
                [<code>stream</code>, "boolean", "false", "Server-sent events, see Streaming."],
                [<code>language</code>, "string", <code>auto</code>, <><code>auto</code>, <code>en</code>, <code>ha</code>, <code>ig</code> or <code>yo</code>. AtlasBridge extension, see below.</>],
                [<code>temperature</code>, "number 0–2", "0.1", "Low by default: N-ATLaS is most reliable near 0."],
                [<code>top_p</code>, "number (0, 1]", "model default", ""],
                [<code>max_tokens</code>, "integer 1–2048", "512", "The CPU backup caps replies at 256 tokens."],
                [<code>repetition_penalty</code>, "number 1–2", "1.12", "The N-ATLaS model card value."],
              ]}
            />
            <p>
              If you don't send a system message, AtlasBridge adds one that tells N-ATLaS who it is (made by Awarri Technologies, not by OpenAI or anyone else).
              Your own system message is used as it is.
            </p>
            <p>The response is a normal <code>chat.completion</code>, plus an <code>x_atlasbridge</code> object:</p>
            <CodeBlock code={CHAT_RESPONSE} title="example response" />
            <ul>
              <li><code>detected_language</code>: the language of the latest user message (<code>und</code> if unclear).</li>
              <li><code>reply_language</code>: the language N-ATLaS was told to use, or <code>unspecified</code>.</li>
              <li><code>backend</code>: <code>gpu</code> (fast, fp16) or <code>cpu-backup</code> (slower, 4-bit), which takes over automatically when the GPU server is off.</li>
            </ul>
          </Section>

          <Section id="streaming" title="Streaming">
            <p>
              With <code>"stream": true</code> the reply arrives as server-sent events in the OpenAI chunk format, ending with{" "}
              <code>data: [DONE]</code>. The OpenAI SDKs handle this for you.
            </p>
            <CodeBlock code={STREAM_PY.replace("{BASE}", base)} title="stream.py" />
            <CodeBlock code={STREAM_WIRE} title="what's on the wire" />
            <ul>
              <li>Streamed chunks don't include <code>x_atlasbridge</code>; make a non-streaming call if you need it.</li>
              <li>If N-ATLaS fails part-way, you get one <code>{'data: {"error": {…}}'}</code> event (type <code>upstream_error</code>) and then <code>[DONE]</code>.</li>
            </ul>
          </Section>

          <Section id="language" title="Controlling the reply language">
            <p>
              An 8B model often answers in the wrong Nigerian language when left to guess, especially after a conversation switches language. AtlasBridge fixes
              this by naming the language in the system prompt.
            </p>
            <Table
              head={["language", "What happens"]}
              rows={[
                [<code>auto</code>, <>With no system message of yours: AtlasBridge detects the latest user message and tells N-ATLaS to reply only in that language. With your own system message: nothing is added, and your prompt decides.</>],
                [<><code>en</code> <code>ha</code> <code>ig</code> <code>yo</code></>, <>"Always reply in &lt;language&gt;." is added to the system prompt (yours or the default), whatever language the user writes in.</>],
              ]}
            />
            <CodeBlock
              title="force Yoruba"
              code={`curl ${base}/chat/completions \\
  -H "Authorization: Bearer ab_YOUR_KEY" -H "Content-Type: application/json" \\
  -d '{"model": "n-atlas", "language": "yo",
       "messages": [{"role": "user", "content": "Tell me about Ibadan"}]}'`}
            />
            <p>
              With the OpenAI Python SDK, pass it as <code>extra_body={'{"language": "yo"}'}</code>. With the AtlasBridge SDK, <code>language="yoruba"</code>{" "}
              (codes or names both work).
            </p>
          </Section>

          <Section id="translate" title="Translate">
            <p><code>POST /v1/translate</code> translates between English, Hausa, Igbo and Yoruba.</p>
            <Table
              head={["Field", "Notes"]}
              rows={[
                [<code>text</code>, "Required, 1–4,000 characters."],
                [<code>target</code>, <><code>en</code>, <code>ha</code>, <code>ig</code> or <code>yo</code>.</>],
                [<code>source</code>, <>Default <code>auto</code>: detected for you (English if unclear).</>],
              ]}
            />
            <CodeBlock
              title="request and example response"
              code={`curl ${base}/translate \\
  -H "Authorization: Bearer ab_YOUR_KEY" -H "Content-Type: application/json" \\
  -d '{"text": "Wash your hands before eating.", "target": "ha"}'

{"translation": "Ku wanke hannuwanku kafin cin abinci.", "source": "en", "target": "ha",
 "model": "n-atlas", "backend": "gpu"}`}
            />
            <p>
              The text is always translated, never answered: a question comes back as the same question in the target language. If source and target are
              the same, the text is returned unchanged without calling the model.
            </p>
          </Section>

          <Section id="detect" title="Detect language">
            <p>
              <code>POST /v1/detect-language</code> with <code>{'{"text": "…", "method": "heuristic"}'}</code>. The default <code>heuristic</code> method is
              fast offline rules (special letters, common words and spelling patterns) that handle text typed with or without diacritics.{" "}
              <code>"method": "model"</code> asks N-ATLaS instead.
            </p>
            <CodeBlock
              title="example response (heuristic)"
              code={`{"language": "ig", "name": "Igbo", "confidence": 0.91,
 "scores": {"en": 0.0, "ha": 0.4, "ig": 4.6, "yo": 0.0}, "method": "heuristic"}`}
            />
            <p>
              <code>language</code> is <code>en</code>, <code>ha</code>, <code>ig</code>, <code>yo</code> or <code>und</code> (unknown). Model responses have{" "}
              <code>language</code>, <code>name</code>, <code>method: "model"</code> and the heuristic result under <code>heuristic</code>.
            </p>
          </Section>

          <Section id="other" title="Models and usage">
            <ul>
              <li><code>GET /v1/models</code> lists <code>n-atlas</code> (languages en, ha, ig, yo; context length 8,192 tokens).</li>
              <li><code>GET /v1/usage</code> returns request counts and average latency per endpoint for the key you call it with.</li>
              <li>The <Link to="/dashboard/usage">dashboard</Link> shows the last 30 days across all your keys, by day, endpoint and language.</li>
              <li><code>GET /health</code> (no key) reports whether N-ATLaS is online and which backend is active.</li>
            </ul>
          </Section>

          <Section id="errors" title="Errors and rate limits">
            <p>Errors use the OpenAI shape, so OpenAI SDKs raise them with the message intact:</p>
            <CodeBlock code={ERROR_SHAPE} title="error" />
            <Table
              head={["Status", "Meaning"]}
              rows={[
                ["401", "Missing, invalid or revoked API key."],
                ["422", <>The request body is invalid (for example an unknown <code>language</code>). On <code>/v1</code> routes this uses FastAPI's <code>{'{"detail": […]}'}</code> shape.</>],
                ["429", "Rate limit: 20 requests per minute per key, over a rolling 60 seconds. Wait and retry."],
                ["502", <>N-ATLaS couldn't be reached or failed (type <code>upstream_error</code>). Retry; the gateway already tried the backup.</>],
                ["503", "No N-ATLaS backend is available right now."],
              ]}
            />
          </Section>

          <Section id="limits" title="Limits and model notes">
            <ul>
              <li>
                <strong>Quality varies by language.</strong> N-ATLaS v1's own human evaluation scores Yoruba lowest (2.69/5), against Hausa 3.98, Igbo 3.87
                and English 4.21. Translation and language detection inherit this. Check important output with a native speaker.
              </li>
              <li><strong>No live facts.</strong> N-ATLaS has no internet access and only knows its training data. Don't rely on it for news, prices or other current information.</li>
              <li>Nigerian Pidgin isn't an officially supported N-ATLaS language.</li>
              <li>The GPU server isn't always on. When it's off, the CPU backup answers more slowly (2–5 tokens per second, replies capped at 256 tokens), and its 4-bit model can word things slightly differently.</li>
              <li>
                <strong>Licence cap.</strong> The N-ATLaS licence limits deployments to 1,000 monthly active end users without a commercial licence from Awarri.
                AtlasBridge is a beta under that cap. See the <a href="https://huggingface.co/NCAIR1/N-ATLaS" target="_blank" rel="noopener">N-ATLaS terms</a>, including the prohibited uses.
              </li>
              <li>Beta logs keep each request's language, latency and a short preview of prompts and replies to measure quality. Don't send personal or sensitive information.</li>
            </ul>
            <p>
              Every endpoint and field is in the <a href="/docs">interactive API reference</a>.
            </p>
            <p className="text-sm text-muted">{ATTRIBUTION}</p>
          </Section>
        </article>
      </div>
    </div>
  );
}
