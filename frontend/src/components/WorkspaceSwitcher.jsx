import { useEffect, useRef, useState } from "react";
import { ChevronsUpDown, Plus, Check } from "lucide-react";
import { api } from "@/lib/api";

export default function WorkspaceSwitcher({ activeWorkspace, onSwitch }) {
  const [open, setOpen] = useState(false);
  const [workspaces, setWorkspaces] = useState([]);
  const popoverRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/workspaces");
        setWorkspaces(data);
      } catch {}
    })();
  }, [activeWorkspace?.workspace_id]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const switchTo = async (ws) => {
    setOpen(false);
    if (ws.workspace_id === activeWorkspace?.workspace_id) return;
    try {
      const { data } = await api.post("/workspaces/switch", { workspace_id: ws.workspace_id });
      try { localStorage.setItem("tf_active_workspace", ws.workspace_id); } catch {}
      onSwitch?.(data);
    } catch (e) {
      // ignore
    }
  };

  const initial = (activeWorkspace?.name?.[0] || "W").toUpperCase();
  const onlyOne = workspaces.length <= 1;

  return (
    <div className="relative" ref={popoverRef}>
      <button
        onClick={() => !onlyOne && setOpen((v) => !v)}
        className={`w-full flex items-start gap-3 text-left ${onlyOne ? "cursor-default" : "hover:bg-white/5 rounded-md -mx-1 px-1 py-0.5 transition"}`}
        data-testid="workspace-switcher-trigger"
        disabled={onlyOne}
      >
        <div className="w-9 h-9 rounded-md bg-[#0055ff] grid place-items-center text-white font-bold font-mono text-sm shrink-0">
          {initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-white font-semibold text-sm leading-tight font-heading truncate" data-testid="sidebar-workspace-name">
            {activeWorkspace?.name || "Workspace"}
          </div>
          <div className="text-[11px] text-neutral-500 font-mono tracking-wider mt-0.5 uppercase">
            High-performance Team
          </div>
        </div>
        {!onlyOne && <ChevronsUpDown size={14} className="text-neutral-500 mt-1.5 shrink-0" />}
      </button>
      {open && !onlyOne && (
        <div className="absolute left-0 right-0 mt-2 rounded-md border border-[#262626] bg-[#0d0d0d] shadow-2xl z-50 overflow-hidden" data-testid="workspace-switcher-list">
          {workspaces.map((w) => (
            <button
              key={w.workspace_id}
              onClick={() => switchTo(w)}
              className="w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-white/5 transition"
              data-testid={`workspace-option-${w.workspace_id}`}
            >
              <div className="w-6 h-6 rounded-sm bg-[#0055ff] grid place-items-center text-white font-bold font-mono text-[11px]">
                {(w.name?.[0] || "W").toUpperCase()}
              </div>
              <span className="text-neutral-200 truncate flex-1">{w.name}</span>
              {w.workspace_id === activeWorkspace?.workspace_id && <Check size={14} className="text-emerald-500" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
