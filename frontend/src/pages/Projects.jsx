import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Plus, FolderKanban, Trash2 } from "lucide-react";
import CreateProjectModal from "@/components/CreateProjectModal";

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openCreate, setOpenCreate] = useState(false);
  const [error, setError] = useState("");

  const reload = async () => {
    try {
      const { data } = await api.get("/projects");
      setProjects(data);
    } catch (e) {
      setError(formatApiError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const handleCreated = (p) => {
    setProjects((prev) => [...prev, p]);
    setOpenCreate(false);
  };

  const handleDelete = async (proj) => {
    if (!window.confirm(`Delete project "${proj.name}" and all its tasks? This cannot be undone.`)) return;
    try {
      await api.delete(`/projects/${proj.project_id}`);
      setProjects((prev) => prev.filter((p) => p.project_id !== proj.project_id));
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  return (
    <div className="h-full flex flex-col overflow-hidden" data-testid="projects-page">
      <div className="px-8 pt-7 pb-5 bg-white border-b border-[var(--tf-border)] flex items-start justify-between gap-6">
        <div>
          <div className="text-xs text-neutral-500">Workspace</div>
          <h1 className="font-heading text-3xl font-semibold tracking-tight mt-1">Projects</h1>
        </div>
        <button
          onClick={() => setOpenCreate(true)}
          className="tf-btn-primary inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-md"
          data-testid="projects-new-btn"
        >
          <Plus size={14} /> New Project
        </button>
      </div>

      {error && (
        <div className="mx-8 mt-4 text-xs px-3 py-2 rounded-md border border-red-200 bg-red-50 text-red-700 font-mono">{error}</div>
      )}

      <div className="flex-1 min-h-0 overflow-y-auto tf-scroll">
        {loading ? (
          <div className="p-10 text-sm font-mono text-neutral-500">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="px-8 py-16 text-center">
            <div className="font-mono text-xs uppercase tracking-wider text-neutral-400 mb-2">No projects</div>
            <button
              onClick={() => setOpenCreate(true)}
              className="tf-btn-primary inline-flex items-center gap-1.5 text-sm font-medium px-4 py-2 rounded-md mt-4"
            >
              <Plus size={14} /> Create your first project
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-6">
            {projects.map((p) => (
              <div
                key={p.project_id}
                className="group relative rounded-lg border border-[var(--tf-border)] bg-white p-5 hover:border-neutral-400 hover:shadow-sm transition"
                data-testid={`project-card-${p.key}`}
              >
                <Link to={`/app/board/${p.project_id}`} className="block">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-md bg-[#0055ff]/10 grid place-items-center text-[#0055ff] font-mono font-semibold text-sm">
                      {p.key.slice(0, 2)}
                    </div>
                    <div className="min-w-0">
                      <div className="font-heading font-medium text-base text-neutral-900 truncate">{p.name}</div>
                      <div className="font-mono text-[11px] uppercase tracking-wider text-neutral-500 mt-0.5">{p.key}</div>
                    </div>
                  </div>
                  {p.description && (
                    <div className="text-sm text-neutral-600 mt-3 line-clamp-2 min-h-[40px]">{p.description}</div>
                  )}
                  <div className="mt-4 flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-neutral-400">
                    <FolderKanban size={12} /> {p.next_task_number - 1} {p.next_task_number - 1 === 1 ? "issue" : "issues"}
                  </div>
                </Link>
                <button
                  onClick={() => handleDelete(p)}
                  className="absolute top-3 right-3 p-1.5 rounded-md text-neutral-400 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition"
                  data-testid={`project-delete-${p.key}`}
                  aria-label="Delete project"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <CreateProjectModal open={openCreate} onClose={() => setOpenCreate(false)} onCreated={handleCreated} />
    </div>
  );
}
