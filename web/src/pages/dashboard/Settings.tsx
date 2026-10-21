import { useNavigate } from "react-router";
import { useAuth } from "../../lib/auth";
import { when } from "../../lib/format";

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
      <section className="card">
        <h2 className="font-semibold">Session</h2>
        <p className="mt-1 text-sm text-muted">Log out of this browser. Your API keys keep working.</p>
        <button className="btn btn-ghost mt-4 w-full" onClick={async () => { await logout(); navigate("/"); }}>Log out</button>
      </section>
    </div>
  );
}
