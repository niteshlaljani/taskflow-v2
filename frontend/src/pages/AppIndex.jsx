import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";

/**
 * /app index route. Loads the user's projects and redirects to the first one.
 * If the user has no projects yet, creates a default "Inbox" project.
 */
export default function AppIndex() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/projects");
        if (cancelled) return;
        if (data.length > 0) {
          navigate(`/app/board/${data[0].project_id}`, { replace: true });
        } else {
          // Auto-create a default project for new users
          const { data: proj } = await api.post("/projects", {
            name: "Inbox",
            key: "INBOX",
            description: "Your first project — rename or create more anytime.",
          });
          navigate(`/app/board/${proj.project_id}`, { replace: true });
        }
      } catch (e) {
        setError(formatApiError(e));
      }
    })();
    return () => { cancelled = true; };
  }, [navigate]);

  return (
    <div className="p-10 text-sm font-mono text-neutral-500" data-testid="app-index-loading">
      {error ? `Error: ${error}` : "Loading workspace…"}
    </div>
  );
}
