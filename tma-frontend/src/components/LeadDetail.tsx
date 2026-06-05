import { useEffect, useRef, useState } from "react";
import { fetchLead, updateLeadStatus, createFollowup } from "../api";
import type { LeadDetail as TLeadDetail, LeadSummary } from "../types";

interface Props {
  lead: LeadSummary;
  onBack: () => void;
}

type LoadState =
  | { status: "loading" }
  | { status: "ok"; data: TLeadDetail }
  | { status: "error"; message: string };

type Toast = { type: "ok" | "err"; text: string };

const SCORE_BG: Record<string, string> = {
  red:    "bg-red-500",
  yellow: "bg-yellow-400",
  blue:   "bg-blue-400",
};

const STATUS_BADGE: Record<string, string> = {
  hot:             "bg-red-100 text-red-700",
  active:          "bg-green-100 text-green-700",
  new:             "bg-blue-100 text-blue-700",
  waiting_call:    "bg-yellow-100 text-yellow-700",
  high_confidence: "bg-purple-100 text-purple-700",
  done:            "bg-gray-100 text-gray-500",
};

const STATUS_CHIPS = [
  { key: "new",          label: "חדש" },
  { key: "active",       label: "פעיל" },
  { key: "waiting_call", label: "ממתין" },
  { key: "hot",          label: "🔥 חם" },
  { key: "done",         label: "סגור" },
];

function badgeClass(status: string) {
  return STATUS_BADGE[status.toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

export function LeadDetail({ lead, onBack }: Props) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [currentStatus, setCurrentStatus] = useState(lead.status);
  const [statusBusy, setStatusBusy] = useState(false);
  const [note, setNote] = useState("");
  const [noteBusy, setNoteBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetchLead(lead.id)
      .then((data) => {
        setState({ status: "ok", data });
        setCurrentStatus(data.status);
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [lead.id]);

  function showToast(type: "ok" | "err", text: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, text });
    toastTimer.current = setTimeout(() => setToast(null), 2500);
  }

  async function handleStatusChange(status: string) {
    if (statusBusy || status === currentStatus) return;
    setStatusBusy(true);
    try {
      await updateLeadStatus(lead.id, status);
      setCurrentStatus(status);
      showToast("ok", `סטטוס עודכן: ${status}`);
    } catch {
      showToast("err", "עדכון סטטוס נכשל");
    } finally {
      setStatusBusy(false);
    }
  }

  async function handleFollowup() {
    if (noteBusy || !note.trim()) return;
    setNoteBusy(true);
    try {
      await createFollowup(lead.id, note.trim());
      setNote("");
      showToast("ok", "משימת מעקב נוצרה ✓");
    } catch {
      showToast("err", "יצירת מעקב נכשלה");
    } finally {
      setNoteBusy(false);
    }
  }

  const data = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-32">
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

      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 left-4 right-4 z-50 rounded-xl px-4 py-3 text-sm font-medium shadow-lg text-center transition-all
          ${toast.type === "ok" ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
          {toast.text}
        </div>
      )}

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

      {data && (
        <div className="flex flex-col gap-3 px-4">
          {/* Score + Status */}
          <div className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-4">
            <div className={`w-14 h-14 rounded-full flex items-center justify-center text-white font-black text-xl flex-shrink-0 ${SCORE_BG[data.score_color] ?? "bg-gray-400"}`}>
              {data.score}
            </div>
            <div>
              <span className={`inline-block text-sm px-2 py-0.5 rounded-full font-medium ${badgeClass(currentStatus)}`}>
                {currentStatus}
              </span>
              {data.source && <p className="text-xs text-gray-400 mt-1">מקור: {data.source}</p>}
            </div>
          </div>

          {/* Contact */}
          {data.phone && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-1">טלפון</p>
              <a href={`tel:${data.phone}`} className="text-blue-600 font-semibold text-base" dir="ltr">
                {data.phone}
              </a>
            </div>
          )}

          {/* Summary */}
          {data.summary && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-1">סיכום</p>
              <p className="text-sm text-gray-800 leading-relaxed">{data.summary}</p>
            </div>
          )}

          {/* Next step */}
          {data.next_step && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
              <p className="text-xs text-blue-400 mb-1">צעד הבא</p>
              <p className="text-sm text-blue-800 font-medium">{data.next_step}</p>
            </div>
          )}

          {/* Timeline */}
          {data.timeline.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-3">היסטוריה</p>
              <div className="flex flex-col gap-2">
                {data.timeline.map((entry, i) => (
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
      )}

      {/* ── Action bar (fixed bottom) ── */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-3 pb-safe pb-4 flex flex-col gap-3 shadow-xl">
        {/* Status chips */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar">
          {STATUS_CHIPS.map((chip) => {
            const active = chip.key === currentStatus;
            return (
              <button
                key={chip.key}
                onClick={() => handleStatusChange(chip.key)}
                disabled={statusBusy}
                className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-all
                  ${active
                    ? "bg-blue-500 text-white shadow"
                    : "bg-gray-100 text-gray-600 active:bg-gray-200"
                  } ${statusBusy ? "opacity-50" : ""}`}
              >
                {chip.label}
              </button>
            );
          })}
        </div>

        {/* Follow-up input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFollowup()}
            placeholder="הוסף מעקב..."
            className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
            dir="rtl"
          />
          <button
            onClick={handleFollowup}
            disabled={noteBusy || !note.trim()}
            className="bg-blue-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70"
          >
            {noteBusy ? "…" : "שלח"}
          </button>
        </div>
      </div>
    </div>
  );
}
