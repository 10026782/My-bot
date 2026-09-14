import type { LeadSummary } from "../types";

// Canonical Pipeline score->color comes from the API (lead.score_color),
// derived once server-side in tma_api.py::_pipeline_temperature — no local
// threshold logic here (PIPELINE-1 remediation item 1).
const SCORE_COLOR_CLASS: Record<string, string> = {
  red:    "text-red-500",
  yellow: "text-yellow-500",
  blue:   "text-gray-400",
};

const STATUS_BADGE: Record<string, string> = {
  hot:          "bg-red-100 text-red-700",
  active:       "bg-green-100 text-green-700",
  new:          "bg-blue-100 text-blue-700",
  waiting_call: "bg-yellow-100 text-yellow-700",
};

function badgeClass(status: string) {
  return STATUS_BADGE[status.toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

export function LeadCard({ lead, onClick }: { lead: LeadSummary; onClick?: () => void }) {
  return (
    <div
      className="bg-white rounded-xl shadow-sm p-4 flex items-center justify-between gap-3 active:opacity-70 cursor-pointer"
      onClick={onClick}
    >
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-gray-900 truncate">{lead.name || "—"}</p>
        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
          <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass(lead.status)}`}>
            {lead.status}
          </span>
          {lead.temperature && (
            <span className="inline-block text-xs px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-500">
              {lead.temperature}
            </span>
          )}
        </div>
        {lead.next_step_label && (
          <p className="text-xs text-gray-400 mt-1 truncate">▸ {lead.next_step_label}</p>
        )}
      </div>
      <div className="flex-shrink-0 text-center">
        <p className={`text-2xl font-black ${SCORE_COLOR_CLASS[lead.score_color] ?? "text-gray-400"}`}>{lead.score}</p>
        <p className="text-[10px] text-gray-400">ציון</p>
      </div>
    </div>
  );
}
