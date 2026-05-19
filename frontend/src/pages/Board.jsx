import { useEffect, useMemo, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { STATUS_META, STATUS_ORDER, PriorityIcon } from "@/lib/constants";
import { Plus, MoreHorizontal, ChevronRight } from "lucide-react";
import NewIssueModal from "@/components/NewIssueModal";
import TaskDetailPanel from "@/components/TaskDetailPanel";

export default function Board() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openNew, setOpenNew] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    setError("");
    try {
      const [p, t, m] = await Promise.all([
        api.get(`/projects/${projectId}`),
        api.get(`/projects/${projectId}/tasks`),
        api.get(`/workspaces/members`),
      ]);
      setProject(p.data);
      setTasks(t.data);
      setMembers(m.data);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    reload();
  }, [reload]);

  const memberMap = useMemo(() => {
    const map = {};
    members.forEach((m) => (map[m.user_id] = m));
    return map;
  }, [members]);

  const grouped = useMemo(() => {
    const g = { backlog: [], todo: [], in_progress: [], done: [] };
    for (const t of tasks) {
      if (g[t.status]) g[t.status].push(t);
    }
    return g;
  }, [tasks]);

  const handleCreate = async (payload) => {
    const { data } = await api.post(`/projects/${projectId}/tasks`, payload);
    setTasks((prev) => [data, ...prev]);
    setOpenNew(false);
  };

  const handleUpdate = async (taskId, patch) => {
    const { data } = await api.patch(`/tasks/${taskId}`, patch);
    setTasks((prev) => prev.map((t) => (t.task_id === taskId ? data : t)));
    return data;
  };

  const handleDelete = async (taskId) => {
    await api.delete(`/tasks/${taskId}`);
    setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
    setSelectedTaskId(null);
  };

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId) || null;

  if (loading && !project) {
    return (
      <div className="p-10 text-sm text-neutral-500 font-mono" data-testid="board-loading">
        Loading board…
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="board-page">
      {/* Page header */}
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)]">
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-neutral-500" data-testid="board-breadcrumb">
              <span>Engineering</span>
              <ChevronRight size={12} />
              <span className="text-neutral-700">{project?.name || "Project"}</span>
            </div>
            <h1 className="font-heading text-3xl font-semibold tracking-tight mt-2" data-testid="board-title">
              Board
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <AvatarStack members={members} />
            <button
              onClick={() => setOpenNew(true)}
              className="tf-btn-primary inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-md"
              data-testid="board-new-issue-btn"
            >
              <Plus size={14} /> New Issue
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="mx-8 mt-4 text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono" data-testid="board-error">
          {error}
        </div>
      )}

      {/* Columns */}
      <div className="flex-1 min-h-0 overflow-x-auto tf-scroll">
        <div className="h-full px-6 py-5 grid grid-cols-4 gap-4 min-w-[1100px]">
          {STATUS_ORDER.map((status) => {
            const items = grouped[status] || [];
            const meta = STATUS_META[status];
            return (
              <div key={status} className="min-w-0 flex flex-col" data-testid={`column-${status}`}>
                <div className="flex items-center justify-between px-1 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="tf-dot" style={{ background: meta.color }} />
                    <span className="font-heading text-sm font-medium">{meta.label}</span>
                    <span className="font-mono text-xs text-neutral-500">{items.length}</span>
                  </div>
                  <button className="text-neutral-400 hover:text-neutral-700 transition">
                    <MoreHorizontal size={14} />
                  </button>
                </div>
                <div className="flex-1 space-y-2 overflow-y-auto tf-scroll pr-1 pb-4">
                  {items.length === 0 ? (
                    <div className="text-xs font-mono text-neutral-400 px-2 py-3">No issues</div>
                  ) : (
                    items.map((t) => (
                      <TaskCard
                        key={t.task_id}
                        task={t}
                        assignee={memberMap[t.assignee_id]}
                        onOpen={() => setSelectedTaskId(t.task_id)}
                      />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <NewIssueModal
        open={openNew}
        onClose={() => setOpenNew(false)}
        onSubmit={handleCreate}
        members={members}
      />

      <TaskDetailPanel
        task={selectedTask}
        members={members}
        memberMap={memberMap}
        onClose={() => setSelectedTaskId(null)}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
      />
    </div>
  );
}

function TaskCard({ task, assignee, onOpen }) {
  const isDone = task.status === "done";
  return (
    <button
      onClick={onOpen}
      className={`group w-full text-left bg-white rounded-md border border-[var(--tf-border)] hover:border-[#9ca3af] hover:shadow-sm transition p-3 ${
        isDone ? "opacity-60" : ""
      }`}
      data-testid={`task-card-${task.key}`}
    >
      <div className="flex items-center justify-between">
        <span className={`font-mono text-[10px] tracking-wider uppercase text-neutral-500 ${isDone ? "line-through" : ""}`}>
          {task.key}
        </span>
        <PriorityIcon priority={task.priority} size={14} />
      </div>
      <div className={`text-[13px] mt-1.5 leading-snug text-neutral-900 ${isDone ? "line-through text-neutral-500" : ""}`}>
        {task.title}
      </div>
      <div className="mt-3 flex items-center justify-between min-h-[20px]">
        {task.tag ? (
          <span className="font-mono text-[10px] tracking-wider uppercase px-1.5 py-0.5 rounded-sm bg-[#0055ff]/10 text-[#0055ff]">
            {task.tag}
          </span>
        ) : (
          <span />
        )}
        {assignee?.picture ? (
          <img src={assignee.picture} alt={assignee.name} className="w-5 h-5 rounded-full object-cover" />
        ) : (
          <span className="w-5 h-5 rounded-full bg-neutral-200" />
        )}
      </div>
    </button>
  );
}

function AvatarStack({ members }) {
  const visible = members.slice(0, 3);
  const extra = Math.max(0, members.length - 3);
  return (
    <div className="flex items-center" data-testid="board-avatar-stack">
      <div className="flex -space-x-1.5">
        {visible.map((m) => (
          <img
            key={m.user_id}
            src={m.picture || ""}
            alt={m.name}
            className="w-7 h-7 rounded-full border-2 border-white object-cover bg-neutral-200"
          />
        ))}
        {extra > 0 && (
          <div className="w-7 h-7 rounded-full border-2 border-white bg-[#e7eeff] text-[#0055ff] grid place-items-center text-[10px] font-mono font-semibold">
            +{extra}
          </div>
        )}
      </div>
    </div>
  );
}
