import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { api, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorNote } from "../components/ui";
import { Mark } from "../components/Brand";

function AuthCard({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <div className="container-x flex justify-center py-12 sm:py-16">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <span className="inline-block text-brand"><Mark className="h-10 w-auto" /></span>
          <h1 className="mt-3 text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        <div className="card p-6">{children}</div>
      </div>
    </div>
  );
}

function useAfterLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  return () => navigate(from && from !== "/login" ? from : "/dashboard", { replace: true });
}

export function Login() {
  const { user, setUser } = useAuth();
  const done = useAfterLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/dashboard" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setUser(await api<User>("/auth/login", { body: { email, password } }));
      done();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Log in" subtitle={<>New here? <Link to="/signup">Create an account</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="field" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary w-full py-3" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
    </AuthCard>
  );
}

export function Signup() {
  const { user, setUser } = useAuth();
  const done = useAfterLogin();
  const [codeRequired, setCodeRequired] = useState<boolean | null>(null);
  const [form, setForm] = useState({ name: "", email: "", organisation: "", password: "", code: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ signup_code_required: boolean }>("/auth/config")
      .then((c) => setCodeRequired(c.signup_code_required))
      .catch(() => setCodeRequired(true));
  }, []);

  if (user) return <Navigate to="/dashboard" replace />;
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (form.password.length < 8) return setError("Use at least 8 characters for your password.");
    setBusy(true);
    setError("");
    try {
      setUser(await api<User>("/auth/signup", { body: form }));
      done();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Create your developer account" subtitle={<>Already have one? <Link to="/login">Log in</Link></>}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="name">Name</label>
          <input id="name" className="field" autoComplete="name" required minLength={2} value={form.name} onChange={set("name")} />
        </div>
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" className="field" type="email" autoComplete="email" required value={form.email} onChange={set("email")} />
        </div>
        <div>
          <label className="label" htmlFor="org">Organisation or project <span className="font-normal">(optional)</span></label>
          <input id="org" className="field" autoComplete="organization" value={form.organisation} onChange={set("organisation")} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" className="field" type="password" autoComplete="new-password" required minLength={8} value={form.password} onChange={set("password")} />
          <p className="mt-1 text-xs text-muted">At least 8 characters.</p>
        </div>
        {codeRequired && (
          <div>
            <label className="label" htmlFor="code">Invite code</label>
            <input id="code" className="field" required autoComplete="off" value={form.code} onChange={set("code")} />
            <p className="mt-1 text-xs text-muted">AtlasBridge is in beta. Ask the maintainer for a code.</p>
          </div>
        )}
        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary w-full py-3" disabled={busy || codeRequired === null}>
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="text-xs text-muted">
          Beta logs record each request's language, latency and a short preview of prompts and replies, to measure quality.
          Don't send personal or sensitive information.
        </p>
      </form>
    </AuthCard>
  );
}
