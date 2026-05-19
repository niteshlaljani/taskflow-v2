import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const hash = location.hash || window.location.hash || "";
    const params = new URLSearchParams(hash.replace(/^#/, ""));
    const sessionId = params.get("session_id");

    if (!sessionId) {
      navigate("/login", { replace: true });
      return;
    }

    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id: sessionId });
        setUser(data.user);
        // strip hash, go to app
        window.history.replaceState(null, "", "/app");
        navigate("/app", { replace: true, state: { user: data.user } });
      } catch (e) {
        console.error("Auth session exchange failed", e);
        navigate("/login?error=oauth", { replace: true });
      }
    })();
  }, [location, navigate, setUser]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex items-center justify-center">
      <div className="font-mono text-sm text-neutral-400" data-testid="auth-callback-status">
        Signing you in…
      </div>
    </div>
  );
}
