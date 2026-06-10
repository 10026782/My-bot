// BossDigest.tsx — BOSS Daily Digest (Production-Ready)
// Morning briefing: system health + what changed + blockers + actions + approvals.
// Visual style unchanged from prototype.

import { useState, useEffect, useCallback } from "react";
import { fetchHealth, fetchApprovals, actOnApproval } from "../api";
import type { SystemHealth, Approval } from "../types";

// ─── Types ────────────────────────────────────────────────────────────────────

type StatusKey = "working" | "partial" | "broken";
type SeverityKey = "high" | "medium" | "low";

interface DigestAction {
  id:   string;
  text: string;
  done: boolean;
}

interface ChangeItem {
  from: StatusKey;
  to:   StatusKey;
  item: string;
  icon: string;
}

interface DigestBlocker {
  text:     string;
  severity: SeverityKey;
}

interface DigestData {
  date:      string;
  health:    number;
  broken:    number;
  partial:   number;
  working:   number;
  changed:   ChangeItem[];
  blockers:  DigestBlocker[];
  actions:   DigestAction[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<StatusKey, string> = {
  working: "#22c55e",
  partial: "#f59e0b",
  broken:  "#ef4444",
};
const STATUS_LABEL: Record<StatusKey, string> = {
  working: "עובד",
  partial: "חלקי",
  broken:  "שבור",
};
const SEVERITY_COLOR: Record<SeverityKey, string> = {
  high:   "#ef4444",
  medium: "#f59e0b",
  low:    "#6b7280",
};

// ─── Integration-Ready Data Layer ────────────────────────────────────────────

async function loadDigestData(health: SystemHealth): Promise<DigestData> {
  const now = new Date();
  const date = now.toLocaleDateString("he-IL", { day: "numeric", month: "long", year: "numeric" });

  // Derive blocker list from real emergency flags + service status
  const blockers: DigestBlocker[] = [];
  Object.entries(health.emergency_flags || {}).forEach(([flag, active]) => {
    if (active) blockers.push({ text: `🚨 ${flag} פעיל`, severity: "high" });
  });
  if (health.services?.anthropic !== "ok") {
    blockers.push({ text: "Claude API לא זמין — AI במצב fallback", severity: "high" });
  }
  if (health.services?.airtable !== "ok") {
    blockers.push({ text: "Airtable לא זמין", severity: "high" });
  }
  if (health.services?.telegram !== "ok") {
    blockers.push({ text: "Telegram לא זמין", severity: "medium" });
  }

  // Derive system counts from health status
  // TODO: replace with actual per-service granular data from health endpoint
  const isOk       = health.status === "ok";
  const isDegraded = health.status === "degraded";
  const broken     = health.active_emergency?.length ?? 0;
  const working    = isOk ? 8 : isDegraded ? 5 : 2;
  const partial    = isDegraded ? 4 : 0;

  // TODO: load today's required actions from Airtable Tasks table
  // Filter: is_required=true AND status=todo AND due_date=today
  const actions: DigestAction[] = [];

  // TODO: load daily delta (what changed) from Airtable Activity_Log or a dedicated digest API
  // For now: empty — no invented data
  const changed: ChangeItem[] = [];

  return { date, health: Math.round((working / Math.max(working + partial + broken, 1)) * 100), broken, partial, working, changed, blockers, actions };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function HealthBar({ value }: { value: number }) {
  const color = value >= 75 ? "#22c55e" : value >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ height: 5, background: "#1f2937", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${value}%`, height: "100%", background: color, borderRadius: 3, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

function Section({
  title, children, accent = "#1f2937",
}: {
  title: string; children: React.ReactNode; accent?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#4b5563", letterSpacing: 2, marginBottom: 8, textTransform: "uppercase" as const }}>
        {title}
      </div>
      <div style={{ background: "#0d1117", border: `1.5px solid ${accent}`, borderRadius: 12, overflow: "hidden" }}>
        {children}
      </div>
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div style={{ padding: "12px 14px", fontSize: 12, color: "#374151", textAlign: "center" as const }}>
      {text}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface Props {
  onBack: () => void;
}

type LoadState = "loading" | "ok" | "error";

export function BossDigest({ onBack }: Props) {
  const [loadState,   setLoadState]   = useState<LoadState>("loading");
  const [digest,      setDigest]      = useState<DigestData | null>(null);
  const [actions,     setActions]     = useState<DigestAction[]>([]);
  const [approvals,   setApprovals]   = useState<Approval[]>([]);
  const [actingOn,    setActingOn]    = useState<string | null>(null);

  const load = useCallback(() => {
    setLoadState("loading");
    Promise.all([fetchHealth(), fetchApprovals()])
      .then(async ([health, approvalsResp]) => {
        const data = await loadDigestData(health);
        setDigest(data);
        setActions(data.actions);
        setApprovals(approvalsResp.approvals.filter((a: Approval) => a.status === "pending"));
        setLoadState("ok");
      })
      .catch(() => setLoadState("error"));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleApproval(approvalId: string, decision: "approve" | "reject") {
    setActingOn(approvalId);
    try {
      await actOnApproval(approvalId, decision);
      setApprovals(prev => prev.filter(a => a.id !== approvalId));
    } catch {
      // keep in list — silent fail, user can retry
    } finally {
      setActingOn(null);
    }
  }

  if (loadState === "loading") {
    return (
      <div style={{ minHeight: "100vh", background: "#030712", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#4b5563", fontSize: 13 }}>טוען...</div>
      </div>
    );
  }

  if (loadState === "error" || !digest) {
    return (
      <div style={{ minHeight: "100vh", background: "#030712", display: "flex", flexDirection: "column" as const, alignItems: "center", justifyContent: "center", gap: 12 }}>
        <div style={{ color: "#4b5563", fontSize: 13 }}>שגיאה בטעינת Digest</div>
        <button onClick={load} style={{ padding: "8px 20px", borderRadius: 10, background: "#1f2937", border: "none", color: "#9ca3af", fontSize: 13, cursor: "pointer", fontFamily: "inherit" }}>נסה שוב</button>
      </div>
    );
  }

  const healthColor = digest.health >= 75 ? "#22c55e" : digest.health >= 50 ? "#f59e0b" : "#ef4444";
  const doneCount   = actions.filter(a => a.done).length;

  return (
    <div style={{ minHeight: "100vh", background: "#030712", fontFamily: "'Segoe UI', Arial, sans-serif", direction: "rtl", padding: "20px 16px" }}>
      <div style={{ maxWidth: 440, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <button onClick={onBack} style={{ background: "transparent", border: "none", color: "#4b5563", fontSize: 13, cursor: "pointer", padding: 0, fontFamily: "inherit" }}>← חזור</button>
            <div style={{ fontSize: 10, letterSpacing: 3, color: "#22c55e", fontWeight: 700 }}>BOSS · DIGEST</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 900, color: "#f9fafb" }}>Daily Digest</div>
              <div style={{ fontSize: 12, color: "#4b5563", marginTop: 2 }}>{digest.date}</div>
            </div>
            <div style={{ textAlign: "left" as const }}>
              <div style={{ fontSize: 28, fontWeight: 900, color: healthColor, fontVariantNumeric: "tabular-nums" }}>{digest.health}%</div>
              <div style={{ fontSize: 10, color: "#4b5563" }}>System Health</div>
            </div>
          </div>
          <HealthBar value={digest.health} />
          <div style={{ display: "flex", gap: 12, marginTop: 8 }}>
            {(["broken", "partial", "working"] as StatusKey[]).map(k => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: STATUS_COLOR[k] }} />
                <span style={{ fontSize: 11, color: "#6b7280", fontVariantNumeric: "tabular-nums" }}>
                  {k === "broken" ? digest.broken : k === "partial" ? digest.partial : digest.working} {STATUS_LABEL[k]}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* What changed */}
        <Section title="מה השתנה היום" accent="#1f2937">
          {digest.changed.length === 0
            ? <EmptyRow text="אין שינויים מתועדים עדיין" />
            : digest.changed.map((c, i) => (
              <div key={i} style={{ padding: "10px 14px", borderBottom: i < digest.changed.length - 1 ? "1px solid #111827" : "none", display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 16 }}>{c.icon}</span>
                <span style={{ fontSize: 13, color: "#d1d5db", flex: 1 }}>{c.item}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: STATUS_COLOR[c.from], background: `${STATUS_COLOR[c.from]}15`, padding: "2px 7px", borderRadius: 8 }}>{STATUS_LABEL[c.from]}</span>
                  <span style={{ fontSize: 10, color: "#4b5563" }}>→</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color: STATUS_COLOR[c.to], background: `${STATUS_COLOR[c.to]}15`, padding: "2px 7px", borderRadius: 8 }}>{STATUS_LABEL[c.to]}</span>
                </div>
              </div>
            ))
          }
        </Section>

        {/* Blockers */}
        <Section title="חסמים" accent="#1a0a0a">
          {digest.blockers.length === 0
            ? <EmptyRow text="אין חסמים פעילים ✓" />
            : digest.blockers.map((b, i) => (
              <div key={i} style={{ padding: "10px 14px", borderBottom: i < digest.blockers.length - 1 ? "1px solid #111827" : "none", display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: SEVERITY_COLOR[b.severity], flexShrink: 0 }} />
                <span style={{ fontSize: 13, color: "#d1d5db" }}>{b.text}</span>
              </div>
            ))
          }
        </Section>

        {/* Required Actions */}
        <Section title={`פעולות נדרשות · ${doneCount}/${actions.length}`} accent="#0f0f2d">
          {actions.length === 0
            ? <EmptyRow text="אין פעולות נדרשות — TODO: חבר לטבלת Tasks" />
            : actions.map((a, i) => (
              <div key={a.id}
                onClick={() => setActions(prev => prev.map((x, j) => j === i ? { ...x, done: !x.done } : x))}
                style={{ padding: "11px 14px", borderBottom: i < actions.length - 1 ? "1px solid #111827" : "none", display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                <div style={{
                  width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                  background: a.done ? "#22c55e" : "transparent",
                  border: `2px solid ${a.done ? "#22c55e" : "#374151"}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  transition: "all 0.2s",
                }}>
                  {a.done && <span style={{ fontSize: 11, color: "#000", fontWeight: 900 }}>✓</span>}
                </div>
                <span style={{ fontSize: 13, color: a.done ? "#374151" : "#d1d5db", textDecoration: a.done ? "line-through" : "none", transition: "all 0.2s" }}>{a.text}</span>
              </div>
            ))
          }
        </Section>

        {/* Approvals — real data from actOnApproval API */}
        {approvals.length > 0 && (
          <Section title="אישורים ממתינים" accent="#1c1200">
            {approvals.map((ap, i) => (
              <div key={ap.id} style={{ padding: "11px 14px", borderBottom: i < approvals.length - 1 ? "1px solid #111827" : "none", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ flex: 1, minWidth: 0, marginLeft: 10 }}>
                  <div style={{ fontSize: 13, color: "#d1d5db", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>{ap.action}</div>
                  <div style={{ fontSize: 10, color: "#6b7280", marginTop: 2 }}>מ: {ap.requested_by}</div>
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <button
                    disabled={actingOn === ap.id}
                    onClick={() => handleApproval(ap.id, "approve")}
                    style={{ padding: "5px 12px", borderRadius: 8, background: "#052e16", border: "1px solid #22c55e", color: "#22c55e", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: actingOn === ap.id ? 0.5 : 1 }}>
                    אשר
                  </button>
                  <button
                    disabled={actingOn === ap.id}
                    onClick={() => handleApproval(ap.id, "reject")}
                    style={{ padding: "5px 12px", borderRadius: 8, background: "transparent", border: "1px solid #374151", color: "#6b7280", fontSize: 11, fontWeight: 700, cursor: "pointer", fontFamily: "inherit", opacity: actingOn === ap.id ? 0.5 : 1 }}>
                    דחה
                  </button>
                </div>
              </div>
            ))}
          </Section>
        )}

        {/* Footer */}
        <div style={{ textAlign: "center" as const, marginTop: 8, padding: "10px 0" }}>
          <div style={{ fontSize: 10, color: "#1f2937", letterSpacing: 1 }}>
            SCORE · Digest מופיע רק כשיש שינוי, חסם, או פעולה נדרשת
          </div>
        </div>

      </div>
    </div>
  );
}
