import { useEffect, useState, type CSSProperties } from "react";
import { createOwnerTask, extendTaskDeadline, fetchMyWork, updateTaskStatus } from "../api";
import type { MyWorkResponse, TaskCadence, TaskWorkItem } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: MyWorkResponse }
  | { status: "error"; code?: number; message: string };

// החלוקה היחידה: Topic (אפשרויות קיימות בשדה Topic של Tasks).
const TOPICS = [
  { label: "שיווק", emoji: "📣" },
  { label: "מכירות", emoji: "🤝" },
  { label: "שירות", emoji: "💬" },
  { label: "תפעול", emoji: "⚙️" },
  { label: "כספים", emoji: "💰" },
  { label: "אדמיניסטרציה", emoji: "📋" },
  { label: "מערכת", emoji: "🖥️" },
  { label: "למידה", emoji: "📚" },
] as const;

const CADENCES: { id: TaskCadence; label: string }[] = [
  { id: "once", label: "חד-פעמית" },
  { id: "daily", label: "יומית" },
  { id: "weekly", label: "שבועית" },
  { id: "monthly", label: "חודשית" },
];

const CADENCE_LABEL: Record<string, string> = {
  Daily: "🔁 יומית",
  Weekly: "🔁 שבועית",
  Monthly: "🔁 חודשית",
};

type TaskKind = "continue" | "recurring" | "deadline";

const KINDS: { id: TaskKind; label: string }[] = [
  { id: "continue", label: "ממשיכה עד לביצוע" },
  { id: "recurring", label: "חוזרת" },
  { id: "deadline", label: "עם מועד אחרון" },
];

const RECURRING_CADENCES = CADENCES.filter((c) => c.id !== "once");

function isoPlusDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const DEADLINE_SHORTCUTS = [
  { label: "היום", days: 0 },
  { label: "3 ימים", days: 2 },
  { label: "שבוע", days: 6 },
];

function NewTaskForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState<string | null>(null);
  const [kind, setKind] = useState<TaskKind>("continue");
  const [cadence, setCadence] = useState<TaskCadence>("daily");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // שבועית/חודשית דורשות תאריך התחלה (עוגן); יומית ברירת מחדל = היום.
  const needsDate = kind === "deadline" || (kind === "recurring" && (cadence === "weekly" || cadence === "monthly"));
  const canSubmit = !!title.trim() && (!needsDate || !!dueDate) && !saving;

  const submit = () => {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    createOwnerTask({
      title: title.trim(),
      topic: topic ?? undefined,
      cadence: kind === "recurring" ? cadence : "once",
      kind: kind === "deadline" ? "deadline" : undefined,
      due_date: dueDate || undefined,
    })
      .then(() => {
        setTitle("");
        setTopic(null);
        setKind("continue");
        setCadence("daily");
        setDueDate("");
        setOpen(false);
        onCreated();
      })
      .catch((e: unknown) => setError((e as Error).message || "היצירה נכשלה"))
      .finally(() => setSaving(false));
  };

  if (!open) {
    return (
      <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => setOpen(true)}>
        ＋ משימה חדשה
      </button>
    );
  }

  const chip = (active: boolean): CSSProperties => ({
    padding: "4px 10px",
    borderRadius: 20,
    fontSize: 12,
    fontWeight: 600,
    border: `1.5px solid ${active ? "#22c55e" : "#374151"}`,
    background: active ? "#052e16" : "transparent",
    color: active ? "#22c55e" : "#9ca3af",
    cursor: "pointer",
    fontFamily: "inherit",
  });

  return (
    <Surface className="my-work-new">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="מה צריך לעשות?"
        aria-label="כותרת המשימה"
        style={{ width: "100%", padding: 10, borderRadius: 10, border: "1.5px solid #374151", background: "transparent", color: "inherit", fontSize: 14, fontFamily: "inherit", direction: "rtl", marginBottom: 10 }}
      />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
        {TOPICS.map((t) => (
          <button key={t.label} type="button" style={chip(topic === t.label)} onClick={() => setTopic(topic === t.label ? null : t.label)}>
            {t.emoji} {t.label}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
        {KINDS.map((k) => (
          <button key={k.id} type="button" style={chip(kind === k.id)} onClick={() => setKind(k.id)}>
            {k.label}
          </button>
        ))}
      </div>
      {kind === "recurring" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {RECURRING_CADENCES.map((c) => (
            <button key={c.id} type="button" style={chip(cadence === c.id)} onClick={() => setCadence(c.id)}>
              {c.label}
            </button>
          ))}
        </div>
      )}
      {kind === "deadline" && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
          {DEADLINE_SHORTCUTS.map((s) => (
            <button key={s.label} type="button" style={chip(dueDate === isoPlusDays(s.days))} onClick={() => setDueDate(isoPlusDays(s.days))}>
              {s.label}
            </button>
          ))}
        </div>
      )}
      <label style={{ display: "block", fontSize: 12, marginBottom: 10 }}>
        {kind === "deadline"
          ? "עד מתי? (היום האחרון)"
          : needsDate
            ? "תאריך התחלה (חובה)"
            : kind === "recurring"
              ? "מתחילה מ- (ברירת מחדל: היום)"
              : "תאריך יעד (אופציונלי)"}
        <input
          type="date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
          style={{ display: "block", marginTop: 4, padding: 8, borderRadius: 8, border: "1.5px solid #374151", background: "transparent", color: "inherit", fontFamily: "inherit" }}
        />
      </label>
      {error && <p className="my-work-card__error">⚠️ {error}</p>}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={!canSubmit} onClick={submit}>
          {saving ? "שומר…" : "הוסף משימה"}
        </button>
        <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setOpen(false)}>
          ביטול
        </button>
      </div>
    </Surface>
  );
}

function TaskCard({
  task,
  isUpdating,
  errorMessage,
  onMarkDone,
  onExtend,
}: {
  task: TaskWorkItem;
  isUpdating: boolean;
  errorMessage?: string;
  onMarkDone: () => void;
  onExtend: (days: number) => void;
}) {
  const missed = task.deadline === "missed";
  const lastDay = task.deadline === "last_day";
  return (
    <div
      className={`my-work-card${task.overdue ? " my-work-card--overdue" : ""}`}
      style={lastDay ? { borderColor: "#f97316", boxShadow: "0 0 0 1.5px #f97316" } : undefined}
    >
      <div className="my-work-card__topline">
        {missed && <StatusBadge tone="danger">פספסת</StatusBadge>}
        {lastDay && <StatusBadge tone="danger">⏳ אחרון היום</StatusBadge>}
        {task.deadline === "active" && <StatusBadge tone="neutral">עם מועד אחרון</StatusBadge>}
        {task.overdue && !missed && <StatusBadge tone="danger">דחוף</StatusBadge>}
        {task.topic && <StatusBadge tone="neutral">{task.topic}</StatusBadge>}
        {task.cadence && CADENCE_LABEL[task.cadence] && <StatusBadge tone="neutral">{CADENCE_LABEL[task.cadence]}</StatusBadge>}
        {task.domain && <StatusBadge tone="neutral">{task.domain}</StatusBadge>}
      </div>
      <h3>{task.title}</h3>
      {task.description && <p>{task.description}</p>}
      {task.due_date && <p className="my-work-card__due">📅 {task.due_date}</p>}
      {task.actionable && (
        <button
          type="button"
          onClick={onMarkDone}
          disabled={isUpdating}
          className="boss-button boss-button--quiet boss-bubble--action my-work-card__action"
        >
          {isUpdating ? "מעדכן…" : "✓ סמן כבוצע"}
        </button>
      )}
      {missed && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 12 }}>הארך:</span>
          {[{ l: "מחר", d: 1 }, { l: "3 ימים", d: 3 }, { l: "שבוע", d: 7 }].map((o) => (
            <button key={o.d} type="button" disabled={isUpdating} onClick={() => onExtend(o.d)}
              className="boss-button boss-button--quiet boss-bubble--action">{o.l}</button>
          ))}
        </div>
      )}
      {errorMessage && <p className="my-work-card__error">⚠️ {errorMessage}</p>}
    </div>
  );
}

export function MyWork({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);
  const [taskErrors, setTaskErrors] = useState<Record<string, string>>({});

  const load = () => {
    setState({ status: "loading" });
    fetchMyWork()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => {
        const error = e as Error & { status?: number };
        setState({
          status: "error",
          code: error.status,
          message: error.message,
        });
      });
  };

  useEffect(() => {
    load();
  }, []);

  const handleMarkDone = (task: { stable_key: string }) => {
    if (updatingKey) return; // one in-flight mutation at a time — prevents duplicate clicks
    setUpdatingKey(task.stable_key);
    setTaskErrors((prev) => {
      const { [task.stable_key]: _drop, ...rest } = prev;
      return rest;
    });
    updateTaskStatus(task.stable_key, "done")
      .then(() => {
        // Backend confirmed persistence — refetch from source of truth
        // rather than optimistically editing local state.
        setUpdatingKey(null);
        load();
      })
      .catch((e: unknown) => {
        const error = e as Error;
        setUpdatingKey(null);
        // Keep the task visible; surface the failure, never claim success.
        setTaskErrors((prev) => ({ ...prev, [task.stable_key]: error.message || "העדכון נכשל" }));
      });
  };

  const handleExtend = (task: { stable_key: string }, days: number) => {
    if (updatingKey) return;
    setUpdatingKey(task.stable_key);
    setTaskErrors((prev) => {
      const { [task.stable_key]: _drop, ...rest } = prev;
      return rest;
    });
    extendTaskDeadline(task.stable_key, isoPlusDays(days))
      .then(() => {
        setUpdatingKey(null);
        load();
      })
      .catch((e: unknown) => {
        setUpdatingKey(null);
        setTaskErrors((prev) => ({ ...prev, [task.stable_key]: (e as Error).message || "ההארכה נכשלה" }));
      });
  };

  if (state.status === "loading") {
    return (
      <main className="ventures-screen my-work-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} title="העבודה שלי" eyebrow="BOSS" />
          <ScreenState state="loading" title="טוען את המשימות שלך" message="אוסף את התמונה העדכנית…" />
        </div>
      </main>
    );
  }

  if (state.status === "error") {
    const forbidden = state.code === 401 || state.code === 403;
    return (
      <main className="ventures-screen my-work-screen">
        <div className="ventures-shell">
          <PageHeader onBack={onBack} title="העבודה שלי" eyebrow="BOSS" />
          <ScreenState
            state="error"
            title={forbidden ? "אין הרשאה" : "לא הצלחנו לטעון"}
            message={forbidden ? "זה זמין לבעלים בלבד." : "אפשר לנסות שוב בעוד רגע."}
            action={
              !forbidden && (
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={load}>
                  נסו שוב
                </button>
              )
            }
          />
        </div>
      </main>
    );
  }

  const { data } = state;
  const immediateCount = data.immediate.length;
  const upcomingCount = data.upcoming.length;
  const isEmpty = immediateCount === 0 && upcomingCount === 0;

  return (
    <main className="ventures-screen my-work-screen">
      <div className="ventures-shell">
        <PageHeader
          onBack={onBack}
          title="העבודה שלי"
          eyebrow="BOSS"
          subtitle={`${immediateCount} דחוף • ${upcomingCount} בהמשך`}
          action={
            <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={load}>
              רענון
            </button>
          }
        />

        <div className="my-work-stack">
          <NewTaskForm onCreated={load} />
          <div className="my-work-summary">
            <Surface className="my-work-stat">
              <p className="my-work-stat__value my-work-stat__value--urgent">{immediateCount}</p>
              <p className="my-work-stat__label">לטיפול עכשיו</p>
            </Surface>
            <Surface className="my-work-stat">
              <p className="my-work-stat__value my-work-stat__value--upcoming">{upcomingCount}</p>
              <p className="my-work-stat__label">בהמשך</p>
            </Surface>
          </div>

          {isEmpty && (
            <ScreenState state="empty" title="אין משימות לעכשיו" message="אתה צלול! ✨" />
          )}

          {immediateCount > 0 && (
            <section className="my-work-section" aria-labelledby="my-work-immediate-heading">
              <h2 id="my-work-immediate-heading" className="my-work-section__heading">לטיפול עכשיו</h2>
              <div className="my-work-list">
                {data.immediate.map((task) => (
                  <TaskCard
                    key={task.stable_key}
                    task={task}
                    isUpdating={updatingKey === task.stable_key}
                    errorMessage={taskErrors[task.stable_key]}
                    onMarkDone={() => handleMarkDone(task)}
                    onExtend={(days) => handleExtend(task, days)}
                  />
                ))}
              </div>
            </section>
          )}

          {upcomingCount > 0 && (
            <section className="my-work-section" aria-labelledby="my-work-upcoming-heading">
              <h2 id="my-work-upcoming-heading" className="my-work-section__heading">בהמשך</h2>
              <div className="my-work-list">
                {data.upcoming.map((task) => (
                  <TaskCard
                    key={task.stable_key}
                    task={task}
                    isUpdating={updatingKey === task.stable_key}
                    errorMessage={taskErrors[task.stable_key]}
                    onMarkDone={() => handleMarkDone(task)}
                    onExtend={(days) => handleExtend(task, days)}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
