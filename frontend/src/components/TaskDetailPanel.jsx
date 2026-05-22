import { useEffect, useState, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Share2, Send, CheckCircle2, Trash2 } from "lucide-react";
import { api, formatApiError } from "@/lib/api";
import { STATUS_META, PRIORITY_META, PriorityIcon } from "@/lib/constants";
import TaskAttachments from "@/components/TaskAttachments";
import { useAuth } from "@/context/AuthContext";

const STATUSES = ["backlog", "todo", "in_progress", "done"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

export default function TaskDetailPanel({ task, members, memberMap, onClose, onUpdate, onDelete }) {
  const { user } = useAuth();
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    if (!task) return;
    try {
      const { data } = await api.get(`/tasks/${task.task_id}/comments`);
      setComments(data);
    } catch (e) {
      console.error(e);
    }
  }, [task]);

  useEffect(() => {
    setNewComment("");
    setError("");
    reload();
  }, [task, reload]);

  const postComment = async (e) => {
    e?.preventDefault?.();
    if (!task) return;
    const body = newComment.trim();
    if (!body) return;
    setPosting(true);
    try {
      const { data } = await api.post(`/tasks/${task.task_id}/comments`, { body });
      setComments((p) => [...p, data]);
      setNewComment("");
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setPosting(false);
    }
  };

  return (
    <AnimatePresence>
      {task && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 tf-backdrop"
            onClick={onClose}
            data-testid="task-detail-backdrop"
          />
          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            className="fixed top-0 right-0 z-50 h-full w-full sm:w-[600px] lg:w-[680px] bg-white shadow-2xl border-l border-[var(--tf-border)] flex flex-col"
            data-testid="task-detail-panel"
          >
            {/* Header */}
            <div className="h-14 px-6 flex items-center justify-between border-b border-[var(--tf-border)]">
              <div className="flex items-center gap-2">
                <CheckCircle2
                  size={16}
                  className={task.status === "done" ? "text-emerald-500" : "text-neutral-400"}
                />
                <span className="font-mono text-xs tracking-wider text-neutral-700" data-testid="task-detail-key">
                  {task.key}
                </span>
              </div>
              <div className="flex items-center gap-2 text-neutral-500">
                <button className="hover:text-neutral-800 transition" data-testid="task-detail-share-btn">
                  <Share2 size={15} />
                </button>
                <button
                  onClick={() => {
                    if (window.confirm("Delete this task?")) onDelete(task.task_id);
                  }}
                  className="hover:text-red-600 transition"
                  data-testid="task-detail-delete-btn"
                >
                  <Trash2 size={15} />
                </button>
                <button onClick={onClose} className="hover:text-neutral-800 transition" data-testid="task-detail-close-btn">
                  <X size={17} />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 min-h-0 overflow-y-auto">
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_220px] gap-6 px-6 py-6">
                {/* Left: title + description + activity */}
                <div className="min-w-0">
                  <TitleField task={task} onUpdate={onUpdate} />
                  <div className="mt-6">
                    <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-2 flex items-center gap-2">
                      Description
                    </div>
                    <DescriptionField task={task} onUpdate={onUpdate} />
                  </div>

                  <div className="mt-8 pt-6 border-t border-[var(--tf-border)]">
                    <TaskAttachments taskId={task.task_id} currentUserId={user?.user_id} />
                  </div>

                  <div className="mt-8 pt-6 border-t border-[var(--tf-border)]">
                    <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-4">Activity</div>
                    {comments.length === 0 ? (
                      <div className="text-sm text-neutral-400">No activity yet.</div>
                    ) : (
                      <ul className="space-y-5">
                        {comments.map((c) => {
                          const author = memberMap[c.author_id];
                          return (
                            <li key={c.comment_id} className="flex gap-3" data-testid={`comment-${c.comment_id}`}>
                              {author?.picture ? (
                                <img src={author.picture} alt="" className="w-7 h-7 rounded-full object-cover shrink-0" />
                              ) : (
                                <span className="w-7 h-7 rounded-full bg-neutral-200 shrink-0" />
                              )}
                              <div className="min-w-0">
                                <div className="text-xs">
                                  <span className="font-medium text-neutral-900">{author?.name || "Unknown"}</span>
                                  <span className="text-neutral-400 ml-2">{relativeTime(c.created_at)}</span>
                                </div>
                                <div className="text-sm text-neutral-700 mt-0.5 whitespace-pre-wrap">{c.body}</div>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>

                {/* Right: meta */}
                <div className="space-y-5 lg:border-l lg:border-[var(--tf-border)] lg:pl-5">
                  <MetaSection label="Status">
                    <PillEditor
                      value={task.status}
                      options={STATUSES.map((s) => ({
                        value: s,
                        label: STATUS_META[s].label,
                        swatch: <span className="tf-dot" style={{ background: STATUS_META[s].color }} />,
                      }))}
                      onChange={(v) => onUpdate(task.task_id, { status: v })}
                      testid="task-detail-status-select"
                    />
                  </MetaSection>
                  <MetaSection label="Priority">
                    <PillEditor
                      value={task.priority}
                      options={PRIORITIES.map((p) => ({
                        value: p,
                        label: PRIORITY_META[p].label,
                        swatch: <PriorityIcon priority={p} size={12} />,
                      }))}
                      onChange={(v) => onUpdate(task.task_id, { priority: v })}
                      testid="task-detail-priority-select"
                    />
                  </MetaSection>
                  <MetaSection label="Assignee">
                    <PillEditor
                      value={task.assignee_id || ""}
                      options={[
                        { value: "", label: "Unassigned", swatch: <span className="w-3.5 h-3.5 rounded-full bg-neutral-200" /> },
                        ...members.map((m) => ({
                          value: m.user_id,
                          label: m.name,
                          swatch: m.picture ? (
                            <img src={m.picture} alt="" className="w-4 h-4 rounded-full object-cover" />
                          ) : (
                            <span className="w-3.5 h-3.5 rounded-full bg-neutral-200" />
                          ),
                        })),
                      ]}
                      onChange={(v) => onUpdate(task.task_id, { assignee_id: v || null })}
                      testid="task-detail-assignee-select"
                    />
                  </MetaSection>
                  {task.tag && (
                    <MetaSection label="Tag">
                      <span className="font-mono text-[10px] tracking-wider uppercase px-1.5 py-0.5 rounded-sm bg-[#0055ff]/10 text-[#0055ff]">
                        {task.tag}
                      </span>
                    </MetaSection>
                  )}
                </div>
              </div>
            </div>

            {/* Comment composer (extra pr to clear the fixed 'Made with Emergent' badge in bottom-right) */}
            <form onSubmit={postComment} className="px-6 py-3 pr-48 border-t border-[var(--tf-border)] bg-white flex items-center gap-2" data-testid="task-detail-composer">
              <input
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="Add a comment..."
                className="flex-1 text-sm bg-[#f3f4f6] border border-transparent rounded-md px-3 py-2 outline-none focus:border-[var(--tf-primary)] focus:bg-white transition"
                data-testid="task-detail-comment-input"
              />
              <button
                type="submit"
                disabled={posting || !newComment.trim()}
                className="tf-btn-primary p-2 rounded-md disabled:opacity-50"
                data-testid="task-detail-comment-submit-btn"
              >
                <Send size={15} />
              </button>
            </form>
            {error && (
              <div className="px-6 pb-2 text-xs text-red-600 font-mono" data-testid="task-detail-error">{error}</div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function MetaSection({ label, children }) {
  return (
    <div>
      <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-1.5">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function TitleField({ task, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(task.title);
  useEffect(() => setVal(task.title), [task.title]);

  const save = async () => {
    setEditing(false);
    if (val.trim() && val.trim() !== task.title) {
      await onUpdate(task.task_id, { title: val.trim() });
    } else {
      setVal(task.title);
    }
  };

  if (editing) {
    return (
      <input
        autoFocus
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onBlur={save}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") {
            setVal(task.title);
            setEditing(false);
          }
        }}
        className="w-full text-2xl font-heading font-semibold tracking-tight bg-transparent outline-none border-b border-[var(--tf-primary)] py-1"
        data-testid="task-detail-title-input"
      />
    );
  }
  return (
    <h2
      onClick={() => setEditing(true)}
      className="text-2xl font-heading font-semibold tracking-tight cursor-text"
      data-testid="task-detail-title"
    >
      {task.title}
    </h2>
  );
}

function DescriptionField({ task, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(task.description || "");
  useEffect(() => setVal(task.description || ""), [task.description]);

  const save = async () => {
    setEditing(false);
    if ((val || "") !== (task.description || "")) {
      await onUpdate(task.task_id, { description: val });
    }
  };

  if (editing) {
    return (
      <textarea
        autoFocus
        rows={6}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        onBlur={save}
        className="w-full text-sm bg-[#f9fafb] border border-[var(--tf-border)] rounded-md p-3 outline-none focus:border-[var(--tf-primary)] resize-y"
        data-testid="task-detail-description-input"
      />
    );
  }

  const text = task.description?.trim();
  return (
    <div
      onClick={() => setEditing(true)}
      className="text-sm text-neutral-700 leading-relaxed whitespace-pre-wrap cursor-text min-h-[60px]"
      data-testid="task-detail-description"
    >
      {text ? (
        renderDescription(text)
      ) : (
        <span className="text-neutral-400">Add description…</span>
      )}
    </div>
  );
}

function renderDescription(text) {
  // Simple renderer: lines starting with "- " become bullet items, otherwise paragraphs.
  const lines = text.split(/\n/);
  const out = [];
  let buf = [];
  const flushBullets = () => {
    if (buf.length) {
      out.push(
        <ul key={`ul-${out.length}`} className="list-disc pl-5 space-y-1.5 my-2">
          {buf.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      );
      buf = [];
    }
  };
  lines.forEach((ln, idx) => {
    if (ln.startsWith("- ") || ln.startsWith("* ")) {
      buf.push(ln.slice(2));
    } else if (ln.trim() === "") {
      flushBullets();
    } else {
      flushBullets();
      out.push(<p key={`p-${idx}`} className="mb-2 last:mb-0">{ln}</p>);
    }
  });
  flushBullets();
  return out;
}

function PillEditor({ value, options, onChange, testid }) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value) || options[0];
  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-md border border-[var(--tf-border)] hover:bg-neutral-50 transition"
        data-testid={testid}
      >
        {current?.swatch}
        <span className="text-neutral-900">{current?.label}</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute z-20 mt-1 w-56 max-h-72 overflow-y-auto rounded-md border border-[var(--tf-border)] bg-white shadow-lg py-1 right-0">
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

function relativeTime(iso) {
  const then = new Date(iso);
  const now = new Date();
  const diff = (now - then) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} days ago`;
  return then.toLocaleDateString();
}
