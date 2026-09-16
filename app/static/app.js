// Shared helpers used across pages

const STATUS_STYLES = {
  "Open": "bg-brand-50 text-brand-700 border-brand-100",
  "In Progress": "bg-amber-50 text-amber-600 border-amber-100",
  "Closed": "bg-sand-100 text-sand-600 border-sand-200",
};

const PRIORITY_STYLES = {
  "Urgent": "bg-red-50 text-red-700",
  "High": "bg-amber-50 text-amber-600",
  "Normal": "bg-brand-50 text-brand-600",
  "Low": "bg-sand-100 text-sand-600",
};

function statusBadge(status) {
  const cls = STATUS_STYLES[status] || "bg-gray-100 text-gray-700 border-gray-200";
  return `<span class="inline-block px-2.5 py-1 rounded-full text-xs font-medium border ${cls}">${status}</span>`;
}

function priorityBadge(priority) {
  const cls = PRIORITY_STYLES[priority] || "bg-slate-100 text-slate-600";
  return `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}">${priority}</span>`;
}

function formatDate(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function isStale(iso, status) {
  if (status === "Closed") return false;
  const created = new Date(iso).getTime();
  const twoDaysMs = 2 * 24 * 60 * 60 * 1000;
  return Date.now() - created > twoDaysMs;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
