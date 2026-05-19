import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "@/lib/api";

/**
 * Hook for board real-time WebSocket — receives task.created/updated/deleted, comment.created, presence.
 *
 * Auth strategy: we fetch a short-lived JWT from POST /api/auth/ws-token and pass it as a
 * `?token=` query parameter on the WS URL. This is necessary because the k8s ingress in front
 * of the backend does not forward httpOnly cookies on the WSS upgrade handshake.
 */
export default function useBoardSocket(projectId, handlers = {}) {
  const [presence, setPresence] = useState([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  const send = useCallback((data) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === 1) {
      ws.send(typeof data === "string" ? data : JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    let retry = null;

    const open = async () => {
      if (!alive) return;
      let token = "";
      try {
        const { data } = await api.post("/auth/ws-token");
        token = data?.token || "";
      } catch {
        // Not authenticated — skip (no WS for anonymous)
        return;
      }
      if (!alive) return;

      const backend = process.env.REACT_APP_BACKEND_URL || "";
      const wsUrl =
        backend.replace(/^http/, "ws") +
        `/api/ws/board/${projectId}` +
        (token ? `?token=${encodeURIComponent(token)}` : "");
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => alive && setConnected(true);
      ws.onclose = () => {
        if (!alive) return;
        setConnected(false);
        // Reconnect after 2s
        retry = setTimeout(open, 2000);
      };
      ws.onerror = () => {
        // onclose will fire and trigger retry
      };
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "presence") {
            setPresence(msg.users || []);
          } else if (msg.type === "task.created") {
            handlersRef.current.onTaskCreated?.(msg.task, msg.by);
          } else if (msg.type === "task.updated") {
            handlersRef.current.onTaskUpdated?.(msg.task, msg.by);
          } else if (msg.type === "task.deleted") {
            handlersRef.current.onTaskDeleted?.(msg.task_id, msg.by);
          } else if (msg.type === "comment.created") {
            handlersRef.current.onCommentCreated?.(msg.task_id, msg.comment, msg.by);
          }
        } catch {}
      };
    };

    open();

    return () => {
      alive = false;
      if (retry) clearTimeout(retry);
      if (wsRef.current) wsRef.current.close();
    };
  }, [projectId]);

  return { presence, connected, send };
}
