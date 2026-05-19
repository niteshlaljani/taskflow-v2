import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Copy, Trash2, Plus, Check, Link2 } from "lucide-react";

export default function Settings() {
  const { user } = useAuth();
  const [workspace, setWorkspace] = useState(null);
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [copiedCode, setCopiedCode] = useState(null);

  const reload = async () => {
    try {
      const [w, m, i] = await Promise.all([
        api.get("/workspaces/current"),
        api.get("/workspaces/members"),
        api.get("/workspaces/invites").catch(() => ({ data: [] })),
      ]);
      setWorkspace(w.data);
      setMembers(m.data);
      setInvites(i.data || []);
    } catch (e) {
      setError(formatApiError(e));
    }
  };
  useEffect(() => { reload(); }, []);

  const isOwner = workspace && user && workspace.owner_id === user.user_id;

  const generateInvite = async () => {
    setCreating(true);
    try {
      const { data } = await api.post("/workspaces/invites", { expires_in_days: 7 });
      setInvites((prev) => [data, ...prev]);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setCreating(false);
    }
  };

  const revokeInvite = async (id) => {
    if (!window.confirm("Revoke this invite link?")) return;
    try {
      await api.delete(`/workspaces/invites/${id}`);
      setInvites((prev) => prev.filter((inv) => inv.invite_id !== id));
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  const copyLink = async (code) => {
    const link = `${window.location.origin}/join/${code}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopiedCode(code);
      setTimeout(() => setCopiedCode(null), 1500);
    } catch {
      // fallback
      window.prompt("Copy invite link:", link);
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="settings-page">
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)]">
        <div className="text-xs text-neutral-500">Workspace</div>
        <h1 className="font-heading text-3xl font-semibold tracking-tight mt-1">Settings</h1>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto tf-scroll">
        <div className="max-w-3xl mx-auto p-8 space-y-10">
          {error && (
            <div className="text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono">{error}</div>
          )}

          {/* Workspace section */}
          <section>
            <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-3">Workspace</div>
            <div className="rounded-md border border-[var(--tf-border)] bg-white p-5">
              <div className="font-heading font-medium text-lg" data-testid="settings-workspace-name">
                {workspace?.name || "—"}
              </div>
              <div className="text-xs text-neutral-500 font-mono mt-1">{workspace?.workspace_id}</div>
            </div>
          </section>

          {/* Members */}
          <section>
            <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-3">
              Members <span className="text-neutral-400">({members.length})</span>
            </div>
            <ul className="rounded-md border border-[var(--tf-border)] bg-white divide-y divide-[var(--tf-border)]">
              {members.map((m) => (
                <li key={m.user_id} className="flex items-center gap-3 px-4 py-3" data-testid={`member-row-${m.user_id}`}>
                  {m.picture ? (
                    <img src={m.picture} alt="" className="w-8 h-8 rounded-full object-cover" />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-neutral-200 grid place-items-center text-xs">
                      {(m.name || "?").slice(0, 1).toUpperCase()}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-neutral-900 truncate">{m.name}</div>
                    <div className="text-xs text-neutral-500 truncate">{m.email}</div>
                  </div>
                  {workspace?.owner_id === m.user_id && (
                    <span className="font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-[#0055ff]/10 text-[#0055ff]">
                      Owner
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Invite links */}
          {isOwner && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500">Invite links</div>
                <button
                  onClick={generateInvite}
                  disabled={creating}
                  className="tf-btn-primary inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-md disabled:opacity-60"
                  data-testid="settings-generate-invite-btn"
                >
                  <Plus size={12} /> {creating ? "Generating…" : "Generate invite link"}
                </button>
              </div>

              {invites.length === 0 ? (
                <div className="rounded-md border border-dashed border-[var(--tf-border)] bg-white p-6 text-center">
                  <Link2 size={20} className="mx-auto text-neutral-400" />
                  <div className="text-sm text-neutral-600 mt-2">No active invite links</div>
                  <div className="text-xs text-neutral-400 mt-1 font-mono">Generate one to invite teammates.</div>
                </div>
              ) : (
                <ul className="rounded-md border border-[var(--tf-border)] bg-white divide-y divide-[var(--tf-border)]">
                  {invites.map((inv) => {
                    const link = `${window.location.origin}/join/${inv.code}`;
                    const expiresAt = new Date(inv.expires_at);
                    const expired = expiresAt < new Date();
                    return (
                      <li key={inv.invite_id} className="flex items-center gap-3 px-4 py-3" data-testid={`invite-row-${inv.invite_id}`}>
                        <div className="flex-1 min-w-0">
                          <div className="font-mono text-xs text-neutral-700 truncate">{link}</div>
                          <div className="text-[11px] font-mono text-neutral-400 mt-0.5">
                            {expired ? "Expired" : `Expires ${expiresAt.toLocaleDateString()}`} ·{" "}
                            {inv.used_by?.length || 0} used
                          </div>
                        </div>
                        <button
                          onClick={() => copyLink(inv.code)}
                          className="text-xs inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-[var(--tf-border)] hover:bg-neutral-50 transition"
                          data-testid={`invite-copy-${inv.invite_id}`}
                        >
                          {copiedCode === inv.code ? (
                            <><Check size={12} className="text-emerald-600" /> Copied</>
                          ) : (
                            <><Copy size={12} /> Copy link</>
                          )}
                        </button>
                        <button
                          onClick={() => revokeInvite(inv.invite_id)}
                          className="p-1.5 rounded-md text-neutral-400 hover:text-red-600 hover:bg-red-50 transition"
                          data-testid={`invite-revoke-${inv.invite_id}`}
                          aria-label="Revoke invite"
                        >
                          <Trash2 size={14} />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
