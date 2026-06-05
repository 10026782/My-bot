import { useEffect, useState } from "react";
import { fetchLead } from "../api";
import type { LeadDetail as TLeadDetail, LeadSummary } from "../types";

interface Props {
  lead: LeadSummary;
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: TLeadDetail }
  | { status: "error"; message: string };

const SCORE_BG: Record<string, string> = {
  red:    "bg-red-500",
  yellow: "bg-yellow-400",
  blue:   "bg-blue-400",
};

const STATUS_BADGE: Record<string, string> = {
  hot:            "bg-red-100 text-red-700",
  active:         "bg-green-100 text-green-700",
  new:            "bg-blue-100 text-blue-700",
  waiting_call:   "bg-yellow-100 text-yellow-700",
  high_confidence:"bg-purple-100 text-purple-700",
};

function badgeClass(status: string) {
  return STATUS_BADGE[status.toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

export function LeadDetail({ lead, onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchLead(lead.id)
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [lead.id]);

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-blue-500 text-xl font-medium leading-none"
          aria-label="חזרה"
        >
          ←
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">{lead.name || "—"}</h1>
          <p className="text-xs text-gray-400">Lead Card</p>
        </div>
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {state.status === "ok" && (() => {
        const d = state.data;
        return (
          <div className="flex flex-col gap-3 px-4">
            {/* Score + Status */}
            <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-4">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center text-white font-black text-xl flex-shrink-0 ${SCORE_BG[d.score_color] ?? "bg-gray-400"}`}>
                {d.score}
              </div>
              <div>
                <span className={`inline-block text-sm px-2 py-0.5 rounded-full font-medium ${badgeClass(d.status)}`}>
                  {d.status}
                </span>
                {d.source && <p className="text-xs text-gray-400 mt-1">מקור: {d.source}</p>}
              </div>
            </div>

            {/* Contact */}
            {d.phone && (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <p className="text-xs text-gray-400 mb-1">טלפון</p>
                <a
                  href={`tel:${d.phone}`}
                  className="text-blue-600 font-semibold text-base"
                  dir="ltr"
                >
                  {d.phone}
                </a>
              </div>
            )}

            {/* Summary */}
            {d.summary && (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <p className="text-xs text-gray-400 mb-1">סיכום</p>
                <p className="text-sm text-gray-800 leading-relaxed">{d.summary}</p>
              </div>
            )}

            {/* Next step */}
            {d.next_step && (
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
                <p className="text-xs text-blue-400 mb-1">צעד הבא</p>
                <p className="text-sm text-blue-800 font-medium">{d.next_step}</p>
              </div>
            )}

            {/* Timeline */}
            {d.timeline.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm p-4">
                <p className="text-xs text-gray-400 mb-3">היסטוריה</p>
                <div className="flex flex-col gap-2">
                  {d.timeline.map((entry, i) => (
                    <div key={i} className="flex gap-2 text-sm">
                      {entry.channel && (
                        <span className="text-gray-400 flex-shrink-0">[{entry.channel}]</span>
                      )}
                      <span className="text-gray-700">{entry.summary}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })()}
    </div>
  );
}
