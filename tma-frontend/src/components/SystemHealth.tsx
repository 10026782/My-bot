import { useEffect, useState } from "react";
import { fetchHealth, emergencyStop, emergencyClear, EmergencyClearConflictError } from "../api";
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
  { action: "stop_ai",         label: "🛑 עצור AI",         color: "bg-orange-500 active:bg-orange-600" },
];

const FLAG_LABELS: Record<string, string> = {
  EMERGENCY_STOP_ALL:        "כל הפעולות",
  EMERGENCY_STOP_WHATSAPP:   "WhatsApp",
  EMERGENCY_STOP_EMAIL:      "Email",
  EMERGENCY_STOP_AUTOMATION: "Automation",
  EMERGENCY_STOP_AI:         "AI",
};

// flag name -> clear_* action, mirrors tma_api.py's _EMERGENCY_FLAG_SUFFIXES
const CLEAR_ACTIONS: Record<string, string> = {
  EMERGENCY_STOP_ALL:        "clear_all",
  EMERGENCY_STOP_WHATSAPP:   "clear_whatsapp",
  EMERGENCY_STOP_EMAIL:      "clear_email",
  EMERGENCY_STOP_AUTOMATION: "clear_automation",
  EMERGENCY_STOP_AI:         "clear_ai",
};

export function SystemHealth({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [acting, setActing] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [clearingFlag, setClearingFlag] = useState<string | null>(null);
  const [clearConfirm, setClearConfirm] = useState<string | null>(null);
  const [conflictNotice, setConflictNotice] = useState<string | null>(null);

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

  async function doClear(flag: string, operationId: string | null) {
    setClearConfirm(null);
    if (!operationId) {
      // Nothing to condition the clear on — the health payload never gave
      // us an operation_id for this flag (shouldn't happen for a flag
      // reported as active, but fail safe rather than send a clear the
      // backend would reject anyway). Refresh and let the user retry.
      setConflictNotice("לא נמצא מזהה עדכני לדגל זה — מרענן ומנסה שוב.");
      load();
      return;
    }
    setClearingFlag(flag);
    setConflictNotice(null);
    try {
      await emergencyClear(CLEAR_ACTIONS[flag], operationId);
      load();
    } catch (e) {
      if (e instanceof EmergencyClearConflictError) {
        // The flag's operation_id moved since this screen loaded — someone
        // (or something, e.g. cost_monitor) changed it in between. Never
        // silently overwrite; refresh and tell the user plainly.
        setConflictNotice("המצב השתנה מאז טעינת המסך. רענן ונסה שוב.");
        load();
      } else {
        alert(`שגיאה: ${String(e)}`);
      }
    } finally {
      setClearingFlag(null);
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

            {/* Conflict notice — a clear was rejected because the flag's
                state moved since this screen was loaded (HTTP 409) */}
            {conflictNotice && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-xs text-yellow-700 font-medium">
                {conflictNotice}
              </div>
            )}

            {/* Active Emergency Flags — each with its own Clear button.
                Clearing is durable (Airtable-backed) and requires the
                flag's current operation_id (optimistic concurrency) — a
                Render restart does NOT clear a durable flag. */}
            {data.active_emergency.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <p className="text-sm font-bold text-red-700 mb-2">🚨 דגלי חירום פעילים</p>
                <div className="flex flex-col gap-2">
                  {data.active_emergency.map((f) => {
                    const operationId = data.emergency_flags[f]?.operation_id ?? null;
                    return (
                      <div key={f} className="flex items-center justify-between gap-2">
                        <p className="text-xs text-red-600 font-medium">{FLAG_LABELS[f] ?? f}</p>
                        {clearConfirm === f ? (
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => doClear(f, operationId)}
                              disabled={!!clearingFlag}
                              className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-green-600 active:bg-green-700 disabled:opacity-50"
                            >
                              {clearingFlag === f ? "מבטל..." : "אשר ביטול"}
                            </button>
                            <button
                              onClick={() => setClearConfirm(null)}
                              className="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-600 bg-gray-100"
                            >
                              חזור
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setClearConfirm(f)}
                            disabled={!!clearingFlag}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold text-white bg-green-600 active:bg-green-700 disabled:opacity-40"
                          >
                            ✅ בטל עצירת {FLAG_LABELS[f] ?? f}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
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
