import { useEffect, useState } from "react";
import { Paperclip, X, Upload, FileText } from "lucide-react";
import { api, formatApiError } from "@/lib/api";

export default function TaskAttachments({ taskId, currentUserId }) {
  const [items, setItems] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const reload = async () => {
    try {
      const { data } = await api.get(`/tasks/${taskId}/attachments`);
      setItems(data);
    } catch {}
  };

  useEffect(() => {
    if (!taskId) return;
    setItems([]);
    setError("");
    reload();
  }, [taskId]);

  const onPick = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      // 1. Ask backend for signed params
      const { data: sig } = await api.get("/cloudinary/signature", {
        params: { folder: "taskflow/attachments", resource_type: "auto" },
      });
      // 2. Upload directly to Cloudinary
      const form = new FormData();
      form.append("file", file);
      form.append("api_key", sig.api_key);
      form.append("timestamp", sig.timestamp);
      form.append("signature", sig.signature);
      form.append("folder", sig.folder);
      // Use /auto/ endpoint so images, videos, and raw files all work via one URL
      const url = `https://api.cloudinary.com/v1_1/${sig.cloud_name}/auto/upload`;
      const res = await fetch(url, { method: "POST", body: form });
      const json = await res.json();
      if (!res.ok || json.error) throw new Error(json?.error?.message || "Upload failed");
      // 3. Save metadata to backend
      const { data } = await api.post(`/tasks/${taskId}/attachments`, {
        public_id: json.public_id,
        secure_url: json.secure_url,
        resource_type: json.resource_type || "image",
        format: json.format,
        bytes: json.bytes,
        original_filename: json.original_filename || file.name,
      });
      setItems((p) => [data, ...p]);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async (att) => {
    if (!window.confirm("Delete this attachment?")) return;
    try {
      await api.delete(`/attachments/${att.attachment_id}`);
      setItems((p) => p.filter((x) => x.attachment_id !== att.attachment_id));
    } catch (e) {
      alert(formatApiError(e));
    }
  };

  return (
    <div data-testid="task-attachments">
      <div className="text-[11px] font-mono uppercase tracking-wider text-neutral-500 mb-2 flex items-center gap-2">
        Attachments
      </div>
      {items.length === 0 ? (
        <div className="text-sm text-neutral-400 mb-2">No attachments yet.</div>
      ) : (
        <ul className="space-y-2 mb-3">
          {items.map((a) => (
            <li
              key={a.attachment_id}
              className="flex items-center gap-3 rounded-md border border-[var(--tf-border)] p-2 group"
              data-testid={`attachment-row-${a.attachment_id}`}
            >
              {a.resource_type === "image" ? (
                <img src={a.secure_url} alt="" className="w-10 h-10 rounded object-cover" />
              ) : (
                <div className="w-10 h-10 rounded bg-neutral-100 grid place-items-center">
                  <FileText size={16} className="text-neutral-500" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <a
                  href={a.secure_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-neutral-900 hover:text-[#0055ff] truncate block"
                >
                  {a.original_filename || a.public_id.split("/").pop()}
                </a>
                <div className="text-[11px] font-mono text-neutral-400">
                  {a.format ? a.format.toUpperCase() : a.resource_type}
                  {a.bytes ? ` · ${formatBytes(a.bytes)}` : ""}
                </div>
              </div>
              {(a.uploader_id === currentUserId) && (
                <button
                  onClick={() => onDelete(a)}
                  className="p-1.5 text-neutral-400 hover:text-red-600 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition"
                  aria-label="Delete attachment"
                  data-testid={`attachment-delete-${a.attachment_id}`}
                >
                  <X size={14} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <label className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border border-dashed border-[var(--tf-border)] hover:border-[#0055ff] hover:bg-[#0055ff]/5 transition cursor-pointer">
        <Upload size={13} />
        {uploading ? "Uploading…" : "Attach a file"}
        <input
          type="file"
          className="hidden"
          onChange={onPick}
          disabled={uploading}
          data-testid="attachment-file-input"
        />
      </label>
      {error && (
        <div className="text-[11px] text-red-600 font-mono mt-2" data-testid="attachment-error">{error}</div>
      )}
    </div>
  );
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
