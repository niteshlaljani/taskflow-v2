import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, formatApiError } from "@/lib/api";

function defaultDates() {
  const today = new Date();
  const start = today.toISOString().slice(0, 10);
  const endD = new Date(today.getTime() + 14 * 24 * 3600 * 1000);
  const end = endD.toISOString().slice(0, 10);
  return { start, end };
}

export default function CreateSprintModal({ open, onClose, onCreated, projectId }) {
  const dd = defaultDates();
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [startDate, setStartDate] = useState(dd.start);
  const [endDate, setEndDate] = useState(dd.end);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setName("");
      setGoal("");
      const d = defaultDates();
      setStartDate(d.start);
      setEndDate(d.end);
      setError("");
    }
  }, [open]);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!name.trim()) return setError("Sprint name required");
    setSubmitting(true);
    try {
      const { data } = await api.post(`/projects/${projectId}/sprints`, {
        name: name.trim(),
        goal: goal.trim(),
        start_date: startDate,
        end_date: endDate,
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
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 tf-backdrop" onClick={onClose}
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
              data-testid="create-sprint-modal"
            >
              <div className="px-6 pt-5 pb-2">
                <h2 className="font-heading text-lg font-medium tracking-tight">New sprint</h2>
                <p className="text-xs text-neutral-500 mt-0.5">Plan a focused iteration with clear dates and goal.</p>
              </div>
              <div className="px-6 pb-4 space-y-3">
                <Field label="Sprint name" value={name} onChange={setName} placeholder="Sprint 12" testid="sprint-name-input" autoFocus />
                <Field label="Goal (optional)" value={goal} onChange={setGoal} placeholder="What does success look like?" testid="sprint-goal-input" />
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Start date" value={startDate} onChange={setStartDate} type="date" testid="sprint-start-input" />
                  <Field label="End date" value={endDate} onChange={setEndDate} type="date" testid="sprint-end-input" />
                </div>
                {error && <div className="text-xs text-red-600 font-mono" data-testid="sprint-error">{error}</div>}
              </div>
              <div className="px-6 py-3 bg-[#f9fafb] border-t border-[var(--tf-border)] flex items-center justify-end gap-2">
                <button type="button" onClick={onClose} className="text-sm px-3 py-1.5 rounded-md text-neutral-600 hover:text-neutral-900 transition" data-testid="sprint-cancel-btn">Cancel</button>
                <button type="submit" disabled={submitting} className="tf-btn-primary text-sm font-medium px-4 py-1.5 rounded-md disabled:opacity-60" data-testid="sprint-submit-btn">
                  {submitting ? "Creating…" : "Create sprint"}
                </button>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function Field({ label, value, onChange, placeholder, testid, type = "text", autoFocus }) {
  return (
    <div>
      <label className="text-[11px] font-mono uppercase tracking-wider text-neutral-500">{label}</label>
      <input
        autoFocus={autoFocus}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1.5 w-full text-sm bg-white border border-[var(--tf-border)] rounded-md px-3 py-2 outline-none focus:border-[var(--tf-primary)] transition"
        data-testid={testid}
      />
    </div>
  );
}
