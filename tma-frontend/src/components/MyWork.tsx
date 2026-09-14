import { useEffect, useState } from "react";
import { fetchMyWork, updateTaskStatus } from "../api";
import type { MyWorkResponse, TaskWorkItem } from "../types";
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

function TaskCard({
  task,
  isUpdating,
  errorMessage,
  onMarkDone,
}: {
  task: TaskWorkItem;
  isUpdating: boolean;
  errorMessage?: string;
  onMarkDone: () => void;
}) {
  return (
    <div className={`my-work-card${task.overdue ? " my-work-card--overdue" : ""}`}>
      <div className="my-work-card__topline">
        {task.overdue && <StatusBadge tone="danger">דחוף</StatusBadge>}
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
