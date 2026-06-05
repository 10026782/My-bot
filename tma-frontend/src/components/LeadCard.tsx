import type { LeadSummary } from "../types";

const SCORE_COLOR = (s: number) =>
  s >= 70 ? "text-red-500" : s >= 40 ? "text-yellow-500" : "text-gray-400";

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
        <span className={`mt-1 inline-block text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass(lead.status)}`}>
          {lead.status}
        </span>
      </div>
      <div className="flex-shrink-0 text-center">
        <p className={`text-2xl font-black ${SCORE_COLOR(lead.score)}`}>{lead.score}</p>
        <p className="text-[10px] text-gray-400">ציון</p>
      </div>
    </div>
  );
}
