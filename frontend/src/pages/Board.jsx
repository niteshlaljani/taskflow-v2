import { useEffect, useMemo, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import {
  DndContext,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  DragOverlay,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { api, formatApiError } from "@/lib/api";
import { STATUS_META, STATUS_ORDER, PriorityIcon } from "@/lib/constants";
import { Plus, MoreHorizontal, ChevronRight, Radio } from "lucide-react";
import NewIssueModal from "@/components/NewIssueModal";
import TaskDetailPanel from "@/components/TaskDetailPanel";
import { useAuth } from "@/context/AuthContext";
import useBoardSocket from "@/hooks/useBoardSocket";

export default function Board() {
  const { projectId } = useParams();
  const { user } = useAuth();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openNew, setOpenNew] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [error, setError] = useState("");
  const [activeDragId, setActiveDragId] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const onSearch = (e) => setSearchQuery((e.detail || "").toLowerCase());
    window.addEventListener("tf:search", onSearch);
    return () => window.removeEventListener("tf:search", onSearch);
  }, []);

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

  // Real-time updates via WS
  const { presence } = useBoardSocket(projectId, {
    onTaskCreated: (task, by) => {
      if (by === user?.user_id) return; // we already added optimistically
      setTasks((prev) => (prev.some((t) => t.task_id === task.task_id) ? prev : [task, ...prev]));
    },
    onTaskUpdated: (task, by) => {
      if (by === user?.user_id) return;
      setTasks((prev) => prev.map((t) => (t.task_id === task.task_id ? task : t)));
    },
    onTaskDeleted: (taskId, by) => {
      if (by === user?.user_id) return;
      setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
    },
  });

  const memberMap = useMemo(() => {
    const map = {};
    members.forEach((m) => (map[m.user_id] = m));
    return map;
  }, [members]);

  const grouped = useMemo(() => {
    const g = { backlog: [], todo: [], in_progress: [], done: [] };
    const q = searchQuery.trim();
    for (const t of tasks) {
      if (!g[t.status]) continue;
      if (q) {
        const hay = `${t.key} ${t.title} ${t.description || ""} ${t.tag || ""}`.toLowerCase();
        if (!hay.includes(q)) continue;
      }
      g[t.status].push(t);
    }
    return g;
  }, [tasks, searchQuery]);

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

  // -------- Drag & Drop --------
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));
  const activeTask = activeDragId ? tasks.find((t) => t.task_id === activeDragId) : null;

  const findContainer = (id) => {
    // id can be a column id (e.g. "col:backlog") or task id
    if (typeof id === "string" && id.startsWith("col:")) return id.slice(4);
    const t = tasks.find((x) => x.task_id === id);
    return t ? t.status : null;
  };

  const onDragStart = (e) => setActiveDragId(e.active.id);

  const onDragEnd = async (e) => {
    setActiveDragId(null);
    const { active, over } = e;
    if (!over) return;
    const taskId = active.id;
    const newStatus = findContainer(over.id);
    if (!newStatus) return;
    const task = tasks.find((t) => t.task_id === taskId);
    if (!task || task.status === newStatus) return;
    // Optimistic update
    setTasks((prev) => prev.map((t) => (t.task_id === taskId ? { ...t, status: newStatus } : t)));
    try {
      await api.patch(`/tasks/${taskId}`, { status: newStatus });
    } catch (err) {
      // Revert
      setTasks((prev) => prev.map((t) => (t.task_id === taskId ? task : t)));
      setError(formatApiError(err));
    }
  };

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId) || null;

  // Others viewing this board (excluding current user)
  const others = (presence || []).filter((p) => p.user_id !== user?.user_id);

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
            <PresenceStack others={others} />
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
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={onDragStart}
          onDragEnd={onDragEnd}
          onDragCancel={() => setActiveDragId(null)}
        >
          <div className="h-full px-6 py-5 grid grid-cols-4 gap-4 min-w-[1100px]">
            {STATUS_ORDER.map((status) => {
              const items = grouped[status] || [];
              return (
                <Column key={status} status={status} items={items}>
                  {items.length === 0 ? (
                    <div className="text-xs font-mono text-neutral-400 px-2 py-3">No issues</div>
                  ) : (
                    <SortableContext items={items.map((i) => i.task_id)} strategy={verticalListSortingStrategy}>
                      {items.map((t) => (
                        <SortableTaskCard
                          key={t.task_id}
                          task={t}
                          assignee={memberMap[t.assignee_id]}
                          onOpen={() => setSelectedTaskId(t.task_id)}
                        />
                      ))}
                    </SortableContext>
                  )}
                </Column>
              );
            })}
          </div>
          <DragOverlay>
            {activeTask ? (
              <TaskCardView task={activeTask} assignee={memberMap[activeTask.assignee_id]} dragging />
            ) : null}
          </DragOverlay>
        </DndContext>
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

function Column({ status, items, children }) {
  const meta = STATUS_META[status];
  const { setNodeRef, isOver } = useSortable({ id: `col:${status}`, data: { type: "column" } });
  return (
    <div className="min-w-0 flex flex-col" data-testid={`column-${status}`}>
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
      <div
        ref={setNodeRef}
        className={`flex-1 space-y-2 overflow-y-auto tf-scroll pr-1 pb-4 rounded-md transition-colors ${
          isOver ? "bg-[#0055ff]/5 ring-1 ring-[#0055ff]/30" : ""
        }`}
      >
        {children}
      </div>
    </div>
  );
}

function SortableTaskCard({ task, assignee, onOpen }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.task_id,
    data: { type: "task", task },
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <TaskCardView task={task} assignee={assignee} onOpen={onOpen} />
    </div>
  );
}

function TaskCardView({ task, assignee, onOpen, dragging }) {
  const isDone = task.status === "done";
  const handleClick = (e) => {
    // dnd-kit listeners use pointerdown; we click on pointerup if not dragged
    if (e.defaultPrevented) return;
    onOpen?.();
  };
  return (
    <div
      onClick={handleClick}
      className={`group w-full text-left bg-white rounded-md border border-[var(--tf-border)] hover:border-[#9ca3af] hover:shadow-sm transition p-3 cursor-grab active:cursor-grabbing ${
        isDone ? "opacity-60" : ""
      } ${dragging ? "shadow-xl rotate-1" : ""}`}
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
    </div>
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
            src={m.picture || undefined}
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

function PresenceStack({ others }) {
  if (!others?.length) return null;
  const visible = others.slice(0, 3);
  const extra = Math.max(0, others.length - 3);
  return (
    <div className="flex items-center gap-2 pr-2 mr-1 border-r border-[var(--tf-border)]" data-testid="board-presence">
      <span className="flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider text-emerald-600">
        <Radio size={10} className="animate-pulse" /> Live
      </span>
      <div className="flex -space-x-1.5">
        {visible.map((p) => (
          <div key={p.user_id} className="relative" title={`${p.name} is viewing`}>
            {p.picture ? (
              <img src={p.picture} alt={p.name} className="w-7 h-7 rounded-full border-2 border-emerald-400 object-cover bg-neutral-200" />
            ) : (
              <div className="w-7 h-7 rounded-full border-2 border-emerald-400 bg-neutral-200 grid place-items-center text-[10px]">
                {(p.name || "?").slice(0, 1).toUpperCase()}
              </div>
            )}
            <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white" />
          </div>
        ))}
        {extra > 0 && (
          <div className="w-7 h-7 rounded-full border-2 border-emerald-400 bg-emerald-50 text-emerald-700 grid place-items-center text-[10px] font-mono font-semibold">
            +{extra}
          </div>
        )}
      </div>
    </div>
  );
}
