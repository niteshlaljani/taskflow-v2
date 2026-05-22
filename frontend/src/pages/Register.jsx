import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Workflow } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";

export default function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [searchParams] = useSearchParams();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(email, password, name);
      const next = searchParams.get("next") || "/app";
      navigate(next, { replace: true });
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const onGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const next = searchParams.get("next") || "/app";
    const redirectUrl = window.location.origin + next;
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
      <header className="px-6 lg:px-10 h-16 flex items-center">
        <Link to="/" className="flex items-center gap-2" data-testid="register-logo-link">
          <div className="w-7 h-7 rounded-sm bg-[#0055ff] grid place-items-center">
            <Workflow size={16} />
          </div>
          <span className="font-heading font-semibold tracking-tight text-[15px]">TaskFlow</span>
        </Link>
      </header>

      <main className="flex-1 grid place-items-center px-6 py-10">
        <div className="w-full max-w-sm">
          <h1 className="font-heading text-3xl font-semibold tracking-tight">Create your account</h1>
          <p className="text-sm text-neutral-400 mt-1.5">Free forever for small teams.</p>

          {error && (
            <div className="mt-5 text-xs px-3 py-2 rounded-md border border-red-900/50 bg-red-950/30 text-red-300 font-mono" data-testid="register-error">
              {error}
            </div>
          )}

          <button
            type="button"
            onClick={onGoogle}
            className="mt-6 w-full text-sm font-medium px-4 py-2.5 rounded-md border border-[#2a2a2a] bg-[#111] hover:border-neutral-500 transition flex items-center justify-center gap-2"
            data-testid="register-google-btn"
          >
            <GoogleG />
            Continue with Google
          </button>

          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-[#1f1f1f]" />
            <span className="text-[10px] font-mono uppercase tracking-wider text-neutral-600">or</span>
            <div className="h-px flex-1 bg-[#1f1f1f]" />
          </div>

          <form onSubmit={onSubmit} className="space-y-3">
            <Field label="Name" value={name} onChange={setName} type="text" testid="register-name-input" />
            <Field label="Email" value={email} onChange={setEmail} type="email" testid="register-email-input" />
            <Field label="Password" value={password} onChange={setPassword} type="password" testid="register-password-input" minLength={6} />
            <button
              type="submit"
              disabled={loading}
              className="tf-btn-primary w-full text-sm font-medium px-4 py-2.5 rounded-md disabled:opacity-60"
              data-testid="register-submit-btn"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
          </form>

          <div className="mt-6 text-xs text-neutral-500">
            Already have an account?{" "}
            <Link to="/login" className="text-[#79a3ff] hover:text-white transition" data-testid="register-to-login-link">
              Sign in
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}

function Field({ label, value, onChange, type, testid, minLength }) {
  return (
    <div>
      <label className="text-[11px] font-mono uppercase tracking-wider text-neutral-500">{label}</label>
      <input
        type={type}
        value={value}
        minLength={minLength}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1.5 w-full text-sm bg-[#111] border border-[#2a2a2a] rounded-md px-3 py-2.5 outline-none focus:border-[#0055ff] transition"
        data-testid={testid}
        required
      />
    </div>
  );
}

function GoogleG() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.07 5.07 0 0 1-2.2 3.32v2.77h3.56c2.08-1.92 3.28-4.75 3.28-8.1Z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.99 7.28-2.66l-3.56-2.77c-.99.66-2.25 1.06-3.72 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" fill="#34A853" />
      <path d="M5.84 14.1A6.6 6.6 0 0 1 5.48 12c0-.73.13-1.44.36-2.1V7.07H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.93l3.66-2.83Z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.07.56 4.21 1.65l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.07L5.84 9.9C6.71 7.3 9.14 5.38 12 5.38Z" fill="#EA4335" />
    </svg>
  );
}
