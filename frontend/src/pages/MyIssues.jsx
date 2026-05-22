import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { STATUS_META, PriorityIcon } from "@/lib/constants";
import { ChevronRight } from "lucide-react";

export default function MyIssues() {
  const [tasks, setTasks] = useState([]);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [t, p] = await Promise.all([api.get("/my-issues"), api.get("/projects")]);
        setTasks(t.data);
        setProjects(p.data);
      } catch (e) {
        setError(formatApiError(e));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const projectMap = Object.fromEntries(projects.map((p) => [p.project_id, p]));

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="my-issues-page">
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)]">
        <div className="flex items-center gap-1.5 text-xs text-neutral-500">
          <span>You</span>
          <ChevronRight size={12} />
          <span className="text-neutral-700">Assigned to me</span>
        </div>
        <h1 className="font-heading text-3xl font-semibold tracking-tight mt-2">My Issues</h1>
        <div className="text-sm text-neutral-500 mt-1 font-mono">
          {loading ? "Loading…" : `${tasks.length} ${tasks.length === 1 ? "issue" : "issues"} assigned`}
        </div>
      </div>

      {error && (
        <div className="mx-8 mt-4 text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono">{error}</div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto tf-scroll">
        {tasks.length === 0 && !loading ? (
          <div className="px-8 py-16 text-center">
            <div className="font-mono text-xs uppercase tracking-wider text-neutral-400 mb-2">Inbox zero</div>
            <div className="text-neutral-600">Nothing assigned to you yet.</div>
          </div>
        ) : (
          <ul className="px-4 py-2">
            {tasks.map((t) => {
              const proj = projectMap[t.project_id];
              const meta = STATUS_META[t.status];
              return (
                <li key={t.task_id} className="border-b border-[var(--tf-border)] last:border-b-0">
                  <Link
                    to={proj ? `/app/board/${proj.project_id}` : "#"}
                    className="flex items-center gap-4 px-4 py-3 hover:bg-neutral-50 transition group"
                    data-testid={`my-issue-row-${t.key}`}
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
                    <span className="font-mono text-[10px] uppercase tracking-wider text-neutral-400 w-24 text-right shrink-0">
                      {meta.label}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
