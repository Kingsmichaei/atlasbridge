import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { when } from "../../lib/format";
import { ErrorNote } from "../../components/ui";

function ChangePassword() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setDone("");
    if (form.next.length < 8) return setError("Use at least 8 characters for your new password.");
    if (form.next !== form.confirm) return setError("The new passwords don't match.");
    setBusy(true);
    try {
      const r = await api<{ other_sessions_ended: number }>("/account/password", {
        body: { current_password: form.current, new_password: form.next },
      });
      setForm({ current: "", next: "", confirm: "" });
      const n = r.other_sessions_ended;
      setDone(`Password changed.${n ? ` Logged out of ${n} other ${n === 1 ? "browser" : "browsers"}.` : ""}`);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2 className="font-semibold">Change password</h2>
      <p className="mt-1 text-sm text-muted">You'll stay logged in here. Other browsers are logged out. Your API keys aren't affected.</p>
      <form onSubmit={submit} className="mt-4 grid gap-4 sm:max-w-sm">
        <div>
          <label className="label" htmlFor="pw-current">Current password</label>
          <input id="pw-current" className="field" type="password" autoComplete="current-password" required value={form.current} onChange={set("current")} />
        </div>
        <div>
          <label className="label" htmlFor="pw-new">New password</label>
          <input id="pw-new" className="field" type="password" autoComplete="new-password" required minLength={8} value={form.next} onChange={set("next")} />
          <p className="mt-1 text-xs text-muted">At least 8 characters.</p>
        </div>
        <div>
          <label className="label" htmlFor="pw-confirm">Confirm new password</label>
          <input id="pw-confirm" className="field" type="password" autoComplete="new-password" required value={form.confirm} onChange={set("confirm")} />
        </div>
        <ErrorNote>{error}</ErrorNote>
        {done && <p className="rounded-lg border border-brand/30 bg-brand-soft px-3 py-2 text-sm text-brand" role="status">{done}</p>}
        <button className="btn btn-primary justify-self-start" disabled={busy}>{busy ? "Saving…" : "Change password"}</button>
      </form>
    </section>
  );
}

export default function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;
  const rows: [string, string][] = [
    ["Name", user.name],
    ["Email", user.email],
    ["Organisation", user.organisation || "–"],
    ["Member since", new Date(user.created_at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })],
    ["Last login", when(user.last_login_at)],
  ];
  return (
    <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
      <div className="space-y-6">
        <section className="card">
          <h2 className="mb-4 font-semibold">Profile</h2>
          <dl className="divide-y divide-line text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="grid grid-cols-[8rem_1fr] gap-3 py-2.5">
                <dt className="text-muted">{k}</dt>
                <dd className="min-w-0 break-words">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-muted">To change these details, contact the maintainer for now.</p>
        </section>
        <ChangePassword />
      </div>
      <section className="card h-fit">
        <h2 className="font-semibold">Session</h2>
        <p className="mt-1 text-sm text-muted">Log out of this browser. Your API keys keep working.</p>
        <button className="btn btn-ghost mt-4 w-full" onClick={async () => { await logout(); navigate("/"); }}>Log out</button>
      </section>
    </div>
  );
}
