import { useEffect, useState } from "react";
import { fetchHealth, emergencyStop } from "../api";
import type { SystemHealth as TSystemHealth } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: TSystemHealth }
  | { status: "error"; message: string };

function serviceIcon(val: string) {
  if (val.startsWith("ok")) return "🟢";
  if (val.startsWith("error")) return "🔴";
  return "🟡";
}

function serviceLabel(val: string) {
  if (val.startsWith("ok:")) return val.slice(3);
  if (val === "ok") return "תקין";
  if (val.startsWith("error:")) return val.slice(6);
  return val;
}

const EMERGENCY_ACTIONS: { action: string; label: string; color: string }[] = [
  { action: "stop_all",        label: "🛑 עצור הכל",        color: "bg-red-600 active:bg-red-700" },
  { action: "stop_whatsapp",   label: "🛑 עצור WhatsApp",   color: "bg-orange-500 active:bg-orange-600" },
  { action: "stop_email",      label: "🛑 עצור Email",      color: "bg-orange-500 active:bg-orange-600" },
  { action: "stop_automation", label: "🛑 עצור Automation", color: "bg-orange-500 active:bg-orange-600" },
];

const FLAG_LABELS: Record<string, string> = {
  EMERGENCY_STOP_ALL:        "כל הפעולות",
  EMERGENCY_STOP_WHATSAPP:   "WhatsApp",
  EMERGENCY_STOP_EMAIL:      "Email",
  EMERGENCY_STOP_AUTOMATION: "Automation",
};

export function SystemHealth({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [acting, setActing] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);

  function load() {
    setState({ status: "loading" });
    fetchHealth()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }

  useEffect(() => { load(); }, []);

  async function doEmergency(action: string) {
    setConfirm(null);
    setActing(action);
    try {
      await emergencyStop(action);
      load();
    } catch (e) {
      alert(`שגיאה: ${String(e)}`);
    } finally {
      setActing(null);
    }
  }

  const statusBanner = state.status === "ok"
    ? state.data.status === "ok"        ? { bg: "bg-green-50  border-green-200",  text: "text-green-700",  label: "✅ כל המערכות תקינות" }
    : state.data.status === "emergency" ? { bg: "bg-red-50    border-red-300",     text: "text-red-700",    label: "🚨 חירום פעיל" }
    :                                     { bg: "bg-yellow-50  border-yellow-200",  text: "text-yellow-700", label: "⚠️ שירות מושבת חלקית" }
    : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none" aria-label="חזרה">←</button>
        <div>
          <h1 className="text-lg font-black text-gray-900">System Health</h1>
          <p className="text-xs text-gray-400">בריאות המערכת</p>
        </div>
        <button onClick={load} className="mr-auto text-gray-400 text-sm active:text-gray-600">רענן</button>
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{state.message}</div>
      )}

      {state.status === "ok" && (() => {
        const { data } = state;
        return (
          <div className="flex flex-col gap-3 px-4">

            {/* Status Banner */}
            {statusBanner && (
              <div className={`rounded-xl border p-4 ${statusBanner.bg}`}>
                <p className={`text-base font-bold ${statusBanner.text}`}>{statusBanner.label}</p>
                <p className="text-xs text-gray-400 mt-0.5">נבדק: {data.checked_at}</p>
              </div>
            )}

            {/* Services */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">שירותים</p>
              {Object.entries(data.services).map(([svc, val]) => (
                <div key={svc} className="flex items-center justify-between py-2.5 border-b border-gray-50 last:border-0">
                  <span className="text-sm font-medium text-gray-700 capitalize">{svc}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs text-gray-500">{serviceLabel(val)}</span>
                    <span className="text-base">{serviceIcon(val)}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Active Emergency Flags */}
            {data.active_emergency.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <p className="text-sm font-bold text-red-700 mb-2">🚨 דגלי חירום פעילים</p>
                {data.active_emergency.map((f) => (
                  <p key={f} className="text-xs text-red-600 font-medium">{FLAG_LABELS[f] ?? f}</p>
                ))}
                <p className="text-xs text-red-400 mt-2">לביטול: הפעל מחדש את השרת ב-Render</p>
              </div>
            )}

            {/* Emergency Stop */}
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wide">עצירת חירום</p>
              <div className="flex flex-col gap-2">
                {EMERGENCY_ACTIONS.map(({ action, label, color }) => (
                  confirm === action ? (
                    <div key={action} className="flex gap-2">
                      <button
                        onClick={() => doEmergency(action)}
                        disabled={!!acting}
                        className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-red-600 active:bg-red-700 disabled:opacity-50"
                      >
                        {acting === action ? "מבצע..." : "אשר עצירה"}
                      </button>
                      <button
                        onClick={() => setConfirm(null)}
                        className="flex-1 py-2.5 rounded-xl text-sm font-medium text-gray-600 bg-gray-100"
                      >
                        ביטול
                      </button>
                    </div>
                  ) : (
                    <button
                      key={action}
                      onClick={() => setConfirm(action)}
                      disabled={!!acting}
                      className={`w-full py-2.5 rounded-xl text-sm font-bold text-white ${color} disabled:opacity-40`}
                    >
                      {label}
                    </button>
                  )
                ))}
              </div>
            </div>

          </div>
        );
      })()}
    </div>
  );
}
