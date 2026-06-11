import { useEffect, useRef, useState } from "react";
import {
  fetchLead,
  patchLead,
  setLeadOutcome,
  createLeadTask,
  createFollowup,
  askAI,
} from "../api";
import type { LeadDetail as TLeadDetail, LeadSummary } from "../types";

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

// ─── Constants ────────────────────────────────────────────────────────────────

const SCORE_BG: Record<string, string> = {
  red:    "bg-red-500",
  yellow: "bg-yellow-400",
  blue:   "bg-blue-400",
};

// סטטוס עבודה — מצב הטיפול הנוכחי
const STATUS_CHIPS = [
  { key: "new",          label: "חדש" },
  { key: "active",       label: "פעיל" },
  { key: "waiting_call", label: "ממתין" },
  { key: "hot",          label: "🔥 חם" },
  { key: "done",         label: "סגור" },
];

// חום ליד — Tier
const TIER_OPTIONS = [
  { key: "COLD", label: "❄️ קר"   },
  { key: "WARM", label: "🌤 חמים" },
  { key: "HOT",  label: "🔥 חם"   },
];

// תוצאה עסקית — Business Outcome
interface OutcomeOption {
  key: string;
  label: string;
  color: string;
  bg: string;
  terminal: boolean;
}
const OUTCOME_OPTIONS: OutcomeOption[] = [
  { key: "OPEN",            label: "פתוח",        color: "#3b82f6", bg: "#eff6ff", terminal: false },
  { key: "FOLLOWUP_NEEDED", label: "צריך פולואפ", color: "#f59e0b", bg: "#fffbeb", terminal: false },
  { key: "MEETING_BOOKED",  label: "פגישה נקבעה", color: "#8b5cf6", bg: "#f5f3ff", terminal: false },
  { key: "CONVERTED",       label: "הומר ✓",       color: "#16a34a", bg: "#f0fdf4", terminal: true  },
  { key: "NOT_RELEVANT",    label: "לא רלוונטי",   color: "#6b7280", bg: "#f9fafb", terminal: true  },
  { key: "LOST",            label: "אבוד",         color: "#ef4444", bg: "#fef2f2", terminal: true  },
  { key: "DUPLICATE",       label: "כפיל",         color: "#9ca3af", bg: "#f9fafb", terminal: true  },
  { key: "ARCHIVED",        label: "בארכיון",      color: "#6b7280", bg: "#f9fafb", terminal: true  },
];

// פעולה הבאה — Next Action (saves to next_step field)
const NEXT_ACTION_OPTIONS = [
  { key: "call_now",           label: "📞 התקשר עכשיו" },
  { key: "call_today",         label: "📞 התקשר היום"  },
  { key: "schedule_this_week", label: "📅 תאם השבוע"   },
  { key: "send_details",       label: "📤 שלח פרטים"   },
  { key: "follow_up",          label: "🔄 פולואפ"       },
  { key: "waiting_response",   label: "⏳ ממתין לתגובה" },
  { key: "create_deal",        label: "🤝 צור עסקה"     },
  { key: "archive",            label: "📦 ארכב"          },
  { key: "none",               label: "— ללא"            },
];

// ─── Section header helper ────────────────────────────────────────────────────

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <p className="text-xs font-bold text-gray-700 uppercase tracking-wide">{title}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export function LeadDetail({ lead, onBack, authRole }: Props) {
  const isOwner = authRole === "owner";

  const [state,    setState]    = useState<LoadState>({ status: "loading" });
  const [toast,    setToast]    = useState<Toast | null>(null);
  const [saving,   setSaving]   = useState(false);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Optimistic state for each editable dimension
  const [currentStatus,    setCurrentStatus]    = useState(lead.status);
  const [currentOutcome,   setCurrentOutcome]   = useState("");
  const [currentTier,      setCurrentTier]      = useState("");
  const [currentAction,    setCurrentAction]    = useState("");  // next_step
  const [scoreInput,       setScoreInput]       = useState("");
  const [scoreDirty,       setScoreDirty]       = useState(false);
  const [nextFollowup,     setNextFollowup]     = useState("");
  const [owner,            setOwner]            = useState("");
  const [scheduleDirty,    setScheduleDirty]    = useState(false);

  // Create task form
  const [taskOpen,  setTaskOpen]  = useState(false);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDue,   setTaskDue]   = useState("");
  const [taskNotes, setTaskNotes] = useState("");
  const [taskBusy,  setTaskBusy]  = useState(false);

  // Follow-up note (log only)
  const [note,     setNote]     = useState("");
  const [noteBusy, setNoteBusy] = useState(false);

  // AI
  const [aiOpen,     setAiOpen]     = useState(false);
  const [aiQuestion, setAiQuestion] = useState("");
  const [aiAnswer,   setAiAnswer]   = useState<string | null>(null);
  const [aiBusy,     setAiBusy]     = useState(false);
  const aiInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchLead(lead.id)
      .then((data) => {
        setState({ status: "ok", data });
        setCurrentStatus(data.status);
        setCurrentOutcome(data.outcome ?? "");
        setCurrentTier(data.tier ?? "");
        setScoreInput(String(data.score));
        setCurrentAction(data.next_step ?? "");
        setNextFollowup(data.next_followup ?? "");
        setOwner(data.owner ?? "");
      })
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, [lead.id]);

  useEffect(() => {
    if (aiOpen) setTimeout(() => aiInputRef.current?.focus(), 100);
  }, [aiOpen]);

  function showToast(type: "ok" | "err", text: string) {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ type, text });
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }

  // ── סטטוס עבודה (autosave) ──────────────────────────────────────
  async function handleStatusChange(status: string) {
    if (saving || status === currentStatus) return;
    const prev = currentStatus;
    setCurrentStatus(status);
    setSaving(true);
    try {
      await patchLead(lead.id, { status });
      showToast("ok", `סטטוס: ${status}`);
    } catch {
      setCurrentStatus(prev);
      showToast("err", "עדכון סטטוס נכשל");
    } finally {
      setSaving(false);
    }
  }

  // ── תוצאה עסקית (autosave) ──────────────────────────────────────
  async function handleOutcome(outcome: string) {
    if (saving || outcome === currentOutcome) return;
    const prevOutcome = currentOutcome;
    const prevStatus  = currentStatus;
    const opt = OUTCOME_OPTIONS.find((o) => o.key === outcome);
    setCurrentOutcome(outcome);
    if (opt?.terminal) setCurrentStatus("done");
    setSaving(true);
    try {
      await setLeadOutcome(lead.id, outcome);
      showToast("ok", `תוצאה: ${opt?.label ?? outcome}`);
    } catch {
      setCurrentOutcome(prevOutcome);
      setCurrentStatus(prevStatus);
      showToast("err", "עדכון תוצאה נכשל");
    } finally {
      setSaving(false);
    }
  }

  // ── חום ליד — Tier (autosave) ───────────────────────────────────
  async function handleTierChange(tier: string) {
    if (saving || tier === currentTier) return;
    const prev = currentTier;
    setCurrentTier(tier);
    setSaving(true);
    try {
      await patchLead(lead.id, { tier });
      showToast("ok", `טייר: ${TIER_OPTIONS.find((t) => t.key === tier)?.label ?? tier}`);
    } catch {
      setCurrentTier(prev);
      showToast("err", "עדכון טייר נכשל");
    } finally {
      setSaving(false);
    }
  }

  // ── פעולה הבאה — Next Action (autosave) ─────────────────────────
  async function handleNextAction(key: string) {
    if (saving || key === currentAction) return;
    const prev = currentAction;
    setCurrentAction(key);
    setSaving(true);
    try {
      await patchLead(lead.id, { next_step: key });
      const label = NEXT_ACTION_OPTIONS.find((a) => a.key === key)?.label ?? key;
      showToast("ok", `פעולה: ${label}`);
    } catch {
      setCurrentAction(prev);
      showToast("err", "עדכון פעולה נכשל");
    } finally {
      setSaving(false);
    }
  }

  // ── ציון (owner, explicit save) ─────────────────────────────────
  async function handleSaveScore() {
    if (saving || !scoreDirty) return;
    const parsed = parseInt(scoreInput, 10);
    if (isNaN(parsed) || parsed < 0 || parsed > 100) {
      showToast("err", "ציון חייב להיות 0–100");
      return;
    }
    setSaving(true);
    try {
      await patchLead(lead.id, { score: parsed });
      setScoreDirty(false);
      showToast("ok", `ציון עודכן: ${parsed}`);
    } catch {
      showToast("err", "עדכון ציון נכשל");
    } finally {
      setSaving(false);
    }
  }

  // ── תזמון ואחראי (explicit save) ────────────────────────────────
  async function handleSaveSchedule() {
    if (saving || !scheduleDirty) return;
    setSaving(true);
    try {
      const fields: Parameters<typeof patchLead>[1] = {};
      if (nextFollowup) fields.next_followup = nextFollowup;
      if (owner)        fields.owner         = owner;
      if (Object.keys(fields).length === 0) { setSaving(false); return; }
      await patchLead(lead.id, fields);
      setScheduleDirty(false);
      showToast("ok", "נשמר ✓");
    } catch {
      showToast("err", "שמירה נכשלה");
    } finally {
      setSaving(false);
    }
  }

  // ── Create Task ──────────────────────────────────────────────────
  async function handleCreateTask() {
    if (taskBusy || !taskTitle.trim()) return;
    setTaskBusy(true);
    try {
      await createLeadTask(lead.id, {
        title:    taskTitle.trim(),
        due_date: taskDue || undefined,
        notes:    taskNotes.trim() || undefined,
      });
      setTaskTitle(""); setTaskDue(""); setTaskNotes("");
      setTaskOpen(false);
      showToast("ok", "משימה נוצרה ✓");
    } catch {
      showToast("err", "יצירת משימה נכשלה");
    } finally {
      setTaskBusy(false);
    }
  }

  // ── הוסף הערה (log only) ─────────────────────────────────────────
  async function handleFollowup() {
    if (noteBusy || !note.trim()) return;
    setNoteBusy(true);
    try {
      await createFollowup(lead.id, note.trim());
      setNote("");
      showToast("ok", "הערה נרשמה ✓");
    } catch {
      showToast("err", "רישום הערה נכשל");
    } finally {
      setNoteBusy(false);
    }
  }

  // ── AI ────────────────────────────────────────────────────────────
  async function handleAskAI() {
    if (aiBusy || !aiQuestion.trim()) return;
    setAiBusy(true);
    setAiAnswer(null);
    try {
      const answer = await askAI(lead.id, aiQuestion.trim());
      setAiAnswer(answer);
      setAiQuestion("");
    } catch {
      setAiAnswer("⚠️ שגיאה בשירות ה-AI");
    } finally {
      setAiBusy(false);
    }
  }

  const data = state.status === "ok" ? state.data : null;
  const activeOutcome = OUTCOME_OPTIONS.find((o) => o.key === currentOutcome);

  const pbClass = taskOpen ? "pb-80" : aiOpen ? "pb-60" : "pb-44";

  return (
    <div className={`min-h-screen bg-gray-100 ${pbClass}`} dir="rtl">

      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none" aria-label="חזרה">←</button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">{lead.name || "—"}</h1>
          <p className="text-xs text-gray-400">Lead Card</p>
        </div>
        {data && (
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-black text-lg flex-shrink-0 ${SCORE_BG[data.score_color] ?? "bg-gray-400"}`}>
            {data.score}
          </div>
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

      {data && (
        <div className="flex flex-col gap-3 px-4">

          {/* Meta row */}
          <div className="bg-white rounded-xl shadow-sm p-3 flex flex-wrap gap-2 items-center">
            {data.domain && (
              <span className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded-full font-medium">{data.domain}</span>
            )}
            {currentTier && (
              <span className="text-xs px-2 py-1 bg-orange-50 text-orange-600 rounded-full font-medium">
                {TIER_OPTIONS.find((t) => t.key === currentTier)?.label ?? currentTier}
              </span>
            )}
            {activeOutcome && (
              <span className="text-xs px-2 py-1 rounded-full font-medium" style={{ background: activeOutcome.bg, color: activeOutcome.color }}>
                {activeOutcome.label}
              </span>
            )}
            {data.source && (
              <span className="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">מקור: {data.source}</span>
            )}
            {data.phone && (
              <a href={`tel:${data.phone}`} className="text-xs px-2 py-1 bg-green-50 text-green-600 rounded-full font-medium" dir="ltr">
                📞 {data.phone}
              </a>
            )}
            {data.created_at && (
              <span className="text-xs text-gray-400 mr-auto">{data.created_at.slice(0, 10)}</span>
            )}
          </div>

          {/* ── תוצאה עסקית ──────────────────────────────────────── */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <SectionHeader title="תוצאה עסקית" sub="מה הסטטוס של הליד? — משנה את ה-outcome" />
            <div className="grid grid-cols-2 gap-2">
              {OUTCOME_OPTIONS.map((opt) => {
                const active = opt.key === currentOutcome;
                return (
                  <button
                    key={opt.key}
                    onClick={() => handleOutcome(opt.key)}
                    disabled={saving}
                    className="text-xs py-2 px-3 rounded-lg font-medium text-right transition-all active:scale-95 disabled:opacity-50"
                    style={{
                      background: active ? opt.color : opt.bg,
                      color:      active ? "#fff"    : opt.color,
                      border:     `1.5px solid ${active ? opt.color : "transparent"}`,
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
            {activeOutcome?.terminal && (
              <p className="text-xs text-gray-400 mt-2 text-center">סטטוס עבודה עודכן ל-סגור אוטומטית</p>
            )}
          </div>

          {/* ── חום ליד ──────────────────────────────────────────── */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <SectionHeader title="חום ליד" sub="עד כמה הליד חם — משנה את ה-tier" />
            <div className="flex gap-2 mb-3">
              {TIER_OPTIONS.map((t) => (
                <button
                  key={t.key}
                  onClick={() => handleTierChange(t.key)}
                  disabled={saving}
                  className={`flex-1 text-sm py-2.5 rounded-xl font-semibold transition-all disabled:opacity-50 active:scale-95 ${
                    currentTier === t.key
                      ? "bg-orange-400 text-white shadow"
                      : "bg-gray-100 text-gray-600 active:bg-gray-200"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {isOwner && (
              <div className="flex gap-2 items-end">
                <div className="flex-1">
                  <label className="text-xs text-gray-400 block mb-1">ציון AI (0–100)</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    value={scoreInput}
                    onChange={(e) => { setScoreInput(e.target.value); setScoreDirty(true); }}
                    className="w-full bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none"
                  />
                </div>
                {scoreDirty && (
                  <button
                    onClick={handleSaveScore}
                    disabled={saving}
                    className="bg-blue-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-80 whitespace-nowrap"
                  >
                    {saving ? "…" : "שמור ציון"}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* ── פעולה הבאה ───────────────────────────────────────── */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <SectionHeader title="פעולה הבאה" sub="מה עושים עכשיו? — משנה את next_step" />
            <div className="flex flex-wrap gap-2">
              {NEXT_ACTION_OPTIONS.map((a) => {
                const active = a.key === currentAction;
                return (
                  <button
                    key={a.key}
                    onClick={() => handleNextAction(a.key)}
                    disabled={saving}
                    className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all active:scale-95 disabled:opacity-50 ${
                      active
                        ? "bg-blue-500 text-white shadow"
                        : "bg-gray-100 text-gray-600 active:bg-gray-200"
                    }`}
                  >
                    {a.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── תזמון ואחראי ─────────────────────────────────────── */}
          <div className="bg-white rounded-xl shadow-sm p-4">
            <SectionHeader title="תזמון ואחראי" sub="מתי ומי — לא משנה outcome" />
            <div className="flex gap-3 mb-3">
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">פולואפ הבא</label>
                <input
                  type="date"
                  value={nextFollowup}
                  onChange={(e) => { setNextFollowup(e.target.value); setScheduleDirty(true); }}
                  className="w-full bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none"
                />
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-400 block mb-1">אחראי</label>
                <input
                  type="text"
                  value={owner}
                  onChange={(e) => { setOwner(e.target.value); setScheduleDirty(true); }}
                  placeholder="שם אחראי"
                  className="w-full bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none"
                />
              </div>
            </div>
            {scheduleDirty && (
              <button
                onClick={handleSaveSchedule}
                disabled={saving}
                className="w-full bg-blue-500 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40 active:opacity-80"
              >
                {saving ? "שומר…" : "שמור"}
              </button>
            )}
          </div>

          {/* Summary (read-only) */}
          {data.summary && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-1">סיכום</p>
              <p className="text-sm text-gray-800 leading-relaxed">{data.summary}</p>
            </div>
          )}

          {/* AI Answer */}
          {aiAnswer && (
            <div className="bg-purple-50 border border-purple-100 rounded-xl p-4">
              <p className="text-xs text-purple-400 mb-1">🤖 BOSS AI</p>
              <p className="text-sm text-purple-900 leading-relaxed whitespace-pre-wrap">{aiAnswer}</p>
            </div>
          )}

          {/* Timeline (read-only) */}
          {data.timeline.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-3">היסטוריה</p>
              <div className="flex flex-col gap-2">
                {data.timeline.map((entry, i) => (
                  <div key={i} className="flex gap-2 text-sm">
                    {entry.channel && <span className="text-gray-400 flex-shrink-0">[{entry.channel}]</span>}
                    <span className="text-gray-700">{entry.summary}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}

      {/* ── Fixed action bar ── */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-2.5 pb-4 flex flex-col gap-2 shadow-xl" dir="rtl">

        {/* Row 1 label */}
        <p className="text-xs text-gray-400">
          <span className="font-semibold text-gray-500">סטטוס עבודה</span>
          <span className="text-gray-300 mx-1">·</span>
          משנה את מצב הטיפול
        </p>

        {/* Status chips + task toggle */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar">
          {STATUS_CHIPS.map((chip) => {
            const active = chip.key === currentStatus;
            return (
              <button
                key={chip.key}
                onClick={() => handleStatusChange(chip.key)}
                disabled={saving}
                className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-all
                  ${active ? "bg-blue-500 text-white shadow" : "bg-gray-100 text-gray-600 active:bg-gray-200"}
                  ${saving ? "opacity-50" : ""}`}
              >
                {chip.label}
              </button>
            );
          })}
          <button
            onClick={() => setTaskOpen((o) => !o)}
            className={`flex-shrink-0 text-xs px-3 py-1.5 rounded-full font-medium transition-all
              ${taskOpen ? "bg-indigo-500 text-white" : "bg-gray-100 text-gray-600 active:bg-gray-200"}`}
          >
            + משימה
          </button>
        </div>

        {/* Create task form */}
        {taskOpen && (
          <div className="flex flex-col gap-2 bg-gray-50 rounded-xl p-3 border border-gray-200">
            <input
              type="text"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
              placeholder="כותרת המשימה *"
              className="bg-white rounded-lg px-3 py-2 text-sm outline-none border border-gray-200"
              autoFocus
            />
            <div className="flex gap-2">
              <input
                type="date"
                value={taskDue}
                onChange={(e) => setTaskDue(e.target.value)}
                className="flex-1 bg-white rounded-lg px-3 py-2 text-sm outline-none border border-gray-200"
              />
              <input
                type="text"
                value={taskNotes}
                onChange={(e) => setTaskNotes(e.target.value)}
                placeholder="הערות"
                className="flex-1 bg-white rounded-lg px-3 py-2 text-sm outline-none border border-gray-200"
              />
            </div>
            <button
              onClick={handleCreateTask}
              disabled={taskBusy || !taskTitle.trim()}
              className="w-full bg-indigo-500 text-white rounded-lg py-2 text-sm font-semibold disabled:opacity-40 active:opacity-80"
            >
              {taskBusy ? "יוצר…" : "צור משימה"}
            </button>
          </div>
        )}

        {/* Row 2 label */}
        <p className="text-xs text-gray-400">
          <span className="font-semibold text-gray-500">📝 הוסף הערה</span>
          <span className="text-gray-300 mx-1">·</span>
          נרשמת ב-Interaction Log בלבד — לא משנה סטטוס
        </p>

        {/* Note + AI row */}
        <div className="flex gap-2">
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFollowup()}
            placeholder="כתוב הערה..."
            className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
          />
          <button
            onClick={handleFollowup}
            disabled={noteBusy || !note.trim()}
            className="bg-gray-700 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70"
          >
            {noteBusy ? "…" : "שלח"}
          </button>
          <button
            onClick={() => { setAiOpen((o) => !o); setAiAnswer(null); }}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors
              ${aiOpen ? "bg-purple-500 text-white" : "bg-gray-100 text-gray-600 active:bg-gray-200"}`}
            aria-label="Ask AI"
          >
            🤖
          </button>
        </div>

        {/* AI input */}
        {aiOpen && (
          <div className="flex gap-2">
            <input
              ref={aiInputRef}
              type="text"
              value={aiQuestion}
              onChange={(e) => setAiQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAskAI()}
              placeholder="שאל שאלה על הליד..."
              className="flex-1 bg-purple-50 border border-purple-200 rounded-xl px-3 py-2 text-sm outline-none placeholder-purple-300"
              disabled={aiBusy}
            />
            <button
              onClick={handleAskAI}
              disabled={aiBusy || !aiQuestion.trim()}
              className="bg-purple-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70 min-w-[52px]"
            >
              {aiBusy ? "…" : "שאל"}
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
