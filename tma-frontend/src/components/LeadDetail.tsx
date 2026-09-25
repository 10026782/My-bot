import { useEffect, useRef, useState } from "react";
import {
  askAI,
  createFollowup,
  createLeadTask,
  fetchLead,
  patchLead,
  setLeadOutcome,
} from "../api";
import type { LeadDetail as TLeadDetail, LeadSummary } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

interface Props {
  lead: LeadSummary;
  onBack: () => void;
  authRole?: string | null;
}

type LoadState =
  | { status: "loading" }
  | { status: "ok"; data: TLeadDetail }
  | { status: "error"; message: string };

type Toast = { type: "ok" | "err"; text: string };

type WorkflowStage = "new" | "followup" | "qualified" | "task" | "closed";

interface OutcomeOption {
  key: string;
  label: string;
  terminal: boolean;
}

const SCORE_CHIP_CLASS: Record<string, string> = {
  red: "lead-detail-score-chip--red",
  yellow: "lead-detail-score-chip--yellow",
  blue: "lead-detail-score-chip--blue",
};

// Owner-only quick temperature buttons — one-tap Score presets instead of
// typing a raw number. Values chosen to land inside the existing 3-bucket
// Pipeline scale (tma_api.py::_pipeline_temperature: <25 קר / 25-59 חם / ≥60 חם מאוד).
const QUICK_SCORE_PRESETS: { key: string; label: string; value: number }[] = [
  { key: "cold", label: "קר", value: 10 },
  { key: "warm", label: "הגיב למודעה", value: 30 },
  { key: "hot", label: "שוחח וחיובי", value: 70 },
];

const OUTCOMES: OutcomeOption[] = [
  { key: "open", label: "פתוח", terminal: false },
  { key: "needs_followup", label: "צריך פולואפ", terminal: false },
  { key: "meeting_scheduled", label: "פגישה נקבעה", terminal: false },
  { key: "converted", label: "הומר", terminal: true },
  { key: "not_relevant", label: "לא רלוונטי", terminal: true },
  { key: "lost", label: "אבוד", terminal: true },
  { key: "duplicate", label: "כפול", terminal: true },
  { key: "archived", label: "בארכיון", terminal: true },
];

const STAGE_LABELS: Record<WorkflowStage, string> = {
  new: "New Lead",
  followup: "Followup",
  qualified: "Qualified",
  task: "Task / Meeting",
  closed: "Closed / Archived",
};

const STAGES: WorkflowStage[] = ["new", "followup", "qualified", "task", "closed"];

const TERMINAL_STATUSES = new Set(["done", "archived", "lost", "duplicate", "not_relevant"]);
const TERMINAL_OUTCOMES = new Set(OUTCOMES.filter((o) => o.terminal).map((o) => o.key));

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="lead-detail-section-header">
      <p className="boss-eyebrow">{title}</p>
      {sub && <p className="lead-detail-section-sub">{sub}</p>}
    </div>
  );
}

function normalizeOutcome(value?: string) {
  return (value ?? "").trim().toLowerCase();
}

function isTerminalLead(data: TLeadDetail, outcome: string) {
  return TERMINAL_OUTCOMES.has(outcome) || TERMINAL_STATUSES.has((data.status ?? "").toLowerCase());
}

function deriveStage(data: TLeadDetail, outcome: string): WorkflowStage {
  if (isTerminalLead(data, outcome)) return "closed";
  if (outcome === "meeting_scheduled") return "task";
  if ((data.next_step ?? "") === "Create Deal") return "task";
  if ((data.status ?? "").toLowerCase() === "high_confidence" || data.score >= 70) return "qualified";
  if (outcome === "needs_followup" || Boolean(data.next_followup)) return "followup";
  return "new";
}

function outcomeLabel(outcome: string) {
  return OUTCOMES.find((o) => o.key === outcome)?.label ?? "פתוח";
}

function readableOwner(owner?: string | string[]) {
  if (!owner) return "";
  const raw = Array.isArray(owner) ? owner.join(", ") : owner;
  return raw.replace(/\brec[a-zA-Z0-9]+\b/g, "אחראי משויך");
}

function readableHistory(text: string) {
  return (text || "")
    .replace(/\brec[a-zA-Z0-9]+\b/g, "רשומה")
    .replace(/\[[^\]]*rec[a-zA-Z0-9]+[^\]]*\]/g, "עדכון מערכת");
}

function formatError(e: unknown, fallback: string) {
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

function ScoreChip({ score, color, size }: { score: number; color: string; size: "sm" | "lg" }) {
  return (
    <div className={`lead-detail-score-chip lead-detail-score-chip--${size} ${SCORE_CHIP_CLASS[color] ?? ""}`}>
      {score}
    </div>
  );
}

export function LeadDetail({ lead, onBack, authRole }: Props) {
  const isOwner = authRole === "owner";

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [toast, setToast] = useState<Toast | null>(null);
  const [saving, setSaving] = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const historyRef = useRef<HTMLDivElement>(null);

  const [currentOutcome, setCurrentOutcome] = useState("");
  const [nextFollowup, setNextFollowup] = useState("");
  const [scheduleDirty, setScheduleDirty] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [scoreInput, setScoreInput] = useState("");
  const [scoreDirty, setScoreDirty] = useState(false);
  const [nextActionBusy, setNextActionBusy] = useState(false);
  const [nextActionPending, setNextActionPending] = useState(false);

  const [taskOpen, setTaskOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDue, setTaskDue] = useState("");
  const [taskNotes, setTaskNotes] = useState("");
  const [taskBusy, setTaskBusy] = useState(false);

  const [note, setNote] = useState("");
  const [noteBusy, setNoteBusy] = useState(false);

  const [aiOpen, setAiOpen] = useState(false);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiAnswer, setAiAnswer] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const aiInputRef = useRef<HTMLInputElement>(null);

  const load = () => {
    setState({ status: "loading" });
    fetchLead(lead.id)
      .then((data) => {
        setState({ status: "ok", data });
        setCurrentOutcome(normalizeOutcome(data.outcome) || "open");
        setNextFollowup(data.next_followup ?? "");
        setScoreInput(String(data.score));
      })
      .catch((e: unknown) => setState({ status: "error", message: formatError(e, "טעינת הליד נכשלה") }));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id]);

  useEffect(() => {
    if (aiOpen) setTimeout(() => aiInputRef.current?.focus(), 100);
  }, [aiOpen]);

  function showToast(type: "ok" | "err", text: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, text });
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }

  function updateLoadedData(patch: Partial<TLeadDetail>) {
    setState((prev) => {
      if (prev.status !== "ok") return prev;
      return { status: "ok", data: { ...prev.data, ...patch } };
    });
  }

  async function handleOutcome(outcome: string) {
    if (saving || outcome === currentOutcome) return;
    const prevOutcome = currentOutcome;
    setCurrentOutcome(outcome);
    setSaving(true);
    try {
      await setLeadOutcome(lead.id, outcome);
      updateLoadedData({ outcome });
      showToast("ok", `תוצאה עסקית: ${outcomeLabel(outcome)}`);
    } catch (e) {
      setCurrentOutcome(prevOutcome);
      showToast("err", formatError(e, "עדכון התוצאה נכשל"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSetFollowup() {
    if (saving) return;
    setSaving(true);
    try {
      const fields: Parameters<typeof patchLead>[1] = {};
      if (nextFollowup) fields.next_followup = nextFollowup;
      await setLeadOutcome(lead.id, "needs_followup");
      if (Object.keys(fields).length > 0) await patchLead(lead.id, fields);
      setCurrentOutcome("needs_followup");
      setScheduleDirty(false);
      updateLoadedData({ outcome: "needs_followup", next_followup: nextFollowup });
      showToast("ok", "הליד הועבר לפולואפ");
    } catch (e) {
      showToast("err", formatError(e, "שמירת הפולואפ נכשלה"));
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkQualified() {
    if (saving) return;
    setSaving(true);
    try {
      await patchLead(lead.id, { status: "high_confidence" });
      updateLoadedData({ status: "high_confidence" });
      showToast("ok", "הליד סומן כמתאים");
    } catch (e) {
      showToast("err", formatError(e, "סימון הליד כמתאים נכשל"));
    } finally {
      setSaving(false);
    }
  }

  async function handleMeetingBooked() {
    await handleOutcome("meeting_scheduled");
  }

  async function handleReopen() {
    if (saving) return;
    setSaving(true);
    try {
      // setLeadOutcome("open") already syncs status -> "active" server-side
      // (tma_api.py::_OUTCOME_STATUS_MAP) — a second patchLead({status})
      // call here was a redundant round-trip writing the same field twice.
      await setLeadOutcome(lead.id, "open");
      setCurrentOutcome("open");
      updateLoadedData({ outcome: "open", status: "active" });
      showToast("ok", "הליד נפתח מחדש");
    } catch (e) {
      showToast("err", formatError(e, "פתיחה מחדש נכשלה"));
    } finally {
      setSaving(false);
    }
  }

  async function handleQuickScore(value: number, label: string) {
    if (saving) return;
    setSaving(true);
    try {
      await patchLead(lead.id, { score: value });
      setScoreInput(String(value));
      setScoreDirty(false);
      updateLoadedData({ score: value });
      showToast("ok", `דרגת חום עודכנה: ${label}`);
    } catch (e) {
      showToast("err", formatError(e, "עדכון דרגת החום נכשל"));
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveScore() {
    if (saving || !scoreDirty) return;
    const parsed = parseInt(scoreInput, 10);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 100) {
      showToast("err", "ציון חייב להיות 0-100");
      return;
    }
    setSaving(true);
    try {
      await patchLead(lead.id, { score: parsed });
      setScoreDirty(false);
      updateLoadedData({ score: parsed });
      showToast("ok", `ציון עודכן: ${parsed}`);
    } catch (e) {
      showToast("err", formatError(e, "עדכון הציון נכשל"));
    } finally {
      setSaving(false);
    }
  }

  // PIPELINE-1 remediation item 4 — Next Action is now a real write through
  // the canonical PATCH route: UI -> patchLead -> ActionGateway
  // (executed for Owner / pending_approval for Manager) -> refetch. A
  // pending_approval result must NEVER be shown as if it already applied.
  async function handleNextActionChange(value: string) {
    if (nextActionBusy) return;
    setNextActionBusy(true);
    try {
      const result = await patchLead(lead.id, { next_step: value });
      if (result.status === "executed") {
        const fresh = await fetchLead(lead.id);
        setState({ status: "ok", data: fresh });
        setNextActionPending(false);
        showToast("ok", `Next Action עודכן: ${fresh.next_step_label || fresh.next_step}`);
      } else if (result.status === "pending_approval") {
        setNextActionPending(true);
        showToast("ok", "הבקשה נשלחה לאישור — טרם בוצעה");
      } else {
        showToast("err", "עדכון Next Action לא הושלם");
      }
    } catch (e) {
      showToast("err", formatError(e, "עדכון Next Action נכשל"));
    } finally {
      setNextActionBusy(false);
    }
  }

  async function handleCreateTask() {
    if (taskBusy || !taskTitle.trim()) return;
    setTaskBusy(true);
    try {
      await createLeadTask(lead.id, {
        title: taskTitle.trim(),
        due_date: taskDue || undefined,
        notes: taskNotes.trim() || undefined,
      });
      setTaskTitle("");
      setTaskDue("");
      setTaskNotes("");
      setTaskOpen(false);
      updateLoadedData({ next_step: "Create Deal", next_step_label: "ליצור עסקה" });
      showToast("ok", "משימה נוצרה");
    } catch (e) {
      showToast("err", formatError(e, "יצירת המשימה נכשלה"));
    } finally {
      setTaskBusy(false);
    }
  }

  async function handleFollowupNote() {
    if (noteBusy || !note.trim()) return;
    setNoteBusy(true);
    try {
      await createFollowup(lead.id, note.trim());
      setNote("");
      showToast("ok", "הערה נרשמה");
    } catch (e) {
      showToast("err", formatError(e, "רישום ההערה נכשל"));
    } finally {
      setNoteBusy(false);
    }
  }

  async function handleAskAI() {
    if (aiBusy || !aiQuestion.trim()) return;
    setAiBusy(true);
    setAiAnswer(null);
    try {
      const answer = await askAI(lead.id, aiQuestion.trim());
      setAiAnswer(answer);
      setAiQuestion("");
    } catch (e) {
      setAiAnswer(formatError(e, "שגיאה בשירות ה-AI"));
    } finally {
      setAiBusy(false);
    }
  }

  if (state.status === "loading") {
    return (
      <main className="ventures-screen lead-detail-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title={lead.name || "ליד ללא שם"} subtitle="CRM Workflow" />
          <ScreenState state="loading" title="טוען את פרטי הליד" message="אוסף את ההיסטוריה העדכנית…" />
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="ventures-screen lead-detail-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} eyebrow="BOSS" title={lead.name || "ליד ללא שם"} subtitle="CRM Workflow" />
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

  const data = state.data;
  const stage = deriveStage(data, currentOutcome);
  const terminal = isTerminalLead(data, currentOutcome);
  const ownerText = readableOwner(data.owner);
  const historyCount = data.timeline?.length ?? 0;
  const shellPaddingBottom = terminal ? 112 : taskOpen ? 320 : aiOpen ? 240 : 208;

  return (
    <main className="ventures-screen lead-detail-screen">
      {toast && (
        <p className={`ventures-toast${toast.type === "err" ? " ventures-toast--error" : ""}`} role="status">
          {toast.text}
        </p>
      )}

      <div className="ventures-shell" style={{ paddingBottom: shellPaddingBottom }}>
        <PageHeader
          onBack={onBack}
          eyebrow="BOSS"
          title={lead.name || "ליד ללא שם"}
          subtitle="CRM Workflow"
          action={<ScoreChip score={data.score} color={data.score_color} size="sm" />}
        />

        <div className="lead-detail-stack">
          <Surface className="lead-detail-stage-card">
            <div className="lead-detail-stage-card__top">
              <ScoreChip score={data.score} color={data.score_color} size="lg" />
              <div className="lead-detail-stage-card__body">
                <p className="lead-detail-hint">שלב נוכחי</p>
                <h2 className="lead-detail-stage-title">{STAGE_LABELS[stage]}</h2>
                <div className="lead-detail-meta-row">
                  <span className="boss-status-badge boss-status-badge--info">{outcomeLabel(currentOutcome)}</span>
                  {data.status && <span className="boss-status-badge boss-status-badge--neutral">טכני: {data.status}</span>}
                </div>
              </div>
            </div>
            <div className="lead-detail-stage-rail">
              {STAGES.map((s) => (
                <div key={s} className={`lead-detail-stage-rail__item${s === stage ? " lead-detail-stage-rail__item--active" : ""}`}>
                  {STAGE_LABELS[s]}
                </div>
              ))}
            </div>
          </Surface>

          {isOwner && (
            <Surface>
              <SectionHeader title="דרגת חום" sub="עדכון מהיר של הציון — קובע את הטמפרטורה והסינון בפייפליין" />
              <div className="lead-detail-outcome-row">
                {QUICK_SCORE_PRESETS.map((p) => (
                  <button
                    key={p.key}
                    type="button"
                    onClick={() => handleQuickScore(p.value, p.label)}
                    disabled={saving}
                    className="boss-button boss-button--quiet boss-bubble--action"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </Surface>
          )}

          <Surface padding="compact" className="lead-detail-meta-row">
            {data.domain && <span className="boss-status-badge boss-status-badge--info">{data.domain}</span>}
            {data.source && <span className="boss-status-badge boss-status-badge--neutral">מקור: {data.source}</span>}
            {ownerText && <span className="boss-status-badge boss-status-badge--neutral">אחראי: {ownerText}</span>}
            {data.phone && (
              <a href={`tel:${data.phone}`} className="boss-status-badge boss-status-badge--success" dir="ltr">
                {data.phone}
              </a>
            )}
            {data.created_at && <span className="lead-detail-meta-row__date">{data.created_at.slice(0, 10)}</span>}
          </Surface>

          <Surface>
            <SectionHeader
              title="Next Action"
              sub={nextActionPending ? "הבקשה נשלחה לאישור — טרם בוצעה" : "הפעולה הבאה לליד — נשמר דרך אותו מסלול אישורים כמו שאר עדכוני הליד"}
            />
            {data.next_step_options?.length ? (
              <select
                value={data.next_step || ""}
                onChange={(e) => handleNextActionChange(e.target.value)}
                disabled={nextActionBusy}
                className="boss-select"
              >
                <option value="" disabled>בחר/י פעולה הבאה</option>
                {data.next_step_options.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            ) : (
              <p className="lead-detail-plain-text">{data.next_step_label || "אין פעולה מומלצת"}</p>
            )}
            {nextActionPending && <p className="lead-detail-pending-note">ממתין לאישור Owner — הערך עדיין לא נכנס לתוקף</p>}
            {data.next_followup && <p className="lead-detail-hint">פולואפ הבא: {data.next_followup}</p>}
          </Surface>

          {!terminal && (
            <Surface>
              <SectionHeader title="הפעולה הבאה" sub="זרימה אחת: New → Followup → Qualified → Task/Meeting → Closed" />
              <div className="lead-detail-progress-stack">
                <div className="lead-detail-followup-row">
                  <input
                    type="date"
                    value={nextFollowup}
                    onChange={(e) => {
                      setNextFollowup(e.target.value);
                      setScheduleDirty(true);
                    }}
                    className="boss-input"
                  />
                  <button
                    type="button"
                    onClick={handleSetFollowup}
                    disabled={saving || (!scheduleDirty && currentOutcome === "needs_followup")}
                    className="boss-button boss-button--quiet boss-bubble--action"
                  >
                    פולואפ
                  </button>
                </div>
                <div className="lead-detail-action-grid">
                  <button type="button" onClick={handleMarkQualified} disabled={saving} className="boss-button boss-button--primary boss-bubble--action">
                    סמן כמתאים
                  </button>
                  <button type="button" onClick={handleMeetingBooked} disabled={saving} className="boss-button boss-button--primary boss-bubble--action">
                    פגישה נקבעה
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => setTaskOpen((o) => !o)}
                  aria-pressed={taskOpen}
                  className={`boss-button boss-bubble--action lead-detail-full-button ${taskOpen ? "boss-button--primary" : "boss-button--quiet"}`}
                >
                  {taskOpen ? "סגור יצירת משימה" : "צור משימה"}
                </button>
              </div>

              {taskOpen && (
                <Surface variant="subtle" padding="compact" className="lead-detail-task-form">
                  <input
                    type="text"
                    value={taskTitle}
                    onChange={(e) => setTaskTitle(e.target.value)}
                    placeholder="כותרת משימה *"
                    className="boss-input"
                    autoFocus
                  />
                  <div className="lead-detail-task-form-row">
                    <input
                      type="date"
                      value={taskDue}
                      onChange={(e) => setTaskDue(e.target.value)}
                      className="boss-input"
                    />
                    <input
                      type="text"
                      value={taskNotes}
                      onChange={(e) => setTaskNotes(e.target.value)}
                      placeholder="הערות"
                      className="boss-input"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleCreateTask}
                    disabled={taskBusy || !taskTitle.trim()}
                    className="boss-button boss-button--primary boss-bubble--action lead-detail-full-button"
                  >
                    {taskBusy ? "יוצר..." : "צור משימה"}
                  </button>
                </Surface>
              )}
            </Surface>
          )}

          {terminal && (
            <Surface>
              <SectionHeader title="ליד סגור" sub="פעולות מכירה מוסתרות כדי למנוע מצב סותר" />
              <p className="lead-detail-plain-text">הליד נמצא בסטטוס סופי: {outcomeLabel(currentOutcome)}.</p>
              <div className="lead-detail-action-grid">
                <button
                  type="button"
                  onClick={() => historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  className="boss-button boss-button--quiet boss-bubble--action"
                >
                  הצג היסטוריה
                </button>
                {isOwner && (
                  <button type="button" onClick={handleReopen} disabled={saving} className="boss-button boss-button--primary boss-bubble--action">
                    פתח מחדש
                  </button>
                )}
              </div>
            </Surface>
          )}

          {!terminal && (
            <Surface>
              <SectionHeader title="סגירת ליד" sub="Business Outcome הוא מקור האמת העסקי" />
              <div className="lead-detail-outcome-row">
                {OUTCOMES.filter((o) => o.terminal).map((opt) => (
                  <button
                    key={opt.key}
                    type="button"
                    onClick={() => handleOutcome(opt.key)}
                    disabled={saving}
                    className="ventures-choice boss-bubble--selectable"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </Surface>
          )}

          {data.summary && (
            <Surface>
              <p className="lead-detail-hint">סיכום</p>
              <p className="lead-detail-summary-text">{data.summary}</p>
            </Surface>
          )}

          {aiAnswer && (
            <div className="lead-detail-ai-panel">
              <p className="lead-detail-ai-panel__label">BOSS AI</p>
              <p className="lead-detail-ai-panel__text">{aiAnswer}</p>
            </div>
          )}

          <div ref={historyRef}>
            <Surface>
              <p className="lead-detail-hint" style={{ marginBottom: "var(--boss-space-3)" }}>היסטוריה</p>
              {historyCount === 0 ? (
                <p className="lead-detail-plain-text">אין היסטוריה להצגה.</p>
              ) : (
                <div className="lead-detail-timeline">
                  {data.timeline.map((entry, i) => (
                    <div key={i} className="lead-detail-timeline__row">
                      {entry.channel && <span className="lead-detail-timeline__channel">[{readableHistory(entry.channel)}]</span>}
                      <span className="lead-detail-timeline__text">{readableHistory(entry.summary)}</span>
                    </div>
                  ))}
                </div>
              )}
            </Surface>
          </div>

          {isOwner && (
            <Surface>
              <button type="button" onClick={() => setAdvancedOpen((o) => !o)} className="lead-detail-advanced-toggle">
                Advanced
              </button>
              {advancedOpen && (
                <div className="lead-detail-advanced-body">
                  <div>
                    <label className="lead-detail-advanced-label">Score override (0-100)</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={scoreInput}
                      onChange={(e) => {
                        setScoreInput(e.target.value);
                        setScoreDirty(true);
                      }}
                      className="boss-input"
                    />
                    <p className="lead-detail-advanced-hint">Tier הוא read-only ומחושב אוטומטית.</p>
                  </div>
                  <button type="button" onClick={handleSaveScore} disabled={saving || !scoreDirty} className="boss-button boss-button--primary boss-bubble--action">
                    שמור
                  </button>
                </div>
              )}
            </Surface>
          )}
        </div>
      </div>

      <div className="lead-detail-footer">
        {terminal ? (
          <div className="lead-detail-footer-actions">
            <button type="button" onClick={() => historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} className="boss-button boss-button--quiet boss-bubble--action">
              היסטוריה
            </button>
            {isOwner && (
              <button type="button" onClick={handleReopen} disabled={saving} className="boss-button boss-button--primary boss-bubble--action">
                פתח מחדש
              </button>
            )}
          </div>
        ) : (
          <>
            <p className="lead-detail-footer__hint">
              <strong>הערה</strong>
              <span> · </span>
              נרשמת כהיסטוריה בלבד, לא משנה סטטוס
            </p>
            <div className="lead-detail-footer-row">
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleFollowupNote()}
                placeholder="כתוב הערה..."
                className="boss-input"
              />
              <button type="button" onClick={handleFollowupNote} disabled={noteBusy || !note.trim()} className="boss-button boss-button--quiet boss-bubble--action">
                {noteBusy ? "..." : "שלח"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setAiOpen((o) => !o);
                  setAiAnswer(null);
                }}
                aria-pressed={aiOpen}
                className="boss-button boss-button--quiet boss-bubble--action"
                aria-label="Ask AI"
              >
                AI
              </button>
            </div>
            {aiOpen && (
              <div className="lead-detail-footer-row">
                <input
                  ref={aiInputRef}
                  type="text"
                  value={aiQuestion}
                  onChange={(e) => setAiQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAskAI()}
                  placeholder="שאל שאלה על הליד..."
                  className="boss-input"
                  disabled={aiBusy}
                />
                <button type="button" onClick={handleAskAI} disabled={aiBusy || !aiQuestion.trim()} className="boss-button boss-button--primary boss-bubble--action">
                  {aiBusy ? "..." : "שאל"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
