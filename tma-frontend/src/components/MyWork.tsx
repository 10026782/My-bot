import { useEffect, useState } from "react";
import { fetchMyWork, updateTaskStatus } from "../api";
import type { MyWorkResponse, TaskWorkItem } from "../types";
import { PageHeader } from "./ui/PageHeader";
import { ScreenState } from "./ui/ScreenState";

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
    <div className="bg-white rounded-lg shadow-sm p-4 mb-3">
      <div className="flex items-start gap-2 mb-2">
        {task.overdue && (
          <span className="inline-block bg-red-100 text-red-700 text-xs font-bold px-2 py-1 rounded">דחוף</span>
        )}
        {task.domain && (
          <span className="inline-block bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">{task.domain}</span>
        )}
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-1">{task.title}</h3>
      {task.description && (
        <p className="text-sm text-gray-600 mb-2 line-clamp-2">{task.description}</p>
      )}
      {task.due_date && (
        <p className="text-xs text-gray-400 mb-2">📅 {task.due_date}</p>
      )}
      {task.actionable && (
        <button
          type="button"
          onClick={onMarkDone}
          disabled={isUpdating}
          className="w-full mt-1 py-2 rounded-md bg-green-50 text-green-700 text-sm font-semibold active:bg-green-100 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isUpdating ? "מעדכן…" : "✓ סמן כבוצע"}
        </button>
      )}
      {errorMessage && (
        <p className="text-xs text-red-600 mt-2">⚠️ {errorMessage}</p>
      )}
    </div>
  );
}

export function MyWork({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [updatingKey, setUpdatingKey] = useState<string | null>(null);
  const [taskErrors, setTaskErrors] = useState<Record<string, string>>({});

  const load = () => {
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
      <div className="min-h-screen bg-gray-100">
        <PageHeader onBack={onBack} title="העבודה שלי" />
        <ScreenState state="loading" title="טוען..." message="אוסף את המשימות שלך…" />
      </div>
    );
  }

  if (state.status === "error") {
    const forbidden = state.code === 401 || state.code === 403;
    return (
      <div className="min-h-screen bg-gray-100">
        <PageHeader onBack={onBack} title="העבודה שלי" />
        <ScreenState
          state="error"
          title={forbidden ? "אין הרשאה" : "לא הצלחנו לטעון"}
          message={forbidden ? "זה זמין לבעלים בלבד." : "אפשר לנסות שוב בעוד רגע."}
        />
      </div>
    );
  }

  const { data } = state;
  const immediateCount = data.immediate.length;
  const upcomingCount = data.upcoming.length;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      <PageHeader onBack={onBack} title="העבודה שלי" subtitle={`${immediateCount} דחוף • ${upcomingCount} בהמשך`} />

      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 px-4 mb-4">
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-2xl font-black text-red-600">{immediateCount}</div>
          <div className="text-xs text-gray-600 mt-1">לטיפול עכשיו</div>
        </div>
        <div className="bg-white rounded-lg p-4 text-center">
          <div className="text-2xl font-black text-blue-600">{upcomingCount}</div>
          <div className="text-xs text-gray-600 mt-1">בהמשך</div>
        </div>
      </div>

      {/* Immediate Tasks */}
      {immediateCount > 0 && (
        <div className="px-4 mb-6">
          <h2 className="text-sm font-bold text-gray-900 mb-3">לטיפול עכשיו</h2>
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
      )}

      {/* Upcoming Tasks */}
      {upcomingCount > 0 && (
        <div className="px-4 mb-6">
          <h2 className="text-sm font-bold text-gray-900 mb-3">בהמשך</h2>
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
      )}

      {/* Empty State */}
      {immediateCount === 0 && upcomingCount === 0 && (
        <div className="px-4 mt-8 text-center">
          <p className="text-gray-400 text-sm">אין משימות לעכשיו</p>
          <p className="text-gray-300 text-xs mt-2">אתה צלול! ✨</p>
        </div>
      )}
    </div>
  );
}
