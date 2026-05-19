import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Check } from "lucide-react";
import { api } from "@/lib/api";

export default function NotificationBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unread, setUnread] = useState(0);
  const popoverRef = useRef(null);

  const refresh = async () => {
    try {
      const [list, count] = await Promise.all([
        api.get("/notifications"),
        api.get("/notifications/unread-count"),
      ]);
      setNotifications(list.data);
      setUnread(count.data?.count || 0);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 20000);
    return () => clearInterval(t);
  }, []);

  // Allow other components to nudge a refresh after creating a notification-worthy event
  useEffect(() => {
    const h = () => refresh();
    window.addEventListener("tf:notifications-refresh", h);
    return () => window.removeEventListener("tf:notifications-refresh", h);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const markAllRead = async () => {
    await api.post("/notifications/read-all");
    setUnread(0);
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const onItemClick = async (n) => {
    if (!n.read) {
      try { await api.post(`/notifications/${n.notification_id}/read`); } catch {}
      setNotifications((p) => p.map((x) => x.notification_id === n.notification_id ? { ...x, read: true } : x));
      setUnread((u) => Math.max(0, u - 1));
    }
    setOpen(false);
    if (n.project_id) navigate(`/app/board/${n.project_id}`);
  };

  return (
    <div className="relative" ref={popoverRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-neutral-500 hover:text-neutral-900 transition relative"
        data-testid="topbar-notifications-btn"
        aria-label="Notifications"
      >
        <Bell size={16} />
        {unread > 0 && (
          <span
            className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-[#0055ff] text-white text-[10px] font-mono leading-4 text-center font-semibold"
            data-testid="topbar-notifications-badge"
          >
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-md border border-[var(--tf-border)] bg-white shadow-2xl z-50 overflow-hidden" data-testid="notifications-dropdown">
          <div className="px-4 py-2.5 border-b border-[var(--tf-border)] flex items-center justify-between">
            <div className="font-heading font-medium text-sm">Notifications</div>
            {unread > 0 && (
              <button
                onClick={markAllRead}
                className="text-[11px] font-mono uppercase tracking-wider text-[#0055ff] hover:underline"
                data-testid="notifications-mark-all-read-btn"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-neutral-400">No notifications yet.</div>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.notification_id}
                  onClick={() => onItemClick(n)}
                  className={`w-full text-left px-4 py-2.5 border-b border-[var(--tf-border)] last:border-b-0 hover:bg-neutral-50 transition flex items-start gap-2 ${
                    n.read ? "" : "bg-blue-50/40"
                  }`}
                  data-testid={`notification-${n.notification_id}`}
                >
                  {!n.read && <span className="tf-dot bg-[#0055ff] mt-1.5 shrink-0" />}
                  {n.read && <span className="w-2 mt-1.5 shrink-0" />}
                  <div className="min-w-0">
                    <div className="text-sm text-neutral-900">{n.message || `${n.type} on ${n.task_id}`}</div>
                    <div className="text-[11px] font-mono text-neutral-400 mt-0.5">
                      {relativeTime(n.created_at)}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function relativeTime(iso) {
  const then = new Date(iso);
  const diff = (new Date() - then) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d`;
  return then.toLocaleDateString();
}
