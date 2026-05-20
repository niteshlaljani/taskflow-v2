import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { STATUS_META, PriorityIcon } from "@/lib/constants";
import { Inbox, Flame, CheckCircle2, Layers, ChevronRight } from "lucide-react";

const FILTERS = [
  { id: "all", label: "All issues", icon: Layers, match: () => true },
  { id: "urgent", label: "Urgent", icon: Flame, match: (t) => t.priority === "urgent" || t.priority === "high" },
  { id: "in_progress", label: "Active", icon: Inbox, match: (t) => t.status === "in_progress" },
  { id: "done", label: "Recently shipped", icon: CheckCircle2, match: (t) => t.status === "done" },
];

export default function Views() {
  const [tasks, setTasks] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState("all");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [{ data: projs }] = await Promise.all([api.get("/projects")]);
        setProjects(projs);
        // Fetch tasks for every project the user has access to
        const all = await Promise.all(
          projs.map((p) => api.get(`/projects/${p.project_id}/tasks`).then((r) => r.data).catch(() => []))
        );
        setTasks(all.flat());
      } catch (e) {
        setError(formatApiError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const projectMap = useMemo(() => Object.fromEntries(projects.map((p) => [p.project_id, p])), [projects]);

  const currentFilter = FILTERS.find((f) => f.id === active) || FILTERS[0];
  const filtered = useMemo(() => tasks.filter(currentFilter.match), [tasks, currentFilter]);
  const counts = useMemo(() => {
    const map = {};
    FILTERS.forEach((f) => (map[f.id] = tasks.filter(f.match).length));
    return map;
  }, [tasks]);

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="views-page">
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)]">
        <div className="text-xs text-neutral-500">Workspace</div>
        <h1 className="font-heading text-3xl font-semibold tracking-tight mt-1">Views</h1>
        <p className="text-sm text-neutral-500 mt-1 font-mono">
          {loading ? "Loading…" : `${tasks.length} ${tasks.length === 1 ? "issue" : "issues"} across ${projects.length} ${projects.length === 1 ? "project" : "projects"}`}
        </p>
      </div>

      {error && (
        <div className="mx-8 mt-4 text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono">{error}</div>
      )}

      <div className="flex-1 min-h-0 overflow-hidden flex">
        {/* Left rail: saved views */}
        <aside className="w-60 shrink-0 border-r border-[var(--tf-border)] bg-white p-3 space-y-0.5 overflow-y-auto">
          <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 px-2 py-2">Saved views</div>
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setActive(f.id)}
              className={`w-full flex items-center gap-2 text-sm px-3 py-2 rounded-md transition ${
                active === f.id ? "bg-[#0055ff]/10 text-[#0055ff] font-medium" : "text-neutral-700 hover:bg-neutral-50"
              }`}
              data-testid={`view-filter-${f.id}`}
            >
              <f.icon size={14} />
              <span className="flex-1 text-left">{f.label}</span>
              <span className="font-mono text-[10px] text-neutral-400">{counts[f.id]}</span>
            </button>
          ))}
        </aside>

        {/* Right: list */}
        <div className="flex-1 min-w-0 overflow-y-auto tf-scroll">
          {filtered.length === 0 ? (
            <div className="px-8 py-16 text-center">
              <div className="font-mono text-xs uppercase tracking-wider text-neutral-400 mb-2">Empty</div>
              <div className="text-neutral-600">No issues match this view.</div>
            </div>
          ) : (
            <ul>
              {filtered.map((t) => {
                const proj = projectMap[t.project_id];
                const meta = STATUS_META[t.status];
                return (
                  <li key={t.task_id} className="border-b border-[var(--tf-border)] last:border-b-0">
                    <Link
                      to={proj ? `/app/board/${proj.project_id}` : "#"}
                      className="flex items-center gap-4 px-6 py-3 hover:bg-neutral-50 transition group"
                      data-testid={`views-row-${t.key}`}
                    >
                      <span className="tf-dot shrink-0" style={{ background: meta.color }} />
                      <span className="font-mono text-[11px] tracking-wider text-neutral-500 w-20 shrink-0">{t.key}</span>
                      <span className="flex-1 text-sm text-neutral-900 truncate group-hover:text-[#0055ff] transition">{t.title}</span>
                      {t.tag && (
                        <span className="font-mono text-[10px] tracking-wider uppercase px-1.5 py-0.5 rounded-sm bg-[#0055ff]/10 text-[#0055ff] shrink-0">
                          {t.tag}
                        </span>
                      )}
                      <PriorityIcon priority={t.priority} size={14} />
                      <span className="font-mono text-[10px] uppercase tracking-wider text-neutral-400 w-24 text-right shrink-0 hidden sm:inline">
                        {proj?.name || ""}
                      </span>
                      <ChevronRight size={14} className="text-neutral-300 group-hover:text-neutral-500 transition" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
