import { useEffect, useState } from "react";
import { fetchHealth, emergencyStop, emergencyClear, EmergencyClearConflictError } from "../api";
import type { SystemHealth as TSystemHealth } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

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

const EMERGENCY_ACTIONS: { action: string; label: string; strong: boolean }[] = [
  { action: "stop_all",        label: "🛑 עצור הכל",        strong: true },
  { action: "stop_whatsapp",   label: "🛑 עצור WhatsApp",   strong: false },
  { action: "stop_email",      label: "🛑 עצור Email",      strong: false },
  { action: "stop_automation", label: "🛑 עצור Automation", strong: false },
  { action: "stop_ai",         label: "🛑 עצור AI",         strong: false },
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

  if (state.status === "loading") {
    return (
      <main className="ventures-screen system-health-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="System Health" subtitle="בריאות המערכת" />
          <ScreenState state="loading" title="בודק את מצב המערכת" message="אוסף את הנתונים העדכניים…" />
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="ventures-screen system-health-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title="System Health" subtitle="בריאות המערכת" />
          <ScreenState
            state="error"
            title="לא הצלחנו לטעון"
            message={state.message}
            action={
              <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>
                נסו שוב
              </button>
            }
          />
        </div>
      </main>
    );
  }

  const { data } = state;
  const bannerTone = data.status === "ok" ? "success" : data.status === "emergency" ? "danger" : "warning";
  const bannerLabel = data.status === "ok" ? "✅ כל המערכות תקינות" : data.status === "emergency" ? "🚨 חירום פעיל" : "⚠️ שירות מושבת חלקית";

  return (
    <main className="ventures-screen system-health-screen">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          eyebrow="BOSS"
          title="System Health"
          subtitle="בריאות המערכת"
          action={
            <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>
              רענן
            </button>
          }
        />

        <div className="system-health-stack">
          <div className={`system-health-banner system-health-banner--${bannerTone}`}>
            <p className="system-health-banner__title">{bannerLabel}</p>
            <p className="system-health-banner__meta">נבדק: {data.checked_at}</p>
          </div>

          <Surface>
            <p className="system-health-section-heading">שירותים</p>
            {Object.entries(data.services).map(([svc, val]) => (
              <div key={svc} className="system-health-service-row">
                <span className="system-health-service-name">{svc}</span>
                <span className="system-health-service-value">
                  <span className="system-health-service-label">{serviceLabel(val)}</span>
                  <span>{serviceIcon(val)}</span>
                </span>
              </div>
            ))}
          </Surface>

          {/* Conflict notice — a clear was rejected because the flag's
              state moved since this screen was loaded (HTTP 409) */}
          {conflictNotice && (
            <div className="system-health-banner system-health-banner--warning">
              <p className="system-health-banner__meta system-health-banner__meta--emphasis">{conflictNotice}</p>
            </div>
          )}

          {/* Active Emergency Flags — each with its own Clear button.
              Clearing is durable (Airtable-backed) and requires the
              flag's current operation_id (optimistic concurrency) — a
              Render restart does NOT clear a durable flag. */}
          {data.active_emergency.length > 0 && (
            <div className="system-health-banner system-health-banner--danger">
              <p className="system-health-banner__title system-health-banner__title--small">🚨 דגלי חירום פעילים</p>
              <div className="system-health-flag-list">
                {data.active_emergency.map((f) => {
                  const operationId = data.emergency_flags[f]?.operation_id ?? null;
                  return (
                    <div key={f} className="system-health-flag-row">
                      <p className="system-health-flag-label">{FLAG_LABELS[f] ?? f}</p>
                      {clearConfirm === f ? (
                        <div className="system-health-flag-actions">
                          <button
                            type="button"
                            onClick={() => doClear(f, operationId)}
                            disabled={!!clearingFlag}
                            className="boss-button boss-button--success boss-bubble--action"
                          >
                            {clearingFlag === f ? "מבטל..." : "אשר ביטול"}
                          </button>
                          <button
                            type="button"
                            onClick={() => setClearConfirm(null)}
                            className="boss-button boss-button--quiet boss-bubble--action"
                          >
                            חזור
                          </button>
                        </div>
                      ) : (
                        <div className="system-health-flag-actions">
                          <button
                            type="button"
                            onClick={() => setClearConfirm(f)}
                            disabled={!!clearingFlag}
                            className="boss-button boss-button--success boss-bubble--action"
                          >
                            ✅ בטל עצירת {FLAG_LABELS[f] ?? f}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Emergency Stop */}
          <Surface>
            <p className="system-health-section-heading">עצירת חירום</p>
            <div className="system-health-actions">
              {EMERGENCY_ACTIONS.map(({ action, label, strong }) => (
                confirm === action ? (
                  <div key={action} className="system-health-confirm-row">
                    <button
                      type="button"
                      onClick={() => doEmergency(action)}
                      disabled={!!acting}
                      className="boss-button boss-button--danger-strong boss-bubble--action"
                    >
                      {acting === action ? "מבצע..." : "אשר עצירה"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirm(null)}
                      className="boss-button boss-button--quiet boss-bubble--action"
                    >
                      ביטול
                    </button>
                  </div>
                ) : (
                  <button
                    key={action}
                    type="button"
                    onClick={() => setConfirm(action)}
                    disabled={!!acting}
                    className={`boss-button boss-bubble--action system-health-full-button ${strong ? "boss-button--danger-strong" : "boss-button--danger"}`}
                  >
                    {label}
                  </button>
                )
              ))}
            </div>
          </Surface>
        </div>
      </div>
    </main>
  );
}
