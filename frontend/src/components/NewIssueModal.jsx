import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Paperclip, Link2 } from "lucide-react";
import { STATUS_META, PRIORITY_META, PriorityIcon } from "@/lib/constants";

const STATUSES = ["backlog", "todo", "in_progress", "done"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

export default function NewIssueModal({ open, onClose, onSubmit, members }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("todo");
  const [priority, setPriority] = useState("medium");
  const [assigneeId, setAssigneeId] = useState(null);
  const [tag, setTag] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) {
      setTitle("");
      setDescription("");
      setStatus("todo");
      setPriority("medium");
      setAssigneeId(null);
      setTag("");
      setError("");
    }
  }, [open]);

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim(),
        status,
        priority,
        assignee_id: assigneeId,
        tag: tag.trim() ? tag.trim().toUpperCase() : null,
      });
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Failed");
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
            data-testid="new-issue-modal-backdrop"
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
              className="pointer-events-auto w-full max-w-xl rounded-lg bg-white shadow-2xl border border-[var(--tf-border)] overflow-hidden"
              data-testid="new-issue-modal"
            >
              <div className="px-6 pt-5 pb-3">
                <input
                  autoFocus
                  type="text"
                  placeholder="Issue title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full text-xl font-medium font-heading tracking-tight bg-transparent outline-none placeholder:text-neutral-400"
                  data-testid="new-issue-title-input"
                />
                <textarea
                  rows={4}
                  placeholder="Add description..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="mt-3 w-full text-sm bg-transparent outline-none resize-none placeholder:text-neutral-400"
                  data-testid="new-issue-description-input"
                />
                {error && (
                  <div className="mt-2 text-xs text-red-600 font-mono" data-testid="new-issue-error">{error}</div>
                )}
              </div>

              <div className="px-6 pb-4 flex flex-wrap items-center gap-2">
                <PillSelect
                  label="Status"
                  value={status}
                  onChange={setStatus}
                  options={STATUSES.map((s) => ({
                    value: s,
                    label: STATUS_META[s].label,
                    swatch: <span className="tf-dot" style={{ background: STATUS_META[s].color }} />,
                  }))}
                  testid="new-issue-status-select"
                />
                <PillSelect
                  label="Priority"
                  value={priority}
                  onChange={setPriority}
                  options={PRIORITIES.map((p) => ({
                    value: p,
                    label: PRIORITY_META[p].label,
                    swatch: <PriorityIcon priority={p} size={12} />,
                  }))}
                  testid="new-issue-priority-select"
                />
                <PillSelect
                  label="Assignee"
                  value={assigneeId || ""}
                  onChange={(v) => setAssigneeId(v || null)}
                  options={[
                    { value: "", label: "Unassigned", swatch: <span className="w-3 h-3 rounded-full bg-neutral-200" /> },
                    ...members.map((m) => ({
                      value: m.user_id,
                      label: m.name,
                      swatch: m.picture ? (
                        <img src={m.picture} alt="" className="w-3.5 h-3.5 rounded-full object-cover" />
                      ) : (
                        <span className="w-3 h-3 rounded-full bg-neutral-200" />
                      ),
                    })),
                  ]}
                  testid="new-issue-assignee-select"
                />
                <input
                  type="text"
                  value={tag}
                  onChange={(e) => setTag(e.target.value)}
                  placeholder="TAG"
                  className="text-[11px] font-mono uppercase tracking-wider px-2 py-1 rounded-md border border-[var(--tf-border)] outline-none focus:border-[var(--tf-primary)] w-24"
                  data-testid="new-issue-tag-input"
                />
              </div>

              <div className="px-6 py-3 bg-[#f9fafb] border-t border-[var(--tf-border)] flex items-center justify-between">
                <div className="flex items-center gap-3 text-neutral-400">
                  <button type="button" className="hover:text-neutral-700 transition" aria-label="Attach"><Paperclip size={15} /></button>
                  <button type="button" className="hover:text-neutral-700 transition" aria-label="Link"><Link2 size={15} /></button>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="text-sm px-3 py-1.5 rounded-md text-neutral-600 hover:text-neutral-900 transition"
                    data-testid="new-issue-cancel-btn"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="tf-btn-primary text-sm font-medium px-4 py-1.5 rounded-md disabled:opacity-60"
                    data-testid="new-issue-submit-btn"
                  >
                    {submitting ? "Creating…" : "Create Issue"}
                  </button>
                </div>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function PillSelect({ label, value, onChange, options, testid }) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value) || options[0];
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-md border border-[var(--tf-border)] hover:bg-neutral-50 transition"
        data-testid={testid}
      >
        {current?.swatch}
        <span className="font-mono uppercase tracking-wider text-[10px] text-neutral-500">{label}</span>
        <span className="text-neutral-900">{current?.label}</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute z-20 mt-1 w-56 max-h-72 overflow-y-auto rounded-md border border-[var(--tf-border)] bg-white shadow-lg py-1">
            {options.map((o) => (
              <button
                type="button"
                key={String(o.value)}
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2 text-xs px-3 py-2 hover:bg-neutral-50 ${
                  o.value === value ? "bg-neutral-50" : ""
                }`}
                data-testid={`${testid}-option-${String(o.value) || "none"}`}
              >
                {o.swatch}
                <span className="text-neutral-900">{o.label}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
