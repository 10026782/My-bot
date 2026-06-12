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

const SCORE_BG: Record<string, string> = {
  red: "bg-red-500",
  yellow: "bg-yellow-400",
  blue: "bg-blue-400",
};

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

const NEXT_ACTION_LABELS: Record<string, string> = {
  call_now: "להתקשר עכשיו",
  call_today: "להתקשר היום",
  schedule_this_week: "לתאם השבוע",
  send_details: "לשלוח פרטים",
  follow_up: "פולואפ",
  waiting_response: "ממתין לתגובה",
  create_deal: "ליצור עסקה",
  archive: "לארכב",
  none: "אין פעולה מומלצת",
};

const TERMINAL_STATUSES = new Set(["done", "archived", "lost", "duplicate", "not_relevant"]);
const TERMINAL_OUTCOMES = new Set(OUTCOMES.filter((o) => o.terminal).map((o) => o.key));

function SectionHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <p className="text-xs font-bold text-gray-700 uppercase tracking-wide">{title}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
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
  if ((data.next_step ?? "") === "create_deal") return "task";
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

  useEffect(() => {
    fetchLead(lead.id)
      .then((data) => {
        setState({ status: "ok", data });
        setCurrentOutcome(normalizeOutcome(data.outcome) || "open");
        setNextFollowup(data.next_followup ?? "");
        setScoreInput(String(data.score));
      })
      .catch((e: unknown) => setState({ status: "error", message: formatError(e, "טעינת הליד נכשלה") }));
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
      await setLeadOutcome(lead.id, "open");
      await patchLead(lead.id, { status: "active" });
      setCurrentOutcome("open");
      updateLoadedData({ outcome: "open", status: "active" });
      showToast("ok", "הליד נפתח מחדש");
    } catch (e) {
      showToast("err", formatError(e, "פתיחה מחדש נכשלה"));
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
      updateLoadedData({ next_step: "create_deal" });
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

  const data = state.status === "ok" ? state.data : null;
  const stage = data ? deriveStage(data, currentOutcome) : "new";
  const terminal = data ? isTerminalLead(data, currentOutcome) : false;
  const nextAction = data?.next_step ? NEXT_ACTION_LABELS[data.next_step] ?? data.next_step : "אין פעולה מומלצת";
  const ownerText = readableOwner(data?.owner);
  const historyCount = data?.timeline?.length ?? 0;
  const pbClass = terminal ? "pb-28" : taskOpen ? "pb-80" : aiOpen ? "pb-60" : "pb-52";

  return (
    <div className={`min-h-screen bg-gray-100 ${pbClass}`} dir="rtl">
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button onClick={onBack} className="text-blue-500 text-xl font-medium leading-none" aria-label="חזרה">
          ←
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-black text-gray-900 truncate">{lead.name || "ליד ללא שם"}</h1>
          <p className="text-xs text-gray-400">CRM Workflow</p>
        </div>
        {data && (
          <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-black text-lg flex-shrink-0 ${SCORE_BG[data.score_color] ?? "bg-gray-400"}`}>
            {data.score}
          </div>
        )}
      </div>

      {toast && (
        <div className={`fixed top-4 left-4 right-4 z-50 rounded-xl px-4 py-3 text-sm font-medium shadow-lg text-center ${toast.type === "ok" ? "bg-green-500 text-white" : "bg-red-500 text-white"}`}>
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
          <div className="bg-white rounded-xl shadow-sm p-4">
            <div className="flex items-start gap-3">
              <div className={`w-14 h-14 rounded-full flex items-center justify-center text-white font-black text-lg flex-shrink-0 ${SCORE_BG[data.score_color] ?? "bg-gray-400"}`}>
                {data.score}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-400">שלב נוכחי</p>
                <h2 className="text-xl font-black text-gray-900">{STAGE_LABELS[stage]}</h2>
                <div className="flex flex-wrap gap-2 mt-2">
                  {data.tier && <span className="text-xs px-2 py-1 bg-orange-50 text-orange-600 rounded-full font-medium">Tier: {data.tier}</span>}
                  <span className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded-full font-medium">{outcomeLabel(currentOutcome)}</span>
                  {data.status && <span className="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">טכני: {data.status}</span>}
                </div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-5 gap-1 text-center text-[10px] font-bold text-gray-400">
              {(["new", "followup", "qualified", "task", "closed"] as WorkflowStage[]).map((s) => (
                <div key={s} className={`rounded-full py-1 ${s === stage ? "bg-blue-500 text-white" : "bg-gray-100"}`}>
                  {STAGE_LABELS[s]}
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm p-3 flex flex-wrap gap-2 items-center">
            {data.domain && <span className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded-full font-medium">{data.domain}</span>}
            {data.source && <span className="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">מקור: {data.source}</span>}
            {ownerText && <span className="text-xs px-2 py-1 bg-gray-100 text-gray-500 rounded-full">אחראי: {ownerText}</span>}
            {data.phone && (
              <a href={`tel:${data.phone}`} className="text-xs px-2 py-1 bg-green-50 text-green-600 rounded-full font-medium" dir="ltr">
                {data.phone}
              </a>
            )}
            {data.created_at && <span className="text-xs text-gray-400 mr-auto">{data.created_at.slice(0, 10)}</span>}
          </div>

          <div className="bg-white rounded-xl shadow-sm p-4">
            <SectionHeader title="המלצת מערכת" sub="Next Action מוצג כהמלצה בלבד, לא כבחירה ידנית" />
            <p className="text-sm font-semibold text-gray-800">{nextAction}</p>
            {data.next_followup && <p className="text-xs text-gray-400 mt-1">פולואפ הבא: {data.next_followup}</p>}
          </div>

          {!terminal && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <SectionHeader title="הפעולה הבאה" sub="זרימה אחת: New → Followup → Qualified → Task/Meeting → Closed" />
              <div className="flex flex-col gap-2">
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={nextFollowup}
                    onChange={(e) => {
                      setNextFollowup(e.target.value);
                      setScheduleDirty(true);
                    }}
                    className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none"
                  />
                  <button
                    onClick={handleSetFollowup}
                    disabled={saving || (!scheduleDirty && currentOutcome === "needs_followup")}
                    className="bg-amber-500 text-white rounded-xl px-4 py-2 text-sm font-semibold disabled:opacity-40 active:opacity-80"
                  >
                    פולואפ
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={handleMarkQualified} disabled={saving} className="bg-blue-500 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40 active:opacity-80">
                    סמן כמתאים
                  </button>
                  <button onClick={handleMeetingBooked} disabled={saving} className="bg-violet-500 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40 active:opacity-80">
                    פגישה נקבעה
                  </button>
                </div>
                <button
                  onClick={() => setTaskOpen((o) => !o)}
                  className={`w-full rounded-xl py-2.5 text-sm font-semibold active:opacity-80 ${taskOpen ? "bg-indigo-500 text-white" : "bg-gray-100 text-gray-700"}`}
                >
                  {taskOpen ? "סגור יצירת משימה" : "צור משימה"}
                </button>
              </div>

              {taskOpen && (
                <div className="mt-3 flex flex-col gap-2 bg-gray-50 rounded-xl p-3 border border-gray-200">
                  <input
                    type="text"
                    value={taskTitle}
                    onChange={(e) => setTaskTitle(e.target.value)}
                    placeholder="כותרת משימה *"
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
                    {taskBusy ? "יוצר..." : "צור משימה"}
                  </button>
                </div>
              )}
            </div>
          )}

          {terminal && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <SectionHeader title="ליד סגור" sub="פעולות מכירה מוסתרות כדי למנוע מצב סותר" />
              <p className="text-sm text-gray-700">הליד נמצא בסטטוס סופי: {outcomeLabel(currentOutcome)}.</p>
              <div className="grid grid-cols-2 gap-2 mt-3">
                <button
                  onClick={() => historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
                  className="bg-gray-100 text-gray-700 rounded-xl py-2.5 text-sm font-semibold active:opacity-80"
                >
                  הצג היסטוריה
                </button>
                {isOwner && (
                  <button onClick={handleReopen} disabled={saving} className="bg-blue-500 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40 active:opacity-80">
                    פתח מחדש
                  </button>
                )}
              </div>
            </div>
          )}

          {!terminal && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <SectionHeader title="סגירת ליד" sub="Business Outcome הוא מקור האמת העסקי" />
              <div className="grid grid-cols-2 gap-2">
                {OUTCOMES.filter((o) => o.terminal).map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => handleOutcome(opt.key)}
                    disabled={saving}
                    className="text-xs py-2 px-3 rounded-lg font-medium text-right bg-gray-100 text-gray-700 active:bg-gray-200 disabled:opacity-50"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {data.summary && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-1">סיכום</p>
              <p className="text-sm text-gray-800 leading-relaxed">{data.summary}</p>
            </div>
          )}

          {aiAnswer && (
            <div className="bg-purple-50 border border-purple-100 rounded-xl p-4">
              <p className="text-xs text-purple-400 mb-1">BOSS AI</p>
              <p className="text-sm text-purple-900 leading-relaxed whitespace-pre-wrap">{aiAnswer}</p>
            </div>
          )}

          <div ref={historyRef} className="bg-white rounded-xl shadow-sm p-4">
            <p className="text-xs text-gray-400 mb-3">היסטוריה</p>
            {historyCount === 0 ? (
              <p className="text-sm text-gray-500">אין היסטוריה להצגה.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {data.timeline.map((entry, i) => (
                  <div key={i} className="flex gap-2 text-sm">
                    {entry.channel && <span className="text-gray-400 flex-shrink-0">[{readableHistory(entry.channel)}]</span>}
                    <span className="text-gray-700">{readableHistory(entry.summary)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {isOwner && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <button onClick={() => setAdvancedOpen((o) => !o)} className="w-full text-right text-sm font-bold text-gray-700">
                Advanced
              </button>
              {advancedOpen && (
                <div className="mt-3 flex gap-2 items-end">
                  <div className="flex-1">
                    <label className="text-xs text-gray-400 block mb-1">Score override (0-100)</label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      value={scoreInput}
                      onChange={(e) => {
                        setScoreInput(e.target.value);
                        setScoreDirty(true);
                      }}
                      className="w-full bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none"
                    />
                    <p className="text-xs text-gray-400 mt-1">Tier הוא read-only ומחושב אוטומטית.</p>
                  </div>
                  <button onClick={handleSaveScore} disabled={saving || !scoreDirty} className="bg-blue-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-80">
                    שמור
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {data && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 pt-2.5 pb-4 flex flex-col gap-2 shadow-xl" dir="rtl">
          {terminal ? (
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => historyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} className="bg-gray-100 text-gray-700 rounded-xl py-2.5 text-sm font-semibold active:opacity-80">
                היסטוריה
              </button>
              {isOwner && (
                <button onClick={handleReopen} disabled={saving} className="bg-blue-500 text-white rounded-xl py-2.5 text-sm font-semibold disabled:opacity-40 active:opacity-80">
                  פתח מחדש
                </button>
              )}
            </div>
          ) : (
            <>
              <p className="text-xs text-gray-400">
                <span className="font-semibold text-gray-500">הערה</span>
                <span className="text-gray-300 mx-1">·</span>
                נרשמת כהיסטוריה בלבד, לא משנה סטטוס
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleFollowupNote()}
                  placeholder="כתוב הערה..."
                  className="flex-1 bg-gray-100 rounded-xl px-3 py-2 text-sm outline-none placeholder-gray-400"
                />
                <button onClick={handleFollowupNote} disabled={noteBusy || !note.trim()} className="bg-gray-700 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70">
                  {noteBusy ? "..." : "שלח"}
                </button>
                <button
                  onClick={() => {
                    setAiOpen((o) => !o);
                    setAiAnswer(null);
                  }}
                  className={`rounded-xl px-3 py-2 text-sm font-medium transition-colors ${aiOpen ? "bg-purple-500 text-white" : "bg-gray-100 text-gray-600 active:bg-gray-200"}`}
                  aria-label="Ask AI"
                >
                  AI
                </button>
              </div>
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
                  <button onClick={handleAskAI} disabled={aiBusy || !aiQuestion.trim()} className="bg-purple-500 text-white rounded-xl px-4 py-2 text-sm font-medium disabled:opacity-40 active:opacity-70 min-w-[52px]">
                    {aiBusy ? "..." : "שאל"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
