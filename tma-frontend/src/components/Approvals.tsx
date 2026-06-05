import { useEffect, useState } from "react";
import { fetchApprovals, actOnApproval, bulkApprove } from "../api";
import type { Approval, ApprovalsResponse } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: ApprovalsResponse }
  | { status: "error"; message: string };

type Toast = { type: "ok" | "err"; text: string };

// Risk level config — Hebrew field values
const RISK: Record<string, { label: string; icon: string; color: string }> = {
  גבוה:   { label: "גבוה",   icon: "🔴", color: "bg-red-100 text-red-700" },
  בינוני: { label: "בינוני", icon: "🟡", color: "bg-yellow-100 text-yellow-700" },
  נמוך:   { label: "נמוך",   icon: "🟢", color: "bg-green-100 text-green-700" },
};

function riskInfo(level: string) {
  return RISK[level] ?? { label: level || "—", icon: "⚪", color: "bg-gray-100 text-gray-500" };
}

function relativeTime(ts: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.slice(0, 10);
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `לפני ${mins} דקות`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `לפני ${hrs} שעות`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "אתמול" : `לפני ${days} ימים`;
}

function ApprovalCard({
  approval,
  onAction,
  busy,
}: {
  approval: Approval;
  onAction: (id: string, action: "approve" | "reject") => void;
  busy: string | null;
}) {
  const risk = riskInfo(approval.risk_level);
  const isBusy = busy === approval.id;

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 flex flex-col gap-3">
      {/* Action + risk */}
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-semibold text-gray-900 flex-1 leading-snug">
          {approval.action || "—"}
        </p>
        <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${risk.color}`}>
          {risk.icon} {risk.label}
        </span>
      </div>

      {/* Meta */}
      <div className="text-xs text-gray-400 flex gap-3">
        {approval.requested_by && <span>👤 {approval.requested_by}</span>}
        {approval.requested_at && <span>{relativeTime(approval.requested_at)}</span>}
        {approval.context_type && <span>📎 {approval.context_type}</span>}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onAction(approval.id, "approve")}
          disabled={isBusy}
          className="flex-1 py-2 bg-green-500 text-white rounded-xl text-sm font-medium active:opacity-70 disabled:opacity-40"
        >
          {isBusy ? "…" : "✅ אשר"}
        </button>
        <button
          onClick={() => onAction(approval.id, "reject")}
          disabled={isBusy}
          className="flex-1 py-2 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium active:opacity-70 disabled:opacity-40"
        >
          {isBusy ? "…" : "❌ דחה"}
        </button>
      </div>
    </div>
  );
}

export function Approvals({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [busy, setBusy] = useState<string | null>(null);   // approval_id in flight
  const [bulkBusy, setBulkBusy] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);

  function load() {
    setState({ status: "loading" });
    fetchApprovals()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => { load(); }, []);

  function showToast(type: "ok" | "err", text: string) {
    setToast({ type, text });
    setTimeout(() => setToast(null), 2500);
  }

  async function handleAction(id: string, action: "approve" | "reject") {
    setBusy(id);
    try {
      await actOnApproval(id, action);
      showToast("ok", action === "approve" ? "✅ אושר" : "❌ נדחה");
      // Remove from list without reload
      setState((prev) => {
        if (prev.status !== "ok") return prev;
        const filtered = prev.data.approvals.filter((a) => a.id !== id);
        return { status: "ok", data: { count: filtered.length, approvals: filtered } };
      });
    } catch {
      showToast("err", "פעולה נכשלה");
    } finally {
      setBusy(null);
    }
  }

  async function handleBulk() {
    setBulkBusy(true);
    try {
      const result = await bulkApprove();
      showToast("ok", `✅ אושרו ${result.approved} פעולות Low Risk`);
      load();
    } catch {
      showToast("err", "אישור מרוכז נכשל");
    } finally {
      setBulkBusy(false);
    }
  }

  const lowRiskCount =
    state.status === "ok"
      ? state.data.approvals.filter((a) => a.risk_level === "נמוך").length
      : 0;

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
        <div className="flex-1">
          <h1 className="text-lg font-black text-gray-900">אישורים</h1>
          <p className="text-xs text-gray-400">
            {state.status === "ok" ? `${state.data.count} ממתינים` : "Approvals"}
          </p>
        </div>
        {lowRiskCount > 0 && (
          <button
            onClick={handleBulk}
            disabled={bulkBusy}
            className="text-xs bg-green-50 text-green-700 border border-green-200 px-3 py-1.5 rounded-full font-medium active:opacity-70 disabled:opacity-40"
          >
            {bulkBusy ? "…" : `🟢 אשר הכל (${lowRiskCount})`}
          </button>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 left-4 right-4 z-50 rounded-xl px-4 py-3 text-sm font-medium shadow-lg text-center
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

      {state.status === "ok" && (
        <div className="flex flex-col gap-2 px-4">
          {state.data.approvals.length === 0 ? (
            <div className="text-center pt-16">
              <p className="text-4xl mb-3">✅</p>
              <p className="text-gray-400 text-sm">אין אישורים ממתינים</p>
            </div>
          ) : (
            state.data.approvals.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                onAction={handleAction}
                busy={busy}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
