import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, type ApiKey, type NewKey } from "../../lib/api";
import { when } from "../../lib/format";
import { setPlaygroundKey } from "../../lib/keyStore";
import { CopyButton, ErrorNote, Modal } from "../../components/ui";

type Confirm = { kind: "rotate" | "revoke" | "delete"; key: ApiKey } | null;

const CONFIRM_TEXT = {
  rotate: {
    title: "Rotate this key?",
    body: "You'll get a new key with the same label. The current key stops working immediately, so update your apps straight away.",
    action: "Rotate key",
  },
  revoke: {
    title: "Revoke this key?",
    body: "Requests using this key will be rejected from now on. This can't be undone, but its usage history is kept.",
    action: "Revoke key",
  },
  delete: {
    title: "Delete this key?",
    body: "The key is removed from this list. It stays revoked, and its requests still count in your usage.",
    action: "Delete key",
  },
};

function StatusBadge({ k }: { k: ApiKey }) {
  return k.active ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand">
      <span className="h-1.5 w-1.5 rounded-full bg-brand" aria-hidden="true" />Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-paper px-2 py-0.5 text-xs font-medium text-muted">
      <span className="h-1.5 w-1.5 rounded-full bg-muted" aria-hidden="true" />Revoked
    </span>
  );
}

export default function Keys() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [max, setMax] = useState(5);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<NewKey | null>(null);
  const [confirm, setConfirm] = useState<Confirm>(null);

  const load = useCallback(async () => {
    try {
      const r = await api<{ data: ApiKey[]; max_active_keys: number }>("/account/keys");
      // Active keys first, then revoked; newest first within each group.
      setKeys([...r.data].sort((a, b) => Number(b.active) - Number(a.active) || b.id - a.id));
      setMax(r.max_active_keys);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const active = keys?.filter((k) => k.active).length ?? 0;

  async function create(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setCreated(await api<NewKey>("/account/keys", { body: { label: label.trim() || "Default" } }));
      setLabel("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runConfirm() {
    if (!confirm) return;
    const { kind, key } = confirm;
    setBusy(true);
    setError("");
    try {
      if (kind === "rotate") setCreated(await api<NewKey>(`/account/keys/${key.id}/rotate`, { method: "POST" }));
      if (kind === "revoke") await api(`/account/keys/${key.id}/revoke`, { method: "POST" });
      if (kind === "delete") await api(`/account/keys/${key.id}`, { method: "DELETE" });
      setConfirm(null);
      await load();
    } catch (err) {
      setError((err as Error).message);
      setConfirm(null);
    } finally {
      setBusy(false);
    }
  }

  const actions = (k: ApiKey) => (
    <div className="flex flex-wrap justify-end gap-2">
      {k.active ? (
        <>
          <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => setConfirm({ kind: "rotate", key: k })}>Rotate</button>
          <button className="btn btn-ghost px-3 py-1.5 text-xs text-danger" onClick={() => setConfirm({ kind: "revoke", key: k })}>Revoke</button>
        </>
      ) : (
        <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => setConfirm({ kind: "delete", key: k })}>Delete</button>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <section className="card">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
          <h2 className="font-semibold">Create a key</h2>
          <span className="text-xs text-muted">{active} of {max} active keys</span>
        </div>
        <form onSubmit={create} className="mt-3 flex flex-col gap-2 sm:flex-row">
          <label htmlFor="label" className="sr-only">Label</label>
          <input id="label" className="field sm:max-w-xs" placeholder="Label, e.g. Production" maxLength={60} value={label} onChange={(e) => setLabel(e.target.value)} />
          <button className="btn btn-primary" disabled={busy || active >= max}>Create key</button>
        </form>
        {active >= max && <p className="mt-2 text-xs text-muted">You've reached the limit. Revoke a key to create another.</p>}
        <div className="mt-3"><ErrorNote>{error}</ErrorNote></div>
      </section>

      <section className="card overflow-hidden p-0">
        <h2 className="px-5 pt-5 font-semibold">Your keys</h2>
        {keys === null ? (
          <div className="m-5 h-24 animate-pulse rounded-lg bg-paper" />
        ) : keys.length === 0 ? (
          <p className="px-5 pb-6 pt-2 text-sm text-muted">No keys yet. Create one above to start calling the API.</p>
        ) : (
          <>
            {/* Table on wider screens */}
            <table className="mt-3 hidden w-full text-left text-sm md:table">
              <thead className="border-y border-line bg-paper text-xs text-muted">
                <tr>
                  <th className="px-5 py-2 font-medium">Label</th>
                  <th className="px-3 py-2 font-medium">Key</th>
                  <th className="px-3 py-2 font-medium">Created</th>
                  <th className="px-3 py-2 font-medium">Last used</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-5 py-2"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {keys.map((k) => (
                  <tr key={k.id} className={k.active ? "" : "text-muted"}>
                    <td className="px-5 py-3 font-medium">{k.label}</td>
                    <td className="px-3 py-3 font-mono text-xs">{k.prefix}…</td>
                    <td className="px-3 py-3">{when(k.created_at)}</td>
                    <td className="px-3 py-3">{when(k.last_used_at)}</td>
                    <td className="px-3 py-3"><StatusBadge k={k} /></td>
                    <td className="px-5 py-3">{actions(k)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Cards on phones */}
            <ul className="mt-3 divide-y divide-line border-t border-line md:hidden">
              {keys.map((k) => (
                <li key={k.id} className="space-y-2 px-5 py-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{k.label}</span>
                    <StatusBadge k={k} />
                  </div>
                  <div className="font-mono text-xs text-muted">{k.prefix}…</div>
                  <div className="text-xs text-muted">Created {when(k.created_at).toLowerCase()} · Last used {when(k.last_used_at).toLowerCase()}</div>
                  {actions(k)}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {created && (
        <Modal title={created.replaces ? "Your new key" : "Your API key"}>
          <p className="rounded-lg border border-gold/60 bg-gold/15 px-3 py-2 text-sm text-ink" role="alert">
            <strong>Copy this key now.</strong> It is shown only once and can't be recovered. If you lose it, rotate or create a new one.
          </p>
          <div className="mt-4 flex items-stretch gap-2">
            <code className="block min-w-0 flex-1 break-all rounded-lg bg-brand-soft px-3 py-2.5 font-mono text-sm" data-testid="raw-key">{created.api_key}</code>
            <CopyButton text={created.api_key} className="btn btn-primary shrink-0 px-4" />
          </div>
          {created.replaces && <p className="mt-3 text-sm text-muted">The old key has been revoked.</p>}
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Link to="/playground" className="btn btn-ghost" onClick={() => setPlaygroundKey(created.api_key)}>Try it in the playground</Link>
            <button className="btn btn-primary" onClick={() => setCreated(null)}>I've saved my key</button>
          </div>
        </Modal>
      )}

      {confirm && (
        <Modal title={CONFIRM_TEXT[confirm.kind].title} onClose={() => !busy && setConfirm(null)}>
          <p className="text-sm text-muted">
            <span className="font-medium text-ink">{confirm.key.label}</span> <code>({confirm.key.prefix}…)</code>
          </p>
          <p className="mt-2 text-sm">{CONFIRM_TEXT[confirm.kind].body}</p>
          <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button className="btn btn-ghost" onClick={() => setConfirm(null)} disabled={busy}>Cancel</button>
            <button className={confirm.kind === "rotate" ? "btn btn-primary" : "btn btn-danger"} onClick={runConfirm} disabled={busy}>
              {busy ? "Working…" : CONFIRM_TEXT[confirm.kind].action}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
