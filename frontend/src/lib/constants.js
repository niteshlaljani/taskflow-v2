import { ChevronsDown, ChevronsUp, Equal, ArrowDown, ArrowUp } from "lucide-react";

export const STATUS_META = {
  backlog: { label: "Backlog", color: "#9ca3af", dotClass: "bg-neutral-400" },
  todo: { label: "To Do", color: "#6b7280", dotClass: "bg-neutral-500" },
  in_progress: { label: "In Progress", color: "#0055ff", dotClass: "bg-[#0055ff]" },
  done: { label: "Done", color: "#10b981", dotClass: "bg-emerald-500" },
};

export const STATUS_ORDER = ["backlog", "todo", "in_progress", "done"];

export const PRIORITY_META = {
  low: { label: "Low", icon: ChevronsDown, color: "text-neutral-400" },
  medium: { label: "Medium", icon: Equal, color: "text-neutral-500" },
  high: { label: "High", icon: ArrowUp, color: "text-orange-500" },
  urgent: { label: "Urgent", icon: ChevronsUp, color: "text-red-500" },
};

export function PriorityIcon({ priority, size = 14 }) {
  const meta = PRIORITY_META[priority] || PRIORITY_META.medium;
  const Icon = meta.icon;
  return <Icon size={size} className={meta.color} aria-label={meta.label} />;
}
