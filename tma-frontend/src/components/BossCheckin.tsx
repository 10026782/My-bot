// BossCheckin.tsx — BOSS Daily Operating Screen (Production-Ready)
// Work Creates Game. Game Never Creates Work.
// Visual style intentionally unchanged from prototype — only data layer upgraded.

import { useState, useEffect } from "react";

// ─── Constants ────────────────────────────────────────────────────────────────

const TOPICS = [
  { id: "marketing", label: "שיווק",         emoji: "📣" },
  { id: "sales",     label: "מכירות",        emoji: "🤝" },
  { id: "service",   label: "שירות",         emoji: "💬" },
  { id: "ops",       label: "תפעול",         emoji: "⚙️" },
  { id: "finance",   label: "כספים",         emoji: "💰" },
  { id: "admin",     label: "אדמיניסטרציה",  emoji: "📋" },
  { id: "system",    label: "מערכת",         emoji: "🖥️" },
  { id: "learning",  label: "למידה",         emoji: "📚" },
] as const;

// Urgency: HOW important is this right now?
const URGENCY = [
  { id: "burning",     label: "בוער",   emoji: "🔥" },
  { id: "roadmap",     label: "רואדמאפ", emoji: "🗺" },
  { id: "maintenance", label: "תחזוקה", emoji: "📋" },
] as const;

// Source: WHERE did this task come from?
const SOURCE = [
  { id: "burning_today", label: "היום",       emoji: "🔥" },
  { id: "roadmap",       label: "רואדמאפ",   emoji: "🗺" },
  { id: "timeline",      label: "לוח זמנים", emoji: "📅" },
  { id: "maintenance",   label: "תחזוקה",    emoji: "🔧" },
] as const;

type TopicId   = typeof TOPICS[number]["id"];
type UrgencyId = typeof URGENCY[number]["id"];
type SourceId  = typeof SOURCE[number]["id"];

// ─── Task Model ───────────────────────────────────────────────────────────────

interface Task {
  id:                   string;
  title:                string;
  topic:                TopicId | null;
  urgency:              UrgencyId | null;
  source:               SourceId | null;
  required:             boolean;
  xp:                   number;   // auto-calculated — never set manually
  status:               "todo" | "done";
  due_date:             string | null;
  completed_at:         string | null;
  carry_over_candidate: boolean;
}

function makeEmptyTask(): Task {
  return {
    id:                   crypto.randomUUID(),
    title:                "",
    topic:                null,
    urgency:              null,
    source:               null,
    required:             false,
    xp:                   25,
    status:               "todo",
    due_date:             null,
    completed_at:         null,
    carry_over_candidate: false,
  };
}

// ─── XP Calculation ───────────────────────────────────────────────────────────

function calculateXP(task: Pick<Task, "required" | "urgency" | "source">): number {
  let xp = 25; // base
  if (task.required)                     xp += 25;
  if (task.urgency === "burning")        xp += 50;
  else if (task.urgency === "roadmap")   xp += 25;
  else if (task.urgency === "maintenance") xp += 10;
  if (task.source === "roadmap")         xp += 15;
  else if (task.source === "timeline")   xp += 15;
  return Math.min(xp, 200);
}

// ─── Integration-Ready Data Layer (mock — wire to Airtable when ready) ────────

async function loadTodayTasks(): Promise<Task[]> {
  // TODO: GET /api/tasks?date=today&status=todo&limit=3
  // Returns up to 3 tasks sorted by priority.
  // If Tasks table is empty for today, create 3 blank stubs.
  return [makeEmptyTask(), makeEmptyTask(), makeEmptyTask()];
}

async function saveTaskUpdate(task: Task): Promise<void> {
  // TODO: PATCH /api/tasks/{task.id}
  // Fields: title, topic, urgency, source, required, xp
  void task;
}

async function markTaskDone(task: Task): Promise<void> {
  // TODO: PATCH /api/tasks/{task.id} with { status: "Done", completed_at, xp }
  // TODO: POST /api/coins_log { action: task.title, coins: task.xp, date: today, quest: [task.id] }
  void task;
}

async function resetDay(incompleteTasks: Task[]): Promise<void> {
  // TODO: for each incompleteTask — PATCH /api/tasks/{id} with { carry_over_candidate: true }
  // TODO: POST /api/daily_checkins with { date: today, summary, total_xp, carry_over_count }
  void incompleteTasks;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function TaskCard({
  task, index, onChange, onDone,
}: {
  task: Task;
  index: number;
  onChange: (updated: Task) => void;
  onDone: (index: number) => void;
}) {
  const isDone = task.status === "done";
  const xp     = calculateXP(task);
  const canComplete = !!(task.title && task.topic && task.urgency && task.source);

  function update(patch: Partial<Task>) {
    if (isDone) return;
    const updated = { ...task, ...patch };
    updated.xp = calculateXP(updated);
    onChange(updated);
  }

  return (
    <div style={{
      background:   isDone ? "#0a1a0a" : "#0d1117",
      border:       `1.5px solid ${isDone ? "#22c55e33" : "#1f2937"}`,
      borderRadius: 16,
      padding:      "18px 16px",
      marginBottom: 12,
      transition:   "all 0.3s ease",
      opacity:      isDone ? 0.65 : 1,
    }}>
      {/* Title row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <div style={{
          width:          26, height: 26, borderRadius: "50%",
          background:     isDone ? "#22c55e" : "#1f2937",
          border:         `2px solid ${isDone ? "#22c55e" : "#374151"}`,
          display:        "flex", alignItems: "center", justifyContent: "center",
          fontSize:       12, fontWeight: 700,
          color:          isDone ? "#000" : "#6b7280", flexShrink: 0,
        }}>{isDone ? "✓" : index + 1}</div>
        <input
          value={task.title}
          onChange={e => update({ title: e.target.value })}
          placeholder="מה עושים היום?"
          disabled={isDone}
          style={{
            flex:           1, background: "transparent", border: "none", outline: "none",
            color:          isDone ? "#374151" : "#f9fafb", fontSize: 14, fontWeight: 600,
            textDecoration: isDone ? "line-through" : "none",
            fontFamily:     "inherit", direction: "rtl",
          }}
        />
      </div>

      {/* Urgency */}
      <div style={{ fontSize: 10, color: "#4b5563", fontWeight: 700, marginBottom: 4, letterSpacing: 1 }}>
        דחיפות
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {URGENCY.map(u => (
          <button key={u.id}
            onClick={() => update({ urgency: task.urgency === u.id ? null : u.id })}
            style={{
              padding:    "4px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
              border:     `1.5px solid ${task.urgency === u.id ? "#f97316" : "#1f2937"}`,
              background: task.urgency === u.id ? "#1a0a00" : "transparent",
              color:      task.urgency === u.id ? "#f97316" : "#4b5563",
              cursor:     isDone ? "default" : "pointer", transition: "all 0.2s", fontFamily: "inherit",
            }}>{u.emoji} {u.label}</button>
        ))}
      </div>

      {/* Source */}
      <div style={{ fontSize: 10, color: "#4b5563", fontWeight: 700, marginBottom: 4, letterSpacing: 1 }}>
        מקור
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {SOURCE.map(s => (
          <button key={s.id}
            onClick={() => update({ source: task.source === s.id ? null : s.id })}
            style={{
              padding:    "4px 10px", borderRadius: 20, fontSize: 12, fontWeight: 600,
              border:     `1.5px solid ${task.source === s.id ? "#38bdf8" : "#1f2937"}`,
              background: task.source === s.id ? "#001a2e" : "transparent",
              color:      task.source === s.id ? "#38bdf8" : "#4b5563",
              cursor:     isDone ? "default" : "pointer", transition: "all 0.2s", fontFamily: "inherit",
            }}>{s.emoji} {s.label}</button>
        ))}
      </div>

      {/* Topic */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 12 }}>
        {TOPICS.map(t => (
          <button key={t.id}
            onClick={() => update({ topic: task.topic === t.id ? null : t.id })}
            style={{
              padding:    "3px 9px", borderRadius: 20, fontSize: 11, fontWeight: 600,
              border:     `1.5px solid ${task.topic === t.id ? "#22c55e" : "#1f2937"}`,
              background: task.topic === t.id ? "#052e16" : "transparent",
              color:      task.topic === t.id ? "#22c55e" : "#4b5563",
              cursor:     isDone ? "default" : "pointer", transition: "all 0.2s", fontFamily: "inherit",
            }}>{t.emoji} {t.label}</button>
        ))}
      </div>

      {/* Footer: required + XP preview + done button */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <button
          onClick={() => update({ required: !task.required })}
          style={{
            padding:    "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700,
            border:     `1.5px solid ${task.required ? "#f59e0b" : "#1f2937"}`,
            background: task.required ? "#1c1200" : "transparent",
            color:      task.required ? "#f59e0b" : "#4b5563",
            cursor:     isDone ? "default" : "pointer", transition: "all 0.2s", fontFamily: "inherit",
          }}>{task.required ? "⚡ חובה" : "◯ רשות"}</button>

        {/* Auto XP preview */}
        <div style={{
          padding:    "3px 10px", borderRadius: 8, fontSize: 11, fontWeight: 800,
          background: "#0f0f2d",
          color:      isDone ? "#818cf8" : xp > 50 ? "#a78bfa" : "#6366f1",
          border:     `1.5px solid ${isDone ? "#818cf8" : "#312e81"}`,
          fontVariantNumeric: "tabular-nums",
          textShadow: xp >= 100 ? "0 0 8px #818cf844" : "none",
          transition: "all 0.3s",
        }}>+{xp} XP</div>

        {!isDone && (
          <button onClick={() => canComplete && onDone(index)}
            style={{
              marginRight: "auto", padding: "5px 14px", borderRadius: 20,
              background:  canComplete ? "#22c55e" : "#1f2937",
              color:       canComplete ? "#000" : "#374151",
              border:      "none", fontSize: 12, fontWeight: 700,
              cursor:      canComplete ? "pointer" : "default",
              transition:  "all 0.2s", fontFamily: "inherit",
            }}>✓ בוצע</button>
        )}
      </div>

      {/* Validation hint */}
      {!isDone && task.title && !(task.topic && task.urgency && task.source) && (
        <div style={{ marginTop: 8, fontSize: 10, color: "#4b5563" }}>
          {!task.urgency && "· בחר דחיפות "}
          {!task.source  && "· בחר מקור "}
          {!task.topic   && "· בחר עולם"}
        </div>
      )}
    </div>
  );
}

function WorldHealth({ tasks }: { tasks: Task[] }) {
  // Only real data from completed tasks — no fake initial values
  const doneTasks = tasks.filter(t => t.status === "done" && t.topic);
  const counts: Partial<Record<TopicId, number>> = {};
  const xpByTopic: Partial<Record<TopicId, number>> = {};

  doneTasks.forEach(t => {
    if (!t.topic) return;
    counts[t.topic]    = (counts[t.topic] || 0) + 1;
    xpByTopic[t.topic] = (xpByTopic[t.topic] || 0) + t.xp;
  });

  const hasActivity = doneTasks.length > 0;

  return (
    <div style={{
      background: "#0d1117", border: "1.5px solid #1f2937",
      borderRadius: 14, padding: "14px 16px", marginBottom: 16,
    }}>
      <div style={{ fontSize: 11, color: "#4b5563", fontWeight: 700, marginBottom: 10, letterSpacing: 1 }}>
        בריאות עולמות
      </div>
      {!hasActivity ? (
        <div style={{ fontSize: 12, color: "#374151", textAlign: "center", padding: "8px 0" }}>
          אין פעילות היום עדיין
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
          {TOPICS.map(t => {
            const done = counts[t.id] || 0;
            if (done === 0) return null;
            // Each completed task in this topic = +20% (cap at 100)
            const pct   = Math.min(100, done * 20 + Math.round((xpByTopic[t.id] || 0) / 10));
            const color = pct >= 75 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
            return (
              <div key={t.id}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: "#6b7280" }}>{t.emoji} {t.label}</span>
                  <span style={{ fontSize: 11, fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>{pct}%</span>
                </div>
                <div style={{ height: 4, background: "#1f2937", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2, transition: "width 0.6s ease" }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface Props {
  onBack: () => void;
  streak?: number;
}

export function BossCheckin({ onBack, streak = 0 }: Props) {
  const [tasks,   setTasks]   = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    loadTodayTasks()
      .then(setTasks)
      .finally(() => setLoading(false));
  }, []);

  const doneTasks      = tasks.filter(t => t.status === "done");
  const totalXP        = doneTasks.reduce((s, t) => s + t.xp, 0);
  const allDone        = tasks.length > 0 && tasks.every(t => t.status === "done");
  const burningCount   = doneTasks.filter(t => t.urgency === "burning").length;
  const roadmapCount   = doneTasks.filter(t => t.urgency === "roadmap").length;
  const requiredCount  = doneTasks.filter(t => t.required).length;
  const optionalCount  = doneTasks.filter(t => !t.required).length;

  const today = new Date().toLocaleDateString("he-IL", {
    weekday: "long", day: "numeric", month: "long",
  });

  function handleChange(index: number, updated: Task) {
    setTasks(prev => prev.map((t, i) => i === index ? updated : t));
    saveTaskUpdate(updated);
  }

  function handleDone(index: number) {
    const task = tasks[index];
    if (!task.title || !task.topic || !task.urgency || !task.source) return;
    const completedAt = new Date().toISOString();
    const finalXP     = calculateXP(task);
    const updated: Task = { ...task, status: "done", completed_at: completedAt, xp: finalXP };
    setTasks(prev => prev.map((t, i) => i === index ? updated : t));
    markTaskDone(updated);
  }

  function handleReset() {
    const incomplete = tasks.filter(t => t.status === "todo");
    // Mark incomplete tasks as carry-over candidates before resetting
    const withCarryOver = incomplete.map(t => ({ ...t, carry_over_candidate: true }));
    resetDay(withCarryOver);
    loadTodayTasks().then(setTasks);
  }

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#030712", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ color: "#4b5563", fontSize: 13 }}>טוען...</div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#030712", fontFamily: "'Segoe UI', Arial, sans-serif", direction: "rtl", padding: "20px 16px" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <button onClick={onBack} style={{
                background: "transparent", border: "none", color: "#4b5563",
                fontSize: 13, cursor: "pointer", padding: 0, fontFamily: "inherit",
              }}>← חזור</button>
              <div style={{ fontSize: 10, letterSpacing: 3, color: "#22c55e", fontWeight: 700 }}>BOSS · DAILY</div>
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#f9fafb" }}>מה 3 הדברים הבוערים?</div>
            <div style={{ fontSize: 12, color: "#4b5563", marginTop: 2 }}>{today}</div>
          </div>
          {streak > 0 && (
            <div style={{ textAlign: "center", background: "#0d1117", border: "1.5px solid #1f2937", borderRadius: 12, padding: "8px 14px" }}>
              <div style={{ fontSize: 20 }}>🔥</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: "#f97316", fontVariantNumeric: "tabular-nums" }}>{streak}</div>
              <div style={{ fontSize: 9, color: "#4b5563", fontWeight: 600 }}>ימי רצף</div>
            </div>
          )}
        </div>

        {/* Boss Battle — no fake progress */}
        <div style={{ background: "#0d0d1f", border: "1.5px solid #312e81", borderRadius: 14, padding: "14px 16px", marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 10, color: "#6366f1", fontWeight: 700, letterSpacing: 1 }}>🎯 BOSS השבוע</div>
              {/* TODO: fetch from Airtable Worlds table — show active world boss */}
              <div style={{ fontSize: 12, color: "#4b5563", marginTop: 4 }}>לא מחובר עדיין</div>
            </div>
            <div style={{ fontSize: 11, color: "#312e81", fontWeight: 700 }}>—</div>
          </div>
        </div>

        {/* XP Bar */}
        <div style={{
          background: "#0d1117", border: "1.5px solid #1f2937", borderRadius: 12,
          padding: "10px 14px", marginBottom: 16,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ fontSize: 11, color: "#4b5563" }}>{doneTasks.length}/{tasks.length} בוצעו</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 100, height: 5, background: "#1f2937", borderRadius: 3, overflow: "hidden" }}>
              <div style={{
                width:      `${tasks.length > 0 ? (doneTasks.length / tasks.length) * 100 : 0}%`,
                height:     "100%", background: "#22c55e", borderRadius: 3, transition: "width 0.5s ease",
              }} />
            </div>
            <span style={{
              fontSize: 14, fontWeight: 800, color: "#818cf8",
              fontVariantNumeric: "tabular-nums",
              textShadow: totalXP >= 100 ? "0 0 10px #818cf855" : "none",
            }}>+{totalXP} XP</span>
          </div>
        </div>

        {/* Three Things Rule: show note if more than 3 tasks pending */}
        {tasks.filter(t => t.status === "todo").length > 3 && (
          <div style={{ fontSize: 11, color: "#4b5563", textAlign: "center", marginBottom: 12, padding: "6px 12px", border: "1px solid #1f2937", borderRadius: 8 }}>
            יש עוד משימות — היום מוגבל ל-3
          </div>
        )}

        {/* Task Cards */}
        {tasks.slice(0, 3).map((task, i) => (
          <TaskCard key={task.id} task={task} index={i}
            onChange={(u) => handleChange(i, u)}
            onDone={handleDone}
          />
        ))}

        {/* World Health */}
        <WorldHealth tasks={tasks} />

        {/* Completion Screen */}
        {allDone && (
          <div style={{
            background: "#052e16", border: "1.5px solid #22c55e",
            borderRadius: 16, padding: "20px 18px", textAlign: "center", marginTop: 8,
          }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>🏆</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: "#22c55e", marginBottom: 12 }}>יום הושלם!</div>

            <div style={{ display: "flex", justifyContent: "center", gap: 16, marginBottom: 14 }}>
              {doneTasks.map((t, i) => {
                const topic = TOPICS.find(tp => tp.id === t.topic);
                return (
                  <div key={i} style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 18 }}>{topic?.emoji}</div>
                    <div style={{ fontSize: 10, color: "#4ade80", fontWeight: 600 }}>{topic?.label}</div>
                    <div style={{ fontSize: 9, color: "#166534" }}>
                      {t.urgency === "burning" ? "🔥" : t.urgency === "roadmap" ? "🗺" : "📋"}
                    </div>
                  </div>
                );
              })}
            </div>

            <div style={{ fontSize: 12, color: "#4b5563", marginBottom: 6 }}>
              {burningCount > 0 && `🔥 ${burningCount} בוערות`}
              {roadmapCount > 0 && ` · 🗺 ${roadmapCount} רואדמאפ`}
            </div>
            <div style={{ fontSize: 12, color: "#4b5563", marginBottom: 14 }}>
              ✓ {requiredCount} חובה · {optionalCount} רשות
            </div>

            <div style={{
              fontSize: 36, fontWeight: 900, color: "#818cf8",
              fontVariantNumeric: "tabular-nums",
              textShadow: "0 0 20px #818cf844",
            }}>+{totalXP} XP</div>
            {streak > 0 && (
              <div style={{ fontSize: 11, color: "#4b5563", marginTop: 4 }}>🔥 רצף: {streak + 1} ימים</div>
            )}
          </div>
        )}

        {allDone && (
          <button onClick={handleReset}
            style={{
              width: "100%", marginTop: 12, padding: "12px",
              background: "transparent", border: "1.5px solid #1f2937",
              borderRadius: 12, color: "#4b5563", fontSize: 13,
              cursor: "pointer", fontFamily: "inherit",
            }}>יום חדש →</button>
        )}
      </div>
    </div>
  );
}
