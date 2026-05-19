import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Workflow, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function JoinInvite() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();
  const [invite, setInvite] = useState(null);
  const [error, setError] = useState("");
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/invites/${code}`);
        setInvite(data);
      } catch (e) {
        setError(formatApiError(e));
      }
    })();
  }, [code]);

  const accept = async () => {
    setAccepting(true);
    try {
      await api.post(`/invites/${code}/accept`);
      navigate("/app", { replace: true });
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setAccepting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
      <header className="px-6 lg:px-10 h-16 flex items-center">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-sm bg-[#0055ff] grid place-items-center">
            <Workflow size={16} />
          </div>
          <span className="font-heading font-semibold tracking-tight text-[15px]">TaskFlow</span>
        </Link>
      </header>

      <main className="flex-1 grid place-items-center px-6 py-10">
        <div className="w-full max-w-md text-center">
          {error ? (
            <>
              <div className="font-mono text-[11px] uppercase tracking-wider text-red-400 mb-3">Invite issue</div>
              <h1 className="font-heading text-2xl font-semibold tracking-tight" data-testid="join-error">{error}</h1>
              <Link to="/login" className="tf-btn-primary mt-6 inline-flex items-center gap-2 text-sm font-medium px-5 py-2 rounded-md">
                Go to TaskFlow <ArrowRight size={14} />
              </Link>
            </>
          ) : !invite ? (
            <div className="font-mono text-sm text-neutral-500">Loading invite…</div>
          ) : invite.expired ? (
            <>
              <div className="font-mono text-[11px] uppercase tracking-wider text-red-400 mb-3">Expired</div>
              <h1 className="font-heading text-2xl font-semibold tracking-tight">This invite link has expired.</h1>
              <p className="text-neutral-400 text-sm mt-2">Ask {invite.inviter_name} for a new one.</p>
            </>
          ) : (
            <>
              <div className="font-mono text-[11px] uppercase tracking-wider text-neutral-500 mb-3">You've been invited</div>
              <h1 className="font-heading text-3xl font-semibold tracking-tight" data-testid="join-workspace-name">
                Join <span className="text-[#0055ff]">{invite.workspace_name}</span>
              </h1>
              <p className="text-neutral-400 text-sm mt-3">
                {invite.inviter_name} invited you to collaborate on TaskFlow.
              </p>

              {authLoading ? (
                <div className="font-mono text-sm text-neutral-500 mt-8">…</div>
              ) : user ? (
                <button
                  onClick={accept}
                  disabled={accepting}
                  className="tf-btn-primary mt-8 inline-flex items-center gap-2 text-sm font-medium px-6 py-2.5 rounded-md disabled:opacity-60"
                  data-testid="join-accept-btn"
                >
                  {accepting ? "Joining…" : `Accept and join`} {!accepting && <ArrowRight size={14} />}
                </button>
              ) : (
                <div className="mt-8 space-y-3">
                  <Link
                    to={`/register?next=/join/${code}`}
                    className="tf-btn-primary block text-sm font-medium px-6 py-2.5 rounded-md"
                    data-testid="join-register-btn"
                  >
                    Create account to join
                  </Link>
                  <Link
                    to={`/login?next=/join/${code}`}
                    className="block text-sm font-medium px-6 py-2.5 rounded-md border border-[#2a2a2a] hover:border-neutral-500 transition"
                    data-testid="join-login-btn"
                  >
                    Sign in
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
