import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Plus, ChevronRight, Calendar, Target, ChevronsRight, Play, CheckCircle2, Trash2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, BarChart, Bar, Legend } from "recharts";
import CreateSprintModal from "@/components/CreateSprintModal";

export default function Sprints() {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [sprints, setSprints] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [velocity, setVelocity] = useState({ sprints: [], average: 0 });
  const [active, setActive] = useState(null);
  const [burndown, setBurndown] = useState(null);
  const [openCreate, setOpenCreate] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const [p, s, t, v] = await Promise.all([
        api.get(`/projects/${projectId}`),
        api.get(`/projects/${projectId}/sprints`),
        api.get(`/projects/${projectId}/tasks`),
        api.get(`/projects/${projectId}/velocity`),
      ]);
      setProject(p.data);
      setSprints(s.data);
      setTasks(t.data);
      setVelocity(v.data);
      if (s.data.length && !active) setActive(s.data[0]);
    } catch (e) {
      setError(formatApiError(e));
    }
  };

  useEffect(() => { load(); }, [projectId]);

  useEffect(() => {
    if (!active) { setBurndown(null); return; }
    (async () => {
      try {
        const { data } = await api.get(`/sprints/${active.sprint_id}/burndown`);
        setBurndown(data);
      } catch (e) {
        setBurndown(null);
      }
    })();
  }, [active?.sprint_id]);

  const taskMap = useMemo(() => Object.fromEntries(tasks.map((t) => [t.task_id, t])), [tasks]);

  const onCreated = (s) => {
    setSprints((prev) => [s, ...prev]);
    setActive(s);
    setOpenCreate(false);
  };

  const setStatus = async (sprint, status) => {
    try {
      const { data } = await api.patch(`/sprints/${sprint.sprint_id}`, { status });
      setSprints((p) => p.map((x) => (x.sprint_id === sprint.sprint_id ? data : x)));
      if (active?.sprint_id === sprint.sprint_id) setActive(data);
      load();
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  const deleteSprint = async (sprint) => {
    if (!window.confirm(`Delete sprint "${sprint.name}"? (Tasks themselves remain.)`)) return;
    try {
      await api.delete(`/sprints/${sprint.sprint_id}`);
      setSprints((p) => p.filter((x) => x.sprint_id !== sprint.sprint_id));
      if (active?.sprint_id === sprint.sprint_id) setActive(null);
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  const toggleTaskInSprint = async (taskId) => {
    if (!active) return;
    const isIn = (active.task_ids || []).includes(taskId);
    try {
      if (isIn) {
        const { data } = await api.delete(`/sprints/${active.sprint_id}/tasks/${taskId}`);
        setActive(data);
        setSprints((p) => p.map((x) => (x.sprint_id === data.sprint_id ? data : x)));
      } else {
        const { data } = await api.post(`/sprints/${active.sprint_id}/tasks`, { task_ids: [taskId] });
        setActive(data);
        setSprints((p) => p.map((x) => (x.sprint_id === data.sprint_id ? data : x)));
      }
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="sprints-page">
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)]">
        <div className="flex items-start justify-between gap-6">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-neutral-500">
              <Link to={`/app/board/${projectId}`} className="hover:text-neutral-700">{project?.name || "Project"}</Link>
              <ChevronRight size={12} />
              <span className="text-neutral-700">Sprints</span>
            </div>
            <h1 className="font-heading text-3xl font-semibold tracking-tight mt-2">Sprints</h1>
          </div>
          <button
            onClick={() => setOpenCreate(true)}
            className="tf-btn-primary inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-md"
            data-testid="sprints-new-btn"
          >
            <Plus size={14} /> New Sprint
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-8 mt-4 text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono">{error}</div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto tf-scroll">
        <div className="p-6 grid grid-cols-12 gap-6">
          {/* Left: sprint list */}
          <div className="col-span-12 lg:col-span-3 space-y-1">
            <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 px-2 mb-2">Sprints</div>
            {sprints.length === 0 ? (
              <div className="text-sm text-neutral-400 px-2 py-4">No sprints yet</div>
            ) : (
              sprints.map((s) => (
                <button
                  key={s.sprint_id}
                  onClick={() => setActive(s)}
                  className={`w-full text-left px-3 py-2 rounded-md transition ${
                    active?.sprint_id === s.sprint_id ? "bg-[#0055ff]/10 border-l-2 border-[#0055ff]" : "hover:bg-neutral-100"
                  }`}
                  data-testid={`sprint-list-item-${s.sprint_id}`}
                >
                  <div className="flex items-center gap-2">
                    <SprintStatusDot status={s.status} />
                    <span className="font-medium text-sm text-neutral-900 truncate flex-1">{s.name}</span>
                  </div>
                  <div className="text-[11px] font-mono text-neutral-400 ml-4 mt-0.5">
                    {s.start_date} → {s.end_date}
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Center: active sprint detail */}
          <div className="col-span-12 lg:col-span-6 space-y-6">
            {active ? (
              <>
                <div className="rounded-md border border-[var(--tf-border)] bg-white p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <SprintStatusDot status={active.status} />
                        <span className="font-mono text-[10px] uppercase tracking-wider text-neutral-500">{active.status}</span>
                      </div>
                      <h2 className="font-heading text-2xl font-semibold tracking-tight mt-1">{active.name}</h2>
                      {active.goal && (
                        <div className="text-sm text-neutral-600 mt-1 flex items-center gap-1.5"><Target size={13} /> {active.goal}</div>
                      )}
                      <div className="text-xs text-neutral-500 mt-2 flex items-center gap-1.5">
                        <Calendar size={12} /> {active.start_date} → {active.end_date}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {active.status === "planned" && (
                        <button onClick={() => setStatus(active, "active")} className="text-xs inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-[var(--tf-border)] hover:bg-neutral-50 transition" data-testid="sprint-start-btn">
                          <Play size={12} /> Start
                        </button>
                      )}
                      {active.status === "active" && (
                        <button onClick={() => setStatus(active, "completed")} className="tf-btn-primary text-xs inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md" data-testid="sprint-complete-btn">
                          <CheckCircle2 size={12} /> Complete
                        </button>
                      )}
                      <button onClick={() => deleteSprint(active)} className="p-1.5 text-neutral-400 hover:text-red-600 hover:bg-red-50 rounded transition" data-testid="sprint-delete-btn" aria-label="Delete sprint">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Burn-down */}
                <div className="rounded-md border border-[var(--tf-border)] bg-white p-5" data-testid="sprint-burndown">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-3">Burn-down</div>
                  {burndown && burndown.series.length > 0 ? (
                    <div style={{ width: "100%", height: 220 }}>
                      <ResponsiveContainer>
                        <LineChart data={burndown.series} margin={{ top: 5, right: 16, bottom: 0, left: -16 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                          <XAxis dataKey="date" tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                          <YAxis tick={{ fontSize: 10, fontFamily: "IBM Plex Mono" }} />
                          <Tooltip contentStyle={{ fontSize: 12, fontFamily: "IBM Plex Mono" }} />
                          <Line type="monotone" dataKey="ideal" stroke="#9ca3af" strokeDasharray="4 3" dot={false} name="Ideal" />
                          <Line type="monotone" dataKey="remaining" stroke="#0055ff" strokeWidth={2} dot={{ r: 3 }} name="Remaining" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="text-sm text-neutral-400">Add tasks to this sprint to see burn-down.</div>
                  )}
                </div>

                {/* Task picker */}
                <div className="rounded-md border border-[var(--tf-border)] bg-white" data-testid="sprint-task-picker">
                  <div className="px-4 py-2.5 border-b border-[var(--tf-border)] flex items-center justify-between">
                    <div className="font-heading text-sm font-medium">Tasks in sprint <span className="font-mono text-neutral-400 ml-1">{active.task_ids?.length || 0}</span></div>
                  </div>
                  <div className="max-h-72 overflow-y-auto">
                    {tasks.length === 0 ? (
                      <div className="px-4 py-6 text-sm text-neutral-400">No tasks in this project yet.</div>
                    ) : (
                      <ul>
                        {tasks.map((t) => {
                          const inSprint = (active.task_ids || []).includes(t.task_id);
                          return (
                            <li key={t.task_id} className="px-4 py-2 flex items-center gap-3 border-b border-[var(--tf-border)] last:border-b-0 hover:bg-neutral-50 transition">
                              <input
                                type="checkbox"
                                checked={inSprint}
                                onChange={() => toggleTaskInSprint(t.task_id)}
                                className="accent-[#0055ff]"
                                data-testid={`sprint-task-toggle-${t.key}`}
                              />
                              <span className="font-mono text-[10px] tracking-wider text-neutral-500 w-16 shrink-0">{t.key}</span>
                              <span className={`flex-1 text-sm truncate ${t.status === "done" ? "line-through text-neutral-400" : "text-neutral-900"}`}>{t.title}</span>
                              <span className="text-[10px] font-mono uppercase tracking-wider text-neutral-400 w-20 text-right">{t.status}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="rounded-md border border-dashed border-[var(--tf-border)] p-12 text-center">
                <div className="font-mono text-[11px] uppercase tracking-wider text-neutral-400">Pick a sprint</div>
                <div className="text-neutral-600 mt-2 text-sm">Select a sprint on the left, or create a new one.</div>
              </div>
            )}
          </div>

          {/* Right: velocity */}
          <div className="col-span-12 lg:col-span-3 space-y-4">
            <div className="rounded-md border border-[var(--tf-border)] bg-white p-5" data-testid="velocity-card">
              <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-1">Velocity</div>
              <div className="font-heading text-3xl font-semibold tracking-tight">{velocity.average}</div>
              <div className="text-xs text-neutral-500 mt-0.5">tasks / sprint (avg)</div>
              {velocity.sprints.length > 0 && (
                <div style={{ width: "100%", height: 140 }} className="mt-4">
                  <ResponsiveContainer>
                    <BarChart data={velocity.sprints} margin={{ top: 5, right: 8, bottom: 0, left: -28 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 9, fontFamily: "IBM Plex Mono" }} interval={0} />
                      <YAxis tick={{ fontSize: 9, fontFamily: "IBM Plex Mono" }} allowDecimals={false} />
                      <Tooltip contentStyle={{ fontSize: 11, fontFamily: "IBM Plex Mono" }} />
                      <Bar dataKey="completed" fill="#0055ff" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {velocity.sprints.length === 0 && (
                <div className="text-xs text-neutral-400 mt-3">Complete sprints to see velocity trend.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <CreateSprintModal
        open={openCreate}
        onClose={() => setOpenCreate(false)}
        onCreated={onCreated}
        projectId={projectId}
      />
    </div>
  );
}

function SprintStatusDot({ status }) {
  const color = status === "active" ? "#0055ff" : status === "completed" ? "#10b981" : "#9ca3af";
  return <span className="tf-dot" style={{ background: color }} />;
}
