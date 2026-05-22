import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, formatApiError } from "@/lib/api";

export default function CreateProjectModal({ open, onClose, onCreated }) {
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setName("");
      setKey("");
      setDescription("");
      setError("");
    }
  }, [open]);

  // Auto-derive key from name (uppercase, first 4 letters)
  const onNameChange = (v) => {
    setName(v);
    if (!key) {
      const derived = v.replace(/[^a-zA-Z]/g, "").slice(0, 4).toUpperCase();
      if (derived.length >= 2) setKey(derived);
    }
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!name.trim()) return setError("Name required");
    if (!key.trim() || key.trim().length < 2) return setError("Key must be at least 2 characters");
    setSubmitting(true);
    try {
      const { data } = await api.post("/projects", {
        name: name.trim(),
        key: key.trim().toUpperCase(),
        description: description.trim(),
      });
      onCreated?.(data);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 tf-backdrop"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 z-50 grid place-items-center p-4 pointer-events-none"
          >
            <form
              onSubmit={submit}
              className="pointer-events-auto w-full max-w-md rounded-lg bg-white shadow-2xl border border-[var(--tf-border)] overflow-hidden"
              data-testid="create-project-modal"
            >
              <div className="px-6 pt-5 pb-2">
                <h2 className="font-heading text-lg font-medium tracking-tight">Create project</h2>
                <p className="text-xs text-neutral-500 mt-0.5">Give your project a clear name and a short key (used as the task ID prefix).</p>
              </div>
              <div className="px-6 pb-4 space-y-3">
                <Field
                  label="Project name"
                  value={name}
                  onChange={onNameChange}
                  placeholder="e.g. Mobile App"
                  testid="create-project-name-input"
                  autoFocus
                />
                <Field
                  label="Key"
                  value={key}
                  onChange={(v) => setKey(v.toUpperCase().replace(/[^A-Z0-9]/g, ""))}
                  placeholder="e.g. MOB"
                  testid="create-project-key-input"
                  hint="Tasks will be MOB-1, MOB-2, …"
                  maxLength={8}
                />
                <Field
                  label="Description"
                  value={description}
                  onChange={setDescription}
                  placeholder="Optional"
                  testid="create-project-description-input"
                  textarea
                />
                {error && (
                  <div className="text-xs text-red-600 font-mono" data-testid="create-project-error">{error}</div>
                )}
              </div>
              <div className="px-6 py-3 bg-[#f9fafb] border-t border-[var(--tf-border)] flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="text-sm px-3 py-1.5 rounded-md text-neutral-600 hover:text-neutral-900 transition"
                  data-testid="create-project-cancel-btn"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="tf-btn-primary text-sm font-medium px-4 py-1.5 rounded-md disabled:opacity-60"
                  data-testid="create-project-submit-btn"
                >
                  {submitting ? "Creating…" : "Create project"}
                </button>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function Field({ label, value, onChange, placeholder, testid, hint, textarea, autoFocus, maxLength }) {
  return (
    <div>
      <label className="text-[11px] font-mono uppercase tracking-wider text-neutral-500">{label}</label>
      {textarea ? (
        <textarea
          rows={3}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="mt-1.5 w-full text-sm bg-white border border-[var(--tf-border)] rounded-md px-3 py-2 outline-none focus:border-[var(--tf-primary)] transition resize-none"
          data-testid={testid}
        />
      ) : (
        <input
          autoFocus={autoFocus}
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          maxLength={maxLength}
          className="mt-1.5 w-full text-sm bg-white border border-[var(--tf-border)] rounded-md px-3 py-2 outline-none focus:border-[var(--tf-primary)] transition"
          data-testid={testid}
        />
      )}
      {hint && <div className="text-[11px] text-neutral-400 mt-1 font-mono">{hint}</div>}
    </div>
  );
}
