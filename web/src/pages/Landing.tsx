import { Link } from "react-router";
import { useAuth } from "../lib/auth";
import { quickSamples } from "../lib/snippets";
import { CodeTabs } from "../components/ui";
import { ATTRIBUTION } from "../components/Brand";

const FEATURES = [
  { title: "OpenAI-compatible", body: "Keep the OpenAI SDK, LangChain or plain fetch. Change the base_url and model, and your app talks to N-ATLaS." },
  { title: "Replies in the right language", body: "The gateway detects the language of each message and tells N-ATLaS to answer in it, even when a chat switches languages. Or set language yourself." },
  { title: "Translate", body: "POST /v1/translate between English, Hausa, Igbo and Yoruba, with the source detected for you." },
  { title: "Detect language", body: "Fast offline language ID that handles text typed with or without diacritics, or ask N-ATLaS itself." },
  { title: "Streaming", body: "stream: true returns server-sent events in the OpenAI format, so tokens appear as they are generated." },
  { title: "Python SDK", body: "A small client with chat, stream, translate, detect and conversation history, plus a command-line tool." },
];

const LANGS = [
  { name: "Hausa", hello: "Sannu" },
  { name: "Igbo", hello: "Ndewo" },
  { name: "Yoruba", hello: "Ẹ n lẹ" },
  { name: "English", hello: "Hello" },
];

export default function Landing() {
  const { user } = useAuth();
  const primary = user ? { to: "/dashboard/keys", text: "Get an API key" } : { to: "/signup", text: "Get an API key" };
  return (
    <>
      <section className="relative overflow-hidden bg-brand-dark text-white">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "40px 40px" }}
          aria-hidden="true"
        />
        <div className="container-x relative grid gap-10 py-14 sm:py-20 lg:grid-cols-[1.05fr_1fr] lg:items-center">
          <div>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs font-medium text-[#cfe9db]">
              OpenAI-compatible API for N-ATLaS
            </p>
            <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl">
              N-ATLaS for every developer,{" "}
              <span className="text-gold">in Hausa, Igbo, Yoruba and English</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg text-[#cfe9db]">
              Nigeria's own multilingual language model, behind the API your code already speaks. Change one{" "}
              <code className="rounded bg-white/10 px-1.5 py-0.5 text-white">base_url</code> and ship.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to={primary.to} className="btn btn-gold px-5 py-3 text-base">{primary.text}</Link>
              <Link to="/guide" className="btn border border-white/25 px-5 py-3 text-base text-white hover:bg-white/10">Read the docs</Link>
            </div>
            <ul className="mt-8 flex flex-wrap gap-2" aria-label="Supported languages">
              {LANGS.map((l) => (
                <li key={l.name} className="rounded-full bg-white/10 px-3 py-1 text-sm">
                  <span className="font-semibold">{l.name}</span> <span className="text-[#a9d3bc]">· {l.hello}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="min-w-0 [&_[role=tab]]:text-[#cfe9db] [&_[role=tab][aria-selected=true]]:bg-white/15 [&_[role=tab][aria-selected=true]]:text-white">
            <CodeTabs samples={quickSamples()} />
          </div>
        </div>
      </section>

      <section className="container-x py-16">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Everything you need to build in Nigerian languages</h2>
        <p className="mt-2 max-w-2xl text-muted">No GPU, no model download, no chat templates. Get a key and call the API.</p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card">
              <div className="mb-3 h-1 w-8 rounded-full bg-brand-bright" aria-hidden="true" />
              <h3 className="font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm text-muted">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-white">
        <div className="container-x py-16">
          <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">How it works</h2>
          <ol className="mt-6 grid gap-4 text-sm sm:grid-cols-3">
            <li className="rounded-xl bg-paper p-4"><span className="font-semibold text-brand">1. Your app</span> sends an OpenAI-style request with your AtlasBridge key.</li>
            <li className="rounded-xl bg-paper p-4"><span className="font-semibold text-brand">2. The gateway</span> checks the key, detects the language, adds the reply-language instruction and logs usage.</li>
            <li className="rounded-xl bg-paper p-4"><span className="font-semibold text-brand">3. N-ATLaS</span> answers from the GPU server, or the CPU backup when the GPU is off.</li>
          </ol>
          <div className="mt-8 grid gap-6">
            <figure className="card overflow-hidden p-3">
              <img src="/images/architecture.svg" alt="Architecture: apps call the AtlasBridge gateway, which forwards to the N-ATLaS GPU server or the CPU backup" className="w-full" loading="lazy" />
              <figcaption className="px-2 pt-2 text-xs text-muted">Architecture</figcaption>
            </figure>
            <figure className="card overflow-hidden p-3">
              <img src="/images/language-flow.svg" alt="Language flow: detect the language of the latest message and tell N-ATLaS to reply in it" className="w-full" loading="lazy" />
              <figcaption className="px-2 pt-2 text-xs text-muted">Choosing the reply language</figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section className="container-x py-16">
        <div className="card flex flex-col items-start gap-5 bg-brand-soft sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-bold">Start building today</h2>
            <p className="mt-1 text-sm text-muted">Free during the beta, 20 requests per minute per key. {ATTRIBUTION}</p>
          </div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <Link to={primary.to} className="btn btn-primary">{primary.text}</Link>
            <a href="https://github.com/Kingsmichaei/atlasbridge" className="btn btn-ghost" target="_blank" rel="noopener">View on GitHub</a>
          </div>
        </div>
      </section>
    </>
  );
}
